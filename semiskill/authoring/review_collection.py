"""Strict, batch-atomic collection of independent content-review results.

The collector treats agent output as untrusted data. It validates the complete batch against an
orchestrator-supplied set of exact skill-version artifacts before appending anything. Unknown or
missing slugs, mixed attempts/runs, stale hashes, malformed booleans, identity reuse, and broken
lineage reject the whole batch.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.gate import (
    ADVERSARIAL_REVIEW_PROMPT,
    CALIBRATED_RECHECK_PROMPT,
    MAX_REVIEW_ATTEMPTS,
    REQUIRED_CHECKS,
    canonical_review_authentication_context,
    make_content_review,
    validate_content_review,
)
from semiskill.capture.intake import payload_fingerprint

MAX_BATCH_SIZE = 10
REVIEW_BATCH_CONTRACT_SCHEMA = "semiskill.review-batch/v1"


class BatchRejected(ValueError):
    """No review artifact was appended because the batch contract was violated."""


@dataclass(frozen=True, slots=True)
class ReviewCellContract:
    """Coordinator-owned evidence and identities for one exact reviewed version."""

    skill_version: Artifact
    reviewer_identity: str
    fixer_identity: str
    checks: Mapping[str, object]
    lineage_id: str
    prior_review_ref: uuid.UUID | None = None


@dataclass(frozen=True, slots=True)
class ReviewBatchContract:
    """One immutable one-skill review lease; agent output cannot widen these fields."""

    batch_id: str
    run_id: str
    phase: str
    prompt_version: str
    attempt: int
    cells: Mapping[str, ReviewCellContract]
    issuer_identity: str
    authentication_context: Mapping[str, object]
    contract_artifact: Artifact | None = None


def _require_exact(result: dict, skill_version: Artifact, key: str, expected) -> None:
    if result.get(key) != expected:
        raise BatchRejected(f"{result.get('slug')}: {key} does not match expected skill version")


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _semver(value: object) -> tuple[int, int, int] | None:
    parts = str(value or "").split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        return None
    return tuple(int(part) for part in parts)


def _trusted_checks(value: Mapping[str, object], *, slug: str) -> dict:
    if not isinstance(value, Mapping) or set(value) != set(REQUIRED_CHECKS):
        raise BatchRejected(f"{slug}: contract checks must contain the exact required check set")
    checks: dict[str, dict] = {}
    for name in REQUIRED_CHECKS:
        check = value.get(name)
        if not isinstance(check, Mapping) or set(check) != {"passed", "evidence"}:
            raise BatchRejected(f"{slug}: contract check {name} is malformed")
        if type(check.get("passed")) is not bool:
            raise BatchRejected(f"{slug}: contract check {name} passed must be a boolean")
        if not _text(check.get("evidence")):
            raise BatchRejected(f"{slug}: contract check {name} evidence is required")
        checks[name] = {"passed": check["passed"], "evidence": check["evidence"]}
    return checks


def _validate_contract_fields(contract: ReviewBatchContract) -> dict[str, ReviewCellContract]:
    if not isinstance(contract, ReviewBatchContract):
        raise BatchRejected("an orchestrator-issued ReviewBatchContract is required")
    if not _text(contract.batch_id) or not _text(contract.run_id):
        raise BatchRejected("contract batch_id and run_id are required")
    if contract.phase not in {"review", "recheck"}:
        raise BatchRejected("contract phase must be review or recheck")
    if not _text(contract.prompt_version):
        raise BatchRejected("contract prompt_version is required")
    if not _text(contract.issuer_identity):
        raise BatchRejected("contract issuer_identity is required")
    if canonical_review_authentication_context(contract.authentication_context) is None:
        raise BatchRejected(
            "contract authentication_context must contain only provider and subject_sha256"
        )
    if (
        type(contract.attempt) is not int
        or not 1 <= contract.attempt <= MAX_REVIEW_ATTEMPTS
    ):
        raise BatchRejected(f"contract attempt must be between 1 and {MAX_REVIEW_ATTEMPTS}")
    if contract.phase == "review" and not ADVERSARIAL_REVIEW_PROMPT.fullmatch(
        contract.prompt_version
    ):
        raise BatchRejected("review contracts require a calibrated P1 prompt version")
    if contract.phase == "recheck" and not CALIBRATED_RECHECK_PROMPT.fullmatch(
        contract.prompt_version
    ):
        raise BatchRejected("recheck contracts require a calibrated P5 prompt version")
    if contract.attempt == 1 and contract.phase != "review":
        raise BatchRejected("attempt 1 must be an adversarial P1 review")
    if contract.phase == "recheck" and contract.attempt < 2:
        raise BatchRejected("a P5 recheck requires a prior P1 review")
    cells = dict(contract.cells) if isinstance(contract.cells, Mapping) else {}
    if not cells:
        raise BatchRejected("batch contract contains no expected slugs")
    if len(cells) != 1:
        raise BatchRejected(
            "review contracts contain exactly one skill; orchestrator batches may group up to "
            f"{MAX_BATCH_SIZE} independent contracts"
        )
    reviewers: list[str] = []
    skill_ids: list[uuid.UUID] = []
    for slug, cell in cells.items():
        if not _text(slug) or not isinstance(cell, ReviewCellContract):
            raise BatchRejected("contract cells require a slug and ReviewCellContract")
        version = cell.skill_version
        if not isinstance(version, Artifact):
            raise BatchRejected(f"{slug}: contract does not reference an artifact")
        if version.artifact_type is not ArtifactType.SKILL_VERSION:
            raise BatchRejected(f"{slug}: contract does not reference a skill version")
        if not isinstance(version.payload, dict) or version.payload.get("slug") != slug:
            raise BatchRejected(f"{slug}: contract slug does not match skill version")
        if not _text(cell.reviewer_identity) or not _text(cell.fixer_identity):
            raise BatchRejected(f"{slug}: contract reviewer and fixer identities are required")
        if cell.reviewer_identity == cell.fixer_identity:
            raise BatchRejected(f"{slug}: contract reviewer and fixer identities are not independent")
        if not _text(cell.lineage_id):
            raise BatchRejected(f"{slug}: contract lineage_id is required")
        try:
            uuid.UUID(cell.lineage_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise BatchRejected(f"{slug}: contract lineage_id must be a UUID") from exc
        if cell.prior_review_ref is not None and not isinstance(cell.prior_review_ref, uuid.UUID):
            raise BatchRejected(f"{slug}: contract prior review reference must be a UUID")
        if contract.attempt == 1 and cell.prior_review_ref is not None:
            raise BatchRejected(f"{slug}: attempt 1 cannot reference a prior review")
        if contract.attempt > 1 and cell.prior_review_ref is None:
            raise BatchRejected(f"{slug}: later attempts require the exact prior review")
        reviewers.append(cell.reviewer_identity)
        skill_ids.append(version.artifact_id)
        _trusted_checks(cell.checks, slug=slug)
    if len(reviewers) != len(set(reviewers)):
        raise BatchRejected("contract reviewer identities must be unique within a batch")
    if len(skill_ids) != len(set(skill_ids)):
        raise BatchRejected("contract skill-version identities must be unique within a batch")
    return cells


def _contract_payload(contract: ReviewBatchContract) -> dict:
    cells = _validate_contract_fields(contract)
    return {
        "schema_version": REVIEW_BATCH_CONTRACT_SCHEMA,
        "batch_id": contract.batch_id,
        "run_id": contract.run_id,
        "phase": contract.phase,
        "prompt_version": contract.prompt_version,
        "attempt": contract.attempt,
        "issuer_identity": contract.issuer_identity,
        "authentication_context": canonical_review_authentication_context(
            contract.authentication_context
        ),
        "cells": [
            {
                "slug": slug,
                "skill_version_id": str(cell.skill_version.artifact_id),
                "skill_payload_sha256": payload_fingerprint(cell.skill_version.payload),
                "version": cell.skill_version.payload.get("version"),
                "role": cell.skill_version.payload.get("role"),
                "level": cell.skill_version.payload.get("level"),
                "reviewer_identity": cell.reviewer_identity,
                "fixer_identity": cell.fixer_identity,
                "lineage_id": cell.lineage_id,
                "prior_review_ref": (
                    str(cell.prior_review_ref) if cell.prior_review_ref is not None else None
                ),
                "checks": _trusted_checks(cell.checks, slug=slug),
            }
            for slug, cell in sorted(cells.items())
        ],
    }


def _contract_digest(payload: dict) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _contract_input_refs(contract: ReviewBatchContract) -> list[uuid.UUID]:
    cells = _validate_contract_fields(contract)
    skill_refs = [cells[slug].skill_version.artifact_id for slug in sorted(cells)]
    prior_refs = [
        cells[slug].prior_review_ref for slug in sorted(cells)
        if cells[slug].prior_review_ref is not None
    ]
    return [*skill_refs, *prior_refs]


def _same_contract_envelope(candidate: Artifact, persisted: Artifact) -> bool:
    """Compare every authoritative contract field except retry-generated ID/timestamps."""
    fields = (
        "artifact_type",
        "source_system",
        "actor",
        "actor_kind",
        "input_refs",
        "output_refs",
        "permissions_label",
        "objective_tag",
        "ground_truth_ref",
        "eval_score",
        "rollback_ref",
        "cost_usd",
        "corrects_ref",
        "payload",
    )
    return isinstance(persisted, Artifact) and all(
        getattr(candidate, field) == getattr(persisted, field) for field in fields
    )


def issue_review_batch_contract(
    *,
    store: ArtifactStore,
    contract: ReviewBatchContract,
) -> ReviewBatchContract:
    """Append one immutable coordinator lease before any untrusted review output is accepted."""
    if contract.contract_artifact is not None:
        raise BatchRejected("review batch contract has already been issued")
    payload = _contract_payload(contract)
    identity_reader = getattr(store, "review_coordinator_authentication_context", None)
    if callable(identity_reader):
        try:
            expected_authentication = identity_reader()
        except (RuntimeError, ValueError) as exc:
            raise BatchRejected("review coordinator authentication is unavailable") from exc
        if payload["authentication_context"] != expected_authentication:
            raise BatchRejected(
                "review contract authentication_context does not match the coordinator login"
            )
    labels = {cell.skill_version.permissions_label for cell in contract.cells.values()}
    if len(labels) != 1:
        raise BatchRejected("review batch contract cannot mix permission labels")
    artifact = Artifact.new(
        artifact_type=ArtifactType.GATE_DECISION,
        source_system=SourceSystem.CLI,
        actor=contract.issuer_identity,
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        input_refs=_contract_input_refs(contract),
        payload=payload,
    )
    artifact = replace(
        artifact,
        permissions_label=next(iter(labels)),
        objective_tag="safety",
        ground_truth_ref=_contract_digest(payload),
    )
    for slug, cell in contract.cells.items():
        skill_completed = cell.skill_version.timestamp_end or cell.skill_version.timestamp_start
        if skill_completed > artifact.timestamp_start:
            raise BatchRejected(f"{slug}: review contract predates the skill version")
        if cell.prior_review_ref is not None:
            prior = store.get(cell.prior_review_ref)
            if (
                prior is None
                or prior.artifact_type is not ArtifactType.REVIEW
                or not isinstance(prior.payload, dict)
                or prior.payload.get("review_kind") != "content_review"
                or prior.payload.get("schema_version") != 2
                or prior.payload.get("lineage_id") != cell.lineage_id
                or prior.payload.get("slug") != slug
            ):
                raise BatchRejected(f"{slug}: prior review is not a canonical lineage head")
            if prior.payload.get("attempt") != contract.attempt - 1:
                raise BatchRejected(f"{slug}: attempt must increment prior review by exactly one")
            prior_completed = prior.timestamp_end or prior.timestamp_start
            if prior_completed > artifact.timestamp_start:
                raise BatchRejected(f"{slug}: review contract predates its prior review")
            prior_skill = store.get(prior.input_refs[0]) if prior.input_refs else None
            current_payload = cell.skill_version.payload
            prior_payload = prior_skill.payload if (
                prior_skill is not None
                and prior_skill.artifact_type is ArtifactType.SKILL_VERSION
                and isinstance(prior_skill.payload, dict)
            ) else {}
            if (
                not prior_payload
                or prior_skill.permissions_label != cell.skill_version.permissions_label
                or prior_payload.get("function") != current_payload.get("function")
                or prior.payload.get("role") != current_payload.get("role")
                or prior.payload.get("level") != current_payload.get("level")
                or prior.payload.get("skill_payload_sha256")
                    != payload_fingerprint(prior_payload)
            ):
                raise BatchRejected(f"{slug}: prior review facets or payload are inconsistent")
            if prior_skill.artifact_id != cell.skill_version.artifact_id:
                previous_version = _semver(prior.payload.get("version"))
                current_version = _semver(current_payload.get("version"))
                if (
                    previous_version is None
                    or current_version is None
                    or current_version <= previous_version
                ):
                    raise BatchRejected(
                        f"{slug}: cross-version review requires a monotonic semver bump"
                    )
    actuator = getattr(store, "append_review_contract", None)
    if not callable(actuator):
        raise BatchRejected("verified review-contract actuator is unavailable")
    persisted = actuator(artifact)
    if not _same_contract_envelope(artifact, persisted):
        raise BatchRejected("review contract retry returned a semantically different artifact")
    if store.get(persisted.artifact_id) != persisted:
        raise BatchRejected("review contract actuator returned an unstored artifact")
    exact_verifier = getattr(store, "review_contract_verified", None)
    verified_reader = getattr(store, "verified_review_contract_ids", None)
    verified = (
        exact_verifier(persisted.artifact_id, persisted.permissions_label)
        if callable(exact_verifier)
        else callable(verified_reader) and persisted.artifact_id in verified_reader()
    )
    if not verified:
        raise BatchRejected("review contract actuator returned an unverified artifact")
    return replace(contract, contract_artifact=persisted)


def review_batch_contract_document(contract: ReviewBatchContract) -> dict:
    """Return the exact portable lease document; collection still verifies the stored artifact."""
    if contract.contract_artifact is None:
        raise BatchRejected("review batch contract has not been issued")
    return {
        "contract_artifact_id": str(contract.contract_artifact.artifact_id),
        **_contract_payload(contract),
    }


def _validate_contract(
    store: ArtifactStore,
    contract: ReviewBatchContract,
) -> dict[str, ReviewCellContract]:
    cells = _validate_contract_fields(contract)
    artifact = contract.contract_artifact
    if artifact is None:
        raise BatchRejected("an issued review batch contract artifact is required")
    stored = store.get(artifact.artifact_id)
    if stored != artifact:
        raise BatchRejected("review batch contract artifact is not the stored immutable lease")
    exact_verifier = getattr(store, "review_contract_verified", None)
    verified_reader = getattr(store, "verified_review_contract_ids", None)
    verified = (
        exact_verifier(artifact.artifact_id, artifact.permissions_label)
        if callable(exact_verifier)
        else callable(verified_reader) and artifact.artifact_id in verified_reader()
    )
    if not verified:
        raise BatchRejected("review batch contract was not issued by the verified actuator")
    payload = _contract_payload(contract)
    if (
        artifact.artifact_type is not ArtifactType.GATE_DECISION
        or artifact.source_system is not SourceSystem.CLI
        or artifact.actor_kind is not ActorKind.SERVICE_ACCOUNT
        or artifact.actor != contract.issuer_identity
        or artifact.objective_tag != "safety"
        or artifact.payload != payload
        or artifact.input_refs != _contract_input_refs(contract)
        or artifact.ground_truth_ref != _contract_digest(payload)
    ):
        raise BatchRejected("review batch contract artifact failed coordinator validation")
    return cells


def _prepare_review_batch(
    *,
    store: ArtifactStore,
    contract: ReviewBatchContract,
    results: Sequence[dict],
    existing_reviews: Sequence[Artifact] | None = None,
) -> list[Artifact]:
    """Validate one issued lease and return its uncommitted canonical review artifact."""
    cells = _validate_contract(store, contract)
    contract_artifact = contract.contract_artifact
    assert contract_artifact is not None  # established by _validate_contract
    expected = {slug: cell.skill_version for slug, cell in cells.items()}
    rows = list(results)
    if not expected:
        raise BatchRejected("batch contract contains no expected slugs")
    if len(expected) > MAX_BATCH_SIZE or len(rows) > MAX_BATCH_SIZE:
        raise BatchRejected(f"review batches are limited to {MAX_BATCH_SIZE} skills")
    if not all(isinstance(row, dict) for row in rows):
        raise BatchRejected("every review result must be an object")

    slugs = [row.get("slug") for row in rows]
    if any(not isinstance(slug, str) or not slug for slug in slugs):
        raise BatchRejected("every review result requires a slug")
    duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    if duplicates:
        raise BatchRejected(f"duplicate slugs in results: {', '.join(duplicates)}")
    unknown = sorted(set(slugs) - set(expected))
    missing = sorted(set(expected) - set(slugs))
    if unknown:
        raise BatchRejected(f"unknown slugs in results: {', '.join(unknown)}")
    if missing:
        raise BatchRejected(f"missing slugs in results: {', '.join(missing)}")

    artifacts: list[Artifact] = []
    for result in rows:
        slug = result["slug"]
        skill_version = expected[slug]
        cell = cells[slug]
        phase = contract.phase
        for key, value in (
            ("phase", contract.phase),
            ("prompt_version", contract.prompt_version),
            ("run_id", contract.run_id),
            ("batch_id", contract.batch_id),
            ("attempt", contract.attempt),
            ("reviewer_identity", cell.reviewer_identity),
            ("fixer_identity", cell.fixer_identity),
            ("lineage_id", cell.lineage_id),
            ("contract_artifact_id", str(contract_artifact.artifact_id)),
            ("prior_review_ref", str(cell.prior_review_ref) if cell.prior_review_ref else None),
        ):
            if result.get(key) != value:
                raise BatchRejected(f"{slug}: {key} does not match the issued batch contract")
        _require_exact(result, skill_version, "skill_version_id", str(skill_version.artifact_id))
        if result.get("skill_payload_sha256") != payload_fingerprint(skill_version.payload):
            raise BatchRejected(f"{slug}: payload hash does not match expected skill version")
        for key in ("version", "role", "level"):
            _require_exact(result, skill_version, key, skill_version.payload.get(key))

        checks = _trusted_checks(cell.checks, slug=slug)
        if result.get("checks") != checks:
            raise BatchRejected(f"{slug}: checks do not match the issued batch contract")
        if "ready" in result and type(result["ready"]) is not bool:
            raise BatchRejected(f"{slug}: agent ready claim must be a boolean when present")
        if not isinstance(result.get("findings"), list):
            raise BatchRejected(f"{slug}: findings must be an array")

        attempt = contract.attempt
        prior = None
        if cell.prior_review_ref is not None:
            prior = store.get(cell.prior_review_ref)
            if prior is None:
                raise BatchRejected(f"{slug}: contract prior review artifact was not found")

        review_history = (
            list(existing_reviews)
            if existing_reviews is not None
            else store.by_type(ArtifactType.REVIEW)
        )
        existing = [
            artifact for artifact in review_history
            if isinstance(artifact.payload, dict)
            and artifact.payload.get("review_kind") == "content_review"
            and artifact.payload.get("slug") == slug
        ]
        foreign_lineages = {
            artifact.payload.get("lineage_id") for artifact in existing
            if artifact.payload.get("lineage_id") != cell.lineage_id
        }
        if foreign_lineages:
            raise BatchRejected(f"{slug}: content review lineage_id does not match prior history")
        existing_attempts = [artifact.payload.get("attempt") for artifact in existing]
        if any(type(value) is not int or value < 1 for value in existing_attempts):
            raise BatchRejected(f"{slug}: existing review lineage has an invalid attempt")
        if attempt in existing_attempts:
            raise BatchRejected(f"{slug}: content review attempt {attempt} already exists")
        if attempt == 1 and existing:
            raise BatchRejected(f"{slug}: content review lineage already has a first attempt")
        if attempt > 1:
            heads = [
                artifact for artifact in existing
                if artifact.payload.get("attempt") == attempt - 1
            ]
            if len(heads) != 1 or prior is None or prior.artifact_id != heads[0].artifact_id:
                raise BatchRejected(
                    f"{slug}: attempt must increment prior review by exactly one unique round"
                )
            if sorted(existing_attempts) != list(range(1, attempt)):
                raise BatchRejected(f"{slug}: existing review lineage is malformed or branched")
            prior_payload = prior.payload if isinstance(prior.payload, dict) else {}
            if prior_payload.get("lineage_id") != cell.lineage_id:
                raise BatchRejected(f"{slug}: prior review lineage_id does not match contract")

        artifact = make_content_review(
            skill_version=skill_version,
            phase=contract.phase,
            prompt_version=contract.prompt_version,
            run_id=contract.run_id,
            batch_id=contract.batch_id,
            attempt=attempt,
            reviewer_identity=cell.reviewer_identity,
            fixer_identity=cell.fixer_identity,
            lineage_id=cell.lineage_id,
            contract_artifact=contract_artifact,
            checks=checks,
            findings=result.get("findings"),
            prior_review=prior,
            agent_ready_claim=result.get("ready") if "ready" in result else None,
        )
        permitted_unmet = (
            {"latest content review is not an independent recheck"}
            if phase == "review" else set()
        )
        errors = [
            error
            for error in validate_content_review(store, artifact, skill_version)
            if error not in permitted_unmet
            and (not error.startswith("check ") or not error.endswith(" did not pass"))
        ]
        if errors:
            raise BatchRejected(f"{slug}: " + "; ".join(errors))
        artifacts.append(artifact)

    return artifacts


def collect_review_batch(
    *,
    store: ArtifactStore,
    contract: ReviewBatchContract,
    results: Sequence[dict],
) -> list[Artifact]:
    """Validate and atomically append the result for one independent one-skill lease."""
    artifacts = _prepare_review_batch(store=store, contract=contract, results=results)
    return store.append_many(artifacts)


def collect_review_contract_batch(
    *,
    store: ArtifactStore,
    contracts: Sequence[ReviewBatchContract],
    results: Sequence[dict],
) -> list[Artifact]:
    """Atomically collect up to ten independent one-skill review leases.

    Every lease has a distinct run and reviewer context, while the shared ``batch_id`` makes the
    coordinator's collection boundary explicit.  All contracts and results are validated before
    the store receives one ``append_many`` call.  A malformed or missing sibling therefore creates
    no completed review state for any skill in the orchestrator batch.
    """
    leases = list(contracts)
    rows = list(results)
    if not leases:
        raise BatchRejected("orchestrator batch contains no review contracts")
    if len(leases) > MAX_BATCH_SIZE or len(rows) > MAX_BATCH_SIZE:
        raise BatchRejected(f"review batches are limited to {MAX_BATCH_SIZE} skills")
    if not all(isinstance(contract, ReviewBatchContract) for contract in leases):
        raise BatchRejected("every orchestrator batch entry must be a review contract")
    if not all(isinstance(row, dict) for row in rows):
        raise BatchRejected("every review result must be an object")

    validated: list[tuple[ReviewBatchContract, str, ReviewCellContract]] = []
    contract_ids: list[uuid.UUID] = []
    for contract in leases:
        cells = _validate_contract(store, contract)
        slug, cell = next(iter(cells.items()))
        assert contract.contract_artifact is not None  # established by _validate_contract
        validated.append((contract, slug, cell))
        contract_ids.append(contract.contract_artifact.artifact_id)

    def _one_value(name: str, values: Sequence[object]) -> object:
        first = values[0]
        if any(value != first for value in values[1:]):
            raise BatchRejected(f"orchestrator contracts must share one {name}")
        return first

    _one_value("batch_id", [contract.batch_id for contract, _, _ in validated])
    _one_value("phase", [contract.phase for contract, _, _ in validated])
    _one_value("prompt_version", [contract.prompt_version for contract, _, _ in validated])
    _one_value("attempt", [contract.attempt for contract, _, _ in validated])
    _one_value("issuer_identity", [contract.issuer_identity for contract, _, _ in validated])
    _one_value(
        "authentication_context",
        [dict(contract.authentication_context) for contract, _, _ in validated],
    )
    _one_value(
        "permissions_label",
        [cell.skill_version.permissions_label for _, _, cell in validated],
    )

    slugs = [slug for _, slug, _ in validated]
    skill_ids = [cell.skill_version.artifact_id for _, _, cell in validated]
    reviewers = [cell.reviewer_identity for _, _, cell in validated]
    lineages = [cell.lineage_id for _, _, cell in validated]
    run_ids = [contract.run_id for contract, _, _ in validated]
    for label, values in (
        ("contract artifacts", contract_ids),
        ("slugs", slugs),
        ("skill versions", skill_ids),
        ("reviewer identities", reviewers),
        ("lineage IDs", lineages),
        ("run IDs", run_ids),
    ):
        if len(values) != len(set(values)):
            raise BatchRejected(f"orchestrator batch requires unique {label}")

    result_slugs = [row.get("slug") for row in rows]
    if any(not isinstance(slug, str) or not slug for slug in result_slugs):
        raise BatchRejected("every review result requires a slug")
    duplicates = sorted({slug for slug in result_slugs if result_slugs.count(slug) > 1})
    if duplicates:
        raise BatchRejected(f"duplicate slugs in results: {', '.join(duplicates)}")
    unknown = sorted(set(result_slugs) - set(slugs))
    missing = sorted(set(slugs) - set(result_slugs))
    if unknown:
        raise BatchRejected(f"unknown slugs in results: {', '.join(unknown)}")
    if missing:
        raise BatchRejected(f"missing slugs in results: {', '.join(missing)}")
    results_by_slug = {row["slug"]: row for row in rows}

    review_history = store.by_type(ArtifactType.REVIEW)
    pending: list[Artifact] = []
    for contract, slug, _ in validated:
        pending.extend(
            _prepare_review_batch(
                store=store,
                contract=contract,
                results=[results_by_slug[slug]],
                existing_reviews=review_history,
            )
        )
    return store.append_many(pending)


def import_legacy_review_files(
    *,
    store: ArtifactStore,
    review_files: Sequence[str | Path],
    archive_root: str | Path,
) -> list[Artifact]:
    """Import raw REVIEW.json files as unbound provenance, then archive only after commit.

    Legacy ``ready`` claims and static agent labels are retained verbatim for audit but receive no
    skill-version input reference and therefore can never satisfy canonical readiness.
    """
    sources = [Path(path) for path in review_files]
    existing_hashes = {
        artifact.payload.get("legacy_source_sha256")
        for artifact in store.by_type(ArtifactType.REVIEW)
        if artifact.payload.get("review_kind") == "content_review_legacy"
    }
    pending: list[Artifact] = []
    moves: list[tuple[Path, Path]] = []
    seen: set[str] = set()
    root = Path(archive_root)

    for source in sources:
        if source.name.lower() != "review.json":
            raise BatchRejected(f"legacy review filename must be REVIEW.json: {source}")
        try:
            raw_bytes = source.read_bytes()
            raw_record = json.loads(raw_bytes.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BatchRejected(f"legacy review is unreadable: {source}") from exc
        if not isinstance(raw_record, dict):
            raise BatchRejected(f"legacy review must contain an object: {source}")
        slug = raw_record.get("slug") or source.parent.name
        if not isinstance(slug, str) or not slug or slug != source.parent.name:
            raise BatchRejected(f"legacy review slug does not match directory: {source}")
        digest = hashlib.sha256(raw_bytes).hexdigest()
        if digest in seen:
            raise BatchRejected(f"legacy lineage collision for source hash {digest}")
        seen.add(digest)
        destination = root / slug / f"{digest}.json"
        if destination.exists():
            raise BatchRejected(f"legacy archive destination already exists: {destination}")
        moves.append((source, destination))
        if digest in existing_hashes:
            continue
        artifact = Artifact.new(
            artifact_type=ArtifactType.REVIEW,
            source_system=SourceSystem.CLI,
            actor="legacy-review-import",
            actor_kind=ActorKind.SERVICE_ACCOUNT,
            payload={
                "review_kind": "content_review_legacy",
                "schema_version": 0,
                "legacy_unbound": True,
                "legacy_source_path": source.as_posix(),
                "legacy_source_sha256": digest,
                "slug": slug,
                "raw_record": raw_record,
            },
        )
        pending.append(replace(artifact, objective_tag="safety"))

    committed = store.append_many(pending) if pending else []
    for source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.replace(destination)
    return committed
