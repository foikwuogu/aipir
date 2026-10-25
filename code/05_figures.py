#!/usr/bin/env python3
"""05 - Figures (PNG, 300 dpi) and tables from the pipeline outputs.

Every figure carries a DRAFT stamp until run with --final (after the author's
verification gate). Palette: validated categorical order (dataviz skill reference
palette), fixed per detector so a detector keeps its colour in every figure.
"""
import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "data", "processed")
FIG = os.path.join(ROOT, "paper", "figures")
TAB = os.path.join(ROOT, "paper", "tables")

COL = {"D3": "#2a78d6", "D1": "#eb6834", "D2": "#1baf7a", "D0": "#eda100"}
NAME = {"D0": "Static limits", "D1": "PCA residual", "D2": "Isolation Forest", "D3": "AIPIR predictive"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ORDER = ["D0", "D1", "D2", "D3"]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})


def save(fig, name, final):
    if not final:
        fig.text(0.99, 0.01, "DRAFT - not verified", ha="right", va="bottom", fontsize=8,
                 color="#b00020", alpha=0.8)
    fig.savefig(os.path.join(FIG, name), dpi=300, bbox_inches="tight")
    plt.close(fig)


def box(ax, x, y, w, h, title, body, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.02",
                                fc="white", ec=color, lw=1.6))
    ax.text(x + w / 2, y + h - 0.05, title, ha="center", va="top", fontsize=10, weight="bold", color=INK)
    ax.text(x + w / 2, y + h - 0.13, body, ha="center", va="top", fontsize=7.4, color=INK2, linespacing=1.4)


def fig_architecture(final):
    fig, ax = plt.subplots(figsize=(9, 3.4))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    layers = [("1  Observe", "Plant telemetry (1 Hz)\nOPC-UA / historian or\nHAI replay\nPrometheus /metrics"),
              ("2  Predict", "Ridge forecaster:\neach sensor 1 s ahead\nfrom 30 s history\nrobust residual score"),
              ("3  Respond", "Threshold calibrated on\nnormal data (1 alarm/day)\ndebounce + merge\nroute to P1 / P2 / P3"),
              ("4  Recover", "Alertmanager webhook\nprocess playbook\nTerraform + Kubernetes\nknown-good rollback")]
    w, gap, y, h = 0.205, 0.045, 0.40, 0.52
    for i, (t, b) in enumerate(layers):
        x = 0.02 + i * (w + gap)
        box(ax, x, y, w, h, t, b, COL["D3"])
        if i < 3:
            ax.add_patch(FancyArrowPatch((x + w + 0.004, y + h / 2), (x + w + gap - 0.004, y + h / 2),
                                         arrowstyle="-|>", mutation_scale=12, color=INK2, lw=1.2))
    ax.annotate("", xy=(0.12, 0.38), xytext=(0.88, 0.38),
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1, connectionstyle="arc3,rad=-0.35"))
    ax.text(0.5, 0.05, "closed loop: recovered plant state is observed again and must return below threshold",
            ha="center", fontsize=7.5, color=INK2)
    save(fig, "fig1_architecture.png", final)


def fig_detection(summ, final):
    t = summ[summ.split == "test"]
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.2), sharey=True)
    for ax, ver in zip(axes, ["hai-21.03", "hai-20.07"]):
        d = t[t.version == ver].set_index("detector")
        x = np.arange(len(ORDER)); bw = 0.38
        for j, (metric, lab, alpha) in enumerate([("event_recall", "Event recall", 1.0), ("f1", "Point-wise F1", 0.45)]):
            vals = [d.loc[k, metric] for k in ORDER]
            bars = ax.bar(x + (j - 0.5) * bw, vals, bw - 0.03, color=[COL[k] for k in ORDER], alpha=alpha,
                          edgecolor=SURF, linewidth=1)
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + b.get_width() / 2, v + 0.02, f"{v:.2f}", ha="center", fontsize=7, color=INK)
        ax.set_xticks(x, [NAME[k].replace(" ", "\n", 1) for k in ORDER], fontsize=7.5)
        n = int(d.loc["D3", "events"])
        ax.set_title(f"{ver.upper()} held-out tests ({n} attack events)", fontsize=9, color=INK)
        ax.set_ylim(0, 1.12); ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    axes[0].set_ylabel("Score (0-1)")
    from matplotlib.patches import Patch
    axes[1].legend(handles=[Patch(color=INK2, alpha=1.0, label="Event recall (solid)"),
                            Patch(color=INK2, alpha=0.45, label="Point-wise F1 (light)")],
                   frameon=False, fontsize=7.5, loc="upper left")
    save(fig, "fig2_detection.png", final)


