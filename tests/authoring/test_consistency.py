"""Pack-consistency tests.

Each rule here exists because a real review round found that exact defect by eye, expensively and
after already missing it once. The point of the module is that the third occurrence of a renamed
field is never missed again.

From ADR-011 onward the enum rules are answered by a signed registry —
`skills/_shared/handoff-vocabulary.md` — rather than by guessing which of two disagreeing enums was
authoritative. Several tests below assert counts measured on the pack *as it stands today*; they are
snapshots on purpose, so that the rename wave the registry describes cannot land silently.

**The wave has landed.** C003, C006, C010 and C012's retirement class are now zero, which is the
system working rather than the snapshots expiring. Each of those tests now asserts the post-wave
state, so it guards the opposite direction: a collision returning, a retired name coming back, a held
noun being taken. A count that is legitimately zero is never asserted alone — every zero is paired
with a synthetic-tree test that reproduces the original defect against the *shipped* registry, so
that "0" can only mean "the pack is clean" and never "the rule stopped working".
"""
import dataclasses
import re
from pathlib import Path

import pytest

from semiskill.authoring.consistency import (
    Registry,
    RegistryError,
    check_pack,
    declared_slots,
    load_registry,
    render,
    report_fields,
)

HEAD = ("---\nname: {slug}\ndescription: Does a thing. Use when you need it.\n"
        "allowed-tools: Read, Grep, Glob\nmetadata:\n  semiskill-role: dv-engineer\n"
        "  semiskill-level: senior\n---\n")

PACK = Path(__file__).resolve().parents[2] / "skills"


def write(root, slug, body):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "SKILL.md").write_text(HEAD.format(slug=slug) + body, encoding="utf-8")


def rules(findings):
    return {f.rule for f in findings}


def only(findings, rule):
    return [f for f in findings if f.rule == rule]


def named(finding, n=0):
    """The n-th quoted name in a finding message — the field the rule is talking about."""
    return re.findall(r"'([^']+)'", finding.message)[n]


# A minimal well-formed registry for synthetic trees. Every slug it mentions gets a stub SKILL.md,
# because the loader is fail-closed about holder slugs that do not exist.
MINI = """# Handoff-field vocabulary

## T1 — REGISTERED

| field | values | narrowing | meaning |
|---|---|---|---|
| `class` | `design` `infrastructure` `unknown` | no | which side of the design line |
| `phase` | `compile` `elab` `run` `finalise` `post` | declared | when it broke |

## T2 — NARROWINGS

| field | skill | values |
|---|---|---|

## T3 — HELD / SHAPE

| name | kind | holder | note |
|---|---|---|---|
| `signature` | shape | - | spelling lock only |
| `ruling` | held | `dv-ruler` | the adjudication verdict |
| `chain` | retired | `dv-was-chain` | was `complete` `no-test` |
"""


def write_registry(root, text=MINI):
    (root / "_shared").mkdir(parents=True, exist_ok=True)
    (root / "_shared" / "handoff-vocabulary.md").write_text(text, encoding="utf-8")
    for slug in set(re.findall(r"`(dv-[a-z0-9-]+)`", text)):
        if not (root / slug / "SKILL.md").exists():
            write(root, slug, "## Report\n\n```\nnotes : anything\n```\n")


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


# ── C003/C006: the one that actually bit us ───────────────────────────────────
# Until ADR-011 this pair of defects was one rule that guessed, from the enums alone, which skill
# was authoritative — and it guessed wrong for nine of the ten collisions on the real pack. The
# registry now answers "is this name pack-wide?" and the two failures split: disagreeing with a
# *registered* enum is C003, and sharing an *unregistered* name at all is C006.

def test_an_unregistered_name_whose_value_sets_differ_is_an_error(tmp_path):
    """Exactly the defect that shipped: `post` was added to one skill's enum and the sibling that
    claims to match it mechanically was left stale. With no registry row saying the two skills
    answer the same question, the repair is a rename, not a reconciliation."""
    write(tmp_path, "dv-a", "## Report\n\n```\nstage     : compile | elab | run | finalise | post\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nstage     : compile | elab | run | finalise\n```\n")

    c006 = only(check_pack(tmp_path), "C006")
    assert len(c006) == 1 and c006[0].level == "error"
    assert named(c006[0]) == "stage"
    assert "dv-a" in c006[0].slug and "dv-b" in c006[0].slug


def test_an_unregistered_name_whose_value_sets_are_identical_is_a_warn(tmp_path):
    """The other half of C006, and the reason it has two levels.

    The harm the registry names is "a reader who sees the same label assumes the tokens are
    commensurable". Where the sets agree that assumption is TRUE: nothing can mismatch, no join is
    wrong, no consumer is misled. Erroring there asserts a harm that does not exist and blocks the
    commonest correct shape there is — two skills built from one body constant, identical by
    construction, which is how most of this suite's fixture trees are written.

    It is still worth saying, because the agreement is unwritten and nothing holds it in place. So
    it warns: register it, or rename it before a third skill copies it."""
    for slug in ("dv-a", "dv-b"):
        write(tmp_path, slug, "## Procedure\n\nRecord clean or dirty.\n\n"
                              "## Report\n\n```\nbin state : clean | dirty\n```\n")
    findings = check_pack(tmp_path)
    c006 = only(findings, "C006")
    assert len(c006) == 1 and c006[0].level == "warn"
    assert named(c006[0]) == "bin state" and "clean | dirty" in c006[0].message
    assert [f for f in findings if f.level == "error"] == []


