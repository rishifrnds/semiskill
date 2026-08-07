import json

import pytest

from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.snapshot import (
    SnapshotUnavailable,
    finalize_scoreboard,
    full_input_tree_sha256,
    load_progress,
    load_scoreboard_snapshot,
    write_json_atomic,
)


def _body():
    states = {
        name: 0 for name in (
            "missing", "lint_blocked", "consistency_blocked", "security_pending",
            "security_blocked", "review_pending", "review_blocked", "recheck_ready",
            "approval_rejected", "published", "published_stale", "invalid",
        )
    }
    funnel = {
        "active": 0, "authored": 0, "strict_lint_pass": 0, "security_pass": 0,
        "reviewed": 0, "recheck_ready": 0, "approved": 0, "published": 0,
        "blocked": {"total": 0, "lint": 0, "consistency": 0, "scan": 0,
                    "review": 0, "approval": 0},
    }
    conservation_checks = {
        "registry_partition": True, "active_state_partition": True,
        "role_active_partition": True, "role_published_partition": True,
        "review_partition": True, "approval_publication_partition": True,
        "funnel_bounds": True,
    }
    release_values = {
        "REGISTRY_ACTIVE": (0, 0), "REGISTRY_DECLINED": (0, 0),
        "REGISTRY_ROLES": (0, 0), "ALL_AUTHORED": (0, 0),
        "ALL_STRICT_LINT": (0, 0), "ALL_REVIEWED": (0, 0),
        "ALL_RECHECK_READY": (0, 0), "ALL_APPROVED": (0, 0),
        "ALL_PUBLISHED": (0, 0), "ALL_ROLES_TARGET": (0, 0),
        "CONSISTENCY_ERRORS": (0, 0), "BLOCKERS": (0, 0),
        "ANOMALIES": (0, 0), "CONSERVATION": (1, 1),
    }
    return {
        "scope": {"phase": "test", "expected_active": 0, "expected_declined": 0,
                  "expected_roles": 0, "target_per_role": 1},
        "sources": {
            "repository": {
                "commit": "test-commit", "dirty": False,
                "tree_sha256": "sha256:" + "2" * 64,
            },
            "registry": {
                "path": "specs/skill_registry.json", "sha256": "sha256:" + "3" * 64,
            },
            "skills": {
                "root": "skills", "tree_sha256": "sha256:" + "2" * 64,
                "full_tree_sha256": "sha256:" + "4" * 64,
            },
            "database": {
                "engine": "postgresql", "database_name": "semiskill_test",
                "environment": "test", "identity_sha256": "sha256:" + "1" * 64,
            },
        },
        "registry": {"total": 0, "active": 0, "declined": 0, "roles": 0, "levels": []},
        "funnel": funnel, "exclusive_states": states,
        "conservation": {"passed": True, "checks": conservation_checks},
        "roles": [], "cells": [], "anomalies": {},
        "consistency": {"errors": 0, "warnings": 0, "registry_error": None},
        "release_gate": {"passed": True, "checks": [
            {"code": code, "actual": actual, "expected": expected, "passed": actual == expected}
            for code, (actual, expected) in release_values.items()
        ]},
    }


def test_snapshot_id_binds_observation_time_and_ignores_mapping_order():
    first = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    reordered = dict(reversed(list(_body().items())))
    second = finalize_scoreboard(reordered, generated_at="2026-08-07T00:00:00Z")
    same_time = finalize_scoreboard(reordered, generated_at="2026-08-06T00:00:00Z")
    assert first["snapshot_id"] != second["snapshot_id"]
    assert first["snapshot_id"] == same_time["snapshot_id"]
    assert first["generated_at"] != second["generated_at"]


def test_full_input_tree_hash_includes_top_level_shared_bytes(tmp_path):
    root = tmp_path / "skills"
    shared = root / "_shared"
    shared.mkdir(parents=True)
    source = shared / "review-contract.md"
    source.write_text("first", encoding="utf-8")
    before = full_input_tree_sha256(root)

    source.write_text("second", encoding="utf-8")

    assert full_input_tree_sha256(root) != before


def test_atomic_write_round_trips_a_valid_snapshot(tmp_path):
    snapshot = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    path = tmp_path / "scoreboard.json"
    write_json_atomic(path, snapshot)
    assert load_scoreboard_snapshot(path) == snapshot
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("payload", [None, {}, {"schema_version": "wrong"}])
def test_missing_or_malformed_snapshot_fails_closed(tmp_path, payload):
    path = tmp_path / "scoreboard.json"
    if payload is not None:
        path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotUnavailable):
        load_scoreboard_snapshot(path)


def test_tampered_snapshot_id_fails_closed(tmp_path):
    snapshot = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    snapshot["funnel"]["published"] = 84
    path = tmp_path / "scoreboard.json"
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    with pytest.raises(SnapshotUnavailable, match="snapshot_id"):
        load_scoreboard_snapshot(path)


