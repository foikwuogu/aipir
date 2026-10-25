#!/usr/bin/env bash
# Validate every template in the AIPIR IaC library with the real tools, when they are installed.
# Writes data/processed/iac_validation.txt. Missing tools are reported as SKIPPED, never as passed.
#   terraform or tofu, promtool, amtool, otelcol-contrib, ansible-playbook, kubeconform (+ schemas)
set -uo pipefail
cd "$(dirname "$0")/.."
out=data/processed/iac_validation.txt; : > "$out"
pass=0; fail=0; skip=0
log() { echo "$1" | tee -a "$out"; }
run() { local name="$1"; shift; if "$@" >/tmp/aipir_val.log 2>&1; then log "PASS  $name"; pass=$((pass+1)); else log "FAIL  $name"; sed 's/^/      /' /tmp/aipir_val.log | tail -8 | tee -a "$out"; fail=$((fail+1)); fi; }
skip() { log "SKIP  $1 ($2 not installed)"; skip=$((skip+1)); }
log "AIPIR IaC library validation - $(date -u +%Y-%m-%dT%H:%M:%SZ)"

TF=$(command -v terraform || command -v tofu || true)
[ -n "$TF" ] && log "terraform binary: $($TF version | head -1)"
if [ -n "$TF" ]; then
  run "terraform fmt (all modules)" "$TF" fmt -check -recursive deploy/terraform
  for e in deploy/terraform/environments/*/; do
    run "terraform validate $(basename "$e")" bash -c "cd '$e' && '$TF' init -backend=false -input=false >/dev/null && '$TF' validate -no-color; rc=\$?; rm -rf .terraform .terraform.lock.hcl; exit \$rc"
  done
else skip "terraform fmt/validate" "terraform/tofu"; fi

if command -v promtool >/dev/null; then
  run "promtool check rules" promtool check rules deploy/observability/prometheus/alert_rules.yml
  run "promtool test rules (alert unit tests)" bash -c "cd tests/promtool && promtool test rules alert_rules_test.yml"
  run "promtool check config" bash -c 'd=$(mktemp -d); mkdir -p $d/secrets; echo t > $d/secrets/scraper.token; sed "s#/etc/prometheus/#$d/#g" deploy/observability/prometheus/prometheus.yml > $d/p.yml; cp deploy/observability/prometheus/alert_rules.yml $d/; promtool check config $d/p.yml'
else skip "promtool checks" "promtool"; fi

if command -v amtool >/dev/null; then
  run "amtool check-config" bash -c 'd=$(mktemp -d); mkdir -p $d/secrets; echo t > $d/secrets/relay.token; sed "s#/etc/alertmanager/#$d/#" deploy/observability/alertmanager/alertmanager.yml > $d/a.yml; amtool check-config $d/a.yml'
else skip "amtool check-config" "amtool"; fi

if command -v otelcol-contrib >/dev/null; then
  run "otelcol validate" otelcol-contrib validate --config=deploy/observability/otel/otel-collector.yaml
else skip "otelcol validate" "otelcol-contrib"; fi

if command -v ansible-playbook >/dev/null; then
  for p in deploy/ansible/playbooks/*.yml; do
    run "ansible syntax $(basename "$p")" env ANSIBLE_CONFIG=deploy/ansible/ansible.cfg ansible-playbook --syntax-check "$p"
  done
else skip "ansible syntax-check" "ansible-playbook"; fi

if command -v kubeconform >/dev/null; then
  loc="${KUBECONFORM_SCHEMAS:-default}"
  run "kubeconform k8s/base (strict, 1.30)" kubeconform -strict -summary -kubernetes-version 1.30.0 \
      -schema-location "$loc" -ignore-filename-pattern kustomization deploy/k8s/base/
else skip "kubeconform" "kubeconform"; fi

run "YAML parse (all deploy/*.yml)" python3 -c "import yaml,glob; [list(yaml.safe_load_all(open(f))) for f in glob.glob('deploy/**/*.y*ml', recursive=True)]"
run "Grafana dashboard JSON" python3 -c "import json; json.load(open('deploy/observability/grafana/provisioning/dashboards/aipir.json'))"
run "bash syntax (scripts)" bash -n deploy/compose/gen-lab-secrets.sh deploy/drift/init-baseline.sh
log "SUMMARY pass=$pass fail=$fail skip=$skip"
[ "$fail" -eq 0 ]
