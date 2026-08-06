"""Approval-bound pack materialization tests."""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.pack import PackRefused, build_pack
from semiskill.capture.intake import (
    build_skill_version,
    load_shared_bundle,
    load_skill_dir,
    load_skill_source,
    payload_fingerprint,
)
from tests.support import public_export_scope, publish_test_skill, publish_wave_sources

MIG = Path("semiskill/artifacts/migrations")
BODY = ("# Title\n\nA procedure with enough substance to be a skill.\n\n"
        "## Fill this in for our team\n\n| Slot | What |\n|---|---|\n"
        "| where | [[FILL: where our logs land]] |\n\n"
        "## Procedure\n\n1. Use **Grep** to locate the marker, then read a bounded window.\n\n"
        "## Gotchas\n\nThe loudest line is rarely the first failure.\n\n"
        "## Human verification\n\nA wrong answer names a cascade line as the cause.\n"
        + "Filler prose to keep this a realistic length. " * 10)


def skill_md(name, *, body=BODY, tools="Read Grep Glob"):
    return (f"---\nname: {name}\ndescription: Does {name}. Use when you need {name}.\n"
            f"allowed-tools: {tools}\nmetadata:\n  semiskill-title: Title of {name}\n"
            "  semiskill-function: design-verification\n  semiskill-role: dv-engineer\n"
            "  semiskill-level: intermediate\n  semiskill-version: 1.0.0\n---\n" + body)


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "skills"
    for name in ("dv-alpha", "dv-beta"):
        directory = root / name
        directory.mkdir(parents=True)
        (directory / "SKILL.md").write_text(skill_md(name), encoding="utf-8")
    shared = root / "_shared"
    shared.mkdir()
    (shared / "team-profile.md").write_bytes(b"# Approved shared team profile\n")
    (shared / "failure-signature-schema.md").write_bytes(b"# Approved signature schema\n")
    (shared / "handoff-vocabulary.md").write_bytes(b"# Approved handoff vocabulary\n")
    return root


def published_scope(store, source):
    fixtures = publish_wave_sources(store, source)
    return fixtures, public_export_scope(store, fixtures)


def test_pack_contains_only_scoped_published_skills(pg_store, source, tmp_path):
    fixtures, scope = published_scope(pg_store, source)
    blocked = source / "dv-blocked"
    blocked.mkdir()
    (blocked / "SKILL.md").write_text(skill_md("dv-blocked", tools="Read Bash"), encoding="utf-8")

    root, manifest = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    assert manifest.skill_count == 2
    assert {path.name for path in root.iterdir() if (path / "SKILL.md").exists()} == {
        "dv-alpha", "dv-beta",
    }
    assert not (root / "dv-blocked").exists()
    assert {skill.skill_version_artifact_id for skill in manifest.skills} == {
        str(fixture.skill_version.artifact_id) for fixture in fixtures
    }


def test_pack_uses_frozen_artifact_bytes_after_source_mutation_or_deletion(
    pg_store, source, tmp_path,
):
    fixtures, scope = published_scope(pg_store, source)
    expected = {
        fixture.skill_version.payload["slug"]: fixture.skill_version.payload["skill_md"].encode("utf-8")
        for fixture in fixtures
    }
    (source / "dv-alpha" / "SKILL.md").write_text("changed after approval", encoding="utf-8")
    (source / "dv-beta" / "SKILL.md").unlink()

    root, manifest = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    for skill in manifest.skills:
        delivered = (root / skill.name / "SKILL.md").read_bytes()
        assert delivered == expected[skill.name]
        assert hashlib.sha256(delivered).hexdigest() == skill.sha256


