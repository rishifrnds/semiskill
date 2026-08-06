"""Queue-only wave tests: capture, scan, reconcile, and stop before human approval."""
import json
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.gate import make_content_review
from semiskill.context.retrieve import search_catalog
from semiskill.wave import (
    AWAITING_APPROVAL,
    AWAITING_REVIEW,
    BLOCKED,
    CHANGES_REQUESTED,
    REVIEW_BLOCKED,
    WOULD_CAPTURE,
    load_wave,
    payload_hash,
    render_report,
    run_wave,
    write_wave_report,
)

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


BODY = """
# Title

A real procedure with enough text to be a skill rather than a note.

## Fill this in for our team

| Slot | What to fill in |
|---|---|
| where | [[FILL: where our logs land]] |

## Procedure

1. Use **Grep** to locate the first marker, then read a bounded window.
2. Classify what you find and name the next artifact to inspect.

## Gotchas

The loudest line is rarely the first failure.

## Human verification

A wrong answer names a cascade line as the cause.
""" + ("Filler prose to keep the body a realistic length. " * 10)


def skill_md(name: str, *, body=BODY, tools="Read Grep Glob"):
    return (
        f"---\nname: {name}\ndescription: Does {name}. Use when you need {name}.\n"
        f"allowed-tools: {tools}\nmetadata:\n  semiskill-title: {name}\n"
        "  semiskill-function: design-verification\n  semiskill-role: dv-engineer\n"
        "  semiskill-level: intermediate\n  semiskill-version: 1.0.0\n---\n"
        f"{body}"
    )


def write_skill(root, name, **kwargs):
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(skill_md(name, **kwargs), encoding="utf-8")
    return directory


def clean_security(_submission):
    return {"findings": []}


def checks():
    return {
        "strict_lint": {"passed": True, "evidence": "lint:1.000"},
        "consistency": {"passed": True, "evidence": "consistency:0"},
        "source_hash": {"passed": True, "evidence": "hash:matched"},
        "artifact_reconciliation": {"passed": True, "evidence": "refs:matched"},
    }


def append_ready_review(store, skill_version, *, findings=()):
    review = make_content_review(
        skill_version=skill_version,
        phase="recheck",
        prompt_version="P5-RECHECK-CALIBRATED@2",
        run_id=f"run:{skill_version.artifact_id}",
        batch_id="batch-1",
        attempt=1,
        reviewer_identity=f"reviewer:{skill_version.artifact_id}",
        fixer_identity=f"fixer:{skill_version.artifact_id}",
        checks=checks(),
        findings=findings,
    )
    return store.append(review)


def run(store, dsn, root, **kwargs):
    return run_wave(
        store=store,
        dsn=dsn,
        items=load_wave(root),
        security_audit_runner=clean_security,
        **kwargs,
    )


def test_load_wave_finds_skills_and_hash_is_content_sensitive(tmp_path):
    write_skill(tmp_path, "dv-a")
    write_skill(tmp_path, "dv-b")
    first = load_wave(tmp_path)
    assert [item.slug for item in first] == ["dv-a", "dv-b"]
    assert first[0].payload_sha256 == load_wave(tmp_path)[0].payload_sha256
    write_skill(tmp_path, "dv-a", body=BODY + "\nChanged.\n")
    assert load_wave(tmp_path)[0].payload_sha256 != first[0].payload_sha256


def test_hash_ignores_store_fields_but_includes_exact_skill_source():
    a = {"slug": "s", "skill_md": "---\nname: s\n---\nb", "body": "b", "files": {}}
    b = dict(a, actor="different", artifact_id="different")
    assert payload_hash(a) == payload_hash(b)
    assert payload_hash(a) != payload_hash({**a, "skill_md": "---\nname: 's'\n---\nb"})