def fig_ttd(ev, final):
    d = ev[(ev.split == "test") & ev.detected & (ev.version == "hai-21.03") & ev.detector.isin(ORDER)]
    fig, ax = plt.subplots(figsize=(6.5, 3.0))
    rng = np.random.default_rng(1)
    for i, k in enumerate(ORDER):
        v = d[d.detector == k].ttd_s.to_numpy()
        if len(v) == 0:
            ax.text(np.log10(5), i, "no detections", va="center", fontsize=7.5, color=INK2)
            continue
        ax.scatter(np.log10(np.maximum(v, 1)), i + rng.uniform(-0.18, 0.18, len(v)), s=16, color=COL[k],
                   edgecolor=SURF, linewidth=0.6, zorder=3)
        med = np.median(v)
        ax.plot([np.log10(max(med, 1))] * 2, [i - 0.3, i + 0.3], color=INK, lw=1.6, zorder=4)
        ax.text(np.log10(max(med, 1)), i + 0.36, f"median {med:.0f} s (n={len(v)})", ha="center", fontsize=7, color=INK)
    ax.set_yticks(range(len(ORDER)), [NAME[k] for k in ORDER])
    ticks = [1, 10, 60, 300, 1800]
    ax.set_xticks(np.log10(ticks), ["1 s", "10 s", "1 min", "5 min", "30 min"])
    ax.set_xlabel("Time to detect (log scale), detected held-out events, HAI 21.03")
    ax.set_ylim(-0.6, len(ORDER) - 0.2); ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    save(fig, "fig3_ttd.png", final)


def fig_tradeoff(sw, final):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.0), sharey=True)
    for ax, ver in zip(axes, ["hai-21.03", "hai-20.07"]):
        for k in ["D0", "D1", "D3"]:
            d = sw[(sw.version == ver) & (sw.detector == k)].sort_values("budget_per_day")
            ax.plot(d.budget_per_day, d.event_recall, color=COL[k], lw=2, marker="o", ms=5,
                    markeredgecolor=SURF, label=NAME[k])
        ax.set_xscale("log"); ax.minorticks_off(); ax.set_xticks([0.25, 0.5, 1, 2, 4], ["0.25", "0.5", "1", "2", "4"])
        ax.set_xlim(0.2, 5); ax.set_ylim(0, 1.05)
        ax.set_title(f"{ver.upper()} held-out tests", fontsize=9)
        ax.set_xlabel("False-alarm budget on normal data (episodes/day)")
        ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    axes[0].set_ylabel("Event recall")
    axes[0].legend(frameon=False, fontsize=7.5, loc="lower left")
    save(fig, "fig4_fa_tradeoff.png", final)


