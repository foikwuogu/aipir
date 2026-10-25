# SOW traceability: what this repository delivers, and what only the pilot can deliver

This file maps each item of the AIPIR pilot Statement of Work (Exhibit 12) to what exists in this
repository. It is meant to be read alongside the SOW so that no reader mistakes lab work for pilot
results.

**Status key**
- **Built** - implemented here and validated in the lab, on public HAI data and local tooling.
- **Built, awaiting pilot** - the tooling exists here; the measured outcome comes only from the
  site pilot.
- **Open (pilot)** - can only be produced by the pilot at the site. Nothing in this repository
  stands in for it.
- **Site / partner** - owned by the pilot host or the training partner.

## Objectives (SOW section 2)

| # | SOW target | Status | What exists here |
|---|---|---|---|
| 1 | MTTD reduced by 30% or more (12 min baseline to 8 min or less) | Open (pilot); measurement tooling built | `aipir.kpi` computes MTTD from site records; alarm timestamps come from `aipir.alarm` traces. The testbed's detection times (seconds) are not comparable with the site's minutes-scale baseline and must not be reported as pilot results. |
| 2 | MTTR reduced by 40% or more (45 min to 27 min or less) | Open (pilot); measurement tooling built | `aipir.kpi`; recovery timestamps come from `aipir.recovery` traces and the Ansible evidence files. The downtime scenario in the paper uses assumed recovery times and is not an MTTR measurement. |
| 3 | Availability 97.5% to 99.5% or higher | Open (pilot); measurement tooling built | `aipir.kpi` (outage records). |
| 4 | Misconfigurations: 6 to 2 or fewer per 100 changes | Open (pilot); measurement tooling built | `aipir.drift` (signed baseline, change ledger, unapproved-drift count) feeds `aipir.kpi`. |
| 5 | 5 TB or more of labelled telemetry from 10 subsystems | Open (pilot) | Not attempted. No open dataset of that size and scope exists, and synthetic or copied data would misrepresent it. The repository uses about 0.3 GB of open HAI data. `docs/CODEBOOK.md` and the replication playbook (section 4) give the format for the pilot dataset. |

## Scope of work (SOW section 3)

| Phase / item | Status | Where |
|---|---|---|
| P1 Establish secure connectivity to the pilot testbed | Site / partner | Zero-Trust templates ready (`deploy/terraform/modules/entra-zero-trust`, network policies) |
| P1 Collect baseline telemetry and incident logs | Open (pilot) | Protocol: `docs/REPLICATION_PLAYBOOK.md`, section 5 |
| P1 Define KPIs and sampling methodology | Built | `docs/REPLICATION_PLAYBOOK.md`, section 5; `framework/aipir/kpi.py` |
| P1 Observability stack: Prometheus, Grafana, OpenTelemetry | Built | `deploy/observability/`, `framework/aipir/otel.py`; checked against a live OTel Collector (`tests/integration/lab_stack_check.py`) |
| P2 AI models for anomaly detection | Built (testbed-validated) | `framework/aipir/detectors.py`; results in `paper/` |
| P2 AI models for predictive maintenance | Not built | The detector forecasts process behaviour for security and reliability anomalies; equipment-health prediction for maintenance needs site maintenance records |
| P2 Integrate models with IaC pipelines (Terraform/Ansible) | Built | `deploy/terraform/`, `deploy/ansible/`, `framework/aipir/recovery.py` |
| P2 Zero-Trust identity controls (MFA, RBAC, IAM) | Built | `framework/aipir/zerotrust.py`, `deploy/zero-trust/`, Entra ID module, Kubernetes RBAC module |
| P2 Controlled incident simulation to benchmark detection speed | Built for the testbed; Open (pilot) at the site | HAI scripted attacks; site procedure in the replication playbook, Phase 2 step 6 |
| P3 Compare MTTD/MTTR against pre-pilot baselines | Open (pilot); tooling built | `aipir.kpi` |
| P3 Statistical validation (ANOVA, regression) | Built, awaiting pilot | `aipir.kpi`: Welch's t-test, Mann-Whitney U, one-way ANOVA, regression |
| P3 Tune hyperparameters and policy rules for false-positive reduction | Built (method) | False-alarm-budget calibration; budget sweep (`paper/figures/fig4`) |
| P4 Final pilot report | Open (pilot) | Manuscript and KPI report templates |
| P4 Training workshop for 30+ engineers | Built (package); delivery Site / partner | `docs/training/` |
| P4 Open-access replication playbook | Built | `docs/REPLICATION_PLAYBOOK.md` |

## Key deliverables (SOW section 6)

| # | Deliverable | Status |
|---|---|---|
| 1 | Pilot Execution Report | Open (pilot). Architecture and lab findings are documented in `paper/` and `README.md`. |
| 2 | Dataset Repository (labelled data) | Open (pilot). Lab replication data (public HAI, plus derived scores) is in `data/`. |
| 3 | IaC Template Library | **Built** - `deploy/` (14 templates; `deploy/validate.sh`, all checks passing) |
| 4 | Training Package (curriculum, slide deck, recorded session) | **Built** - curriculum, deck, labs, quiz, evaluation, and recording script. The recording itself is made at delivery. |
| 5 | Cost-Benefit and Risk-Reduction Analysis | Open (pilot). Needs site costs and measured outcomes. |

## Data collected (SOW section 5)

| SOW data type | Where AIPIR produces it |
|---|---|
| Telemetry (network flow, sensor readings, application logs) | Observe layer; OTel Collector pipelines (network-flow ingestion is a site integration) |
| Anomaly events | `aipir.alarm` spans and logs; `/status` |
| Recovery metrics (restoration time, rollback success) | `aipir.recovery` spans; `/recoveries`; Ansible evidence files |
| System health (CPU, memory, latency, uptime) | Collector and Prometheus (host metrics receivers are a site integration) |
| User data (role-based access logs, auth success/failure) | Hash-chained audit log and OTel audit logs |
