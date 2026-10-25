# Verification checklist (author completes before any release)

Initial and date each line in your own copy. `publish_gate.py` checks the mechanical items;
these are yours. Nothing is published until every box is ticked.

## Reproduce
- [ ] Clean clone, `pip install -r requirements.txt`, `./run_all.sh` completes (about 40 min on 2 vCPU)
- [ ] `data/raw/PROVENANCE.txt` SHA-256 values match your fresh fetch (HAI commit 2a814ce)
- [ ] `data/processed/metrics_summary.csv` matches the committed version (diff clean)
- [ ] `data/processed/qa_report.txt` section 7 says "none"
- [ ] `python -m pytest -q tests` passes

## Source-level checks
- [ ] Open HAI 21.03 test2.csv.gz and confirm three spot-check events in `qa_report.txt`
      section 6 (start time, attack flag, attack_P* columns)
- [ ] Confirm event counts per file equal the HAI README table (QA section 2)
- [ ] Re-read the HAI license (CC BY-SA 4.0) and the citation the HAI authors request;
      confirm both appear in README, manuscript references, and LICENSE-DATA.md
- [ ] Check whether newer HAI versions (22.04, 23.05) change any conclusion you intend to state

## Results checks
- [ ] Five held-out events AIPIR detected: open `scores_hai-21.03_<file>.csv.gz` and confirm
      `alarm_D3` turns on at start + ttd_s from `events.csv`
- [ ] Five events AIPIR missed: look at `score_D3` around them and note why (fig5 helps)
- [ ] Five random events (seed 20261024 in QA section 6)
- [ ] Every number in the manuscript traces to `paper/stats.json` (06_document reads it)

## Judgment calls to own (edit config, rerun, or record agreement)
- [ ] **V1 Recovery-time assumptions** (code/03_recovery_scenario.py): manual 2-8 h (central 4 h),
      automated 5-30 min (central 15 min), missed-attack discovery 8-72 h (central 24 h).
      Replace with values you can defend from experience or a cited source.
- [ ] **V2 False-alarm budget** 1 alarm episode/day on normal data (framework/aipir/config.py)
- [ ] **V3 Alarm logic**: 5 s debounce, 30 s merge gap, 60 s grace window
- [ ] **V4 Co-authors and CRediT roles** in AUTHORS.json; each co-author has read and approved
      the manuscript and confirmed their listed role
- [ ] **V5 Licenses**: MIT code, CC BY-SA 4.0 derived data (forced by HAI), CC BY 4.0 paper
- [ ] **V6 No employer or operator data**: confirm nothing from any employer or client
      (data, configurations, incident details, screenshots) is in the repository or paper,
      and that publishing does not conflict with any employment agreement
- [ ] Framing: the paper reports AIPIR's weaknesses (event recall vs baselines; HAI 20.07)
      as plainly as its strengths, and S3 is labelled exploratory

## Before it goes public
- [ ] README, LIMITATIONS and manuscript rewritten in your own voice; nothing you cannot defend
- [ ] AI-assistance disclosure in the manuscript is accurate
- [ ] Regenerate with `--final` (`python code/05_figures.py --final`, `node code/06_document.js --final`)
- [ ] `python scripts/publish_gate.py .` passes
- [ ] Release date, repository URL and DOI placeholders filled after publishing
- [ ] Evidence log row written the day of release (`docs/evidence_log.csv`)
