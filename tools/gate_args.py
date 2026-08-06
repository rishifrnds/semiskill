"""Tombstone for the retired file-based review batch selector.

Canonical selection comes from the source/hash-bound wave report plus artifact-backed scoreboard.
This command intentionally cannot inspect mutable sidecars or emit a review contract.
"""
from __future__ import annotations

import sys


def main(_argv: list[str] | None = None) -> int:
    print(
        "RETIRED: gate_args.py used mutable file-based review state. "
        "Use a validated scoreboard snapshot and an orchestrator-issued exact batch contract "
        "as documented in docs/WORKFLOW.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
