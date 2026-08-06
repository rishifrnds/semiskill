"""Pack-builder tests.

The load-bearing ones are `test_packed_bytes_are_identical_to_the_source` and
`test_pack_refuses_when_the_source_has_drifted` — together they are the entire integrity claim:
what an engineer installs is what passed the gate.
"""
import json
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.pack import PackRefused, build_pack
from tests.support import publish_wave_sources

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
            f"  semiskill-function: design-verification\n  semiskill-role: dv-engineer\n"
            f"  semiskill-level: intermediate\n  semiskill-version: 1.0.0\n---\n{body}")


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "skills"
    for name in ("dv-alpha", "dv-beta"):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(skill_md(name), encoding="utf-8")
    shared = root / "_shared"
    shared.mkdir()
    (shared / "notes.md").write_text("# Shared\n\nReferenced by several skills.\n", encoding="utf-8")
    return root


@pytest.mark.integration
def test_pack_contains_every_published_skill(pg_store, pg_dsn, source, tmp_path):
    publish_wave_sources(pg_store, source)
    root, manifest = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist",
                                generated_at="2026-08-05")
    assert manifest.skill_count == 2
    assert (root / "dv-alpha" / "SKILL.md").exists()
    assert (root / "dv-beta" / "SKILL.md").exists()


@pytest.mark.integration
def test_packed_bytes_are_identical_to_the_source(pg_store, pg_dsn, source, tmp_path):
    """Packaging places bytes; it never re-serialises them (ADR-008)."""
    publish_wave_sources(pg_store, source)
    root, manifest = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    for s in manifest.skills:
        packed = (root / s.name / "SKILL.md").read_bytes()
        original = (source / s.name / "SKILL.md").read_bytes()
        assert packed == original
        import hashlib
        assert hashlib.sha256(packed).hexdigest() == s.sha256


@pytest.mark.integration
def test_pack_refuses_when_the_source_has_drifted(pg_store, pg_dsn, source, tmp_path):
    """Shipping content that changed after it was scanned would give it a badge it did not earn."""
    publish_wave_sources(pg_store, source)
    p = source / "dv-alpha" / "SKILL.md"
    p.write_text(p.read_text(encoding="utf-8") + "\nAn edit made after publication.\n",
                 encoding="utf-8")
    with pytest.raises(PackRefused) as e:
        build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    assert "changed since it published" in str(e.value)


@pytest.mark.integration
def test_unpublished_skills_are_excluded(pg_store, pg_dsn, source, tmp_path):
    """A skill blocked by the pipeline must not be able to reach an engineer's machine."""
    publish_wave_sources(pg_store, source)
    blocked = source / "dv-blocked"
    blocked.mkdir()
    (blocked / "SKILL.md").write_text(skill_md("dv-blocked", tools="Read Bash"), encoding="utf-8")

    root, manifest = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    names = {s.name for s in manifest.skills}
    assert "dv-blocked" not in names and names == {"dv-alpha", "dv-beta"}
    assert not (root / "dv-blocked").exists()


@pytest.mark.integration
def test_pack_refuses_when_nothing_is_published(pg_store, source, tmp_path):
    with pytest.raises(PackRefused):
        build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")


@pytest.mark.integration
def test_directory_name_equals_frontmatter_name(pg_store, pg_dsn, source, tmp_path):
    """Cursor resolves a skill by its directory; a mismatch means it silently does not load."""
    publish_wave_sources(pg_store, source)
    root, manifest = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    for s in manifest.skills:
        text = (root / s.name / "SKILL.md").read_text(encoding="utf-8")
        assert f"name: {s.name}\n" in text


@pytest.mark.integration
def test_pack_ships_docs_shared_files_and_the_body_linter(pg_store, pg_dsn, source, tmp_path):
    publish_wave_sources(pg_store, source)
    root, _ = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")

    assert (root / "README-INSTALL.md").exists()
    assert (root / "PERSONALIZING.md").exists()
    assert (root / "_shared" / "notes.md").exists()
    linter = root / "tools" / "lint_body.py"
    assert linter.exists()
    # it must still be the standalone, stdlib-only file the engineer can actually run
    assert "import yaml" not in linter.read_text(encoding="utf-8")

    install = (root / "README-INSTALL.md").read_text(encoding="utf-8")
    assert ".cursor/skills/" in install
    assert "not a runtime guarantee" in install


@pytest.mark.integration
def test_manifest_records_verdict_and_checksums(pg_store, pg_dsn, source, tmp_path):
    publish_wave_sources(pg_store, source)
    root, _ = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    data = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    assert data["skill_count"] == 2
    for s in data["skills"]:
        assert s["verdict"] == "approve"
        assert s["aggregate_safety"] == 1.0
        assert len(s["sha256"]) == 64
        assert s["slots"] >= 1


@pytest.mark.integration
def test_zip_is_written_and_contains_the_pack(pg_store, pg_dsn, source, tmp_path):
    import zipfile
    publish_wave_sources(pg_store, source)
    build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    z = tmp_path / "dist" / "semiskill-dv.zip"
    assert z.exists()
    with zipfile.ZipFile(z) as zf:
        names = zf.namelist()
    assert "semiskill-dv/dv-alpha/SKILL.md" in names
    assert "semiskill-dv/README-INSTALL.md" in names


@pytest.mark.integration
def test_pack_is_deterministic(pg_store, pg_dsn, source, tmp_path):
    publish_wave_sources(pg_store, source)
    _, a = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "d1",
                      generated_at="fixed", make_zip=False)
    _, b = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "d2",
                      generated_at="fixed", make_zip=False)
    assert a.to_json() == b.to_json()


@pytest.mark.integration
def test_a_skill_that_bundles_files_is_not_reported_as_drifted(pg_store, pg_dsn, source, tmp_path):
    """The wave publishes a payload built from the whole directory. Recomputing the hash from
    SKILL.md alone reports false drift on every skill that bundles a reference file."""
    (source / "dv-alpha" / "references").mkdir()
    (source / "dv-alpha" / "references" / "notes.md").write_text("# Notes\n", encoding="utf-8")
    publish_wave_sources(pg_store, source)

    root, manifest = build_pack(store=pg_store, source_root=source, out_dir=tmp_path / "dist")
    assert "dv-alpha" in {s.name for s in manifest.skills}