def test_embedded_review_metadata_is_refused_before_scanning(tmp_path):
    directory = write_skill(tmp_path, "dv-a")
    (directory / "REVIEW.json").write_text('{"ready":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="governance metadata must not be embedded"):
        load_wave(tmp_path)


def test_dry_run_writes_nothing(tmp_path):
    write_skill(tmp_path, "dv-a")

    class Exploding:
        def __getattr__(self, _name):
            raise AssertionError("dry run must not touch the store")

    report = run_wave(
        store=Exploding(), dsn="postgresql://unused", items=load_wave(tmp_path), dry_run=True,
    )
    assert report.items[0].status == WOULD_CAPTURE and report.ok


@pytest.mark.integration
def test_clean_wave_captures_and_scans_but_does_not_publish(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-wave-one")
    report = run(pg_store, pg_dsn, tmp_path)

    item = report.items[0]
    assert item.status == AWAITING_REVIEW and item.skill_version_id
    assert item.automated_review_id and len(item.scan_artifact_ids) == 5
    judge = pg_store.get(item.scan_artifact_ids[-1])
    assert judge.payload["stage"] == 5 and judge.payload["status"] == "not_sampled"
    assert pg_store.by_type(ArtifactType.APPROVAL) == []
    assert search_catalog(dsn=pg_dsn, principal=["public"]) == []
    assert report.counts["approvals-created"] == report.counts["published"] == 0


@pytest.mark.integration
def test_ready_candidate_returns_exact_inputs_and_stops_at_approval(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-ready")
    first = run(pg_store, pg_dsn, tmp_path).items[0]
    skill_version = pg_store.get(first.skill_version_id)
    content_review = append_ready_review(pg_store, skill_version)

    second = run(pg_store, pg_dsn, tmp_path)
    item = second.items[0]

    assert item.status == AWAITING_APPROVAL and item.gate == "recheck-ready"
    assert item.content_review_id == str(content_review.artifact_id)
    assert item.automated_review_id and item.scan_artifact_ids
    assert pg_store.by_type(ArtifactType.APPROVAL) == []
    assert search_catalog(dsn=pg_dsn, principal=["public"]) == []


@pytest.mark.integration
def test_rerun_reuses_exact_version_and_security_chain(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-idempotent")
    first = run(pg_store, pg_dsn, tmp_path).items[0]
    before = {
        artifact_type: len(pg_store.by_type(artifact_type))
        for artifact_type in (ArtifactType.SKILL_VERSION, ArtifactType.SCAN_RUN,
                              ArtifactType.INJECTION_TEST, ArtifactType.REVIEW)
    }
    second = run(pg_store, pg_dsn, tmp_path).items[0]
    after = {artifact_type: len(pg_store.by_type(artifact_type)) for artifact_type in before}
    assert second.skill_version_id == first.skill_version_id
    assert second.automated_review_id == first.automated_review_id
    assert before == after


@pytest.mark.integration
def test_open_blocker_is_visible_and_blocks_approval_queue(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-blocked-review")
    first = run(pg_store, pg_dsn, tmp_path).items[0]
    skill_version = pg_store.get(first.skill_version_id)
    append_ready_review(pg_store, skill_version, findings=[{
        "finding_id": "F-1", "category": "technical_correctness", "severity": "blocking",
        "evidence": "Step names a nonexistent signal.", "location": "SKILL.md:20",
        "required_change": "Use the registered signal.", "disposition": "open",
    }])
    item = run(pg_store, pg_dsn, tmp_path).items[0]
    assert item.status == REVIEW_BLOCKED and "open blocking" in item.error
    assert pg_store.by_type(ArtifactType.APPROVAL) == []


@pytest.mark.integration
def test_content_edit_invalidates_old_review_hash(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-stale")
    first = run(pg_store, pg_dsn, tmp_path).items[0]
    append_ready_review(pg_store, pg_store.get(first.skill_version_id))
    write_skill(tmp_path, "dv-stale", body=BODY + "\nA source edit.\n")

    changed = run(pg_store, pg_dsn, tmp_path).items[0]

    assert changed.skill_version_id != first.skill_version_id
    assert changed.status == REVIEW_BLOCKED and changed.gate == "stale"
    assert "payload hash" in changed.error


@pytest.mark.integration
def test_dangerous_payload_blocks_in_pipeline(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-dangerous", tools="Read Bash")
    item = run(pg_store, pg_dsn, tmp_path).items[0]
    assert item.status == BLOCKED and item.blocked_at == 1
    assert pg_store.by_type(ArtifactType.APPROVAL) == []


@pytest.mark.integration
def test_nonpassing_aggregate_is_reported_not_silently_queued(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-needs-changes", body=BODY + "\nSee https://example.invalid\n")
    item = run(pg_store, pg_dsn, tmp_path).items[0]
    assert item.status == CHANGES_REQUESTED and item.verdict == "request-changes"
    assert pg_store.by_type(ArtifactType.APPROVAL) == []


def test_ungated_escape_hatch_is_a_tombstone(tmp_path):
    write_skill(tmp_path, "dv-a")
    with pytest.raises(ValueError, match="allow_ungated was removed"):
        run_wave(
            store=None,
            dsn="postgresql://unused",
            items=load_wave(tmp_path),
            allow_ungated=True,
        )


@pytest.mark.integration
def test_report_and_journal_expose_exact_approval_inputs(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-report")
    first = run(pg_store, pg_dsn, tmp_path).items[0]
    append_ready_review(pg_store, pg_store.get(first.skill_version_id))
    journal = tmp_path / "reports" / "journal.jsonl"
    report = run_wave(
        store=pg_store,
        dsn=pg_dsn,
        items=load_wave(tmp_path),
        security_audit_runner=clean_security,
        journal_path=journal,
    )
    data = json.loads(render_report(report, style="json"))
    item = data["items"][0]
    assert item["status"] == AWAITING_APPROVAL
    assert item["skill_version_id"] and item["automated_review_id"] and item["content_review_id"]
    assert item["scan_artifact_ids"]
    assert data["allow_ungated"] is False and data["counts"]["published"] == 0
    assert json.loads(journal.read_text(encoding="utf-8"))["status"] == AWAITING_APPROVAL

    markdown, machine = write_wave_report(report, tmp_path / "out")
    assert "human approval required" in markdown.read_text(encoding="utf-8")
    assert json.loads(machine.read_text(encoding="utf-8"))["counts"]["published"] == 0
