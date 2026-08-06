import io
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from semiskill.artifacts.schema import Artifact, ArtifactType
from semiskill.artifacts.store import PublicationReconciliationBundle
from semiskill.authoring.snapshot import load_scoreboard_snapshot
from semiskill.cli import build_parser, main

SKILL_MD = """---
name: STA Timing Closure
slug: pd/sta-closure
version: 0.3.0
function: physical-design
role: sta-engineer
level: senior
---
Body.
"""


class FakeStore:
    def __init__(self):
        self.rows: list[Artifact] = []

    def append(self, a: Artifact) -> Artifact:
        self.rows.append(a)
        return a

    def get(self, aid):
        return next((r for r in self.rows if r.artifact_id == aid), None)

    def by_type(self, t: ArtifactType):
        return [r for r in self.rows if r.artifact_type == t]

    def publication_reconciliation_bundle(self):
        return PublicationReconciliationBundle(tuple(self.rows), ())


@pytest.fixture
def skill_dir(tmp_path):
    (tmp_path / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    return tmp_path


def test_submit_appends_skill_version(skill_dir):
    store, out = FakeStore(), io.StringIO()
    rc = main(["submit", str(skill_dir), "--actor", "rishi", "--label", "need-to-know"],
              store=store, out=out)
    assert rc == 0
    assert len(store.rows) == 1
    art = store.rows[0]
    assert art.artifact_type is ArtifactType.SKILL_VERSION
    assert art.payload["slug"] == "pd/sta-closure"
    assert art.permissions_label == "need-to-know"
    assert "submitted pd/sta-closure" in out.getvalue()
    assert "state=submitted" in out.getvalue()


def test_list_shows_submitted(skill_dir):
    store, out = FakeStore(), io.StringIO()
    main(["submit", str(skill_dir)], store=store, out=io.StringIO())
    main(["list"], store=store, out=out)
    assert "pd/sta-closure" in out.getvalue()


def test_list_empty():
    out = io.StringIO()
    main(["list"], store=FakeStore(), out=out)
    assert "no skills submitted yet" in out.getvalue()


def test_invalid_label_rejected(skill_dir):
    with pytest.raises(SystemExit):  # argparse rejects bad choice
        main(["submit", str(skill_dir), "--label", "top-secret"], store=FakeStore(), out=io.StringIO())


def test_approve_requires_exact_hash_both_reviews_decision_and_reason():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["approve", "00000000-0000-0000-0000-000000000000"])


def test_approve_has_no_actor_override():
    argv = [
        "approve", "00000000-0000-0000-0000-000000000000",
        "--automated-review", "00000000-0000-0000-0000-000000000001",
        "--content-review", "00000000-0000-0000-0000-000000000002",
        "--expected-sha256", "0" * 64,
        "--decision", "approve", "--reason", "I reviewed this exact evidence.",
        "--actor", "forged-user",
    ]
    with pytest.raises(SystemExit):
        build_parser().parse_args(argv)


def test_production_approve_fails_closed_without_entra_adapter():
    out = io.StringIO()
    rc = main([
        "approve", "00000000-0000-0000-0000-000000000000",
        "--automated-review", "00000000-0000-0000-0000-000000000001",
        "--content-review", "00000000-0000-0000-0000-000000000002",
        "--expected-sha256", "0" * 64,
        "--decision", "approve", "--reason", "Reviewed.", "--environment", "production",
    ], store=FakeStore(), out=out)
    assert rc == 2 and "Entra/OIDC" in out.getvalue()


@pytest.mark.parametrize("command", ["pack", "catalog", "site"])
def test_export_commands_require_explicit_snapshot_and_permission_label(command):
    with pytest.raises(SystemExit):
        build_parser().parse_args([command])


@pytest.mark.parametrize("command", ["pack", "catalog", "site"])
def test_production_export_commands_fail_closed_without_entra_adapter(command):
    out = io.StringIO()
    rc = main([
        command, "--scoreboard-snapshot", "missing.json", "--permission-label", "public",
        "--environment", "production",
    ], store=FakeStore(), out=out)
    assert rc == 2 and "Entra/OIDC" in out.getvalue()


