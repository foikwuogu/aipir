#!/usr/bin/env python3
"""Write SYNTHETIC incident records for training Lab 6 only (to /tmp/aipir_practice/).
These records are invented to practise the KPI tool. They are not pilot data and must never be
reported as such; every row carries source=SYNTHETIC-TRAINING."""
import os

import numpy as np
import pandas as pd

rng = np.random.default_rng(42)
out = "/tmp/aipir_practice"
os.makedirs(out, exist_ok=True)
rows = []
for ph, base_day, ttd, ttr in [("baseline", 0, 12, 45), ("pilot", 60, 9, 30)]:
    for i in range(15):
        s = pd.Timestamp("2030-01-01") + pd.Timedelta(days=base_day + 2 * i, hours=int(rng.integers(0, 23)))
        d = s + pd.Timedelta(minutes=max(1.0, float(rng.normal(ttd, 3))))
        r = d + pd.Timedelta(minutes=max(5.0, float(rng.normal(ttr, 10))))
        rows.append({"incident_id": f"TRN-{ph[:1].upper()}{i:02d}", "phase": ph, "subsystem": f"SUB{i % 4}",
                     "start": s, "detected": d, "recovered": r, "source": "SYNTHETIC-TRAINING"})
pd.DataFrame(rows).to_csv(f"{out}/incidents.csv", index=False)
pd.DataFrame([{"phase": "baseline", "start": "2030-01-01", "end": "2030-01-31"},
              {"phase": "pilot", "start": "2030-03-02", "end": "2030-04-01"}]).to_csv(f"{out}/periods.csv", index=False)
pd.DataFrame([{"phase": ph, "change_id": f"{ph}-{i}", "misconfiguration": int(rng.random() < p)}
              for ph, p in [("baseline", 0.06), ("pilot", 0.03)] for i in range(80)]).to_csv(f"{out}/changes.csv", index=False)
print(f"SYNTHETIC training records written to {out} (not pilot data)")
