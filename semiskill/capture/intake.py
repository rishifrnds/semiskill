"""L1 Capture — turn a skill submission into an immutable `skill_version` artifact.

The submitted SKILL.md body and any bundled files are UNTRUSTED: they are stored verbatim in the
artifact payload but never executed or interpreted as instructions. The L4/L6 pipeline (Phase C)
scans them, and a human approves, before anything becomes discoverable (ADR-002).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, replace
from pathlib import Path
import yaml
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind

_FENCE = "---"


@dataclass(frozen=True)
class ParsedSkill:
    frontmatter: dict
    body: str


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "skill"


def _sanitize(s: str) -> str:
    """Strip NUL bytes from untrusted content. Postgres jsonb rejects \\u0000, so an unsanitized NUL
    in a body/file would crash the store — sanitize at the L1 boundary (fail-safe, not fail-crash)."""
    return s.replace("\x00", "�") if "\x00" in s else s


def parse_skill_md(text: str) -> ParsedSkill:
    """Split a SKILL.md into YAML frontmatter (a mapping) + the untrusted body."""
    if not text.startswith(_FENCE):
        raise ValueError("SKILL.md must start with a '---' YAML frontmatter fence")
    rest = text[len(_FENCE):]
    end = rest.find("\n" + _FENCE)
    if end == -1:
        raise ValueError("SKILL.md frontmatter is not closed with '---'")
    fm_text = rest[:end]
    body = rest[end + len("\n" + _FENCE):].lstrip("\n")
    fm = yaml.safe_load(fm_text) or {}          # safe_load: never construct arbitrary objects
    if not isinstance(fm, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return ParsedSkill(frontmatter=fm, body=body)


def build_skill_version(*, skill_md: str, actor: str,
                        source_system: SourceSystem = SourceSystem.CLI,
                        actor_kind: ActorKind = ActorKind.HUMAN,
                        permissions_label: str = "team",
                        files: dict[str, str] | None = None) -> Artifact:
    """Build a `skill_version` artifact from a SKILL.md submission. Body/files kept UNTRUSTED."""
    parsed = parse_skill_md(skill_md)
    fm = parsed.frontmatter
    name = fm.get("name")
    if not name:
        raise ValueError("SKILL.md frontmatter must include a 'name'")
    payload = {
        "slug": fm.get("slug") or _slugify(str(name)),
        "name": str(name),
        "description": str(fm.get("description", "")),
        "version": str(fm.get("version", "0.1.0")),
        "function": fm.get("function"),
        "role": fm.get("role"),
        "level": fm.get("level"),
        "owner": fm.get("owner") or actor,
        "tags": [str(t) for t in (fm.get("tags") or [])],
        "allowed_tools": [str(t) for t in (fm.get("allowed-tools") or fm.get("allowed_tools") or [])],
        "body": _sanitize(parsed.body),                          # UNTRUSTED submitter content
        "files": {k: _sanitize(v) for k, v in (files or {}).items()},  # UNTRUSTED submitter content
    }
    art = Artifact.new(artifact_type=ArtifactType.SKILL_VERSION, source_system=source_system,
                       actor=actor, actor_kind=actor_kind, payload=payload)
    if permissions_label != art.permissions_label:
        art = replace(art, permissions_label=permissions_label)
    return art


def load_skill_dir(path: str | Path) -> tuple[str, dict[str, str]]:
    """Read a skill directory: its SKILL.md text + a {relpath: content} map of the other files.
    Undecodable (binary) files are recorded as a flagged placeholder, not silently dropped."""
    p = Path(path)
    skill_md_path = p / "SKILL.md"
    if not skill_md_path.exists():
        raise ValueError(f"no SKILL.md found in {p}")
    skill_md = skill_md_path.read_text(encoding="utf-8")
    files: dict[str, str] = {}
    for f in sorted(x for x in p.rglob("*") if x.is_file() and x.name != "SKILL.md"):
        rel = f.relative_to(p).as_posix()
        try:
            files[rel] = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            files[rel] = f"<binary:{f.stat().st_size}bytes>"
    return skill_md, files
