#!/usr/bin/env python3
"""08 - Write README.md with every number interpolated from paper/stats.json."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = "--final" in sys.argv
S = json.load(open(os.path.join(ROOT, "paper", "stats.json")))
A = json.load(open(os.path.join(ROOT, "AUTHORS.json")))
IDS = json.load(open(os.path.join(ROOT, "docs", "release_ids.json")))
DOI = IDS["doi"].replace("https://doi.org/", "")
CONCEPT = (IDS.get("concept_doi") or "").replace("https://doi.org/", "")
R = lambda v, d: S["results"][f"{v}|test|{d}"]  # noqa: E731
a, b = "hai-21.03", "hai-20.07"
c, dt = S["downtime"]["central"], S["downtime"]
pct = lambda x: f"{100 * x:.0f}%"  # noqa: E731
import re  # noqa: E402
LAB = json.load(open(os.path.join(ROOT, "data", "processed", "lab_stack_check.json")))
VAL = re.search(r"SUMMARY pass=(\d+) fail=(\d+) skip=(\d+)",
                open(os.path.join(ROOT, "data", "processed", "iac_validation.txt")).read()).groups()
NTPL = len(re.findall(r"^\| \d+ \|", open(os.path.join(ROOT, "deploy", "README.md")).read(), re.M))
NAME = {"D0": "Static limits", "D1": "PCA residual", "D2": "Isolation Forest", "D3": "**AIPIR predictive**"}


def row(v, k):
    r = R(v, k)
    ttd = "-" if r["ttd_median_s"] is None else f"{r['ttd_median_s']:.0f}"
    route = "-" if r["routing_accuracy"] is None else pct(r["routing_accuracy"])
    return (f"| {NAME[k]} | {r['events_detected']}/{r['events']} | {ttd} | {r['f1']:.2f} | "
            f"{r['false_episodes_per_day']:.2f} | {route} |")


status = ("**Status: v0.2.0 released** - see the DOI badge and CITATION.cff." if FINAL else
          "**Status: DRAFT v0.2.0 - results not yet verified by the authors; do not cite.**")
authors = "; ".join(p["name"] for p in A["authors"] + A["collaborators"])
s1 = c["S1_reduction_pct"]
md = f"""# AIPIR - AI-Enabled Predictive Infrastructure Resilience Framework

