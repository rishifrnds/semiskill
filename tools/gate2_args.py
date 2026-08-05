"""Emit the `args` payload for tools/dv-gate2.js — the skills a first independent recheck rejected.

Reads the gate record on disk rather than a claim in a chat log: every skill whose REVIEW.json says
`recheck.ready` is false, carrying the exact findings that reviewer left open.

    python tools/gate2_args.py                # summary
    python tools/gate2_args.py --emit         # the args JSON for every not-ready skill
    python tools/gate2_args.py --emit --slugs dv-a,dv-b
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def remaining_of(rec: dict) -> list[str]:
    """Every open finding, whatever key the round-1 recheck happened to record it under."""
    rc = rec.get("recheck") or {}
    out: list[str] = []
    for key in ("blocking", "remaining", "remaining_nits", "new_problems"):
        for item in rc.get(key) or []:
            if isinstance(item, str) and item.strip() and item not in out:
                out.append(item)
    return out


def main(argv: list[str]) -> int:
    cells = {c["slug"]: c for c in
             json.loads((REPO / "specs" / "skill_registry.json").read_text(encoding="utf-8"))["cells"]}

    wanted = None
    if "--slugs" in argv:
        wanted = {s.strip() for s in argv[argv.index("--slugs") + 1].split(",") if s.strip()}

    todo = []
    for p in sorted((REPO / "skills").glob("*/REVIEW.json")):
        slug = p.parent.name
        if wanted and slug not in wanted:
            continue
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if (rec.get("recheck") or {}).get("ready"):
            continue
        c = cells.get(slug)
        if not c:
            continue
        todo.append({"slug": slug, "role": c["role"], "level": c["level"],
                     "remaining": remaining_of(rec)})

    if "--emit" not in argv:
        print(f"{len(todo)} skills failed their first independent recheck")
        for t in todo:
            print(f"  {t['slug']:45s} {len(t['remaining']):2d} open  ({t['role']})")
        return 0

    size = int(argv[argv.index("--size") + 1]) if "--size" in argv else len(todo)
    n = int(argv[argv.index("--batch") + 1]) if "--batch" in argv else 1
    print(json.dumps({"batch": f"r2-{n}", "cells": todo[(n - 1) * size: n * size]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
