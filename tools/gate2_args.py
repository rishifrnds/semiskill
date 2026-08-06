"""Tombstone for the retired file-based round-two selector."""
from __future__ import annotations

import sys


def main(_argv: list[str] | None = None) -> int:
    print(
        "RETIRED: gate2_args.py used mutable file-based review state. "
        "Use canonical review artifacts and an orchestrator-issued exact batch contract "
        "as documented in docs/WORKFLOW.md.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