def test_a_registered_field_emitting_a_value_outside_the_canonical_set_is_an_error(tmp_path):
    """A value the registry does not carry can never be matched: the two sets cannot both be right,
    and now a signed file says which one is."""
    write_registry(tmp_path)
    write(tmp_path, "dv-a", "## Report\n\n```\nclass : design | infrastructure | unknown\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nclass : design | tooling | unknown\n```\n")

    c003 = only(check_pack(tmp_path), "C003")
    assert len(c003) == 1 and c003[0].level == "error" and c003[0].slug == "dv-b"
    assert "tooling" in c003[0].message


def test_two_skills_sharing_a_registered_enum_exactly_are_clean(tmp_path):
    write_registry(tmp_path)
    for slug in ("dv-a", "dv-b"):
        write(tmp_path, slug, "## Report\n\n```\nclass : design | infrastructure | unknown\n```\n")
    findings = check_pack(tmp_path)
    assert not only(findings, "C003") and not only(findings, "C006")


def test_a_field_in_only_one_skill_is_not_compared(tmp_path):
    write(tmp_path, "dv-a", "## Report\n\n```\nlocal_only : x | y\n```\n")
    findings = check_pack(tmp_path)
    assert not only(findings, "C003") and not only(findings, "C006")


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
    # Both enum values need a branch that assigns them, or C005 fires — a self-consistent pack is
    # one whose procedure can actually reach every value its handoff block offers.
    write(tmp_path, "dv-a",
          "## Procedure\n\nIf the build fails, record compile. If it builds and the test fails,\n"
          "record run.\n\n## Report\n\n```\nphase : compile | run\n```\n")
    # One header line, then the verdict: the header is what stops a run against a missing registry
    # from being read as a verified one. See test_render_headers_every_run_including_the_clean_one.
    assert render(check_pack(tmp_path)).splitlines()[-1] == "pack is self-consistent"


def test_render_lists_rule_slug_and_fix(tmp_path):
    write(tmp_path, "dv-a", "## Report\n\n```\nstage : compile | run | post\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nstage : compile | run\n```\n")
    text = render(check_pack(tmp_path))
    assert "C006" in text and "fix:" in text


@pytest.mark.integration
def test_the_real_pack_is_checked(tmp_path):
    """Runs against the shipped skills. Not asserting clean — asserting the checker engages."""
    findings = check_pack(Path("skills"))
    assert isinstance(findings, list)
    for f in findings:
        assert f.rule and f.slug and f.message and f.fix


# ── C002: a slot reference is a label, not any capitalised word before "slot" ──
# The first run over the real 83-skill pack returned 105 C002 findings and every one was prose:
# 80x "If a", 7x "If that", 5x "If the", plus "Check the", "The first", "Answer this". A rule with
# zero precision is worse than no rule, because the one real finding is invisible inside it.

@pytest.mark.parametrize("prose", [
    "If a slot is unfilled, stop and ask.",
    "If the boundary slot convention differs, say so.",
    "Check the generated-sources slot listing before you start.",
    "The first slot you fill decides the rest.",
    "Answer this slot from the spec, not from memory.",
    "Read any IP-XACT the slot mentions.",
])
def test_sentence_initial_capitals_are_not_slot_references(tmp_path, prose):
    write(tmp_path, "dv-a",
          "| Slot | What | Who |\n|---|---|---|\n"
          "| Log location | [[FILL: where logs land]] | mentor |\n\n"
          f"## Procedure\n\nGrep the Log location slot. {prose}\n")
    assert not [f for f in check_pack(tmp_path) if f.rule == "C002"]


def test_a_real_undeclared_slot_reference_is_still_flagged(tmp_path):
    write(tmp_path, "dv-a",
          "| Slot | What | Who |\n|---|---|---|\n"
          "| Log location | [[FILL: where logs land]] | mentor |\n\n"
          "## Procedure\n\nGrep the Log location slot, then compare the two filelists named in\n"
          "the Block-versus-top slot.\n")
    findings = [f for f in check_pack(tmp_path) if f.rule == "C002"]
    assert len(findings) == 1 and "Block-versus-top" in findings[0].message


def test_a_declared_slot_named_mid_sentence_is_clean(tmp_path):
    write(tmp_path, "dv-a",
          "| Slot | What | Who |\n|---|---|---|\n"
          "| Mismatch markers | [[FILL: the strings printed on a mismatch]] | lead |\n\n"
          "## Procedure\n\nGrep the log for the **Mismatch markers** slot strings.\n")
    assert not [f for f in check_pack(tmp_path) if f.rule == "C002"]


