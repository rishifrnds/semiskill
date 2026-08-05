"""Coverage scoreboard — what the catalog actually contains, versus what was planned.

Deliberately **deterministic code, not an agent**. This project's own principle is "the model proposes;
deterministic code disposes", and a scoreboard that can be talked into optimism is worse than no
scoreboard: it converts an unfinished catalog into a claim that it is finished. So every number here
is derived from two files-of-record and nothing else:

  * `specs/skill_registry.json` — the plan (which cells are supposed to exist)
  * the **published catalog** — the truth (which cells reached it through the gate)

A skill on disk that never published counts as missing, because from an engineer's point of view it
is. An agent's assertion that a skill is "done" counts for nothing at all.

Gate status comes from `skills/<slug>/REVIEW.json`, written by the authoring gate. A skill that
published without an independent recheck returning `ready: true` is reported as `unreviewed` and fails
`--strict-gate` — that is the Phase-H lesson made mechanical.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from semiskill.artifacts.store import ArtifactStore
from semiskill.wave import _published_index

DEFAULT_TARGET = 5

# Cell status, worst to best.
MISSING = "missing"
FAILING_LINT = "authored-failing-lint"
UNPUBLISHED = "lint-clean-unpublished"
PUBLISHED = "published"
DECLINED = "declined"

# Gate status for a published cell.
UNREVIEWED = "unreviewed"
REVIEWED = "reviewed"
READY = "recheck-ready"


@dataclass(frozen=True)
class CellStatus:
    slug: str
    role: str
    level: str
    title: str
    status: str
    gate: str | None = None
    declined_why: str | None = None
    lint_verdict: str | None = None
    findings: int = 0


@dataclass(frozen=True)
class RoleCoverage:
    role: str
    target: int
    published: int
    declined: int
    planned: int
    ok: bool
    weakest_gap: int


@dataclass(frozen=True)
class Scoreboard:
    generated_at: str
    target: int
    cells: tuple[CellStatus, ...]
    roles: tuple[RoleCoverage, ...]
    levels: dict[str, int]
    totals: dict[str, int]
    unregistered: tuple[str, ...] = ()          # published but absent from the registry
    failures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return not self.failures


def load_registry(path: str | Path) -> list[dict]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    cells = data["cells"] if isinstance(data, dict) else data
    seen: set[str] = set()
    for c in cells:
        for key in ("slug", "role", "level"):
            if not c.get(key):
                raise ValueError(f"registry cell missing {key!r}: {c}")
        if c["slug"] in seen:
            raise ValueError(f"duplicate slug in registry: {c['slug']}")
        seen.add(c["slug"])
    return list(cells)


def read_review(skills_root: str | Path, slug: str) -> dict | None:
    p = Path(skills_root) / slug / "REVIEW.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _gate_status(review: dict | None) -> str:
    if not review:
        return UNREVIEWED
    recheck = review.get("recheck") or {}
    if recheck.get("ready") is True:
        return READY
    if review.get("findings") is not None or review.get("review"):
        return REVIEWED
    return UNREVIEWED


def build_scoreboard(*, store: ArtifactStore, registry_path: str | Path,
                     skills_root: str | Path = "skills", target: int = DEFAULT_TARGET,
                     generated_at: str = "unset", lint: bool = True,
                     strict_gate: bool = False) -> Scoreboard:
    registry = load_registry(registry_path)
    published = _published_index(store)
    root = Path(skills_root)

    lint_by_slug: dict[str, tuple[str, int]] = {}
    if lint:
        from semiskill.authoring.lint import lint_wave_dir
        for rep in lint_wave_dir(root).reports:
            if rep.slug:
                lint_by_slug[rep.slug] = (rep.predicted_verdict, len(rep.errors))

    cells: list[CellStatus] = []
    for c in registry:
        slug = c["slug"]
        common = dict(slug=slug, role=c["role"], level=c["level"], title=c.get("title", slug))

        if c.get("declined"):
            why = c["declined"].get("why") if isinstance(c["declined"], dict) else str(c["declined"])
            cells.append(CellStatus(status=DECLINED, declined_why=why, **common))
            continue

        verdict, errs = lint_by_slug.get(slug, (None, 0))
        if slug in published:
            cells.append(CellStatus(status=PUBLISHED,
                                    gate=_gate_status(read_review(root, slug)),
                                    lint_verdict=verdict, findings=errs, **common))
        elif not (root / slug / "SKILL.md").exists():
            cells.append(CellStatus(status=MISSING, **common))
        elif verdict == "approve" and errs == 0:
            cells.append(CellStatus(status=UNPUBLISHED, lint_verdict=verdict, **common))
        else:
            cells.append(CellStatus(status=FAILING_LINT, lint_verdict=verdict,
                                    findings=errs, **common))

    roles: list[RoleCoverage] = []
    for role in sorted({c.role for c in cells}):
        mine = [c for c in cells if c.role == role]
        pub = sum(1 for c in mine if c.status == PUBLISHED)
        dec = sum(1 for c in mine if c.status == DECLINED and c.declined_why)
        roles.append(RoleCoverage(role=role, target=target, published=pub, declined=dec,
                                  planned=len(mine), ok=(pub + dec) >= target,
                                  weakest_gap=max(0, target - (pub + dec))))

    levels: dict[str, int] = {}
    for c in cells:
        if c.status == PUBLISHED:
            levels[c.level] = levels.get(c.level, 0) + 1

    registered = {c.slug for c in cells}
    unregistered = tuple(sorted(set(published) - registered))

    totals = {
        "planned": len(cells),
        PUBLISHED: sum(1 for c in cells if c.status == PUBLISHED),
        UNPUBLISHED: sum(1 for c in cells if c.status == UNPUBLISHED),
        FAILING_LINT: sum(1 for c in cells if c.status == FAILING_LINT),
        MISSING: sum(1 for c in cells if c.status == MISSING),
        DECLINED: sum(1 for c in cells if c.status == DECLINED),
        READY: sum(1 for c in cells if c.gate == READY),
        UNREVIEWED: sum(1 for c in cells if c.status == PUBLISHED and c.gate == UNREVIEWED),
        "roles_ok": sum(1 for r in roles if r.ok),
        "roles": len(roles),
    }

    failures: list[str] = []
    for r in roles:
        if not r.ok:
            failures.append(f"{r.role}: {r.published}/{r.target} published"
                            + (f" (+{r.declined} declined)" if r.declined else "")
                            + f" — {r.weakest_gap} short")
    for c in cells:
        if c.status == FAILING_LINT:
            failures.append(f"{c.slug}: authored but fails lint ({c.findings} errors)")
    if strict_gate:
        for c in cells:
            if c.status == PUBLISHED and c.gate != READY:
                failures.append(f"{c.slug}: published with gate status {c.gate!r}, "
                                "not an independent recheck-ready")
    for slug in unregistered:
        failures.append(f"{slug}: published but not in the registry")

    return Scoreboard(generated_at=generated_at, target=target, cells=tuple(cells),
                      roles=tuple(roles), levels=levels, totals=totals,
                      unregistered=unregistered, failures=tuple(failures))


def render(sb: Scoreboard, *, style: str = "text") -> str:
    if style == "json":
        return json.dumps({
            "generated_at": sb.generated_at, "target": sb.target, "ok": sb.ok,
            "totals": sb.totals, "levels": sb.levels,
            "roles": [asdict(r) for r in sb.roles],
            "cells": [asdict(c) for c in sb.cells],
            "unregistered": list(sb.unregistered), "failures": list(sb.failures),
        }, indent=2, sort_keys=True)

    bar = lambda r: ("#" * min(r.published, r.target)).ljust(r.target, ".")   # noqa: E731
    lines: list[str] = []
    if style == "markdown":
        lines += [f"### Catalog coverage — {sb.totals[PUBLISHED]}/{sb.totals['planned']} published", "",
                  f"| Role | Published | Target | Status |", "|---|---|---|---|"]
        for r in sb.roles:
            note = f" (+{r.declined} declined)" if r.declined else ""
            lines.append(f"| {r.role} | {r.published}{note} | {r.target} | "
                         f"{'ok' if r.ok else f'{r.weakest_gap} short'} |")
        lines += ["", f"Gate: {sb.totals[READY]} recheck-ready · "
                      f"{sb.totals[UNREVIEWED]} published without an independent recheck.", ""]
        if sb.failures:
            lines += ["**Failures**", ""] + [f"- {f}" for f in sb.failures]
        return "\n".join(lines)

    lines.append(f"coverage — target {sb.target} per role · generated {sb.generated_at}")
    lines.append("")
    for r in sb.roles:
        note = f"  (+{r.declined} declined)" if r.declined else ""
        flag = "ok  " if r.ok else "SHORT"
        lines.append(f"  {flag} {r.role:34} [{bar(r)}] {r.published}/{r.target}{note}")
    lines.append("")
    lines.append("  by level: " + " · ".join(f"{k} {v}" for k, v in sorted(sb.levels.items())) or "  (none)")
    lines.append("")
    t = sb.totals
    lines.append(f"  planned {t['planned']} · published {t[PUBLISHED]} · lint-clean unpublished "
                 f"{t[UNPUBLISHED]} · failing lint {t[FAILING_LINT]} · missing {t[MISSING]} · "
                 f"declined {t[DECLINED]}")
    lines.append(f"  gate: {t[READY]} recheck-ready · {t[UNREVIEWED]} published without one")
    lines.append(f"  roles meeting target: {t['roles_ok']}/{t['roles']}")
    if sb.failures:
        lines.append("")
        lines.append("  FAILURES")
        for f in sb.failures:
            lines.append(f"    - {f}")
    return "\n".join(lines)
