#!/usr/bin/env python3
"""03 - Downtime scenario: what the measured detection results imply for downtime.

This is a SCENARIO MODEL, not a measurement. Time-to-detect and detected/missed status
per attack come from 02_build (measured on held-out HAI data). Recovery and discovery
times are ASSUMPTIONS (approved by the author, 2026-10-31), swept over ranges so the conclusion's dependence
on them is visible.

Per held-out attack event:
    downtime = TTD + recovery time            if the operating model detects it
             = T_discover + R_manual          if it is missed (found later by other means)

Operating models:
    S0  static alarm limits (D0) + manual recovery        (classic baseline)
    S1  AIPIR detection (D3)     + manual recovery        (detection contribution only)
    S2  AIPIR detection (D3)     + IaC/playbook recovery  (full framework)
    S3  static limits AND AIPIR layered: detection = earlier of D0/D3; IaC/playbook recovery
        when AIPIR detected (routed), manual otherwise. EXPLORATORY: defined after the
        held-out results showed D0 and D3 miss different events; label it as such.
"""
import itertools
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "processed")
STATS = os.path.join(ROOT, "paper", "stats.json")

# Central values and ranges, hours (author-approved assumptions, 2026-10-31)
CENTRAL = {"r_manual_h": 4.0, "r_auto_h": 0.25, "t_discover_h": 24.0}
RANGES = {"r_manual_h": [2.0, 4.0, 6.0, 8.0],
          "r_auto_h": [5 / 60, 0.25, 0.5],
          "t_discover_h": [8.0, 24.0, 72.0]}


def downtime(ev, r_detected_h, r_manual_h, t_discover_h):
    ttd_h = ev.ttd_s.fillna(0) / 3600.0
    return np.where(ev.detected, ttd_h + r_detected_h, t_discover_h + r_manual_h)


def scenario(events, p):
    d0 = events[events.detector == "D0"].set_index(["version", "file", "event"]).sort_index()
    d3 = events[events.detector == "D3"].set_index(["version", "file", "event"]).sort_index()
    s0 = downtime(d0, p["r_manual_h"], p["r_manual_h"], p["t_discover_h"]).sum()
    s1 = downtime(d3, p["r_manual_h"], p["r_manual_h"], p["t_discover_h"]).sum()
    s2 = downtime(d3, p["r_auto_h"], p["r_manual_h"], p["t_discover_h"]).sum()
    a3 = d3.ttd_s.where(d3.detected)
    a0 = d0.ttd_s.where(d0.detected)
    layered_ttd_h = np.fmin(a3.to_numpy(dtype=float), a0.to_numpy(dtype=float)) / 3600.0
    layered_det = d3.detected.to_numpy() | d0.detected.to_numpy()
    rec = np.where(d3.detected.to_numpy(), p["r_auto_h"], p["r_manual_h"])
    s3 = np.where(layered_det, np.nan_to_num(layered_ttd_h) + rec, p["t_discover_h"] + p["r_manual_h"]).sum()
    return {"S0_h": s0, "S1_h": s1, "S2_h": s2, "S3_h": s3,
            "S1_reduction_pct": 100 * (1 - s1 / s0), "S2_reduction_pct": 100 * (1 - s2 / s0),
            "S3_reduction_pct": 100 * (1 - s3 / s0), "layered_events_detected": int(layered_det.sum()),
            "n_events": int(len(d3))}


def main():
    ev = pd.read_csv(os.path.join(OUT, "events.csv"))
    ev = ev[ev.split == "test"]
    rows = []
    for vals in itertools.product(*RANGES.values()):
        p = dict(zip(RANGES.keys(), vals))
        rows.append({**p, **scenario(ev, p)})
    grid = pd.DataFrame(rows)
    grid.to_csv(os.path.join(OUT, "downtime_scenarios.csv"), index=False)
    central = scenario(ev, CENTRAL)
    n_events = int(ev[ev.detector == "D3"].shape[0])
    stats = json.load(open(STATS))
    stats["downtime"] = {
        "assumptions_central": CENTRAL, "ranges": RANGES, "n_events": n_events,
        "central": central,
        "S2_reduction_pct_min": float(grid.S2_reduction_pct.min()),
        "S2_reduction_pct_max": float(grid.S2_reduction_pct.max()),
        "S1_reduction_pct_min": float(grid.S1_reduction_pct.min()),
        "S1_reduction_pct_max": float(grid.S1_reduction_pct.max()),
        "S3_reduction_pct_min": float(grid.S3_reduction_pct.min()),
        "S3_reduction_pct_max": float(grid.S3_reduction_pct.max()),
    }
    # layered detection per version (exploratory)
    lay = {}
    for ver, g in ev.groupby("version"):
        d0 = g[g.detector == "D0"].set_index(["file", "event"]).sort_index()
        d3 = g[g.detector == "D3"].set_index(["file", "event"]).sort_index()
        both = d0.detected.to_numpy() | d3.detected.to_numpy()
        ttd = np.fmin(d0.ttd_s.where(d0.detected).to_numpy(dtype=float), d3.ttd_s.where(d3.detected).to_numpy(dtype=float))
        lay[ver] = {"events": int(len(d3)), "detected": int(both.sum()), "event_recall": float(both.mean()),
                    "ttd_median_s": float(np.nanmedian(ttd)),
                    "only_D0": int((d0.detected.to_numpy() & ~d3.detected.to_numpy()).sum()),
                    "only_D3": int((~d0.detected.to_numpy() & d3.detected.to_numpy()).sum())}
    stats["layered"] = lay
    stats["sweep"] = pd.read_csv(os.path.join(OUT, "fa_budget_sweep.csv")).to_dict("records")
    json.dump(stats, open(STATS, "w"), indent=2, default=float)
    print(json.dumps(stats["downtime"], indent=2, default=float))


if __name__ == "__main__":
    main()