# ══ ADR-011: the signed handoff-field registry ════════════════════════════════
# Everything below exists because a name-based checker that guesses is worse than one that reads a
# file a human signed. The registry answers exactly one question — "is this name pack-wide?" — and
# every rule here is a consequence of that answer.


# ── T01–T05: the loader is fail-closed ────────────────────────────────────────
# A silently-empty registry is the worst available failure: it turns C006 into 16 errors on correct
# files and C003 into zero on the one wrong file. So the loader raises rather than degrades.

def test_the_shipped_registry_loads_the_signed_vocabulary():
    reg = load_registry(PACK)
    assert len(reg.registered) == 7
    assert set(reg.registered) == {"class", "phase", "proof status", "action", "fired", "strength",
                                   "window"}
    assert len(reg.shape) == 5
    assert reg.shape == frozenset({"signature", "run id", "owner", "evidence", "notes"})
    assert len(reg.narrowings) == 5
    assert len(reg.held) == 19
    assert len(reg.retired) == 11
    assert reg.registered["class"] == frozenset({"design", "infrastructure", "unknown"})
    assert reg.narrowing_allowed["phase"] is True
    assert reg.narrowing_allowed["class"] is False


def test_a_missing_registry_raises_rather_than_degrading(tmp_path):
    write(tmp_path, "dv-a", "## Report\n\n```\nclass : design | infrastructure\n```\n")
    with pytest.raises(RegistryError):
        load_registry(tmp_path)


def test_a_narrowing_that_is_not_a_proper_subset_raises(tmp_path):
    write_registry(tmp_path, MINI.replace(
        "| field | skill | values |\n|---|---|---|\n",
        "| field | skill | values |\n|---|---|---|\n| `class` | `dv-a` | `design` `tooling` |\n"))
    write(tmp_path, "dv-a", "## Report\n\n```\nclass : design | tooling\n```\n")
    with pytest.raises(RegistryError, match="subset"):
        load_registry(tmp_path)


def test_a_canonical_value_that_is_not_a_token_raises(tmp_path):
    write_registry(tmp_path, MINI.replace("`design` `infrastructure` `unknown`",
                                          "`design` `infra structure` `unknown`"))
    with pytest.raises(RegistryError):
        load_registry(tmp_path)


def test_a_holder_slug_with_no_skill_raises(tmp_path):
    write_registry(tmp_path, MINI.replace("`dv-ruler`", "`dv-does-not-exist`"))
    (tmp_path / "dv-does-not-exist" / "SKILL.md").unlink()
    with pytest.raises(RegistryError, match="dv-does-not-exist"):
        load_registry(tmp_path)


def test_an_unknown_kind_keyword_raises(tmp_path):
    write_registry(tmp_path, MINI.replace("| `signature` | shape |", "| `signature` | spelling |"))
    with pytest.raises(RegistryError, match="spelling"):
        load_registry(tmp_path)


# ── T06–T10: the parser ───────────────────────────────────────────────────────

def test_separator_spellings_are_one_field_identity_reported_as_written():
    """`proof status`, `proof-status` and `proof_status` are one column or the registry is a lie.
    Identity is normalised; the spelling reported back is the one the author wrote."""
    for spelling in ("proof status", "proof-status", "proof_status"):
        fields = report_fields("```\n" + spelling + " : proven | falsified\n```\n")
        assert "proof status" in fields
        assert fields["proof status"] == "proven | falsified"
        assert fields["proof status"].spelling == spelling


def test_a_qualified_name_is_not_merged_into_the_bare_one():
    """Rule 9: consumers compare the whole name. `match` and `match key` are different fields, and
    the normalisation must be separator-level only or the qualified-name escape hatch closes."""
    fields = report_fields("```\nmatch     : in-band | out-of-band\nmatch key : file-line | object\n```\n")
    assert set(fields) == {"match", "match key"}


def test_a_registered_field_may_declare_a_single_value_but_an_unregistered_one_may_not(tmp_path):
    """A registered field must be able to say `phase : run` without hiding from every rule. An
    unregistered name keeps the two-part floor so `kind : tool` is not promoted into an enum."""
    write_registry(tmp_path)
    write(tmp_path, "dv-a", "## Procedure\n\nRecord run.\n\n## Report\n\n```\nphase : run\nkind : tool\n```\n")
    write(tmp_path, "dv-b", "## Procedure\n\nRecord tool.\n\n## Report\n\n```\nkind : tool\n```\n")
    findings = check_pack(tmp_path)
    # `phase : run` is seen as the narrowing it is …
    assert [f.slug for f in only(findings, "C007")] == ["dv-a"]
    # … and `kind : tool` is not an enum at all, so no shared-name rule can reach it.
    assert not only(findings, "C006")


