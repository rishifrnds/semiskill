"""Offline body linter for authored skills — STDLIB ONLY, by construction.

Why this file has no imports beyond the standard library: it ships *inside* the delivered skill pack
as `tools/lint_body.py`, so an engineer can check a personalised fork inside the firewall with nothing
but `python`. `tests/authoring/test_lint_body_is_stdlib_only.py` parses this file's AST and fails if
that ever stops being true.

What it does: predicts, positionally, the deterministic findings the real pipeline would raise, so an
author gets a line number and a fix instead of a silent `published=False` three steps later. The
authoritative SCORE always comes from the real scanners (see `semiskill.authoring.lint`); the regexes
here exist to say *where* and *why*.

Scope and honesty:
  * stage 1 / stage 4 rules mirror `scanners/static_structure.py` and `scanners/secret_pii.py`. A
    drift-guard test asserts they agree on which codes fire.
  * stage 3 (held-out injection corpus) is NOT mirrored — this linter is author-facing and ships to
    engineers, and publishing the corpus to the population it is withheld from would turn a privilege
    boundary into an evasion manual. The `advisory` rules below are authored independently against the
    real authoring hazard: ordinary technical English that reads as an instruction to the agent. They
    overlap with the corpus by nature, not by copying. A clean advisory pass is not a guarantee.

    A clean lint means *probably publishable*. Only the pipeline says *published*.

    python tools/lint_body.py SKILL.md [SKILL.md ...]
"""
from __future__ import annotations

import re
import sys
from dataclasses import dataclass

ERROR, WARN, ADVISORY = "error", "warn", "advisory"

OVERSIZE = 50_000          # scanners/static_structure.py::_OVERSIZE
THIN_BODY = 400            # below this a "skill" is a note, not a procedure


@dataclass(frozen=True)
class BodyFinding:
    rule: str              # L0NN
    level: str             # error | warn | advisory
    message: str
    line: int
    col: int
    excerpt: str
    fix: str
    stage: int | None      # pipeline stage this predicts (1, 3, 4) or None
    scanner_code: str | None = None   # the finding code the real scanner would emit

    def __str__(self) -> str:
        return f"{self.line}:{self.col} {self.level.upper():8} {self.rule} {self.message}"


