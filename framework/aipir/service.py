"""AIPIR runtime service: Observe -> Predict -> Respond -> Recover.

  * Observe : reads telemetry one second at a time (CSV replay of HAI in lab mode; swap
              `replay_source` for an OPC-UA / historian reader in a real deployment).
  * Predict : StreamingScorer computes the AIPIR anomaly score each second.
  * Respond : exposes Prometheus/OpenMetrics gauges on /metrics; Prometheus alert rules
              (deploy/prometheus/alert_rules.yml) fire on aipir_alarm and route by `process`.
  * Recover : Alertmanager posts to /recover; the service selects the playbook for the routed
              process and runs it in DRY-RUN mode (logs the plan) unless AIPIR_RECOVERY=execute.
              Execution is a hook for the operator's own automation (Ansible/IaC pipeline);
              this repository never writes to a control system.

Run:  python -m aipir.service --model models/aipir_hai2103.joblib \
          --replay data/raw/hai-21.03/test2.csv.gz --speed 60 --port 9108
Standard library only (plus numpy/scikit-learn/joblib for the model).
"""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import joblib

from .data import load_file, process_of
from .routing import PLAYBOOKS
from .streaming import StreamingScorer

STATE = {"status": None, "rows": 0, "started": time.time(), "recoveries": []}
LOCK = threading.Lock()


def replay_source(path: str, speed: float):
    df = load_file(path)
    delay = 1.0 / speed if speed > 0 else 0.0
    for ts, row in df.iterrows():
        yield ts, row.to_dict()
        if delay:
            time.sleep(delay)


def metrics_text() -> str:
    with LOCK:
        st, n = STATE["status"], STATE["rows"]
        recov = len(STATE["recoveries"])
    lines = ["# HELP aipir_rows_processed_total Telemetry seconds scored.",
             "# TYPE aipir_rows_processed_total counter", f"aipir_rows_processed_total {n}",
             "# HELP aipir_recovery_requests_total Recovery webhooks received.",
             "# TYPE aipir_recovery_requests_total counter", f"aipir_recovery_requests_total {recov}"]
    if st:
        lines += ["# HELP aipir_anomaly_score AIPIR predictive anomaly score (higher = more anomalous).",
                  "# TYPE aipir_anomaly_score gauge", f"aipir_anomaly_score {st['score']:.6f}",
                  "# HELP aipir_threshold Calibrated alarm threshold.",
                  "# TYPE aipir_threshold gauge", f"aipir_threshold {st['threshold']:.6f}",
                  "# HELP aipir_alarm 1 while a debounced alarm episode is active.",
                  "# TYPE aipir_alarm gauge"]
        for p in ("P1", "P2", "P3"):
            lines.append(f'aipir_alarm{{process="{p}"}} {int(st["alarm"] and st["routed"] == p)}')
        lines += ["# HELP aipir_sensor_residual Normalized per-sensor forecast residual.",
                  "# TYPE aipir_sensor_residual gauge"]
        for c, v in zip(st["cols"], st["contrib"]):
            lines.append(f'aipir_sensor_residual{{sensor="{c}",process="{process_of(c)}"}} {float(v):.5f}')
    return "\n".join(lines) + "\n# EOF\n"


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype="text/plain; version=0.0.4"):
        b = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/metrics"):
            self._send(200, metrics_text())
        elif self.path.startswith("/healthz"):
            self._send(200, "ok\n")
        else:
            self._send(404, "not found\n")

    def do_POST(self):
        if not self.path.startswith("/recover"):
            return self._send(404, "not found\n")
        payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0)) or b"{}") or "{}")
        procs = sorted({a.get("labels", {}).get("process") for a in payload.get("alerts", [])} - {None})
        mode = os.environ.get("AIPIR_RECOVERY", "dry-run")
        plan = [{"process": p, "playbook": PLAYBOOKS.get(p, "unknown"), "mode": mode,
                 "received": time.strftime("%Y-%m-%dT%H:%M:%S")} for p in procs]
        with LOCK:
            STATE["recoveries"].extend(plan)
        print("RECOVERY", json.dumps(plan), flush=True)
        self._send(200, json.dumps({"accepted": plan}), "application/json")


def run(model, replay, speed, port):
    bundle = joblib.load(model)
    scorer = StreamingScorer(bundle)
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"AIPIR service on :{port} (model {os.path.basename(model)}, threshold {scorer.thr:.4f})", flush=True)
    for ts, row in replay_source(replay, speed):
        st = scorer.update(row)
        st["cols"] = scorer.cols
        with LOCK:
            STATE["status"], STATE["rows"] = st, STATE["rows"] + 1
    print("replay finished; serving last state", flush=True)
    while True:
        time.sleep(3600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed multiplier (1 = real time)")
    ap.add_argument("--port", type=int, default=9108)
    a = ap.parse_args()
    run(a.model, a.replay, a.speed, a.port)


if __name__ == "__main__":
    main()