def test_bundled_payload_files_are_exact_and_rebuild_to_the_approved_hash(
    pg_store, source, tmp_path,
):
    nested = source / "dv-alpha" / "references"
    nested.mkdir()
    (nested / "notes.md").write_text("line one\r\nno final newline", encoding="utf-8", newline="")
    fixtures, scope = published_scope(pg_store, source)

    root, manifest = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    fixture = next(item for item in fixtures if item.skill_version.payload["slug"] == "dv-alpha")
    assert (root / "dv-alpha" / "references" / "notes.md").read_bytes() == (
        fixture.skill_version.payload["files"]["references/notes.md"].encode("utf-8")
    )
    skill_md_text, files = load_skill_dir(root / "dv-alpha")
    rebuilt = build_skill_version(skill_md=skill_md_text, actor="test", files=files)
    assert payload_fingerprint(rebuilt.payload) == payload_fingerprint(fixture.skill_version.payload)
    row = next(item for item in manifest.skills if item.name == "dv-alpha")
    assert {item.path for item in row.files} == {
        "SKILL.md",
        "references/notes.md",
        "_shared/failure-signature-schema.md",
        "_shared/handoff-vocabulary.md",
        "_shared/team-profile.md",
    }


def test_repository_shared_tree_is_approval_bound_inside_each_skill_root(
    pg_store, source, tmp_path,
):
    fixtures, scope = published_scope(pg_store, source)
    root, manifest = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    assert not (root / "_shared").exists()
    assert not (root / "tools").exists()
    assert manifest.shared_bundle_sha256 == (
        "sha256:" + load_shared_bundle(source / "_shared").sha256
    )
    for fixture in fixtures:
        slug = fixture.skill_version.payload["slug"]
        assert fixture.skill_version.payload["files"]["_shared/team-profile.md"] == (
            "# Approved shared team profile\n"
        )
        assert (root / slug / "_shared" / "team-profile.md").read_bytes() == (
            b"# Approved shared team profile\n"
        )


def test_pack_refuses_mixed_approved_shared_snapshots_before_write(
    pg_store, source, tmp_path,
):
    first_bundle = load_shared_bundle(source / "_shared")
    first_md, first_files = load_skill_source(source / "dv-alpha", shared_bundle=first_bundle)
    first_version = pg_store.append(build_skill_version(
        skill_md=first_md, files=first_files, actor="test-author", permissions_label="public",
    ))
    first = publish_test_skill(pg_store, first_version)

    (source / "_shared" / "team-profile.md").write_bytes(b"# Later approved profile\n")
    second_bundle = load_shared_bundle(source / "_shared")
    second_md, second_files = load_skill_source(source / "dv-beta", shared_bundle=second_bundle)
    second_version = pg_store.append(build_skill_version(
        skill_md=second_md, files=second_files, actor="test-author", permissions_label="public",
    ))
    second = publish_test_skill(pg_store, second_version)

    scope = public_export_scope(pg_store, [first, second])
    with pytest.raises(PackRefused, match="different canonical shared snapshot"):
        build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


@pytest.mark.parametrize("variant", ["missing", "extra", "case-alias"])
def test_pack_refuses_noncanonical_legacy_shared_sets_before_write(
    pg_store, tmp_path, variant,
):
    files = {
        "_shared/failure-signature-schema.md": "schema\n",
        "_shared/handoff-vocabulary.md": "vocabulary\n",
        "_shared/team-profile.md": "profile\n",
    }
    if variant == "missing":
        del files["_shared/handoff-vocabulary.md"]
    elif variant == "extra":
        files["_shared/future.md"] = "not registered\n"
    else:
        files = {path.replace("_shared/", "_SHARED/"): text for path, text in files.items()}
    version = pg_store.append(build_skill_version(
        skill_md=skill_md(f"dv-{variant}"), files=files, actor="legacy-author",
        permissions_label="public",
    ))
    fixture = publish_test_skill(pg_store, version)
    scope = public_export_scope(pg_store, [fixture])

    with pytest.raises(PackRefused, match="exact canonical shared set"):
        build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    assert not (tmp_path / "dist").exists()


def test_source_capture_refuses_unresolved_shared_dependency(pg_store, source, tmp_path):
    path = source / "dv-alpha" / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nRead `_shared/missing.md`.\n", encoding="utf-8")
    with pytest.raises(ValueError, match="unresolved shared dependencies"):
        published_scope(pg_store, source)
    assert not (tmp_path / "dist" / "semiskill-dv-release").exists()


