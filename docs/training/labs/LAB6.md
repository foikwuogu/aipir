# Lab 6 - IaC, configuration drift and pilot KPIs (60 min)

**Objective:** validate the template library, catch drift, and compute KPIs from records.
**Layer:** Recover + measurement.

## Steps

1. Validate the library: `./deploy/validate.sh` (tools that are not installed are reported as SKIP).
2. Read one module end to end: `deploy/terraform/modules/aipir-detector/main.tf`. Find the
   NetworkPolicy and explain each allow rule.
3. Drift:
   ```bash
   python tests/integration/drift_demo.py     # clean -> unapproved edit -> recorded change -> tampered baseline -> k8s image swap
   ```
   Read `data/processed/drift_demo.json`. Which finding would raise `AIPIRUnapprovedConfigDrift`?
4. KPIs with **synthetic practice records** (not pilot data):
   ```bash
   python docs/training/make_practice_records.py
   python -m aipir.kpi --incidents /tmp/aipir_practice/incidents.csv --periods /tmp/aipir_practice/periods.csv \
       --changes /tmp/aipir_practice/changes.csv --out /tmp/aipir_practice/kpis
   ```
   Which SOW targets does the practice pilot meet? What does the regression add beyond the means?

## Discussion

- Why must baseline and pilot use the same incident definition and observers?
- Why are drift findings without a change record counted as misconfigurations?

## Check

You can run the KPI tool on your own site's records and explain each number in the output.
