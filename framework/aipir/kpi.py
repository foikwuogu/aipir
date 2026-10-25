"""Pilot KPI calculator - turns incident and change records into the SOW's measured targets.

This module computes; it does not supply data. The numbers it reports are only as real as the
records a site feeds it.

Inputs (CSV, one row per record; see docs/REPLICATION_PLAYBOOK.md section 5 for definitions)
  incidents.csv : incident_id, phase (baseline|pilot), subsystem, start, detected, recovered
                  timestamps ISO-8601; `start` = first evidence of the incident (from the
                  post-incident review), `detected` = first alert or human report,
                  `recovered` = service verified restored
  outages.csv   : (optional) phase, subsystem, start, end - service unavailability intervals;
                  if omitted, incident start->recovered intervals are used
  periods.csv   : phase, start, end - observation window per phase (needed for availability)
  changes.csv   : (optional) phase, change_id, misconfiguration (0/1) - one row per change

Outputs: JSON + Markdown with MTTD, MTTR, availability, misconfigurations per 100 changes per
phase, the percentage change vs baseline compared with the SOW targets, Welch's t-test and a
one-way ANOVA (phase x subsystem) for MTTD and MTTR, and a regression of MTTR on phase with
subsystem as a covariate - computed only when each group has enough incidents (n >= 5).

    python -m aipir.kpi --incidents incidents.csv --periods periods.csv [--outages outages.csv]
                        [--changes changes.csv] --out pilot_kpis
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd
from scipy import stats

SOW_TARGETS = {"mttd_reduction_pct": 30.0, "mttr_reduction_pct": 40.0, "availability_pct": 99.5,
               "misconfig_per_100_changes": 2.0}
MIN_N = 5


def _minutes(a, b):
    return (pd.to_datetime(b) - pd.to_datetime(a)).dt.total_seconds() / 60.0


def compute(incidents: pd.DataFrame, periods: pd.DataFrame, outages: pd.DataFrame | None = None,
            changes: pd.DataFrame | None = None) -> dict:
    inc = incidents.copy()
    inc["ttd_min"] = _minutes(inc["start"], inc["detected"])
    inc["ttr_min"] = _minutes(inc["detected"], inc["recovered"])
    bad = inc[(inc.ttd_min < 0) | (inc.ttr_min < 0)]
    if len(bad):
        raise ValueError(f"{len(bad)} incident(s) have timestamps out of order: {list(bad.incident_id)[:5]}")
    out = {"phases": {}, "targets": SOW_TARGETS, "notes": []}
    per = periods.set_index("phase")
    if outages is None:
        outages = inc.rename(columns={"start": "o_start", "recovered": "o_end"})[["phase", "subsystem", "o_start", "o_end"]]
        outages.columns = ["phase", "subsystem", "start", "end"]
        out["notes"].append("availability computed from incident start->recovered (no outage file)")
    for ph, g in inc.groupby("phase"):
        window = (pd.to_datetime(per.loc[ph, "end"]) - pd.to_datetime(per.loc[ph, "start"])).total_seconds() / 60.0
        o = outages[outages.phase == ph]
        down = float(_minutes(o["start"], o["end"]).sum()) if len(o) else 0.0
        n_sub = max(int(inc.subsystem.nunique()), 1)
        row = {"incidents": int(len(g)), "subsystems": int(g.subsystem.nunique()),
               "mttd_min": float(g.ttd_min.mean()), "mttd_median_min": float(g.ttd_min.median()),
               "mttr_min": float(g.ttr_min.mean()), "mttr_median_min": float(g.ttr_min.median()),
               "window_days": window / 1440.0,
               "availability_pct": 100.0 * (1 - down / (window * n_sub)) if window > 0 else None}
        if changes is not None and len(changes[changes.phase == ph]):
            c = changes[changes.phase == ph]
            row["changes"] = int(len(c))
            row["misconfig_per_100_changes"] = 100.0 * float(c.misconfiguration.sum()) / len(c)
        out["phases"][ph] = row
    if {"baseline", "pilot"} <= set(out["phases"]):
        b, p = out["phases"]["baseline"], out["phases"]["pilot"]
        cmpd = {"mttd_reduction_pct": 100 * (1 - p["mttd_min"] / b["mttd_min"]) if b["mttd_min"] else None,
                "mttr_reduction_pct": 100 * (1 - p["mttr_min"] / b["mttr_min"]) if b["mttr_min"] else None,
                "availability_pct_pilot": p["availability_pct"],
                "misconfig_per_100_changes_pilot": p.get("misconfig_per_100_changes")}
        cmpd["meets"] = {
            "mttd": cmpd["mttd_reduction_pct"] is not None and cmpd["mttd_reduction_pct"] >= SOW_TARGETS["mttd_reduction_pct"],
            "mttr": cmpd["mttr_reduction_pct"] is not None and cmpd["mttr_reduction_pct"] >= SOW_TARGETS["mttr_reduction_pct"],
            "availability": p["availability_pct"] is not None and p["availability_pct"] >= SOW_TARGETS["availability_pct"],
            "misconfig": p.get("misconfig_per_100_changes") is not None
            and p["misconfig_per_100_changes"] <= SOW_TARGETS["misconfig_per_100_changes"]}
        out["comparison"] = cmpd
        out["statistics"] = _statistics(inc)
    else:
        out["notes"].append("comparison needs both a baseline and a pilot phase")
    return out


def _statistics(inc):
    res = {}
    gb, gp = inc[inc.phase == "baseline"], inc[inc.phase == "pilot"]
    if min(len(gb), len(gp)) < MIN_N:
        return {"skipped": f"need >= {MIN_N} incidents per phase (have {len(gb)} baseline, {len(gp)} pilot)"}
    for m in ("ttd_min", "ttr_min"):
        t = stats.ttest_ind(gb[m], gp[m], equal_var=False)
        u = stats.mannwhitneyu(gb[m], gp[m], alternative="two-sided")
        groups = [g[m].to_numpy() for _, g in inc.groupby(["phase", "subsystem"]) if len(g) >= 2]
        an = stats.f_oneway(*groups) if len(groups) >= 2 else None
        res[m] = {"welch_t": float(t.statistic), "welch_p": float(t.pvalue),
                  "mannwhitney_p": float(u.pvalue),
                  "anova_phase_x_subsystem_F": float(an.statistic) if an else None,
                  "anova_p": float(an.pvalue) if an else None, "anova_groups": len(groups)}
    X = pd.get_dummies(inc[["subsystem"]], drop_first=True).astype(float)
    X.insert(0, "pilot", (inc.phase == "pilot").astype(float))
    X.insert(0, "const", 1.0)
    y = inc["ttr_min"].to_numpy()
    beta, *_ = np.linalg.lstsq(X.to_numpy(), y, rcond=None)
    resid = y - X.to_numpy() @ beta
    dof = max(len(y) - X.shape[1], 1)
    cov = (resid @ resid / dof) * np.linalg.pinv(X.to_numpy().T @ X.to_numpy())
    se = float(np.sqrt(cov[1, 1]))
    tval = beta[1] / se if se else float("nan")
    res["regression_ttr_on_pilot"] = {"pilot_effect_min": float(beta[1]), "se": se,
                                      "p": float(2 * stats.t.sf(abs(tval), dof)), "dof": int(dof),
                                      "covariates": list(X.columns[2:])}
    return res


def markdown(r):
    L = ["# Pilot KPI report", "", "| Phase | Incidents | MTTD (min) | MTTR (min) | Availability (%) | Misconfig / 100 changes |",
         "|---|---|---|---|---|---|"]
    for ph, v in r["phases"].items():
        mc = v.get("misconfig_per_100_changes")
        L.append(f"| {ph} | {v['incidents']} | {v['mttd_min']:.1f} | {v['mttr_min']:.1f} | "
                 f"{'-' if v['availability_pct'] is None else f'{v['availability_pct']:.2f}'} | {'-' if mc is None else f'{mc:.1f}'} |")
    if "comparison" in r:
        c = r["comparison"]
        L += ["", "| SOW target | Result | Met |", "|---|---|---|",
              f"| MTTD reduced >= 30% | {c['mttd_reduction_pct']:.1f}% | {'yes' if c['meets']['mttd'] else 'no'} |",
              f"| MTTR reduced >= 40% | {c['mttr_reduction_pct']:.1f}% | {'yes' if c['meets']['mttr'] else 'no'} |",
              f"| Availability >= 99.5% | {c['availability_pct_pilot']:.2f}% | {'yes' if c['meets']['availability'] else 'no'} |"]
        if c["misconfig_per_100_changes_pilot"] is not None:
            L.append(f"| Misconfig <= 2 / 100 changes | {c['misconfig_per_100_changes_pilot']:.1f} | {'yes' if c['meets']['misconfig'] else 'no'} |")
    L += ["", "Statistics: see the JSON report. Notes: " + "; ".join(r["notes"] or ["none"])]
    return "\n".join(L) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--incidents", required=True)
    ap.add_argument("--periods", required=True)
    ap.add_argument("--outages")
    ap.add_argument("--changes")
    ap.add_argument("--out", required=True, help="output path prefix (.json and .md are written)")
    a = ap.parse_args(argv)
    r = compute(pd.read_csv(a.incidents), pd.read_csv(a.periods),
                pd.read_csv(a.outages) if a.outages else None, pd.read_csv(a.changes) if a.changes else None)
    json.dump(r, open(a.out + ".json", "w"), indent=2, default=float)
    open(a.out + ".md", "w").write(markdown(r))
    print(markdown(r))


if __name__ == "__main__":
    main()