def test_self_hashed_but_semantically_fabricated_counts_fail_closed():
    body = _body()
    body["registry"]["active"] = 84
    body["scope"]["expected_active"] = 84
    with pytest.raises(SnapshotUnavailable, match="registry counts"):
        finalize_scoreboard(body, generated_at="2026-08-06T00:00:00Z")


def test_progress_must_reference_the_loaded_scoreboard(tmp_path):
    snapshot = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    path = tmp_path / "progress.json"
    write_json_atomic(path, {
        "schema_version": "semiskill.progress/v1",
        "scoreboard_snapshot_id": snapshot["snapshot_id"],
        "generated_at": "2026-08-06T00:00:01Z",
        "workers": [],
    })
    assert load_progress(path, snapshot["snapshot_id"])["workers"] == []
    with pytest.raises(SnapshotUnavailable, match="does not match"):
        load_progress(path, "sha256:" + "0" * 64)


def test_progress_workers_require_typed_assignment_attempt_and_timestamps(tmp_path):
    snapshot = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    path = tmp_path / "progress.json"
    write_json_atomic(path, {
        "schema_version": "semiskill.progress/v1",
        "scoreboard_snapshot_id": snapshot["snapshot_id"],
        "generated_at": "2026-08-06T00:00:01Z",
        "workers": [{"worker_id": "qa-1", "slug": "dv-one", "stage": "recheck",
                     "attempt": "2", "started_at": "2026-08-06T00:00:00Z",
                     "updated_at": "2026-08-06T00:00:01Z"}],
    })
    with pytest.raises(SnapshotUnavailable, match="attempt"):
        load_progress(path, snapshot["snapshot_id"])


@pytest.mark.parametrize("generated_at", ["", "yesterday", "2026-08-06T00:00:00"])
def test_scoreboard_requires_an_aware_rfc3339_generation_time(generated_at):
    with pytest.raises(SnapshotUnavailable, match="generated_at"):
        finalize_scoreboard(_body(), generated_at=generated_at)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("engine", ""),
        ("database_name", ""),
        ("environment", "unknown"),
        ("identity_sha256", "sha256:not-a-hash"),
    ],
)
def test_scoreboard_requires_complete_database_provenance(field, value):
    body = _body()
    body["sources"]["database"][field] = value
    with pytest.raises(SnapshotUnavailable, match="database"):
        finalize_scoreboard(body, generated_at="2026-08-06T00:00:00Z")


def test_scoreboard_environment_must_match_the_database_identity():
    body = _body()
    body["sources"]["database"]["environment"] = "development"
    with pytest.raises(SnapshotUnavailable, match="development snapshot"):
        finalize_scoreboard(body, generated_at="2026-08-06T00:00:00Z")


@pytest.mark.parametrize(("field", "value"), [("commit", ""), ("dirty", "false")])
def test_scoreboard_requires_typed_repository_provenance(field, value):
    body = _body()
    body["sources"]["repository"][field] = value
    with pytest.raises(SnapshotUnavailable, match="repository"):
        finalize_scoreboard(body, generated_at="2026-08-06T00:00:00Z")


def test_scoreboard_registry_levels_must_be_unique_and_match_active_cells():
    body = _body()
    body["registry"]["levels"] = ["senior", "senior"]
    with pytest.raises(SnapshotUnavailable, match="levels"):
        finalize_scoreboard(body, generated_at="2026-08-06T00:00:00Z")


def test_progress_requires_aware_rfc3339_timestamps(tmp_path):
    snapshot = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    path = tmp_path / "progress.json"
    write_json_atomic(path, {
        "schema_version": "semiskill.progress/v1",
        "scoreboard_snapshot_id": snapshot["snapshot_id"],
        "generated_at": "not-a-time",
        "workers": [],
    })
    with pytest.raises(SnapshotUnavailable, match="generated_at"):
        load_progress(path, snapshot["snapshot_id"])


def test_database_identity_is_sanitized_and_stable(monkeypatch):
    monkeypatch.delenv("SEMISKILL_APPROVAL_DATABASE_URL", raising=False)
    monkeypatch.delenv("SEMISKILL_REVIEW_COORDINATOR_DATABASE_URL", raising=False)
    monkeypatch.delenv("SEMISKILL_EXPORT_DATABASE_URL", raising=False)
    store = PostgresArtifactStore(
        "postgresql://private-user:super-secret@db.internal:5433/semiskill_dev?sslmode=require"
    )
    identity = store.database_identity(environment="development")
    encoded = json.dumps(identity, sort_keys=True)
    assert identity["database_name"] == "semiskill_dev"
    assert identity["engine"] == "postgresql"
    assert identity["identity_sha256"].startswith("sha256:")
    assert "super-secret" not in encoded and "private-user" not in encoded
