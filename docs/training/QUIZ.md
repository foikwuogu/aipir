# AIPIR knowledge check (15 questions, pass mark 12)

Name: ____________________  Date: __________  Cohort: __________

1. Which AIPIR layer turns an alert into a restored, verified state?
   a) Observe  b) Predict  c) Respond  d) Recover
2. On which data is the AIPIR alarm threshold calibrated?
   a) the attack labels of the test files  b) held-out normal operating data  c) the whole dataset  d) operator opinion
3. What does the AIPIR predictive detector forecast?
   a) the next attack type  b) each sensor's value one second ahead  c) the daily load  d) the threshold
4. On HAI 21.03, compared with static limits, the AIPIR detector...
   a) detected every attack  b) detected attacks earlier but detected fewer of them  c) produced 10x more false alarms  d) had no routing ability
5. Why can AIPIR detection with *manual* recovery fail to reduce downtime in the scenario model?
   a) detection takes hours  b) missed attacks and hours-long recovery dominate seconds saved  c) the model is slow  d) OpenTelemetry adds delay
6. Which token claim does the service check for MFA?
   a) `roles`  b) `amr` containing "mfa"  c) `aud`  d) `idtyp`
7. Bob requested a recovery. Who may approve it?
   a) Bob, if he has the approver role  b) any administrator  c) a different person with the approver role and MFA  d) Alertmanager
8. What happens when a human token carries the role `aipir.alert-relay`?
   a) it can request recoveries  b) it gets nothing from that role  c) it becomes admin  d) it can approve
9. What does the audit log's hash chain detect?
   a) slow requests  b) deleted or edited entries  c) wrong passwords  d) network scans
10. Which component removes `authorization` attributes before telemetry leaves the collector?
    a) `batch` processor  b) `attributes/scrub` processor  c) Prometheus exporter  d) `memory_limiter`
11. By default, an approved recovery runs Ansible in...
    a) check mode  b) production mode  c) parallel on all hosts  d) no mode; it is skipped
12. The `ot_restore` role refuses to restore when...
    a) the score is low  b) the baseline file's SHA-256 does not match its recorded hash  c) it is night time  d) OTel is down
13. A drift finding with no matching change-ledger entry counts as...
    a) noise  b) an approved change  c) a misconfiguration (unapproved drift)  d) a false alarm
14. MTTR in the replication playbook is measured from...
    a) incident start to detection  b) detection to verified recovery  c) alert to ticket closure  d) start of shift to end of shift
15. Which statement is consistent with the project's data integrity rules?
    a) Testbed results can be reported as pilot results.  b) Synthetic practice records can stand in for missing pilot data.  c) Pilot targets stay open until a real pilot measures them.  d) Incidents can be dropped after the fact if they hurt the averages.
