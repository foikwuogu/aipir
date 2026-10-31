#!/usr/bin/env bash
# Build the final Zenodo package for this branch's release. Run ONLY after the author has
# completed docs/VERIFY_CHECKLIST.md.   Usage: ./scripts/make_zenodo_release.sh YYYY-MM-DD
set -euo pipefail
cd "$(dirname "$0")/.."
date="${1:?give the publication date, e.g. 2026-11-02}"
[[ "$date" =~ ^20[0-9]{2}-[01][0-9]-[0-3][0-9]$ ]] || { echo "date must be YYYY-MM-DD"; exit 1; }
ver=$(python3 -c "import re;print(re.search(r'^version: \"([^\"]+)\"', open('CITATION.cff').read(), re.M).group(1))")
python3 - "$date" <<'PY'
import json, re, sys
d = sys.argv[1]
ids = json.load(open("docs/release_ids.json")); ids["release_date"] = d
json.dump(ids, open("docs/release_ids.json", "w"), indent=2)
c = open("CITATION.cff").read()
c = re.sub(r'^date-released: .*$', f'date-released: "{d}"', c, flags=re.M)
open("CITATION.cff", "w").write(c)
PY
python3 code/05_figures.py --final
node code/06_document.js --final
python3 code/08_readme.py --final
python3 scripts/publish_gate.py . --allow-draft-in code/ framework/ scripts/ tests/ docs/PUBLISH_GUIDE.md docs/BUILD_SPEC.md docs/ZENODO_UPLOAD.md docs/training/
out="../aipir-v${ver}.zip"
rm -f "$out"
here="$(basename "$PWD")"; (cd .. && zip -qr "aipir-v${ver}.zip" "$here" -x "*/data/raw/*/*.csv.gz" "*/.git/*" "*/deploy/compose/.lab/*" "*/__pycache__/*" "*/.terraform/*" "*.pem")
echo "built $out for v${ver}, release date ${date}. Commit the final files: git add -A && git commit -m 'Release v${ver}'"
