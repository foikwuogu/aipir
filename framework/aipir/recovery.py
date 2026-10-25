"""Recover layer: recovery requests, approval workflow, and the Ansible hook.

Flow
  1. Alertmanager (workload identity, role aipir.alert-relay) or an operator (MFA) POSTs /recover.
     A request is created per routed process with status:
       - "planned"           in dry-run mode (default): nothing will run
       - "pending_approval"  in execute mode
  2. A different person with role aipir.recovery-approver (MFA) POSTs /recoveries/<id>/approve.
  3. The Ansible hook runs the process playbook. By default it runs `ansible-playbook --check
     --diff` (no changes made). Real changes need AIPIR_ANSIBLE_CHECK=0 in addition to execute mode,
     and the playbooks themselves only act through the site-supplied restore command.

Every transition is audited and emitted as an OpenTelemetry span/log by the service.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field

from .routing import PLAYBOOKS

ANSIBLE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "ansible")
PLAYBOOK_FILES = {"P1": "recover_boiler.yml", "P2": "recover_turbine.yml", "P3": "recover_water.yml",
                  "MON": "recover_monitoring.yml"}


@dataclass
class RecoveryRequest:
    id: str
    process: str
    playbook: str
    requested_by: str
    mode: str
    status: str
    created: float = field(default_factory=time.time)
    approved_by: str | None = None
    approved_at: float | None = None
    result: dict | None = None
    context: dict = field(default_factory=dict)


class AnsibleHook:
    def __init__(self, ansible_dir: str | None = None, check: bool | None = None,
                 binary: str | None = None, timeout_s: int = 900):
        self.dir = os.path.abspath(ansible_dir or os.environ.get("AIPIR_ANSIBLE_DIR", ANSIBLE_DIR))
        self.check = (os.environ.get("AIPIR_ANSIBLE_CHECK", "1") != "0") if check is None else check
        self.binary = binary or os.environ.get("AIPIR_ANSIBLE_PLAYBOOK", "ansible-playbook")
        self.timeout = timeout_s

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def run(self, req: RecoveryRequest) -> dict:
        pb = os.path.join(self.dir, "playbooks", PLAYBOOK_FILES.get(req.process, ""))
        inv = os.environ.get("AIPIR_ANSIBLE_INVENTORY", os.path.join(self.dir, "inventory", "lab.yml"))
        if not os.path.isfile(pb):
            return {"rc": None, "ok": False, "error": f"no playbook for process {req.process}"}
        if not self.available():
            return {"rc": None, "ok": False, "error": f"{self.binary} not found on PATH"}
        extra = {"aipir_request_id": req.id, "aipir_process": req.process,
                 "aipir_requested_by": req.requested_by, "aipir_approved_by": req.approved_by,
                 "aipir_top_sensors": req.context.get("top_sensors", [])}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(extra, f)
            vars_file = f.name
        cmd = [self.binary, "-i", inv, pb, "-e", f"@{vars_file}"]
        if self.check:
            cmd += ["--check", "--diff"]
        t0 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            out = {"rc": p.returncode, "ok": p.returncode == 0, "check_mode": self.check,
                   "seconds": round(time.time() - t0, 2), "cmd": " ".join(cmd[:4]),
                   "stdout_tail": p.stdout[-4000:], "stderr_tail": p.stderr[-2000:]}
        except subprocess.TimeoutExpired:
            out = {"rc": None, "ok": False, "error": "timeout", "seconds": self.timeout}
        finally:
            os.unlink(vars_file)
        return out


class RecoveryManager:
    def __init__(self, hook: AnsibleHook | None = None, store_path: str | None = None, on_event=None):
        self.mode = os.environ.get("AIPIR_RECOVERY", "dry-run")
        self.hook = hook or AnsibleHook()
        self.store_path = store_path or os.environ.get("AIPIR_RECOVERY_LOG")
        self.on_event = on_event or (lambda *a, **k: None)
        self.items: dict[str, RecoveryRequest] = {}
        self.lock = threading.Lock()

    def _persist(self, r: RecoveryRequest):
        if self.store_path:
            with open(self.store_path, "a") as f:
                f.write(json.dumps(asdict(r)) + "\n")

    def request(self, process: str, requested_by: str, context: dict | None = None) -> RecoveryRequest:
        status = "pending_approval" if self.mode == "execute" else "planned"
        r = RecoveryRequest(id=uuid.uuid4().hex[:12], process=process,
                            playbook=PLAYBOOKS.get(process, "recover_monitoring"),
                            requested_by=requested_by, mode=self.mode, status=status, context=context or {})
        with self.lock:
            self.items[r.id] = r
        self._persist(r)
        self.on_event("recovery.requested", r)
        return r

    def approve(self, rid: str, approver: str) -> RecoveryRequest:
        with self.lock:
            r = self.items.get(rid)
            if r is None:
                raise KeyError(rid)
            if r.status != "pending_approval":
                raise ValueError(f"request is {r.status}, not pending_approval")
            r.status, r.approved_by, r.approved_at = "running", approver, time.time()
        self.on_event("recovery.approved", r)
        r.result = self.hook.run(r)
        r.status = "succeeded" if r.result.get("ok") else "failed"
        self._persist(r)
        self.on_event("recovery.finished", r)
        return r

    def list(self) -> list[dict]:
        with self.lock:
            return [asdict(r) for r in sorted(self.items.values(), key=lambda x: x.created, reverse=True)]
