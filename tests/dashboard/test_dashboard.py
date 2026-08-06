import json
from pathlib import Path

from dashboard import server
from semiskill.authoring.snapshot import finalize_scoreboard, write_json_atomic
from tests.authoring.test_snapshot import _body


def _snapshot(environment="development", database_name="semiskill_dev"):
    body = _body()
    body["sources"]["database"].update(
        environment=environment,
        database_name=database_name,
    )
    return finalize_scoreboard(body, generated_at="2026-08-06T10:00:00Z")


def test_missing_snapshot_is_explicitly_unavailable(monkeypatch):
    monkeypatch.delenv("SEMISKILL_SCOREBOARD_SNAPSHOT", raising=False)
    monkeypatch.delenv("SEMISKILL_PROGRESS_SNAPSHOT", raising=False)

    signals = server.canonical_snapshot_signals()

    assert signals["scoreboard"]["status"] == "unavailable"
    assert signals["scoreboard"]["snapshot"] is None
    assert signals["progress"]["status"] == "unavailable"
    assert signals["progress"]["snapshot"] is None


def test_valid_scoreboard_and_matching_progress_are_preserved(tmp_path, monkeypatch):
    snapshot = _snapshot()
    scoreboard_path = tmp_path / "scoreboard.json"
    progress_path = tmp_path / "progress.json"
    write_json_atomic(scoreboard_path, snapshot)
    write_json_atomic(progress_path, {
        "schema_version": "semiskill.progress/v1",
        "scoreboard_snapshot_id": snapshot["snapshot_id"],
        "generated_at": "2026-08-06T10:00:01Z",
        "workers": [{
            "worker_id": "review-1", "slug": "dv-one", "stage": "P5",
            "attempt": 2, "started_at": "2026-08-06T09:59:00Z",
            "updated_at": "2026-08-06T10:00:01Z",
        }],
    })
    monkeypatch.setenv("SEMISKILL_ENVIRONMENT", "development")
    monkeypatch.setenv("SEMISKILL_SCOREBOARD_SNAPSHOT", str(scoreboard_path))
    monkeypatch.setenv("SEMISKILL_PROGRESS_SNAPSHOT", str(progress_path))

    signals = server.canonical_snapshot_signals()

    assert signals["scoreboard"] == {
        "status": "available", "observed_at": signals["scoreboard"]["observed_at"],
        "reason": None, "snapshot": snapshot,
    }
    assert signals["progress"]["status"] == "available"
    assert signals["progress"]["snapshot"]["scoreboard_snapshot_id"] == snapshot["snapshot_id"]


def test_environment_mismatch_and_bad_progress_fail_closed(tmp_path, monkeypatch):
    snapshot = _snapshot(environment="test", database_name="semiskill_test")
    scoreboard_path = tmp_path / "scoreboard.json"
    progress_path = tmp_path / "progress.json"
    write_json_atomic(scoreboard_path, snapshot)
    progress_path.write_text(json.dumps({"schema_version": "wrong"}), encoding="utf-8")
    monkeypatch.setenv("SEMISKILL_ENVIRONMENT", "development")
    monkeypatch.setenv("SEMISKILL_SCOREBOARD_SNAPSHOT", str(scoreboard_path))
    monkeypatch.setenv("SEMISKILL_PROGRESS_SNAPSHOT", str(progress_path))

    signals = server.canonical_snapshot_signals()

    assert signals["scoreboard"]["status"] == "unavailable"
    assert signals["scoreboard"]["reason"] == "environment_mismatch"
    assert signals["progress"]["status"] == "unavailable"
    assert signals["progress"]["snapshot"] is None


def test_state_has_no_seed_or_raw_publication_count_fallback(monkeypatch):
    monkeypatch.setattr(server, "repo_signals", lambda: {})
    monkeypatch.setattr(server, "state_files", lambda: {})
    monkeypatch.setattr(server, "runtime_signals", lambda: {
        "checked_at": "now", "docker": "down",
        "db": {"status": "down", "detail": ""},
        "api": {"status": "down", "detail": ""},
    })
    monkeypatch.setattr(server, "canonical_snapshot_signals", lambda: {
        "scoreboard": {"status": "unavailable", "snapshot": None},
        "progress": {"status": "unavailable", "snapshot": None},
    })
    monkeypatch.setattr(server, "redteam_attacks", lambda: [])
    monkeypatch.setattr(server, "adrs", lambda: [])
    monkeypatch.setattr(server, "read_inbox", lambda: [])

    state = server.build_state()

    assert "seeds" not in state
    assert "approvals" not in state["runtime"]["db"]
    assert "catalog" not in state["runtime"]["api"]


def test_dashboard_html_uses_only_canonical_catalog_state():
    html = Path("dashboard/index.html").read_text(encoding="utf-8")

    for retired in ("S.seeds", "seed fixture", "runtime.api.catalog", "X-Principal-Labels"):
        assert retired not in html
    assert "S.scoreboard" in html
    assert "S.progress" in html
    assert "sources.repository.commit" in html
    assert "sources.database.database_name" in html
    assert "setInterval(() => { if (document.visibilityState === 'visible') refresh(); }, 15000)" in html