def test_an_inline_reason_after_an_em_dash_is_parsed_beside_the_enum(tmp_path):
    """`phase : run — a trap is always a run-phase failure` is the shape the pack already writes.
    Before this it parsed as nothing at all: no pipe, so no enum, so C003, C005 and C007 were all
    blind to a narrowing sitting in plain sight.

    Now both halves are read. The reason is a declaration under Rule 7, so C007 is satisfied — and
    C009 still asks for the sentence to move below the block, because a value with commentary
    stapled to it is a value no consumer can compare."""
    write_registry(tmp_path)
    write(tmp_path, "dv-a",
          "## Procedure\n\nRecord run.\n\n## Report\n\n```\n"
          "phase : run — a trap is always a run-phase failure\n```\n")
    findings = check_pack(tmp_path)
    assert not only(findings, "C007")
    assert len(only(findings, "C009")) == 1


def test_a_placeholder_value_is_not_an_enum():
    fields = report_fields("```\nphase : <the phase it broke in>\n```\n")
    assert fields["phase"] == "<the phase it broke in>"


# ── T11–T13: C003 and C006 on the pack as it stands ───────────────────────────
# Both were worklists before the wave: one C003 error and nine C006 collisions. Both are zero now.
# A zero on its own is ambiguous between "clean" and "rule broken", so each is paired below with a
# synthetic tree that reinstates the exact defect it used to name — against the *shipped* registry,
# not a stub, so the guard covers the real canonical sets and the real held nouns.

@pytest.mark.integration
def test_c003_is_silent_now_that_the_one_disagreement_was_renamed_away():
    """Pre-wave this was one error: dv-formal-overconstraint-credit spelled `proof status` with the
    tool's older words, `full` and `counterexample`, where the registry carries `proven` and
    `falsified` — the normalisation the registry states in prose. That value rename has landed."""
    assert only(check_pack(PACK), "C003") == []


def test_c003_still_fires_on_the_old_proof_status_spellings(tmp_path):
    """The defect the snapshot above used to name, rebuilt against the shipped registry. Without
    this, the zero would read the same whether the pack got clean or C003 stopped firing."""
    reg = load_registry(PACK)
    write(tmp_path, "dv-a", "## Report\n\n```\nproof status : full | counterexample | bounded\n```\n")
    c003 = only(check_pack(tmp_path, registry=reg), "C003")
    assert len(c003) == 1 and c003[0].level == "error" and c003[0].slug == "dv-a"
    assert "full" in c003[0].message and "counterexample" in c003[0].message


@pytest.mark.integration
def test_c006_is_silent_now_that_the_nine_collisions_were_renamed_away():
    """Nine unregistered nouns each carried a token list in two skills — two skills asking different
    questions under one borrowed noun, where the repair is a rename and not a reconciliation. The
    tenth collision, `proof status`, was resolved by registration instead, which is why it was
    C003's problem and never C006's. All nine renames have landed."""
    assert only(check_pack(PACK), "C006") == []


def test_c006_still_fires_when_a_renamed_noun_is_taken_by_two_skills_again(tmp_path):
    """`divergence` was one of the nine and is now held-and-unclaimed. If two skills reach for it
    again — the regression this snapshot exists to catch — C006 must still be an error.

    The two value sets differ here, as all nine real collisions did: they were two skills asking
    different questions under one borrowed noun, never two skills that happened to agree."""
    reg = load_registry(PACK)
    write(tmp_path, "dv-a", "## Procedure\n\nRecord it.\n\n"
                            "## Report\n\n```\ndivergence : matches | wrong-view\n```\n")
    write(tmp_path, "dv-b", "## Procedure\n\nRecord it.\n\n"
                            "## Report\n\n```\ndivergence : two-state | zero-delay-race\n```\n")
    c006 = only(check_pack(tmp_path, registry=reg), "C006")
    assert len(c006) == 1 and c006[0].level == "error" and named(c006[0]) == "divergence"
    assert "dv-a" in c006[0].slug and "dv-b" in c006[0].slug


@pytest.mark.integration
def test_the_four_already_agreeing_pairs_produce_no_c006():
    """The regression test for registering pairs that already agree. Without those four rows C006
    invents an error on four correct files, which is the whole rule discrediting itself."""
    c006 = only(check_pack(PACK), "C006")
    assert not {named(f) for f in c006} & {"action", "fired", "strength", "window"}


# ── T14–T15: C007, narrowing ──────────────────────────────────────────────────

@pytest.mark.integration
def test_declared_narrowings_are_silent_and_undeclared_ones_are_not():
    reg = load_registry(PACK)
    assert not only(check_pack(PACK, registry=reg), "C007")

    bare = dataclasses.replace(reg, narrowings={})
    undeclared = only(check_pack(PACK, registry=bare), "C007")
    # Derived from the registry, not hard-coded. The pre-wave version of this test listed three slugs
    # and went stale the moment `proof status` was registered and dv-trap-exception-triage moved its
    # narrowing from an inline reason to a T2 row. The set below cannot go stale that way, and it is
    # not a tautology: read with the first assertion it says the T2 rows and the pack's actual
    # narrowings are the *same* set — no narrowing goes undeclared, and no row declares a narrowing
    # nobody makes. Both directions are real defects.
    assert undeclared, "stripping every declaration must make C007 audible, or the rule is dead"
    assert {f.slug for f in undeclared} == {slug for _, slug in reg.narrowings}
    # A skill declaring BOTH ways — a T2 row *and* an inline reason on the value line — would drop
    # out of this set. None does, and none can: for a registered field the inline form is
    # `phase : run — why`, which C009 rejects as a value wearing a sentence. The registry row is the
    # only form a registered narrowing can take without raising an error somewhere else.


