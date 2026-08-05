from __future__ import annotations
import json

_OPEN = "<<<UNTRUSTED-ARTIFACT-DATA>>>"
_CLOSE = "<<<END-UNTRUSTED-ARTIFACT-DATA>>>"


def delimit(payload: dict) -> str:
    """Wrap retrieved artifact content (a submitted skill body, a comment, ...) as clearly-delimited
    UNTRUSTED data. Downstream consumers — especially any LLM — must treat everything between the
    markers as data and never execute it as instructions.

    The fence only works if the content cannot forge it. `json.dumps` escapes quotes and backslashes
    but leaves `<` alone, so a body containing the literal close marker used to terminate the fence
    early and everything after it read as trusted text. Escaping every `<` to its JSON unicode form
    makes the marker unrepresentable inside the payload while round-tripping losslessly: `json.loads`
    decodes `\\u003c` back to `<`.
    """
    return f"{_OPEN}\n{json.dumps(payload).replace('<', chr(92) + 'u003c')}\n{_CLOSE}"
