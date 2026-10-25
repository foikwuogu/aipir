#!/usr/bin/env python3
"""Integration check of the lab stack: service + Zero-Trust + Ansible hook + OpenTelemetry Collector.

Starts a real OpenTelemetry Collector (otelcol-contrib on PATH or $OTELCOL) and the AIPIR service
replaying HAI 21.03 test4, then exercises every access rule and the recovery workflow end to end.
Ansible (`ansible-playbook` on PATH) runs the recovery playbook in check mode.

    python tests/integration/lab_stack_check.py            # writes data/processed/lab_stack_check.json
Exit code 0 when every check passes.
"""
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "framework"))
from aipir.zerotrust import mint_lab_token, verify_audit  # noqa: E402

PORT, OTLP, PROM = 19108, 14318, 18889
ISS, AUD = "aipir-lab", "api://aipir"
results = []


def check(name, cond, detail=""):
    results.append({"check": name, "pass": bool(cond), "detail": detail})
    print(("PASS " if cond else "FAIL ") + name + (f"  ({detail})" if detail else ""), flush=True)


def call(method, path, token=None, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def wait(url, secs=60):
    for _ in range(secs * 2):
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def main():
    work = tempfile.mkdtemp(prefix="aipir-lab-")
    secret = secrets.token_urlsafe(32).encode()
    tok = lambda sub, roles, mfa=False, app=False, ttl=900: mint_lab_token(secret, ISS, AUD, sub, roles, mfa, app, ttl)  # noqa: E731
    otelcol = os.environ.get("OTELCOL") or shutil.which("otelcol-contrib")
    procs = []
    evidence = os.path.join(work, "otel-evidence.jsonl")
    if otelcol:
        cfg = open(os.path.join(ROOT, "deploy/observability/otel/otel-collector.yaml")).read()
        cfg = (cfg.replace("0.0.0.0:4318", f"127.0.0.1:{OTLP}").replace("0.0.0.0:4317", "127.0.0.1:14317")
               .replace("0.0.0.0:8889", f"127.0.0.1:{PROM}").replace("0.0.0.0:13133", "127.0.0.1:13134")
               .replace("/tmp/aipir-otel-evidence.jsonl", evidence))
        cpath = os.path.join(work, "otel.yaml")
        open(cpath, "w").write(cfg)
        procs.append(subprocess.Popen([otelcol, f"--config={cpath}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        check("otel collector started", wait("http://127.0.0.1:13134/"))
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([os.path.join(ROOT, "framework")] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])), AIPIR_LAB_SECRET=secret.decode(),
               AIPIR_AUTH_MODE="hs256", AIPIR_ISSUER=ISS, AIPIR_AUDIENCE=AUD, AIPIR_RECOVERY="execute",
               AIPIR_ANSIBLE_CHECK="1", AIPIR_AUDIT_LOG=os.path.join(work, "audit.jsonl"),
               ANSIBLE_CONFIG=os.path.join(ROOT, "deploy/ansible/ansible.cfg"))
    if otelcol:
        env["OTEL_EXPORTER_OTLP_ENDPOINT"] = f"http://127.0.0.1:{OTLP}"
    svc = subprocess.Popen([sys.executable, "-m", "aipir.service", "--model", os.path.join(ROOT, "models/aipir_hai2103.joblib"),
                            "--replay", os.path.join(ROOT, "data/raw/hai-21.03/test4.csv.gz"), "--speed", "0",
                            "--port", str(PORT), "--host", "127.0.0.1"], env=env, stdout=open(os.path.join(work, "svc.log"), "w"),
                           stderr=subprocess.STDOUT)
    procs.append(svc)
    try:
        check("service started", wait(f"http://127.0.0.1:{PORT}/healthz"))
        viewer = tok("vera", ["aipir.viewer"])
        scraper = tok("prometheus", ["aipir.metrics-scraper"], app=True)
        relay = tok("alertmanager", ["aipir.alert-relay"], app=True)
        op_nomfa = tok("bob", ["aipir.operator"])
        op = tok("bob", ["aipir.operator"], mfa=True)
        appr_nomfa = tok("carol", ["aipir.recovery-approver"])
        appr = tok("carol", ["aipir.recovery-approver"], mfa=True)
        bob_appr = tok("bob", ["aipir.recovery-approver"], mfa=True)

        # --- identity
        check("health is public", call("GET", "/healthz")[0] == 200)
        check("metrics without token -> 401", call("GET", "/metrics")[0] == 401)
        check("metrics with scraper workload token -> 200", call("GET", "/metrics", scraper)[0] == 200)
        bad = op[:-4] + ("AAAA" if not op.endswith("AAAA") else "BBBB")
        check("tampered signature -> 401", call("GET", "/status", bad)[0] == 401)
        expired = tok("vera", ["aipir.viewer"], ttl=-3600)
        check("expired token -> 401", call("GET", "/status", expired)[0] == 401)
        other = mint_lab_token(b"wrong-secret-wrong-secret", ISS, AUD, "mallory", ["aipir.admin"], True)
        check("token from another issuer key -> 401", call("GET", "/status", other)[0] == 401)
        # --- RBAC + MFA
        check("viewer can read status", call("GET", "/status", viewer)[0] == 200)
        check("viewer cannot request recovery -> 403", call("POST", "/recover", viewer, {"process": "P1"})[0] == 403)
        check("operator without MFA cannot request -> 403", call("POST", "/recover", op_nomfa, {"process": "P1"})[0] == 403)
        check("workload role is ignored for humans -> 403",
              call("POST", "/recover", tok("eve", ["aipir.alert-relay"], mfa=True), {"process": "P1"})[0] == 403)
        s, b = call("POST", "/recover", relay, {"alerts": [{"labels": {"alertname": "AIPIRProcessAnomaly", "process": "P1"}}]})
        rec = json.loads(b)["accepted"][0] if s == 200 else {}
        check("Alertmanager relay can request recovery", s == 200 and rec.get("status") == "pending_approval", rec.get("status", s))
        check("relay cannot approve -> 403", call("POST", f"/recoveries/{rec.get('id')}/approve", relay)[0] == 403)
        check("operator cannot approve -> 403", call("POST", f"/recoveries/{rec.get('id')}/approve", op)[0] == 403)
        check("approver without MFA -> 403", call("POST", f"/recoveries/{rec.get('id')}/approve", appr_nomfa)[0] == 403)
        s2, b2 = call("POST", "/recover", op, {"process": "P2"})
        rec2 = json.loads(b2)["accepted"][0] if s2 == 200 else {}
        check("operator with MFA can request", s2 == 200)
        check("two-person rule: requester cannot approve own -> 403",
              call("POST", f"/recoveries/{rec2.get('id')}/approve", bob_appr)[0] == 403)
        t0 = time.time()
        s3, b3 = call("POST", f"/recoveries/{rec.get('id')}/approve", appr)
        r3 = json.loads(b3) if s3 == 200 else {}
        ansible_ok = shutil.which("ansible-playbook") is not None
        check("approver with MFA runs Ansible playbook (check mode)",
              s3 == 200 and (r3.get("status") == "succeeded" if ansible_ok else True),
              f"status={r3.get('status')}, rc={(r3.get('result') or {}).get('rc')}, check_mode={(r3.get('result') or {}).get('check_mode')}, {time.time() - t0:.1f}s"
              + ("" if r3.get("status") == "succeeded" else " " + str((r3.get("result") or {}).get("stderr_tail", ""))[-300:]))
        check("approved twice -> 409", call("POST", f"/recoveries/{rec.get('id')}/approve", appr)[0] == 409)
        # --- detection while all this happened
        deadline = time.time() + 180
        while time.time() < deadline:
            m = call("GET", "/metrics", scraper)[1]
            n = [ln for ln in m.splitlines() if ln.startswith("aipir_rows_processed_total")]
            if n and int(float(n[0].split()[-1])) >= 39601:
                break
            time.sleep(2)
        check("full replay scored", n and int(float(n[0].split()[-1])) >= 39601, n[0] if n else "")
        # --- audit chain
        ok, nent, msg = verify_audit(env["AIPIR_AUDIT_LOG"])
        check("audit hash chain intact", ok, f"{nent} entries")
        lines = open(env["AIPIR_AUDIT_LOG"]).read().splitlines()
        denies = sum(json.loads(x).get("decision") == "deny" for x in lines)
        check("denials recorded in audit", denies >= 9, f"{denies} denials")
        tampered = os.path.join(work, "audit_tampered.jsonl")
        open(tampered, "w").write("\n".join(lines[:3] + lines[4:]) + "\n")
        check("deleting an audit entry is detected", not verify_audit(tampered)[0])
        # --- OpenTelemetry
        if otelcol:
            time.sleep(13)
            try:
                pm = urllib.request.urlopen(f"http://127.0.0.1:{PROM}/metrics", timeout=5).read().decode()
            except Exception:  # noqa: BLE001
                pm = ""
            check("OTel metrics reach collector (aipir.anomaly.score)", "otel_aipir_anomaly_score" in pm)
            check("OTel alarm gauge per process", 'otel_aipir_alarm_active{' in pm and 'process="P1"' in pm)
            ev = open(evidence).read() if os.path.exists(evidence) else ""
            check("OTel alarm spans exported", '"aipir.alarm"' in ev, f"{ev.count(chr(34) + 'aipir.alarm' + chr(34))} occurrences")
            check("OTel recovery span exported", '"aipir.recovery"' in ev)
            check("OTel audit logs exported", "audit deny" in ev and "audit allow" in ev)
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    out = {"checks": results, "passed": sum(r["pass"] for r in results), "total": len(results),
           "otel_collector": bool(otelcol), "ansible": shutil.which("ansible-playbook") is not None,
           "date": time.strftime("%Y-%m-%d")}
    os.makedirs(os.path.join(ROOT, "data/processed"), exist_ok=True)
    json.dump(out, open(os.path.join(ROOT, "data/processed/lab_stack_check.json"), "w"), indent=2)
    print(f"{out['passed']}/{out['total']} checks passed")
    shutil.rmtree(work, ignore_errors=True)
    return 0 if out["passed"] == out["total"] else 1


if __name__ == "__main__":
    sys.exit(main())
