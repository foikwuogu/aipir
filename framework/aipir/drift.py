"""Configuration-drift check: does what is running still match what was declared and approved?

Three sources, one report:
  files      SHA-256 baseline of configuration files (Prometheus rules, Alertmanager routes,
             playbooks, policy, exported controller configs). The baseline can be signed with
             Ed25519 so a tampered baseline is detected too.
  kubernetes Declared manifests (deploy/k8s/*.yaml) compared field-by-field with live objects
             (`kubectl get <kind> <name> -o json`, or a saved JSON dump). Only fields the manifest
             declares are compared, so server-filled defaults do not count as drift.
  terraform  `terraform plan -detailed-exitcode` (exit 2 = live infrastructure differs).

Change ledger: approved changes are recorded with `drift record-change`. A drift finding whose
item appears in an approved change since the baseline is "approved"; anything else is
"unapproved". The report gives the counts needed for the SOW KPI
"misconfigurations per 100 changes" = 100 x unapproved findings / approved changes in the period.

Report: JSON written to --out (read by the service for the aipir_config_drift_items metric).
Exit code: 0 no drift, 3 unapproved drift found, 1 error.

CLI
  python -m aipir.drift baseline --paths deploy/observability deploy/ansible --out baseline.json [--sign key.pem]
  python -m aipir.drift check --baseline baseline.json [--pubkey key.pub] [--k8s-declared deploy/k8s/base]
                              [--k8s-live live.json | --kubectl] [--terraform-dir deploy/terraform/environments/lab-k8s]
                              [--ledger changes.jsonl] --out drift_report.json
  python -m aipir.drift record-change --ledger changes.jsonl --item <path or kind/ns/name> --by <name> --ticket CHG-123
  python -m aipir.drift keygen --out key.pem
"""
from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import yaml


