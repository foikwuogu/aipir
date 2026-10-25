# AIPIR - AI-Enabled Predictive Infrastructure Resilience Framework

**Status: DRAFT v0.1.0 - results not yet verified by the authors; do not cite.**

AIPIR is an open, cloud-native framework that connects **detection, response and recovery** for
energy-sector control systems in one reproducible loop:

| Layer | What it does | Where |
|---|---|---|
| 1 Observe | Reads 1 Hz plant telemetry; exposes score, threshold, per-process alarm and per-sensor residuals as Prometheus metrics | `framework/aipir/service.py` |
| 2 Predict | Ridge forecaster predicts every sensor 1 s ahead from 30 s of history; robust, causal residual score | `framework/aipir/detectors.py` |
| 3 Respond | Threshold calibrated on normal data only (1 alarm/day); debounced alarms routed to boiler / turbine / water process | `framework/aipir/metrics.py`, `routing.py`, `deploy/prometheus` |
| 4 Recover | Alertmanager webhook selects the process playbook (dry-run); Terraform + Kubernetes restore the stack to a known-good state | `deploy/` |

It is validated on the open **HAI** security datasets (a hardware-in-the-loop testbed emulating
steam-turbine power generation and pumped-storage hydropower) against three baselines, with every
threshold set to the same false-alarm budget and all design choices frozen on one development file.

## Headline results (held-out data)

HAI 21.03, 45 attacks over 4.2 days:

| Detector | Attacks detected | Median time-to-detect (s) | Point-wise F1 | False alarms/day | Routed to attacked process |
|---|---|---|---|---|---|
| Static limits | 37/45 | 19 | 0.57 | 0.00 | 100% |
| PCA residual | 40/45 | 33 | 0.68 | 0.48 | 80% |
| Isolation Forest | 0/45 | - | 0.00 | 0.00 | - |
| **AIPIR predictive** | 35/45 | 16 | 0.69 | 0.72 | 100% |

HAI 20.07 (replication), 38 attacks over 5.1 days:

| Detector | Attacks detected | Median time-to-detect (s) | Point-wise F1 | False alarms/day | Routed to attacked process |
|---|---|---|---|---|---|
| Static limits | 20/38 | 70 | 0.13 | 0.00 | 100% |
| PCA residual | 27/38 | 58 | 0.55 | 18.46 | 100% |
| Isolation Forest | 25/38 | 120 | 0.32 | 16.13 | - |
| **AIPIR predictive** | 21/38 | 68 | 0.45 | 0.39 | 86% |

**Read honestly:** On HAI 21.03, AIPIR detects attacks earliest and routes them correctly, with the best F1 on
HAI 21.03, but static limits and PCA detect *more* attacks; on HAI 20.07 every detector is weak.
The detectors miss different attacks, so AIPIR is best used as a layer on top of existing alarms.

**Downtime scenario** (assumed recovery times, not measured; `code/03_recovery_scenario.py`):
relative to static alarms with manual recovery, AIPIR with automated recovery cuts total downtime
over the 83 held-out attacks by 19.4% (range
0.6-49.9% across assumptions); AIPIR with
manual recovery changes it by +2.5%; an exploratory layered setup (static limits + AIPIR)
cuts it by 49.5%. See `docs/LIMITATIONS.md`.

## Reproduce

```bash
pip install -r requirements.txt          # Python 3.12-3.13; Node 18+ for the manuscript (npm i docx)
./run_all.sh                             # fetch HAI at a pinned commit, fit, evaluate, QA, figures, paper
python -m pytest -q tests                # unit tests (synthetic data, seconds)
```

Outputs: `data/processed/` (scores, events, metrics, `qa_report.txt`), `paper/stats.json`,
`paper/figures/`, `paper/tables/`, `paper/AIPIR_manuscript.docx`. Every number in the paper and in
this README is read from `paper/stats.json`.

## Run the framework (lab mode)

```bash
# detector service replaying a held-out HAI file at 60x
PYTHONPATH=framework python -m aipir.service --model models/aipir_hai2103.joblib \
    --replay data/raw/hai-21.03/test2.csv.gz --speed 60 --port 9108
curl localhost:9108/metrics

# full stack: detector + Prometheus + Alertmanager + Grafana (http://localhost:3000)
docker compose -f deploy/docker-compose.yml up --build

# any Kubernetes cluster (cloud or plant edge)
terraform -chdir=deploy/terraform init && terraform -chdir=deploy/terraform apply
```

Recovery runs in **dry-run** mode: the service logs which playbook it would start and never writes
to a control system. See `deploy/RUNBOOK.md`.

## Data and sources

- HAI security dataset, versions 21.03 and 20.07, https://github.com/icsdataset/hai at commit
  `2a814ce`, CC BY-SA 4.0. Please cite: Shin, Lee, Yun, Min, *Two ICS Security Datasets and Anomaly
  Detection Contest on the HIL-Based Augmented ICS Testbed*, CSET '21, doi:10.1145/3474718.3474719.
  Provenance (SHA-256 per file) in `data/raw/PROVENANCE.txt`.
- No employer, operator or customer data is used anywhere in this project.

## Repository map

`code/` numbered pipeline (01 fetch ... 08 README) - `framework/aipir/` the framework package -
`deploy/` Docker, Prometheus, Alertmanager, Grafana, Kubernetes, Terraform, runbook - `tests/` -
`docs/` build spec, codebook, limitations, verification checklist, next steps, publish guide -
`paper/` stats, figures, tables, manuscript - `models/` fitted models (CC BY-SA 4.0).

## License

Code MIT (`LICENSE`); derived data and models CC BY-SA 4.0 (required by HAI); paper and docs
CC BY 4.0. Details in `LICENSE-DATA.md`.

## Citation and contact

Friday Ogochukwu Ikwuogu; Abidemi Orimogunje; Eria Othieno Pinyi; David Mike-Ewewie. *AIPIR: AI-Enabled Predictive Infrastructure Resilience Framework*, v0.1.0, 2026.
See `CITATION.cff`. Maintainer: Friday Ogochukwu Ikwuogu (Friday.ikwuogu@gmail.com,
ORCID 0009-0009-2222-1318).
