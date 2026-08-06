"""Authenticated append-only unpublication of an active approval/v1 head."""
from __future__ import annotations

from dataclasses import replace

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import ArtifactStore
from semiskill.governance.identity import AuthenticatedHuman
from semiskill.governance.publish import APPROVAL_SCHEMA, _safe_authentication, _validate_environment


class RollbackRefused(Exception):
    """The exact active publication cannot be safely corrected."""


def decide_unpublication(
    *,
    store: ArtifactStore,
    published_approval_id,
    reason: str,
    identity: AuthenticatedHuman,
    environment: str,
    quarantine: bool = True,
    expected_entra_issuer: str | None = None,
    expected_entra_tenant: str | None = None,
) -> Artifact:
    """Append an authenticated correction; never mutate or delete the original approval."""
    _validate_environment(
        identity,
        environment,
        expected_entra_issuer=expected_entra_issuer,
        expected_entra_tenant=expected_entra_tenant,
    )
    reason = reason.strip() if isinstance(reason, str) else ""
    if not reason:
        raise RollbackRefused("a non-empty human unpublication reason is required")
    published = store.get(published_approval_id)
    if (
        published is None
        or published.artifact_type is not ArtifactType.APPROVAL
        or published.payload.get("schema_version") != APPROVAL_SCHEMA
        or published.payload.get("decision") != "approve"
        or published.payload.get("published") is not True
    ):
        raise RollbackRefused("active approval/v1 publication not found")
    corrections = [
        artifact for artifact in store.by_type(ArtifactType.APPROVAL)
        if artifact.corrects_ref == published.artifact_id
    ]
    if corrections:
        matching = next((artifact for artifact in corrections
                         if artifact.payload.get("decision") == "unpublish"), None)
        if matching is not None:
            activate = getattr(store, "activate_approval", None)
            if not callable(activate):
                raise RollbackRefused("verified publication actuator is unavailable")
            activate(matching.artifact_id)
            return matching
        raise RollbackRefused("publication already has a different correction")

    payload = {
        **published.payload,
        "decision": "unpublish",
        "verdict": "approve",
        "published": False,
        "reason": reason,
        "environment": environment,
        "quarantined": bool(quarantine),
        "authentication": _safe_authentication(identity),
    }
    correction = Artifact.new(
        artifact_type=ArtifactType.APPROVAL,
        source_system=(SourceSystem.CLI if identity.provider == "local_os" else SourceSystem.WEB),
        actor=identity.actor,
        actor_kind=ActorKind.HUMAN,
        input_refs=list(published.input_refs),
        payload=payload,
    )
    correction = replace(
        correction,
        permissions_label=published.permissions_label,
        objective_tag="safety",
        corrects_ref=published.artifact_id,
        rollback_ref={"action": "reapprove", "approval_id": str(published.artifact_id)},
    )
    append_approval = getattr(store, "append_approval", None)
    if not callable(append_approval):
        raise RollbackRefused("verified publication actuator is unavailable")
    return append_approval(correction)


def unpublish_skill(*_args, **_kwargs):
    """Tombstone for the callback-based rollback API."""
    raise RollbackRefused(
        "unpublish_skill callback API was removed; use decide_unpublication with authenticated identity"
    )
