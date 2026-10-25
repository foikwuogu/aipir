# Lab 5 - Recover: Ansible playbooks with approval and evidence (45 min)

**Objective:** run a guarded recovery and inspect its evidence. **Layer:** Recover.

## Steps

1. Syntax-check all playbooks: `for p in deploy/ansible/playbooks/*.yml; do ansible-playbook --syntax-check $p; done`.
2. Approve the pending recovery from Lab 3 with `$APPROVER`. The service runs
   `recover_boiler.yml` in **check mode**. Read the JSON result: `rc`, `check_mode`, `stdout_tail`.
3. Run the playbook yourself in the lab (every site command is an `echo`):
   ```bash
   echo '{"aipir_request_id":"lab5","aipir_process":"P1","aipir_requested_by":"bob","aipir_approved_by":"carol"}' > /tmp/v.json
   ansible-playbook deploy/ansible/playbooks/recover_boiler.yml -e @/tmp/v.json
   cat /tmp/aipir-recovery-evidence/lab5/*.json
   ```
4. Break the two-person rule (`"aipir_approved_by":"bob"`) and run again: the guard refuses.
5. Tamper with the baseline (`echo x >> deploy/ansible/baselines/lab_P1.yml`), run again: the
   integrity check refuses. Restore it with `git checkout deploy/ansible/baselines/lab_P1.yml`.

## Discussion

- Why does Ansible call the site's own restore command instead of writing setpoints itself?
- What must a site do before it sets `AIPIR_ANSIBLE_CHECK=0`?

## Check

You can name the four guards between an alert and a change on equipment: approval, MFA,
two-person rule, baseline integrity (plus check mode by default).
