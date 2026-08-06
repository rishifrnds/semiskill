"""Scoreboard tests.

The scoreboard's whole value is that it cannot be talked into optimism, so most of these assert that
it stays pessimistic: a skill on disk is not covered, a published skill without an independent
recheck is not gated, and a published skill nobody planned is a failure rather than a bonus.
"""
import json
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.scoreboard import (
    DECLINED, FAILING_LINT, MISSING, PUBLISHED, READY, REVIEWED, UNPUBLISHED,
    build_scoreboard, load_registry, render,
)
from semiskill.capture.intake import build_skill_version, load_skill_dir
from tests.support import append_test_content_review, content_checks, publish_wave_sources

MIG = Path("semiskill/artifacts/migrations")
BODY = ("# Title\n\nA procedure with enough substance to be a skill.\n\n"
        "## Fill this in for our team\n\n| Slot | What |\n|---|---|\n"
        "| where | [[FILL: where our logs land]] |\n\n"
        "## Procedure\n\n1. Use **Grep** to locate the marker, then read a bounded window.\n\n"
        "## Gotchas\n\nThe loudest line is rarely the first failure.\n\n"
        "## Human verification\n\nA wrong answer names a cascade line as the cause.\n"
        + "Filler prose to keep this a realistic length. " * 10)


def skill_md(name, *, tools="Read Grep Glob", role="dv-engineer", level="senior"):
    return (f"---\nname: {name}\ndescription: Does {name}. Use when you need {name}.\n"
            f"allowed-tools: {tools}\nmetadata:\n  semiskill-title: Title of {name}\n"
            f"  semiskill-function: design-verification\n  semiskill-role: {role}\n"
            f"  semiskill-level: {level}\n  semiskill-version: 1.0.0\n---\n{BODY}")


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def write_registry(tmp_path, cells):
    p = tmp_path / "registry.json"
    p.write_text(json.dumps({"cells": cells}, indent=1), encoding="utf-8")
    return p


def write_skill(root, name, **kw):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill_md(name, **kw), encoding="utf-8")
    return d


# ── registry validation ───────────────────────────────────────────────────────

def test_registry_rejects_a_duplicate_slug(tmp_path):
    p = write_registry(tmp_path, [{"slug": "a", "role": "r", "level": "senior"},
                                  {"slug": "a", "role": "r", "level": "junior"}])
    with pytest.raises(ValueError, match="duplicate"):
        load_registry(p)


def test_registry_rejects_a_cell_missing_a_facet(tmp_path):
    p = write_registry(tmp_path, [{"slug": "a", "role": "r"}])
    with pytest.raises(ValueError, match="level"):
        load_registry(p)


# ── the pessimism that makes it useful ────────────────────────────────────────

@pytest.mark.integration
def test_a_skill_on_disk_that_never_published_is_not_covered(pg_store, tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "dv-a")
    reg = write_registry(tmp_path, [{"slug": "dv-a", "role": "dv-engineer", "level": "senior"}])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1)
    assert sb.cells[0].status == UNPUBLISHED
    assert sb.totals[PUBLISHED] == 0
    assert not sb.ok and "0 published of 1 planned" in sb.failures[0]


@pytest.mark.integration
def test_a_missing_skill_is_reported_as_missing(pg_store, tmp_path):
    root = tmp_path / "skills"
    root.mkdir()
    reg = write_registry(tmp_path, [{"slug": "dv-nope", "role": "dv-engineer", "level": "senior"}])
    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1)
    assert sb.cells[0].status == MISSING and sb.totals[MISSING] == 1


@pytest.mark.integration
def test_an_authored_skill_that_fails_lint_is_a_failure(pg_store, tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "dv-bad", tools="Read Bash")          # dangerous tool -> lint error
    reg = write_registry(tmp_path, [{"slug": "dv-bad", "role": "dv-engineer", "level": "senior"}])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1)
    assert sb.cells[0].status == FAILING_LINT
    assert any("fails lint" in f for f in sb.failures)


@pytest.mark.integration
def test_published_counts_and_role_target(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    for n in ("dv-a", "dv-b"):
        write_skill(root, n)
    publish_wave_sources(pg_store, root)
    reg = write_registry(tmp_path, [
        {"slug": "dv-a", "role": "dv-engineer", "level": "senior"},
        {"slug": "dv-b", "role": "dv-engineer", "level": "senior"},
    ])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=2)
    assert sb.totals[PUBLISHED] == 2
    assert sb.roles[0].ok and sb.ok
    assert sb.levels == {"senior": 2}


@pytest.mark.integration
def test_facet_drift_between_the_registry_and_what_published_is_a_failure(pg_store, pg_dsn, tmp_path):
    """This actually happened: a remediation pass re-levelled skills one at a time and collectively
    collapsed the role x level grid onto a single role. Nothing caught it."""
    root = tmp_path / "skills"
    write_skill(root, "dv-a", role="dv-engineer", level="senior")
    publish_wave_sources(pg_store, root)
    reg = write_registry(tmp_path, [
        {"slug": "dv-a", "role": "soc-dv-engineer", "level": "junior"}])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1)
    assert sb.cells[0].drift and "registry says soc-dv-engineer/junior" in sb.cells[0].drift
    assert not sb.ok and any("facet drift" in f for f in sb.failures)


