from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Mapping, Protocol

from semiskill.artifacts.schema import PERMISSIONS_LABELS


class PrincipalUnauthenticated(RuntimeError):
    """The request did not establish an authenticated catalog principal."""


class PrincipalResolutionUnavailable(RuntimeError):
    """The configured identity-to-clearance service could not provide a trustworthy result."""


@dataclass(frozen=True)
class ResolvedPrincipal:
    subject: str
    provider: str
    labels: tuple[str, ...]

    def __post_init__(self):
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("resolved principal subject is required")
        if not isinstance(self.provider, str) or not self.provider.strip():
            raise ValueError("resolved principal provider is required")
        normalized = resolve_allowed_labels(self.labels)
        object.__setattr__(self, "labels", normalized)


class OidcClaimsVerifier(Protocol):
    def verify(self, assertion: str) -> dict: ...


@dataclass(frozen=True)
class EntraPrincipalResolver:
    """Convert a verified Entra bearer assertion into allowlisted catalog labels."""

    verifier: OidcClaimsVerifier
    expected_issuer: str
    expected_tenant: str
    group_labels: Mapping[str, tuple[str, ...]]

    def __post_init__(self):
        if self.verifier is None:
            raise ValueError("Entra verifier is required")
        if not isinstance(self.expected_issuer, str) or not self.expected_issuer.strip():
            raise ValueError("Entra issuer policy is required")
        if not isinstance(self.expected_tenant, str) or not self.expected_tenant.strip():
            raise ValueError("Entra tenant policy is required")
        for labels in self.group_labels.values():
            resolve_allowed_labels(labels)

    def __call__(self, headers) -> ResolvedPrincipal:
        authorization = headers.get("Authorization")
        if not isinstance(authorization, str) or not authorization.startswith("Bearer "):
            raise PrincipalUnauthenticated("signed Entra bearer assertion is required")
        assertion = authorization[7:].strip()
        if not assertion:
            raise PrincipalUnauthenticated("signed Entra bearer assertion is required")
        try:
            claims = self.verifier.verify(assertion)
        except PrincipalResolutionUnavailable:
            raise
        except Exception as exc:
            raise PrincipalUnauthenticated("Entra assertion verification failed") from exc
        if not isinstance(claims, dict):
            raise PrincipalUnauthenticated("Entra verifier returned invalid claims")
        if claims.get("iss") != self.expected_issuer or claims.get("tid") != self.expected_tenant:
            raise PrincipalUnauthenticated("Entra issuer or tenant is invalid")
        subject = claims.get("oid")
        if not isinstance(subject, str) or not subject.strip():
            raise PrincipalUnauthenticated("Entra object identity is missing")
        groups = claims.get("groups") if isinstance(claims.get("groups"), list) else []
        labels = {"public"}
        for group in groups:
            if isinstance(group, str):
                labels.update(self.group_labels.get(group, ()))
        return ResolvedPrincipal(
            subject=subject,
            provider="entra_oidc",
            labels=tuple(sorted(labels)),
        )


def resolve_allowed_labels(principal: Iterable[str]) -> tuple[str, ...]:
    """The single place that decides which permission labels a caller may see. For now `principal`
    IS the caller's iterable of labels; this normalizes them (dedup, ordered tuple) and is the one
    seam to extend when a real principal->labels mapping (roles/groups/identity) arrives. Every L3
    retrieval and provenance path resolves through here so they cannot drift. Fails closed on an
    empty clearance."""
    if isinstance(principal, (str, bytes)):
        raise ValueError("principal labels must be an iterable of labels")
    try:
        values = tuple(principal)
    except TypeError as exc:
        raise ValueError("principal labels must be an iterable of labels") from exc
    if any(not isinstance(label, str) or label not in PERMISSIONS_LABELS for label in values):
        raise ValueError("principal contains an unsupported permission label")
    labels = tuple(sorted(set(values)))
    if not labels:
        raise ValueError("principal resolves to no permission labels")
    return labels
