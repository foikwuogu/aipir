# AIPIR build spec (v0.1)

```
PROJECT:        AI-Enabled Predictive Infrastructure Resilience (AIPIR) Framework.
                Archetypes: (2) pipeline/tool  +  (6) validation study  +  (9) technical report / preprint.

QUESTION:       Can a lightweight, cloud-native pipeline that predicts expected sensor behaviour,
                flags deviations, routes each alert to the affected sub-process, and triggers
                scripted (Infrastructure-as-Code) recovery detect attacks on a power-generation
                control system earlier and more reliably than fixed alarm limits, and how much
                downtime would that save under stated recovery assumptions?

SOURCES:        HAI 21.03 (primary)  - HIL-based Augmented ICS security dataset, ETRI / NSR (Korea).
                  Testbed emulates steam-turbine power generation + pumped-storage hydropower.
                  https://github.com/icsdataset/hai  commit 2a814cebc9a66b06c9e5cd545e2d72e65d383737
                  (repo last commit 2023-06-07), 1 Hz, 78 process points, 3 normal train files,
                  5 test files with labelled attacks (attack, attack_P1, attack_P2, attack_P3).
                  License CC BY-SA 4.0. Cite Shin et al., CSET '21, doi:10.1145/3474718.3474719.
                HAI 20.07 (replication) - same repo, same license; earlier testbed configuration.
                  Cite Shin et al., USENIX CSET '20 (HAI 1.0).
                Accessed 2026-10-24.

UNIT:           One second of plant telemetry (scoring); one contiguous labelled attack (event metrics);
                one test day (false alarms per day).

MEASURES:       Point-wise precision, recall, F1 against `attack`.
                Event recall: share of attack events with >=1 alarm inside the event (+60 s grace).
                Time-to-detect (TTD): seconds from event start to first alarm.
                False alarms per day: alarm episodes outside any event (+grace), per 24 h of test data.
                Routing accuracy: share of detected events whose top-contributing sensors fall in the
                  process (P1/P2/P3) named by the attack_P* label.
                Downtime-avoided scenario: per event, downtime = TTD + recovery time; recovery time
                  for manual vs IaC-automated recovery is a stated ASSUMPTION swept over a range.

DETECTORS:      D0 static limits   - per-sensor min/max from normal training data (+margin) - the
                                     "classic alarm" baseline.
                D1 PCA residual    - reconstruction error of standardized telemetry.
                D2 Isolation Forest- unsupervised outlier score.
                D3 AIPIR predictive- multi-output ridge forecaster: predicts each sensor 1 s ahead
                                     from a 30 s history; anomaly score = smoothed normalized
                                     forecast residual. Per-sensor residuals give routing.
                Thresholds for all detectors are set on held-out NORMAL data only (no peeking at
                test labels), at a fixed target false-alarm budget.

FRAMEWORK:      Observe  - telemetry replay + Prometheus/OpenMetrics exporter (aipir/exporter.py)
                Predict  - detector service scoring each second (aipir/detect.py)
                Respond  - alert rules + routing to P1 boiler / P2 turbine / P3 water playbooks
                Recover  - Terraform + Kubernetes manifests + recovery runbook (deploy/)
                Lab mode - docker-compose stack (detector, Prometheus, Alertmanager, Grafana).

OUTPUTS:        code/01_fetch.py ... 06_document.py ; data/processed/scores_*.parquet,
                events_*.csv, qa_report.txt ; paper/stats.json ; paper/figures/*.png ;
                paper/AIPIR_manuscript.docx ; framework package ; deploy/ (IaC) ;
                docs/ (CODEBOOK, LIMITATIONS, VERIFY_CHECKLIST, NEXT_STEPS, PUBLISH_GUIDE).

VENUES:         1. GitHub release + Zenodo DOI (software + replication package)
                2. arXiv preprint, primary cs.CR, cross-list eess.SY
                3. Journal/conference after preprint (author chooses; candidates in PUBLISH_GUIDE)

VERIFY POINTS:  V1 Recovery-time assumptions (manual vs automated) used in the downtime scenario.
                V2 Target false-alarm budget used to set thresholds (default: <=1 alarm episode/day
                   on held-out normal data).
                V3 Event grace window (default 60 s) and minimum alarm duration.
                V4 Co-author list and CRediT roles.
                V5 License for derived data (CC BY-SA 4.0 is forced by HAI's share-alike term).
                V6 Confirm NO employer or operator data was used; all results are from HAI.

LICENSE:        Code: MIT.  Derived data/scores: CC BY-SA 4.0 (share-alike from HAI).
                Manuscript and docs: CC BY 4.0.

ASSUMPTIONS:    Proceeding without confirmation on V1-V5 using the defaults above; all are flagged
                [VERIFY] in the outputs and block publication until ruled on.
                No real cloud deployment is performed; IaC is syntax-validated and the stack is
                run in lab mode only. "Downtime reduction" is reported as a scenario, never as a
                measured result.
```

## v0.2 additions (2026-10-24)

```
ADDED:          Zero-Trust controls (tokens, RBAC policy, MFA, two-person rule, hash-chained audit;
                Entra ID and Kubernetes RBAC templates); OpenTelemetry export + Collector config;
                Ansible recovery hook and playbooks; configuration-drift check; IaC template
                library with validate.sh; replication playbook with KPI protocol and calculator;
                training package; SOW traceability.
VALIDATION:     unit tests; lab_stack_check.py against a live OTel Collector and ansible-core;
                deploy/validate.sh with OpenTofu, promtool, amtool, otelcol, ansible, kubeconform.
NOT CHANGED:    detection models, data, results (v0.1 numbers stand).
OPEN:           all SOW measured targets and the 5 TB dataset - site pilot only.
```