def test_pack_defensively_refuses_a_legacy_unresolved_shared_payload(pg_store, tmp_path):
    skill = pg_store.append(build_skill_version(
        skill_md=skill_md("dv-legacy", body=BODY + "\nRead `_shared/missing.md`.\n"),
        actor="legacy-author",
        permissions_label="public",
    ))
    fixture = publish_test_skill(pg_store, skill)
    scope = public_export_scope(pg_store, [fixture])
    with pytest.raises(PackRefused, match="unresolved shared dependencies"):
        build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    assert not (tmp_path / "dist" / "semiskill-dv-release").exists()


def test_local_shared_shadow_cannot_override_the_canonical_bundle(pg_store, source):
    path = source / "dv-alpha" / "SKILL.md"
    path.write_text(path.read_text(encoding="utf-8") + "\nRead `_shared/team-profile.md`.\n", encoding="utf-8")
    shared = source / "dv-alpha" / "_shared"
    shared.mkdir()
    (shared / "team-profile.md").write_text("# Shadow support\n", encoding="utf-8")
    with pytest.raises(ValueError, match="shadows the canonical shared bundle"):
        published_scope(pg_store, source)


def test_manifest_is_frozen_to_scope_and_active_approval_chain(pg_store, source, tmp_path):
    fixtures, scope = published_scope(pg_store, source)
    fixture = next(item for item in fixtures if item.skill_version.payload["slug"] == "dv-alpha")
    later = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="later-controller",
        actor_kind=ActorKind.AGENT,
        input_refs=[fixture.skill_version.artifact_id],
        payload={"review_kind": "security_aggregate", "schema_version": 1, "stage": 6,
                 "verdict": "reject", "aggregate_safety": 0.0, "judge_required": True,
                 "scan_artifact_ids": []},
    )
    pg_store.append(replace(later, permissions_label=fixture.skill_version.permissions_label))

    root, _ = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    data = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    row = next(item for item in data["skills"] if item["name"] == "dv-alpha")
    assert data["scope_id"] == scope.scope_id
    assert row["approval_artifact_id"] == str(fixture.approval.artifact_id)
    assert row["automated_review_artifact_id"] == str(fixture.automated_review.artifact_id)
    assert row["content_review_artifact_id"] == str(fixture.content_review.artifact_id)
    assert row["scan_artifact_ids"] == [str(scan.artifact_id) for scan in fixture.scans]


def test_zip_is_deterministic_and_covered_by_release_manifest(pg_store, source, tmp_path):
    _, scope = published_scope(pg_store, source)
    first, _ = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "a")
    second, _ = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "b")
    first_zip = first.parent / "semiskill-dv.zip"
    second_zip = second.parent / "semiskill-dv.zip"
    assert first_zip.read_bytes() == second_zip.read_bytes()
    with zipfile.ZipFile(first_zip) as archive:
        assert "semiskill-dv/dv-alpha/SKILL.md" in archive.namelist()
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())
    release = json.loads((first.parent / "EXPORT-MANIFEST.json").read_text(encoding="utf-8"))
    assert "semiskill-dv.zip" in {item["path"] for item in release["files"]}


def test_rebuild_without_zip_removes_stale_zip(pg_store, source, tmp_path):
    _, scope = published_scope(pg_store, source)
    root, _ = build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist")
    assert (root.parent / "semiskill-dv.zip").exists()
    root, _ = build_pack(
        store=pg_store, scope=scope, out_dir=tmp_path / "dist", make_zip=False,
    )
    assert not (root.parent / "semiskill-dv.zip").exists()


def test_empty_scope_and_unsafe_pack_name_are_refused(pg_store, source, tmp_path):
    empty = public_export_scope(pg_store, [])
    with pytest.raises(PackRefused, match="no published skills"):
        build_pack(store=pg_store, scope=empty, out_dir=tmp_path / "dist")
    _, scope = published_scope(pg_store, source)
    with pytest.raises(PackRefused, match="portable path segment"):
        build_pack(store=pg_store, scope=scope, out_dir=tmp_path / "dist", pack_name="../escape")
