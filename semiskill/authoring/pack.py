"""Materialize one exact, permission-scoped installable SemiSkill release.

Only frozen bytes from the approval-bound skill payload are eligible. Mutable repository source
files, authoring tools, and review files are never copied into a release. Canonical shared source
bytes are already vendored into every approved skill payload and must form one coherent snapshot
across the release. A complete release directory (pack folder, deterministic ZIP, and export
manifest) is transactionally swapped as one owned tree.
"""
from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.catalog_page import CatalogRefused, collect
from semiskill.authoring.export_files import (
    atomic_build_tree,
    safe_path_segment,
    safe_relative_path,
)
from semiskill.authoring.export_scope import ExportRefused, ExportScope
from semiskill.capture.intake import (
    CANONICAL_SHARED_FILES,
    build_skill_version,
    load_skill_dir,
    payload_fingerprint,
)

PACK_NAME = "semiskill-dv"
_SHARED_REF = re.compile(r"_shared/[A-Za-z0-9._/-]+")
_CANONICAL_SHARED_PATHS = tuple(f"_shared/{name}" for name in CANONICAL_SHARED_FILES)


class PackRefused(ExportRefused):
    """A pack precondition failed before any unverified output was published."""


@dataclass(frozen=True, slots=True)
class PackedFile:
    path: str
    sha256: str
    bytes_len: int


@dataclass(frozen=True, slots=True)
class PackedSkill:
    name: str
    title: str
    description: str
    role: str | None
    level: str | None
    function: str | None
    version: str
    sha256: str
    bytes_len: int
    slots: int
    verdict: str
    aggregate_safety: float | None
    permission_label: str
    skill_version_artifact_id: str
    approval_artifact_id: str
    payload_sha256: str
    automated_review_artifact_id: str
    content_review_artifact_id: str
    scan_artifact_ids: tuple[str, ...]
    files: tuple[PackedFile, ...]


@dataclass(frozen=True, slots=True)
class PackManifest:
    pack: str
    generated_at: str
    scope_id: str
    permission_label: str
    scoreboard_snapshot_id: str
    source_commit: str
    source_tree_sha256: str
    shared_bundle_sha256: str
    skill_count: int
    skills: tuple[PackedSkill, ...]

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": "semiskill.pack/v3",
                "pack": self.pack,
                "generated_at": self.generated_at,
                "scope_id": self.scope_id,
                "permission_label": self.permission_label,
                "scoreboard_snapshot_id": self.scoreboard_snapshot_id,
                "source_commit": self.source_commit,
                "source_tree_sha256": self.source_tree_sha256,
                "shared_bundle_sha256": self.shared_bundle_sha256,
                "skill_count": self.skill_count,
                "skills": [asdict(skill) for skill in self.skills],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"


def _write_approved_file(root: Path, relative: str, text: str) -> None:
    path = safe_relative_path(relative)
    destination = root.joinpath(*path.parts)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(text.encode("utf-8"))


def _missing_shared_references(files: tuple) -> tuple[str, ...]:
    available = {item.path for item in files}
    referenced = {
        reference
        for item in files
        for reference in _SHARED_REF.findall(item.text)
    }
    return tuple(sorted(reference for reference in referenced if reference not in available))


def _canonical_shared_snapshot(files: tuple, *, slug: str) -> tuple[tuple[str, str], ...]:
    shared = {
        item.path: item.text
        for item in files
        if item.path.split("/", 1)[0].casefold() == "_shared"
    }
    expected = set(_CANONICAL_SHARED_PATHS)
    actual = set(shared)
    if actual != expected:
        details = []
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unexpected " + ", ".join(extra))
        raise PackRefused(
            f"{slug}: approved payload does not contain the exact canonical shared set"
            + (": " + "; ".join(details) if details else "")
        )
    return tuple((path, shared[path]) for path in _CANONICAL_SHARED_PATHS)


