# AIPIR recovery runbook (Respond + Recover layers)

Use this runbook when an `AIPIRProcessAnomaly` alert fires, a recovery waits for approval, or
the configuration drifts. By default the service runs in **dry-run** mode: it records which
playbook it would start and does nothing else. In **execute** mode a recovery runs only after a
second person approves it with MFA. Even then Ansible runs in check mode until the site sets
`AIPIR_ANSIBLE_CHECK=0` through its management-of-change process.

## 1. Triage (first 5 minutes, any process)

1. Confirm the alert in Grafana (*AIPIR - Predictive Infrastructure Resilience*). Look at the
   score against the threshold, the routed process, and the top contributing sensors.
2. Compare the top sensors with an independent reading (local gauge, redundant transmitter,
   historian). This tells a **sensor or telemetry manipulation** apart from a **real process upset**.
3. Open an incident. Record the alert time, routed process, and top sensors. The OpenTelemetry
   trace `aipir.alarm` holds the same data.

## 2. Request and approve a recovery

Alertmanager has already filed a request (`GET /recoveries` shows it as `pending_approval`). An
operator can also file one: `POST /recover {"process": "P1"}`. This needs the operator role and MFA.

The approver must be a different person, with the `aipir.recovery-approver` role and MFA:

```bash
curl -X POST -H "Authorization: Bearer $APPROVER_TOKEN" https://<aipir>/recoveries/<id>/approve
```

The service then runs the process playbook through Ansible and returns the result. The request
and both identities are written to the hash-chained audit log, and an evidence record is written
per host.

## 3. Process playbooks

| Routed process | Ansible playbook | Immediate containment | Restore | Verify |
|---|---|---|---|---|
| P1 boiler (DCS) | `deploy/ansible/playbooks/recover_boiler.yml` | Block remote writes to the DCS engineering/OPC path | Site command restores the last-known-good setpoints from the signed baseline (refused if the baseline hash does not match) | Site verify command: FCV/LCV loops track setpoints; AIPIR score below threshold |
| P2 turbine (DCS) | `recover_turbine.yml` | Hold the governor at a safe speed reference | Restore the Mark VIe configuration from the signed baseline | RPM loop stable; vibration (VXT/VYT) within the normal band |
| P3 water treatment (PLC) | `recover_water.yml` | Switch the PLC to local/manual | Restore level setpoints and pump/valve states | Level (LIT01) and flow (FIT01) stable |

The lab inventory replaces every site command with an `echo`. A real site fills them in
`inventory/site.yml`, starting from `site.example.yml`.

## 4. Recover the monitoring stack itself (Infrastructure-as-Code)

```bash
# approved through the same workflow: POST /recover {"process": "MON"} then approve
# or by hand:
terraform -chdir=deploy/terraform/environments/lab-k8s apply -var image=ghcr.io/OWNER/aipir:<known-good-tag>
kubectl -n aipir rollout undo deployment/aipir-detector && kubectl -n aipir rollout status deployment/aipir-detector
```

Two replicas plus a PodDisruptionBudget keep detection running while a pod is replaced. Liveness
probes restart a hung detector. The NetworkPolicy gives the detector no route to the control
network.

## 5. Configuration drift (`AIPIRUnapprovedConfigDrift`)

```bash
PYTHONPATH=framework python -m aipir.drift check --baseline deploy/drift/baseline.json \
  --pubkey deploy/drift/baseline_signing.pem.pub --ledger deploy/drift/changes.jsonl \
  --k8s-declared deploy/k8s/base --kubectl --out drift_report.json
```

- **The change was approved:** record it with
  `python -m aipir.drift record-change --ledger deploy/drift/changes.jsonl --item <path or Kind/ns/name> --by <you> --ticket <CHG-id>`.
  Then refresh the baseline (`deploy/drift/init-baseline.sh`).
- **The change was not approved:** treat it as a security event. Restore the declared state
  (section 4 for the stack, `git checkout` for files) and investigate who made it. Check the
  audit log.
- **The baseline signature is invalid:** the baseline itself was altered. Stop. Rebuild it from
  version control on a trusted workstation.

## 6. Close out

Record time-to-detect (alert time minus first evidence), time-to-recover (request to verified
recovery; the `aipir.recovery` trace gives both timestamps), root cause, and whether routing
pointed to the right process. These are the inputs of the pilot KPIs in
`docs/REPLICATION_PLAYBOOK.md`, section 5.
