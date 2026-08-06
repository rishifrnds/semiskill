"""Strict collector for canonical content reviews and legacy-review migration.

Canonical batch (all-or-nothing, maximum 10 skills)::

    python tools/collect_wave.py --contract batch-contract.json --results p5-results.json

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
    BatchRejected,
    collect_review_batch,
    import_legacy_review_files,
)
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


def load_contract(store: PostgresArtifactStore, path: Path) -> dict[str, object]:
    contract = _load_object(path)
    cells = contract.get("cells")
    if not isinstance(cells, list) or not cells:
        raise BatchRejected("contract cells must be a non-empty array")
    versions = {}
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict):
            raise BatchRejected(f"contract cell {index} must be an object")
        slug = cell.get("slug")
        raw_id = cell.get("skill_version_id")
        if not isinstance(slug, str) or not slug or not isinstance(raw_id, str):
            raise BatchRejected(f"contract cell {index} requires slug and skill_version_id")
        if slug in versions:
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
        versions[slug] = artifact
    return versions


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="artifact database; defaults to DATABASE_URL")
    parser.add_argument("--contract", type=Path, help="orchestrator-issued exact batch contract")
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
    versions = load_contract(store, args.contract)
    results = load_results(args.results)
    reviews = collect_review_batch(store=store, skill_versions=versions, results=results)
    print(json.dumps({
        "mode": "canonical-review",
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
