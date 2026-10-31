# AIPIR publish guide (complete only after docs/VERIFY_CHECKLIST.md is fully ticked)

No push or submission was automated in this session: no GitHub or Zenodo token was supplied,
and arXiv requires your personal attestation. Everything below is ready for you to do in one
sitting (about 60-90 minutes the first time).

## 0. Finalize (10 min)

```bash
cd aipir
python code/05_figures.py --final
node code/06_document.js --final
python code/08_readme.py --final
python scripts/publish_gate.py . --allow-draft-in code/ framework/ scripts/ tests/ docs/PUBLISH_GUIDE.md docs/BUILD_SPEC.md   # must pass
```

Code folders are allowed because source code legitimately contains words like DRAFT and
square brackets. The gate blocks on the bracketed placeholders in `CITATION.cff`,
`docs/zenodo_metadata.json` and `docs/release_ids.json` (the `--final` manuscript build refuses
to run until release_ids.json is filled). Fill them in the
order below (GitHub URL first, then DOI), rerun `node code/06_document.js --final`, and rerun
the gate before step 3.

## 1. GitHub (10 min)

1. Create an empty public repository at https://github.com/new named **aipir** (no README,
   no license; the project has both).
2. In the project folder (a git repository with the initial commit is already prepared):
   ```bash
   git remote add origin https://github.com/<your-username>/aipir.git
   git push -u origin main
   ```
   Raw HAI files are excluded by `.gitignore` (they are fetched by `code/01_fetch.py`); no file
   in the repository exceeds 100 MB.
3. Replace `[repository URL - set on publish]` in `CITATION.cff` and
   `docs/zenodo_metadata.json` and `docs/release_ids.json`; commit and push.
4. Check that the **ci** workflow passes in the Actions tab (unit tests, YAML, terraform validate).

Alternative with a token: `export GITHUB_TOKEN=...` (classic token, `repo` scope) then
`python scripts/publish_github.py --repo aipir --description "AI-Enabled Predictive Infrastructure Resilience framework for energy-sector control systems" --release v0.1.0`. Revoke the token afterwards.

## 2. Zenodo DOI (10 min)

1. Log in at https://zenodo.org with ORCID 0009-0009-2222-1318 (attaches your ORCID).
2. Account > GitHub > switch on **aipir**.
3. On GitHub: Releases > Draft a new release > tag `v0.1.0`, title
   "AIPIR v0.1.0 - first public release", notes:
   > First release of the AIPIR framework (Observe-Predict-Respond-Recover) and the replication
   > package for its validation on HAI 21.03 and HAI 20.07. Code MIT; derived data and models
   > CC BY-SA 4.0. See README and docs/LIMITATIONS.md.
4. Zenodo mints a DOI within minutes. On the Zenodo record, edit: add the three co-authors with
   affiliations exactly as in `AUTHORS.json`, license MIT, keywords from
   `docs/zenodo_metadata.json`.
5. Put the DOI and release date in `CITATION.cff` and `docs/release_ids.json`, rebuild with
   `node code/06_document.js --final`, add the DOI badge to the README; commit, push.

Alternative with a token: `export ZENODO_SANDBOX_TOKEN=...` then
`python scripts/zenodo_deposit.py --files aipir-v0.1.0.zip --metadata docs/zenodo_metadata.json --sandbox`,
inspect the sandbox record, then repeat with `ZENODO_TOKEN` and `--publish`.

## 3. arXiv preprint (20 min + moderation)

- **Category:** primary `cs.CR` (Cryptography and Security); cross-list `eess.SY`
  (Systems and Control).
- **Files:** export `paper/AIPIR_manuscript.docx` to PDF (Word: File > Save as PDF) after the
  final build; arXiv accepts PDF for documents not produced from TeX.
- **Metadata:** title as in the manuscript; authors in this order:
  Friday Ogochukwu Ikwuogu; Silas Abutu; Ayodeji Olutosin Ejiade; Fejiro Eni.
  Abstract: paste from the manuscript (arXiv limit 1,920 characters; trim if needed).
- **Comments field:** "N pages, 6 figures, 3 tables. Code and data: <GitHub URL>; DOI <Zenodo DOI>".
- **License:** CC BY 4.0.
- **Endorsement:** first-time submitters to cs.CR may need an endorser. Request text:
  > Dear Dr. ___, I am preparing my first arXiv submission in cs.CR, "AIPIR: An AI-Enabled
  > Predictive Infrastructure Resilience Framework for Energy-Sector Control Systems". It
  > evaluates an open anomaly-detection and recovery framework on the public HAI ICS datasets;
  > code and data are at <GitHub URL>. arXiv asks that I be endorsed by an established author in
  > the category; my endorsement code is ______. I would be grateful for your help. Friday Ikwuogu
- **Before you click submit:** every co-author has approved the final PDF; the AI-assistance
  statement is accurate; nothing from your employer appears anywhere.
- Moderation takes 1-3 business days. Record the arXiv ID in `docs/evidence_log.csv`.

## 4. Journal (after the preprint)

Candidates to check (confirm scope, review time and fees on each site before choosing):
*International Journal of Critical Infrastructure Protection* (Elsevier; subscription route has
no publication fee), *IEEE Access* (open access, article processing charge), *Energies*
(MDPI, open access, charge). Submit the final manuscript, the arXiv ID, the Zenodo DOI and the
cover letter below; record the manuscript ID in the evidence log.

> Cover letter: We submit "AIPIR ..." for consideration. The paper presents an open framework that
> connects predictive detection, alert routing and Infrastructure-as-Code recovery for energy-sector
> control systems, validated on two public HAI testbed releases under a fixed false-alarm budget
> and a frozen design, and it reports where the approach does not outperform simpler baselines.
> All code, data derivatives and infrastructure definitions are openly available (DOI ...). The
> work has been posted as a preprint (arXiv ...) and is not under review elsewhere.

## 5. Same day as each step

Add a row to `docs/evidence_log.csv`
(`date,artifact_or_event,type,venue_or_host,link_or_doi,status,...`) and save a PDF of the
release page, Zenodo record and arXiv abstract page.
