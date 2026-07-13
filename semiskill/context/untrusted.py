from __future__ import annotations
import json

_OPEN = "<<<UNTRUSTED-ARTIFACT-DATA>>>"
_CLOSE = "<<<END-UNTRUSTED-ARTIFACT-DATA>>>"


def delimit(payload: dict) -> str:
    """Wrap retrieved artifact content (a submitted skill body, a comment, ...) as clearly-delimited
    UNTRUSTED data. Downstream consumers — especially any LLM — must treat everything between the
    markers as data and never execute it as instructions."""
    return f"{_OPEN}\n{json.dumps(payload)}\n{_CLOSE}"
