"""L1 Capture — turn a skill submission into an immutable `skill_version` artifact.

The submitted SKILL.md body and any bundled files are UNTRUSTED: they are stored verbatim in the
artifact payload but never executed or interpreted as instructions. The L4/L6 pipeline (Phase C)
scans them, and a human approves, before anything becomes discoverable (ADR-002).
"""
from __future__ import annotations
import hashlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
import yaml
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind

_FENCE = "---"

# Legacy content-review records are governance evidence, not installable skill content.  Keep the
# exception deliberately exact and root-scoped: every other file under the directory remains an
# untrusted part of the payload and must be scanned.  New reviews live in the artifact store; this
# compatibility boundary exists only while legacy REVIEW.json records are migrated.
_LEGACY_GOVERNANCE_FILES = frozenset({"REVIEW.json"})

# Canonical identity of the installable skill bytes. Governance metadata, artifact IDs, actors,
# and timestamps are intentionally absent.
PAYLOAD_FINGERPRINT_FIELDS = (
    "slug", "name", "description", "version", "function", "role", "level", "tags",
    "allowed_tools", "body", "files",
)


def payload_fingerprint(payload: dict) -> str:
    """Return a stable SHA-256 fingerprint of the installable skill payload."""
    canonical = {key: payload.get(key) for key in PAYLOAD_FINGERPRINT_FIELDS}
    encoded = json.dumps(
        canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ParsedSkill:
    frontmatter: dict
    body: str


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "skill"


def _meta(fm: dict) -> dict:
    """The `metadata` block, or {} when absent or not a mapping (never fatal — the pipeline, not
    the parser, is what rejects a bad submission)."""
    m = fm.get("metadata")
    return m if isinstance(m, dict) else {}


def _field(fm: dict, key: str):
    """Resolve one taxonomy field per ADR-008: `metadata['semiskill-<k>']` → `metadata['<k>']` →
    top-level `'<k>'`. The last hop keeps the pre-ADR-008 seeds working unchanged."""
    m = _meta(fm)
    for candidate in (m.get(f"semiskill-{key}"), m.get(key), fm.get(key)):
        if candidate is not None:
            return candidate
    return None


def _str_list(value) -> list[str]:
    """A YAML list, or a delimited string. The Agent Skills standard writes `allowed-tools` as a
    space-separated string, and `metadata` values are strings by spec — iterating either as a
    sequence would yield one entry per CHARACTER, which scores every skill 0.0 at stage 1."""
    if value is None:
        return []
    if isinstance(value, str):
        return [t for t in re.split(r"[,\s]+", value.strip()) if t]
    if isinstance(value, (list, tuple)):
        return [str(t) for t in value]
    return []


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
    version = _field(fm, "version")
    title = _field(fm, "title")                  # ADR-008: human title rides in metadata…
    payload = {
        "slug": _field(fm, "slug") or _slugify(str(name)),   # …`name` is the kebab identifier
        "name": str(title if title is not None else name),
        "description": str(fm.get("description", "")),
        "version": str(version if version is not None else "0.1.0"),
        "function": _field(fm, "function"),
        "role": _field(fm, "role"),
        "level": _field(fm, "level"),
        "owner": _field(fm, "owner") or actor,
        "tags": _str_list(_field(fm, "tags")),
        "allowed_tools": _str_list(fm.get("allowed-tools") or fm.get("allowed_tools")),
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
        if rel in _LEGACY_GOVERNANCE_FILES:
            continue
        try:
            files[rel] = f.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            files[rel] = f"<binary:{f.stat().st_size}bytes>"
    return skill_md, files
