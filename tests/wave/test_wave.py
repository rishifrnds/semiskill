"""Wave-driver tests.

The three that matter most are `test_one_malformed_item_does_not_abort_the_wave`,
`test_request_changes_is_reported_not_silent` — the exact failure modes that made `seed_catalog`
unsafe at scale — and the `content gate` block at the bottom, which is the same lesson one level up:
the catalog must not be writable by a skill nobody independently rechecked.

Tests whose subject is publishing *mechanics* (idempotence, supersede, error isolation, reporting)
pass `allow_ungated=True`, because their fixtures deliberately carry no REVIEW.json and the gate is
not what they are measuring. Tests whose subject IS the gate write the record and assert on it.
"""
import json
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.gate import READY, UNREVIEWED
from semiskill.context.retrieve import search_catalog
from semiskill.wave import (
    BLOCKED, CHANGES_REQUESTED, ERROR, GATE_MISSING, GATE_NOT_READY, PUBLISHED, SKIPPED_IDENTICAL,
    SUPERSEDED, WaveAborted, load_wave, payload_hash, render_report, run_wave, write_wave_report,
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


def skill_md(name: str, *, level="intermediate", body=BODY, description=None, tools="Read Grep Glob"):
    description = description or f"Does {name}. Use when you need {name}."
    return (f"---\nname: {name}\ndescription: {description}\n"
            f"allowed-tools: {tools}\n"
            f"metadata:\n  semiskill-title: {name}\n"
            f"  semiskill-function: design-verification\n"
            f"  semiskill-role: dv-engineer\n  semiskill-level: {level}\n"
            f"  semiskill-version: 1.0.0\n---\n{body}")


def write_skill(root, name, **kw):
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(skill_md(name, **kw), encoding="utf-8")
    return d


def write_review(skill_dir, *, ready: bool, why="", **extra):
    """The authoring gate's record: an INDEPENDENT recheck's verdict (tools/collect_wave.py)."""
    record = {"slug": skill_dir.name, "review": {"must_fix": []},
              "recheck": {"agent": f"recheck:{skill_dir.name}", "ready": ready, "why": why}}
    record.update(extra)
    (skill_dir / "REVIEW.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    return skill_dir


# ── loading and hashing (no DB) ───────────────────────────────────────────────

def test_load_wave_finds_every_skill_directory(tmp_path):
    write_skill(tmp_path, "dv-a")
    write_skill(tmp_path, "dv-b")
    (tmp_path / "_shared").mkdir()
    (tmp_path / "_shared" / "notes.md").write_text("shared, not a skill", encoding="utf-8")
    items = load_wave(tmp_path)
    assert [i.slug for i in items] == ["dv-a", "dv-b"]        # _shared has no SKILL.md
    assert all(i.payload_sha256 for i in items)


def test_hash_is_stable_and_content_sensitive(tmp_path):
    write_skill(tmp_path, "dv-a")
    first = load_wave(tmp_path)[0]
    assert load_wave(tmp_path)[0].payload_sha256 == first.payload_sha256
    write_skill(tmp_path, "dv-a", body=BODY + "\nOne more line.\n")
    assert load_wave(tmp_path)[0].payload_sha256 != first.payload_sha256


def test_review_metadata_never_changes_installable_payload_or_hash(tmp_path):
    skill_dir = write_skill(tmp_path, "dv-a")
    write_review(skill_dir, ready=False, why="initial review")
    first = load_wave(tmp_path)[0]

    write_review(skill_dir, ready=True, why="a later governance decision")
    second = load_wave(tmp_path)[0]

    assert "REVIEW.json" not in first.files
    assert "REVIEW.json" not in second.files
    assert second.payload_sha256 == first.payload_sha256


def test_hash_ignores_fields_the_store_adds():
    a = {"slug": "s", "name": "n", "body": "b", "files": {}}
    b = dict(a, actor="someone-else", artifact_id="different")
    assert payload_hash(a) == payload_hash(b)


def test_dry_run_touches_no_database(tmp_path):
    write_skill(tmp_path, "dv-a")

    class Exploding:
        def append(self, a):
            raise AssertionError("dry run must not write")

        def by_type(self, t):
            raise AssertionError("dry run must not read")

        def get(self, i):
            raise AssertionError("dry run must not read")

    report = run_wave(store=Exploding(), dsn="postgresql://unused",
                      items=load_wave(tmp_path), dry_run=True, allow_ungated=True)
    assert report.counts["total"] == 1


def test_on_duplicate_is_validated():
    with pytest.raises(ValueError):
        run_wave(store=None, dsn="x", items=[], on_duplicate="clobber")


# ── against the live gate ─────────────────────────────────────────────────────

@pytest.mark.integration
def test_wave_publishes_only_through_the_gate(pg_store, pg_dsn, tmp_path):
    """The whole default path, with nothing waived: a ready content recheck AND a clean pipeline."""
    write_review(write_skill(tmp_path, "dv-wave-one"), ready=True)
    write_review(write_skill(tmp_path, "dv-wave-two"), ready=True)
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path))

    assert report.ok and report.counts[PUBLISHED] == 2
    assert report.counts["ungated-published"] == 0
    for item in report.items:
        sv_id = item.skill_version_id
        scans = [a for a in pg_store.by_type(ArtifactType.SCAN_RUN)
                 if str(a.input_refs[0]) == sv_id]
        assert scans and not any(a.payload.get("hard_fail") for a in scans)
        approvals = [a for a in pg_store.by_type(ArtifactType.APPROVAL)
                     if a.input_refs and str(a.input_refs[0]) == sv_id
                     and a.payload.get("published")]
        assert approvals, "published without an approval artifact — the gate was bypassed"

    slugs = {c.slug for c in search_catalog(dsn=pg_dsn, principal=["public"])}
    assert slugs == {"dv-wave-one", "dv-wave-two"}


