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
import re
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
FINDING_IDENTITY_FIELDS = ("category", "severity")
CALIBRATED_RECHECK_PROMPT = re.compile(r"^P5-RECHECK-CALIBRATED@[1-9][0-9]*$")


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
    effective_findings: tuple[Finding, ...] = ()

    @property
    def ready(self) -> bool:
        return self.status == READY


def _text(value) -> str:
    return value.strip() if isinstance(value, str) else ""


def _completed_at(artifact: Artifact):
    return artifact.timestamp_end or artifact.timestamp_start


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
    skill_payload = skill_version.payload if isinstance(skill_version.payload, dict) else {}

    if artifact.artifact_type is not ArtifactType.REVIEW:
        structural.append("artifact is not a review")
    if not isinstance(artifact.payload, dict):
        structural.append("review payload must be an object")
    if not isinstance(skill_version.payload, dict):
        structural.append("skill version payload must be an object")
    if payload.get("review_kind") != CONTENT_REVIEW_KIND:
        structural.append("artifact is not a canonical content review")
    if payload.get("schema_version") != CONTENT_REVIEW_SCHEMA_VERSION:
        structural.append("content review schema version is unsupported")
    if not artifact.input_refs or artifact.input_refs[0] != skill_version.artifact_id:
        structural.append("review does not reference the exact skill version")
    if _completed_at(skill_version) > artifact.timestamp_start:
        structural.append("content review predates completion of the skill version")
    if payload.get("skill_payload_sha256") != payload_fingerprint(skill_payload):
        structural.append("payload hash does not match skill version")

    for facet in ("slug", "version", "role", "level"):
        if payload.get(facet) != skill_payload.get(facet):
            structural.append(f"{facet} does not match skill version")
    for key in ("prompt_version", "run_id", "batch_id", "reviewer_identity", "fixer_identity"):
        if not _text(payload.get(key)):
            structural.append(f"{key} is required")
    if payload.get("phase") != "recheck":
        unmet.append("latest content review is not an independent recheck")
    elif not CALIBRATED_RECHECK_PROMPT.fullmatch(str(payload.get("prompt_version") or "")):
        structural.append("recheck prompt version is not calibrated P5 evidence")
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
        if prior_ref is not None or len(artifact.input_refs) != 1:
            structural.append("first attempt must not reference a prior review")
    elif type(attempt) is int and attempt > 1:
        if not isinstance(prior_ref, str) or len(artifact.input_refs) != 2:
            structural.append("recheck attempt must reference the prior attempt")
        elif str(artifact.input_refs[1]) != prior_ref:
            structural.append("prior review payload and input reference disagree")
        elif store is not None:
            prior = store.get(artifact.input_refs[1])
            if prior is None or prior.artifact_type is not ArtifactType.REVIEW:
                structural.append("prior review artifact was not found")
            else:
                if _completed_at(prior) > artifact.timestamp_start:
                    structural.append("prior review was not complete before this attempt")
                prior_payload = prior.payload if isinstance(prior.payload, dict) else {}
                if not isinstance(prior.payload, dict):
                    structural.append("prior review payload must be an object")
                prior_attempt = prior_payload.get("attempt")
                if type(prior_attempt) is not int or attempt != prior_attempt + 1:
                    structural.append("attempt must increment prior review by exactly one")
                for key in ("slug", "skill_payload_sha256", "version", "role", "level"):
                    if prior_payload.get(key) != payload.get(key):
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


def _effective_findings(
    store: ArtifactStore | None,
    review: Artifact,
) -> tuple[list[Finding], list[str]]:
    """Fold immutable review rounds into the effective finding state at ``review``.

    Review bodies are append-only events. Omitting a prior finding is not an adjudication: the
    newest explicit occurrence controls only its disposition, while the issue identity remains
    immutable. This keeps an omitted open/disputed blocker visible and publication-blocking.
    """
    effective: dict[str, Finding] = {}
    errors: list[str] = []
    seen_artifacts: set = set()
    seen_runs: set[str] = set()
    seen_reviewers: set[str] = set()
    seen_fixers: set[str] = set()
    current: Artifact | None = review

    while current is not None:
        if current.artifact_id in seen_artifacts:
            errors.append("content review lineage contains a cycle")
            break
        seen_artifacts.add(current.artifact_id)
        payload = current.payload if isinstance(current.payload, dict) else {}
        if not isinstance(current.payload, dict):
            errors.append("review payload must be an object")
            break

        run_id = _text(payload.get("run_id"))
        reviewer = _text(payload.get("reviewer_identity"))
        fixer = _text(payload.get("fixer_identity"))
        if run_id:
            if run_id in seen_runs:
                errors.append("run_id must be unique across the review lineage")
            seen_runs.add(run_id)
        if reviewer:
            if reviewer in seen_reviewers:
                errors.append("reviewer_identity must be unique across the review lineage")
            if reviewer in seen_fixers:
                errors.append("reviewer context must be independent from every fixer context")
            seen_reviewers.add(reviewer)
        if fixer:
            if fixer in seen_reviewers:
                errors.append("reviewer context must be independent from every fixer context")
            seen_fixers.add(fixer)

        raw_findings = payload.get("findings")
        if not isinstance(raw_findings, list):
            errors.append("findings must be an array")
        else:
            for index, raw in enumerate(raw_findings):
                finding, finding_errors = _finding(raw, index)
                errors.extend(finding_errors)
                if finding is None:
                    continue
                newer = effective.get(finding.finding_id)
                if newer is None:
                    effective[finding.finding_id] = finding
                    continue
                if any(
                    getattr(newer, field) != getattr(finding, field)
                    for field in FINDING_IDENTITY_FIELDS
                ):
                    errors.append(
                        f"finding {finding.finding_id} identity changed across review attempts"
                    )
                if finding.disposition == "resolved" and newer.disposition != "resolved":
                    errors.append(
                        f"resolved finding {finding.finding_id} was reopened without a new finding_id"
                    )

        prior_ref = payload.get("prior_review_ref")
        if prior_ref is None:
            break
        if store is None or len(current.input_refs) != 2:
            errors.append("review lineage cannot resolve its prior review")
            break
        prior = store.get(current.input_refs[1])
        if prior is None or prior.artifact_type is not ArtifactType.REVIEW:
            errors.append("prior review artifact was not found")
            break
        current = prior

    return list(effective.values()), errors


