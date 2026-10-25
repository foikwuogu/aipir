#!/usr/bin/env bash
# Reproduce every committed output from scratch. ~40 min on 2 vCPU / 8 GB.
set -euo pipefail
cd "$(dirname "$0")"
python code/01_fetch.py
python -W ignore code/02_build.py | tee data/processed/build_log.txt
python code/03_recovery_scenario.py
python -W ignore code/04_qa.py
python -W ignore code/07_lab_check.py
python code/05_figures.py "$@"          # add --final only after the verification gate
node code/06_document.js "$@"
python code/08_readme.py "$@"