# (rule, level, stage, scanner_code, pattern, message, fix)
# Ordered as: stage-1 mirrors, stage-4 mirrors, stage-3 advisories, SemiSkill-specific.
_RULES: list[tuple] = [
    # ── stage 1: static structure ────────────────────────────────────────────
    ("L030", ERROR, 1, "dynamic-exec",
     re.compile(r"\beval\s*\(|\bexec\s*\(|\bos\.system\s*\(|\bsubprocess\.|__import__\s*\(|"
                r"\batob\s*\(|base64\.b64decode|String\.fromCharCode|\bFunction\s*\(", re.I),
     "reads as a dynamic-execution idiom (severity 0.85 — rejects the skill)",
     "This is case-INSENSITIVE, so 'transfer function (H(s))' matches. Never write a word from "
     "{eval, exec, function} immediately followed by '('. Write 'the transfer function H(s)'."),

    ("L031", ERROR, 1, "network-call",
     re.compile(r"https?://"),
     "contains a URL (severity 0.3 — drops the skill to 0.70, which silently never publishes)",
     "Cite the document by name and section instead of by link: 'IEEE 1800-2023 §20.10'."),

    ("L032", ERROR, 1, "network-call",
     re.compile(r"\bcurl\s|\bwget\s|\brequests\.(?:get|post)|\burllib|\bfetch\s*\(|\bsocket\.|\bnc\s+-"),
     "contains an outbound-fetch verb (severity 0.3 — never publishes)",
     "A skill must not instruct the agent to fetch anything. Describe the artifact the human "
     "should already have on disk."),

    ("L033", ERROR, 1, "obfuscated-blob",
     re.compile(r"[A-Za-z0-9+/]{200,}={0,2}"),
     "contains a 200+ character unbroken alphanumeric run, read as an encoded blob (severity 0.6)",
     "Break long hashes/IDs across lines, or replace with a short placeholder."),

    # ── stage 4: secret / PII ────────────────────────────────────────────────
    ("L045", ERROR, 4, "private-key",
     re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
     "contains a private-key header (severity 0.95 — HARD FAIL)",
     "Never include key material, even a truncated example."),

    ("L045a", ERROR, 4, "aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "contains an AWS access-key shape (severity 0.95 — HARD FAIL)",
     "Use a short placeholder like <ACCESS-KEY>."),

    ("L045b", ERROR, 4, "github-token",
     re.compile(r"\bghp_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
     "contains a GitHub token shape (severity 0.95 — HARD FAIL)", "Use <TOKEN>."),

    ("L045c", ERROR, 4, "slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
     "contains a Slack token shape (severity 0.95 — HARD FAIL)", "Use <TOKEN>."),

    ("L040", ERROR, 4, "credential-assignment",
     re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*"
                r"['\"]?[A-Za-z0-9_\-]{16,}"),
     "credential-shaped assignment (severity 0.90 — HARD FAIL, even when obviously fake)",
     "'token: REPLACE_WITH_YOUR_TOKEN' hard-fails. Use angle brackets — 'token: <your-token>' — "
     "which breaks the pattern, or drop the keyword next to the colon entirely."),

    ("L046", ERROR, 4, "jwt",
     re.compile(r"\beyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"),
     "contains a JWT shape (severity 0.7)", "Replace with <JWT>."),

    ("L043", ERROR, 4, "internal-url",
     re.compile(r"https?://[A-Za-z0-9.\-]+\.(?:internal|corp|local|intranet)\b"),
     "contains an internal hostname (severity 0.5)",
     "Internal infrastructure names belong in a [[FILL: ...]] slot the team fills in locally."),

    ("L042", ERROR, 4, "private-ip",
     re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"),
     "reads as a private IP address (severity 0.4)",
     "This catches version strings: '10.2.1.4' matches. Write 'v10.2 patch 1.4' or 'version 10.2'."),

    ("L041", ERROR, 4, "ssn",
     re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
     "reads as a US social-security number (severity 0.85)",
     "This catches part numbers and standard clauses: '802-11-2020' matches. Re-punctuate it."),

    ("L044", ERROR, 4, "credit-card",
     re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"),
     "reads as a payment-card number (severity 0.6)",
     "This catches 4-group lot/wafer IDs. Re-punctuate or shorten."),

    # ── stage 3: ADVISORY only — independently authored, corpus never mirrored ──
    # The hazard these target: a skill body is re-served to an agent as untrusted data, so prose
    # phrased as a direct instruction to the reader is indistinguishable from an injected one.
    ("L050", ADVISORY, 3, None,
     re.compile(r"(?i)\brun\s+the\s+following\s+(?:shell|command|bash|script)"),
     "instructs the reader to run a command verbatim — reads as tool-abuse",
     "The agent cannot run EDA tools anyway. Write: 'ask your mentor for the invocation and run it "
     "yourself in a scratch area', then have the agent read the output."),

    ("L051", ADVISORY, 3, None,
     re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions|"
                r"\bdisregard\s+(?:the\s+)?(?:above|previous|system)"),
     "overrides prior context — the canonical prompt-injection shape",
     "Say 'skip step 3' or 'this does not apply when …' instead."),

    ("L052", ADVISORY, 3, None,
     re.compile(r"(?i)\byou\s+are\s+now\s+(?:a|an|the)\s"),
     "assigns a role to the reader — reads as a persona override",
     "Catches ordinary prose like 'you are now the owner of this block'. "
     "Rewrite as 'as the block owner, you …'."),

    ("L053", ADVISORY, 3, None, re.compile(r"(?i)exfiltrat"),
     "uses exfiltration vocabulary", "Write 'unauthorised data egress'."),

    ("L054", ADVISORY, 3, None,
     re.compile(r"(?i)\b(?:read|access|leak)\s+.{0,60}(?:other\s+users|another\s+context|cross[- ]context)"),
     "describes cross-context access", "Rephrase without naming other users' contexts."),

    ("L056", ADVISORY, 3, None, re.compile(r"(?i)execute\s+arbitrary\s+(?:code|commands)"),
     "describes arbitrary execution", "Write 'unconstrained execution'."),

    ("L057", ADVISORY, 3, None,
     re.compile(r"(?i)\bsend\s+.{0,60}\b(?:secret|token|password|credential|api[_-]?key)\b.{0,60}\b(?:to|https?://)"),
     "describes sending a credential somewhere", "Remove; a skill never moves credentials."),

    # ── SemiSkill-specific ───────────────────────────────────────────────────
    ("L060", ERROR, None, None, re.compile(r"<<<|>>>"),
     "contains a triple angle bracket, which can terminate the untrusted-artifact fence "
     "that wraps this body when L3 serves it to an agent",
     "Never use '<<<' or '>>>' in a skill body. Personalisation slots use [[FILL: ...]]."),

    ("L062", ERROR, None, None,
     re.compile(r"\[\[FILL:[^\]]*\b(?:token|secret|password|passwd|pwd|api[_-]?key)\b", re.I),
     "a [[FILL:]] slot is named after a credential — it will hard-fail stage 4 the moment it is filled",
     "A skill must never ask for a credential. Ask for the *location* of a config instead."),

    ("L061", ERROR, None, None, re.compile(r"\[\[FILL:(?:(?!\]\]).){0,400}$", re.M | re.S),
     "unterminated [[FILL: ...]] slot", "Close it with ']]' on the same line."),
]


