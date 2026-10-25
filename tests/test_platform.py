"""Unit tests: Zero-Trust (tokens, RBAC, MFA, two-person, audit), drift check, OTel payloads,
recovery workflow. Synthetic inputs only.   python -m pytest -q tests
"""
import base64
import json
import os
import sys
import tempfile
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "framework"))

from aipir import drift  # noqa: E402
from aipir.otel import OTLPExporter  # noqa: E402
from aipir.recovery import AnsibleHook, RecoveryManager  # noqa: E402
from aipir.zerotrust import (AuditLog, Authorizer, AuthError, Policy, TokenVerifier,  # noqa: E402
                             mint_lab_token, verify_audit)

SECRET = b"unit-test-secret-unit-test-secret"
ISS, AUD = "aipir-lab", "api://aipir"


def authz(tmp):
    return Authorizer(TokenVerifier("hs256", ISS, AUD, secret=SECRET), Policy.load(),
                      AuditLog(os.path.join(tmp, "a.jsonl")))


def bearer(sub, roles, mfa=False, app=False, ttl=600):
    return "Bearer " + mint_lab_token(SECRET, ISS, AUD, sub, roles, mfa, app, ttl)


def test_policy_roles_loaded():
    p = Policy.load()
    assert "recovery:approve" in p.roles["aipir.recovery-approver"]
    assert "aipir.alert-relay" in p.workload_roles
    assert "recovery:approve" in p.two_person


def test_rbac_and_mfa(tmp_path):
    a = authz(str(tmp_path))
    assert a.authorize(bearer("v", ["aipir.viewer"]), "status:read").sub == "v"
    with pytest.raises(AuthError) as e:
        a.authorize(bearer("v", ["aipir.viewer"]), "recovery:request")
    assert e.value.status == 403
    with pytest.raises(AuthError, match="multi-factor"):
        a.authorize(bearer("o", ["aipir.operator"]), "recovery:request")
    assert a.authorize(bearer("o", ["aipir.operator"], mfa=True), "recovery:request").mfa


def test_unknown_role_grants_nothing(tmp_path):
    with pytest.raises(AuthError):
        authz(str(tmp_path)).authorize(bearer("x", ["aipir.superuser"], mfa=True), "status:read")


def test_workload_rules(tmp_path):
    a = authz(str(tmp_path))
    assert a.authorize(bearer("am", ["aipir.alert-relay"], app=True), "recovery:request").workload
    with pytest.raises(AuthError):  # human holding a workload role gets nothing from it
        a.authorize(bearer("eve", ["aipir.alert-relay"], mfa=True), "recovery:request")
    with pytest.raises(AuthError):  # workload holding a human role gets nothing from it
        a.authorize(bearer("bot", ["aipir.recovery-approver"], app=True), "recovery:approve")


def test_two_person_rule(tmp_path):
    a = authz(str(tmp_path))
    p = a.authorize(bearer("bob", ["aipir.recovery-approver"], mfa=True), "recovery:approve")
    with pytest.raises(AuthError, match="two-person"):
        a.check_two_person("recovery:approve", "bob", p, "r1")
    a.check_two_person("recovery:approve", "alice", p, "r1")


def test_token_rejections(tmp_path):
    a = authz(str(tmp_path))
    for hdr in [None, "Basic abc", bearer("v", ["aipir.viewer"], ttl=-3600),
                "Bearer " + mint_lab_token(b"other-secret-other-secret", ISS, AUD, "v", ["aipir.viewer"]),
                "Bearer " + mint_lab_token(SECRET, "evil", AUD, "v", ["aipir.viewer"]),
                "Bearer " + mint_lab_token(SECRET, ISS, "api://other", "v", ["aipir.viewer"])]:
        with pytest.raises(AuthError) as e:
            a.authorize(hdr, "status:read")
        assert e.value.status == 401


