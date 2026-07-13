"""L1 Capture — marketplace interaction events (comment / rating / reuse) as immutable artifacts.

Each event references the skill_version it targets via input_refs, so L3 can build comment threads,
aggregate ratings, and draw the reuse graph purely from the append-only log. Comment bodies are
untrusted user content and are delimited on retrieval (L3), never executed.
"""
from __future__ import annotations
from dataclasses import replace
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind


def _event(t: ArtifactType, *, actor, actor_kind, source_system, input_refs, payload,
           permissions_label) -> Artifact:
    art = Artifact.new(artifact_type=t, source_system=source_system, actor=actor,
                       actor_kind=actor_kind, input_refs=input_refs, payload=payload)
    if permissions_label != art.permissions_label:
        art = replace(art, permissions_label=permissions_label)
    return art


def build_comment(*, skill_version_id, actor: str, body: str, parent_id=None,
                  actor_kind: ActorKind = ActorKind.HUMAN,
                  source_system: SourceSystem = SourceSystem.WEB,
                  permissions_label: str = "team") -> Artifact:
    """A comment on a skill (optionally a reply to another comment via parent_id)."""
    refs = [skill_version_id]
    payload = {"body": str(body)}
    if parent_id is not None:
        refs.append(parent_id)
        payload["parent_id"] = str(parent_id)
    return _event(ArtifactType.COMMENT, actor=actor, actor_kind=actor_kind,
                  source_system=source_system, input_refs=refs, payload=payload,
                  permissions_label=permissions_label)


def build_rating(*, skill_version_id, actor: str, stars: int,
                 actor_kind: ActorKind = ActorKind.HUMAN,
                 source_system: SourceSystem = SourceSystem.WEB,
                 permissions_label: str = "team") -> Artifact:
    """A 1..5 star rating (upvote = 5-star)."""
    stars = int(stars)
    if not 1 <= stars <= 5:
        raise ValueError(f"stars must be 1..5, got {stars}")
    return _event(ArtifactType.RATING, actor=actor, actor_kind=actor_kind,
                  source_system=source_system, input_refs=[skill_version_id],
                  payload={"stars": stars}, permissions_label=permissions_label)


def build_reuse_event(*, skill_version_id, actor: str, method: str = "skills-add",
                      actor_kind: ActorKind = ActorKind.HUMAN,
                      source_system: SourceSystem = SourceSystem.CLI,
                      permissions_label: str = "team") -> Artifact:
    """A reuse event — someone installed/copied the skill (feeds the reuse graph + trending)."""
    return _event(ArtifactType.REUSE_EVENT, actor=actor, actor_kind=actor_kind,
                  source_system=source_system, input_refs=[skill_version_id],
                  payload={"method": str(method)}, permissions_label=permissions_label)