def _shared_snapshot_sha256(snapshot: tuple[tuple[str, str], ...]) -> str:
    encoded = json.dumps(
        dict(snapshot), sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _markdown_cell(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _zip_release(pack_root: Path, zip_path: Path, pack_name: str) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, strict_timestamps=True) as zf:
        zf.comment = b""
        for source in sorted(
            (path for path in pack_root.rglob("*") if path.is_file()),
            key=lambda path: path.relative_to(pack_root).as_posix(),
        ):
            relative = source.relative_to(pack_root).as_posix()
            safe_relative_path(relative)
            info = zipfile.ZipInfo(f"{pack_name}/{relative}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.extra = b""
            info.comment = b""
            zf.writestr(info, source.read_bytes())


def build_pack(
    *,
    store: ArtifactStore,
    scope: ExportScope,
    out_dir: str | Path,
    pack_name: str = PACK_NAME,
    make_zip: bool = True,
) -> tuple[Path, PackManifest]:
    """Build a complete release from exact frozen publications in ``scope``."""
    try:
        safe_path_segment(pack_name, label="pack name")
    except ExportRefused as exc:
        raise PackRefused(str(exc)) from exc
    if not isinstance(scope, ExportScope):
        raise PackRefused("an explicit export scope is required")
    if not scope.publications:
        raise PackRefused("the export scope contains no published skills")
    try:
        catalog = collect(store, scope=scope)
    except CatalogRefused as exc:
        raise PackRefused(str(exc)) from exc

    packed: list[PackedSkill] = []
    shared_snapshot: tuple[tuple[str, str], ...] | None = None
    for entry in catalog.entries:
        missing = _missing_shared_references(entry.files)
        if missing:
            raise PackRefused(
                f"{entry.slug}: approved payload has unresolved shared dependencies: "
                + ", ".join(missing)
            )
        entry_shared = _canonical_shared_snapshot(entry.files, slug=entry.slug)
        if shared_snapshot is None:
            shared_snapshot = entry_shared
        elif entry_shared != shared_snapshot:
            raise PackRefused(
                f"{entry.slug}: approved payload uses a different canonical shared snapshot"
            )
        skill_file = next(item for item in entry.files if item.path == "SKILL.md")
        packed.append(PackedSkill(
            name=entry.slug,
            title=entry.title,
            description=entry.description,
            role=entry.role,
            level=entry.level,
            function=entry.function,
            version=entry.version,
            sha256=skill_file.sha256.removeprefix("sha256:"),
            bytes_len=skill_file.bytes_len,
            slots=entry.slots,
            verdict=entry.verdict,
            aggregate_safety=entry.aggregate_safety,
            permission_label=entry.permissions_label,
            skill_version_artifact_id=entry.skill_version_id,
            approval_artifact_id=entry.approval_id,
            payload_sha256=entry.payload_sha256,
            automated_review_artifact_id=entry.automated_review_id,
            content_review_artifact_id=entry.content_review_id,
            scan_artifact_ids=entry.scan_artifact_ids,
            files=tuple(PackedFile(item.path, item.sha256, item.bytes_len) for item in entry.files),
        ))

    if shared_snapshot is None:  # Defensive: the non-empty scope/catalog contracts imply this.
        raise PackRefused("the export scope contains no approved shared snapshot")
    manifest = PackManifest(
        pack=pack_name,
        generated_at=scope.generated_at,
        scope_id=scope.scope_id,
        permission_label=scope.permission_label,
        scoreboard_snapshot_id=scope.scoreboard_snapshot_id,
        source_commit=scope.source_commit,
        source_tree_sha256=scope.source_tree_sha256,
        shared_bundle_sha256=_shared_snapshot_sha256(shared_snapshot),
        skill_count=len(packed),
        skills=tuple(packed),
    )
    release_target = Path(out_dir) / f"{pack_name}-release"

    def build(staging: Path) -> None:
        pack_root = staging / pack_name
        pack_root.mkdir(parents=True)
        for entry in catalog.entries:
            skill_root = pack_root / entry.slug
            skill_root.mkdir()
            for approved in entry.files:
                _write_approved_file(skill_root, approved.path, approved.text)
            skill_md, files = load_skill_dir(skill_root)
            rebuilt = build_skill_version(
                skill_md=skill_md,
                actor="pack-verifier",
                permissions_label=entry.permissions_label,
                files=files,
            )
            if payload_fingerprint(rebuilt.payload) != entry.payload_sha256.removeprefix("sha256:"):
                raise PackRefused(f"{entry.slug}: staged bytes do not match the approved payload")

        (pack_root / "MANIFEST.json").write_bytes(manifest.to_json().encode("utf-8"))
        (pack_root / "README-INSTALL.md").write_bytes(
            _install_doc(pack_name, manifest).encode("utf-8")
        )
        (pack_root / "PERSONALIZING.md").write_bytes(
            _personalizing_doc(pack_name).encode("utf-8")
        )
        if make_zip:
            _zip_release(pack_root, staging / f"{pack_name}.zip", pack_name)

    try:
        release_root, _ = atomic_build_tree(
            target=release_target,
            export_kind="pack",
            scope=scope,
            build=build,
        )
    except ExportRefused as exc:
        if isinstance(exc, PackRefused):
            raise
        raise PackRefused(str(exc)) from exc
    return release_root / pack_name, manifest


def _install_doc(pack_name: str, manifest: PackManifest) -> str:
    rows = "\n".join(
        f"| `/{_markdown_cell(skill.name)}` | {_markdown_cell(skill.title)} | "
        f"{_markdown_cell(skill.role or '-')} | {_markdown_cell(skill.level or '-')} | "
        f"{skill.slots} |"
        for skill in manifest.skills
    )
    return f"""# DV skills - install

{manifest.skill_count} exact approved skill folders. No installer or admin rights are required.

Put the `{pack_name}` folder in `~/.cursor/skills/` (Windows:
`%USERPROFILE%\\.cursor\\skills\\`) or `<your repo>/.cursor/skills/`, then reload Cursor.

| Invoke | Skill | Role | Level | Blanks to fill |
|---|---|---|---|---|
{rows}

`MANIFEST.json` binds every delivered file to export scope `{manifest.scope_id}` and records the
exact approval, review, scan, payload-hash, permission-label, and source-snapshot provenance.
Shared bundle `{manifest.shared_bundle_sha256}` is vendored under every skill root. Each skill is
self-contained; these are frozen approval-bound support copies, not a global writable store.

Verification describes these exact bytes at publication time. It is not a runtime guarantee, and
Cursor does not enforce the declared tool list. Read a procedure before relying on it.
"""


def _personalizing_doc(pack_name: str) -> str:
    return f"""# Making these yours

Fill `[[FILL: ...]]` slots from your repository, but never place credentials, customer data, or
export-controlled content in a shared skill. The source pack is authored once, while installed
`_shared/` support files are deliberately vendored per skill; editing one installed copy does not
update siblings. Save a personalized fork under a new slug so it cannot be confused with the
approved `{pack_name}` payload. A changed fork no longer carries this pack's verification badge and
must pass the normal submission, scan, review, and human-approval gates before it can be shared.
"""
