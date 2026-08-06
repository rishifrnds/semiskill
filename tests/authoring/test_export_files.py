import hashlib
import json

import pytest

from semiskill.authoring.export_files import atomic_build_tree
from semiskill.authoring.export_scope import ExportRefused
from tests.support import public_export_scope


def test_manifest_hashes_every_delivered_file_and_stamps_scope(pg_dsn, tmp_path):
    from semiskill.artifacts.migrate import apply_migrations
    from semiskill.artifacts.store import PostgresArtifactStore
    apply_migrations(pg_dsn, "semiskill/artifacts/migrations")
    store = PostgresArtifactStore(pg_dsn)
    scope = public_export_scope(store, [])

    target, manifest = atomic_build_tree(
        target=tmp_path / "site", export_kind="site", scope=scope,
        build=lambda root: (root / "index.html").write_bytes(b"<h1>safe</h1>"),
    )
    persisted = json.loads((target / "EXPORT-MANIFEST.json").read_text(encoding="utf-8"))
    assert persisted == manifest
    assert persisted["scope"]["scope_id"] == scope.scope_id
    assert persisted["files"] == [{
        "path": "index.html", "bytes": 13,
        "sha256": "sha256:" + hashlib.sha256(b"<h1>safe</h1>").hexdigest(),
    }]


def test_failed_build_preserves_prior_complete_tree(pg_dsn, tmp_path):
    from semiskill.artifacts.migrate import apply_migrations
    from semiskill.artifacts.store import PostgresArtifactStore
    apply_migrations(pg_dsn, "semiskill/artifacts/migrations")
    scope = public_export_scope(PostgresArtifactStore(pg_dsn), [])
    target = tmp_path / "site"
    atomic_build_tree(
        target=target, export_kind="site", scope=scope,
        build=lambda root: (root / "old.txt").write_text("old", encoding="utf-8"),
    )

    def fail(root):
        (root / "new.txt").write_text("partial", encoding="utf-8")
        raise RuntimeError("boom")

    with pytest.raises(ExportRefused, match="previous complete output was preserved"):
        atomic_build_tree(target=target, export_kind="site", scope=scope, build=fail)
    assert (target / "old.txt").read_text(encoding="utf-8") == "old"
    assert not (target / "new.txt").exists()


def test_rebuild_removes_stale_files(pg_dsn, tmp_path):
    from semiskill.artifacts.migrate import apply_migrations
    from semiskill.artifacts.store import PostgresArtifactStore
    apply_migrations(pg_dsn, "semiskill/artifacts/migrations")
    scope = public_export_scope(PostgresArtifactStore(pg_dsn), [])
    target = tmp_path / "site"
    atomic_build_tree(
        target=target, export_kind="site", scope=scope,
        build=lambda root: (root / "restricted.html").write_text("secret", encoding="utf-8"),
    )
    atomic_build_tree(
        target=target, export_kind="site", scope=scope,
        build=lambda root: (root / "public.html").write_text("public", encoding="utf-8"),
    )
    assert not (target / "restricted.html").exists()
    assert (target / "public.html").exists()


def test_unowned_or_tampered_target_is_never_deleted(pg_dsn, tmp_path):
    from semiskill.artifacts.migrate import apply_migrations
    from semiskill.artifacts.store import PostgresArtifactStore
    apply_migrations(pg_dsn, "semiskill/artifacts/migrations")
    scope = public_export_scope(PostgresArtifactStore(pg_dsn), [])
    target = tmp_path / "site"
    target.mkdir()
    (target / "keep.txt").write_text("mine", encoding="utf-8")
    with pytest.raises(ExportRefused, match="ownership manifest"):
        atomic_build_tree(
            target=target, export_kind="site", scope=scope,
            build=lambda root: (root / "new.txt").write_text("new", encoding="utf-8"),
        )
    assert (target / "keep.txt").read_text(encoding="utf-8") == "mine"
