# AIPIR recovery runbook (Respond + Recover layers)

This runbook is what the `AIPIRProcessAnomaly` alert hands to the operator and to the
`/recover` webhook. In this repository the webhook runs in **dry-run** mode: it logs which
playbook it would start and never writes to a control system. Wiring `execute` mode to a
site's own automation (Ansible, a historian-approved setpoint restore, a vendor tool) is a
site decision that requires the plant's management-of-change process.

## 1. Triage (first 5 minutes, any process)

1. Confirm the alert in Grafana (*AIPIR - Predictive Infrastructure Resilience*): score above
   threshold, routed process, top contributing sensors.
2. Compare the top sensors against an independent reading (local gauge, redundant
   transmitter, historian) to separate a **sensor/telemetry manipulation** from a **real
   process upset**.
3. Open an incident; record alert time, routed process, top sensors.

## 2. Process playbooks

| Routed process | Playbook | Immediate containment | Restore | Verify |
|---|---|---|---|---|
| P1 boiler (DCS) | `playbook-boiler` | Block remote writes to the DCS engineering/OPC path | Restore last-known-good setpoints (B2004, B3004, B3005, B4002) from the signed baseline | FCV/LCV loops track setpoints for 10 min; AIPIR score below threshold |
| P2 turbine (DCS) | `playbook-turbine` | Hold governor at safe speed reference | Restore Mark VIe configuration from the signed baseline | RPM loop stable; vibration (VXT/VYT) within normal band |
| P3 water treatment (PLC) | `playbook-water` | Switch PLC to local/manual | Restore level setpoints and pump/valve states | Level (LIT01) and flow (FIT01) stable |

## 3. Recover the monitoring stack itself (Infrastructure-as-Code)

The detection stack is declared in `deploy/terraform` and `deploy/k8s`. If a monitoring
node, model, or configuration is suspected compromised:

```bash
# rebuild every AIPIR resource to the declared known-good state
terraform -chdir=deploy/terraform apply -var image=ghcr.io/OWNER/aipir:<known-good-tag>

# or roll the detector back one revision without Terraform
kubectl -n aipir rollout undo deployment/aipir-detector
kubectl -n aipir rollout status deployment/aipir-detector
```

Two replicas plus a PodDisruptionBudget keep detection running while a pod is replaced;
liveness probes restart a hung detector automatically; the NetworkPolicy gives the detector
no egress, so a compromised detector cannot reach the control network.

## 4. Close out

Record time-to-detect (alert time minus first evidence), time-to-recover, root cause, and
whether routing pointed to the right process. These are the same measures the AIPIR
validation reports, so field incidents can be compared with the HAI results.
