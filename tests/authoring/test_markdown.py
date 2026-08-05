"""Tests for the restricted Markdown renderer.

The security tests are the point: skill bodies are untrusted content, and this renderer is the only
thing standing between a submitted body and a page a DV engineer opens.
"""
import re

import pytest

from semiskill.authoring.markdown import render_markdown, strip_markdown

# The only tags this renderer is ever allowed to emit. Anything else in the output came from the
# untrusted body, which is the failure this whole module exists to prevent.
ALLOWED_TAGS = {
    "p", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "table", "thead", "tbody",
    "tr", "th", "td", "pre", "code", "strong", "em", "blockquote", "hr", "span",
}
_TAG = re.compile(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9]*)")


def tags(out: str) -> set[str]:
    return {m.group(1).lower() for m in _TAG.finditer(out)}


# ── security ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hostile", [
    "<script>alert(1)</script>",
    '<img src=x onerror="alert(1)">',
    "<iframe src='evil'></iframe>",
    '<a href="javascript:alert(1)">click</a>',
    "<svg/onload=alert(1)>",
    "<style>body{display:none}</style>",
    '<div onclick="steal()">text</div>',
    "</p><script>alert(1)</script><p>",
    '"><script>alert(1)</script>',
    "<TEXTAREA><script>alert(1)</script>",
])
def test_no_tag_from_an_untrusted_body_ever_reaches_the_output(hostile):
    out = render_markdown(f"Some text.\n\n{hostile}\n")
    leaked = tags(out) - ALLOWED_TAGS
    assert not leaked, f"untrusted body emitted real tags: {leaked}"
    assert "&lt;" in out, "the hostile markup should survive as visible, inert text"


def test_markdown_links_never_become_anchors():
    out = render_markdown("See [the docs](https://example.com/x) for detail.")
    assert "a" not in tags(out) and "href" not in out
    assert "the docs" in out and "example.com/x" in out      # shown as inert text


def test_images_never_become_img_tags():
    out = render_markdown("![a diagram](evil.png)")
    assert "img" not in tags(out)
    assert "[image: a diagram]" in out


def test_html_in_a_table_cell_is_inert():
    md = "| a | b |\n|---|---|\n| <script>x</script> | ok |"
    out = render_markdown(md)
    assert "<script" not in out and "<td>" in out


def test_html_in_a_code_fence_is_inert():
    out = render_markdown("```html\n<script>alert(1)</script>\n```")
    assert "<script" not in out
    assert "<pre><code" in out and "&lt;script&gt;" in out


def test_attribute_injection_through_a_code_language_is_not_possible():
    """The language capture is restricted to [A-Za-z0-9_+-], so a crafted fence cannot smuggle an
    attribute into the emitted class. The text survives escaped and inert."""
    out = render_markdown('```js"onload="alert(1)\nx\n```')
    assert 'class="lang-js"onload' not in out
    assert not (tags(out) - ALLOWED_TAGS)


# ── structure ─────────────────────────────────────────────────────────────────

def test_headings_are_demoted_so_the_page_owns_h1():
    out = render_markdown("# Title\n\n## Section\n")
    assert "<h2>Title</h2>" in out and "<h3>Section</h3>" in out
    assert "<h1>" not in out


def test_paragraphs_lists_and_rules():
    out = render_markdown("One line.\n\n- a\n- b\n\n1. first\n2. second\n\n---\n")
    assert "<p>One line.</p>" in out
    assert out.count("<ul>") == 1 and out.count("<li>a</li>") == 1
    assert out.count("<ol>") == 1 and "<li>first</li>" in out
    assert "<hr>" in out


def test_table_renders_with_header_and_rows():
    md = "| Slot | What |\n|---|---|\n| where | our logs |\n| who | the lead |"
    out = render_markdown(md)
    assert "<table>" in out and "<th>Slot</th>" in out
    assert out.count("<tr>") == 3 and "<td>our logs</td>" in out


def test_blockquote_and_inline_formatting():
    out = render_markdown("> a caution\n\nUse **Grep** and *then* `Read`.")
    assert "<blockquote>" in out
    assert "<strong>Grep</strong>" in out and "<em>then</em>" in out
    assert "<code>Read</code>" in out


def test_emphasis_inside_code_is_not_applied():
    out = render_markdown("Write `a * b * c` exactly.")
    assert "<em>" not in out and "<code>a * b * c</code>" in out


def test_fill_slots_are_surfaced_not_hidden():
    out = render_markdown("| where | [[FILL: where our logs land]] |\n")
    assert 'class="fill"' in out and "[[FILL: where our logs land]]" in out


def test_a_real_skill_body_round_trips(tmp_path):
    body = (open("skills/dv-sim-log-first-error/SKILL.md", encoding="utf-8")
            .read().split("---", 2)[2])
    out = render_markdown(body)
    assert "<h2>" in out and "<table>" in out and "<pre><code>" in out
    assert not (tags(out) - ALLOWED_TAGS)
    # every heading in the source became a heading in the output
    assert out.count("<h2>") + out.count("<h3>") >= 5


# ── strip ─────────────────────────────────────────────────────────────────────

def test_strip_markdown_removes_markup_and_truncates():
    s = strip_markdown("# Title\n\nUse **Grep** for `x`. See [docs](http://e.com).", limit=30)
    assert "#" not in s and "**" not in s and "`" not in s
    assert s.endswith("…") and len(s) <= 32
