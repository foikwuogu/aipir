# Zenodo upload sheet: AIPIR v0.2.0 ("New version" of the v0.1.0 record)

Publish v0.2.0 only after v0.1.0 is published (DOI 10.5281/zenodo.23846615).

## 1. Reserve the v0.2.0 DOI

1. Open the published v0.1.0 record on Zenodo and click **New version**. Zenodo opens a draft that
   copies the v0.1.0 metadata.
2. In the draft, under *Digital Object Identifier*, click **Get a DOI now**. Copy it. It differs
   from the v0.1.0 DOI.
3. On the v0.1.0 record, copy the **concept DOI** ("Cite all versions", in the sidebar).

## 2. Build the final package

```bash
git switch main
python scripts/set_release_ids.py --doi <v0.2.0 DOI> --concept-doi <concept DOI> --repo https://github.com/<user>/aipir
./scripts/make_zenodo_release.sh YYYY-MM-DD      # the date you will press Publish
git add -A && git commit -m "Release v0.2.0"
```

Export `paper/AIPIR_manuscript.docx` to PDF in Word.

## 3. On the draft

1. **Files:** remove the v0.1.0 files Zenodo copied into the draft (trash icon), then upload
   `aipir-v0.2.0.zip` and `AIPIR_manuscript.pdf`.
2. **Version:** 0.2.0. **Publication date:** the date given to the script.
3. **Description:** paste from `docs/zenodo_metadata.json`, then add: "Version 0.2.0 adds Zero-Trust
   controls (OIDC/Entra ID, RBAC, MFA, two-person approval, hash-chained audit), OpenTelemetry
   export, Ansible recovery playbooks, configuration-drift checking, a validated IaC template
   library, an open-access replication playbook and a training package. Results come from the
   public HAI testbed datasets; no operator data is used. SOW pilot targets are not measured here."
4. **Keywords:** add "OpenTelemetry", "zero trust", "Ansible" to the existing ones.
5. **Creators, licenses, related works:** already copied from v0.1.0; check they are unchanged.
   Add "Is supplemented by" with the GitHub URL if it was not on v0.1.0.
6. Click **Preview**, check, then **Publish**.
