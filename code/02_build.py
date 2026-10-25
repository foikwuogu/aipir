#!/usr/bin/env python3
"""02 - Fit detectors on normal data, calibrate thresholds, score test files, evaluate.

For each HAI version:
  1. split every normal training file: first 80 % fit, last 20 % calibrate
  2. standardize with statistics of the fit portion (constant points dropped)
  3. fit D0-D3 and ablations; calibrate each threshold to the false-alarm budget on the
     calibration portion (labels never used)
  4. score development + held-out test files; evaluate point-wise and event-wise; route alarms
  5. false-alarm budget sweep and scoring throughput
Writes data/processed/* and paper/stats.json (section "results").
"""
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "framework"))

from aipir import config as C  # noqa: E402
from aipir.data import LABEL_COLS, Scaler, load_file, sensor_columns  # noqa: E402
from aipir.metrics import alarm_mask, calibrate, episodes, evaluate, prf, runs  # noqa: E402
from aipir.routing import attacked_processes, route  # noqa: E402

RAW = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "data", "processed")
MODELS = os.path.join(ROOT, "models")
STATS = os.path.join(ROOT, "paper", "stats.json")
BUDGETS = [0.25, 0.5, 1.0, 2.0, 4.0]


def normal_segments(df, pad):
    """Contiguous stretches with no attack label within `pad` seconds after any labelled second."""
    bad = df["attack"].to_numpy().astype(bool).copy()
    for s_, e_ in runs(bad):
        bad[s_:min(len(bad), e_ + pad + 1)] = True
    return [df.iloc[a:b + 1] for a, b in runs(~bad) if b - a + 1 >= 3600]


def alarm_params():
    return dict(merge_gap=C.MERGE_GAP_S, min_dur=C.MIN_DUR_S)


def run_version(ver, stats):
    print(f"== {ver}")
    full = [load_file(os.path.join(RAW, ver, f"{n}.csv.gz")) for n in C.TRAIN_FILES[ver]]
    # HAI 20.07 train2 carries two short attack-labelled segments; training must be normal
    # only, so labelled seconds (plus a recovery pad) split each file into normal segments.
    segs = [g for f in full for g in normal_segments(f, C.TRAIN_EXCLUDE_PAD_S)]
    fit = [g.iloc[:int(len(g) * C.FIT_FRACTION)] for g in segs]
    cal = [g.iloc[int(len(g) * C.FIT_FRACTION):] for g in segs]
    sc = Scaler().fit(fit, sensor_columns(fit[0]))
    zf = [sc.transform(f) for f in fit]
    zc = [sc.transform(f) for f in cal]
    cal_hours = sum(len(z) for z in zc) / 3600.0
    qa = {"train_rows": {n: len(f) for n, f in zip(C.TRAIN_FILES[ver], full)},
          "fit_rows": int(sum(len(z) for z in zf)), "cal_rows": int(sum(len(z) for z in zc)),
          "train_label_sum_raw": int(sum(f["attack"].sum() for f in full)),
          "train_label_sum": int(sum(g["attack"].sum() for g in fit + cal)),
          "train_rows_excluded": int(sum(len(f) for f in full) - sum(len(g) for g in segs)),
          "normal_segments": len(segs),
          "sensors_total": len(sensor_columns(fit[0])), "sensors_used": len(sc.cols_),
          "sensors_dropped_constant": sc.dropped_}

    dets = {**C.make_detectors(), **C.make_ablations()}
    thr, fit_s, cal_scores = {}, {}, {}
    for k, m in dets.items():
        t = time.time()
        m.fit(zf)
        cal_scores[k] = [m.score(z)[0] for z in zc]
        thr[k] = calibrate(cal_scores[k], cal_hours, C.FA_BUDGET_PER_DAY, **alarm_params())
        fit_s[k] = time.time() - t
        print(f"  fit {k}: thr={thr[k]:.4f} ({fit_s[k]:.0f}s)")
    cal_eps = {k: sum(len(episodes(s, thr[k], **alarm_params())) for s in v) for k, v in cal_scores.items()}

    files = [("dev", n) for n in C.DEV_FILES.get(ver, [])] + [("test", n) for n in C.TEST_FILES[ver]]
    ev_rows, file_rows, speed = [], [], {}
    for split, name in files:
        df = load_file(os.path.join(RAW, ver, f"{name}.csv.gz"))
        z = sc.transform(df)
        y = df["attack"].to_numpy()
        out = df[LABEL_COLS].copy()
        for k, m in dets.items():
            t = time.time()
            s, contrib = m.score(z)
            el = time.time() - t
            speed.setdefault(k, []).append((len(z), el))
            r = evaluate(s, y, thr[k], grace=C.GRACE_S, **alarm_params())
            out[f"score_{k}"] = s
            out[f"alarm_{k}"] = alarm_mask(len(s), episodes(s, thr[k], **alarm_params())).astype(np.int8)
            file_rows.append({"version": ver, "split": split, "file": name, "detector": k,
                              "tp": r["tp"], "fp": r["fp"], "fn": r["fn"], "seconds": r["n_seconds"],
                              "events": len(r["events"]), "events_detected": sum(e["detected"] for e in r["events"]),
                              "false_episodes": r["false_episodes"], "episodes": r["n_episodes"]})
            for e in r["events"]:
                row = {"version": ver, "split": split, "file": name, "detector": k, **e,
                       "start_time": str(df.index[e["start_idx"]]), "end_time": str(df.index[e["end_idx"]]),
                       "attacked": "+".join(sorted(attacked_processes(df, e["start_idx"], e["end_idx"])))}
                if e["detected"] and contrib is not None:
                    t0 = e["first_alarm_idx"]
                    vec = contrib[max(0, t0 - C.MIN_DUR_S + 1):t0 + 1].mean(0)
                    target, ranked = route(vec, sc.cols_)
                    row["routed"] = target
                    row["routing_correct"] = target in row["attacked"].split("+") if row["attacked"] else None
                    row["top_sensors"] = ";".join(n for n, _ in ranked)
                ev_rows.append(row)
        out.to_csv(os.path.join(OUT, f"scores_{ver}_{name}.csv.gz"), float_format="%.5g")
        print(f"  scored {split} {name}: {len(df)} s, {int(y.sum())} attack s")

    # false-alarm budget sweep on held-out tests (thresholds recalibrated on normal data only)
    sweep = []
    tests = [n for s, n in files if s == "test"]
    test_frames = {n: load_file(os.path.join(RAW, ver, f"{n}.csv.gz")) for n in tests}
    for k in ["D0", "D1", "D3"]:
        m = dets[k]
        tscores = {n: m.score(sc.transform(f))[0] for n, f in test_frames.items()}
        for b in BUDGETS:
            t_b = calibrate(cal_scores[k], cal_hours, b, **alarm_params())
            tp = fp = fn = ev = det = fa = 0
            secs = 0
            for n, f in test_frames.items():
                r = evaluate(tscores[n], f["attack"].to_numpy(), t_b, grace=C.GRACE_S, **alarm_params())
                tp += r["tp"]; fp += r["fp"]; fn += r["fn"]; fa += r["false_episodes"]; secs += r["n_seconds"]
                ev += len(r["events"]); det += sum(e["detected"] for e in r["events"])
            p, rc, f1 = prf(tp, fp, fn)
            sweep.append({"version": ver, "detector": k, "budget_per_day": b, "threshold": t_b,
                          "precision": p, "recall": rc, "f1": f1, "event_recall": det / ev,
                          "false_episodes_per_day": fa / (secs / 86400)})

    os.makedirs(MODELS, exist_ok=True)
    joblib.dump({"version": ver, "scaler": sc, "detector": dets["D3"], "threshold": thr["D3"],
                 "alarm": alarm_params(), "columns": sc.cols_},
                os.path.join(MODELS, f"aipir_{ver.replace('-', '').replace('.', '')}.joblib"))
    qa.update({"thresholds": thr, "cal_hours": cal_hours, "cal_episodes": cal_eps,
               "fit_seconds": fit_s,
               "throughput_rows_per_s": {k: sum(n for n, _ in v) / max(sum(t for _, t in v), 1e-9)
                                         for k, v in speed.items()}})
    return pd.DataFrame(ev_rows), pd.DataFrame(file_rows), pd.DataFrame(sweep), qa