@pytest.mark.integration
def test_public_label_makes_the_catalog_visible_to_an_anonymous_caller(pg_store, pg_dsn, tmp_path):
    """A `team` label plus api.py's `public` default is why a successful wave used to yield an
    empty-looking catalog (ADR-009)."""
    write_skill(tmp_path, "dv-visible")
    run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), permissions_label="public",
             allow_ungated=True)
    assert [c.slug for c in search_catalog(dsn=pg_dsn, principal=["public"])] == ["dv-visible"]


@pytest.mark.integration
def test_rerunning_an_unchanged_wave_is_a_noop(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-idem")
    items = load_wave(tmp_path)
    assert run_wave(store=pg_store, dsn=pg_dsn, items=items,
                    allow_ungated=True).counts[PUBLISHED] == 1

    again = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)
    assert again.counts[SKIPPED_IDENTICAL] == 1 and again.ok
    assert len([c for c in search_catalog(dsn=pg_dsn, principal=["public"])]) == 1


@pytest.mark.integration
def test_changed_content_supersedes_and_the_old_card_leaves_the_catalog(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-super")
    run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)

    write_skill(tmp_path, "dv-super", body=BODY + "\nA materially improved step.\n")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)

    assert report.counts[SUPERSEDED] == 1 and report.ok
    cards = list(search_catalog(dsn=pg_dsn, principal=["public"]))
    assert len(cards) == 1, "supersede must leave exactly one live card per slug"
    # the old approval is corrected, never deleted (ADR-003)
    approvals = pg_store.by_type(ArtifactType.APPROVAL)
    assert any(a.corrects_ref is not None for a in approvals)


