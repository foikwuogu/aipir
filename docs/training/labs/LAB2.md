# Lab 2 - Detection: what was found, how fast, what was missed (45 min)

**Objective:** interpret detection results honestly. **Layer:** Predict.

## Steps

1. Open `data/processed/qa_report.txt`, then `paper/figures/fig5_timeline.png`.
2. Compare the detectors in `data/processed/metrics_summary.csv` (held-out rows, `split == test`):
   ```bash
   python - <<'PY'
   import pandas as pd
   d = pd.read_csv("data/processed/metrics_summary.csv")
   print(d[d.split == "test"][["version","detector","events_detected","events","ttd_median_s","f1","false_episodes_per_day"]])
   PY
   ```
3. Find the HAI 21.03 attacks that AIPIR (D3) missed but static limits (D0) caught:
   ```bash
   python - <<'PY'
   import pandas as pd
   e = pd.read_csv("data/processed/events.csv"); e = e[(e.split=="test") & (e.version=="hai-21.03")]
   p = e.pivot_table(index=["file","event"], columns="detector", values="detected", aggfunc="first")
   print(p[(p.D0 == True) & (p.D3 == False)])
   PY
   ```
4. Look at `paper/figures/fig4_fa_tradeoff.png`: how does event recall change with the
   false-alarm budget?

## Discussion

- Why is "AIPIR replaces alarm limits" the wrong conclusion, and "AIPIR is a layer on top of
  limits" a better one?
- Why were thresholds set on normal data only, and why were design choices frozen on one file?

## Check

You can state one strength and one weakness of the predictive detector with numbers.
