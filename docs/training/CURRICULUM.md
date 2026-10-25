# AIPIR workshop curriculum (1 day, 7 contact hours)

**Audience:** OT/ICS engineers, reliability and SRE engineers, security analysts, operations managers.
**Prerequisites:** a laptop with Python 3.12+ and git, and comfort with a terminal. Optional:
Docker, Terraform or OpenTofu, ansible-core, otelcol-contrib.
**Setup (before the day):** `git clone <repo>`, `pip install -r requirements.txt ansible-core`,
`python code/01_fetch.py` (about 300 MB of open HAI data).

## Learning outcomes

By the end, a participant can:
1. Explain the four AIPIR layers (Observe, Predict, Respond, Recover) and where downtime is won
   or lost.
2. Interpret predictive-detection results (event recall, time to detect, false alarms per day,
   routing) and state their limits.
3. Apply Zero-Trust controls to an OT monitoring service: identity, RBAC, MFA, two-person rule,
   tamper-evident audit.
4. Trace an alarm and a recovery through OpenTelemetry metrics, traces, and logs.
5. Run a guarded Ansible recovery and explain each guard.
6. Deploy from the IaC template library, detect configuration drift, and compute pilot KPIs
   (MTTD, MTTR, availability, misconfigurations per 100 changes) from incident records.

## Agenda

| Time | Module | Slides | Lab |
|---|---|---|---|
| 08:30 | Welcome, safety briefing (non-production only), objectives | 1-3 | - |
| 08:45 | M1 Why resilience: detection, response and recovery in energy OT | 4-6 | - |
| 09:15 | M2 Observe and Predict: telemetry, the forecaster, calibration | 7-9 | Lab 1 (45 min) |
| 10:30 | Break | | |
| 10:45 | M3 Reading results honestly: what AIPIR finds and misses | 10-11 | Lab 2 (45 min) |
| 12:00 | Lunch | | |
| 12:45 | M4 Zero-Trust for OT monitoring | 12-13 | Lab 3 (60 min) |
| 14:00 | M5 OpenTelemetry: following an incident | 14 | Lab 4 (40 min) |
| 14:50 | Break | | |
| 15:00 | M6 Recover: playbooks, approvals, IaC, drift | 15-16 | Lab 5 (45 min) |
| 16:00 | M7 Measuring a pilot: KPIs and statistics | 17 | Lab 6 (45 min, condensed) |
| 16:50 | Quiz (15 questions), evaluation, close | 18 | - |

## Assessment

- A knowledge check (`QUIZ.md`) with a pass mark of 12/15.
- Practical completion: the participant shows the instructor the results of the Lab 3 table and
  Lab 5 step 3.

## Delivery formats

- In person (preferred): one instructor and one assistant per 15 participants.
- Recorded session: the instructor follows the script in `INSTRUCTOR_GUIDE.md` section 4 and
  records the slides plus live Labs 1, 3 and 5 (about 90 minutes). Publish it with the deck.
