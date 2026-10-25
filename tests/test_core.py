"""Unit tests for alarm logic, metrics, routing and detectors (synthetic data; no HAI needed).

Run:  python -m pytest -q tests
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "framework"))

from aipir.detectors import AIPIRPredictive, StaticLimits, causal_mean, lag_features  # noqa: E402
from aipir.metrics import calibrate, episodes, evaluate, prf, runs  # noqa: E402
from aipir.routing import route  # noqa: E402


def test_runs():
    assert runs(np.array([0, 1, 1, 0, 1])) == [(1, 2), (4, 4)]
    assert runs(np.zeros(5)) == []


def test_episodes_debounce_and_merge():
    s = np.zeros(200)
    s[10:13] = 5          # 3 s: too short, dropped
    s[50:60] = 5          # 10 s
    s[70:80] = 5          # gap 10 s <= 30 -> merged with previous
    assert episodes(s, 1.0, merge_gap=30, min_dur=5) == [(50, 79)]


def test_evaluate_ttd_and_no_credit_for_preexisting_alarm():
    y = np.zeros(400, dtype=int); y[100:150] = 1; y[300:320] = 1
    s = np.zeros(400)
    s[110:140] = 5          # detects event 0, confirmation at 114 -> ttd 14
    s[280:330] = 5          # alarm started before event 1 -> no credit
    r = evaluate(s, y, 1.0, merge_gap=30, min_dur=5, grace=60)
    e0, e1 = r["events"]
    assert e0["detected"] and e0["ttd_s"] == 14
    assert not e1["detected"]


def test_false_episode_count():
    y = np.zeros(1000, dtype=int); y[100:110] = 1
    s = np.zeros(1000); s[500:520] = 5
    r = evaluate(s, y, 1.0)
    assert r["false_episodes"] == 1


def test_calibrate_respects_budget():
    rng = np.random.default_rng(0)
    s = rng.normal(size=86400)
    thr = calibrate([s], hours=24, budget_per_day=1.0)
    assert len(episodes(s, thr)) <= 1


def test_prf():
    assert prf(5, 5, 0) == (0.5, 1.0, 2 / 3)


def test_causal_mean_is_causal():
    a = np.arange(10, dtype=np.float32)[:, None]
    m = causal_mean(a, 3)
    assert m[0, 0] == 0 and m[1, 0] == 0.5 and m[5, 0] == 4.0


def test_lag_features_shape():
    z = np.arange(20, dtype=np.float32).reshape(10, 2)
    f = lag_features(z, [1, 3])
    assert f.shape == (10, 4) and f[5, 0] == z[4, 0] and f[5, 2] == z[2, 0]


def test_route_skips_hil_points():
    target, ranked = route(np.array([9.0, 3.0, 1.0]), ["P4_ST_PT01", "P2_SIT01", "P1_FT01"])
    assert target == "P2" and ranked[0][0] == "P4_ST_PT01"


def test_predictive_detector_flags_injected_fault():
    rng = np.random.default_rng(1)
    t = np.arange(20000)
    base = np.sin(t / 50.0)
    z = np.stack([base + 0.05 * rng.normal(size=t.size) for _ in range(6)], axis=1).astype(np.float32)
    m = AIPIRPredictive(stride=1, topk=2).fit([z[:15000]])
    test = z[15000:].copy()
    test[2000:2300, 3] += 3.0          # spoofed sensor
    s, contrib = m.score(test)
    assert s[2010:2290].mean() > 3 * s[:1500].mean()
    assert int(np.argmax(contrib[2100])) == 3


def test_static_limits():
    z = np.zeros((100, 2), dtype=np.float32); z[:, 0] = np.linspace(0, 1, 100)
    d = StaticLimits().fit([z])
    s, _ = d.score(np.array([[2.0, 0.0]], dtype=np.float32))
    assert s[0] > 0