def validate_content_review(
    store: ArtifactStore,
    artifact: Artifact,
    skill_version: Artifact,
) -> tuple[str, ...]:
    """Validate exact binding, typed data, lineage, and required deterministic checks."""
    structural, unmet, _ = _review_validation(artifact, skill_version, store)
    _, lineage_errors = _effective_findings(store, artifact)
    return tuple(structural + unmet + lineage_errors)


def readiness_for_version(store: ArtifactStore, skill_version: Artifact) -> Readiness:
    """Compute readiness from the latest canonical content-review round for this skill slug."""
    skill_payload = skill_version.payload if isinstance(skill_version.payload, dict) else {}
    slug = skill_payload.get("slug")
    slug_candidates = [
        artifact
        for artifact in store.by_type(ArtifactType.REVIEW)
        if isinstance(artifact.payload, dict)
        and artifact.payload.get("review_kind") == CONTENT_REVIEW_KIND
        and artifact.payload.get("slug") == slug
    ]
    if not slug_candidates:
        return Readiness(UNREVIEWED)
    candidates = [
        artifact for artifact in slug_candidates
        if artifact.input_refs and artifact.input_refs[0] == skill_version.artifact_id
    ]
    if not candidates:
        latest = max(slug_candidates, key=lambda artifact: (
            artifact.timestamp_start, str(artifact.artifact_id),
        ))
        return Readiness(
            STALE, latest,
            ("no content review references the exact skill version and payload hash",),
        )
    lineage_errors: list[str] = []
    by_attempt: dict[int, list[Artifact]] = {}
    for candidate in candidates:
        candidate_payload = candidate.payload if isinstance(candidate.payload, dict) else {}
        attempt = candidate_payload.get("attempt")
        if type(attempt) is not int or attempt < 1:
            lineage_errors.append("content review lineage contains an invalid attempt")
            continue
        by_attempt.setdefault(attempt, []).append(candidate)
    for attempt, rows in sorted(by_attempt.items()):
        if len(rows) != 1:
            lineage_errors.append(f"content review lineage has duplicate attempt {attempt}")
    for candidate in candidates:
        structural, _unmet, _findings = _review_validation(candidate, skill_version, store)
        lineage_errors.extend(structural)
    if by_attempt:
        maximum = max(by_attempt)
        missing = sorted(set(range(1, maximum + 1)) - set(by_attempt))
        if missing:
            lineage_errors.append(
                "content review lineage has missing attempts: "
                + ", ".join(str(value) for value in missing)
            )
        for attempt in range(2, maximum + 1):
            current = by_attempt.get(attempt, [])
            prior = by_attempt.get(attempt - 1, [])
            if len(current) == 1 and len(prior) == 1 and (
                len(current[0].input_refs) != 2
                or current[0].input_refs[1] != prior[0].artifact_id
            ):
                lineage_errors.append(
                    f"content review attempt {attempt} does not reference attempt {attempt - 1}"
                )
    candidates.sort(
        key=lambda artifact: (
            artifact.payload.get("attempt")
            if isinstance(artifact.payload, dict) and type(artifact.payload.get("attempt")) is int
            else -1,
            artifact.timestamp_start,
            str(artifact.artifact_id),
        )
    )
    latest = candidates[-1]
    if lineage_errors:
        errors = tuple(sorted(set(lineage_errors)))
        status = STALE if set(errors) == {"payload hash does not match skill version"} else INVALID
        return Readiness(status, latest, errors)
    return readiness_for_review(store, skill_version, latest)


def readiness_for_review(
    store: ArtifactStore,
    skill_version: Artifact,
    review: Artifact,
) -> Readiness:
    """Compute readiness for one immutable review without consulting later review rounds.

    Publication admission uses :func:`readiness_for_version` to require the latest evidence. A
    published badge uses this exact-review form so later review work cannot rewrite history.
    """
    structural, unmet, _ = _review_validation(review, skill_version, store)
    findings, lineage_errors = _effective_findings(store, review)
    structural.extend(lineage_errors)
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
    return Readiness(
        status, review, errors, open_blocking, open_non_blocking, tuple(findings),
    )


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
