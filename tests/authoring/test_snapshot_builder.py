import json
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.snapshot import build_scoreboard_snapshot
from tests.support import publish_wave_sources

MIGRATIONS = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIGRATIONS)
    return PostgresArtifactStore(pg_dsn)


def _skill(slug: str, *, role="dv-engineer", level="senior") -> str:
    return f"""---
name: {slug}
description: Review {slug}. Use when exact evidence needs bounded verification.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: {slug}
  semiskill-function: design-verification
  semiskill-role: {role}
  semiskill-level: {level}
  semiskill-version: 1.0.0
  semiskill-owner: dv-guild
  semiskill-tags: evidence, review
---
# {slug}

## Procedure

1. Read a bounded evidence window and record the exact source location.
2. Compare the observed value with the documented expected value.

## Gotchas

Do not infer missing evidence.

## Human verification

A reviewer checks the cited source and conclusion.
"""


def _registry(path: Path, cells: list[dict], target=1) -> Path:
    path.write_text(json.dumps({"target_per_role": target, "cells": cells}), encoding="utf-8")
    return path


@pytest.mark.integration
def test_snapshot_reconciles_exact_published_chain_and_non_crediting_decline(store, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-one"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(_skill("dv-one"), encoding="utf-8")
    fixture = publish_wave_sources(store, root)[0]
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
        {"slug": "declined-x", "role": "dv-engineer", "level": "n/a",
         "declined": {"why": "provenance only"}},
    ])

    snapshot = build_scoreboard_snapshot(
        store=store,
        registry_path=registry,
        skills_root=root,
        generated_at="2026-08-06T00:00:00Z",
        expected_active=1,
        expected_declined=1,
        expected_roles=1,
        target_per_role=1,
        environment="test",
        source_commit="test-commit",
        repository_dirty=False,
    )

    assert snapshot["registry"] == {"total": 2, "active": 1, "declined": 1,
                                    "roles": 1, "levels": ["senior"]}
    assert snapshot["funnel"]["published"] == 1
    assert snapshot["roles"][0]["published"] == 1
    assert snapshot["roles"][0]["declined_provenance"] == 1
    cell = next(c for c in snapshot["cells"] if c["slug"] == "dv-one")
    assert cell["state"] == "published"
    assert cell["artifacts"]["approval_id"] == str(fixture.approval.artifact_id)
    assert cell["artifacts"]["content_review_id"] == str(fixture.content_review.artifact_id)
    assert cell["artifacts"]["scan_artifact_ids"] == [str(s.artifact_id) for s in fixture.scans]


@pytest.mark.integration
def test_repository_84_snapshot_conserves_registry_funnel_and_roles(store, pg_dsn):
    snapshot = build_scoreboard_snapshot(
        store=store,
        registry_path="specs/skill_registry.json",
        skills_root="skills",
        generated_at="2026-08-06T00:00:00Z",
        environment="test",
        source_commit="test-commit",
        repository_dirty=False,
    )

    assert snapshot["registry"]["active"] == 84
    assert snapshot["registry"]["declined"] == 20
    assert snapshot["registry"]["roles"] == 16
    assert snapshot["funnel"]["authored"] == 84
    assert snapshot["funnel"]["published"] == 0
    assert len(snapshot["cells"]) == 104
    assert sum(snapshot["exclusive_states"].values()) == 84
    assert sum(role["active"] for role in snapshot["roles"]) == 84
    assert sum(role["published"] for role in snapshot["roles"]) == 0
    assert snapshot["sources"]["database"]["database_name"].endswith("_test")
    assert snapshot["anomalies"]["unregistered_authored"] == []


@pytest.mark.integration
def test_source_edit_is_published_stale_without_rewriting_frozen_badge(store, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-one"
    d.mkdir(parents=True)
    skill_path = d / "SKILL.md"
    skill_path.write_text(_skill("dv-one"), encoding="utf-8")
    publish_wave_sources(store, root)
    skill_path.write_text(_skill("dv-one") + "\nA later source edit.\n", encoding="utf-8")
    registry = _registry(tmp_path / "registry.json", [
        {"slug": "dv-one", "role": "dv-engineer", "level": "senior"},
    ])

    snapshot = build_scoreboard_snapshot(
        store=store, registry_path=registry, skills_root=root,
        generated_at="2026-08-06T00:00:00Z", expected_active=1, expected_declined=0,
        expected_roles=1, target_per_role=1, environment="test",
        source_commit="test-commit", repository_dirty=True,
    )

    cell = snapshot["cells"][0]
    assert cell["state"] == "published_stale"
    assert cell["stage_flags"]["published"] is False
    assert snapshot["anomalies"]["stale_source_hashes"] == ["dv-one"]
    assert snapshot["funnel"]["published"] == 0