@pytest.mark.parametrize("command", ["pack", "catalog", "site"])
def test_export_cli_passes_the_resolved_scope_to_the_materializer(
    command, monkeypatch, tmp_path,
):
    import semiskill.cli as cli

    scope = SimpleNamespace(publications=(object(),))
    observed = {}
    monkeypatch.setattr(cli, "_export_scope_from_args", lambda args, store: scope)

    if command == "pack":
        def build_pack(**kwargs):
            observed.update(kwargs)
            return tmp_path / "release" / "semiskill-dv", SimpleNamespace(
                skill_count=1, skills=(),
            )
        monkeypatch.setattr("semiskill.authoring.pack.build_pack", build_pack)
        extra = ["--no-zip"]
    elif command == "catalog":
        def build_catalog(**kwargs):
            observed.update(kwargs)
            return tmp_path / "catalog", SimpleNamespace(entries=(object(),))
        monkeypatch.setattr("semiskill.authoring.catalog_page.build_catalog", build_catalog)
        extra = []
    else:
        def build_site(**kwargs):
            observed.update(kwargs)
            return SimpleNamespace(
                entries=(object(),), pages=("index.html",), root=tmp_path / "site",
            )
        monkeypatch.setattr("semiskill.authoring.site.build_site", build_site)
        extra = []

    out = io.StringIO()
    rc = main([
        command, "--scoreboard-snapshot", "snapshot.json", "--permission-label", "public",
        "--out", str(tmp_path / "out"), *extra,
    ], store=FakeStore(), out=out)
    assert rc == 0 and observed["scope"] is scope


def test_lint_needs_no_store_and_exits_nonzero_on_error(tmp_path, capsys):
    """`semiskill lint` must work with no database — authoring feedback has to be instant, and a
    wave must be provably clean before the first artifact is written."""
    import io
    from semiskill.cli import main
    d = tmp_path / "dv-bad-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        "---\nname: dv-bad-skill\ndescription: Does a thing. Use when needed.\n"
        "allowed-tools: Read Bash\n---\nbody text that is long enough to not be thin " * 12,
        encoding="utf-8")
    out = io.StringIO()
    # store=None and needs_store=False => no Postgres connection is attempted
    assert main(["lint", str(tmp_path)], store=None, out=out) == 1
    assert "L017" in out.getvalue()


def test_lint_clean_tree_exits_zero(tmp_path):
    import io
    from semiskill.cli import main
    d = tmp_path / "dv-good-skill"
    d.mkdir()
    body = ("# Good\n\nA real procedure.\n\n" + "Read the summary and classify each failure. " * 20)
    (d / "SKILL.md").write_text(
        "---\nname: dv-good-skill\n"
        "description: Classify regression failures. Use when a nightly run has failures.\n"
        "allowed-tools: Read Grep Glob\nmetadata:\n"
        "  semiskill-function: design-verification\n  semiskill-role: dv-engineer\n"
        "  semiskill-level: intermediate\n---\n" + body, encoding="utf-8")
    out = io.StringIO()
    assert main(["lint", str(tmp_path)], store=None, out=out) == 0
    assert "approve" in out.getvalue()


def _clean_skill(root, slug, extra_body=""):
    """A skill that passes the per-skill lint, so a wave gets as far as the pack check."""
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    body = ("# Title\n\nA real procedure.\n\n"
            + "Read the summary and classify each failure. " * 20 + "\n" + extra_body)
    (d / "SKILL.md").write_text(
        f"---\nname: {slug}\n"
        "description: Classify regression failures. Use when a nightly run has failures.\n"
        "allowed-tools: Read Grep Glob\nmetadata:\n"
        "  semiskill-function: design-verification\n  semiskill-role: dv-engineer\n"
        "  semiskill-level: intermediate\n---\n" + body, encoding="utf-8")
    return d


REPORT = "\n## Report\n\n```\nlocal verdict : {values}\n```\n"


def test_a_wave_aborts_on_a_pack_level_consistency_error(tmp_path):
    """`semiskill lint` always ran BOTH the per-skill lint and the pack check; the wave ran only the
    first. So a pack that disagreed with itself could still publish — the pack gate was advisory in
    the one place it had to be a precondition. Two skills sharing an unregistered field name with
    DIFFERENT values is the error that must stop it, before any artifact is written."""
    import io
    from semiskill.cli import main
    _clean_skill(tmp_path, "dv-one", REPORT.format(values="alpha | beta"))
    _clean_skill(tmp_path, "dv-two", REPORT.format(values="gamma | delta"))

    out = io.StringIO()
    # wave-plan writes nothing and needs no database, so this exercises the gate on its own.
    rc = main(["wave-plan", str(tmp_path)], store=None, out=out)
    text = out.getvalue()
    assert rc == 1
    assert "C006" in text
    assert "before any artifact was written" in text