@pytest.mark.integration
def test_declines_do_not_credit_a_role_that_has_not_published_yet(pg_store, tmp_path):
    """A decline explains why a role stops at 4; it must not turn 'not started' into 'finished'."""
    root = tmp_path / "skills"
    write_skill(root, "dv-a")
    reg = write_registry(tmp_path, [
        {"slug": "dv-a", "role": "dv-engineer", "level": "senior"},
        {"slug": "dv-x", "role": "dv-engineer", "level": "staff",
         "declined": {"why": "no distinct task at this level"}},
    ])
    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=2)
    assert sb.roles[0].declined == 1
    assert not sb.roles[0].ok, "nothing is published, so the role cannot be complete"


@pytest.mark.integration
def test_a_declined_cell_is_non_crediting_provenance(pg_store, pg_dsn, tmp_path):
    """A decline remains visible but never substitutes for a published skill."""
    root = tmp_path / "skills"
    write_skill(root, "dv-a")
    publish_wave_sources(pg_store, root)

    with_reason = write_registry(tmp_path, [
        {"slug": "dv-a", "role": "dv-engineer", "level": "senior"},
        {"slug": "dv-x", "role": "dv-engineer", "level": "staff",
         "declined": {"why": "no distinct week-one task at this level"}},
    ])
    sb = build_scoreboard(store=pg_store, registry_path=with_reason, skills_root=root, target=2)
    assert sb.roles[0].declined == 1 and not sb.roles[0].ok and not sb.ok
    assert sb.cells[1].status == DECLINED and sb.cells[1].declined_why

    (tmp_path / "registry.json").write_text(json.dumps({"cells": [
        {"slug": "dv-a", "role": "dv-engineer", "level": "senior"},
        {"slug": "dv-x", "role": "dv-engineer", "level": "staff", "declined": {}},
    ]}), encoding="utf-8")
    sb2 = build_scoreboard(store=pg_store, registry_path=tmp_path / "registry.json",
                           skills_root=root, target=2)
    assert sb2.roles[0].declined == 0 and not sb2.ok


@pytest.mark.integration
def test_published_exact_chain_is_independently_recheck_ready(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "dv-a")
    publish_wave_sources(pg_store, root)
    reg = write_registry(tmp_path, [{"slug": "dv-a", "role": "dv-engineer", "level": "senior"}])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1,
                          strict_gate=True)
    assert sb.cells[0].gate == READY and sb.ok


@pytest.mark.integration
def test_an_adversarial_review_is_reviewed_not_ready(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    directory = write_skill(root, "dv-a")
    skill_md, files = load_skill_dir(directory)
    skill_version = pg_store.append(build_skill_version(
        skill_md=skill_md, actor="test-author", permissions_label="public", files=files,
    ))
    append_test_content_review(
        pg_store,
        skill_version,
        phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3",
        run_id="test-run",
        batch_id="test-batch",
        reviewer_identity="test-reviewer",
        fixer_identity="test-fixer",
        checks=content_checks(),
        findings=[],
    )
    reg = write_registry(tmp_path, [{"slug": "dv-a", "role": "dv-engineer", "level": "senior"}])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1,
                          strict_gate=True)
    assert sb.cells[0].status == UNPUBLISHED
    assert sb.cells[0].gate == REVIEWED and not sb.ok


@pytest.mark.integration
def test_a_published_skill_missing_from_the_registry_is_a_failure(pg_store, pg_dsn, tmp_path):
    """Catalog drift in the other direction: something reached engineers that nobody planned."""
    root = tmp_path / "skills"
    write_skill(root, "dv-a")
    write_skill(root, "dv-surprise")
    publish_wave_sources(pg_store, root)
    reg = write_registry(tmp_path, [{"slug": "dv-a", "role": "dv-engineer", "level": "senior"}])

    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1)
    assert sb.unregistered == ("dv-surprise",)
    assert any("not in the registry" in f for f in sb.failures)


@pytest.mark.integration
def test_render_styles(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    write_skill(root, "dv-a")
    publish_wave_sources(pg_store, root)
    reg = write_registry(tmp_path, [
        {"slug": "dv-a", "role": "dv-engineer", "level": "senior"},
        {"slug": "dv-b", "role": "vip-engineer", "level": "staff"},
    ])
    sb = build_scoreboard(store=pg_store, registry_path=reg, skills_root=root, target=1,
                          generated_at="2026-08-05")

    text = render(sb, style="text")
    assert "dv-engineer" in text and "SHORT" in text and "FAILURES" in text

    md = render(sb, style="markdown")
    assert md.startswith("### Catalog coverage") and "| vip-engineer |" in md

    data = json.loads(render(sb, style="json"))
    assert data["ok"] is False and data["totals"]["published"] == 1
    assert {c["slug"] for c in data["cells"]} == {"dv-a", "dv-b"}
