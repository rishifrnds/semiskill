"""ADR-024 Stage 2 — host-side staging projection for the governed deterministic scanner.

The trusted host, never the container and never the payload, decides two things: which bytes reach
the scanner, and what the expected coverage set is. Everything in a `SkillSubmission` is untrusted
input, including the file *paths* — so this module projects the payload into a scanner-owned staging
directory and refuses anything that could escape that root, silence the engine, or make the host's
idea of "every file" disagree with what is actually on disk.

Fail closed, loudly. ADR-024 makes any ignored, skipped, unparsed, truncated, extra or missing file
a blocking Stage-2 `not_run`, so a refusal here is the correct outcome, not an inconvenience. There
is deliberately no "best effort" mode: a projection that quietly drops a file would produce a clean
scan of an incomplete payload, which is precisely the fail-open shape that retired the previous
runner.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

# Scanner configuration a payload must never be able to supply for its own scan. A submitted
# `.semgrepignore` would let a skill exclude itself from the rules that judge it, and the ignore
# files below do the same through the engine's file-discovery defaults. These are isolated (recorded
# and withheld from the scan root) rather than dropped, so the audit trail shows the containment.
ISOLATED_CONFIG_NAMES = frozenset({
    ".semgrepignore",
    ".semgrep.yml",
    ".semgrep.yaml",
    ".semgrepconfig",
    ".semgrepconfig.yml",
    ".semgrepconfig.yaml",
    "semgrep.yml",
    "semgrep.yaml",
    ".gitignore",
    ".dockerignore",
})

SKILL_MD = "SKILL.md"


class Stage2Refused(Exception):
    """A Stage-2 precondition failed before any scan could claim coverage."""


@dataclass(frozen=True)
class StagedPayload:
    """What the host projected, and what it will therefore require the engine to have analyzed."""

    root: Path
    expected_files: tuple[str, ...]     # sorted POSIX relpaths the engine MUST report analyzing
    isolated: tuple[str, ...]           # payload-controlled scanner config, withheld on purpose


def _normalized_relpath(raw: object) -> str:
    """Return a safe POSIX relpath, or raise. Backslashes are separators, not name characters.

    Windows and POSIX disagree about `\\`, and a payload can exploit that disagreement: on POSIX
    `refs\\..\\..\\x` is a single innocent-looking filename that becomes a traversal the moment it
    reaches a Windows host. Normalizing both separators the same way removes the ambiguity instead
    of depending on which platform happens to run the scan.
    """
    if not isinstance(raw, str):
        raise Stage2Refused(f"file path must be a string, got {type(raw).__name__}")
    if not raw:
        raise Stage2Refused("empty file path")
    if "\x00" in raw:
        raise Stage2Refused(f"NUL byte in file path: {raw!r}")
    # Unicode normalization first: distinct code point sequences can name the same file on disk,
    # which would let a payload smuggle a second entry past a naive duplicate check.
    candidate = unicodedata.normalize("NFC", raw).replace("\\", "/")
    if candidate.startswith("/"):
        raise Stage2Refused(f"absolute file path: {raw!r}")
    if len(candidate) >= 2 and candidate[1] == ":":
        raise Stage2Refused(f"drive-qualified file path: {raw!r}")
    if candidate.endswith("/"):
        raise Stage2Refused(f"file path names a directory: {raw!r}")
    parts = PurePosixPath(candidate).parts
    if not parts:
        raise Stage2Refused(f"file path resolves to nothing: {raw!r}")
    for part in parts:
        if part in {"", ".", ".."}:
            raise Stage2Refused(f"traversing or non-normalized file path: {raw!r}")
    return PurePosixPath(*parts).as_posix()


def _is_isolated_config(relpath: str) -> bool:
    return PurePosixPath(relpath).name in ISOLATED_CONFIG_NAMES


def project_payload(submission, *, root: Path | str) -> StagedPayload:
    """Materialize the exact payload into a fresh scanner-owned staging root.

    Returns the staged root, the exact expected coverage set, and any isolated scanner config.
    Raises `Stage2Refused` on anything that would make coverage ambiguous.
    """
    root = Path(root)
    if root.exists() and any(root.iterdir()):
        raise Stage2Refused(f"staging root is not empty: {root}")

    body = getattr(submission, "body", None)
    if not isinstance(body, str):
        raise Stage2Refused("submission body must be a string")

    files = getattr(submission, "files", None) or {}
    if not isinstance(files, dict):
        raise Stage2Refused("submission files must be a mapping")

    # Validate EVERY path before writing a single byte, so a refusal never leaves a half-projected
    # root behind for something else to scan.
    planned: dict[str, str] = {SKILL_MD: body}
    isolated: list[str] = []
    for raw_path, content in files.items():
        relpath = _normalized_relpath(raw_path)
        if not isinstance(content, str):
            raise Stage2Refused(
                f"file content must be a string, got {type(content).__name__} for {relpath!r}"
            )
        if _is_isolated_config(relpath):
            isolated.append(relpath)
            continue
        if relpath in planned:
            raise Stage2Refused(f"duplicate file path after normalization: {relpath!r}")
        planned[relpath] = content

    if len(set(isolated)) != len(isolated):
        raise Stage2Refused("duplicate isolated scanner configuration path")

    root.mkdir(parents=True, exist_ok=True)
    resolved_root = root.resolve()
    for relpath, content in planned.items():
        target = (root / relpath)
        # Belt and braces: even after normalization, confirm the write lands inside the root. A
        # symlinked staging parent or an exotic path form must not become an escape.
        if not str(target.resolve().parent).startswith(str(resolved_root)):
            raise Stage2Refused(f"file would be written outside the staging root: {relpath!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    expected = tuple(sorted(planned))
    on_disk = tuple(sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()
    ))
    if expected != on_disk:
        # The host's coverage claim and the filesystem must agree exactly, or the engine's later
        # "I analyzed everything" is unverifiable.
        raise Stage2Refused(
            f"staged tree does not match the expected coverage set: "
            f"expected {expected!r}, found {on_disk!r}"
        )

    return StagedPayload(root=root, expected_files=expected, isolated=tuple(sorted(isolated)))