def summarize(files, events):
    rows = []
    for (ver, split, k), g in files.groupby(["version", "split", "detector"]):
        p, r, f = prf(g.tp.sum(), g.fp.sum(), g.fn.sum())
        ev = events[(events.version == ver) & (events.split == split) & (events.detector == k)]
        det = ev[ev.detected]
        routed = det.dropna(subset=["routing_correct"]) if "routing_correct" in det else det.iloc[0:0]
        rows.append({"version": ver, "split": split, "detector": k,
                     "precision": p, "recall": r, "f1": f,
                     "events": len(ev), "events_detected": len(det), "event_recall": len(det) / len(ev),
                     "ttd_median_s": float(det.ttd_s.median()) if len(det) else None,
                     "ttd_mean_s": float(det.ttd_s.mean()) if len(det) else None,
                     "false_episodes": int(g.false_episodes.sum()),
                     "test_days": g.seconds.sum() / 86400,
                     "false_episodes_per_day": g.false_episodes.sum() / (g.seconds.sum() / 86400),
                     "routing_n": len(routed),
                     "routing_accuracy": float(routed.routing_correct.mean()) if len(routed) else None})
    return pd.DataFrame(rows)


def main():
    os.makedirs(OUT, exist_ok=True)
    allev, allf, allsw, qas = [], [], [], {}
    for ver in C.TRAIN_FILES:
        ev, f, sw, qa = run_version(ver, None)
        allev.append(ev); allf.append(f); allsw.append(sw); qas[ver] = qa
    ev = pd.concat(allev, ignore_index=True)
    f = pd.concat(allf, ignore_index=True)
    sw = pd.concat(allsw, ignore_index=True)
    summ = summarize(f, ev)
    ev.to_csv(os.path.join(OUT, "events.csv"), index=False)
    f.to_csv(os.path.join(OUT, "metrics_by_file.csv"), index=False)
    sw.to_csv(os.path.join(OUT, "fa_budget_sweep.csv"), index=False)
    summ.to_csv(os.path.join(OUT, "metrics_summary.csv"), index=False)
    with open(os.path.join(OUT, "qa_inputs.json"), "w") as fh:
        json.dump(qas, fh, indent=2, default=str)

    stats = json.load(open(STATS)) if os.path.exists(STATS) else {}
    stats["results"] = {f"{r.version}|{r.split}|{r.detector}": {k: (None if pd.isna(v) else v)
                        for k, v in r._asdict().items() if k not in ("Index",)}
                        for r in summ.itertuples()}
    stats["qa"] = qas
    os.makedirs(os.path.dirname(STATS), exist_ok=True)
    json.dump(stats, open(STATS, "w"), indent=2, default=float)
    print(summ.round(3).to_string())


if __name__ == "__main__":
    main()