def _pos(text: str, idx: int) -> tuple[int, int, str]:
    line = text.count("\n", 0, idx) + 1
    bol = text.rfind("\n", 0, idx) + 1
    eol = text.find("\n", idx)
    eol = len(text) if eol == -1 else eol
    excerpt = text[bol:eol].strip()
    return line, idx - bol + 1, (excerpt[:110] + "…") if len(excerpt) > 110 else excerpt


def lint_body(text: str) -> tuple[BodyFinding, ...]:
    """Positional findings for one skill body. Pure; no I/O, no DB, no third-party imports."""
    out: list[BodyFinding] = []

    for rule, level, stage, code, rx, message, fix in _RULES:
        for m in rx.finditer(text):
            line, col, excerpt = _pos(text, m.start())
            out.append(BodyFinding(rule, level, message, line, col, excerpt, fix, stage, code))
            break                       # one finding per rule — the scanner scores per rule, not per hit

    if len(text) > OVERSIZE:
        out.append(BodyFinding(
            "L034", ERROR,
            f"body is {len(text)} chars (>{OVERSIZE}); severity 0.2 consumes the entire approval margin",
            1, 1, "", "Move depth into a references/ file.", 1, "oversized"))

    if "\x00" in text:
        idx = text.index("\x00")
        line, col, excerpt = _pos(text, idx)
        out.append(BodyFinding("L066", WARN, "contains a NUL byte (silently replaced at intake)",
                               line, col, excerpt, "Strip it.", None, None))

    if len(text.strip()) < THIN_BODY:
        out.append(BodyFinding("L065", WARN,
                               f"body is only {len(text.strip())} chars — too thin to be a procedure",
                               1, 1, "", "A skill that fits in a sentence belongs in a rule, not a skill.",
                               None, None))

    out.sort(key=lambda f: (f.line, f.col, f.rule))
    return tuple(out)


def format_findings(findings, *, path: str) -> str:
    if not findings:
        return f"{path}: clean"
    lines = [f"{path}: {len(findings)} finding(s)"]
    for f in findings:
        lines.append(f"  {path}:{f.line}:{f.col}  {f.level.upper():8} {f.rule}  {f.message}")
        if f.excerpt:
            lines.append(f"      | {f.excerpt}")
        lines.append(f"      fix: {f.fix}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:                                  # Windows consoles default to cp1252 and mangle the dashes
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                     # noqa: BLE001 — never let output encoding break the lint
        pass
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(__doc__.strip().splitlines()[-1].strip())
        return 2
    worst = 0
    for path in args:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as e:
            print(f"{path}: cannot read ({e})")
            worst = 2
            continue
        findings = lint_body(text)
        print(format_findings(findings, path=path))
        if any(f.level == ERROR for f in findings):
            worst = max(worst, 1)
    print("\nnote: body rules only — frontmatter and the injection corpus are checked by the "
          "pipeline. A clean run means probably publishable, not published.")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
