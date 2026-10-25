"""Zero-Trust controls for the AIPIR service: verify every request, least privilege, MFA,
two-person rule, tamper-evident audit.

* Identity   - every API call carries a bearer token (JWT). Production: an OIDC identity
               provider such as Microsoft Entra ID signs tokens with RS256 and publishes its keys
               (JWKS). Lab: tokens are HS256-signed with a secret generated at start-up.
* RBAC       - the token's `roles` claim maps to permissions in deploy/zero-trust/rbac_policy.yaml.
               Unknown roles grant nothing; there is no implicit admin bypass.
* MFA        - permissions listed under `mfa_required` need proof of multi-factor sign-in in the
               token's `amr` claim (Entra ID sets amr=["pwd","mfa"] after MFA).
* Workloads  - service identities (Alertmanager) are recognized by `idtyp=app`; they may only hold
               permissions the policy grants to workloads and can never approve a recovery.
* Two-person - an executed recovery needs an approver who is not the requester.
* Audit      - every decision is appended to a JSON-lines log in which each entry carries the
               SHA-256 of the previous entry, so deletion or editing is detectable (`verify_audit`).

Standard library + `cryptography` (for RS256) + PyYAML.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import time
from dataclasses import dataclass, field

import yaml

DEFAULT_POLICY = os.path.join(os.path.dirname(__file__), "..", "..", "deploy", "zero-trust", "rbac_policy.yaml")


class AuthError(Exception):
    """Authentication or authorization failure (message is safe to return to the caller)."""

    def __init__(self, status: int, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


# ---------------------------------------------------------------- tokens
class TokenVerifier:
    """Verify JWTs. mode='hs256' (lab, shared secret) or mode='rs256' (OIDC, JWKS file)."""

    def __init__(self, mode: str, issuer: str, audience: str, secret: bytes | None = None,
                 jwks: dict | None = None, leeway_s: int = 60):
        if mode not in ("hs256", "rs256"):
            raise ValueError("mode must be hs256 or rs256")
        if mode == "hs256" and not secret:
            raise ValueError("hs256 needs a secret")
        if mode == "rs256" and not jwks:
            raise ValueError("rs256 needs a JWKS document")
        self.mode, self.issuer, self.audience = mode, issuer, audience
        self.secret, self.leeway = secret, leeway_s
        self.keys = {}
        if jwks:
            from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers
            for k in jwks.get("keys", []):
                if k.get("kty") == "RSA":
                    n = int.from_bytes(_b64d(k["n"]), "big")
                    e = int.from_bytes(_b64d(k["e"]), "big")
                    self.keys[k.get("kid", "default")] = RSAPublicNumbers(e, n).public_key()

    def verify(self, token: str) -> dict:
        try:
            h64, p64, s64 = token.split(".")
            header, claims, sig = json.loads(_b64d(h64)), json.loads(_b64d(p64)), _b64d(s64)
        except Exception as exc:  # noqa: BLE001
            raise AuthError(401, "malformed token") from exc
        alg = header.get("alg")
        signing_input = f"{h64}.{p64}".encode()
        if self.mode == "hs256":
            if alg != "HS256":
                raise AuthError(401, "unexpected token algorithm")
            good = hmac.compare_digest(hmac.new(self.secret, signing_input, hashlib.sha256).digest(), sig)
            if not good:
                raise AuthError(401, "bad signature")
        else:
            if alg != "RS256":
                raise AuthError(401, "unexpected token algorithm")
            key = self.keys.get(header.get("kid", "default"))
            if key is None:
                raise AuthError(401, "unknown signing key")
            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            try:
                key.verify(sig, signing_input, padding.PKCS1v15(), hashes.SHA256())
            except InvalidSignature as exc:
                raise AuthError(401, "bad signature") from exc
        now = time.time()
        if claims.get("iss") != self.issuer:
            raise AuthError(401, "wrong issuer")
        aud = claims.get("aud")
        if self.audience not in (aud if isinstance(aud, list) else [aud]):
            raise AuthError(401, "wrong audience")
        if "exp" not in claims or now > float(claims["exp"]) + self.leeway:
            raise AuthError(401, "token expired")
        if "nbf" in claims and now < float(claims["nbf"]) - self.leeway:
            raise AuthError(401, "token not yet valid")
        return claims


def mint_lab_token(secret: bytes, issuer: str, audience: str, sub: str, roles: list[str],
                   mfa: bool = False, app: bool = False, ttl_s: int = 900) -> str:
    """Lab only: mint an HS256 token. Refuses to run when AIPIR_ENV=production."""
    if os.environ.get("AIPIR_ENV", "lab") == "production":
        raise RuntimeError("lab tokens are disabled in production; use the identity provider")
    now = int(time.time())
    claims = {"iss": issuer, "aud": audience, "sub": sub, "roles": roles, "iat": now, "nbf": now,
              "exp": now + ttl_s, "amr": ["pwd", "mfa"] if mfa else ["pwd"]}
    if app:
        claims["idtyp"] = "app"
        claims["amr"] = []
    h = _b64e(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = _b64e(json.dumps(claims).encode())
    s = _b64e(hmac.new(secret, f"{h}.{p}".encode(), hashlib.sha256).digest())
    return f"{h}.{p}.{s}"


# ---------------------------------------------------------------- policy
@dataclass
class Policy:
    roles: dict[str, set[str]]
    workload_roles: set[str]
    mfa_required: set[str]
    workload_forbidden: set[str]
    two_person: set[str]
    public: set[str] = field(default_factory=set)

    @classmethod
    def load(cls, path: str | None = None) -> "Policy":
        with open(path or DEFAULT_POLICY) as f:
            d = yaml.safe_load(f)
        return cls(roles={r: set(v["permissions"]) for r, v in d["roles"].items()},
                   workload_roles={r for r, v in d["roles"].items() if v.get("workload")},
                   mfa_required=set(d.get("mfa_required", [])),
                   workload_forbidden=set(d.get("workload_forbidden", [])),
                   two_person=set(d.get("two_person", [])),
                   public=set(d.get("public", [])))


@dataclass
class Principal:
    sub: str
    roles: list[str]
    mfa: bool
    workload: bool
    permissions: set[str]


class Authorizer:
    def __init__(self, verifier: TokenVerifier | None, policy: Policy, audit: "AuditLog"):
        self.verifier, self.policy, self.audit = verifier, policy, audit

    def principal(self, claims: dict) -> Principal:
        workload = claims.get("idtyp") == "app"
        roles = [r for r in claims.get("roles", []) if isinstance(r, str)]
        perms = set()
        for r in roles:
            if r not in self.policy.roles:
                continue
            if workload != (r in self.policy.workload_roles):
                continue  # human roles never apply to workloads and vice versa
            perms |= self.policy.roles[r]
        sub = claims.get("preferred_username") or claims.get("upn") or claims.get("sub") or "unknown"
        return Principal(sub=sub, roles=roles, mfa="mfa" in (claims.get("amr") or []),
                         workload=workload, permissions=perms)

    def authorize(self, auth_header: str | None, permission: str, resource: str = "") -> Principal:
        """Return the principal if allowed; raise AuthError otherwise. Every outcome is audited."""
        if permission in self.policy.public:
            return Principal("anonymous", [], False, False, {permission})
        p = None
        try:
            if self.verifier is None:
                raise AuthError(401, "authentication is required but no verifier is configured")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise AuthError(401, "missing bearer token")
            p = self.principal(self.verifier.verify(auth_header[7:].strip()))
            if permission not in p.permissions:
                raise AuthError(403, f"role(s) {p.roles} lack permission {permission}")
            if p.workload and permission in self.policy.workload_forbidden:
                raise AuthError(403, f"workload identities may not {permission}")
            if permission in self.policy.mfa_required and not p.workload and not p.mfa:
                raise AuthError(403, f"{permission} requires multi-factor authentication")
        except AuthError as e:
            self.audit.write({"decision": "deny", "permission": permission, "resource": resource,
                              "subject": p.sub if p else None, "reason": e.reason})
            raise
        self.audit.write({"decision": "allow", "permission": permission, "resource": resource,
                          "subject": p.sub, "roles": p.roles, "mfa": p.mfa, "workload": p.workload})
        return p

    def check_two_person(self, permission: str, requester: str, approver: Principal, resource: str):
        if permission in self.policy.two_person and requester == approver.sub:
            self.audit.write({"decision": "deny", "permission": permission, "resource": resource,
                              "subject": approver.sub, "reason": "two-person rule: approver is the requester"})
            raise AuthError(403, "two-person rule: the requester cannot approve their own recovery")


# ---------------------------------------------------------------- audit
class AuditLog:
    """Append-only JSON lines; each entry stores the SHA-256 of the previous line (hash chain)."""

    def __init__(self, path: str | None, sink=None):
        self.path, self.sink = path, sink
        self.lock = threading.Lock()
        self.prev = "0" * 64
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                lines = f.read().splitlines()
            if lines:
                self.prev = hashlib.sha256(lines[-1]).hexdigest()

    def write(self, event: dict):
        with self.lock:
            rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **event, "prev": self.prev}
            line = json.dumps(rec, sort_keys=True).encode()
            self.prev = hashlib.sha256(line).hexdigest()
            if self.path:
                with open(self.path, "ab") as f:
                    f.write(line + b"\n")
        if self.sink:
            self.sink(rec)
        return rec


def verify_audit(path: str) -> tuple[bool, int, str]:
    """Check the hash chain. Returns (ok, entries checked, message)."""
    prev = "0" * 64
    n = 0
    with open(path, "rb") as f:
        for n, line in enumerate(f.read().splitlines(), 1):
            if json.loads(line).get("prev") != prev:
                return False, n, f"chain broken at entry {n}"
            prev = hashlib.sha256(line).hexdigest()
    return True, n, "audit chain intact"


def from_env(audit_sink=None) -> Authorizer:
    """Build the authorizer from environment variables (see deploy/zero-trust/README.md)."""
    mode = os.environ.get("AIPIR_AUTH_MODE", "hs256").lower()
    policy = Policy.load(os.environ.get("AIPIR_POLICY"))
    audit = AuditLog(os.environ.get("AIPIR_AUDIT_LOG", "aipir_audit.jsonl"), sink=audit_sink)
    iss = os.environ.get("AIPIR_ISSUER", "aipir-lab")
    aud = os.environ.get("AIPIR_AUDIENCE", "api://aipir")
    if mode == "rs256":
        with open(os.environ["AIPIR_JWKS_FILE"]) as f:
            verifier = TokenVerifier("rs256", iss, aud, jwks=json.load(f))
    elif mode == "hs256":
        secret = os.environ.get("AIPIR_LAB_SECRET")
        verifier = TokenVerifier("hs256", iss, aud, secret=secret.encode()) if secret else None
    else:
        raise ValueError("AIPIR_AUTH_MODE must be hs256 (lab) or rs256 (OIDC); auth cannot be disabled")
    return Authorizer(verifier, policy, audit)


def _cli():
    import argparse
    ap = argparse.ArgumentParser(description="AIPIR Zero-Trust lab utilities")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("mint", help="mint a LAB token (HS256) using AIPIR_LAB_SECRET")
    m.add_argument("--sub", required=True)
    m.add_argument("--role", action="append", required=True)
    m.add_argument("--mfa", action="store_true")
    m.add_argument("--app", action="store_true", help="workload identity (e.g. Alertmanager)")
    m.add_argument("--ttl", type=int, default=900)
    v = sub.add_parser("verify-audit", help="check the audit log hash chain")
    v.add_argument("path")
    a = ap.parse_args()
    if a.cmd == "mint":
        secret = os.environ.get("AIPIR_LAB_SECRET")
        if not secret:
            raise SystemExit("set AIPIR_LAB_SECRET (generated by deploy/compose/gen-lab-secrets.sh)")
        print(mint_lab_token(secret.encode(), os.environ.get("AIPIR_ISSUER", "aipir-lab"),
                             os.environ.get("AIPIR_AUDIENCE", "api://aipir"), a.sub, a.role,
                             mfa=a.mfa, app=a.app, ttl_s=a.ttl))
    else:
        ok, n, msg = verify_audit(a.path)
        print(f"{msg} ({n} entries)")
        raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    _cli()
