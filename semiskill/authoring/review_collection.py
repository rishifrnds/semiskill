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
from dataclasses import replace
from pathlib import Path

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.gate import make_content_review, validate_content_review
from semiskill.capture.intake import payload_fingerprint

MAX_BATCH_SIZE = 10


class BatchRejected(ValueError):
    """No review artifact was appended because the batch contract was violated."""


def _uniform(results: Sequence[dict], key: str) -> None:
    values = {result.get(key) for result in results}
    if len(values) != 1:
        raise BatchRejected(f"mixed {key} values in one batch")


def _require_exact(result: dict, skill_version: Artifact, key: str, expected) -> None:
    if result.get(key) != expected:
        raise BatchRejected(f"{result.get('slug')}: {key} does not match expected skill version")


def collect_review_batch(
    *,
    store: ArtifactStore,
    skill_versions: Mapping[str, Artifact],
    results: Sequence[dict],
) -> list[Artifact]:
    """Validate all results, then append all canonical review artifacts in one transaction."""
    expected = dict(skill_versions)
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

    for key in ("run_id", "batch_id", "attempt", "prompt_version"):
        _uniform(rows, key)
    reviewers = [row.get("reviewer_identity") for row in rows]
    if any(not isinstance(identity, str) or not identity.strip() for identity in reviewers):
        raise BatchRejected("every recheck requires a runtime-issued reviewer identity")
    if len(set(reviewers)) != len(reviewers):
        raise BatchRejected("reviewer identities must be unique within a batch")

    artifacts: list[Artifact] = []
    for result in rows:
        slug = result["slug"]
        skill_version = expected[slug]
        if result.get("phase") != "recheck":
            raise BatchRejected(f"{slug}: missing independent recheck result")
        _require_exact(result, skill_version, "skill_version_id", str(skill_version.artifact_id))
        if result.get("skill_payload_sha256") != payload_fingerprint(skill_version.payload):
            raise BatchRejected(f"{slug}: payload hash does not match expected skill version")
        for key in ("version", "role", "level"):
            _require_exact(result, skill_version, key, skill_version.payload.get(key))

        checks = result.get("checks")
        if not isinstance(checks, dict):
            raise BatchRejected(f"{slug}: checks must be an object")
        for name, check in checks.items():
            if isinstance(check, dict) and "passed" in check and type(check["passed"]) is not bool:
                raise BatchRejected(f"{slug}: check {name} passed must be a boolean")
        if "ready" in result and type(result["ready"]) is not bool:
            raise BatchRejected(f"{slug}: agent ready claim must be a boolean when present")
        if not isinstance(result.get("findings"), list):
            raise BatchRejected(f"{slug}: findings must be an array")

        attempt = result.get("attempt")
        if type(attempt) is not int or attempt < 1:
            raise BatchRejected(f"{slug}: attempt must be a positive integer")
        prior = None
        prior_ref = result.get("prior_review_ref")
        if prior_ref is not None:
            try:
                prior_id = uuid.UUID(str(prior_ref))
            except (ValueError, TypeError, AttributeError) as exc:
                raise BatchRejected(f"{slug}: prior review reference is not a UUID") from exc
            prior = store.get(prior_id)
            if prior is None:
                raise BatchRejected(f"{slug}: prior review artifact was not found")

        artifact = make_content_review(
            skill_version=skill_version,
            phase=result["phase"],
            prompt_version=result.get("prompt_version"),
            run_id=result.get("run_id"),
            batch_id=result.get("batch_id"),
            attempt=attempt,
            reviewer_identity=result.get("reviewer_identity"),
            fixer_identity=result.get("fixer_identity"),
            checks=checks,
            findings=result.get("findings"),
            prior_review=prior,
            agent_ready_claim=result.get("ready") if "ready" in result else None,
        )
        errors = [
            error
            for error in validate_content_review(store, artifact, skill_version)
            if not error.startswith("check ") or not error.endswith(" did not pass")
        ]
        if errors:
            raise BatchRejected(f"{slug}: " + "; ".join(errors))
        artifacts.append(artifact)

    return store.append_many(artifacts)


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
