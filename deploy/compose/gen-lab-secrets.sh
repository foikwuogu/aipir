#!/usr/bin/env bash
# LAB ONLY: generate a random HS256 secret and the two workload tokens the compose stack needs.
# Files go to deploy/compose/.lab/ (git-ignored). For a pilot use Entra ID (rs256) instead.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../.." && pwd)"
mkdir -p "$here/.lab/prometheus" "$here/.lab/alertmanager"
secret="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')"
printf 'AIPIR_LAB_SECRET=%s\n' "$secret" > "$here/.lab/lab-secrets.env"
chmod 600 "$here/.lab/lab-secrets.env"
mint() { AIPIR_LAB_SECRET="$secret" PYTHONPATH="$root/framework" python3 -m aipir.zerotrust mint --app --ttl 2592000 "$@"; }
mint --sub prometheus --role aipir.metrics-scraper > "$here/.lab/prometheus/scraper.token"
mint --sub alertmanager --role aipir.alert-relay > "$here/.lab/alertmanager/relay.token"
echo "lab secrets and workload tokens written to $here/.lab (valid 30 days)"
echo "mint a person token:  AIPIR_LAB_SECRET=\$(cut -d= -f2 $here/.lab/lab-secrets.env) PYTHONPATH=framework python -m aipir.zerotrust mint --sub alice --role aipir.operator --mfa"
