"""Content-review evidence and deterministic readiness.

Canonical reviews are immutable ``review`` artifacts bound to one exact skill-version fingerprint.
The model may report observations, including a claimed ``ready`` value, but deterministic code is
the only authority: all required checks must pass, lineage/facets/hashes must match, reviewer and
fixer contexts must be independent, and no blocking finding may remain open or disputed.

The legacy ``REVIEW.json`` readers remain temporarily for migration only. They must not be used by
new publication, scoreboard, or badge code and no legacy record can produce canonical readiness.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import ArtifactStore
from semiskill.capture.intake import payload_fingerprint

REVIEW_FILENAME = "REVIEW.json"

# Gate status for a skill, worst to best. Legacy file readers expose only the first three for
# compatibility; canonical artifact readiness additionally distinguishes stale and invalid evidence.
UNREVIEWED = "unreviewed"
REVIEWED = "reviewed"
READY = "recheck-ready"
STALE = "stale"
INVALID = "invalid"

CONTENT_REVIEW_KIND = "content_review"
CONTENT_REVIEW_SCHEMA_VERSION = 1
LEGACY_CONTENT_REVIEW_KIND = "content_review_legacy"
SECURITY_REVIEW_KIND = "security_aggregate"

REQUIRED_CHECKS = (
    "strict_lint",
    "consistency",
    "source_hash",
    "artifact_reconciliation",
)
FINDING_SEVERITIES = frozenset({"blocking", "non_blocking"})
FINDING_DISPOSITIONS = frozenset({"open", "resolved", "disputed"})


@dataclass(frozen=True)
class Finding:
    finding_id: str
    category: str
    severity: str
    evidence: str
    location: str
    required_change: str
    disposition: str


@dataclass(frozen=True)
class Readiness:
    status: str
    review: Artifact | None = None
    errors: tuple[str, ...] = ()
    open_blocking_findings: int = 0
    open_non_blocking_findings: int = 0

    @property
    def ready(self) -> bool:
        return self.status == READY


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _finding(raw: object, index: int) -> tuple[Finding | None, list[str]]:
    if not isinstance(raw, dict):
        return None, [f"finding {index} must be an object"]
    errors: list[str] = []
    values = {
        key: _text(raw.get(key))
        for key in (
            "finding_id", "category", "severity", "evidence", "location",
            "required_change", "disposition",
        )
    }
    for key, value in values.items():
        if not value:
            errors.append(f"finding {index} {key} is required")
    if values["severity"] and values["severity"] not in FINDING_SEVERITIES:
        errors.append(f"finding {index} severity is invalid")
    if values["disposition"] and values["disposition"] not in FINDING_DISPOSITIONS:
        errors.append(f"finding {index} disposition is invalid")
    return (Finding(**values) if not errors else None), errors


def make_content_review(
    *,
    skill_version: Artifact,
    phase: str,
    prompt_version: str,
    run_id: str,
    batch_id: str,
    attempt: int,
    reviewer_identity: str,
    fixer_identity: str,
    checks: dict,
    findings: Iterable[dict],
    prior_review: Artifact | None = None,
    agent_ready_claim: bool | None = None,
) -> Artifact:
    """Construct content-review evidence; never accept or return authoritative readiness."""
    if skill_version.artifact_type is not ArtifactType.SKILL_VERSION:
        raise ValueError("content review requires a skill_version artifact")
    payload = skill_version.payload
    fingerprint = payload_fingerprint(payload)
    refs = [skill_version.artifact_id]
    if prior_review is not None:
        refs.append(prior_review.artifact_id)
    review_payload = {
        "review_kind": CONTENT_REVIEW_KIND,
        "schema_version": CONTENT_REVIEW_SCHEMA_VERSION,
        "phase": phase,
        "prompt_version": prompt_version,
        "run_id": run_id,
        "batch_id": batch_id,
        "attempt": attempt,
        "slug": payload.get("slug"),
        "skill_payload_sha256": fingerprint,
        "version": payload.get("version"),
        "role": payload.get("role"),
        "level": payload.get("level"),
        "reviewer_identity": reviewer_identity,
        "fixer_identity": fixer_identity,
        "prior_review_ref": str(prior_review.artifact_id) if prior_review is not None else None,
        "checks": checks,
        "findings": list(findings),
    }
    if agent_ready_claim is not None:
        review_payload["agent_ready_claim"] = agent_ready_claim
    artifact = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor=reviewer_identity,
        actor_kind=ActorKind.AGENT,
        input_refs=refs,
        payload=review_payload,
    )
    return replace(
        artifact,
        permissions_label=skill_version.permissions_label,
        objective_tag="safety",
        ground_truth_ref=fingerprint,
    )


def _review_validation(
    artifact: Artifact,
    skill_version: Artifact,
    store: ArtifactStore | None,
) -> tuple[list[str], list[str], list[Finding]]:
    """Return structural errors, unmet readiness checks, and parsed findings."""
    structural: list[str] = []
    unmet: list[str] = []
    findings: list[Finding] = []
    payload = artifact.payload if isinstance(artifact.payload, dict) else {}

    if artifact.artifact_type is not ArtifactType.REVIEW:
        structural.append("artifact is not a review")
    if payload.get("review_kind") != CONTENT_REVIEW_KIND:
        structural.append("artifact is not a canonical content review")
    if payload.get("schema_version") != CONTENT_REVIEW_SCHEMA_VERSION:
        structural.append("content review schema version is unsupported")
    if not artifact.input_refs or artifact.input_refs[0] != skill_version.artifact_id:
        structural.append("review does not reference the exact skill version")
    if payload.get("skill_payload_sha256") != payload_fingerprint(skill_version.payload):
        structural.append("payload hash does not match skill version")

    for facet in ("slug", "version", "role", "level"):
        if payload.get(facet) != skill_version.payload.get(facet):
            structural.append(f"{facet} does not match skill version")
    for key in ("prompt_version", "run_id", "batch_id", "reviewer_identity", "fixer_identity"):
        if not _text(payload.get(key)):
            structural.append(f"{key} is required")
    if payload.get("phase") != "recheck":
        unmet.append("latest content review is not an independent recheck")
    if (
        _text(payload.get("reviewer_identity"))
        and payload.get("reviewer_identity") == payload.get("fixer_identity")
    ):
        structural.append("reviewer and fixer identities are not independent")

    attempt = payload.get("attempt")
    if type(attempt) is not int or attempt < 1:
        structural.append("attempt must be a positive integer")
    prior_ref = payload.get("prior_review_ref")
    if attempt == 1:
        if prior_ref is not None or len(artifact.input_refs) > 1:
            structural.append("first attempt must not reference a prior review")
    elif type(attempt) is int and attempt > 1:
        if not isinstance(prior_ref, str) or len(artifact.input_refs) < 2:
            structural.append("recheck attempt must reference the prior attempt")
        elif str(artifact.input_refs[1]) != prior_ref:
            structural.append("prior review payload and input reference disagree")
        elif store is not None:
            prior = store.get(artifact.input_refs[1])
            if prior is None or prior.artifact_type is not ArtifactType.REVIEW:
                structural.append("prior review artifact was not found")
            else:
                prior_attempt = prior.payload.get("attempt")
                if type(prior_attempt) is not int or attempt != prior_attempt + 1:
                    structural.append("attempt must increment prior review by exactly one")
                for key in ("slug", "skill_payload_sha256", "version", "role", "level"):
                    if prior.payload.get(key) != payload.get(key):
                        structural.append(f"prior review {key} lineage does not match")

    raw_checks = payload.get("checks")
    if not isinstance(raw_checks, dict):
        structural.append("checks must be an object")
        raw_checks = {}
    for name in REQUIRED_CHECKS:
        check = raw_checks.get(name)
        if not isinstance(check, dict):
            structural.append(f"check {name} is required")
            continue
        passed = check.get("passed")
        if type(passed) is not bool:
            structural.append(f"check {name} passed must be a boolean")
        elif not passed:
            unmet.append(f"check {name} did not pass")
        if not _text(check.get("evidence")):
            structural.append(f"check {name} evidence is required")

    raw_findings = payload.get("findings")
    if not isinstance(raw_findings, list):
        structural.append("findings must be an array")
    else:
        seen: set[str] = set()
        for index, raw in enumerate(raw_findings):
            parsed, errors = _finding(raw, index)
            structural.extend(errors)
            if parsed is not None:
                if parsed.finding_id in seen:
                    structural.append(f"finding {index} finding_id is duplicated")
                seen.add(parsed.finding_id)
                findings.append(parsed)
    return structural, unmet, findings


def validate_content_review(
    store: ArtifactStore,
    artifact: Artifact,
    skill_version: Artifact,
) -> tuple[str, ...]:
    """Validate exact binding, typed data, lineage, and required deterministic checks."""
    structural, unmet, _ = _review_validation(artifact, skill_version, store)
    return tuple(structural + unmet)


def readiness_for_version(store: ArtifactStore, skill_version: Artifact) -> Readiness:
    """Compute readiness from the latest canonical content-review round for this skill slug."""
    slug = skill_version.payload.get("slug")
    candidates = [
        artifact
        for artifact in store.by_type(ArtifactType.REVIEW)
        if artifact.payload.get("review_kind") == CONTENT_REVIEW_KIND
        and artifact.payload.get("slug") == slug
    ]
    if not candidates:
        return Readiness(UNREVIEWED)
    candidates.sort(
        key=lambda artifact: (
            artifact.payload.get("attempt")
            if type(artifact.payload.get("attempt")) is int
            else -1,
            artifact.timestamp_start,
            str(artifact.artifact_id),
        )
    )
    latest = candidates[-1]
    structural, unmet, findings = _review_validation(latest, skill_version, store)
    open_blocking = sum(
        finding.severity == "blocking" and finding.disposition in {"open", "disputed"}
        for finding in findings
    )
    open_non_blocking = sum(
        finding.severity == "non_blocking" and finding.disposition in {"open", "disputed"}
        for finding in findings
    )
    errors = tuple(structural + unmet)
    if "payload hash does not match skill version" in structural:
        status = STALE
    elif structural:
        status = INVALID
    elif unmet or open_blocking:
        status = REVIEWED
    else:
        status = READY
    return Readiness(status, latest, errors, open_blocking, open_non_blocking)


# --- Legacy file migration readers. These are evidence-only and never create canonical readiness. ---

def read_review_dir(skill_dir: str | Path) -> dict | None:
    """Read a legacy REVIEW.json record for migration, or None if absent/unreadable."""
    path = Path(skill_dir) / REVIEW_FILENAME
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def has_review(skill_dir: str | Path) -> bool:
    """Whether a legacy REVIEW.json exists at all."""
    return (Path(skill_dir) / REVIEW_FILENAME).exists()


def read_review(skills_root: str | Path, slug: str) -> dict | None:
    """Read a legacy review by slug for migration-only callers."""
    return read_review_dir(Path(skills_root) / slug)


def gate_status(review: dict | None) -> str:
    """Classify legacy evidence for migration reports; never use this as a publication gate."""
    if not review:
        return UNREVIEWED
    recheck = review.get("recheck") or {}
    if recheck.get("ready") is True:
        return READY
    if review.get("findings") is not None or review.get("review"):
        return REVIEWED
    return UNREVIEWED
