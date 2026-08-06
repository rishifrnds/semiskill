"""Strict collector for canonical content reviews and legacy-review migration.

Canonical batch (all-or-nothing, maximum 10 independent one-skill contracts)::

    python tools/collect_wave.py --contract contract-a.json --contract contract-b.json \
        --results p5-results.json

Legacy import (non-authoritative provenance, followed by archive)::

    python tools/collect_wave.py --legacy-import

The contract is produced by the orchestrator and names exact ``skill_version`` artifact IDs. Agent
results cannot add slugs, change hashes/facets, invent runtime identities, or mix attempts. No
result is written back into a skill directory.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from semiskill.artifacts.schema import ArtifactType  # noqa: E402
from semiskill.artifacts.store import PostgresArtifactStore  # noqa: E402
from semiskill.authoring.review_collection import (  # noqa: E402
    MAX_BATCH_SIZE,
    BatchRejected,
    ReviewBatchContract,
    ReviewCellContract,
    collect_review_contract_batch,
    import_legacy_review_files,
)
from semiskill.capture.intake import payload_fingerprint  # noqa: E402
from semiskill.config import Config  # noqa: E402


def _load_object(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BatchRejected(f"cannot parse JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BatchRejected(f"expected a JSON object in {path}")
    return value


def load_results(path: Path) -> list[dict]:
    """Load a strict results array/object or JSONL; malformed rows are never skipped."""
    text = path.read_text(encoding="utf-8")
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        value = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BatchRejected(f"malformed JSONL at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise BatchRejected(f"result at {path}:{line_number} must be an object")
            value.append(row)
    if isinstance(value, dict):
        value = value.get("results")
    if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
        raise BatchRejected(f"{path} must contain an array of result objects")
    return value


def load_contract(store: PostgresArtifactStore, path: Path) -> ReviewBatchContract:
    contract = _load_object(path)
    required_root = {
        "schema_version", "contract_artifact_id", "batch_id", "run_id", "phase",
        "prompt_version", "attempt", "issuer_identity", "authentication_context", "cells",
    }
    if set(contract) != required_root:
        raise BatchRejected("contract must contain the exact review-batch fields")
    if contract.get("schema_version") != "semiskill.review-batch/v1":
        raise BatchRejected("unsupported review batch contract schema")
    for field in ("batch_id", "run_id", "prompt_version", "issuer_identity"):
        if not isinstance(contract.get(field), str) or not contract[field].strip():
            raise BatchRejected(f"contract {field} is required")
    if contract.get("phase") not in {"review", "recheck"}:
        raise BatchRejected("contract phase must be review or recheck")
    attempt = contract.get("attempt")
    if type(attempt) is not int or attempt < 1:
        raise BatchRejected("contract attempt must be a positive integer")
    if not isinstance(contract.get("authentication_context"), dict) or not contract[
        "authentication_context"
    ]:
        raise BatchRejected("contract authentication_context is required")
    try:
        contract_artifact_id = uuid.UUID(contract["contract_artifact_id"])
    except (ValueError, TypeError, AttributeError) as exc:
        raise BatchRejected("contract_artifact_id must be a UUID") from exc
    contract_artifact = store.get(contract_artifact_id)
    if (
        contract_artifact is None
        or contract_artifact.artifact_type is not ArtifactType.GATE_DECISION
    ):
        raise BatchRejected("issued review batch contract artifact was not found")
    if contract_artifact.payload != {
        key: value for key, value in contract.items() if key != "contract_artifact_id"
    }:
        raise BatchRejected("contract JSON does not match the stored immutable lease")
    cells = contract.get("cells")
    if not isinstance(cells, list) or len(cells) != 1:
        raise BatchRejected(
            "each review contract must contain exactly one skill; pass up to "
            f"{MAX_BATCH_SIZE} independent --contract files"
        )
    required_cell = {
        "slug", "skill_version_id", "skill_payload_sha256", "version", "role", "level",
        "reviewer_identity", "fixer_identity", "lineage_id", "prior_review_ref", "checks",
    }
    leases = {}
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or set(cell) != required_cell:
            raise BatchRejected(f"contract cell {index} must contain the exact lease fields")
        slug = cell.get("slug")
        raw_id = cell.get("skill_version_id")
        if not isinstance(slug, str) or not slug or not isinstance(raw_id, str):
            raise BatchRejected(f"contract cell {index} requires slug and skill_version_id")
        if slug in leases:
            raise BatchRejected(f"duplicate contract slug: {slug}")
        try:
            artifact_id = uuid.UUID(raw_id)
        except ValueError as exc:
            raise BatchRejected(f"contract skill_version_id is not a UUID: {raw_id}") from exc
        artifact = store.get(artifact_id)
        if artifact is None or artifact.artifact_type is not ArtifactType.SKILL_VERSION:
            raise BatchRejected(f"contract skill version not found: {raw_id}")
        if artifact.payload.get("slug") != slug:
            raise BatchRejected(f"contract slug does not match skill version: {slug}")
        if cell.get("skill_payload_sha256") != payload_fingerprint(artifact.payload):
            raise BatchRejected(f"contract payload hash does not match skill version: {slug}")
        for field in ("version", "role", "level"):
            if cell.get(field) != artifact.payload.get(field):
                raise BatchRejected(f"contract {field} does not match skill version: {slug}")
        for field in ("reviewer_identity", "fixer_identity"):
            if not isinstance(cell.get(field), str) or not cell[field].strip():
                raise BatchRejected(f"contract cell {slug} requires {field}")
        lineage_id = cell.get("lineage_id")
        try:
            uuid.UUID(lineage_id)
        except (ValueError, TypeError, AttributeError) as exc:
            raise BatchRejected(f"contract lineage_id is not a UUID: {slug}") from exc
        raw_prior = cell.get("prior_review_ref")
        try:
            prior = uuid.UUID(raw_prior) if raw_prior is not None else None
        except (ValueError, TypeError, AttributeError) as exc:
            raise BatchRejected(f"contract prior_review_ref is not a UUID: {slug}") from exc
        leases[slug] = ReviewCellContract(
            skill_version=artifact,
            reviewer_identity=cell["reviewer_identity"],
            fixer_identity=cell["fixer_identity"],
            checks=cell.get("checks"),
            lineage_id=lineage_id,
            prior_review_ref=prior,
        )
    return ReviewBatchContract(
        batch_id=contract["batch_id"],
        run_id=contract["run_id"],
        phase=contract["phase"],
        prompt_version=contract["prompt_version"],
        attempt=attempt,
        cells=leases,
        issuer_identity=contract["issuer_identity"],
        authentication_context=contract["authentication_context"],
        contract_artifact=contract_artifact,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="artifact database; defaults to DATABASE_URL")
    parser.add_argument(
        "--contract", type=Path, action="append",
        help="one-skill orchestrator contract; repeat up to 10 times",
    )
    parser.add_argument("--results", type=Path, help="strict P5 result JSON/JSONL")
    parser.add_argument("--legacy-import", action="store_true",
                        help="import skills/*/REVIEW.json as non-authoritative provenance")
    parser.add_argument("--skills-root", type=Path, default=REPO / "skills")
    parser.add_argument("--archive-root", type=Path,
                        default=REPO / "archive" / "content-reviews")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    dsn = args.dsn or os.environ.get("DATABASE_URL") or Config.from_env().database_url
    store = PostgresArtifactStore(dsn)
    if args.legacy_import:
        if args.contract or args.results:
            raise BatchRejected("--legacy-import cannot be combined with a canonical batch")
        review_files = sorted(args.skills_root.glob("*/REVIEW.json"))
        imported = import_legacy_review_files(
            store=store, review_files=review_files, archive_root=args.archive_root,
        )
        print(json.dumps({
            "mode": "legacy-import",
            "found": len(review_files),
            "imported": len(imported),
            "authoritative": False,
            "artifact_ids": [str(artifact.artifact_id) for artifact in imported],
        }, indent=2))
        return 0
    if args.contract is None or args.results is None:
        raise BatchRejected("canonical collection requires both --contract and --results")
    contracts = [load_contract(store, path) for path in args.contract]
    results = load_results(args.results)
    reviews = collect_review_contract_batch(store=store, contracts=contracts, results=results)
    print(json.dumps({
        "mode": "canonical-review",
        "contracts": len(contracts),
        "committed": len(reviews),
        "artifact_ids": [str(artifact.artifact_id) for artifact in reviews],
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BatchRejected as exc:
        print(f"COLLECTION REJECTED: {exc}", file=sys.stderr)
        raise SystemExit(2)