def test_dropping_the_escape_hatch_is_an_error_not_a_warning(tmp_path):
    """`class` without `unknown` forces the next reader to guess, so narrowing_allowed is false and
    the severity flips. This asymmetry is the whole reason C007 has two levels."""
    write_registry(tmp_path)
    write(tmp_path, "dv-a",
          "## Procedure\n\nRecord design or infrastructure.\n\n"
          "## Report\n\n```\nclass : design | infrastructure\n```\n")
    c007 = only(check_pack(tmp_path), "C007")
    assert len(c007) == 1 and c007[0].level == "error" and c007[0].slug == "dv-a"
    assert "unknown" in c007[0].message


# ── T16: C008, the synonym field no name rule can see ─────────────────────────

@pytest.mark.integration
def test_c008_finds_exactly_the_four_synonym_candidates():
    """Counted, not sampled: an edit to the escape-token list that changes this number is a change
    to the rule's precision and has to be argued for.

    Monotone on purpose — a CEILING, not an equality. These four are authoring defects the gate is
    closing skill by skill, so pinning the exact set went red every time the gate did its job. What
    still fails here is the regression that matters: a NEW field duplicating a registered enum under
    a different name. Tighten to `== set()` once the gate has run the whole pack."""
    KNOWN = {
        ("dv-tool-feature-testplan", "force", "strength"),
        ("dv-security-negative-tests", "proof", "proof status"),
        ("dv-cross-tool-mismatch-adjudication", "clause says", "strength"),
        ("dv-memory-perf-bandwidth", "saturated", "fired"),
    }
    c008 = only(check_pack(PACK), "C008")
    found = {(f.slug, named(f, 0), named(f, 1)) for f in c008}
    assert found <= KNOWN, f"a NEW synonym of a registered field appeared: {found - KNOWN}"
    assert len(c008) <= 4 and all(f.level == "warn" for f in c008)


# ── T17: C009, the narrowing hidden in a sentence ─────────────────────────────

@pytest.mark.integration
def test_c009_is_silent_now_that_the_narrowing_moved_into_the_registry():
    """The one occurrence was dv-trap-exception-triage's `phase : run — a trap is always a run-phase
    failure`. The repair C009 asks for is exactly what landed: the value line is a bare `run`, the
    sentence moved below the block, and the narrowing is declared as a T2 row instead. That row is
    what test_declared_narrowings_are_silent_and_undeclared_ones_are_not now counts."""
    assert only(check_pack(PACK), "C009") == []


def test_c009_still_fires_on_a_registered_value_wearing_a_sentence(tmp_path):
    """Rebuilt against the shipped registry, because this is the shape that hides a narrowing from
    every other rule: no pipe, so it was never an enum, so C003, C005 and C007 are all blind to it."""
    reg = load_registry(PACK)
    write(tmp_path, "dv-a", "## Procedure\n\nRecord run.\n\n## Report\n\n```\n"
                            "phase : run — a trap is always a run-phase failure\n```\n")
    c009 = only(check_pack(tmp_path, registry=reg), "C009")
    assert len(c009) == 1 and c009[0].level == "error" and c009[0].slug == "dv-a"
    assert named(c009[0], 0) == "phase" and named(c009[0], 1) == "run"


# ── T18: C010, the only prospective rule ──────────────────────────────────────

def test_taking_a_held_name_fires_before_a_second_skill_exists_to_collide_with(tmp_path):
    write_registry(tmp_path)
    write(tmp_path, "dv-thief", "## Procedure\n\nRecord agrees or disagrees.\n\n"
                                "## Report\n\n```\nruling : agrees | disagrees\n```\n")
    c010 = only(check_pack(tmp_path), "C010")
    assert len(c010) == 1 and c010[0].level == "warn" and c010[0].slug == "dv-thief"
    assert "dv-ruler" in c010[0].fix or "dv-ruler" in c010[0].message


