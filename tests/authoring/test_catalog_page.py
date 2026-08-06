"""Catalog-page tests.

The two that matter most are `test_an_unpublished_skill_never_appears` and
`test_an_untrusted_body_cannot_break_out_of_the_page` — the first is the ADR-002 promise carried all
the way to the browsable artifact, the second is because every body on this page is untrusted content
by the project's own rule.
"""
import csv
import io
import json
from dataclasses import replace
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.catalog_page import build_catalog, collect, render_html, render_markdown
from tests.support import publish_wave_sources

MIG = Path("semiskill/artifacts/migrations")
BODY = ("# Title\n\nA procedure with enough substance to count as a skill.\n\n"
        "## Fill this in for our team\n\n| Slot | What |\n|---|---|\n"
        "| where | [[FILL: where our logs land]] |\n\n"
        "## Procedure\n\n1. Use **Grep** to locate the marker, then read a bounded window.\n\n"
        "## Gotchas\n\nThe loudest line is rarely the first failure.\n\n"
        "## Human verification\n\nA wrong answer names a cascade line as the cause.\n"
        + "Filler prose to keep this a realistic length. " * 10)


def skill_md(name, *, body=BODY, tools="Read Grep Glob", role="dv-engineer", level="intermediate"):
    return (f"---\nname: {name}\ndescription: Does {name}. Use when you need {name}.\n"
            f"allowed-tools: {tools}\nmetadata:\n  semiskill-title: Title of {name}\n"
            f"  semiskill-function: design-verification\n  semiskill-role: {role}\n"
            f"  semiskill-level: {level}\n  semiskill-version: 1.0.0\n"
            f"  semiskill-owner: dv-guild\n  semiskill-tags: alpha, beta\n---\n{body}")


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.fixture
def populated(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    for name, role, level in (("dv-alpha", "dv-engineer", "junior"),
                              ("dv-beta", "dv-infra-engineer", "senior")):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(skill_md(name, role=role, level=level), encoding="utf-8")
    publish_wave_sources(pg_store, root)
    return pg_store, root


@pytest.mark.integration
def test_collect_returns_published_skills_with_their_real_scan_report(populated):
    store, _ = populated
    entries = collect(store)
    assert {e.slug for e in entries} == {"dv-alpha", "dv-beta"}
    for e in entries:
        assert e.verdict == "approve"
        assert e.aggregate_safety == 1.0
        assert [s["stage"] for s in e.stages] == [1, 2, 3, 4, 5]
        assert all(s["status"] == "passed" and s["sampled"] for s in e.stages)
        assert all(not s["hard_fail"] for s in e.stages)
        assert e.slots == 1 and e.body and e.title.startswith("Title of")


@pytest.mark.integration
def test_catalog_badge_is_frozen_to_the_active_approval_chain(pg_store, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-frozen"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(skill_md("dv-frozen"), encoding="utf-8")
    fixture = publish_wave_sources(pg_store, root)[0]

    later_scan = Artifact.new(
        artifact_type=ArtifactType.SCAN_RUN,
        source_system=SourceSystem.CLI,
        actor="later-pipeline",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        input_refs=[fixture.skill_version.artifact_id],
        payload={"stage": 1, "status": "failed", "sampled": True,
                 "safety_score": 0.1, "hard_fail": True, "findings": []},
    )
    later_scan = replace(later_scan, permissions_label=fixture.skill_version.permissions_label)
    pg_store.append(later_scan)
    later_review = Artifact.new(
        artifact_type=ArtifactType.REVIEW,
        source_system=SourceSystem.CLI,
        actor="later-controller",
        actor_kind=ActorKind.AGENT,
        input_refs=[fixture.skill_version.artifact_id, later_scan.artifact_id],
        payload={"review_kind": "security_aggregate", "schema_version": 1, "stage": 6,
                 "verdict": "reject", "aggregate_safety": 0.1, "judge_required": True,
                 "scan_artifact_ids": [str(later_scan.artifact_id)]},
    )
    pg_store.append(replace(later_review, permissions_label=fixture.skill_version.permissions_label))

    entry = collect(pg_store)[0]
    assert entry.approval_id == str(fixture.approval.artifact_id)
    assert entry.automated_review_id == str(fixture.automated_review.artifact_id)
    assert entry.content_review_id == str(fixture.content_review.artifact_id)
    assert [stage["artifact_id"] for stage in entry.stages] == [
        str(scan.artifact_id) for scan in fixture.scans
    ]
    assert entry.verdict == "approve" and entry.aggregate_safety == 1.0


@pytest.mark.integration
def test_an_unpublished_skill_never_appears(populated, pg_store, pg_dsn):
    """ADR-002 carried all the way to the page a human browses."""
    store, root = populated
    d = root / "dv-blocked"
    d.mkdir()
    (d / "SKILL.md").write_text(skill_md("dv-blocked", tools="Read Bash"), encoding="utf-8")

    entries = collect(store)
    assert "dv-blocked" not in {e.slug for e in entries}
    html = render_html(entries, generated_at="t")
    assert "dv-blocked" not in html


@pytest.mark.integration
def test_an_untrusted_body_cannot_break_out_of_the_page(pg_store, pg_dsn, tmp_path):
    """A skill body is untrusted content. A body containing a closing script tag must not be able to
    terminate the embedded JSON block."""
    root = tmp_path / "skills"
    d = root / "dv-hostile"
    d.mkdir(parents=True)
    nasty = BODY + "\nA body containing </script><script>window.pwned=1</script> and \"quotes\".\n"
    (d / "SKILL.md").write_text(skill_md("dv-hostile", body=nasty), encoding="utf-8")
    publish_wave_sources(pg_store, root)

    html = render_html(collect(pg_store), generated_at="t")
    # The HTML parser ends a <script> block on `</script` and nothing else, so that is the sequence
    # that must not survive. A bare `<script>` inside the JSON is inert text.
    assert "</script><script>window.pwned" not in html
    assert "<\\/script>" in html                     # neutralised inside the JSON block
    assert html.count("</script>") == 2, "only the page's own two script blocks may close"
    payload = html.split('type="application/json">')[1].split("</script>")[0]
    assert "</" not in payload, "no raw closing tag may survive inside the data block"
    assert json.loads(payload.replace("<\\/", "</"))["skills"][0]["body"]


@pytest.mark.integration
def test_page_states_the_limits_of_the_badge(populated):
    store, _ = populated
    html = render_html(collect(store), generated_at="t")
    assert "not a runtime guarantee" in html
    assert "does not enforce" in html


@pytest.mark.integration
def test_page_fabricates_nothing(populated):
    """`ui/catalog-demo.html` invented install counts, star ratings and an approver name. Presenting
    invented adoption numbers to the team deciding whether to trust this is a self-inflicted wound."""
    store, _ = populated
    html = render_html(collect(store), generated_at="t").lower()
    for invented in ("installs", "★", "rating", "downloads", "trending", "1.3k"):
        assert invented not in html, f"page contains fabricated metric {invented!r}"


@pytest.mark.integration
def test_markdown_renders_the_catalog_and_the_coverage_matrix(populated):
    store, _ = populated
    md = render_markdown(collect(store), generated_at="t")
    assert "# DV Agent Skills" in md
    assert "/dv-alpha" in md and "/dv-beta" in md
    assert "~/.cursor/skills/" in md
    assert "Cursor 2.4" in md
    assert "| Role |" in md                                  # the coverage matrix
    assert "nobody has written" in md                        # empty cells are an invitation
    assert "not a runtime guarantee" in md


@pytest.mark.integration
def test_csv_is_loadable_and_has_the_expected_columns(populated, tmp_path):
    store, _ = populated
    out, entries = build_catalog(store=store, out_dir=tmp_path / "site", generated_at="t")
    rows = list(csv.DictReader(io.StringIO((out / "catalog.csv").read_text(encoding="utf-8"))))
    assert len(rows) == len(entries)
    assert {"Title", "Slug", "Role", "Level", "Blanks", "Verified", "Safety"} <= set(rows[0])
    assert rows[0]["Verified"] == "approve"


@pytest.mark.integration
def test_build_writes_all_three_artifacts_and_html_is_self_contained(populated, tmp_path):
    store, _ = populated
    out, _ = build_catalog(store=store, out_dir=tmp_path / "site", generated_at="t")
    for f in ("catalog.md", "catalog.csv", "catalog.html"):
        assert (out / f).exists()
    html = (out / "catalog.html").read_text(encoding="utf-8")
    # must work from a USB stick / after a SharePoint download: no CDN, no network at all
    assert "http://" not in html and "https://" not in html
    assert "fetch(" not in html
    assert json.loads(html.split('type="application/json">')[1].split("</script>")[0]
                      .replace("<\\/", "</"))["skills"]


@pytest.mark.integration
def test_generation_is_deterministic(populated, tmp_path):
    store, _ = populated
    a, _ = build_catalog(store=store, out_dir=tmp_path / "a", generated_at="fixed")
    b, _ = build_catalog(store=store, out_dir=tmp_path / "b", generated_at="fixed")
    for f in ("catalog.md", "catalog.csv", "catalog.html"):
        assert (a / f).read_text(encoding="utf-8") == (b / f).read_text(encoding="utf-8")
