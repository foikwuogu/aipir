#!/usr/bin/env python3
"""07 - Lab-mode check of the runtime path: stream a full held-out file through the
StreamingScorer used by the service and compare its alarms and routing with the batch
pipeline. Writes data/processed/lab_check.json (and adds "lab_check" to stats.json)."""
import json, os, sys, time
import joblib, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "framework"))
from aipir.data import load_file  # noqa: E402
from aipir.streaming import StreamingScorer  # noqa: E402

FILE = "test4"
sc = StreamingScorer(joblib.load(os.path.join(ROOT, "models", "aipir_hai2103.joblib")))
df = load_file(os.path.join(ROOT, "data", "raw", "hai-21.03", f"{FILE}.csv.gz"))
t = time.time()
out = [sc.update(r) for r in df.to_dict("records")]
el = time.time() - t
on = np.array([o["alarm"] for o in out]); batch = pd.read_csv(os.path.join(ROOT, "data", "processed", f"scores_hai-21.03_{FILE}.csv.gz"))["alarm_D3"].to_numpy().astype(bool)
y = df["attack"].to_numpy().astype(bool)
ev = pd.read_csv(os.path.join(ROOT, "data", "processed", "events.csv"))
ev = ev[(ev.file == FILE) & (ev.version == "hai-21.03") & (ev.detector == "D3")]
first_on = [int(np.argmax(on[s:e + 61])) if on[s:e + 61].any() else None for s, e in zip(ev.start_idx, ev.end_idx)]
res = {"file": f"hai-21.03 {FILE}", "seconds": len(df), "stream_seconds_per_second": len(df) / el,
       "per_second_latency_ms": 1000 * el / len(df),
       "alarm_agreement": float((on == batch).mean()),
       "events": int(len(ev)), "events_detected_batch": int(ev.detected.sum()),
       "events_alarmed_stream": int(sum(x is not None for x in first_on)),
       "stream_ttd_s": first_on, "batch_ttd_s": [None if pd.isna(x) else int(x) for x in ev.ttd_s]}
json.dump(res, open(os.path.join(ROOT, "data", "processed", "lab_check.json"), "w"), indent=2)
st = json.load(open(os.path.join(ROOT, "paper", "stats.json"))); st["lab_check"] = res
json.dump(st, open(os.path.join(ROOT, "paper", "stats.json"), "w"), indent=2, default=float)
print(json.dumps(res, indent=2))
