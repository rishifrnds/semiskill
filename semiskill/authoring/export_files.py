"""Atomic whole-tree persistence and cryptographic manifests for offline exports."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Callable

from semiskill.authoring.export_scope import ExportRefused, ExportScope

EXPORT_MANIFEST_SCHEMA = "semiskill.export/v1"
EXPORT_MANIFEST_NAME = "EXPORT-MANIFEST.json"
_WINDOWS_DEVICE = re.compile(
    r"(?i)^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$"
)
_SAFE_SEGMENT = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _tree_sha256(export_kind: str, scope_id: str, files: list[dict]) -> str:
    tree_material = json.dumps(
        {"schema_version": "semiskill.export-tree/v1", "export_kind": export_kind,
         "scope_id": scope_id, "files": files},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(tree_material).hexdigest()


def safe_relative_path(value: str) -> PurePosixPath:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 1024
        or "\\" in value
        or ":" in value
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
    ):
        raise ExportRefused("export path is invalid")
    path = PurePosixPath(value)
    if (
        value != path.as_posix()
        or path.is_absolute()
        or any(
            part in {"", ".", ".."}
            or part.endswith((".", " "))
            or _WINDOWS_DEVICE.fullmatch(part)
            for part in path.parts
        )
    ):
        raise ExportRefused("export path is invalid")
    return path


def safe_path_segment(value: str, *, label: str) -> str:
    """Return one portable kebab-case path segment or refuse it."""
    if (
        not isinstance(value, str)
        or len(value) > 128
        or not _SAFE_SEGMENT.fullmatch(value)
        or _WINDOWS_DEVICE.fullmatch(value)
    ):
        raise ExportRefused(f"{label} is not a portable path segment")
    return value


def scope_stamp(scope: ExportScope) -> str:
    return (
        f"scope={scope.scope_id} | permission={scope.permission_label} | "
        f"snapshot={scope.scoreboard_snapshot_id} | commit={scope.source_commit} | "
        f"source-tree={scope.source_tree_sha256} | generated={scope.generated_at}"
    )


def _files(root: Path) -> list[Path]:
    rows: list[Path] = []
    seen: dict[str, tuple[str, str]] = {}
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        metadata = path.lstat()
        if path.is_symlink():
            raise ExportRefused("export tree contains a link or special filesystem node")
        relative = path.relative_to(root).as_posix()
        safe_relative_path(relative)
        folded = relative.casefold()
        kind = "directory" if stat.S_ISDIR(metadata.st_mode) else "file"
        prior = seen.setdefault(folded, (relative, kind))
        if prior != (relative, kind):
            raise ExportRefused("export tree contains case-insensitively colliding paths")
        if kind == "directory":
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise ExportRefused("export tree contains a link or special filesystem node")
        if relative != EXPORT_MANIFEST_NAME:
            rows.append(path)
    return rows


def build_export_manifest(*, root: Path, export_kind: str, scope: ExportScope) -> dict:
    if export_kind not in {"catalog", "site", "pack"}:
        raise ExportRefused("export kind is invalid")
    files = []
    for path in _files(root):
        raw = path.read_bytes()
        files.append({
            "path": path.relative_to(root).as_posix(),
            "bytes": len(raw),
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        })
    return {
        "schema_version": EXPORT_MANIFEST_SCHEMA,
        "export_kind": export_kind,
        "generated_at": scope.generated_at,
        "publication_count": len(scope.publications),
        "tree_sha256": _tree_sha256(export_kind, scope.scope_id, files),
        "scope": scope.safe_dict(),
        "files": files,
    }


def write_export_manifest(*, root: Path, export_kind: str, scope: ExportScope) -> dict:
    manifest = build_export_manifest(root=root, export_kind=export_kind, scope=scope)
    (root / EXPORT_MANIFEST_NAME).write_bytes(
        (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    return manifest


def _remove_owned_tree(path: Path, parent: Path) -> None:
    if path.parent.resolve() != parent.resolve() or path.is_symlink():
        raise ExportRefused("refusing to remove an export path outside its owned parent")
    if path.exists():
        shutil.rmtree(path)


def _scope_id(scope: dict) -> str | None:
    if not isinstance(scope, dict) or not isinstance(scope.get("scope_id"), str):
        return None
    material = dict(scope)
    claimed = material.pop("scope_id")
    raw = json.dumps(
        material, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    observed = "sha256:" + hashlib.sha256(raw).hexdigest()
    return claimed if claimed == observed else None


def verify_export_tree(
    root: Path,
    *,
    expected_kind: str | None = None,
    expected_scope: ExportScope | None = None,
) -> dict:
    manifest_path = root / EXPORT_MANIFEST_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportRefused("existing export directory has no valid ownership manifest") from exc
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != EXPORT_MANIFEST_SCHEMA
        or manifest.get("export_kind") not in {"catalog", "site", "pack"}
        or (expected_kind is not None and manifest.get("export_kind") != expected_kind)
    ):
        raise ExportRefused("existing export directory has a different or invalid owner")
    observed_files = []
    for path in _files(root):
        raw = path.read_bytes()
        observed_files.append({
            "path": path.relative_to(root).as_posix(), "bytes": len(raw),
            "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
        })
    scope = manifest.get("scope")
    scope_id = _scope_id(scope)
    if (
        scope_id is None
        or manifest.get("generated_at") != scope.get("generated_at")
        or manifest.get("publication_count") != len(scope.get("publications", []))
        or (expected_scope is not None and scope != expected_scope.safe_dict())
        or observed_files != manifest.get("files")
        or _tree_sha256(manifest["export_kind"], scope_id, observed_files)
        != manifest.get("tree_sha256")
    ):
        raise ExportRefused("existing export directory was modified outside its manifest")
    return manifest


def atomic_build_tree(
    *,
    target: str | Path,
    export_kind: str,
    scope: ExportScope,
    build: Callable[[Path], None],
) -> tuple[Path, dict]:
    """Build+hash privately, then replace one complete tree with rollback on swap failure."""
    if not isinstance(scope, ExportScope):
        raise ExportRefused("an explicit export scope is required")
    if export_kind not in {"catalog", "site", "pack"}:
        raise ExportRefused("export kind is invalid")
    destination = Path(target)
    if not destination.name or destination.name in {".", ".."}:
        raise ExportRefused("export destination is unsafe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
        raise ExportRefused("export destination must be a real directory")
    had_destination = destination.exists()
    if had_destination:
        verify_export_tree(destination, expected_kind=export_kind)
    parent = destination.parent.resolve()
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=parent))
    backup = parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
    manifest: dict | None = None
    moved_old = False
    committed = False
    try:
        build(staging)
        manifest = write_export_manifest(root=staging, export_kind=export_kind, scope=scope)
        verify_export_tree(staging, expected_kind=export_kind, expected_scope=scope)
        if destination.exists():
            os.replace(destination, backup)
            moved_old = True
        try:
            os.replace(staging, destination)
            committed = True
        except Exception as swap_error:
            if moved_old and backup.exists() and not destination.exists():
                try:
                    os.replace(backup, destination)
                    moved_old = False
                except Exception as restore_error:
                    raise ExportRefused(
                        "export swap failed and the prior complete output could not be restored"
                    ) from restore_error
            raise swap_error
        if moved_old:
            _remove_owned_tree(backup, parent)
        return destination, manifest
    except Exception as exc:
        if staging.exists():
            _remove_owned_tree(staging, parent)
        if isinstance(exc, ExportRefused):
            raise
        if committed:
            raise ExportRefused(
                "new export committed, but cleanup of the prior complete output failed"
            ) from exc
        if had_destination:
            raise ExportRefused(
                "export build failed; the previous complete output was preserved"
            ) from exc
        raise ExportRefused(
            "export build failed; no unverified partial output was published"
        ) from exc
