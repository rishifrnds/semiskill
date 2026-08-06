"""Authenticated human identity adapters for publication decisions.

Local development binds decisions to the logged-in operating-system account. Production accepts
only a verified Entra/OIDC adapter result and fails closed when the adapter or required claims are
absent. Bearer tokens and raw assertions are never stored in artifacts.
"""
from __future__ import annotations

import csv
import io
import os
import platform
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Protocol

try:  # pragma: no cover - platform-specific import
    import pwd
except ImportError:  # Windows
    pwd = None


class IdentityRefused(RuntimeError):
    """A trustworthy human identity could not be established."""


@dataclass(frozen=True)
class AuthenticatedHuman:
    actor: str
    subject: str
    provider: str
    auth_context: dict = field(default_factory=dict)

    def __post_init__(self):
        if (not isinstance(self.actor, str) or not self.actor.strip()
                or not isinstance(self.subject, str) or not self.subject.strip()):
            raise IdentityRefused("authenticated actor and subject are required")
        if not isinstance(self.provider, str) or self.provider not in {"local_os", "entra_oidc"}:
            raise IdentityRefused(f"unsupported identity provider: {self.provider!r}")
        if not isinstance(self.auth_context, dict):
            raise IdentityRefused("authentication context must be an object")
        if self.provider == "local_os":
            account = self.auth_context.get("account")
            sid = self.auth_context.get("sid")
            uid = self.auth_context.get("uid")
            if account != self.actor:
                raise IdentityRefused("local identity actor is not bound to its OS account")
            if isinstance(sid, str) and sid:
                if self.subject != sid:
                    raise IdentityRefused("local identity subject is not bound to its SID")
            elif type(uid) is int and uid >= 0:
                if self.subject != f"uid:{uid}":
                    raise IdentityRefused("local identity subject is not bound to its uid")
            else:
                raise IdentityRefused("local identity requires a SID or uid")
        else:
            issuer = self.auth_context.get("issuer")
            tenant = self.auth_context.get("tenant_id")
            object_id = self.auth_context.get("object_id")
            if not all(isinstance(value, str) and value.strip()
                       for value in (issuer, tenant, object_id)):
                raise IdentityRefused("Entra identity requires issuer, tenant, and object ID")
            if object_id != self.subject:
                raise IdentityRefused("Entra identity subject is not bound to its object ID")


def validate_identity_policy(
    identity: AuthenticatedHuman,
    *,
    environment: str,
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
) -> None:
    """Apply environment policy after the adapter established an internally bound identity."""
    if not isinstance(environment, str) or environment not in {
        "development", "test", "production",
    }:
        raise IdentityRefused(f"unknown identity environment: {environment!r}")
    if environment != "production":
        return
    if identity.provider != "entra_oidc":
        raise IdentityRefused("production accepts only an Entra/OIDC authenticated identity")
    if not isinstance(expected_entra_issuer, str) or not expected_entra_issuer.strip():
        raise IdentityRefused("production Entra issuer policy is not configured")
    if not isinstance(expected_entra_tenant, str) or not expected_entra_tenant.strip():
        raise IdentityRefused("production Entra tenant policy is not configured")
    if identity.auth_context.get("issuer") != expected_entra_issuer:
        raise IdentityRefused("Entra issuer does not match production policy")
    if identity.auth_context.get("tenant_id") != expected_entra_tenant:
        raise IdentityRefused("Entra tenant does not match production policy")


def identity_from_authentication(
    authentication: dict,
    *,
    artifact_actor: str,
    environment: str,
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
) -> AuthenticatedHuman:
    """Revalidate persisted non-secret authentication evidence for reconciliation."""
    if not isinstance(authentication, dict):
        raise IdentityRefused("persisted authentication must be an object")
    if authentication.get("actor") != artifact_actor:
        raise IdentityRefused("persisted authentication actor does not match the artifact actor")
    identity = AuthenticatedHuman(
        actor=authentication.get("actor"),
        subject=authentication.get("subject"),
        provider=authentication.get("provider"),
        auth_context=authentication.get("context"),
    )
    validate_identity_policy(
        identity,
        environment=environment,
        expected_entra_issuer=expected_entra_issuer,
        expected_entra_tenant=expected_entra_tenant,
    )
    return identity


class EntraVerifier(Protocol):
    def verify(self, assertion: str) -> dict: ...


def local_os_identity(
    *,
    system: str | None = None,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> AuthenticatedHuman:
    """Resolve the interactive OS identity without environment-variable fallbacks."""
    system = system or platform.system()
    if system == "Windows":
        try:
            completed = runner(
                ["whoami", "/user", "/fo", "csv", "/nh"],
                capture_output=True,
                text=True,
                check=True,
                timeout=10,
            )
            row = next(csv.reader(io.StringIO(completed.stdout.strip())))
            account, sid = row[0].strip(), row[1].strip()
        except Exception as exc:  # noqa: BLE001 - normalize OS command failures
            raise IdentityRefused(f"could not resolve Windows account/SID: {exc}") from exc
        if not account or not sid.startswith("S-"):
            raise IdentityRefused("whoami did not return a valid account and SID")
        return AuthenticatedHuman(
            actor=account,
            subject=sid,
            provider="local_os",
            auth_context={"account": account, "sid": sid},
        )

    try:
        uid = os.getuid()
        if pwd is None:
            raise AttributeError("pwd module unavailable")
        account = pwd.getpwuid(uid).pw_name
    except (AttributeError, KeyError, OSError) as exc:
        raise IdentityRefused(f"could not resolve POSIX uid: {exc}") from exc
    return AuthenticatedHuman(
        actor=account,
        subject=f"uid:{uid}",
        provider="local_os",
        auth_context={"account": account, "uid": uid},
    )


def entra_identity(
    *,
    assertion: str | None,
    verifier: EntraVerifier | None,
    expected_issuer: str,
    expected_tenant: str,
) -> AuthenticatedHuman:
    """Verify an Entra assertion and return only allowlisted, non-secret identity metadata."""
    if not isinstance(expected_issuer, str) or not expected_issuer.strip():
        raise IdentityRefused("production Entra issuer policy is not configured")
    if not isinstance(expected_tenant, str) or not expected_tenant.strip():
        raise IdentityRefused("production Entra tenant policy is not configured")
    if verifier is None:
        raise IdentityRefused("production Entra/OIDC verifier is not configured")
    if not assertion:
        raise IdentityRefused("signed Entra/OIDC assertion is required")
    claims = verifier.verify(assertion)
    if not isinstance(claims, dict):
        raise IdentityRefused("Entra verifier returned invalid claims")
    if claims.get("iss") != expected_issuer or claims.get("tid") != expected_tenant:
        raise IdentityRefused("Entra issuer or tenant does not match configuration")
    oid = claims.get("oid")
    actor = claims.get("preferred_username") or claims.get("name")
    if not isinstance(oid, str) or not oid or not isinstance(actor, str) or not actor:
        raise IdentityRefused("verified Entra claims lack oid/actor")
    amr = claims.get("amr") if isinstance(claims.get("amr"), list) else []
    return AuthenticatedHuman(
        actor=actor,
        subject=oid,
        provider="entra_oidc",
        auth_context={
            "issuer": claims["iss"],
            "tenant_id": claims["tid"],
            "object_id": oid,
            "amr": [str(value) for value in amr],
        },
    )