# ------------------------------------------------------------------ files
def _iter_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for root, dirs, files in os.walk(p):
                dirs[:] = sorted(d for d in dirs if not d.startswith("."))
                for f in sorted(files):
                    if not f.startswith("."):
                        yield os.path.join(root, f)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def make_baseline(paths, created_by="unknown"):
    files = {os.path.normpath(p): sha256_file(p) for p in _iter_files(paths)}
    return {"version": 1, "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "created_by": created_by, "roots": [os.path.normpath(p) for p in paths], "files": files}


def _canonical(b):
    return json.dumps({k: v for k, v in b.items() if k != "signature"}, sort_keys=True).encode()


def sign_baseline(b, key_pem_path):
    from cryptography.hazmat.primitives import serialization
    with open(key_pem_path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    b["signature"] = base64.b64encode(key.sign(_canonical(b))).decode()
    return b


def verify_baseline(b, pub_pem_path):
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    with open(pub_pem_path, "rb") as f:
        pub = serialization.load_pem_public_key(f.read())
    try:
        pub.verify(base64.b64decode(b.get("signature", "")), _canonical(b))
        return True
    except (InvalidSignature, ValueError):
        return False


def check_files(baseline):
    current = {os.path.normpath(p): sha256_file(p) for p in _iter_files(baseline["roots"]) if os.path.exists(p)}
    old = baseline["files"]
    findings = []
    for p in sorted(set(old) | set(current)):
        if p not in current:
            findings.append({"source": "files", "item": p, "change": "removed"})
        elif p not in old:
            findings.append({"source": "files", "item": p, "change": "added"})
        elif old[p] != current[p]:
            findings.append({"source": "files", "item": p, "change": "modified"})
    return findings


# ------------------------------------------------------------- kubernetes
def load_manifests(path):
    docs = []
    for f in sorted(glob.glob(os.path.join(path, "*.y*ml")) if os.path.isdir(path) else [path]):
        with open(f) as fh:
            docs += [d for d in yaml.safe_load_all(fh) if d and "kind" in d]
    return docs


def _key(o):
    md = o.get("metadata", {})
    return f"{o['kind']}/{md.get('namespace', '')}/{md.get('name')}"


def _diff(declared, live, path=""):
    """Paths where `live` differs from `declared`, looking only at declared fields."""
    out = []
    if isinstance(declared, dict):
        if not isinstance(live, dict):
            return [path or "/"]
        for k, v in declared.items():
            if path == "" and k == "status":
                continue
            out += _diff(v, live.get(k), f"{path}/{k}")
    elif isinstance(declared, list):
        if not isinstance(live, list) or len(live) != len(declared):
            return [path]
        for i, (d, l) in enumerate(zip(declared, live)):
            out += _diff(d, l, f"{path}[{i}]")
    else:
        if str(declared) != str(live):
            out.append(path)
    return out


IGNORED = ("/metadata/annotations", "/metadata/labels/app.kubernetes.io/managed-by")


def check_kubernetes(declared_dir, live_objects):
    live = {_key(o): o for o in live_objects}
    findings = []
    for d in load_manifests(declared_dir):
        k = _key(d)
        if k not in live:
            findings.append({"source": "kubernetes", "item": k, "change": "missing"})
            continue
        paths = [p for p in _diff(d, live[k]) if not p.startswith(IGNORED)]
        if paths:
            findings.append({"source": "kubernetes", "item": k, "change": "modified", "fields": paths[:20]})
    return findings


def kubectl_live(declared_dir):
    out = []
    for d in load_manifests(declared_dir):
        md = d["metadata"]
        cmd = ["kubectl", "get", d["kind"], md["name"], "-o", "json"]
        if md.get("namespace"):
            cmd += ["-n", md["namespace"]]
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode == 0:
            out.append(json.loads(p.stdout))
    return out


# -------------------------------------------------------------- terraform
def check_terraform(tf_dir, binary=None):
    binary = binary or os.environ.get("AIPIR_TERRAFORM", "terraform")
    if shutil.which(binary) is None:
        return [], f"{binary} not found; terraform drift not checked"
    p = subprocess.run([binary, f"-chdir={tf_dir}", "plan", "-detailed-exitcode", "-no-color", "-lock=false",
                        "-input=false"], capture_output=True, text=True)
    if p.returncode == 0:
        return [], "no changes"
    if p.returncode == 2:
        items = [ln.strip().lstrip("#").strip() for ln in p.stdout.splitlines()
                 if ln.strip().startswith("#") and (" will be " in ln or " must be " in ln)]
        return [{"source": "terraform", "item": i.split(" ")[0], "change": "plan-diff"} for i in items] or \
               [{"source": "terraform", "item": tf_dir, "change": "plan-diff"}], "drift"
    return [], f"terraform plan error: {p.stderr.strip()[-300:]}"


# ------------------------------------------------------------------ ledger
def read_ledger(path, since=None):
    if not path or not os.path.exists(path):
        return []
    with open(path) as f:
        rows = [json.loads(ln) for ln in f if ln.strip()]
    return [r for r in rows if since is None or r["ts"] >= since]


def record_change(path, item, by, ticket):
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "item": os.path.normpath(item)
           if os.path.exists(item) else item, "by": by, "ticket": ticket}
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


def build_report(findings, ledger_rows, notes):
    approved_items = {r["item"] for r in ledger_rows}
    for f in findings:
        f["approved"] = f["item"] in approved_items
    counts = {}
    for f in findings:
        counts[f["source"]] = counts.get(f["source"], 0) + 1
    unapproved = sum(not f["approved"] for f in findings)
    changes = len(ledger_rows)
    return {"generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "findings": findings,
            "counts": counts, "total": len(findings), "unapproved": unapproved,
            "approved_changes_in_period": changes,
            "misconfigurations_per_100_changes": (100.0 * unapproved / changes) if changes else None,
            "notes": notes}


def main(argv=None):
    ap = argparse.ArgumentParser(description="AIPIR configuration-drift check")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baseline")
    b.add_argument("--paths", nargs="+", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--sign")
    b.add_argument("--by", default=os.environ.get("USER", "unknown"))
    c = sub.add_parser("check")
    c.add_argument("--baseline")
    c.add_argument("--pubkey")
    c.add_argument("--k8s-declared")
    g = c.add_mutually_exclusive_group()
    g.add_argument("--k8s-live")
    g.add_argument("--kubectl", action="store_true")
    c.add_argument("--terraform-dir")
    c.add_argument("--ledger")
    c.add_argument("--out", required=True)
    r = sub.add_parser("record-change")
    r.add_argument("--ledger", required=True)
    r.add_argument("--item", required=True)
    r.add_argument("--by", required=True)
    r.add_argument("--ticket", required=True)
    k = sub.add_parser("keygen")
    k.add_argument("--out", required=True)
    a = ap.parse_args(argv)

    if a.cmd == "keygen":
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        key = Ed25519PrivateKey.generate()
        with open(a.out, "wb") as f:
            f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()))
        os.chmod(a.out, 0o600)
        with open(a.out + ".pub", "wb") as f:
            f.write(key.public_key().public_bytes(serialization.Encoding.PEM,
                                                  serialization.PublicFormat.SubjectPublicKeyInfo))
        print(f"wrote {a.out} (keep secret) and {a.out}.pub")
        return 0
    if a.cmd == "baseline":
        bl = make_baseline(a.paths, a.by)
        if a.sign:
            sign_baseline(bl, a.sign)
        with open(a.out, "w") as f:
            json.dump(bl, f, indent=2)
        print(f"baseline of {len(bl['files'])} files -> {a.out}{' (signed)' if a.sign else ''}")
        return 0
    if a.cmd == "record-change":
        print(json.dumps(record_change(a.ledger, a.item, a.by, a.ticket)))
        return 0

    findings, notes, since = [], [], None
    if a.baseline:
        with open(a.baseline) as f:
            bl = json.load(f)
        since = bl.get("created")
        if a.pubkey:
            if not verify_baseline(bl, a.pubkey):
                notes.append("BASELINE SIGNATURE INVALID - baseline may have been tampered with")
                findings.append({"source": "files", "item": a.baseline, "change": "baseline-signature-invalid"})
            else:
                notes.append("baseline signature valid")
        findings += check_files(bl)
    if a.k8s_declared:
        if a.kubectl:
            live = kubectl_live(a.k8s_declared) if shutil.which("kubectl") else None
            if live is None:
                notes.append("kubectl not found; kubernetes drift not checked")
        elif a.k8s_live:
            with open(a.k8s_live) as f:
                d = json.load(f)
            live = d.get("items", d) if isinstance(d, dict) else d
        else:
            live = None
        if live is not None:
            findings += check_kubernetes(a.k8s_declared, live)
    if a.terraform_dir:
        tf, msg = check_terraform(a.terraform_dir)
        findings += tf
        notes.append(f"terraform: {msg}")
    rep = build_report(findings, read_ledger(a.ledger, since), notes)
    with open(a.out, "w") as f:
        json.dump(rep, f, indent=2)
    print(f"drift: {rep['total']} finding(s), {rep['unapproved']} unapproved -> {a.out}")
    for n in notes:
        print("  note:", n)
    return 3 if rep["unapproved"] else 0


if __name__ == "__main__":
    sys.exit(main())
