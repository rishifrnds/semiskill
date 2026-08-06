"""Atomic whole-tree persistence and cryptographic manifests for offline exports."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Callable

from semiskill.authoring.export_scope import ExportRefused, ExportScope

EXPORT_MANIFEST_SCHEMA = "semiskill.export/v1"
EXPORT_MANIFEST_NAME = "EXPORT-MANIFEST.json"


def _tree_sha256(export_kind: str, scope_id: str, files: list[dict]) -> str:
    tree_material = json.dumps(
        {"schema_version": "semiskill.export-tree/v1", "export_kind": export_kind,
         "scope_id": scope_id, "files": files},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(tree_material).hexdigest()


def safe_relative_path(value: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise ExportRefused("export path is invalid")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ExportRefused("export path is invalid")
    return path


def scope_stamp(scope: ExportScope) -> str:
    principal = scope.safe_dict()["principal"]
    return (
        f"permission={scope.permission_label} | principal={principal['principal_ref']} | "
        f"snapshot={scope.scoreboard_snapshot_id} | commit={scope.source_commit} | "
        f"generated={scope.generated_at}"
    )


def _files(root: Path) -> list[Path]:
    rows: list[Path] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        metadata = path.lstat()
        if path.is_symlink() or not stat.S_ISREG(metadata.st_mode):
            if stat.S_ISDIR(metadata.st_mode) and not path.is_symlink():
                continue
            raise ExportRefused("export tree contains a link or special filesystem node")
        relative = path.relative_to(root).as_posix()
        safe_relative_path(relative)
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


def verify_export_tree(root: Path, *, expected_kind: str | None = None) -> dict:
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
    scope_id = manifest.get("scope", {}).get("scope_id")
    if (
        not isinstance(scope_id, str)
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
    destination = Path(target)
    if not destination.name or destination.name in {".", ".."}:
        raise ExportRefused("export destination is unsafe")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
        raise ExportRefused("export destination must be a real directory")
    if destination.exists():
        verify_export_tree(destination, expected_kind=export_kind)
    parent = destination.parent.resolve()
    staging = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=parent))
    backup = parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
    manifest: dict | None = None
    moved_old = False
    try:
        build(staging)
        manifest = write_export_manifest(root=staging, export_kind=export_kind, scope=scope)
        if destination.exists():
            os.replace(destination, backup)
            moved_old = True
        try:
            os.replace(staging, destination)
        except Exception:
            if moved_old and backup.exists() and not destination.exists():
                os.replace(backup, destination)
                moved_old = False
            raise
        if moved_old:
            _remove_owned_tree(backup, parent)
        return destination, manifest
    except Exception as exc:
        if staging.exists():
            _remove_owned_tree(staging, parent)
        if isinstance(exc, ExportRefused):
            raise
        raise ExportRefused("export build failed; the previous complete output was preserved") from exc
