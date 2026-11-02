#!/usr/bin/env bash
# Reproduce every committed output from scratch. About 45 min on 2 vCPU / 8 GB.
set -euo pipefail
cd "$(dirname "$0")"
python code/01_fetch.py
python -W ignore code/02_build.py | tee data/processed/build_log.txt
python code/03_recovery_scenario.py
python -W ignore code/04_qa.py
python -W ignore code/07_lab_check.py
python -m pytest -q tests                         # unit tests (needs pytest)
python tests/integration/drift_demo.py
python -W ignore tests/integration/lab_stack_check.py   # uses otelcol-contrib and ansible-playbook if on PATH
./deploy/validate.sh                              # IaC library; missing tools are reported as SKIP
python code/05_figures.py "$@"                    # add --final only after the verification gate
node code/06_document.js "$@"
node docs/training/build_deck.js                  # training deck (set PPTX_SKILL_DIR to apply theme colours)
python code/08_readme.py "$@"
python code/09_dashboard.py                        # static results dashboard (site/, published to GitHub Pages)
