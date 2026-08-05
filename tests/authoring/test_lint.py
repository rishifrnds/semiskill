"""Frontmatter-contract and predicted-verdict tests for the full linter."""
import json
import pytest

from semiskill.authoring.lint import lint_text, lint_skill_dir, lint_wave_dir, render

GOOD_BODY = """
# First-Error Extraction

Pull the true first error out of a long simulation log instead of the cascade that follows it.

## Fill this in for our team

| Slot | What to fill in |
|---|---|
| log root | [[FILL: where our regression logs land]] |

## Procedure

1. Use **Grep** for the first fatal marker, then read a bounded window around it.
2. Classify the failure and name the next artifact to look at.
3. Ask the engineer to re-run that seed and paste the tail.

## Gotchas

The first line printed is rarely the first failure; earlier warnings usually carry the cause.

## Human verification

A wrong answer names a cascade line as the root cause. Check the timestamp ordering.
"""


_DEFAULT = object()


def md(*, name="dv-sim-log-first-error", description=_DEFAULT, tools="Read Grep Glob",
       function="design-verification", role="dv-engineer", level="intermediate",
       extra_top="", body=GOOD_BODY, metadata=True):
    if description is _DEFAULT:      # a sentinel, so description="" is testable
        description = ("Extract the true first error from a simulation log. "
                       "Use when a run failed and the log is too large to read.")
    meta = ("metadata:\n"
            f"  semiskill-title: First-Error Extraction\n"
            f"  semiskill-function: {function}\n"
            f"  semiskill-role: {role}\n"
            f"  semiskill-level: {level}\n"
            f"  semiskill-version: 1.0.0\n") if metadata else ""
    return (f"---\nname: {name}\ndescription: {description}\n"
            f"allowed-tools: {tools}\n{extra_top}{meta}---\n{body}")


def rules(report):
    return {f.rule for f in report.findings}


def test_a_well_formed_skill_is_clean_and_would_publish():
    r = lint_text(text=md())
    assert r.ok, [f"{f.rule} {f.message}" for f in r.findings]
    assert r.predicted_verdict == "approve"
    assert r.stage_safety[1] == 1.0 and r.stage_safety[4] == 1.0
    assert r.slug == "dv-sim-log-first-error"
    assert r.name == "First-Error Extraction"
    assert r.stage3_authoritative is False       # never claim the corpus was consulted


def test_non_standard_top_level_key_rejected():
    assert "L010" in rules(lint_text(text=md(extra_top="function: design-verification\n")))


def test_name_must_be_kebab():
    assert "L011" in rules(lint_text(text=md(name="DV Sim Log First Error")))


def test_name_must_match_folder(tmp_path):
    d = tmp_path / "dv-something-else"
    d.mkdir()
    (d / "SKILL.md").write_text(md(), encoding="utf-8")
    assert "L012" in {f.rule for f in lint_skill_dir(d).findings}


def test_name_matching_folder_is_clean(tmp_path):
    d = tmp_path / "dv-sim-log-first-error"
    d.mkdir()
    (d / "SKILL.md").write_text(md(), encoding="utf-8")
    r = lint_skill_dir(d)
    assert r.ok and r.predicted_verdict == "approve"


def test_missing_description_is_an_error():
    assert "L013" in rules(lint_text(text=md(description="")))


def test_description_without_a_trigger_warns():
    r = lint_text(text=md(description="Extracts the first error from a log."))
    assert "L022" in rules(r) and r.ok        # a warning, not a blocker


def test_description_angle_brackets_rejected():
    assert "L015" in rules(lint_text(text=md(description="Do <thing>. Use when needed.")))


def test_dangerous_tool_is_an_error():
    r = lint_text(text=md(tools="Read Bash"))
    assert "L017" in rules(r) and not r.ok
    assert r.predicted_verdict == "reject"


def test_unlisted_tool_is_an_error():
    assert "L017" in rules(lint_text(text=md(tools="Read Task")))


def test_unknown_facet_value_is_an_error_with_a_suggestion():
    r = lint_text(text=md(level="senio"))
    f = next(f for f in r.findings if f.rule == "L019")
    assert "senior" in f.fix


def test_missing_facet_warns_only():
    r = lint_text(text=md(metadata=False))
    assert "L020" in rules(r) and r.ok


def test_yaml_scanner_error_is_reported_not_raised():
    """An unquoted 'key: value: value' raises yaml.YAMLError — NOT a ValueError — which uncaught
    aborts an entire wave mid-run. The linter must surface it as a finding."""
    bad = "---\nname: x\ndescription: Guide: do the thing\n---\nbody"
    r = lint_text(text=bad)
    assert r.predicted_verdict == "unparseable" and "L003" in rules(r)


def test_missing_fence_is_reported_not_raised():
    r = lint_text(text="no fence here at all")
    assert r.predicted_verdict == "unparseable" and "L001" in rules(r)


def test_url_in_body_predicts_request_changes_not_approve():
    """The silent killer: 0.3 network-call -> 0.70 -> request-changes -> published=False with no
    exception anywhere."""
    r = lint_text(text=md(body=GOOD_BODY + "\nSee https://example.com/spec\n"))
    assert r.predicted_verdict == "request-changes"
    assert r.stage_safety[1] == pytest.approx(0.7)
    assert "L031" in rules(r)


def test_hard_fail_secret_predicts_reject():
    r = lint_text(text=md(body=GOOD_BODY + "\ntoken: ABCDEFGHIJKLMNOPQRST\n"))
    assert r.predicted_verdict == "reject" and "L040" in rules(r)


def test_slot_in_frontmatter_rejected():
    # quoted, because an unquoted '[[' starts a YAML flow sequence and would be caught by L003 first
    assert "L063" in rules(lint_text(text=md(description="'[[FILL: what]] Use when x.'")))


def test_unquoted_bracket_description_is_caught_as_a_yaml_error():
    assert "L003" in rules(lint_text(text=md(description="[[FILL: what]] Use when x.")))


def test_wave_lint_detects_duplicate_slugs(tmp_path):
    for folder in ("dv-a", "dv-b"):
        d = tmp_path / folder
        d.mkdir()
        (d / "SKILL.md").write_text(md(name=folder), encoding="utf-8")
    # force a slug collision via an explicit metadata slug on both
    for folder in ("dv-a", "dv-b"):
        p = tmp_path / folder / "SKILL.md"
        p.write_text(p.read_text(encoding="utf-8").replace(
            "  semiskill-version: 1.0.0\n", "  semiskill-version: 1.0.0\n  semiskill-slug: dv-same\n"),
            encoding="utf-8")
    wave = lint_wave_dir(tmp_path)
    assert wave.duplicate_slugs and wave.duplicate_slugs[0][0] == "dv-same"
    assert not wave.ok


def test_wave_lint_counts_and_renders(tmp_path):
    d = tmp_path / "dv-sim-log-first-error"
    d.mkdir()
    (d / "SKILL.md").write_text(md(), encoding="utf-8")
    wave = lint_wave_dir(tmp_path)
    assert wave.ok and wave.counts["skills"] == 1 and wave.counts["would_publish"] == 1
    text = render(wave, style="text")
    assert "approve" in text and "stage 3 not evaluated" in text
    payload = json.loads(render(wave, style="json"))
    assert payload["ok"] is True and payload["skills"][0]["slug"] == "dv-sim-log-first-error"