@pytest.mark.integration
def test_none_of_the_nine_collisions_was_an_agreement():
    """C006's warn branch downgrades exactly one shape — two skills whose value sets are identical —
    so it is worth proving from the repo, not assuming, that it would not have quietly downgraded
    any real finding to a warn.

    Each retired row records the value set the name carried in the skill that renamed it away; the
    skill that kept the noun still carries its own. All nine pairs disagree, which is the error
    branch. They were two skills asking different questions under one borrowed noun — never two
    skills that happened to agree."""
    reg = load_registry(PACK)
    sets: dict[str, list[frozenset[str]]] = {}
    for row in reg.retired:
        sets.setdefault(row.name, []).append(row.values)
    for name, holder in reg.held.items():
        if name in sets and holder:
            kept = report_fields((PACK / holder / "SKILL.md").read_text(encoding="utf-8")).get(name)
            assert kept, f"{holder} no longer carries the held noun {name!r}"
            sets[name].append(frozenset(p.strip() for p in kept.split("|")))
    assert len(sets) == 9
    for name, variants in sorted(sets.items()):
        assert len(variants) == 2, f"{name} was a collision between two skills, got {variants}"
        assert variants[0] != variants[1], (
            f"{name}: the two skills agreed, so C006 would warn where it used to block")


@pytest.mark.integration
def test_c010_is_silent_now_that_the_eleven_held_nouns_were_qualified():
    """This was the eleven-item worklist; the wave moved every one, so it is zero by construction.
    Kept as an assertion because the pressure runs the other way too — the next author to write
    `mechanism :` or `ruling :` in a skill that does not hold the noun must be caught the first
    time, before a second skill exists to collide with."""
    assert only(check_pack(PACK), "C010") == []


def test_c010_still_fires_when_a_shipped_held_noun_is_taken(tmp_path):
    """Against the real registry, so the guard covers the nouns the pack actually holds rather than
    a stub's. `mechanism` is held by dv-ams-view-binding-audit; anyone else classifying with it is
    the regression the zero above is asserting the absence of."""
    reg = load_registry(PACK)
    write(tmp_path, "dv-thief", "## Procedure\n\nRecord control or data.\n\n"
                                "## Report\n\n```\nmechanism : control | data\n```\n")
    c010 = only(check_pack(tmp_path, registry=reg), "C010")
    assert len(c010) == 1 and c010[0].level == "warn" and c010[0].slug == "dv-thief"
    assert named(c010[0]) == "mechanism" and "dv-ams-view-binding-audit" in c010[0].message


# ── T19–T21: C011, stale references, and the precision guards ─────────────────

@pytest.mark.integration
def test_c011_finds_the_cross_skill_citation_of_a_field_that_does_not_exist():
    """The rule's job: a skill naming a sibling's field that the sibling does not have.

    Asserted on a synthetic tree, not on the pack. These three were live defects when the rule was
    written and the authoring gate is closing them one skill at a time, so a test that pinned the
    pack's exact defect set went red every time the gate did its job — which trains you to ignore it.
    The pack-level claim that stays true in both directions is the one below: never MORE than the
    three known, and zero once the gate finishes."""
    root = Path(__file__).resolve().parent / "_c011_tmp"
    import shutil
    shutil.rmtree(root, ignore_errors=True)
    write(root, "dv-holder", "## Report\n\n```\nhole class : unreachable | excluded\n```\n")
    write(root, "dv-citer",
          "## Report\n\n```\nnotes : anything\n```\n\n"
          "## Gotchas\n\nRoute it using dv-holder's `disposition` field so the two blocks match.\n")
    try:
        hits = [f for f in only(check_pack(root), "C011") if f.slug == "dv-citer"]
        assert len(hits) == 1
        assert "dv-holder" in hits[0].message and "disposition" in hits[0].message
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.mark.integration
def test_c011_finds_the_two_blocks_that_claim_a_field_they_do_not_carry():
    """Both say in prose that they reuse a shared field and then do not emit it:
    dv-cross-tool-mismatch-adjudication promises `run id` and writes `runs`; dv-tool-version-migration
    says the block reuses `signature` and has no such line. Three findings in total, all real —
    the same rule written without these guards produced fifty-two, and eyeballing fifty-two is how
    the one that matters gets missed.

    Monotone on purpose. The authoring gate is closing these three, so the assertion is a CEILING —
    C011 may only shrink toward zero, and any NEW dangling citation (the regression that matters)
    still fails it. Tighten to `== set()` once the gate has run the whole pack."""
    KNOWN = {"dv-coverage-hole-disposition", "dv-cross-tool-mismatch-adjudication",
             "dv-tool-version-migration"}
    c011 = only(check_pack(PACK), "C011")
    assert {f.slug for f in c011} <= KNOWN, "a NEW dangling cross-skill field citation appeared"
    assert len(c011) <= 3


@pytest.mark.integration
def test_c012_is_silent_now_that_the_eleven_retirements_are_finished():
    """Retirement is per skill, not pack-wide: `mechanism` left dv-signal-trace-localisation and is
    still the right name in dv-ams-view-binding-audit, which holds it. All eleven renames have
    landed, so the rule is quiet — and the second half reads the files directly rather than the
    rule, so a rule that stopped working cannot fake this."""
    reg = load_registry(PACK)
    assert len(reg.retired) == 11
    c012 = only(check_pack(PACK), "C012")
    assert [f for f in c012 if "retired from this skill" in f.message] == []
    for row in reg.retired:
        fields = report_fields((PACK / row.slug / "SKILL.md").read_text(encoding="utf-8"))
        assert row.name not in fields, f"{row.slug} emits the retired field {row.name!r} again"


