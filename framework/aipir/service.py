"""AIPIR runtime service: Observe -> Predict -> Respond -> Recover, with Zero-Trust access.

  * Observe : reads telemetry one second at a time (CSV replay of HAI in lab mode; swap
              `replay_source` for an OPC-UA / historian reader in a deployment). Publishes
              Prometheus metrics on /metrics and OpenTelemetry metrics/traces/logs over OTLP.
  * Predict : StreamingScorer computes the AIPIR anomaly score each second.
  * Respond : Prometheus alert rules fire per routed process; Alertmanager posts to /recover
              using a workload identity token.
  * Recover : RecoveryManager plans (dry-run, default) or queues (execute) a recovery; a second
              person with the approver role and MFA approves it; the Ansible hook runs the process
              playbook (check mode unless AIPIR_ANSIBLE_CHECK=0).
  * Zero-Trust: every endpoint except /healthz needs a verified token; permissions come from
              deploy/zero-trust/rbac_policy.yaml; every decision goes to a hash-chained audit log.

Endpoints
  GET  /healthz                         public liveness
  GET  /metrics                         metrics:read      Prometheus text format
  GET  /status                          status:read       current score, alarm, routing (JSON)
  GET  /recoveries                      status:read       recovery requests (JSON)
  POST /recover                         recovery:request  Alertmanager webhook or operator request
  POST /recoveries/<id>/approve         recovery:approve  MFA + two-person rule

Run (lab):  see deploy/README.md and docs/training/labs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import joblib

from .data import load_file, process_of
from .otel import OTLPExporter
from .recovery import RecoveryManager
from .streaming import StreamingScorer
from .zerotrust import AuthError, from_env

STATE = {"status": None, "rows": 0, "started": time.time()}
LOCK = threading.Lock()
CTX = {}  # authorizer, recovery manager, otel exporter


def replay_source(path: str, speed: float):
    df = load_file(path)
    delay = 1.0 / speed if speed > 0 else 0.0
    for ts, row in df.iterrows():
        yield ts, row.to_dict()
        if delay:
            time.sleep(delay)


def read_drift_report():
    path = os.environ.get("AIPIR_DRIFT_REPORT")
    if not path or not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def metrics_text() -> str:
    with LOCK:
        st, n = STATE["status"], STATE["rows"]
    rm: RecoveryManager = CTX["recovery"]
    recs = rm.list()
    lines = ["# HELP aipir_rows_processed_total Telemetry seconds scored.",
             "# TYPE aipir_rows_processed_total counter", f"aipir_rows_processed_total {n}",
             "# HELP aipir_recovery_requests_total Recovery requests by status.",
             "# TYPE aipir_recovery_requests_total gauge"]
    for status in ("planned", "pending_approval", "running", "succeeded", "failed"):
        lines.append(f'aipir_recovery_requests_total{{status="{status}"}} {sum(r["status"] == status for r in recs)}')
    drift = read_drift_report()
    if drift:
        lines += ["# HELP aipir_config_drift_items Configuration items differing from the declared baseline.",
                  "# TYPE aipir_config_drift_items gauge"]
        for src, cnt in drift.get("counts", {}).items():
            lines.append(f'aipir_config_drift_items{{source="{src}"}} {cnt}')
        lines.append(f'aipir_config_drift_unapproved {drift.get("unapproved", 0)}')
    if st:
        lines += ["# HELP aipir_anomaly_score AIPIR predictive anomaly score (higher = more anomalous).",
                  "# TYPE aipir_anomaly_score gauge", f"aipir_anomaly_score {st['score']:.6f}",
                  "# HELP aipir_threshold Calibrated alarm threshold.",
                  "# TYPE aipir_threshold gauge", f"aipir_threshold {st['threshold']:.6f}",
                  "# HELP aipir_alarm 1 while a debounced alarm episode is active, per routed process.",
                  "# TYPE aipir_alarm gauge"]
        for p in ("P1", "P2", "P3"):
            lines.append(f'aipir_alarm{{process="{p}"}} {int(st["alarm"] and st["routed"] == p)}')
        lines += ["# HELP aipir_sensor_residual Normalized per-sensor forecast residual.",
                  "# TYPE aipir_sensor_residual gauge"]
        for c, v in zip(st["cols"], st["contrib"]):
            lines.append(f'aipir_sensor_residual{{sensor="{c}",process="{process_of(c)}"}} {float(v):.5f}')
    return "\n".join(lines) + "\n"


class Handler(BaseHTTPRequestHandler):
    server_version = "aipir"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(b)

    def _auth(self, permission, resource=""):
        return CTX["authz"].authorize(self.headers.get("Authorization"), permission, resource or self.path)

    def _err(self, e: AuthError):
        hdr = 'Bearer realm="aipir"' if e.status == 401 else None
        b = json.dumps({"error": e.reason}).encode()
        self.send_response(e.status)
        if hdr:
            self.send_header("WWW-Authenticate", hdr)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        try:
            if self.path.startswith("/healthz"):
                self._auth("health:read")
                return self._send(200, "ok\n", "text/plain")
            if self.path.startswith("/metrics"):
                self._auth("metrics:read")
                return self._send(200, metrics_text(), "text/plain; version=0.0.4")
            if self.path.startswith("/status"):
                self._auth("status:read")
                with LOCK:
                    st = STATE["status"] or {}
                return self._send(200, json.dumps({k: st.get(k) for k in ("t", "score", "threshold", "alarm", "routed", "top_sensors")}, default=float))
            if self.path.startswith("/recoveries"):
                self._auth("status:read")
                return self._send(200, json.dumps(CTX["recovery"].list(), default=str))
            return self._send(404, '{"error":"not found"}')
        except AuthError as e:
            return self._err(e)

    def do_POST(self):
        try:
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
            body = json.loads(raw or b"{}")
        except ValueError:
            return self._send(400, '{"error":"invalid JSON"}')
        try:
            if self.path.startswith("/recover") and not self.path.startswith("/recoveries"):
                p = self._auth("recovery:request")
                procs = sorted({a.get("labels", {}).get("process") for a in body.get("alerts", [])} - {None})
                if not procs and body.get("process"):
                    procs = [body["process"]]
                with LOCK:
                    st = STATE["status"] or {}
                ctx = {"top_sensors": [s for s, _ in st.get("top_sensors", [])], "score": st.get("score")}
                made = [CTX["recovery"].request(pr, p.sub, ctx) for pr in procs if pr in ("P1", "P2", "P3", "MON")]
                return self._send(200, json.dumps({"accepted": [vars(r) for r in made]}, default=str))
            m = re.fullmatch(r"/recoveries/([0-9a-f]{6,32})/approve", self.path)
            if m:
                rid = m.group(1)
                p = self._auth("recovery:approve", f"recovery/{rid}")
                rm: RecoveryManager = CTX["recovery"]
                req = rm.items.get(rid)
                if req is None:
                    return self._send(404, '{"error":"no such recovery"}')
                CTX["authz"].check_two_person("recovery:approve", req.requested_by, p, f"recovery/{rid}")
                try:
                    r = rm.approve(rid, p.sub)
                except ValueError as e:
                    return self._send(409, json.dumps({"error": str(e)}))
                return self._send(200, json.dumps(vars(r), default=str))
            return self._send(404, '{"error":"not found"}')
        except AuthError as e:
            return self._err(e)


def _on_recovery_event(kind, r):
    otel: OTLPExporter = CTX["otel"]
    CTX["authz"].audit.write({"event": kind, "recovery_id": r.id, "process": r.process, "status": r.status,
                              "requested_by": r.requested_by, "approved_by": r.approved_by})
    otel.add("aipir.recovery.events", 1, kind=kind, process=r.process)
    otel.log(f"{kind} {r.id} {r.process} {r.status}", "WARN" if kind == "recovery.requested" else "INFO",
             recovery_id=r.id, process=r.process, status=r.status)
    if kind == "recovery.finished":
        ev = [(r.created, "requested", {"by": r.requested_by})]
        if r.approved_at:
            ev.append((r.approved_at, "approved", {"by": r.approved_by}))
        otel.span("aipir.recovery", r.created, time.time(),
                  {"aipir.process": r.process, "aipir.recovery.id": r.id, "aipir.recovery.status": r.status,
                   "aipir.recovery.mode": r.mode,
                   "aipir.ansible.check_mode": bool((r.result or {}).get("check_mode", True))}, ev)


def build_context():
    otel = OTLPExporter().start()

    def audit_sink(rec):
        otel.log("audit " + rec.get("decision", rec.get("event", "")), "INFO",
                 **{k: v for k, v in rec.items() if k in ("permission", "subject", "reason", "event", "recovery_id")})
    CTX["otel"] = otel
    CTX["authz"] = from_env(audit_sink=audit_sink)
    CTX["recovery"] = RecoveryManager(on_event=_on_recovery_event)


def run(model, replay, speed, port, host="0.0.0.0"):
    build_context()
    bundle = joblib.load(model)
    scorer = StreamingScorer(bundle)
    srv = ThreadingHTTPServer((host, port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    otel: OTLPExporter = CTX["otel"]
    print(f"AIPIR service on :{port} (model {os.path.basename(model)}, threshold {scorer.thr:.4f}, "
          f"recovery {CTX['recovery'].mode}, otel {'on' if otel.enabled else 'off'})", flush=True)
    episode = None
    for ts, row in replay_source(replay, speed):
        st = scorer.update(row)
        st["cols"] = scorer.cols
        with LOCK:
            STATE["status"], STATE["rows"] = st, STATE["rows"] + 1
        otel.gauge("aipir.anomaly.score", st["score"])
        otel.gauge("aipir.threshold", st["threshold"])
        otel.add("aipir.telemetry.rows", 1)
        for p in ("P1", "P2", "P3"):
            otel.gauge("aipir.alarm.active", int(st["alarm"] and st["routed"] == p), process=p)
        now = time.time()
        if st["alarm"] and episode is None:
            episode = {"start": now, "process": st["routed"], "peak": st["score"],
                       "top": [s for s, _ in st["top_sensors"]], "telemetry_time": str(ts)}
            otel.log(f"alarm raised, routed to {st['routed']}", "WARN", process=st["routed"],
                     top_sensors=episode["top"], telemetry_time=str(ts))
        elif st["alarm"] and episode:
            episode["peak"] = max(episode["peak"], st["score"])
        elif not st["alarm"] and episode:
            otel.span("aipir.alarm", episode["start"], now,
                      {"aipir.process": episode["process"], "aipir.score.peak": float(episode["peak"]),
                       "aipir.top_sensors": episode["top"], "aipir.telemetry.start": episode["telemetry_time"]})
            episode = None
        drift = read_drift_report()
        if drift and STATE["rows"] % 60 == 0:
            for src, cnt in drift.get("counts", {}).items():
                otel.gauge("aipir.config.drift.items", cnt, source=src)
    print("replay finished; serving last state", flush=True)
    otel.flush()
    while True:
        time.sleep(3600)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--replay", required=True)
    ap.add_argument("--speed", type=float, default=1.0, help="replay speed multiplier (1 = real time)")
    ap.add_argument("--port", type=int, default=9108)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    run(a.model, a.replay, a.speed, a.port, a.host)


if __name__ == "__main__":
    main()
