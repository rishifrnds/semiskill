"""Drift guard: the linter must never disagree with the scanners it predicts.

The linter exists so an author sees a finding at authoring time instead of a silent
`published=False` three steps later. That promise holds only while the linter's positional regexes
and the real scanners' regexes fire on the same text. This test is what fails the day someone edits
`scanners/static_structure.py` or `scanners/secret_pii.py` without updating
`authoring/lint_body.py` — the failure mode that would otherwise be discovered by a half-published
40-skill wave.

Scope: stages 1 and 4 only, body-only submissions (no declared tools, no bundled files) so the
comparison is like-for-like. Stage 3 is deliberately not mirrored and so cannot drift.
"""
import pytest

from semiskill.authoring.lint import lint_text
from semiskill.authoring.lint_body import lint_body
from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.secret_pii import SecretPiiScanner
from semiskill.scanners.static_structure import StaticStructureScanner

# Bodies chosen to exercise every mirrored rule, including the ordinary-English false positives that
# make authoring hard. These are inert data — nothing here is executed.
BODIES = [
    "A clean procedure. Use Grep to find the first fatal marker, then read a bounded window.",
    "See https://example.com/spec for the register map.",
    "Then curl the artifact from the archive.",
    "Compute the transfer function (H(s)) for the loop.",
    "Call eval(expr) on the parsed value.",
    "Use subprocess.run to drive the tool.",
    "Upgrade to version 10.2.1.4 of the simulator.",
    "Part number 123-45-6789 is the qualified device.",
    "Lot 1234-5678-9012-3456 shipped last week.",
    "Open https://build.corp/results for the nightly.",
    "token: ABCDEFGHIJKLMNOPQRSTUVWX is the placeholder.",
    "-----BEGIN RSA PRIVATE KEY----- redacted",
    "blob " + "A" * 240,
    "Header eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.signature",
    "A body with several at once: https://x.example and version 10.1.2.3 and eval(y).",
    "x" * 50_001,
]


def _submission(body: str) -> SkillSubmission:
    return SkillSubmission(slug="s", name="n", body=body, files={}, allowed_tools=())


@pytest.mark.parametrize("body", BODIES, ids=lambda b: (b[:38] + "…") if len(b) > 38 else b)
def test_linter_predicts_the_same_codes_as_the_scanners(body):
    sub = _submission(body)
    expected = {
        *(f.code for f in StaticStructureScanner().scan(sub).findings),
        *(f.code for f in SecretPiiScanner().scan(sub).findings),
    }
    predicted = {f.scanner_code for f in lint_body(body)
                 if f.scanner_code is not None and f.stage in (1, 4)}
    assert predicted == expected, (
        f"linter/scanner drift.\n  scanner: {sorted(expected)}\n  linter:  {sorted(predicted)}\n"
        "Update semiskill/authoring/lint_body.py to match the scanner, or vice versa."
    )


@pytest.mark.parametrize("body", BODIES, ids=lambda b: (b[:38] + "…") if len(b) > 38 else b)
def test_reported_stage_scores_come_from_the_real_scanners(body):
    """The linter must never invent a score — it reports what the scanner computed."""
    sub = _submission(body)
    md = f"---\nname: n\ndescription: d. Use when x.\n---\n{body}"
    report = lint_text(text=md)
    assert report.stage_safety[1] == StaticStructureScanner().scan(sub).safety_score
    assert report.stage_safety[4] == SecretPiiScanner().scan(sub).safety_score


def test_thresholds_are_imported_not_hardcoded():
    """A local copy of 0.8/0.5 would silently diverge the day the pipeline recalibrates."""
    import semiskill.authoring.lint as lint_mod
    from semiskill.spine import pipeline
    assert lint_mod.APPROVE_THRESHOLD is pipeline.APPROVE_THRESHOLD
    assert lint_mod.REJECT_THRESHOLD is pipeline.REJECT_THRESHOLD


def test_stage3_is_never_claimed_authoritative_without_a_probe():
    r = lint_text(text="---\nname: n\ndescription: d. Use when x.\n---\nbody text here")
    assert r.stage3_authoritative is False
    assert r.stage_safety.get(3) is None
