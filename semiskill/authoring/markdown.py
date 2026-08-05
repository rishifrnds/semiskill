"""A deliberately restricted Markdown renderer for UNTRUSTED skill bodies.

Skill bodies are submitter-controlled content that this project treats as an injection payload
everywhere else; rendering one into a page with a general-purpose Markdown library would undo that in
one line, because every mainstream renderer passes raw HTML through by default.

The rule here is **escape first, then re-admit a fixed subset**. `html.escape` runs over the whole
document before any parsing, so no tag a body contains can ever reach the output as markup — an
`<img onerror=...>` is inert text by the time the parser sees it. The parser then emits its own tags
around that already-safe text. There is no path by which body content becomes an attribute value.

Admitted: headings, paragraphs, unordered/ordered lists, GFM pipe tables, fenced and inline code,
bold, italic, blockquotes, horizontal rules.

**Links and images are rendered as inert text, never anchors.** A catalog whose entire purpose is
trustworthiness must not turn text an author controls into a clickable destination — and skills are
lint-blocked from containing URLs anyway, so an anchor here would only ever be a smell.
"""
from __future__ import annotations

import html
import re

__all__ = ["render_markdown", "strip_markdown"]

_H = re.compile(r"^(#{1,6})\s+(.*)$")
_HR = re.compile(r"^(?:---+|\*\*\*+|___+)\s*$")
_UL = re.compile(r"^\s*[-*+]\s+(.*)$")
_OL = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")
# `&gt;` because escaping runs before parsing — the security property costs us the raw marker.
_QUOTE = re.compile(r"^(?:&gt;|>)\s?(.*)$")
_FENCE = re.compile(r"^\s*```+\s*([A-Za-z0-9_+-]*)\s*$")
_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")

# Inline. Applied to ALREADY-ESCAPED text, so these can never match across a tag boundary.
_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*]+?)(?<=\S)\*(?![\w*])")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
# [[FILL: ...]] is the pack's personalisation marker — surfaced, never hidden.
_FILL = re.compile(r"\[\[FILL:([^\]]*)\]\]")

_PLACEHOLDER = "\x00CODE{}\x00"


def _inline(escaped: str) -> str:
    """Inline formatting over already-escaped text."""
    # Code spans are extracted first so ** and * inside them are not treated as emphasis.
    spans: list[str] = []

    def _stash(m: re.Match) -> str:
        spans.append(m.group(1))
        return _PLACEHOLDER.format(len(spans) - 1)

    out = _CODE.sub(_stash, escaped)

    out = _IMAGE.sub(lambda m: f"[image: {m.group(1) or m.group(2)}]", out)
    out = _LINK.sub(lambda m: f"{m.group(1)} ({m.group(2)})" if m.group(2) else m.group(1), out)
    out = _FILL.sub(lambda m: f'<span class="fill">[[FILL:{m.group(1)}]]</span>', out)
    out = _BOLD.sub(r"<strong>\1</strong>", out)
    out = _ITALIC.sub(r"<em>\1</em>", out)

    for i, code in enumerate(spans):
        out = out.replace(_PLACEHOLDER.format(i), f"<code>{code}</code>")
    return out


def _cells(line: str) -> list[str]:
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def render_markdown(text: str) -> str:
    """Render untrusted Markdown to a safe HTML fragment."""
    escaped = html.escape(text, quote=True)
    lines = escaped.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    def close(stack: list[str]) -> None:
        while stack:
            out.append(f"</{stack.pop()}>")

    stack: list[str] = []          # open list elements, innermost last
    para: list[str] = []

    def flush_para() -> None:
        if para:
            out.append(f"<p>{_inline(' '.join(para).strip())}</p>")
            para.clear()

    while i < n:
        line = lines[i]

        fence = _FENCE.match(line)
        if fence:
            flush_para()
            close(stack)
            lang = fence.group(1)
            body: list[str] = []
            i += 1
            while i < n and not _FENCE.match(lines[i]):
                body.append(lines[i])
                i += 1
            i += 1                                  # consume the closing fence
            cls = f' class="lang-{lang}"' if lang else ""
            out.append(f"<pre><code{cls}>{chr(10).join(body)}</code></pre>")
            continue

        if not line.strip():
            flush_para()
            close(stack)
            i += 1
            continue

        # GFM pipe table: a header row followed by a separator row.
        if "|" in line and i + 1 < n and _TABLE_SEP.match(lines[i + 1]):
            flush_para()
            close(stack)
            head = _cells(line)
            rows: list[list[str]] = []
            i += 2
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append(_cells(lines[i]))
                i += 1
            out.append("<table><thead><tr>"
                       + "".join(f"<th>{_inline(c)}</th>" for c in head)
                       + "</tr></thead><tbody>")
            for r in rows:
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in r) + "</tr>")
            out.append("</tbody></table>")
            continue

        h = _H.match(line)
        if h:
            flush_para()
            close(stack)
            lvl = min(6, len(h.group(1)) + 1)       # demote: the page owns <h1>
            out.append(f"<h{lvl}>{_inline(h.group(2).strip())}</h{lvl}>")
            i += 1
            continue

        if _HR.match(line):
            flush_para()
            close(stack)
            out.append("<hr>")
            i += 1
            continue

        q = _QUOTE.match(line)
        if q:
            flush_para()
            close(stack)
            body = [q.group(1)]
            i += 1
            while i < n and _QUOTE.match(lines[i]):
                body.append(_QUOTE.match(lines[i]).group(1))
                i += 1
            out.append(f"<blockquote><p>{_inline(' '.join(body).strip())}</p></blockquote>")
            continue

        ul = _UL.match(line)
        ol = _OL.match(line)
        if ul or ol:
            flush_para()
            want = "ul" if ul else "ol"
            if not stack or stack[-1] != want:
                close(stack)
                out.append(f"<{want}>")
                stack.append(want)
            out.append(f"<li>{_inline((ul or ol).group(1 if ul else 2).strip())}</li>")
            i += 1
            continue

        close(stack)
        para.append(line.strip())
        i += 1

    flush_para()
    close(stack)
    return "\n".join(out)


def strip_markdown(text: str, *, limit: int | None = None) -> str:
    """Plain text with the markup removed — for meta descriptions and search indexes."""
    s = re.sub(r"```.*?```", " ", text, flags=re.S)
    s = _IMAGE.sub(lambda m: m.group(1), s)
    s = _LINK.sub(lambda m: m.group(1), s)
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.M)
    s = re.sub(r"[`*_>|]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    if limit is not None and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + "…"
    return s
