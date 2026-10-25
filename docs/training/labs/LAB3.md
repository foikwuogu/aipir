# Lab 3 - Zero-Trust: identity, roles, MFA, two-person rule, audit (60 min)

**Objective:** see every access rule enforced and logged. **Layer:** cross-cutting.
Start the service as in Lab 1, but in execute mode:
```bash
source docs/training/lab_env.sh
AIPIR_RECOVERY=execute python -m aipir.service --model models/aipir_hai2103.joblib \
    --replay data/raw/hai-21.03/test4.csv.gz --speed 50 --port 9108 --host 127.0.0.1 &
```

## Steps

| # | Try | Expect |
|---|---|---|
| 1 | `api GET /status "$VIEWER"` | 200 |
| 2 | `api POST /recover "$VIEWER" -d '{"process":"P1"}'` | 403 (role lacks permission) |
| 3 | `api POST /recover "$OPERATOR_NOMFA" -d '{"process":"P1"}'` | 403 (MFA required) |
| 4 | `api POST /recover "$OPERATOR" -d '{"process":"P1"}'` | 200, status `pending_approval` (note the id) |
| 5 | `api POST /recoveries/<id>/approve "$BOB_APPROVER"` | 403 (two-person rule: bob requested it) |
| 6 | `api POST /recoveries/<id>/approve "$RELAY"` | 403 (workloads cannot approve) |
| 7 | Edit one character in `$VIEWER` and call `/status` | 401 (bad signature) |
| 8 | `python -m aipir.zerotrust verify-audit $AIPIR_AUDIT_LOG` | "audit chain intact" |
| 9 | Copy the audit log, delete one line from the copy, verify the copy | chain broken |

Open `deploy/zero-trust/rbac_policy.yaml` and find the rule behind each result.

## Check

You can explain why an administrator cannot approve a recovery, and what the audit hash chain
protects against.
