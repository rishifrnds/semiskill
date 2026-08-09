"""Standalone-script entry point for the review-batch issuer.

The orchestration logic lives in `semiskill.authoring.issue_batch` (an importable package module,
needed so `semiskill review-issue` can call it without depending on the unpackaged `tools/` tree —
see HANDOFF.md Gate 1 item 2). This script is kept only for direct
`python tools/issue_batch.py ...` invocation; prefer `semiskill review-issue` going forward.

    python tools/issue_batch.py --snapshot reports/scoreboard.json --phase review \
        --prompt-version P1-ADVERSARIAL-REVIEW@3 --size 10 --out-dir reports/contracts/<batch-id>/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from semiskill.artifacts.store import PostgresArtifactStore  # noqa: E402
from semiskill.authoring.issue_batch import (  # noqa: E402
    BatchRefused,
    Refusal,
    _cell_checks,
    _confined_path,
    _lease_cell,
    _select_cells,
    _verify_snapshot_freshness,
    render_worker_prompt,
    run_issue_batch,
)
from semiskill.authoring.review_collection import BatchRejected  # noqa: E402
from semiskill.authoring.snapshot import SnapshotUnavailable, load_scoreboard_snapshot  # noqa: E402
from semiskill.authoring.review_collection import MAX_BATCH_SIZE  # noqa: E402
from semiskill.config import Config  # noqa: E402

__all__ = [
    "BatchRefused",
    "Refusal",
    "_cell_checks",
    "_confined_path",
    "_lease_cell",
    "_select_cells",
    "_verify_snapshot_freshness",
    "render_worker_prompt",
    "run_issue_batch",
]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="artifact database; defaults to DATABASE_URL")
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="validated scoreboard snapshot JSON (semiskill scoreboard --snapshot-out)")
    parser.add_argument("--phase", required=True, choices=["review", "recheck"])
    parser.add_argument("--prompt-version", required=True,
                        help="e.g. P1-ADVERSARIAL-REVIEW@3 or P5-RECHECK-CALIBRATED@3")
    parser.add_argument("--size", type=int, default=MAX_BATCH_SIZE,
                        help=f"at most {MAX_BATCH_SIZE} skills per batch")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--batch-id", help="defaults to a generated phase+timestamp id")
    parser.add_argument("--issuer-identity", default="orchestrator:issue_batch@1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    document = load_scoreboard_snapshot(args.snapshot)
    dsn = args.dsn or os.environ.get("DATABASE_URL") or Config.from_env().database_url
    store = PostgresArtifactStore(dsn)
    manifest = run_issue_batch(
        store=store, document=document, phase=args.phase, prompt_version=args.prompt_version,
        size=args.size, out_dir=args.out_dir, batch_id=args.batch_id,
        issuer_identity=args.issuer_identity,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BatchRefused, BatchRejected, SnapshotUnavailable) as exc:
        print(f"BATCH REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
