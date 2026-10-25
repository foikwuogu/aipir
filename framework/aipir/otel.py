"""OpenTelemetry export (OTLP/HTTP, JSON encoding) for the AIPIR service - standard library only.

Sends metrics, traces and logs to an OpenTelemetry Collector (or any OTLP/HTTP receiver) at
$OTEL_EXPORTER_OTLP_ENDPOINT (default http://localhost:4318) on the standard paths /v1/metrics,
/v1/traces, /v1/logs. Disabled unless that variable is set or `enabled=True`.

Signals
  metrics : aipir.anomaly.score, aipir.threshold (gauges); aipir.alarm.active{process} (gauge);
            aipir.telemetry.rows (counter); aipir.recovery.requests (counter);
            aipir.config.drift.items{source} (gauge, from the drift check)
  traces  : one span per alarm episode ("aipir.alarm", attributes: process, top sensors, peak
            score); one span per recovery ("aipir.recovery") with events requested/approved/finished
  logs    : audit decisions and alarm/recovery events
Resource: service.name=aipir-detector, service.version, deployment.environment.
"""
from __future__ import annotations

import json
import os
import secrets
import threading
import time
import urllib.request

from . import __version__


def _attr(k, v):
    if isinstance(v, bool):
        return {"key": k, "value": {"boolValue": v}}
    if isinstance(v, int):
        return {"key": k, "value": {"intValue": str(v)}}
    if isinstance(v, float):
        return {"key": k, "value": {"doubleValue": v}}
    if isinstance(v, (list, tuple)):
        return {"key": k, "value": {"arrayValue": {"values": [{"stringValue": str(x)} for x in v]}}}
    return {"key": k, "value": {"stringValue": str(v)}}


def _attrs(d):
    return [_attr(k, v) for k, v in (d or {}).items() if v is not None]


def _ns(t=None):
    return str(int((t if t is not None else time.time()) * 1e9))


class OTLPExporter:
    def __init__(self, endpoint: str | None = None, enabled: bool | None = None, interval_s: float = 10.0,
                 service_name: str = "aipir-detector", environment: str | None = None, headers: dict | None = None):
        ep = endpoint or os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        self.enabled = bool(ep) if enabled is None else enabled
        self.endpoint = (ep or "http://localhost:4318").rstrip("/")
        self.interval = interval_s
        self.headers = {"Content-Type": "application/json", **(headers or {})}
        self.resource = {"attributes": _attrs({
            "service.name": service_name, "service.version": __version__,
            "deployment.environment": environment or os.environ.get("AIPIR_ENV", "lab")})}
        self.scope = {"name": "aipir", "version": __version__}
        self.gauges: dict[tuple, float] = {}
        self.counters: dict[tuple, float] = {}
        self.spans, self.logs = [], []
        self.lock = threading.Lock()
        self.start_ns = _ns()
        self.sent = {"metrics": 0, "traces": 0, "logs": 0, "errors": 0}
        self._stop = threading.Event()

    # ------------- recording API
    def gauge(self, name, value, **attrs):
        with self.lock:
            self.gauges[(name, tuple(sorted(attrs.items())))] = float(value)

    def add(self, name, value=1, **attrs):
        with self.lock:
            k = (name, tuple(sorted(attrs.items())))
            self.counters[k] = self.counters.get(k, 0.0) + value

    def span(self, name, start, end, attrs=None, events=None, trace_id=None, parent=None):
        sid = secrets.token_hex(8)
        s = {"traceId": trace_id or secrets.token_hex(16), "spanId": sid, "name": name, "kind": 1,
             "startTimeUnixNano": _ns(start), "endTimeUnixNano": _ns(end), "attributes": _attrs(attrs),
             "events": [{"timeUnixNano": _ns(t), "name": n, "attributes": _attrs(a)} for t, n, a in (events or [])],
             "status": {"code": 1}}
        if parent:
            s["parentSpanId"] = parent
        with self.lock:
            self.spans.append(s)
        return s["traceId"], sid

    def log(self, body: str, severity: str = "INFO", **attrs):
        sev = {"DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17}.get(severity, 9)
        with self.lock:
            self.logs.append({"timeUnixNano": _ns(), "severityNumber": sev, "severityText": severity,
                              "body": {"stringValue": body}, "attributes": _attrs(attrs)})

    # ------------- OTLP payloads
    def payloads(self):
        now = _ns()
        with self.lock:
            gauges, counters = dict(self.gauges), dict(self.counters)
            spans, logs = self.spans, self.logs
            self.spans, self.logs = [], []
        metrics = []
        for name in sorted({k[0] for k in gauges}):
            pts = [{"timeUnixNano": now, "asDouble": v, "attributes": _attrs(dict(a))}
                   for (n, a), v in gauges.items() if n == name]
            metrics.append({"name": name, "gauge": {"dataPoints": pts}})
        for name in sorted({k[0] for k in counters}):
            pts = [{"startTimeUnixNano": self.start_ns, "timeUnixNano": now, "asDouble": v,
                    "attributes": _attrs(dict(a))} for (n, a), v in counters.items() if n == name]
            metrics.append({"name": name, "sum": {"dataPoints": pts, "aggregationTemporality": 2,
                                                  "isMonotonic": True}})
        out = {}
        if metrics:
            out["metrics"] = {"resourceMetrics": [{"resource": self.resource, "scopeMetrics": [
                {"scope": self.scope, "metrics": metrics}]}]}
        if spans:
            out["traces"] = {"resourceSpans": [{"resource": self.resource, "scopeSpans": [
                {"scope": self.scope, "spans": spans}]}]}
        if logs:
            out["logs"] = {"resourceLogs": [{"resource": self.resource, "scopeLogs": [
                {"scope": self.scope, "logRecords": logs}]}]}
        return out

    def flush(self):
        if not self.enabled:
            return
        for signal, body in self.payloads().items():
            req = urllib.request.Request(f"{self.endpoint}/v1/{signal}", data=json.dumps(body).encode(),
                                         headers=self.headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=5) as r:
                    r.read()
                self.sent[signal] += 1
            except Exception:  # noqa: BLE001 - telemetry must never break detection
                self.sent["errors"] += 1

    def start(self):
        if not self.enabled:
            return self

        def loop():
            while not self._stop.wait(self.interval):
                self.flush()
        threading.Thread(target=loop, daemon=True).start()
        return self

    def stop(self):
        self._stop.set()
        self.flush()