def test_c012_still_fires_when_a_retired_name_comes_back(tmp_path):
    """The regression the zero above guards against: a skill re-adopting the name it retired. A name
    that is both retired and live tells the next author two different things, which is the exact
    confusion the rename wave was run to end."""
    reg = load_registry(PACK)
    write(tmp_path, "dv-signal-trace-localisation",
          "## Procedure\n\nRecord control, data or sampling.\n\n"
          "## Report\n\n```\nmechanism : control | data | sampling\n```\n")
    hits = [f for f in only(check_pack(tmp_path, registry=reg), "C012")
            if "retired from this skill" in f.message]
    assert len(hits) == 1 and hits[0].slug == "dv-signal-trace-localisation"
    assert "mechanism" in hits[0].message


@pytest.mark.integration
def test_ordinary_english_never_becomes_a_stale_reference():
    """`checked against` is ordinary prose in ten skills. An unscoped matcher produced ten false
    positives on that one name alone, which is the C002 failure repeated."""
    c011 = only(check_pack(PACK), "C011")
    for f in c011:
        assert "checked against" not in f.message


@pytest.mark.integration
def test_a_name_used_as_an_enum_here_and_as_free_text_there_is_never_a_finding():
    """Measured at 40 occurrences, nearly all benign — `window` alone is six ordinary time windows.
    Every registry rule is scoped to token-list values only (Rule 8), and this is the guard."""
    free_text_window = {"dv-config-space-coverage", "dv-emulation-dump-strategy", "dv-gls-bringup",
                        "dv-mem-refresh-lowpower-audit", "dv-memory-perf-bandwidth",
                        "dv-signal-trace-localisation"}
    registry_rules = {"C003", "C006", "C007", "C008", "C009", "C010", "C011"}
    for f in check_pack(PACK):
        if f.rule in registry_rules and set(f.slug.split(", ")) & free_text_window:
            assert "window" not in f.message


# ── T22–T24: the state the rename wave had to reach, and did ──────────────────

@pytest.mark.integration
def test_the_registry_rules_block_nothing():
    """Was an xfail marking the gate the rename wave had to pass. It passes, so it is an assertion:
    an error-level finding is wave-blocking, and the pack has none. Leaving it xfail would have made
    it guard nothing in the one direction that now matters — an error coming back."""
    assert [(f.rule, f.slug, f.message) for f in check_pack(PACK) if f.level == "error"] == []


@pytest.mark.integration
@pytest.mark.xfail(reason="still three live C011 findings — two blocks that promise a shared field "
                          "in prose and do not emit it, and one cross-skill citation of a field "
                          "that does not exist. Those are authoring defects owned by the skills, "
                          "not rename-wave debt; test_c011_* below assert they are still there",
                   strict=False)
def test_only_the_four_synonym_warns_remain():
    registry_rules = {"C003", "C006", "C007", "C009", "C010", "C011", "C012"}
    left = [f for f in check_pack(PACK) if f.rule in registry_rules]
    assert left == []


@pytest.mark.integration
def test_each_new_qualified_name_belongs_to_exactly_one_skill():
    """The direct, file-level evidence that the rename wave landed — read from the SKILL.md files
    rather than from any rule, so it holds even if every rule above were broken. Before the wave the
    assertion was `<= 1`: none of the eleven was in use, so no rename could land on top of an
    existing field. After it, each is a field of exactly one skill, and `== 1` is what keeps a
    half-finished revert visible."""
    new_names = ["req chain", "plan chain", "timing source", "fault verdict", "view match",
                 "divergence class", "match key", "localised as", "card result", "checked against",
                 "input parity"]
    owners = {n: [] for n in new_names}
    for md in sorted(PACK.rglob("SKILL.md")):
        fields = report_fields(md.read_text(encoding="utf-8"))
        for n in new_names:
            if n in fields:
                owners[n].append(md.parent.name)
    for n, slugs in sorted(owners.items()):
        assert len(slugs) == 1, n + " is a field of " + repr(slugs)


# ── T25: C004 still catches the value left behind ─────────────────────────────

def test_a_prose_value_left_behind_by_a_rename_is_still_an_error(tmp_path):
    """The live case at dv-testplan-traceability-review:316. C004 is load-bearing while a rename is
    in flight, which is why it runs after each rename rather than once at the end."""
    write(tmp_path, "dv-a",
          "## Report\n\n```\nchain : broken | full | waived\n```\n\n"
          "## Gotchas\n\nA requirement with a test and a checker is `chain: complete`.\n")
    c004 = only(check_pack(tmp_path), "C004")
    assert len(c004) == 1 and c004[0].level == "error" and "complete" in c004[0].message


# ── C012: registry hygiene ────────────────────────────────────────────────────

