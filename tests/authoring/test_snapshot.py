import json

import pytest

from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.snapshot import (
    SnapshotUnavailable,
    finalize_scoreboard,
    load_progress,
    load_scoreboard_snapshot,
    write_json_atomic,
)


def _body():
    return {
        "scope": {"phase": "dv-84", "expected_active": 84},
        "sources": {"database": {"database_name": "semiskill"}},
        "registry": {"active": 84, "declined": 20, "roles": 16},
        "funnel": {"authored": 84, "published": 0},
        "conservation": {"passed": True, "checks": {}},
        "roles": [],
        "cells": [],
        "anomalies": {},
        "release_gate": {"passed": False, "checks": []},
    }


def test_snapshot_id_ignores_observation_time_and_mapping_order():
    first = finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")
    reordered = dict(reversed(list(_body().items())))
    second = finalize_scoreboard(reordered, generated_at="2026-08-07T00:00:00Z")
    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["generated_at"] != second["generated_at"]


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


def test_database_identity_is_sanitized_and_stable():
    store = PostgresArtifactStore(
        "postgresql://private-user:super-secret@db.internal:5433/semiskill_dev?sslmode=require"
    )
    identity = store.database_identity(environment="development")
    encoded = json.dumps(identity, sort_keys=True)
    assert identity["database_name"] == "semiskill_dev"
    assert identity["engine"] == "postgresql"
    assert identity["identity_sha256"].startswith("sha256:")
    assert "super-secret" not in encoded and "private-user" not in encoded