def test_a_wave_is_not_stopped_by_pack_level_warnings(tmp_path):
    """Warns are the authoring backlog, not a release blocker. An unused slot (C001) must not stop a
    release, or the pack could never ship while any skill still carried a to-do."""
    import io
    from semiskill.authoring.consistency import check_pack
    from semiskill.cli import main
    _clean_skill(tmp_path, "dv-warn",
                 "\n| Slot | What | Who |\n|---|---|---|\n"
                 "| Unused thing | [[FILL: never spent]] | lead |\n")

    findings = check_pack(tmp_path)
    assert any(f.rule == "C001" for f in findings), "fixture must actually produce a warn"
    assert not [f for f in findings if f.level == "error"]

    out = io.StringIO()
    rc = main(["wave-plan", str(tmp_path)], store=None, out=out)
    assert rc == 0
    assert "before any artifact was written" not in out.getvalue()


def _scoreboard_inputs(tmp_path):
    root = tmp_path / "skills"
    _clean_skill(root, "dv-one")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"target_per_role": 1, "cells": [{
        "slug": "dv-one", "role": "dv-engineer", "level": "intermediate",
    }]}), encoding="utf-8")
    return root, registry


def test_scoreboard_snapshot_is_explicit_loadable_and_written_when_incomplete(tmp_path):
    root, registry = _scoreboard_inputs(tmp_path)
    target = tmp_path / "reports" / "scoreboard.json"
    out = io.StringIO()
    rc = main([
        "scoreboard", "--registry", str(registry), "--skills", str(root),
        "--dsn", "postgresql://unused/semiskill_dev", "--fail-under", "1",
        "--snapshot-out", str(target),
    ], store=FakeStore(), out=out)
    snapshot = load_scoreboard_snapshot(target)
    assert rc == 1 and snapshot["release_gate"]["passed"] is False
    assert snapshot["registry"]["active"] == 1
    assert str(target) in out.getvalue() and snapshot["snapshot_id"] in out.getvalue()


def test_canonical_snapshot_path_never_invokes_legacy_scoreboard(tmp_path, monkeypatch):
    root, registry = _scoreboard_inputs(tmp_path)
    target = tmp_path / "scoreboard.json"

    def legacy_must_not_run(**_kwargs):
        raise AssertionError("legacy scoreboard was invoked")

    monkeypatch.setattr("semiskill.authoring.scoreboard.build_scoreboard", legacy_must_not_run)
    rc = main([
        "scoreboard", "--registry", str(registry), "--skills", str(root),
        "--dsn", "postgresql://unused/semiskill_dev", "--fail-under", "1",
        "--snapshot-out", str(target),
    ], store=FakeStore(), out=io.StringIO())
    assert rc == 1 and load_scoreboard_snapshot(target)["registry"]["active"] == 1


def test_scoreboard_without_snapshot_out_has_no_file_side_effect(tmp_path):
    root, registry = _scoreboard_inputs(tmp_path)
    rc = main([
        "scoreboard", "--registry", str(registry), "--skills", str(root),
        "--dsn", "postgresql://unused/semiskill_dev", "--fail-under", "1",
    ], store=FakeStore(), out=io.StringIO())
    assert rc == 1 and not (tmp_path / "reports").exists()


@pytest.mark.parametrize("extra", [["--snapshot-out", "-"],
                                    ["--snapshot-out", "out.json", "--no-lint"]])
def test_scoreboard_refuses_non_atomic_or_lintless_snapshot(tmp_path, extra):
    root, registry = _scoreboard_inputs(tmp_path)
    out = io.StringIO()
    rc = main([
        "scoreboard", "--registry", str(registry), "--skills", str(root),
        "--dsn", "postgresql://unused/semiskill_dev", *extra,
    ], store=FakeStore(), out=out)
    assert rc == 2 and "snapshot refused" in out.getvalue()


def test_snapshot_generation_failure_preserves_prior_file(tmp_path, monkeypatch):
    root, registry = _scoreboard_inputs(tmp_path)
    target = tmp_path / "scoreboard.json"
    target.write_text("prior-complete-snapshot", encoding="utf-8")

    def fail(**_kwargs):
        raise RuntimeError("private database detail")

    monkeypatch.setattr("semiskill.authoring.snapshot.build_scoreboard_snapshot", fail)
    out = io.StringIO()
    rc = main([
        "scoreboard", "--registry", str(registry), "--skills", str(root),
        "--dsn", "postgresql://unused/semiskill_dev",
        "--snapshot-out", str(target),
    ], store=FakeStore(), out=out)
    assert rc == 2 and target.read_text(encoding="utf-8") == "prior-complete-snapshot"
    assert "private database detail" not in out.getvalue()


