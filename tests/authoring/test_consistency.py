"""Pack-consistency tests.

Each rule here exists because a real review round found that exact defect by eye, expensively and
after already missing it once. The point of the module is that the third occurrence of a renamed
field is never missed again.
"""
from pathlib import Path

import pytest

from semiskill.authoring.consistency import check_pack, declared_slots, render, report_fields

HEAD = ("---\nname: {slug}\ndescription: Does a thing. Use when you need it.\n"
        "allowed-tools: Read, Grep, Glob\nmetadata:\n  semiskill-role: dv-engineer\n"
        "  semiskill-level: senior\n---\n")


def write(root, slug, body):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(HEAD.format(slug=slug) + body, encoding="utf-8")


def rules(findings):
    return {f.rule for f in findings}


# ── parsing ───────────────────────────────────────────────────────────────────

def test_declared_slots_reads_the_table_convention():
    body = ("| Slot | What | Who |\n|---|---|---|\n"
            "| Log location | [[FILL: where logs land]] | mentor |\n"
            "| Pass marker | [[FILL: the clean-run string]] | lead |\n")
    assert declared_slots(body) == {"Log location", "Pass marker"}


def test_report_fields_only_reads_fenced_blocks():
    body = ("Prose with a colon: not a field.\n\n"
            "```\nphase     : compile | elab | run\nclass     : design | infrastructure\n```\n")
    fields = report_fields(body)
    assert fields["phase"] == "compile | elab | run"
    assert fields["class"] == "design | infrastructure"
    assert "Prose with a colon" not in fields


# ── C003: the one that actually bit us ────────────────────────────────────────

def test_a_handoff_enum_widened_in_one_skill_and_not_its_sibling_is_an_error(tmp_path):
    """Exactly the defect that shipped: `post` was added to one skill's phase enum and the sibling
    that claims to match it mechanically was left stale."""
    write(tmp_path, "dv-a", "## Report\n\n```\nphase     : compile | elab | run | finalise | post\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nphase     : compile | elab | run | finalise\n```\n")

    # Every variant is a subset of the widest, so this warns rather than errors: narrowing is
    # sometimes deliberate scoping (a build-break skill only ever produces compile or elab).
    c003 = [f for f in check_pack(tmp_path) if f.rule == "C003"]
    assert len(c003) == 1 and c003[0].level == "warn"
    assert "post" in c003[0].message and "dv-a" in c003[0].slug and "dv-b" in c003[0].slug


def test_incompatible_enums_are_an_error(tmp_path):
    """Neither set contains the other: a value one skill emits is one no sibling accepts, so a match
    is impossible rather than merely narrower."""
    write(tmp_path, "dv-a", "## Report\n\n```\nclass : design | infrastructure\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nclass : design | tooling\n```\n")

    c003 = [f for f in check_pack(tmp_path) if f.rule == "C003"]
    assert len(c003) == 1 and c003[0].level == "error"
    assert "no sibling accepts" in c003[0].message


def test_matching_enums_across_the_pack_are_clean(tmp_path):
    for slug in ("dv-a", "dv-b"):
        write(tmp_path, slug, "## Report\n\n```\nphase     : compile | elab | run\n```\n")
    assert not [f for f in check_pack(tmp_path) if f.rule == "C003"]


def test_a_field_in_only_one_skill_is_not_compared(tmp_path):
    write(tmp_path, "dv-a", "## Report\n\n```\nlocal_only : x | y\n```\n")
    assert not [f for f in check_pack(tmp_path) if f.rule == "C003"]


# ── C004: the stale reference after a rename ──────────────────────────────────

def test_prose_referring_to_a_value_the_field_no_longer_has_is_an_error(tmp_path):
    """A field was split and one of three references was missed — twice, by two different reviewers."""
    write(tmp_path, "dv-a",
          "## Report\n\n```\nbaseline  : also-failed | not-in-baseline | not-checked\n```\n\n"
          "## Gotchas\n\nIf the list cannot be read, every bucket is `baseline: unknown`.\n")
    findings = [f for f in check_pack(tmp_path) if f.rule == "C004"]
    assert len(findings) == 1 and "unknown" in findings[0].message


def test_prose_referring_to_a_legal_value_is_clean(tmp_path):
    write(tmp_path, "dv-a",
          "## Report\n\n```\nbaseline  : also-failed | not-checked\n```\n\n"
          "## Gotchas\n\nIf it cannot be read, mark `baseline: not-checked`.\n")
    assert not [f for f in check_pack(tmp_path) if f.rule == "C004"]


# ── C001: a slot nobody spends ────────────────────────────────────────────────

def test_a_declared_slot_no_step_uses_is_flagged(tmp_path):
    write(tmp_path, "dv-a",
          "| Slot | What | Who |\n|---|---|---|\n"
          "| Bug convention | [[FILL: what a bug title looks like]] | lead |\n\n"
          "## Procedure\n\nRead the log and classify the failure.\n")
    findings = [f for f in check_pack(tmp_path) if f.rule == "C001"]
    assert len(findings) == 1 and "Bug convention" in findings[0].message


def test_a_slot_the_procedure_uses_is_clean(tmp_path):
    write(tmp_path, "dv-a",
          "| Slot | What | Who |\n|---|---|---|\n"
          "| Log location | [[FILL: where logs land]] | mentor |\n\n"
          "## Procedure\n\nGlob against the Log location slot, then Read a window.\n")
    assert not [f for f in check_pack(tmp_path) if f.rule == "C001"]


# ── output ────────────────────────────────────────────────────────────────────

def test_render_says_so_when_the_pack_agrees(tmp_path):
    write(tmp_path, "dv-a", "## Report\n\n```\nphase : compile | run\n```\n")
    assert render(check_pack(tmp_path)) == "pack is self-consistent"


def test_render_lists_rule_slug_and_fix(tmp_path):
    write(tmp_path, "dv-a", "## Report\n\n```\nphase : compile | run | post\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nphase : compile | run\n```\n")
    text = render(check_pack(tmp_path))
    assert "C003" in text and "fix:" in text


@pytest.mark.integration
def test_the_real_pack_is_checked(tmp_path):
    """Runs against the shipped skills. Not asserting clean — asserting the checker engages."""
    findings = check_pack(Path("skills"))
    assert isinstance(findings, list)
    for f in findings:
        assert f.rule and f.slug and f.message and f.fix