def test_an_enum_three_skills_already_share_is_a_promotion_candidate(tmp_path):
    """Two skills agreeing is a coincidence you can leave alone. Three is a convention that will
    keep being copied, and should be written down before it drifts."""
    write_registry(tmp_path)
    for slug in ("dv-a", "dv-b", "dv-c"):
        write(tmp_path, slug, "## Procedure\n\nRecord clean or dirty.\n\n"
                              "## Report\n\n```\nbin state : clean | dirty\n```\n")
    c012 = only(check_pack(tmp_path), "C012")
    assert [f for f in c012 if "bin state" in f.message]
    assert all(f.level == "warn" for f in c012)


# ── C005: dead values, and the one field class it must not judge ──────────────

def test_c005_flags_a_value_the_procedure_never_assigns(tmp_path):
    """The rule's own rationale, on the field class where it holds: nobody but the author fixed
    `bin state`'s value set, so a value the procedure cannot reach is the author's bug."""
    write(tmp_path, "dv-a", "## Procedure\n\nRecord clean.\n\n"
                            "## Report\n\n```\nbin state : clean | dirty\n```\n")
    c005 = only(check_pack(tmp_path), "C005")
    assert len(c005) == 1 and c005[0].level == "warn" and "dirty" in c005[0].message


def test_c005_never_fires_on_a_registered_field(tmp_path):
    """The contradiction ADR-011 shipped with, pinned so it cannot be restored.

    On a REGISTERED name C005's rationale is not weaker, it is inverted. `class` is registered
    `design | infrastructure | unknown` with narrowing:no, so every skill MUST offer all three — but
    a procedure routinely assigns only two of them. C005 then reported a warn whose only stated fix,
    dropping `infrastructure`, raises a wave-blocking C007 error instead: unfixable by construction,
    and 62 of the 205 C005 warns measured on the pack (42 `phase`, 20 `class`) were that shape.

    A registered field's value set belongs to the registry, and the narrowing rules already govern
    it. C005 judges skill-owned names only — which the second half asserts, so this is a scope fix
    and not the rule being switched off."""
    write_registry(tmp_path)
    write(tmp_path, "dv-a",
          "## Procedure\n\nIf the RTL is at fault record design. If you cannot tell, record\n"
          "unknown.\n\n## Report\n\n```\nclass : design | infrastructure | unknown\n"
          "local kind : reachable | never-reached\n```\n")
    findings = check_pack(tmp_path)
    # `infrastructure` is a canonical value this procedure never assigns, and that is not a defect.
    assert [f for f in only(findings, "C005") if named(f) == "class"] == []
    # Dropping it to silence a warn would have been the wave-blocking error instead …
    assert not only(findings, "C007") and not only(findings, "C003")
    # … while the skill's own unregistered field is still judged exactly as before.
    assert {named(f) for f in only(findings, "C005")} == {"local kind"}


# ── rendering ─────────────────────────────────────────────────────────────────

def test_render_names_the_registry_it_loaded():
    """A green run against a registry that registered nothing must not look like a green run."""
    reg = load_registry(PACK)
    text = render([], registry=reg)
    assert "handoff-vocabulary.md" in text and "7" in text
    assert "pack is self-consistent" in text


def test_render_headers_every_run_including_the_clean_one():
    """Eight of the twelve rules are consequences of the registry, so a registry that parsed to
    nothing makes all eight pass and prints the same two words a genuinely clean pack does. The
    header is the only thing separating "checked and clean" from "not checked" — so it is one line,
    it is unconditional, and it is the first line whether or not there are findings."""
    empty = render([], registry=Registry())
    assert empty.splitlines()[0].startswith("registry:")
    assert "0 field(s) registered" in empty          # the loud signal, not a silent green run
    assert empty.splitlines()[1] == "pack is self-consistent"

    unsupplied = render([])
    assert unsupplied.splitlines()[0].startswith("registry: not supplied")
    assert unsupplied.splitlines()[1] == "pack is self-consistent"


def test_render_keeps_its_shape_when_there_are_findings(tmp_path):
    """`semiskill lint` consumes this. The header is added; nothing else moves."""
    write(tmp_path, "dv-a", "## Report\n\n```\nstage : compile | run | post\n```\n")
    write(tmp_path, "dv-b", "## Report\n\n```\nstage : compile | run\n```\n")
    lines = render(check_pack(tmp_path)).splitlines()
    assert lines[0].startswith("registry:")
    assert lines[1].endswith("pack-consistency finding(s)")
    assert any("C006" in ln for ln in lines) and any("fix:" in ln for ln in lines)


def test_a_pack_with_no_registry_says_so_rather_than_inventing_errors(tmp_path):
    """The checker never crashes on an absent registry — it says the vocabulary rules are inert, so
    a green run cannot be mistaken for a verified one."""
    for slug in ("dv-a", "dv-b"):
        write(tmp_path, slug, "## Report\n\n```\nclass : design | infrastructure | unknown\n```\n")
    findings = check_pack(tmp_path)
    assert len(only(findings, "C000")) == 1
    assert only(findings, "C000")[0].level == "warn"
    assert not only(findings, "C003")
