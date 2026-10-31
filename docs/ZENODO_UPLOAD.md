# Zenodo upload sheet: AIPIR v0.1.0 (reserved DOI 10.5281/zenodo.23846615)

This DOI was reserved on a Zenodo **draft**. It becomes live only when you press **Publish**, and
after that the record's files can never be changed. Publish only after
`docs/VERIFY_CHECKLIST.md` is complete.

The DOI is already written into `CITATION.cff`, `docs/release_ids.json`, the README badge and the
manuscript's code-availability statement.

## 1. Build the final package (after verification)

```bash
git switch release/v0.1.0
./scripts/make_zenodo_release.sh 2026-MM-DD      # the date you will press Publish
```

The script removes the DRAFT stamps, rebuilds the figures, manuscript and README, runs the
publish gate, and writes `../aipir-v0.1.0.zip`. It stops if anything is still marked DRAFT,
`[VERIFY]` or left as a placeholder.

## 2. Files to upload

| File | Why |
|---|---|
| `aipir-v0.1.0.zip` | The full replication package: code, framework, deployment templates, derived data, models, figures, documentation. Raw HAI files are excluded; `code/01_fetch.py` downloads them at the pinned commit. |
| `AIPIR_manuscript.pdf` | Export `paper/AIPIR_manuscript.docx` to PDF in Word (File > Save as > PDF). It lets readers see the paper without unzipping. |

## 3. Fields on the Zenodo form (copy exactly)

| Field | Value |
|---|---|
| Digital Object Identifier | Already reserved: 10.5281/zenodo.23846615. Do not click "Get a DOI now" again. |
| Resource type | Software |
| Title | AIPIR: AI-Enabled Predictive Infrastructure Resilience Framework |
| Publication date | The date you publish (the same date given to the script) |
| Creators (in this order) | 1. Ikwuogu, Friday Ogochukwu (Independent Researcher, Odessa, Texas, USA; ORCID 0009-0009-2222-1318; role: contact person)<br>2. Orimogunje, Abidemi (Electrical and Electronic Engineering Department, Redeemer's University, Ede, Osun State, Nigeria)<br>3. Pinyi, Eria Othieno (Computer Science and Engineering Department, University of Fairfax, USA)<br>4. Mike-Ewewie, David (Computer Science Department, University of Texas Permian Basin, Odessa, Texas, USA) |
| Description | Paste the description from `docs/zenodo_metadata.json`. Then add: "Version 0.1.0. Results come from the public HAI testbed datasets; no operator data is used. See docs/LIMITATIONS.md." |
| Licenses | MIT License (code). Add **Creative Commons Attribution Share Alike 4.0 International** as a second license, covering the derived data and models (required by HAI's share-alike term). |
| Keywords | industrial control systems; anomaly detection; critical infrastructure resilience; energy sector; predictive analytics; observability; infrastructure as code; HAI dataset |
| Version | 0.1.0 |
| Language | English |
| Related works | "References", DOI **10.1145/3474718.3474719** (HAI dataset paper). After GitHub or arXiv exist, also add "Is supplemented by" with the repository URL or arXiv ID. |
| Software: repository URL | Leave blank unless the GitHub repository is public already |
| Software: programming language | Python |
| Funding | Leave blank (no funding) |
| Access | Public; files public |

Before you press **Publish**, click **Preview** and check that the authors, licenses and version
are correct. A typo in the metadata can be edited later; the files cannot.

## 4. After publishing (the same day)

1. Open the published record. In the sidebar under *Versions*, copy the **concept DOI** ("Cite
   all versions"). v0.2.0 will cite it.
2. Add a row to `docs/evidence_log.csv` (template row already there; change `reserved` to
   `published` and fill in the date).
3. Save the record page as a PDF.

## 5. v0.2.0 later: "New version" on the same record

1. On the published v0.1.0 record, click **New version**. Zenodo creates a new draft. Reserve its
   DOI on the draft (**Get a DOI now**); it will differ from 10.5281/zenodo.23846615.
2. Send me that new DOI and the concept DOI. I'll write them into the v0.2.0 files and build that
   package the same way.
3. Upload `aipir-v0.2.0.zip` and its manuscript PDF, set Version 0.2.0, check the form, then
   Preview and Publish.
