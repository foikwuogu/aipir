# AIPIR IaC template library

Reusable, validated templates for deploying, securing, observing, and recovering AIPIR. Every
template is declared as code, so the same files serve for first deployment, for audits, and
for recovery to a known-good state. Run `./deploy/validate.sh` to check them all with the real
tools. Results go to `data/processed/iac_validation.txt`.

Nothing in this library connects to or writes to a control system. Plant-facing recovery
actions are the site's own commands, called through Ansible after two-person approval, in check
mode by default.

## Index

| # | Template | Path | What it gives you | Validated with |
|---|---|---|---|---|
| 1 | Detector module | `terraform/modules/aipir-detector` | Deployment (2 replicas, probes, read-only root, non-root), Service, PodDisruptionBudget, default-deny NetworkPolicy (egress only to DNS and the OTel Collector) | `terraform validate` |
| 2 | Kubernetes RBAC module | `terraform/modules/aipir-k8s-rbac` | Workload service accounts (detector has no API rights; drift checker is read-only; recovery runner can only patch the detector); namespaced roles for people bound to identity-provider groups | `terraform validate` |
| 3 | OTel Collector module | `terraform/modules/otel-collector` | OpenTelemetry Collector Deployment and Service with the AIPIR collector config | `terraform validate`, `otelcol validate` |
| 4 | Entra ID Zero-Trust module | `terraform/modules/entra-zero-trust` | App registration with AIPIR app roles, role assignment required, a security group per role, a workload identity for Alertmanager, a Conditional Access policy requiring MFA | `terraform validate` (needs Entra ID P1 to apply) |
| 5 | Environment: lab / pilot on Kubernetes | `terraform/environments/lab-k8s` | Namespace (restricted pod security) plus modules 1-3 | `terraform validate` |
| 6 | Environment: Entra ID tenant | `terraform/environments/azure-entra` | Module 4, MFA policy in report-only mode first | `terraform validate` |
| 7 | Plain Kubernetes manifests | `k8s/base` (+ `kustomization.yaml`) | The same objects for teams that do not use Terraform, plus the hourly drift-check CronJob | `kubeconform -strict` (Kubernetes 1.30) |
| 8 | Lab stack (Docker Compose) | `compose/` | Detector, OTel Collector, Prometheus, Alertmanager and Grafana, with lab tokens from `gen-lab-secrets.sh` | YAML parse; no Docker daemon in the build environment |
| 9 | Container image | `docker/Dockerfile` | Non-root image with the framework, policy, playbooks and model | Not built in the build environment |
| 10 | Observability configs | `observability/` | Prometheus scrape config (bearer-token auth), six alert rules, Alertmanager routing (authenticated webhook), Grafana dashboard and Entra SSO template, OTel Collector config | `promtool check`, `promtool test rules`, `amtool`, `otelcol validate` |
| 11 | Ansible recovery | `ansible/` | `recover_boiler/turbine/water.yml` (guard, snapshot, baseline integrity check, site restore, verify, evidence), `recover_monitoring.yml` (IaC re-apply or rollback), `drift_check.yml`, `deploy_aipir.yml`; lab and site inventories | `ansible-playbook --syntax-check`; lab runs in check and live mode |
| 12 | Zero-Trust policy | `zero-trust/rbac_policy.yaml` | Roles, permissions, MFA-required actions, workload restrictions, two-person rule | Unit tests (`tests/test_platform.py`) and lab stack check |
| 13 | Drift baseline | `drift/init-baseline.sh` | Signed SHA-256 baseline of the deployable configuration; private key never stored in git | `tests/integration/drift_demo.py` |
| 14 | Recovery runbook | `RUNBOOK.md` | Triage, process playbooks, approval workflow, IaC recovery, drift handling | Review |

## Quick start (lab)

```bash
./deploy/compose/gen-lab-secrets.sh                     # lab secret + workload tokens (git-ignored)
docker compose -f deploy/compose/docker-compose.yml up --build
# a person's token, e.g. an operator who signed in with MFA (lab only)
export AIPIR_LAB_SECRET=$(cut -d= -f2 deploy/compose/.lab/lab-secrets.env)
TOKEN=$(PYTHONPATH=framework python -m aipir.zerotrust mint --sub alice --role aipir.viewer)
curl -H "Authorization: Bearer $TOKEN" localhost:9108/status
```

## Pilot deployment (summary)

1. Apply `terraform/environments/azure-entra` (MFA policy in report-only mode first). Add people
   to the AIPIR groups, then switch the policy to `enabled`.
2. Apply `terraform/environments/lab-k8s` with `auth = { mode = "rs256", issuer = ...,
   audience = ..., jwks_configmap = "aipir-jwks" }`, using the values from step 1.
3. Run `drift/init-baseline.sh` on the admin workstation. Schedule `ansible/playbooks/drift_check.yml`
   or use the CronJob.
4. Copy `ansible/inventory/site.example.yml` to `site.yml`, fill in the site commands, and take them
   through management of change. Then set `recovery_mode = "execute"`. Leave
   `AIPIR_ANSIBLE_CHECK=1` until the site has signed off.

The complete procedure, including KPI measurement, is in `docs/REPLICATION_PLAYBOOK.md`.

## Conventions

- Validated with OpenTofu 1.8 (Terraform-compatible syntax), Prometheus 2.53, Alertmanager 0.27,
  OpenTelemetry Collector contrib 0.111, ansible-core 2.18, and Kubernetes 1.30 schemas.
- Images are pinned to versions. Replace `ghcr.io/OWNER/aipir` with your registry.
- Secrets are never committed. Lab secrets are generated at start-up; pilot identities come from
  Entra ID; recovery credentials belong in your vault.
