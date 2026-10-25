"""Alarm logic, threshold calibration, and evaluation metrics.

Alarm logic (shared by every detector so the comparison is fair):
  1. raw alarm when score > threshold
  2. alarm episodes = runs of raw alarms, with gaps <= `merge_gap` s merged,
     keeping only episodes lasting >= `min_dur` s (debounce, as real alarm systems do)
Thresholds are calibrated on held-out NORMAL data to a false-alarm budget
(alarm episodes per day); test labels are never used to set them.
"""
from __future__ import annotations

import numpy as np


def runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) index pairs of True runs."""
    m = np.asarray(mask, dtype=np.int8)
    d = np.diff(np.r_[0, m, 0])
    s = np.flatnonzero(d == 1)
    e = np.flatnonzero(d == -1) - 1
    return list(zip(s.tolist(), e.tolist()))


def episodes(score: np.ndarray, thr: float, merge_gap: int = 30, min_dur: int = 5):
    raw = runs(score > thr)
    merged = []
    for s, e in raw:
        if merged and s - merged[-1][1] - 1 <= merge_gap:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return [(s, e) for s, e in merged if e - s + 1 >= min_dur]


def alarm_mask(n: int, eps) -> np.ndarray:
    """Alarm is considered active from the moment the episode is confirmed (start + min_dur - 1)."""
    m = np.zeros(n, dtype=bool)
    for s, e in eps:
        m[s:e + 1] = True
    return m


def calibrate(scores: list[np.ndarray], hours: float, budget_per_day: float = 1.0,
              merge_gap: int = 30, min_dur: int = 5, grid: int = 200) -> float:
    """Lowest threshold whose alarm-episode rate on normal data is <= budget_per_day."""
    allv = np.concatenate([s[np.isfinite(s)] for s in scores])
    qs = np.unique(np.quantile(allv, np.linspace(0.90, 1.0, grid)))
    hi = allv.max() * 1.05 + 1e-9
    for t in list(qs) + [hi]:
        n = sum(len(episodes(s, t, merge_gap, min_dur)) for s in scores)
        if n / (hours / 24.0) <= budget_per_day:
            return float(t)
    return float(hi)


def evaluate(score, labels, thr, merge_gap=30, min_dur=5, grace=60):
    """Point-wise and event-wise metrics for one test file.

    Detection time of an episode is its confirmation time: start + min_dur - 1.
    TTD is measured from the labelled attack start to that confirmation time.
    """
    n = len(score)
    eps = episodes(score, thr, merge_gap, min_dur)
    pred = alarm_mask(n, eps)
    y = np.asarray(labels).astype(bool)
    tp = int((pred & y).sum()); fp = int((pred & ~y).sum()); fn = int((~pred & y).sum())
    events = runs(y)
    ev_rows = []
    covered = np.zeros(n, dtype=bool)
    for s, e in events:
        covered[s:min(n, e + grace + 1)] = True
    for i, (s, e) in enumerate(events):
        win_end = min(n - 1, e + grace)
        # an episode detects the event only if it is CONFIRMED inside [start, end + grace];
        # an alarm already active before the attack began gets no credit.
        det_times = [es + min_dur - 1 for es, ee in eps if s <= es + min_dur - 1 <= win_end]
        t0 = min(det_times) if det_times else None
        ev_rows.append({"event": i, "start_idx": s, "end_idx": e, "duration_s": e - s + 1,
                        "detected": t0 is not None,
                        "ttd_s": (t0 - s) if t0 is not None else None,
                        "first_alarm_idx": t0})
    false_eps = [(s, e) for s, e in eps if not covered[s:e + 1].any()]
    return {"tp": tp, "fp": fp, "fn": fn, "events": ev_rows,
            "n_episodes": len(eps), "false_episodes": len(false_eps), "n_seconds": n}


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f
