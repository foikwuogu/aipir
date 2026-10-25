#!/usr/bin/env python3
"""Lab demonstration of the configuration-drift check (writes data/processed/drift_demo.json).

1. Sign a baseline of the repository's own deployable configuration.
2. Make an UNAPPROVED change (edit an alert rule) -> drift check reports 1 unapproved finding.
3. Record the change in the change ledger -> the same finding becomes approved.
4. Tamper with the baseline file itself -> signature check fails.
5. Kubernetes: compare the declared manifests with SIMULATED live objects (declared objects plus
   typical server-filled defaults, one with a swapped image) -> exactly that object is flagged.
All edits happen in a temporary copy; the repository is not modified.
"""
import copy
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "framework"))
from aipir import drift  # noqa: E402

work = tempfile.mkdtemp(prefix="aipir-drift-")
os.chdir(work)
shutil.copytree(os.path.join(ROOT, "deploy"), "deploy", ignore=shutil.ignore_patterns(".lab", ".terraform*"))
paths = ["deploy/observability", "deploy/ansible/playbooks", "deploy/zero-trust", "deploy/k8s/base"]
out = {}
drift.main(["keygen", "--out", "key.pem"])
drift.main(["baseline", "--paths", *paths, "--out", "baseline.json", "--sign", "key.pem"])
args = ["check", "--baseline", "baseline.json", "--pubkey", "key.pem.pub", "--ledger", "changes.jsonl", "--out", "r.json"]
out["1_clean_exit"] = drift.main(args)
out["1_clean"] = json.load(open("r.json"))["total"]
with open("deploy/observability/prometheus/alert_rules.yml", "a") as f:
    f.write("# unapproved edit: threshold silently relaxed\n")
out["2_unapproved_exit"] = drift.main(args)
r = json.load(open("r.json"))
out["2_unapproved"] = {"total": r["total"], "unapproved": r["unapproved"], "item": r["findings"][0]["item"]}
drift.main(["record-change", "--ledger", "changes.jsonl", "--item", "deploy/observability/prometheus/alert_rules.yml",
            "--by", "alice", "--ticket", "CHG-0042"])
out["3_after_change_record_exit"] = drift.main(args)
r = json.load(open("r.json"))
out["3_after_change_record"] = {"total": r["total"], "unapproved": r["unapproved"],
                                "misconfigurations_per_100_changes": r["misconfigurations_per_100_changes"]}
b = json.load(open("baseline.json"))
b["files"]["deploy/observability/prometheus/alert_rules.yml"] = "0" * 64
json.dump(b, open("baseline.json", "w"))
out["4_tampered_baseline_exit"] = drift.main(args)
out["4_tampered_baseline_notes"] = json.load(open("r.json"))["notes"]
live = []
for d in drift.load_manifests("deploy/k8s/base"):
    o = copy.deepcopy(d)
    o.setdefault("metadata", {}).update({"uid": "simulated", "resourceVersion": "1"})
    if o["kind"] == "Deployment":
        o["spec"]["progressDeadlineSeconds"] = 600
        for c in o["spec"]["template"]["spec"]["containers"]:
            c["imagePullPolicy"] = "IfNotPresent"
            c["terminationMessagePath"] = "/dev/termination-log"
        if o["metadata"]["name"] == "aipir-detector":
            o["spec"]["template"]["spec"]["containers"][0]["image"] = "ghcr.io/attacker/aipir:latest"
    live.append(o)
json.dump(live, open("live.json", "w"))
out["5_k8s_exit"] = drift.main(["check", "--k8s-declared", "deploy/k8s/base", "--k8s-live", "live.json", "--out", "k.json"])
k = json.load(open("k.json"))
out["5_k8s"] = {"objects_declared": len(live), "findings": k["findings"]}
json.dump(out, open(os.path.join(ROOT, "data/processed/drift_demo.json"), "w"), indent=2)
print(json.dumps(out, indent=2))
shutil.rmtree(work, ignore_errors=True)
ok = (out["1_clean"] == 0 and out["2_unapproved"]["unapproved"] == 1 and out["3_after_change_record"]["unapproved"] == 0
      and out["4_tampered_baseline_exit"] == 3 and len(k["findings"]) == 1)
sys.exit(0 if ok else 1)