def fig_timeline(final, thr):
    s = pd.read_csv(os.path.join(OUT, "scores_hai-21.03_test2.csv.gz"), parse_dates=["time"])
    runs_y = s.attack.to_numpy()
    i0 = int(np.argmax(runs_y)) - 1800
    seg = s.iloc[max(0, i0):max(0, i0) + 6 * 3600]
    fig, ax = plt.subplots(figsize=(9, 2.8))
    y = seg.attack.to_numpy().astype(bool)
    t = seg.time.to_numpy()
    edges = np.flatnonzero(np.diff(np.r_[0, y.astype(int), 0]))
    for a, b in zip(edges[::2], edges[1::2]):
        ax.axvspan(t[a], t[min(b, len(t) - 1)], color="#e34948", alpha=0.15, lw=0)
    ax.plot(seg.time, seg.score_D3, color=COL["D3"], lw=1.2, label="AIPIR score")
    ax.axhline(thr, color=INK, lw=1, ls="--")
    ax.text(seg.time.iloc[0], thr + 0.12, "calibrated threshold", va="bottom", fontsize=7.5, color=INK)
    al = seg.alarm_D3.to_numpy().astype(bool)
    ax.scatter(seg.time[al], np.full(al.sum(), -0.25), marker="|", s=40, color=COL["D3"])
    ax.text(seg.time.iloc[0], -0.25, "alarm ", ha="right", va="center", fontsize=7.5, color=INK2)
    ax.set_ylabel("Anomaly score"); ax.set_ylim(-0.5, None)
    ax.set_title("HAI 21.03 test2, 6 h excerpt: shaded = labelled attacks", fontsize=9, loc="left")
    ax.yaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    save(fig, "fig5_timeline.png", final)


def fig_downtime(stats, final):
    g = pd.read_csv(os.path.join(OUT, "downtime_scenarios.csv"))
    c = stats["downtime"]["central"]
    labels = ["S0  Static limits\n+ manual recovery", "S1  AIPIR detection\n+ manual recovery",
              "S2  AIPIR detection\n+ IaC/playbook recovery",
              "S3  Static limits + AIPIR layered\n(exploratory, post hoc)"]
    cols = [COL["D0"], "#8fb6e8", COL["D3"], "#1a4f8f"]
    keys = ["S0_h", "S1_h", "S2_h", "S3_h"]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for i, k in enumerate(keys):
        ax.barh(i, c[k], color=cols[i], height=0.55, edgecolor=SURF)
        ax.plot([g[k].min(), g[k].max()], [i, i], color=INK, lw=1)
        ax.text(g[k].max() * 1.02, i, f"{c[k]:,.0f} h (range {g[k].min():,.0f}-{g[k].max():,.0f})",
                va="center", fontsize=7.5, color=INK)
    ax.set_yticks(range(4), labels, fontsize=8); ax.invert_yaxis()
    ax.set_xlabel("Total downtime across held-out attack events, hours (SCENARIO, assumed recovery times)")
    ax.set_xlim(0, g[keys].max().max() * 1.5)
    ax.xaxis.grid(True, color=GRID, lw=0.6); ax.set_axisbelow(True)
    save(fig, "fig6_downtime_scenario.png", final)


def tables(summ):
    t = summ[summ.split == "test"].copy()
    t["detector"] = t.detector.map(lambda k: NAME.get(k, k))
    cols = ["version", "detector", "events", "events_detected", "event_recall", "ttd_median_s",
            "precision", "recall", "f1", "false_episodes_per_day", "routing_accuracy"]
    t[cols].round(3).to_csv(os.path.join(TAB, "table1_heldout_results.csv"), index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true", help="remove DRAFT stamps (after verification)")
    a = ap.parse_args()
    os.makedirs(FIG, exist_ok=True); os.makedirs(TAB, exist_ok=True)
    summ = pd.read_csv(os.path.join(OUT, "metrics_summary.csv"))
    ev = pd.read_csv(os.path.join(OUT, "events.csv"))
    sw = pd.read_csv(os.path.join(OUT, "fa_budget_sweep.csv"))
    stats = json.load(open(os.path.join(ROOT, "paper", "stats.json")))
    fig_architecture(a.final)
    fig_detection(summ, a.final)
    fig_ttd(ev, a.final)
    fig_tradeoff(sw, a.final)
    fig_timeline(a.final, stats["qa"]["hai-21.03"]["thresholds"]["D3"])
    fig_downtime(stats, a.final)
    tables(summ)
    print("figures:", sorted(os.listdir(FIG)))


if __name__ == "__main__":
    main()
