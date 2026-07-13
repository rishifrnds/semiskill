from __future__ import annotations
import uuid
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum


class ArtifactType(str, Enum):
    # --- domain lifecycle (Phase A; created in migration 0001) ---
    SKILL_VERSION = "skill_version"      # L1 Capture — a submitted / versioned skill
    SCAN_RUN = "scan_run"                # L6 Sensor — one scanner stage's verdict
    INJECTION_TEST = "injection_test"    # L6 Sensor — held-out injection-corpus result
    REVIEW = "review"                    # L4/L5 — aggregated verdict proposal
    APPROVAL = "approval"                # L4 — human signoff (the publish gate)
    COMMENT = "comment"                  # L1 — marketplace comment thread
    RATING = "rating"                    # L1 — rating / upvote
    REUSE_EVENT = "reuse_event"          # observed telemetry — a `skills add` / copy
    # --- L5/L6 controller vocabulary (added to the DB enum via later ALTER TYPE migrations) ---
    PROPOSAL = "proposal"
    EXECUTION = "execution"
    SENSOR_READING = "sensor_reading"
    GOLD_SET = "gold_set"


class SourceSystem(str, Enum):
    GITHUB = "github"
    SHAREPOINT = "sharepoint"
    CLI = "cli"
    WEB = "web"


class ActorKind(str, Enum):
    HUMAN = "human"
    SERVICE_ACCOUNT = "service-account"
    AGENT = "agent"


# Constrained governance vocabularies (also enforced with a DB CHECK — see migration 0001).
PERMISSIONS_LABELS = ("public", "team", "need-to-know", "regulated")
OBJECTIVE_TAGS = ("safety", "velocity", "reuse", "compliance")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Artifact:
    artifact_id: uuid.UUID
    artifact_type: ArtifactType
    source_system: SourceSystem
    actor: str
    actor_kind: ActorKind
    timestamp_start: datetime
    timestamp_end: datetime | None = None
    input_refs: list[uuid.UUID] = field(default_factory=list)
    output_refs: list[uuid.UUID] = field(default_factory=list)
    permissions_label: str = "team"
    objective_tag: str = "velocity"
    ground_truth_ref: str | None = None
    eval_score: float | None = None
    rollback_ref: dict | None = None
    cost_usd: float | None = None
    corrects_ref: uuid.UUID | None = None
    payload: dict = field(default_factory=dict)

    @classmethod
    def new(cls, *, artifact_type, source_system, actor, actor_kind,
            input_refs=None, payload=None) -> "Artifact":
        return cls(
            artifact_id=uuid.uuid4(),
            artifact_type=artifact_type,
            source_system=source_system,
            actor=actor,
            actor_kind=actor_kind,
            timestamp_start=_now(),
            input_refs=list(input_refs or []),
            payload=dict(payload or {}),
        )

    def with_eval_score(self, score: float) -> "Artifact":
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"eval_score must be in [0,1], got {score}")
        return replace(self, eval_score=score)
