"""Collect one authoring wave: write REVIEW.json per skill from the workflow journal.

The gate record has to be a file on disk, not a claim in a chat log — the scoreboard reads it, and
"was this actually reviewed?" must be a queryable fact. Run after a wave workflow completes:

    python collect_wave.py <workflow-run-dir> [--wave N]
"""
from __future__ import annotations

import datetime
import io
import json
import sys
from pathlib import Path

REPO = Path(r"E:\code\VLSI\semiskill")


def load(journal: Path) -> list[dict]:
    out = []
    for line in journal.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        val = row.get("result") if isinstance(row.get("result"), dict) else row.get("value")
        if isinstance(val, dict):
            out.append(val)
    return out


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    run_dir = Path(argv[0])
    wave = None
    if "--wave" in argv:
        wave = argv[argv.index("--wave") + 1]

    vals = load(run_dir / "journal.jsonl")
    by_slug: dict[str, dict] = {}
    for v in vals:
        slug = v.get("slug")
        if not slug:
            continue
        rec = by_slug.setdefault(slug, {})
        if "ready" in v:
            rec["recheck"] = v
        elif "must_fix" in v or "technical_errors" in v:
            rec["review"] = v
        elif "fixed" in v:
            rec["fix"] = v
        elif "uncertainties" in v:
            rec["author"] = v

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ready, not_ready, missing = [], [], []

    for slug, rec in sorted(by_slug.items()):
        d = REPO / "skills" / slug
        if not (d / "SKILL.md").exists():
            missing.append(slug)
            continue
        rc = rec.get("recheck") or {}
        out = {
            "slug": slug,
            "wave": wave,
            "gate": "author -> lint 1.000 -> adversarial review -> fix -> independent recheck",
            "recorded_at": now,
            "author": {"agent": f"author:{slug}",
                       "lint_line": (rec.get("author") or {}).get("lint_line", ""),
                       "uncertainties": (rec.get("author") or {}).get("uncertainties", [])},
            "review": {"agent": f"review:{slug}",
                       "must_fix": (rec.get("review") or {}).get("must_fix", []),
                       "technical_errors": (rec.get("review") or {}).get("technical_errors", []),
                       "verb_honesty": (rec.get("review") or {}).get("verb_honesty", []),
                       "hallucination_risks": (rec.get("review") or {}).get("hallucination_risks", []),
                       "budget_violations": (rec.get("review") or {}).get("budget_violations", []),
                       "open_twice": (rec.get("review") or {}).get("open_twice", "")},
            "fix": {"agent": f"fix:{slug}",
                    "fixed": (rec.get("fix") or {}).get("fixed", []),
                    "not_fixed": (rec.get("fix") or {}).get("not_fixed", []),
                    "lint_line": (rec.get("fix") or {}).get("lint_line", "")},
            "recheck": {"agent": f"recheck:{slug}",
                        "ready": bool(rc.get("ready")),
                        "why": rc.get("why", ""),
                        "remaining": rc.get("remaining", []),
                        "new_problems": rc.get("new_problems", [])},
        }
        io.open(d / "REVIEW.json", "w", encoding="utf-8", newline="\n").write(
            json.dumps(out, indent=1, ensure_ascii=False))
        (ready if out["recheck"]["ready"] else not_ready).append(slug)

    print(f"wave {wave}: {len(ready)} ready, {len(not_ready)} not ready, {len(missing)} missing")
    for s in ready:
        print(f"  READY      {s}")
    for s in not_ready:
        n = len((by_slug[s].get("recheck") or {}).get("remaining", []))
        print(f"  NOT-READY  {s}  ({n} remaining)")
    for s in missing:
        print(f"  MISSING    {s}  (no SKILL.md on disk)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
