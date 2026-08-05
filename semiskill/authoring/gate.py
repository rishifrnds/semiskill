"""The content gate record — `skills/<slug>/REVIEW.json`, written by the authoring gate.

A skill's *security* verdict comes from the pipeline; its *content* verdict comes from this file:
an independent recheck, by an agent that neither wrote nor fixed the skill, recording
`recheck.ready: true|false`. The recurring failure mode this exists to stop is an author declaring
its own fix ready.

This module is the single reader. Two callers depend on it and they must not be able to disagree:

  * `semiskill.wave` — refuses to publish a skill whose recheck is not ready (the precondition).
  * `semiskill.authoring.scoreboard` — reports which published skills got one (the audit).

It lives here, below both, so the wave driver never has to import a reporting module.
"""
from __future__ import annotations

import json
from pathlib import Path

REVIEW_FILENAME = "REVIEW.json"

# Gate status for a skill, worst to best.
UNREVIEWED = "unreviewed"
REVIEWED = "reviewed"
READY = "recheck-ready"


def read_review_dir(skill_dir: str | Path) -> dict | None:
    """The gate record sitting beside a SKILL.md, or None when it is absent or unreadable.

    Unreadable collapses to None deliberately: a record that cannot be parsed proves nothing, and
    the callers treat "no usable record" as the same refusal. Use `has_review` to tell the two
    apart when the *reason* matters to a human.
    """
    p = Path(skill_dir) / REVIEW_FILENAME
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None


def has_review(skill_dir: str | Path) -> bool:
    """Whether a REVIEW.json file exists at all — parseable or not."""
    return (Path(skill_dir) / REVIEW_FILENAME).exists()


def read_review(skills_root: str | Path, slug: str) -> dict | None:
    """The gate record for `slug` under a skills root."""
    return read_review_dir(Path(skills_root) / slug)


def gate_status(review: dict | None) -> str:
    """Classify a gate record. Only an explicit `recheck.ready is True` counts as READY."""
    if not review:
        return UNREVIEWED
    recheck = review.get("recheck") or {}
    if recheck.get("ready") is True:
        return READY
    if review.get("findings") is not None or review.get("review"):
        return REVIEWED
    return UNREVIEWED
