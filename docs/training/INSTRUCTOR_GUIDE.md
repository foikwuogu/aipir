# Instructor guide

## 1. One week before

- [ ] Confirm the room has power for every seat, and Wi-Fi that allows GitHub (participants clone the repo and fetch HAI).
- [ ] Run every lab yourself on a clean machine. `./deploy/validate.sh` and `python -m pytest -q tests` must pass.
- [ ] Prepare a USB drive or file share with the repository and `data/raw/` for anyone whose download fails.
- [ ] Print `QUIZ.md` and `EVALUATION_FORM.md`, or prepare online versions.
- [ ] Confirm the certificate process with the training partner.

## 2. Safety and integrity messages (say these at the start)

1. Everything today runs on recorded, public data. Nothing connects to a plant.
2. AIPIR never writes to a controller. A real recovery goes through the site's management of
   change, two people, and MFA.
3. Lab tokens and the lab secret are for the classroom only. In a pilot, identities come from
   Entra ID with MFA.
4. The detection numbers you will see come from a testbed. The pilot targets (MTTD, MTTR,
   availability, misconfigurations) are measured at the site and are not shown today.

## 3. Facilitation notes per module

| Module | Key point | Common confusion | Fix |
|---|---|---|---|
| M1 | Downtime = time to detect + time to recover + time lost to missed incidents | "Faster detection alone fixes downtime" | Show `fig6_downtime_scenario.png`: AIPIR with manual recovery does not beat limits |
| M2 | The threshold comes from normal data only, set to about 1 false alarm per day | Thinking the model "learned the attacks" | Point to `config.py` and the 80/20 fit/calibrate split |
| M3 | The predictive detector is earlier and routes correctly, but misses some attacks that limits catch | Treating F1 as the only number | Lab 2 step 3: the missed events |
| M4 | Deny by default; roles map to permissions; MFA and two-person for actions | "Admin can do everything" | Show that admin cannot approve recoveries |
| M5 | Traces carry the timestamps MTTD/MTTR need | Mixing up metrics and traces | Lab 4 step 5 |
| M6 | Recovery is code: playbooks, Terraform, signed baselines | "Ansible writes setpoints" | It calls the site's approved command |
| M7 | Same definitions in both phases, fixed windows, report medians and n | Cherry-picking incidents | Section 5 rules in the replication playbook |

## 4. Recorded-session script (about 90 minutes)

1. **(0-5 min) Introduction.** Slides 1-3: who the course is for, the safety messages above, the
   four layers.
2. **(5-20 min) Why resilience.** Slides 4-6: the downtime equation; detection compared with
   recovery.
3. **(20-35 min) Live: Lab 1.** Start the service, show 401 without a token, read the metrics with
   the scraper token, point out the score against the threshold.
4. **(35-45 min) Results.** Slides 10-11: what AIPIR finds and misses; show fig2 and fig3.
5. **(45-65 min) Live: Lab 3.** Walk through the table, then verify and tamper the audit log.
6. **(65-80 min) Live: Lab 5.** Approve a recovery; show the check-mode result, the evidence file,
   and the two-person and baseline-integrity guards.
7. **(80-90 min) Measuring a pilot.** Slide 17; run the KPI tool on the synthetic practice
   records, stressing that they are synthetic.

Record at 1920x1080, use a 16 pt or larger terminal font, and caption the video.

## 5. After the session

- Collect quizzes and evaluations. Summarize the averages, and keep the attendance list for
  certificates.
- Log questions you could not answer as repository issues.
