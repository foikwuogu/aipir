# Lab 4 - OpenTelemetry: metrics, traces and logs (40 min)

**Objective:** follow an alarm and a recovery through OpenTelemetry. **Layer:** Observe.

## Steps

1. Start a collector with the AIPIR config (binary `otelcol-contrib` from the OpenTelemetry
   releases page, or the `otel-collector` service in `deploy/compose`):
   ```bash
   otelcol-contrib --config=deploy/observability/otel/otel-collector.yaml &
   ```
2. Restart the service with `OTEL_EXPORTER_OTLP_ENDPOINT=http://127.0.0.1:4318` (Lab 3 command).
3. After 15 s, read the metrics the collector re-exports:
   `curl -s 127.0.0.1:8889/metrics | grep otel_aipir`.
4. Request and approve a recovery (Lab 3 steps 4 and then approve with `$APPROVER`).
5. Read the trace and log evidence:
   `grep -o '"name":"aipir\.[a-z]*"' /tmp/aipir-otel-evidence.jsonl | sort | uniq -c`.

## Questions

- Which attributes on the `aipir.alarm` span help a responder most?
- Which processor in the collector config removes token material, and why does that matter?

## Check

You can find the start and end time of an alarm episode and of a recovery from the traces;
these are the inputs to MTTD and MTTR.
