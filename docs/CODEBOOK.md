# Codebook

All processed files are written by the numbered scripts in `code/`. Times are the HAI
timestamps (testbed local time, 1 Hz). "Held-out" = HAI 21.03 test2-test5 and HAI 20.07
test1-test2; "dev" = HAI 21.03 test1, the only labelled file used for design decisions.

## `data/processed/scores_<version>_<file>.csv.gz` (one row per second)

| Column | Definition | Source / transformation |
|---|---|---|
| `time` | Timestamp of the second | HAI `time` column |
| `attack` | 1 if any attack is active | HAI label, unchanged |
| `attack_P1`, `attack_P2`, `attack_P3` | 1 if the attack targets boiler / turbine / water process | HAI labels, unchanged |
| `score_<D>` | Anomaly score of detector D at this second (higher = more anomalous); causal | `02_build.py`, detector `score()` |
| `alarm_<D>` | 1 while a debounced alarm episode of detector D is active | score > calibrated threshold, runs merged across gaps <= 30 s, kept if >= 5 s |

Detectors `<D>`: `D0` static limits, `D1` PCA residual, `D2` Isolation Forest, `D3` AIPIR
predictive (the proposed detector), `D3+C` AIPIR with the added consistency channel
(ablation), `D3-noclip` AIPIR without robust normalization (ablation).

## `data/processed/events.csv` (one row per attack event x detector)

| Column | Definition |
|---|---|
| `version`, `split`, `file`, `detector` | Dataset version, dev/test, HAI file, detector |
| `event` | Index of the event within the file (contiguous run of `attack` = 1) |
| `start_idx`, `end_idx`, `start_time`, `end_time`, `duration_s` | Event bounds (inclusive) |
| `attacked` | Processes with a P-level attack label during the event (`P1`, `P1+P2`, ...; empty if none) |
| `detected` | True if an alarm episode is *confirmed* between event start and end + 60 s. An alarm already active before the event starts earns no credit. |
| `ttd_s` | Time to detect: confirmation second minus event start, seconds |
| `first_alarm_idx` | Row index of the detecting confirmation |
| `routed` | Process (P1/P2/P3) the alarm is routed to: process of the top-contributing sensor among P1-P3, averaged over the 5 s before confirmation |
| `routing_correct` | `routed` is in `attacked` (blank when the event has no P-level label) |
| `top_sensors` | Three highest-contributing sensors at confirmation (may include P4 HIL points) |

## `data/processed/metrics_by_file.csv` and `metrics_summary.csv`

`tp`, `fp`, `fn`: second-level confusion counts of `alarm_<D>` vs `attack`.
`precision`, `recall`, `f1`: point-wise from those counts (pooled over files in the summary).
`events`, `events_detected`, `event_recall`: event-level detection.
`ttd_median_s`, `ttd_mean_s`: over detected events.
`false_episodes`: alarm episodes that overlap no event (or its 60 s grace window).
`false_episodes_per_day`: false episodes / test-data days.
`routing_n`, `routing_accuracy`: detected events with a P-level label, and share routed correctly.

## `data/processed/fa_budget_sweep.csv`

Held-out results when each detector's threshold is recalibrated (on normal data only) to a
different false-alarm budget: `budget_per_day`, `threshold`, point-wise metrics, `event_recall`,
and the realized `false_episodes_per_day` on the test files.

## `data/processed/downtime_scenarios.csv` (scenario model, not measurement)

One row per combination of assumed `r_manual_h` (manual recovery), `r_auto_h` (IaC/playbook
recovery), `t_discover_h` (time until a missed attack is found by other means). `S0_h`, `S1_h`,
`S2_h`: total downtime over held-out events for the three operating models; `S1_/S2_reduction_pct`:
reduction relative to S0. See `code/03_recovery_scenario.py`.

## `models/aipir_<version>.joblib`

Fitted scaler, AIPIR detector, calibrated threshold, and alarm parameters, loaded by
`framework/aipir/service.py`. Derived from HAI; CC BY-SA 4.0. Load only with the pinned
scikit-learn version in `requirements.txt`.

## `paper/stats.json`

Every number quoted in the manuscript and README, written by scripts 02-04. Documents read
this file; no number is typed by hand.
