#!/usr/bin/env bash
# Create (or refresh, after an approved change) the signed configuration baseline for this site.
# The private signing key stays on the admin workstation / in a vault - never in git.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; root="$(cd "$here/../.." && pwd)"
export PYTHONPATH="$root/framework"
key="${AIPIR_DRIFT_KEY:-$here/baseline_signing.pem}"
[ -f "$key" ] || python3 -m aipir.drift keygen --out "$key"
cd "$root"
python3 -m aipir.drift baseline --sign "$key" --out deploy/drift/baseline.json \
  --paths deploy/observability deploy/ansible/playbooks deploy/ansible/roles deploy/ansible/baselines \
          deploy/zero-trust deploy/k8s/base
echo "baseline signed with $key; public key: $key.pub"
