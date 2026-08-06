"""Pre-flight linter for authored skills — catch every wave-killer offline, before the DB.

Two layers, deliberately separated:
  * `lint_body` (stdlib-only, ships inside the delivered pack) supplies line/column/fix messaging.
  * this module supplies the FRONTMATTER contract (ADR-008) and, critically, takes its SCORES from
    the real scanners rather than reimplementing them. `tests/authoring/test_lint_drift.py` asserts
    the two agree, so editing a scanner regex without updating the linter fails CI.

Stage 3 is advisory here by design: the held-out injection corpus is never mirrored into
author-facing code (see `lint_body`). Pass `probe_dsn=` to consult the real corpus through the
existing `probe_skill` seam, which returns matched class names and never the patterns.

    semiskill lint skills/                 # whole tree
    semiskill lint skills/dv-x/SKILL.md    # one file
    semiskill lint skills/ --json          # machine-readable
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from semiskill.authoring import facets
from semiskill.authoring.lint_body import ERROR, WARN, ADVISORY, BodyFinding, lint_body
from semiskill.capture.intake import (
    SharedBundle,
    build_skill_version,
    load_skill_source,
    parse_skill_md,
    shared_bundle_for_skills_root,
)
from semiskill.governance.policy import ALLOWED_SKILL_TOOLS, DANGEROUS_SKILL_TOOLS, tool_risk
from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.secret_pii import SecretPiiScanner
from semiskill.scanners.static_structure import StaticStructureScanner
from semiskill.spine.pipeline import APPROVE_THRESHOLD, REJECT_THRESHOLD

# The Agent Skills open standard fixes the permitted frontmatter keys. `allowed_tools` is accepted
# as an alias because intake.py has always read it.
STANDARD_KEYS = frozenset({
    "name", "description", "license", "compatibility", "metadata", "allowed-tools", "allowed_tools",
})
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MAX_NAME = 64
MAX_DESCRIPTION = 1024


@dataclass(frozen=True)
class LintReport:
    path: str
    slug: str | None
    name: str | None
    ok: bool                              # no error-level findings
    stage_safety: dict[int, float | None]
    predicted_aggregate: float | None
    predicted_verdict: str                # approve | request-changes | reject | unparseable
    stage3_authoritative: bool
    body_sha256: str
    findings: tuple[BodyFinding, ...]

    @property
    def errors(self) -> tuple[BodyFinding, ...]:
        return tuple(f for f in self.findings if f.level == ERROR)


@dataclass(frozen=True)
class WaveLintReport:
    root: str
    reports: tuple[LintReport, ...] = ()
    duplicate_slugs: tuple[tuple[str, tuple[str, ...]], ...] = ()
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.duplicate_slugs and all(r.ok for r in self.reports)


def _f(rule: str, level: str, message: str, fix: str, *, line: int = 1, stage=None) -> BodyFinding:
    return BodyFinding(rule, level, message, line, 1, "", fix, stage, None)


def _frontmatter_findings(fm: dict, *, path: Path | None) -> list[BodyFinding]:
    out: list[BodyFinding] = []

    for key in fm:
        if key not in STANDARD_KEYS:
            out.append(_f("L010", ERROR,
                          f"frontmatter key {key!r} is not one of the six standard keys",
                          f"Move it under `metadata:` as `semiskill-{key}` (ADR-008). Permitted at "
                          f"top level: {sorted(STANDARD_KEYS - {'allowed_tools'})}."))

    name = fm.get("name")
    if not name:
        out.append(_f("L005", ERROR, "frontmatter has no `name`", "Add a kebab-case name."))
    else:
        name = str(name)
        if not NAME_RE.match(name):
            out.append(_f("L011", ERROR,
                          f"`name` {name!r} is not kebab-case; Cursor will not load it",
                          "Lowercase letters, digits and hyphens only — e.g. dv-sim-log-first-error."))
        if len(name) > MAX_NAME:
            out.append(_f("L011", ERROR, f"`name` is {len(name)} chars (max {MAX_NAME})",
                          "Shorten it."))
        if path is not None and path.parent.name and name != path.parent.name:
            out.append(_f("L012", ERROR,
                          f"`name` {name!r} does not match the folder {path.parent.name!r}",
                          "The Agent Skills standard resolves a skill by its directory; they must match."))

    desc = fm.get("description")
    if not desc or not str(desc).strip():
        out.append(_f("L013", ERROR, "frontmatter has no `description`",
                      "This is the ONLY text the agent sees when deciding to invoke the skill. "
                      "Write '<what it does>. Use when <concrete trigger>.'"))
    else:
        desc = str(desc)
        if len(desc) > MAX_DESCRIPTION:
            out.append(_f("L014", ERROR, f"`description` is {len(desc)} chars (max {MAX_DESCRIPTION})",
                          "Trim it."))
        if "<" in desc or ">" in desc:
            out.append(_f("L015", ERROR, "`description` contains an angle bracket",
                          "Angle brackets are rejected by the Agent Skills validator."))
        if "use when" not in desc.lower():
            out.append(_f("L022", WARN, "`description` does not say when to use the skill",
                          "Without a concrete trigger the agent will not auto-invoke it, and the "
                          "catalog degrades into a manual slash-command menu."))

    raw_tools = fm.get("allowed-tools", fm.get("allowed_tools"))
    if isinstance(raw_tools, str) and raw_tools.strip():
        pass                                # supported since ADR-008; intake splits it
    for tool in _declared_tools(fm):
        risk = tool_risk(tool)
        if tool in DANGEROUS_SKILL_TOOLS:
            out.append(_f("L017", ERROR, f"declares shell/exec tool {tool!r} (severity {risk} — HARD FAIL)",
                          f"A skill may declare only: {sorted(ALLOWED_SKILL_TOOLS)}.", stage=1))
        elif risk > 0:
            out.append(_f("L017", ERROR, f"declares unlisted tool {tool!r} (severity {risk} each)",
                          f"Two unlisted tools alone reject the skill. Permitted: "
                          f"{sorted(ALLOWED_SKILL_TOOLS)}.", stage=1))

    meta = fm.get("metadata")
    if meta is not None and not isinstance(meta, dict):
        out.append(_f("L018", WARN, "`metadata` is not a mapping and will be ignored",
                      "The standard defines metadata as a map of string to string."))
    elif isinstance(meta, dict):
        for k, v in meta.items():
            if isinstance(v, (dict, list)):
                out.append(_f("L018", WARN, f"metadata[{k!r}] is not a scalar",
                              "The standard defines metadata values as strings."))

    for facet in facets.FACET_KEYS:
        value = _facet_value(fm, facet)
        if value is None:
            out.append(_f("L020", WARN, f"no `{facet}` facet",
                          f"Without it the skill is invisible to browse-by-{facet}."))
        elif not facets.is_valid(facet, value):
            hint = facets.suggest(facet, value)
            out.append(_f("L019", ERROR,
                          f"{facet}={value!r} is not in the vocabulary — the facet is unreachable",
                          (f"Did you mean {hint!r}? " if hint else "")
                          + f"Permitted: {list(facets.allowed(facet))}."))

    version = _resolve(fm, "version")
    if version is not None and not re.match(r"^\d+\.\d+\.\d+$", str(version)):
        out.append(_f("L021", WARN, f"version {str(version)!r} is not semver",
                      "Use MAJOR.MINOR.PATCH."))

    for slot_key in ("name", "description"):
        if "[[FILL:" in str(fm.get(slot_key, "")):
            out.append(_f("L063", ERROR, f"`{slot_key}` contains a [[FILL:]] slot",
                          "Slots belong in the body only — frontmatter is how the skill is found."))

    return out


def _declared_tools(fm: dict) -> list[str]:
    raw = fm.get("allowed-tools", fm.get("allowed_tools"))
    if isinstance(raw, str):
        return [t for t in re.split(r"[,\s]+", raw.strip()) if t]
    if isinstance(raw, (list, tuple)):
        return [str(t) for t in raw]
    return []


def _resolve(fm: dict, key: str):
    meta = fm.get("metadata")
    meta = meta if isinstance(meta, dict) else {}
    for candidate in (meta.get(f"semiskill-{key}"), meta.get(key), fm.get(key)):
        if candidate is not None:
            return candidate
    return None


def _facet_value(fm: dict, facet: str):
    return _resolve(fm, facet)


def lint_text(*, text: str, path: str = "<memory>", files: dict[str, str] | None = None,
              probe_dsn: str | None = None) -> LintReport:
    """Lint one SKILL.md. Scores come from the real scanners; messaging from lint_body."""
    p = Path(path) if path != "<memory>" else None
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

    try:
        parsed = parse_skill_md(text)
    except ValueError as e:
        return LintReport(path, None, None, False, {}, None, "unparseable", False, sha,
                          (_f("L001", ERROR, f"frontmatter unparseable: {e}",
                              "The file must start with '---' at byte 0 (no BOM, no leading blank "
                              "line) and close the fence with '---'."),))
    except yaml.YAMLError as e:
        # NOT a ValueError — uncaught, this aborts an entire wave mid-run.
        first = str(e).splitlines()[0] if str(e) else "invalid YAML"
        return LintReport(path, None, None, False, {}, None, "unparseable", False, sha,
                          (_f("L003", ERROR, f"YAML error in frontmatter: {first}",
                              "Quote any value containing ': ', and never start a value with "
                              "@ ` % * & ! | > [ or {."),))

    findings = list(_frontmatter_findings(parsed.frontmatter, path=p))
    findings.extend(lint_body(parsed.body))

    try:
        payload = build_skill_version(skill_md=text, actor="lint", files=files).payload
    except ValueError as e:
        findings.append(_f("L005", ERROR, str(e), "Add a `name` to the frontmatter."))
        return LintReport(path, None, None, False, {}, None, "unparseable", False, sha,
                          tuple(findings))

    sub = SkillSubmission.from_payload(payload)
    stage1 = StaticStructureScanner().scan(sub)
    stage4 = SecretPiiScanner().scan(sub)
    stage_safety: dict[int, float | None] = {1: stage1.safety_score, 4: stage4.safety_score}

    stage3_authoritative = False
    stage3_safety: float | None = None
    if probe_dsn:
        from semiskill.sensor.corpus import probe_skill          # noqa: PLC0415 — optional path
        result = probe_skill(probe_dsn, "\n".join(sub.texts()))
        classes = tuple(getattr(result, "classes", ()) or ())
        stage3_authoritative = True
        stage3_safety = 0.05 if classes else 1.0
        for cls in classes:
            findings.append(_f("L058", ERROR,
                               f"matched held-out injection corpus class {cls!r} (HARD FAIL)",
                               "Rephrase so the body never reads as an instruction to the agent."))
    stage_safety[3] = stage3_safety

    known = [v for v in stage_safety.values() if v is not None]
    aggregate = min(known) if known else None
    if aggregate is None:
        verdict = "unparseable"
    elif stage1.hard_fail or stage4.hard_fail or (stage3_safety is not None and stage3_safety < 0.5):
        verdict = "reject"
    else:
        verdict = ("approve" if aggregate >= APPROVE_THRESHOLD
                   else "reject" if aggregate < REJECT_THRESHOLD
                   else "request-changes")

    if verdict == "approve" and aggregate is not None and aggregate == APPROVE_THRESHOLD:
        findings.append(_f("L067", WARN, "predicted aggregate is exactly at the approve threshold",
                           "One more finding and this silently stops publishing. Aim for 1.000."))

    findings.sort(key=lambda f: (f.line, f.rule))
    ok = not any(f.level == ERROR for f in findings)
    return LintReport(path, payload.get("slug"), payload.get("name"), ok, stage_safety,
                      aggregate, verdict, stage3_authoritative, sha, tuple(findings))


def lint_skill_dir(
    path: str | Path,
    *,
    shared_bundle: SharedBundle | None = None,
    **kw,
) -> LintReport:
    d = Path(path)
    skill_md = d / "SKILL.md" if d.is_dir() else d
    files: dict[str, str] = {}
    if d.is_dir():
        skill_text, files = load_skill_source(d, shared_bundle=shared_bundle)
    else:
        skill_text, files = load_skill_source(skill_md.parent, shared_bundle=shared_bundle)
    return lint_text(text=skill_text, path=str(skill_md),
                     files=files or None, **kw)


def lint_wave_dir(root: str | Path, **kw) -> WaveLintReport:
    r = Path(root)
    skill_files = sorted(r.rglob("SKILL.md")) if r.is_dir() else [r]
    if r.is_file():
        source_root = r.parent.parent
    elif (r / "SKILL.md").is_file():
        source_root = r.parent
    else:
        source_root = r
    shared_bundle = shared_bundle_for_skills_root(source_root)
    reports = tuple(lint_skill_dir(
        f.parent if f.name == "SKILL.md" else f,
        shared_bundle=shared_bundle,
        **kw,
    )
                    for f in skill_files)

    by_slug: dict[str, list[str]] = {}
    for rep in reports:
        if rep.slug:
            by_slug.setdefault(rep.slug, []).append(rep.path)
    dupes = tuple((slug, tuple(paths)) for slug, paths in sorted(by_slug.items()) if len(paths) > 1)

    counts = {
        "skills": len(reports),
        "clean": sum(1 for x in reports if x.ok),
        "errors": sum(len(x.errors) for x in reports),
        "advisories": sum(1 for x in reports for f in x.findings if f.level == ADVISORY),
        "would_publish": sum(1 for x in reports if x.predicted_verdict == "approve"),
    }
    return WaveLintReport(str(r), reports, dupes, counts)


def render(report: WaveLintReport, *, style: str = "text") -> str:
    if style == "json":
        return json.dumps({
            "root": report.root, "ok": report.ok, "counts": report.counts,
            "duplicate_slugs": [{"slug": s, "paths": list(p)} for s, p in report.duplicate_slugs],
            "skills": [{
                "path": r.path, "slug": r.slug, "name": r.name, "ok": r.ok,
                "predicted_verdict": r.predicted_verdict,
                "predicted_aggregate": r.predicted_aggregate,
                "stage_safety": {str(k): v for k, v in r.stage_safety.items()},
                "stage3_authoritative": r.stage3_authoritative,
                "sha256": r.body_sha256,
                "findings": [{"rule": f.rule, "level": f.level, "line": f.line,
                              "message": f.message, "fix": f.fix} for f in r.findings],
            } for r in report.reports],
        }, indent=2, sort_keys=True)

    lines: list[str] = []
    for r in report.reports:
        head = f"{r.path}  [{r.predicted_verdict}"
        if r.predicted_aggregate is not None:
            head += f" {r.predicted_aggregate:.3f}"
        head += "]" + ("" if r.stage3_authoritative else "  (stage 3 not evaluated — advisory only)")
        lines.append(head)
        for f in r.findings:
            lines.append(f"  {f.line}:{f.col}  {f.level.upper():8} {f.rule}  {f.message}")
            if f.excerpt:
                lines.append(f"      | {f.excerpt}")
            lines.append(f"      fix: {f.fix}")
        if not r.findings:
            lines.append("  clean")
    for slug, paths in report.duplicate_slugs:
        lines.append(f"DUPLICATE SLUG {slug!r}: {', '.join(paths)}")
        lines.append("      fix: slugs are not unique-constrained in the catalog — a duplicate "
                     "double-publishes invisibly.")
    c = report.counts
    lines.append(f"\n{c.get('clean', 0)}/{c.get('skills', 0)} clean · {c.get('errors', 0)} errors · "
                 f"{c.get('advisories', 0)} advisories · {c.get('would_publish', 0)} predicted to publish")
    lines.append("A clean lint means probably publishable. Only the pipeline says published.")
    return "\n".join(lines)
