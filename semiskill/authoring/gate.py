"""Content-review evidence and deterministic readiness.

Canonical reviews are immutable ``review`` artifacts bound to one exact skill-version fingerprint.
The model may report observations, including a claimed ``ready`` value, but deterministic code is
the only authority: all required checks must pass, lineage/facets/hashes must match, reviewer and
fixer contexts must be independent, and no blocking finding may remain open or disputed.

The legacy ``REVIEW.json`` readers remain temporarily for migration only. They must not be used by
new publication, scoreboard, or badge code and no legacy record can produce canonical readiness.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
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
CONTENT_REVIEW_SCHEMA_VERSION = 2
MAX_REVIEW_ATTEMPTS = 64
REVIEW_BATCH_CONTRACT_SCHEMA = "semiskill.review-batch/v1"
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
FINDING_CATEGORIES = frozenset({
    "technical_correctness",
    "verb_honesty",
    "hallucination_risk",
    "retrieval_budget",
    "unused_slot",
    "handoff_contract",
    "facet_drift",
    "security",
    "usability",
})
FINDING_IDENTITY_FIELDS = (
    "category", "severity", "evidence", "location", "required_change",
)
CALIBRATED_RECHECK_PROMPT = re.compile(r"^P5-RECHECK-CALIBRATED@[1-9][0-9]*$")
ADVERSARIAL_REVIEW_PROMPT = re.compile(r"^P1-ADVERSARIAL-REVIEW@[1-9][0-9]*$")
REVIEW_AUTHENTICATION_PROVIDERS = frozenset({"database-role", "test"})
REVIEW_AUTHENTICATION_CONTEXT_KEYS = frozenset({"provider", "subject_sha256"})
SHA256_REFERENCE = re.compile(r"^sha256:[0-9a-f]{64}$")


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


def _semver(value: object) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", str(value or ""))
    return tuple(int(part) for part in match.groups()) if match else None


def _contract_digest(payload: dict) -> str | None:
    try:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def canonical_review_authentication_context(value: object) -> dict[str, str] | None:
    """Return the bounded non-secret coordinator identity claim, or ``None`` if invalid."""
    if not isinstance(value, Mapping) or set(value) != REVIEW_AUTHENTICATION_CONTEXT_KEYS:
        return None
    provider = value.get("provider")
    subject_sha256 = value.get("subject_sha256")
    if (
        provider not in REVIEW_AUTHENTICATION_PROVIDERS
        or not isinstance(subject_sha256, str)
        or not SHA256_REFERENCE.fullmatch(subject_sha256)
    ):
        return None
    return {"provider": provider, "subject_sha256": subject_sha256}


def _review_contract_errors(
    review: Artifact,
    skill_version: Artifact,
    store: ArtifactStore | None,
) -> list[str]:
    """Validate the immutable coordinator lease copied into a content review."""
    errors: list[str] = []
    payload = review.payload if isinstance(review.payload, dict) else {}
    raw_contract_id = payload.get("contract_artifact_id")
    try:
        contract_id = uuid.UUID(raw_contract_id) if isinstance(raw_contract_id, str) else None
    except ValueError:
        contract_id = None
    if contract_id is None:
        return ["contract_artifact_id must be a UUID"]
    if len(review.input_refs) < 2 or review.input_refs[1] != contract_id:
        errors.append("content review does not reference its issued contract")
    if store is None:
        errors.append("content review contract cannot be resolved")
        return errors
    contract = store.get(contract_id)
    if contract is None or contract.artifact_type is not ArtifactType.GATE_DECISION:
        errors.append("content review contract artifact was not found")
        return errors
    exact_verifier = getattr(store, "review_contract_verified", None)
    verified_reader = getattr(store, "verified_review_contract_ids", None)
    verified = (
        exact_verifier(contract_id, skill_version.permissions_label)
        if callable(exact_verifier)
        else callable(verified_reader) and contract_id in verified_reader()
    )
    if not verified:
        errors.append("content review contract was not issued by the verified actuator")
    contract_payload = contract.payload if isinstance(contract.payload, dict) else {}
    required_root = {
        "schema_version", "batch_id", "run_id", "phase", "prompt_version", "attempt",
        "issuer_identity", "authentication_context", "cells",
    }
    if set(contract_payload) != required_root:
        errors.append("content review contract has unexpected fields")
    if contract_payload.get("schema_version") != REVIEW_BATCH_CONTRACT_SCHEMA:
        errors.append("content review contract schema is unsupported")
    if (
        contract.source_system is not SourceSystem.CLI
        or contract.actor_kind is not ActorKind.SERVICE_ACCOUNT
        or contract.objective_tag != "safety"
        or contract.actor != contract_payload.get("issuer_identity")
    ):
        errors.append("content review contract issuer is not trusted")
    if canonical_review_authentication_context(
        contract_payload.get("authentication_context")
    ) is None:
        errors.append("content review contract authentication context is invalid")
    if contract.ground_truth_ref != _contract_digest(contract_payload):
        errors.append("content review contract digest does not match")
    if contract.permissions_label != skill_version.permissions_label:
        errors.append("content review contract permission label does not match")
    if _completed_at(contract) > review.timestamp_start:
        errors.append("content review predates its issued contract")

    cells = contract_payload.get("cells")
    if not isinstance(cells, list) or len(cells) != 1:
        errors.append("content review contract must contain exactly one skill lease")
        return errors
    required_cell = {
        "slug", "skill_version_id", "skill_payload_sha256", "version", "role", "level",
        "reviewer_identity", "fixer_identity", "lineage_id", "prior_review_ref", "checks",
    }
    seen_slugs: set[str] = set()
    seen_reviewers: set[str] = set()
    selected: list[dict] = []
    expected_refs: list[uuid.UUID] = []
    prior_refs: list[uuid.UUID] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or set(cell) != required_cell:
            errors.append(f"content review contract cell {index} is malformed")
            continue
        slug = _text(cell.get("slug"))
        reviewer = _text(cell.get("reviewer_identity"))
        fixer = _text(cell.get("fixer_identity"))
        if not slug or slug in seen_slugs:
            errors.append("content review contract slugs must be unique")
        seen_slugs.add(slug)
        if not reviewer or reviewer in seen_reviewers:
            errors.append("content review contract reviewer identities must be unique")
        seen_reviewers.add(reviewer)
        if not fixer or reviewer == fixer:
            errors.append("content review contract reviewer and fixer must be independent")
        try:
            skill_id = uuid.UUID(str(cell.get("skill_version_id")))
            expected_refs.append(skill_id)
        except ValueError:
            errors.append(f"content review contract cell {index} skill id is invalid")
            skill_id = None
        raw_prior = cell.get("prior_review_ref")
        if raw_prior is not None:
            try:
                prior_refs.append(uuid.UUID(str(raw_prior)))
            except ValueError:
                errors.append(f"content review contract cell {index} prior id is invalid")
        try:
            uuid.UUID(str(cell.get("lineage_id")))
        except ValueError:
            errors.append(f"content review contract cell {index} lineage id is invalid")
        checks = cell.get("checks")
        if not isinstance(checks, dict) or set(checks) != set(REQUIRED_CHECKS):
            errors.append(f"content review contract cell {index} checks are malformed")
        else:
            for name in REQUIRED_CHECKS:
                check = checks.get(name)
                if (
                    not isinstance(check, dict)
                    or set(check) != {"passed", "evidence"}
                    or type(check.get("passed")) is not bool
                    or not _text(check.get("evidence"))
                ):
                    errors.append(
                        f"content review contract cell {index} check {name} is malformed"
                    )
        if skill_id == skill_version.artifact_id and slug == payload.get("slug"):
            selected.append(cell)
    if contract.input_refs != [*expected_refs, *prior_refs]:
        errors.append("content review contract input references do not match its leases")
    if len(selected) != 1:
        errors.append("content review contract does not contain one exact skill lease")
        return errors
    cell = selected[0]
    expected = {
        "skill_payload_sha256": payload.get("skill_payload_sha256"),
        "version": payload.get("version"),
        "role": payload.get("role"),
        "level": payload.get("level"),
        "reviewer_identity": payload.get("reviewer_identity"),
        "fixer_identity": payload.get("fixer_identity"),
        "lineage_id": payload.get("lineage_id"),
        "prior_review_ref": payload.get("prior_review_ref"),
        "checks": payload.get("checks"),
    }
    for key, value in expected.items():
        if cell.get(key) != value:
            errors.append(f"content review {key} does not match issued contract")
    for key in ("batch_id", "run_id", "phase", "prompt_version", "attempt"):
        if contract_payload.get(key) != payload.get(key):
            errors.append(f"content review {key} does not match issued contract")
    return errors


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
    if values["category"] and values["category"] not in FINDING_CATEGORIES:
        errors.append(f"finding {index} category is invalid")
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
    lineage_id: str,
    contract_artifact: Artifact,
    checks: dict,
    findings: Iterable[dict],
    prior_review: Artifact | None = None,
    agent_ready_claim: bool | None = None,
) -> Artifact:
    """Construct content-review evidence; never accept or return authoritative readiness."""
    if skill_version.artifact_type is not ArtifactType.SKILL_VERSION:
        raise ValueError("content review requires a skill_version artifact")
    if contract_artifact.artifact_type is not ArtifactType.GATE_DECISION:
        raise ValueError("content review requires an issued review batch contract")
    payload = skill_version.payload
    fingerprint = payload_fingerprint(payload)
    refs = [skill_version.artifact_id, contract_artifact.artifact_id]
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
        "lineage_id": lineage_id,
        "contract_artifact_id": str(contract_artifact.artifact_id),
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
    structural.extend(_review_contract_errors(artifact, skill_version, store))

    for facet in ("slug", "version", "role", "level"):
        if payload.get(facet) != skill_payload.get(facet):
            structural.append(f"{facet} does not match skill version")
    for key in ("prompt_version", "run_id", "batch_id", "reviewer_identity", "fixer_identity"):
        if not _text(payload.get(key)):
            structural.append(f"{key} is required")
    try:
        uuid.UUID(str(payload.get("lineage_id")))
    except ValueError:
        structural.append("lineage_id must be a UUID")
    phase = payload.get("phase")
    if phase == "review":
        unmet.append("latest content review is not an independent recheck")
        if not ADVERSARIAL_REVIEW_PROMPT.fullmatch(str(payload.get("prompt_version") or "")):
            structural.append("initial review prompt version is not calibrated P1 evidence")
    elif phase == "recheck" and not CALIBRATED_RECHECK_PROMPT.fullmatch(
        str(payload.get("prompt_version") or "")
    ):
        structural.append("recheck prompt version is not calibrated P5 evidence")
    elif phase != "recheck":
        structural.append("content review phase must be review or recheck")
    if (
        _text(payload.get("reviewer_identity"))
        and payload.get("reviewer_identity") == payload.get("fixer_identity")
    ):
        structural.append("reviewer and fixer identities are not independent")

    attempt = payload.get("attempt")
    if type(attempt) is not int or not 1 <= attempt <= MAX_REVIEW_ATTEMPTS:
        structural.append("attempt must be a positive integer")
    elif attempt == 1 and phase != "review":
        structural.append("attempt 1 must be an adversarial P1 review")
    elif phase == "recheck" and attempt < 2:
        structural.append("a P5 recheck requires a prior P1 review")
    prior_ref = payload.get("prior_review_ref")
    if attempt == 1:
        if prior_ref is not None or len(artifact.input_refs) != 2:
            structural.append("first attempt must not reference a prior review")
    elif type(attempt) is int and attempt > 1:
        if not isinstance(prior_ref, str) or len(artifact.input_refs) != 3:
            structural.append("recheck attempt must reference the prior attempt")
        elif str(artifact.input_refs[2]) != prior_ref:
            structural.append("prior review payload and input reference disagree")
        elif store is not None:
            prior = store.get(artifact.input_refs[2])
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
                if prior_payload.get("lineage_id") != payload.get("lineage_id"):
                    structural.append("prior review lineage_id does not match")
                for key in ("slug", "role", "level"):
                    if prior_payload.get(key) != payload.get(key):
                        structural.append(f"prior review {key} lineage does not match")
                same_version = (
                    bool(prior.input_refs)
                    and prior.input_refs[0] == skill_version.artifact_id
                )
                if same_version:
                    for key in ("skill_payload_sha256", "version"):
                        if prior_payload.get(key) != payload.get(key):
                            structural.append(f"prior review {key} lineage does not match")
                else:
                    prior_skill = (
                        store.get(prior.input_refs[0]) if prior.input_refs else None
                    )
                    if (
                        prior_skill is None
                        or prior_skill.artifact_type is not ArtifactType.SKILL_VERSION
                    ):
                        structural.append("prior review does not reference a skill version")
                    else:
                        previous = _semver(prior_payload.get("version"))
                        current = _semver(payload.get("version"))
                        if previous is None or current is None or current <= previous:
                            structural.append(
                                "cross-version review lineage requires a monotonic semver bump"
                            )
                        prior_skill_payload = (
                            prior_skill.payload if isinstance(prior_skill.payload, dict) else {}
                        )
                        if prior_skill.permissions_label != skill_version.permissions_label:
                            structural.append(
                                "cross-version review permissions label does not match"
                            )
                        if prior_skill_payload.get("function") != skill_payload.get("function"):
                            structural.append(
                                "cross-version review function facet does not match"
                            )
                        if prior_payload.get("skill_payload_sha256") != payload_fingerprint(
                            prior_skill_payload
                        ):
                            structural.append(
                                "prior review payload hash does not match its skill version"
                            )

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
        if len(seen_artifacts) >= MAX_REVIEW_ATTEMPTS:
            errors.append("content review lineage exceeds 64 attempts")
            break
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
        if store is None or len(current.input_refs) != 3:
            errors.append("review lineage cannot resolve its prior review")
            break
        prior = store.get(current.input_refs[2])
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
    lineage_errors.extend(_frozen_review_chain_errors(store, artifact))
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
    exact_candidates = [
        artifact for artifact in slug_candidates
        if artifact.input_refs and artifact.input_refs[0] == skill_version.artifact_id
    ]
    if not exact_candidates:
        latest = max(slug_candidates, key=lambda artifact: (
            artifact.timestamp_start, str(artifact.artifact_id),
        ))
        return Readiness(
            STALE, latest,
            ("no content review references the exact skill version and payload hash",),
        )
    exact_candidates.sort(
        key=lambda artifact: (
            artifact.payload.get("attempt")
            if isinstance(artifact.payload, dict) and type(artifact.payload.get("attempt")) is int
            else -1,
            artifact.timestamp_start,
            str(artifact.artifact_id),
        )
    )
    latest = exact_candidates[-1]
    lineage_id = latest.payload.get("lineage_id")
    lineage_errors: list[str] = []
    lineages = {
        artifact.payload.get("lineage_id") for artifact in slug_candidates
        if isinstance(artifact.payload, dict)
    }
    if len(lineages) != 1 or lineage_id not in lineages:
        lineage_errors.append("content review slug has multiple or invalid lineage identities")
    lineage_candidates = [
        artifact for artifact in slug_candidates
        if isinstance(artifact.payload, dict)
        and artifact.payload.get("lineage_id") == lineage_id
    ]
    by_attempt: dict[int, list[Artifact]] = {}
    for candidate in lineage_candidates:
        candidate_payload = candidate.payload if isinstance(candidate.payload, dict) else {}
        attempt = candidate_payload.get("attempt")
        if type(attempt) is not int or not 1 <= attempt <= MAX_REVIEW_ATTEMPTS:
            lineage_errors.append("content review lineage contains an invalid attempt")
            continue
        by_attempt.setdefault(attempt, []).append(candidate)
    for attempt, rows in sorted(by_attempt.items()):
        if len(rows) != 1:
            lineage_errors.append(f"content review lineage has duplicate attempt {attempt}")
    for candidate in lineage_candidates:
        referenced_skill = (
            store.get(candidate.input_refs[0]) if candidate.input_refs else None
        )
        if (
            referenced_skill is None
            or referenced_skill.artifact_type is not ArtifactType.SKILL_VERSION
        ):
            lineage_errors.append("content review does not reference a stored skill version")
            continue
        structural, _unmet, _findings = _review_validation(
            candidate, referenced_skill, store,
        )
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
                len(current[0].input_refs) != 3
                or current[0].input_refs[2] != prior[0].artifact_id
            ):
                lineage_errors.append(
                    f"content review attempt {attempt} does not reference attempt {attempt - 1}"
                )
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
    structural.extend(_frozen_review_chain_errors(store, review))
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


def _frozen_review_chain_errors(store: ArtifactStore, review: Artifact) -> list[str]:
    """Revalidate every immutable ancestor and require export-private one-cell leases.

    The live readiness path validates every slug candidate, but a published badge is intentionally
    bound to one historical head.  Replaying that frozen head must therefore validate its complete
    chain rather than trusting that ancestors happened to be valid when a later row was written.
    A multi-cell contract is useful for review coordination but is not safe publication evidence:
    exporting it would reveal unrelated, possibly unpublished sibling cells.
    """
    errors: list[str] = []
    current = review
    visited: set[uuid.UUID] = set()
    first = True
    while True:
        if len(visited) >= MAX_REVIEW_ATTEMPTS:
            errors.append("content review lineage exceeds 64 attempts")
            break
        if current.artifact_id in visited:
            errors.append("content review lineage contains a cycle")
            break
        visited.add(current.artifact_id)
        if not current.input_refs:
            errors.append("content review does not reference a stored skill version")
            break
        referenced_skill = store.get(current.input_refs[0])
        if (
            referenced_skill is None
            or referenced_skill.artifact_type is not ArtifactType.SKILL_VERSION
        ):
            errors.append("content review does not reference a stored skill version")
            break
        if not first:
            ancestor_errors, _ancestor_unmet, _ancestor_findings = _review_validation(
                current, referenced_skill, store,
            )
            errors.extend(ancestor_errors)
        first = False
        if len(current.input_refs) < 2:
            errors.append("content review does not reference its issued contract")
            break
        contract = store.get(current.input_refs[1])
        cells = contract.payload.get("cells") if (
            contract is not None
            and contract.artifact_type is ArtifactType.GATE_DECISION
            and isinstance(contract.payload, dict)
        ) else None
        if not isinstance(cells, list) or len(cells) != 1:
            errors.append("publication review contracts must contain exactly one skill lease")
        payload = current.payload if isinstance(current.payload, dict) else {}
        prior_ref = payload.get("prior_review_ref")
        if prior_ref is None:
            break
        if len(current.input_refs) != 3 or str(current.input_refs[2]) != prior_ref:
            errors.append("review lineage cannot resolve its prior review")
            break
        prior = store.get(current.input_refs[2])
        if prior is None or prior.artifact_type is not ArtifactType.REVIEW:
            errors.append("prior review artifact was not found")
            break
        current = prior
    return errors


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