def test_rs256_with_jwks():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    b64 = lambda i: base64.urlsafe_b64encode(i.to_bytes((i.bit_length() + 7) // 8, "big")).rstrip(b"=").decode()  # noqa: E731
    jwks = {"keys": [{"kty": "RSA", "kid": "k1", "n": b64(pub.n), "e": b64(pub.e)}]}
    enc = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()  # noqa: E731
    now = int(time.time())
    h, p = enc({"alg": "RS256", "kid": "k1"}), enc({"iss": ISS, "aud": AUD, "sub": "u", "exp": now + 60,
                                                     "roles": ["aipir.viewer"], "amr": ["pwd", "mfa"]})
    sig = key.sign(f"{h}.{p}".encode(), padding.PKCS1v15(), hashes.SHA256())
    tok = f"{h}.{p}." + base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
    v = TokenVerifier("rs256", ISS, AUD, jwks=jwks)
    assert v.verify(tok)["sub"] == "u"
    with pytest.raises(AuthError):
        v.verify(tok[:-6] + "AAAAAA")
    with pytest.raises(AuthError):  # algorithm confusion: HS256 token offered to an RS256 verifier
        v.verify(mint_lab_token(SECRET, ISS, AUD, "u", ["aipir.viewer"]))


def test_lab_tokens_blocked_in_production(monkeypatch):
    monkeypatch.setenv("AIPIR_ENV", "production")
    with pytest.raises(RuntimeError):
        mint_lab_token(SECRET, ISS, AUD, "u", ["aipir.viewer"])


def test_audit_chain(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    log = AuditLog(path)
    for i in range(5):
        log.write({"decision": "allow", "i": i})
    assert verify_audit(path)[0]
    lines = open(path).read().splitlines()
    lines[2] = lines[2].replace('"i": 2', '"i": 9')
    open(path, "w").write("\n".join(lines) + "\n")
    assert not verify_audit(path)[0]


def test_drift_files_signature_and_ledger(tmp_path):
    d = tmp_path / "cfg"
    d.mkdir()
    (d / "a.yml").write_text("x: 1\n")
    (d / "b.yml").write_text("y: 2\n")
    key = str(tmp_path / "k.pem")
    drift.main(["keygen", "--out", key])
    bl = drift.sign_baseline(drift.make_baseline([str(d)]), key)
    assert drift.verify_baseline(bl, key + ".pub")
    (d / "a.yml").write_text("x: 2\n")
    (d / "c.yml").write_text("z: 3\n")
    os.remove(d / "b.yml")
    f = {x["item"].split(os.sep)[-1]: x["change"] for x in drift.check_files(bl)}
    assert f == {"a.yml": "modified", "b.yml": "removed", "c.yml": "added"}
    bl["files"]["evil"] = "0"
    assert not drift.verify_baseline(bl, key + ".pub")
    del bl["files"]["evil"]
    ledger = str(tmp_path / "changes.jsonl")
    drift.record_change(ledger, str(d / "a.yml"), "alice", "CHG-1")
    rep = drift.build_report(drift.check_files(bl), drift.read_ledger(ledger), [])
    approved = {x["item"].split(os.sep)[-1]: x["approved"] for x in rep["findings"]}
    assert approved == {"a.yml": True, "b.yml": False, "c.yml": False} and rep["unapproved"] == 2


def test_drift_kpi_counts(tmp_path):
    ledger = str(tmp_path / "l.jsonl")
    for i in range(4):
        drift.record_change(ledger, f"item{i}", "a", f"CHG-{i}")
    findings = [{"source": "files", "item": "item1", "change": "modified"},
                {"source": "files", "item": "rogue", "change": "modified"}]
    rep = drift.build_report(findings, drift.read_ledger(ledger), [])
    assert rep["unapproved"] == 1 and rep["misconfigurations_per_100_changes"] == 25.0


def test_drift_kubernetes_compare(tmp_path):
    (tmp_path / "d.yaml").write_text(
        "apiVersion: apps/v1\nkind: Deployment\nmetadata: {name: web, namespace: ns}\n"
        "spec: {replicas: 2, template: {spec: {containers: [{name: c, image: img:1}]}}}\n")
    live_ok = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "web", "namespace": "ns", "uid": "u"},
               "spec": {"replicas": 2, "strategy": {}, "template": {"spec": {"containers": [{"name": "c", "image": "img:1",
                                                                                             "imagePullPolicy": "IfNotPresent"}]}}}}
    assert drift.check_kubernetes(str(tmp_path), [live_ok]) == []
    live_bad = json.loads(json.dumps(live_ok))
    live_bad["spec"]["template"]["spec"]["containers"][0]["image"] = "img:evil"
    f = drift.check_kubernetes(str(tmp_path), [live_bad])
    assert f[0]["change"] == "modified" and "image" in f[0]["fields"][0]
    assert drift.check_kubernetes(str(tmp_path), [])[0]["change"] == "missing"


def test_otel_payload_shapes():
    ex = OTLPExporter(enabled=False)
    ex.gauge("aipir.anomaly.score", 1.5)
    ex.gauge("aipir.alarm.active", 1, process="P1")
    ex.add("aipir.telemetry.rows", 10)
    ex.span("aipir.alarm", time.time() - 5, time.time(), {"aipir.process": "P1", "aipir.top_sensors": ["a", "b"]})
    ex.log("audit allow", "INFO", subject="bob")
    p = ex.payloads()
    names = [m["name"] for m in p["metrics"]["resourceMetrics"][0]["scopeMetrics"][0]["metrics"]]
    assert {"aipir.anomaly.score", "aipir.alarm.active", "aipir.telemetry.rows"} <= set(names)
    span = p["traces"]["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert len(span["traceId"]) == 32 and len(span["spanId"]) == 16
    res = {a["key"]: a["value"] for a in p["metrics"]["resourceMetrics"][0]["resource"]["attributes"]}
    assert res["service.name"]["stringValue"] == "aipir-detector"
    assert p["logs"]["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["severityNumber"] == 9


def test_recovery_workflow(tmp_path, monkeypatch):
    monkeypatch.setenv("AIPIR_RECOVERY", "execute")
    hook = AnsibleHook(binary="definitely-not-installed-ansible")
    events = []
    rm = RecoveryManager(hook=hook, on_event=lambda k, r: events.append(k))
    r = rm.request("P1", "alertmanager", {"top_sensors": ["P1_B3004"]})
    assert r.status == "pending_approval"
    r = rm.approve(r.id, "carol")
    assert r.status == "failed" and "not found" in r.result["error"]
    with pytest.raises(ValueError):
        rm.approve(r.id, "carol")
    assert events == ["recovery.requested", "recovery.approved", "recovery.finished"]


def test_dry_run_never_runs(monkeypatch):
    monkeypatch.setenv("AIPIR_RECOVERY", "dry-run")
    rm = RecoveryManager(hook=AnsibleHook(binary="x"))
    r = rm.request("P2", "bob")
    assert r.status == "planned"
    with pytest.raises(ValueError):
        rm.approve(r.id, "carol")


def test_kpi_calculator_on_synthetic_records():
    """SYNTHETIC records generated here only to test the arithmetic - not pilot data."""
    import numpy as np
    import pandas as pd
    from aipir.kpi import compute
    rng = np.random.default_rng(0)
    rows = []
    for ph, ttd, ttr in [("baseline", 12, 45), ("pilot", 6, 20)]:
        for i in range(12):
            s = pd.Timestamp("2026-01-01") + pd.Timedelta(days=i * 2 + (0 if ph == "baseline" else 40))
            d = s + pd.Timedelta(minutes=float(rng.normal(ttd, 1)))
            r = d + pd.Timedelta(minutes=float(rng.normal(ttr, 3)))
            rows.append({"incident_id": f"{ph}{i}", "phase": ph, "subsystem": f"S{i % 3}", "start": s, "detected": d, "recovered": r})
    periods = pd.DataFrame([{"phase": "baseline", "start": "2026-01-01", "end": "2026-01-31"},
                            {"phase": "pilot", "start": "2026-02-10", "end": "2026-03-12"}])
    changes = pd.DataFrame([{"phase": "pilot", "change_id": i, "misconfiguration": int(i < 2)} for i in range(100)])
    r = compute(pd.DataFrame(rows), periods, changes=changes)
    assert 45 < r["comparison"]["mttd_reduction_pct"] < 55
    assert r["comparison"]["meets"]["mttr"] and r["comparison"]["meets"]["misconfig"]
    assert r["statistics"]["ttr_min"]["welch_p"] < 0.001
    assert r["statistics"]["regression_ttr_on_pilot"]["pilot_effect_min"] < -15


def test_kpi_rejects_out_of_order_timestamps():
    import pandas as pd
    from aipir.kpi import compute
    bad = pd.DataFrame([{"incident_id": "x", "phase": "baseline", "subsystem": "S", "start": "2026-01-01 10:00",
                         "detected": "2026-01-01 09:00", "recovered": "2026-01-01 11:00"}])
    with pytest.raises(ValueError):
        compute(bad, pd.DataFrame([{"phase": "baseline", "start": "2026-01-01", "end": "2026-01-02"}]))
