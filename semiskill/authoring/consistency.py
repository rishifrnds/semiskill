"""Pack-level consistency checks — the failures reviewers kept finding by eye.

Four rounds of adversarial review on the first six skills produced real findings, and nearly all of
them were the same shape: something in one file disagreed with something in another file, or with
another part of itself. A slot declared and never used. A step Grepping for a slot that was never
declared. A handoff-block field widened in one skill and left stale in the sibling that claims to
match it mechanically. A field renamed with one reference missed.

Every one of those is decidable from the text, so paying a reviewer to notice it is both expensive
and unreliable — a human or an agent reading 220 lines will miss the third occurrence of a renamed
field, which is exactly what happened. These checks run in milliseconds and never miss it.

They complement the per-skill linter rather than replacing it: `lint.py` asks "is this file
publishable", these ask "does this pack agree with itself".
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

# `| Slot name | [[FILL: ...]] | who |` — the pack's slot-table convention.
_SLOT_ROW = re.compile(r"^\|\s*([A-Z][^|]{1,60}?)\s*\|\s*\[\[FILL:", re.M)
# A fenced handoff/report block line: `field    : a | b | c`
_FIELD_LINE = re.compile(r"^([a-z][a-z0-9 _-]{1,20}?)\s*:\s*(.+)$", re.M)
_FENCE = re.compile(r"```.*?```", re.S)


@dataclass(frozen=True)
class ConsistencyFinding:
    rule: str
    level: str            # error | warn
    slug: str
    message: str
    fix: str

    def __str__(self) -> str:
        return f"{self.slug}: {self.rule} {self.message}"


def _body(text: str) -> str:
    """Everything after the frontmatter."""
    parts = text.split("---", 2)
    return parts[2] if len(parts) > 2 else text


def declared_slots(body: str) -> set[str]:
    return {m.group(1).strip() for m in _SLOT_ROW.finditer(body)}


def report_fields(body: str) -> dict[str, str]:
    """Fields inside fenced blocks: {field: raw value}. Only fenced blocks count, so ordinary prose
    containing a colon is not mistaken for a handoff field."""
    out: dict[str, str] = {}
    for block in _FENCE.findall(body):
        for m in _FIELD_LINE.finditer(block):
            name = m.group(1).strip()
            if " " in name and len(name.split()) > 2:      # prose, not a field label
                continue
            out.setdefault(name, m.group(2).strip())
    return out


def _enum(value: str) -> set[str] | None:
    """The alternatives in `a | b | c`, or None if the value is not an enum."""
    if "|" not in value or "<" in value:
        return None
    parts = [p.strip() for p in value.split("|")]
    if len(parts) < 2 or any(not p or " " in p.strip() and len(p.split()) > 3 for p in parts):
        return None
    return set(parts)


def check_pack(root: str | Path) -> list[ConsistencyFinding]:
    """Cross-file and intra-file consistency over a tree of skill directories."""
    r = Path(root)
    bodies: dict[str, str] = {}
    for skill_md in sorted(r.rglob("SKILL.md")):
        bodies[skill_md.parent.name] = _body(skill_md.read_text(encoding="utf-8"))

    findings: list[ConsistencyFinding] = []

    # C001/C002 — slots must be declared and used, in both directions.
    for slug, body in bodies.items():
        slots = declared_slots(body)
        table_end = body.find("\n## ", body.find("[[FILL:")) if "[[FILL:" in body else -1
        after = body[table_end:] if table_end > 0 else ""
        for slot in sorted(slots):
            # a slot is "used" if its name, or a distinctive word from it, appears after the table
            key = slot.lower()
            head = key.split()[0]
            if key not in after.lower() and head not in after.lower():
                findings.append(ConsistencyFinding(
                    "C001", "warn", slug,
                    f"slot {slot!r} is declared but no step ever uses it",
                    "Either consume it in the procedure or drop the row — a slot table that asks for "
                    "facts the skill never spends sends the reader to interrupt someone for nothing."))

    # C003 — a handoff field carrying an enum must carry the SAME enum everywhere it appears.
    enums: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for slug, body in bodies.items():
        for field, value in report_fields(body).items():
            e = _enum(value)
            if e:
                enums[field][slug] = e
    for field, by_slug in sorted(enums.items()):
        if len(by_slug) < 2:
            continue
        variants = {frozenset(v) for v in by_slug.values()}
        if len(variants) == 1:
            continue

        detail = "; ".join(f"{s}: {' | '.join(sorted(v))}" for s, v in sorted(by_slug.items()))
        widest = max(by_slug.values(), key=len)
        rogue = {s: sorted(v - widest) for s, v in by_slug.items() if v - widest}

        if rogue:
            # Genuinely incompatible: some skill emits a value no other skill accepts, so the two
            # sets cannot both be right.
            findings.append(ConsistencyFinding(
                "C003", "error", ", ".join(sorted(rogue)),
                f"handoff field {field!r} has values no sibling accepts — {detail}",
                "These blocks are compared exactly by the people using them, so a value only one "
                "skill emits can never be matched."))
        else:
            # Every variant is a subset of the widest. Narrowing is often deliberate — a build-break
            # skill only ever produces compile or elab — so this is a prompt to confirm, not a bug.
            findings.append(ConsistencyFinding(
                "C003", "warn", ", ".join(sorted(by_slug)),
                f"handoff field {field!r} is narrower in some skills than others — {detail}",
                "If the narrowing is deliberate (this skill can only ever produce those values), say "
                "so next to the block. If it is drift — an enum widened in one skill and not its "
                "siblings — the sibling needs the same values or the two will never match."))

    # C004 — a value named in prose for a known field must be one of that field's legal values.
    for slug, body in bodies.items():
        fields = report_fields(body)
        for field, value in fields.items():
            e = _enum(value)
            if not e:
                continue
            for m in re.finditer(rf"`{re.escape(field)}:\s*([a-z][a-z0-9-]*)`", body):
                if m.group(1) not in e:
                    findings.append(ConsistencyFinding(
                        "C004", "error", slug,
                        f"prose refers to `{field}: {m.group(1)}` but that is not one of "
                        f"{field}'s legal values ({' | '.join(sorted(e))})",
                        "A renamed or re-split field leaves stale references behind; this is the "
                        "third-occurrence class that eyeball review reliably misses."))

    return findings


def render(findings: list[ConsistencyFinding]) -> str:
    if not findings:
        return "pack is self-consistent"
    lines = [f"{len(findings)} pack-consistency finding(s)", ""]
    for f in findings:
        lines.append(f"  {f.level.upper():5} {f.rule}  {f.slug}")
        lines.append(f"        {f.message}")
        lines.append(f"        fix: {f.fix}")
    return "\n".join(lines)
