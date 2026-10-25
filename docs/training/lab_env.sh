# Source this from the repository root:  source docs/training/lab_env.sh
# Sets a fresh lab secret and mints one token per training persona (LAB ONLY, 4-hour tokens).
export AIPIR_ENV=lab AIPIR_AUTH_MODE=hs256 AIPIR_ISSUER=aipir-lab AIPIR_AUDIENCE=api://aipir
export AIPIR_LAB_SECRET="$(python3 -c 'import secrets;print(secrets.token_urlsafe(32))')"
export PYTHONPATH="$PWD/framework${PYTHONPATH:+:$PYTHONPATH}"
export AIPIR_AUDIT_LOG=/tmp/aipir_lab_audit.jsonl ANSIBLE_CONFIG="$PWD/deploy/ansible/ansible.cfg"
_m() { python3 -m aipir.zerotrust mint --ttl 14400 "$@"; }
export VIEWER=$(_m --sub vera --role aipir.viewer)
export OPERATOR=$(_m --sub bob --role aipir.operator --mfa)
export OPERATOR_NOMFA=$(_m --sub bob --role aipir.operator)
export APPROVER=$(_m --sub carol --role aipir.recovery-approver --mfa)
export BOB_APPROVER=$(_m --sub bob --role aipir.recovery-approver --mfa)
export RELAY=$(_m --app --sub alertmanager --role aipir.alert-relay)
export SCRAPER=$(_m --app --sub prometheus --role aipir.metrics-scraper)
api() { local m=$1 p=$2 t=$3; shift 3; curl -s -w '  [HTTP %{http_code}]\n' -X "$m" -H "Authorization: Bearer $t" -H 'Content-Type: application/json' "http://127.0.0.1:9108$p" "$@"; }
echo "lab environment ready: tokens VIEWER OPERATOR OPERATOR_NOMFA APPROVER BOB_APPROVER RELAY SCRAPER; helper: api METHOD PATH TOKEN"