[![Zenodo DOI](https://zenodo.org/badge/DOI/{CONCEPT or DOI}.svg)](https://doi.org/{CONCEPT or DOI})

{status}

**[Live results dashboard](https://foikwuogu.github.io/aipir/)** - the headline numbers and
figures below, rebuilt by `code/09_dashboard.py` and published by `.github/workflows/pages.yml`
whenever `paper/` changes.

AIPIR is an open, cloud-native framework that connects **detection, response and recovery** for
energy-sector control systems in one reproducible loop:

| Layer | What it does | Where |
|---|---|---|
| 1 Observe | Reads 1 Hz plant telemetry; Prometheus metrics plus OpenTelemetry metrics, traces (one span per alarm and per recovery) and logs | `framework/aipir/service.py`, `otel.py`, `deploy/observability/` |
| 2 Predict | Ridge forecaster predicts every sensor 1 s ahead from 30 s of history; robust, causal residual score | `framework/aipir/detectors.py` |
| 3 Respond | Threshold calibrated on normal data only (1 alarm/day); debounced alarms routed to boiler / turbine / water process; authenticated Alertmanager webhook | `framework/aipir/metrics.py`, `routing.py`, `deploy/observability/` |
| 4 Recover | Recovery requests with two-person approval run Ansible playbooks (check mode by default); Terraform and Kubernetes restore the stack; signed configuration baseline and drift check | `framework/aipir/recovery.py`, `drift.py`, `deploy/ansible/`, `deploy/terraform/` |
| Zero-Trust | Signed tokens on every call (Entra ID in a pilot), RBAC from a policy file, MFA for sensitive actions, two-person rule, hash-chained audit log, default-deny networking | `framework/aipir/zerotrust.py`, `deploy/zero-trust/` |

It is validated on the open **HAI** security datasets (a hardware-in-the-loop testbed emulating
steam-turbine power generation and pumped-storage hydropower) against three baselines, with every
threshold set to the same false-alarm budget and all design choices frozen on one development file.

## Headline results (held-out data)

HAI 21.03, {R(a, 'D3')['events']} attacks over {R(a, 'D3')['test_days']:.1f} days:

| Detector | Attacks detected | Median time-to-detect (s) | Point-wise F1 | False alarms/day | Routed to attacked process |
|---|---|---|---|---|---|
{chr(10).join(row(a, k) for k in ['D0', 'D1', 'D2', 'D3'])}

HAI 20.07 (replication), {R(b, 'D3')['events']} attacks over {R(b, 'D3')['test_days']:.1f} days:

| Detector | Attacks detected | Median time-to-detect (s) | Point-wise F1 | False alarms/day | Routed to attacked process |
|---|---|---|---|---|---|
{chr(10).join(row(b, k) for k in ['D0', 'D1', 'D2', 'D3'])}

**Read honestly:** On HAI 21.03, AIPIR detects attacks earliest and routes them correctly, with the best F1 on
HAI 21.03, but static limits and PCA detect *more* attacks; on HAI 20.07 every detector is weak.
The detectors miss different attacks, so AIPIR is best used as a layer on top of existing alarms.

**Downtime scenario** (assumed recovery times, not measured; `code/03_recovery_scenario.py`):
relative to static alarms with manual recovery, AIPIR with automated recovery cuts total downtime
over the {c['n_events']} held-out attacks by {c['S2_reduction_pct']:.1f}% (range
{dt['S2_reduction_pct_min']:.1f}-{dt['S2_reduction_pct_max']:.1f}% across assumptions); AIPIR with
manual recovery changes it by {-s1:+.1f}%; an exploratory layered setup (static limits + AIPIR)
cuts it by {c['S3_reduction_pct']:.1f}%. See `docs/LIMITATIONS.md`.

## Platform checks (lab)

- **Zero-Trust, recovery and OpenTelemetry end to end:** {LAB['passed']}/{LAB['total']} checks passed
  (`tests/integration/lab_stack_check.py`, against a live OpenTelemetry Collector, with Ansible
  in check mode).
- **IaC template library:** {NTPL} templates; {VAL[0]} validation checks passed, {VAL[1]} failed,
  {VAL[2]} skipped (`deploy/validate.sh`, using terraform/OpenTofu, promtool, amtool, otelcol,
  ansible-playbook and kubeconform).
- **Configuration drift:** unapproved edits, approved changes, a tampered baseline and a swapped
  container image are all classified correctly (`tests/integration/drift_demo.py`).

These checks show the software works as designed in a lab. They are not pilot results: the SOW's
measured targets (MTTD, MTTR, availability, misconfigurations, the 5 TB dataset) stay open until
the site pilot produces them. See `docs/SOW_TRACEABILITY.md`.

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
source docs/training/lab_env.sh          # lab secret + one token per role
python -m aipir.service --model models/aipir_hai2103.joblib \\
    --replay data/raw/hai-21.03/test2.csv.gz --speed 60 --port 9108 &
api GET /metrics "$SCRAPER"

# full stack: detector + OTel Collector + Prometheus + Alertmanager + Grafana
./deploy/compose/gen-lab-secrets.sh
docker compose -f deploy/compose/docker-compose.yml up --build

# any Kubernetes cluster (cloud or plant edge), and the Entra ID identity controls
terraform -chdir=deploy/terraform/environments/lab-k8s init && terraform -chdir=deploy/terraform/environments/lab-k8s apply
terraform -chdir=deploy/terraform/environments/azure-entra init && terraform -chdir=deploy/terraform/environments/azure-entra apply
```

Every endpoint except `/healthz` needs a token. For lab tokens, see `deploy/README.md` or
`source docs/training/lab_env.sh`. Recovery runs in **dry-run** mode by default. In execute
mode a second person must approve, and Ansible still runs in check mode until the site signs
off. Nothing writes to a control system. See `deploy/RUNBOOK.md`.

## Data and sources

- HAI security dataset, versions 21.03 and 20.07, https://github.com/icsdataset/hai at commit
  `2a814ce`, CC BY-SA 4.0. Please cite: Shin, Lee, Yun, Min, *Two ICS Security Datasets and Anomaly
  Detection Contest on the HIL-Based Augmented ICS Testbed*, CSET '21, doi:10.1145/3474718.3474719.
  Provenance (SHA-256 per file) in `data/raw/PROVENANCE.txt`.
- No employer, operator or customer data is used anywhere in this project.

## Repository map

| Path | Contents |
|---|---|
| `code/` | Numbered pipeline (01 fetch ... 08 README) |
| `framework/aipir/` | Detectors, streaming scorer, service, Zero-Trust, OpenTelemetry, recovery/Ansible hook, drift check, KPI calculator |
| `deploy/` | **IaC template library** (index in `deploy/README.md`): Terraform modules and environments, Kubernetes manifests, Docker/Compose, observability configs, Ansible, Zero-Trust policy, drift baseline, runbook, `validate.sh` |
| `docs/REPLICATION_PLAYBOOK.md` | **Open-access replication playbook** for other facilities, including the KPI protocol |
| `docs/training/` | **Training package**: curriculum, slide deck, six labs, instructor guide with recording script, quiz, evaluation |
| `docs/SOW_TRACEABILITY.md` | Each SOW item: built, built and awaiting pilot, or open |
| `docs/` (other) | Build spec, codebook, limitations, verification checklist, next steps, publish guide |
| `tests/` | Unit tests, Prometheus alert tests, lab integration checks |
| `paper/` | Stats, figures, tables, manuscript |
| `models/` | Fitted models (CC BY-SA 4.0) |

## License

Code MIT (`LICENSE`); derived data and models CC BY-SA 4.0 (required by HAI); paper and docs
CC BY 4.0. Details in `LICENSE-DATA.md`.

## Citation and contact

{authors}. *AIPIR: AI-Enabled Predictive Infrastructure Resilience Framework*, v0.2.0, 2026.
doi:{DOI}{f" (all versions: doi:{CONCEPT})" if CONCEPT else ""}. See `CITATION.cff`. Maintainer: {A['authors'][0]['name']} ({A['authors'][0]['email']},
ORCID {A['authors'][0]['orcid']}).
"""
open(os.path.join(ROOT, "README.md"), "w").write(md)
print("wrote README.md", "(final)" if FINAL else "(DRAFT)")
