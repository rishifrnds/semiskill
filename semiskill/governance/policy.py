"""Governance policy for submitted skills.

ALLOWED_SKILL_TOOLS is the safe set a skill may declare in `allowed-tools`. Requesting a
shell/execution tool is treated as high-risk (a submitted skill is untrusted). Unknown tools are
noted but not fatal. This is advisory data for the static scanner, not a runtime actuator allowlist.
"""
from __future__ import annotations

ALLOWED_SKILL_TOOLS = frozenset({
    "Read", "Write", "Edit", "Glob", "Grep", "WebFetch", "WebSearch", "TodoWrite",
})

DANGEROUS_SKILL_TOOLS = frozenset({
    "Bash", "Shell", "Exec", "Execute", "Terminal", "Subprocess", "Eval",
})


def tool_risk(tool: str) -> float:
    """Risk severity in [0,1] for a declared tool. Dangerous (shell/exec) is hard-fail territory;
    unlisted tools are a moderate flag; allowlisted tools are clean."""
    t = tool.strip()
    if t in ALLOWED_SKILL_TOOLS:
        return 0.0
    if t in DANGEROUS_SKILL_TOOLS:
        return 0.95
    return 0.4