@pytest.mark.integration
def test_one_malformed_item_does_not_abort_the_wave(pg_store, pg_dsn, tmp_path):
    """`seed_catalog`'s bare comprehension let a YAML error — which is NOT a ValueError — propagate
    out and abandon every remaining skill."""
    write_skill(tmp_path, "dv-good-one")
    bad = tmp_path / "dv-broken"
    bad.mkdir()
    (bad / "SKILL.md").write_text("---\nname: dv-broken\ndescription: Guide: do it\n---\nbody",
                                  encoding="utf-8")
    write_skill(tmp_path, "dv-good-two")

    items = []
    for d in sorted(tmp_path.iterdir()):
        try:
            items.extend(load_wave(d))
        except Exception:                       # loader surfaces it; the driver must survive it
            from semiskill.wave import WaveItem
            items.append(WaveItem(path=str(d), slug="dv-broken", name="dv-broken",
                                  skill_md=(d / "SKILL.md").read_text(encoding="utf-8"),
                                  files={}, payload_sha256="unparseable"))

    report = run_wave(store=pg_store, dsn=pg_dsn, items=items, allow_ungated=True)
    assert report.counts.get(ERROR) == 1
    assert report.counts.get(PUBLISHED) == 2, "the good items either side must still publish"
    assert not report.ok


@pytest.mark.integration
def test_request_changes_is_reported_not_silent(pg_store, pg_dsn, tmp_path):
    """A single URL scores 0.3 -> aggregate 0.70 -> `request-changes`. The old path returned
    published=False with no exception, so a wave that published nothing looked successful."""
    write_skill(tmp_path, "dv-has-url", body=BODY + "\nSee https://example.com/spec\n")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)

    item = report.items[0]
    assert item.status == CHANGES_REQUESTED and not item.ok and not report.ok
    assert item.verdict == "request-changes" and "not published" in item.error
    assert search_catalog(dsn=pg_dsn, principal=["public"]) == []


@pytest.mark.integration
def test_a_dangerous_tool_is_blocked_like_any_other_submission(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-dangerous", tools="Read Bash")
    # --allow-ungated waives the CONTENT gate; it must not waive the security pipeline.
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)
    assert report.items[0].status == BLOCKED and report.items[0].blocked_at == 1
    assert search_catalog(dsn=pg_dsn, principal=["public"]) == []


@pytest.mark.integration
def test_infrastructure_failure_aborts_rather_than_reporting_forty_identical_errors(pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-a")
    write_skill(tmp_path, "dv-b")

    class Broken:
        def by_type(self, t):
            return []

        def append(self, a):
            import psycopg
            raise psycopg.OperationalError("connection refused")

        def get(self, i):
            return None

    with pytest.raises(WaveAborted) as e:
        run_wave(store=Broken(), dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)
    assert "aborted at dv-a" in str(e.value)


@pytest.mark.integration
def test_journal_and_report_are_written(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-report")
    journal = tmp_path / "reports" / "journal.jsonl"
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path),
                      journal_path=journal, allow_ungated=True)

    rows = [json.loads(l) for l in journal.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["status"] == PUBLISHED

    md, js = write_wave_report(report, tmp_path / "reports")
    assert md.exists() and js.exists()
    assert "dv-report" in md.read_text(encoding="utf-8")
    assert json.loads(js.read_text(encoding="utf-8"))["ok"] is True


def test_render_report_lists_failures():
    from semiskill.wave import WaveItemResult, WaveReport
    r = WaveReport(wave_id="wave-x", started_at="a", finished_at="b", permissions_label="public",
                   on_duplicate="supersede",
                   items=(WaveItemResult(slug="dv-x", path="p", status=CHANGES_REQUESTED,
                                         error="aggregate verdict 'request-changes' — not published"),),
                   counts={"total": 1})
    text = render_report(r)
    assert "INCOMPLETE" in text and "Not published" in text and "dv-x" in text


# ── the content gate is a precondition, not a report ──────────────────────────
#
# `scoreboard --strict-gate` already counted "published without an independent recheck" AFTER the
# catalog was written. These assert the same rule one step earlier, where it can still say no.

@pytest.mark.integration
def test_a_skill_with_no_review_json_is_not_published(pg_store, pg_dsn, tmp_path):
    write_skill(tmp_path, "dv-no-record")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path))

    item = report.items[0]
    assert item.status == GATE_MISSING and item.gate == UNREVIEWED and not item.ok
    assert "no REVIEW.json" in item.error and "independent content recheck" in item.error
    assert not report.ok and report.counts["gate-refused"] == 1
    assert search_catalog(dsn=pg_dsn, principal=["public"]) == [], "nothing may reach the catalog"


