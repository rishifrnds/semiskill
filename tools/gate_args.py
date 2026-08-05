"""Emit the `args` payload for tools/dv-gate.js — one batch of authored skills to gate.

The gate agents should not have to rediscover what the deterministic checker already knows, so each
cell carries its own machine-checked consistency findings. Selection is by gate state, read from
disk: a skill with no REVIEW.json has never been reviewed; one whose REVIEW.json says ready:false
carries unresolved findings. Both need the gate; a ready:true skill does not.

    python tools/gate_args.py                     # what still needs the gate, as a summary
    python tools/gate_args.py --batch 1 --size 12 # the args JSON for batch 1
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from semiskill.authoring.consistency import check_pack  # noqa: E402


def gate_state(slug: str) -> str:
    """never-reviewed | not-ready | ready — read from the REVIEW.json on disk, never from a claim."""
    p = REPO / "skills" / slug / "REVIEW.json"
    if not p.exists():
        return "never-reviewed"
    try:
        rec = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "never-reviewed"
    return "ready" if (rec.get("recheck") or {}).get("ready") else "not-ready"


def main(argv: list[str]) -> int:
    cells = [c for c in json.loads((REPO / "specs" / "skill_registry.json").read_text(encoding="utf-8"))["cells"]
             if not c["slug"].startswith("declined-") and (REPO / "skills" / c["slug"] / "SKILL.md").exists()]

    findings: dict[str, list[str]] = defaultdict(list)
    for f in check_pack(REPO / "skills"):
        for slug in (s.strip() for s in f.slug.split(",")):      # C003 groups several slugs
            if (REPO / "skills" / slug).is_dir():
                findings[slug].append(f"{f.rule} ({f.level}): {f.message}")

    todo = [c for c in cells if gate_state(c["slug"]) != "ready"]
    # Group by role so a batch shares domain context, then order by role for an even spread.
    todo.sort(key=lambda c: (c["role"], c["level"], c["slug"]))

    if "--batch" not in argv:
        by_state: dict[str, int] = defaultdict(int)
        for c in cells:
            by_state[gate_state(c["slug"])] += 1
        print(f"{len(cells)} authored skills — " + ", ".join(f"{k}: {v}" for k, v in sorted(by_state.items())))
        print(f"{len(todo)} need the gate; {sum(len(v) for v in findings.values())} consistency findings "
              f"across {len(findings)} skills")
        size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 12
        for i in range(0, len(todo), size):
            batch = todo[i:i + size]
            print(f"  batch {i // size + 1}: {len(batch):2d}  {batch[0]['role']} .. {batch[-1]['role']}")
        return 0

    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else 12
    n = int(argv[argv.index("--batch") + 1])
    batch = todo[(n - 1) * size: n * size]
    payload = {
        "batch": n,
        "cells": [{"slug": c["slug"], "role": c["role"], "level": c["level"],
                   "findings": findings.get(c["slug"], [])} for c in batch],
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
