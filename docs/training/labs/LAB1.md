# Lab 1 - Stand up AIPIR and read what it sees (45 min)

**Objective:** run the detector service on recorded power-plant telemetry and read its metrics.
**Layer:** Observe + Predict.

## Steps

1. From the repository root (data fetched with `python code/01_fetch.py`):
   ```bash
   source docs/training/lab_env.sh
   python -m aipir.service --model models/aipir_hai2103.joblib \
       --replay data/raw/hai-21.03/test4.csv.gz --speed 50 --port 9108 --host 127.0.0.1 &
   ```
2. The liveness endpoint is public. Everything else needs a token:
   ```bash
   curl -s 127.0.0.1:9108/healthz
   curl -s -o /dev/null -w '%{http_code}\n' 127.0.0.1:9108/metrics      # expect 401
   api GET /metrics "$SCRAPER" | grep -E 'aipir_(anomaly_score|threshold|alarm)'
   ```
3. Watch the score for a minute: `watch -n 2 "curl -s -H 'Authorization: Bearer $SCRAPER' 127.0.0.1:9108/metrics | grep aipir_anomaly_score"`.
4. Read the current state as a viewer: `api GET /status "$VIEWER"`.

## Questions

- What does `aipir_threshold` represent, and on which data was it set? (Hint: `framework/aipir/config.py`.)
- Which sensors appear in `top_sensors` when the score is high, and which process do they belong to?

## Check

You can explain the difference between the anomaly score, the threshold and an alarm episode
(debounce 5 s, merge gap 30 s).