@pytest.mark.integration
def test_a_skill_whose_recheck_says_not_ready_is_not_published(pg_store, pg_dsn, tmp_path):
    """The distinction is load-bearing: 'nobody looked' and 'somebody looked and said no' send the
    reader to different places."""
    write_review(write_skill(tmp_path, "dv-not-ready"), ready=False, why="the fix broke step 3")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path))

    item = report.items[0]
    assert item.status == GATE_NOT_READY and item.status != GATE_MISSING
    assert "recheck.ready is not true" in item.error and "the fix broke step 3" in item.error
    assert not report.ok and search_catalog(dsn=pg_dsn, principal=["public"]) == []


@pytest.mark.integration
def test_a_ready_recheck_publishes_with_no_flag(pg_store, pg_dsn, tmp_path):
    write_review(write_skill(tmp_path, "dv-ready"), ready=True, why="all must-fixes closed")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path))

    assert report.ok and report.items[0].status == PUBLISHED
    assert report.items[0].gate == READY
    assert report.ungated_published == () and report.counts["ungated-published"] == 0
    assert [c.slug for c in search_catalog(dsn=pg_dsn, principal=["public"])] == ["dv-ready"]


@pytest.mark.integration
def test_an_unparseable_review_json_is_refused_not_trusted(pg_store, pg_dsn, tmp_path):
    d = write_skill(tmp_path, "dv-corrupt")
    (d / "REVIEW.json").write_text('{"recheck": {"ready": true', encoding="utf-8")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path))

    assert report.items[0].status == GATE_MISSING and "unreadable" in report.items[0].error
    assert search_catalog(dsn=pg_dsn, principal=["public"]) == []


@pytest.mark.integration
def test_the_escape_hatch_publishes_and_is_named_in_the_report(pg_store, pg_dsn, tmp_path):
    """An override that leaves no trace is the same problem the gate exists to solve."""
    write_skill(tmp_path, "dv-fixture")
    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path), allow_ungated=True)

    assert report.ok and report.items[0].status == PUBLISHED
    assert report.allow_ungated is True
    assert report.ungated_published == ("dv-fixture",)
    assert report.counts["ungated-published"] == 1

    md = render_report(report, style="markdown")
    assert "BYPASSED (--allow-ungated)" in md
    assert "Published WITHOUT an independent content recheck" in md and "`dv-fixture`" in md

    data = json.loads(render_report(report, style="json"))
    assert data["allow_ungated"] is True and data["ungated_published"] == ["dv-fixture"]


@pytest.mark.integration
def test_a_mixed_directory_publishes_the_ready_ones_and_reports_the_rest(pg_store, pg_dsn, tmp_path):
    """The worst available failure is a silently-reduced wave reported as success, so the counts
    have to add up in the report itself."""
    write_review(write_skill(tmp_path, "dv-ready-one"), ready=True)
    write_review(write_skill(tmp_path, "dv-ready-two"), ready=True)
    write_skill(tmp_path, "dv-never-reviewed")
    write_review(write_skill(tmp_path, "dv-said-no"), ready=False, why="procedure is still wrong")

    report = run_wave(store=pg_store, dsn=pg_dsn, items=load_wave(tmp_path))

    by_slug = {i.slug: i for i in report.items}
    assert by_slug["dv-ready-one"].status == PUBLISHED
    assert by_slug["dv-ready-two"].status == PUBLISHED
    assert by_slug["dv-never-reviewed"].status == GATE_MISSING
    assert by_slug["dv-said-no"].status == GATE_NOT_READY

    assert report.counts["total"] == 4 and report.counts[PUBLISHED] == 2
    assert report.counts["gate-refused"] == 2 and not report.ok

    assert {c.slug for c in search_catalog(dsn=pg_dsn, principal=["public"])} == {
        "dv-ready-one", "dv-ready-two"}

    md = render_report(report, style="markdown")
    assert "INCOMPLETE" in md and "Not published" in md
    for slug in ("dv-never-reviewed", "dv-said-no"):
        assert slug in md, "a skipped skill must be named, not silently dropped"
    assert "procedure is still wrong" in md
