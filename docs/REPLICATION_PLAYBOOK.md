# AIPIR open-access replication playbook

**Purpose:** let another facility (energy, water, healthcare, transportation) stand up AIPIR in
a non-production environment, measure its own baseline, run a pilot, and report results in a
way that can be compared with other sites.

**License:** CC BY 4.0 (this document); code MIT; templates in `deploy/`.

**Status:** the framework, templates and lab validation are complete. Field results exist only
where a site has run the pilot and published its own measurements; this repository contains none.

---

## 0. Before you start (go / no-go)

| Item | Needed | Owner |
|---|---|---|
| Executive sponsor and a named pilot lead | yes | Site |
| **Non-production** environment: a test bench, simulator, historian replica, or mirrored telemetry. AIPIR has no write path to production controllers. | yes | Site OT engineering |
| A data-handling agreement (NDA, anonymization rules, what may be published) | yes | Site legal / security |
| An identity provider with MFA (Entra ID templates included; any OIDC provider works) | yes | Site IAM |
| A Kubernetes cluster (cloud or edge) or a Docker host for the lab stack | yes | Site IT |
| Management-of-change approval for any recovery command that touches equipment | before execute mode | Site OT engineering |
| People: a pilot lead, one OT engineer, one IT/cloud engineer, one security reviewer; 30 engineers trained in Phase 4 | yes | Site |

Stop if the only available environment is production.

## 1. Phase 1 - Baseline assessment (month 1)

1. **Lab first.** Follow `docs/training/labs/LAB1.md` to run the HAI replay stack. This confirms
   the toolchain before touching site systems.
2. **Identity.** Apply `deploy/terraform/environments/azure-entra` with MFA in report-only mode.
   Create the role groups and assign people (`deploy/zero-trust/README.md`).
3. **Observability.** Deploy the OTel Collector, Prometheus and Grafana (`deploy/README.md`,
   templates 3, 8 and 10). Connect the site's existing telemetry through an OTLP or Prometheus
   source.
4. **Baseline KPIs.** Collect at least **30 days** of incident records with the current process,
   before AIPIR alerts anyone. Use the definitions in section 5, and log every configuration
   change in the change ledger.
5. **Data inventory.** List subsystems, points, sampling rates and labelling sources. Agree what
   counts as an incident.

**Exit criterion:** baseline incident records, outage records and the change log exist for the
baseline window, recorded with the section 5 definitions.

## 2. Phase 2 - Framework deployment (months 2-3)

1. **Model.** Fit AIPIR on **normal** site data (`code/02_build.py` pattern: fit on 80%,
   calibrate the threshold on 20%, false-alarm budget agreed with operations). Freeze the
   configuration and record it.
2. **Deploy** `deploy/terraform/environments/lab-k8s` with `auth.mode = "rs256"` and the Entra
   values from Phase 1. Keep `recovery_mode = "dry-run"`.
3. **Zero-Trust checks.** Run `tests/integration/lab_stack_check.py` against the deployed stack (it
   needs lab tokens; in the pilot, repeat its checks with real identities), and confirm the
   NetworkPolicy blocks egress.
4. **Drift baseline.** Run `deploy/drift/init-baseline.sh` and schedule `drift_check.yml` or the
   CronJob.
5. **Recovery playbooks.** Fill in `deploy/ansible/inventory/site.yml`, run every playbook in
   check mode, and take the site commands through management of change.
6. **Controlled incident simulation.** On the non-production environment only, inject a scripted
   set of faults or attacks, as the HAI datasets do. Record each with the section 5 timestamps.

**Exit criterion:** AIPIR alerts are flowing, routing is checked against the simulations, and
check-mode recoveries succeed.

## 3. Phase 3 - Validation and optimization (months 4-5)

1. Switch to `recovery_mode = "execute"` (two-person approval), still with Ansible in check mode
   until the site signs off. Then enable real restores for the subsystems approved.
2. Collect pilot-period records with exactly the same definitions as the baseline.
3. Run `python -m aipir.kpi` (section 5). Report every KPI, including those that did not
   improve.
4. Tune thresholds only on **normal** data or a held-out set, never on the pilot incidents you
   report. Record any change and its date.

## 4. Phase 4 - Reporting and knowledge transfer (month 6)

1. **Pilot report.** Use the sections of `paper/AIPIR_manuscript.docx` as a template, plus the
   `aipir.kpi` Markdown table. Include the data-handling statement and the limitations.
2. **Dataset.** Publish only what the data agreement allows, anonymized, with a codebook (see
   `docs/CODEBOOK.md` for the pattern) and a DOI.
3. **Training.** Run the workshop in `docs/training/` (one day, up to 30 participants per cohort).
4. **Share back.** Send your KPI table and lessons learned to the AIPIR repository (issue or pull
   request), so the replication record grows.

## 5. KPI definitions and measurement protocol

| KPI | Definition | Source | Tool |
|---|---|---|---|
| Time to detect (per incident) | `detected - start`. `start` is the first evidence of the incident, set in the post-incident review; `detected` is the first alert or human report. | Incident records; AIPIR `aipir.alarm` trace | `aipir.kpi` |
| MTTD | Mean (and median) time to detect over the phase | as above | `aipir.kpi` |
| Time to recover | `recovered - detected`, where `recovered` is when the service is verified restored | Incident records; `aipir.recovery` trace; Ansible evidence files | `aipir.kpi` |
| MTTR | Mean (and median) time to recover over the phase | as above | `aipir.kpi` |
| Availability | `1 - downtime / (window x subsystems)`, from outage intervals | Outage records or uptime monitoring | `aipir.kpi` |
| Misconfigurations per 100 changes | `100 x changes later found to be misconfigurations / all changes`. Drift findings without an approved change count as misconfigurations. | Change ledger + drift reports | `aipir.drift`, `aipir.kpi` |

**Record formats** (CSV, read by `python -m aipir.kpi`):

```
incidents.csv : incident_id,phase,subsystem,start,detected,recovered
periods.csv   : phase,start,end
outages.csv   : phase,subsystem,start,end              (optional)
changes.csv   : phase,change_id,misconfiguration        (optional, 0/1)
```

```bash
PYTHONPATH=framework python -m aipir.kpi --incidents incidents.csv --periods periods.csv \
    --outages outages.csv --changes changes.csv --out pilot_kpis
```

The tool reports per-phase KPIs and the change against the SOW targets. It also reports Welch's
t-test and Mann-Whitney U (baseline vs pilot), a one-way ANOVA over phase x subsystem groups,
and a regression of MTTR on the pilot indicator with subsystem as covariate. Statistics are
computed only when each phase has at least 5 incidents.

**Rules that keep the comparison honest**

- Use the same incident definition and the same observers in both phases.
- Fix the observation windows before the pilot starts.
- Do not drop incidents after the fact. If one is excluded, record why.
- Report medians alongside means; a few long incidents dominate means.
- State the number of incidents. With few incidents, report the result as descriptive.

## 6. Data handling

- Anonymize asset names and personal identifiers before data leaves the site (keep the mapping
  on site).
- Telemetry stays in the non-production environment unless the agreement allows export.
- Audit logs contain user identities. Retain them under the site's security-log policy, not in
  the public dataset.

## 7. What "replicated" means

A site has replicated AIPIR when it can show:
1. the deployed templates (Terraform state or manifests),
2. the validation report (`deploy/validate.sh` output),
3. the Zero-Trust checks passing,
4. baseline and pilot KPI tables produced with section 5,
5. the training record.
