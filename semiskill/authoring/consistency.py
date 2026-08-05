"""Pack-level consistency checks — the failures reviewers kept finding by eye.

Four rounds of adversarial review on the first six skills produced real findings, and nearly all of
them were the same shape: something in one file disagreed with something in another file, or with
another part of itself. A slot declared and never used. A step Grepping for a slot that was never
declared. A handoff-block field widened in one skill and left stale in the sibling that claims to
match it mechanically. A field renamed with one reference missed.

Every one of those is decidable from the text, so paying a reviewer to notice it is both expensive
and unreliable — a human or an agent reading 220 lines will miss the third occurrence of a renamed
field, which is exactly what happened. These checks run in milliseconds and never miss it.

They complement the per-skill linter rather than replacing it: `lint.py` asks "is this file
publishable", these ask "does this pack agree with itself".

ADR-011 changed how the enum rules decide. The old C003 compared every skill that used a field name
against every other and then *guessed*, from the value sets alone, which one was authoritative. On
the real pack it guessed wrong for nine of the ten collisions: nine were two skills asking different
questions under one borrowed noun, where "make the enums agree" is the wrong repair and "rename all
but one" is the right one. A checker cannot tell those apart from the tokens, so it stopped trying.
`skills/_shared/handoff-vocabulary.md` — a signed file a human owns — now answers the one question
that decides everything: is this name pack-wide? The rules fall out of that answer:

  C003  a REGISTERED field emitting a value the registry does not carry (error, decidable in one file)
  C006  an UNREGISTERED name carrying a token list in two or more skills — error where the value
        sets DIFFER (one label, two value spaces, so a consumer can never match them; one of them
        renames), warn where they are IDENTICAL (nothing can mismatch, so it is a prompt to register
        the agreement or rename it, not grounds to block a wave)
  C007  a registered field narrowed to a proper subset (warn, or error where the dropped token is
        the honesty escape hatch)
  C008  an unregistered field wearing a registered field's vocabulary under a different name — the
        synonym FIELD, the one failure no name-identity rule can reach
  C009  a single value followed by commentary, which hides a narrowing from every other rule
  C010  a held bare noun taken by a skill that does not hold it — the only prospective rule, and the
        only moment the fix is one rename instead of a pack-wide reconciliation
  C011  a stale prose reference to a field that has been renamed away, here or in a sibling
  C012  registry hygiene: dead rows, promotion candidates, retired names come back

The registry loader is FAIL-CLOSED. A silently-empty registry is the worst available failure mode: it
would turn C006 into sixteen errors on correct files and C003 into zero on the one wrong file.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from functools import lru_cache
from pathlib import Path

# `| Slot name | [[FILL: ...]] | who |` — the pack's slot-table convention.
_SLOT_ROW = re.compile(r"^\|\s*([A-Z][^|]{1,60}?)\s*\|\s*\[\[FILL:", re.M)
# A fenced handoff/report block line: `field    : a | b | c`
_FIELD_LINE = re.compile(r"^([a-z][a-z0-9 _-]{1,20}?)\s*:\s*(.+)$", re.M)
_FENCE = re.compile(r"```.*?```", re.S)

# A registry table row, and the backticked tokens inside a cell. Two regexes, reusing the shapes
# above: a row is anything pipe-delimited, a token is anything backticked and lowercase.
_ROW = re.compile(r"^\|(.+)\|$")
_TOKEN = re.compile(r"`([a-z][a-z0-9 -]*)`")
_VALUE = re.compile(r"^[a-z][a-z0-9-]*$")

REGISTRY_RELPATH = Path("_shared") / "handoff-vocabulary.md"


@dataclass(frozen=True)
class ConsistencyFinding:
    rule: str
    level: str            # error | warn
    slug: str
    message: str
    fix: str

    def __str__(self) -> str:
        return f"{self.slug}: {self.rule} {self.message}"


class RegistryError(ValueError):
    """The handoff-field registry could not be read, or contradicts itself.

    Raised rather than warned about, on purpose. Every rule below is a consequence of what the
    registry says; a registry that half-loaded would answer "no, that name is not pack-wide" for
    every field in the pack, which is a confident wrong answer on 83 files at once.
    """


@dataclass(frozen=True)
class Retired:
    name: str
    slug: str
    values: frozenset[str]


@dataclass(frozen=True)
class Registry:
    """The signed pack-wide vocabulary. `registered` holds enums only; `shape` holds spelling locks."""
    path: Path | None = None
    registered: dict[str, frozenset[str]] = dc_field(default_factory=dict)
    narrowing_allowed: dict[str, bool] = dc_field(default_factory=dict)
    shape: frozenset[str] = frozenset()
    narrowings: dict[tuple[str, str], frozenset[str]] = dc_field(default_factory=dict)
    held: dict[str, str | None] = dc_field(default_factory=dict)
    retired: tuple[Retired, ...] = ()

    @property
    def loaded(self) -> bool:
        return bool(self.registered or self.held)

    def knows(self, name: str) -> bool:
        """Is this name pack-wide — an enum, or a locked spelling?"""
        return name in self.registered or name in self.shape


def _ident(name: str) -> str:
    """The identity of a field name: case- and separator-insensitive, nothing else.

    `proof status`, `proof-status` and `proof_status` are one column or the registry is a lie. The
    normalisation is separator-level ONLY, so `match` and `match key` stay two different fields —
    consumers compare the whole name and must not prefix-match (Rule 9).
    """
    return re.sub(r"\s+", " ", name.replace("_", " ").replace("-", " ")).strip().lower()


def _cells(line: str) -> list[str] | None:
    m = _ROW.match(line.strip())
    return [c.strip() for c in m.group(1).split("|")] if m else None


def load_registry(root: str | Path) -> Registry:
    """Read `_shared/handoff-vocabulary.md`. Fail-closed: anything unreadable raises."""
    r = Path(root)
    path = r / REGISTRY_RELPATH
    if not path.exists():
        raise RegistryError(
            f"no handoff-field registry at {path}. Every enum rule depends on it, and a checker "
            f"that assumed an empty vocabulary would report zero problems on a pack full of them.")

    registered: dict[str, frozenset[str]] = {}
    allowed: dict[str, bool] = {}
    shape: set[str] = set()
    narrowings: dict[tuple[str, str], frozenset[str]] = {}
    held: dict[str, str | None] = {}
    retired: list[Retired] = []
    slugs: set[str] = set()
    section = None

    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("#"):
            m = re.search(r"\bT([123])\b", line)
            section = m.group(1) if m else None
            continue
        cells = _cells(line)
        if cells is None:
            continue
        names = _TOKEN.findall(cells[0])
        if not names:
            continue                    # a header or separator row, not data
        where = f"{path}:{lineno}"
        name = _ident(names[0])

        if section == "1":
            if len(cells) < 3:
                raise RegistryError(f"{where}: registered row needs field, values, narrowing")
            values = _TOKEN.findall(cells[1])
            if not values:
                raise RegistryError(f"{where}: {name!r} registers no values")
            for v in values:
                if not _VALUE.match(v):
                    raise RegistryError(f"{where}: {v!r} is not a canonical value token")
            keyword = cells[2].lower()
            if keyword not in {"no", "declared"}:
                raise RegistryError(f"{where}: unknown narrowing keyword {cells[2]!r}")
            registered[name] = frozenset(values)
            allowed[name] = keyword == "declared"

        elif section == "2":
            if len(cells) < 3:
                raise RegistryError(f"{where}: narrowing row needs field, skill, values")
            slug = (_TOKEN.findall(cells[1]) or [""])[0]
            values = _TOKEN.findall(cells[2])
            if not slug or not values:
                raise RegistryError(f"{where}: narrowing row is missing a skill or its values")
            for v in values:
                if not _VALUE.match(v):
                    raise RegistryError(f"{where}: {v!r} is not a canonical value token")
            narrowings[(name, slug)] = frozenset(values)
            slugs.add(slug)

        elif section == "3":
            if len(cells) < 3:
                raise RegistryError(f"{where}: held/shape row needs name, kind, holder")
            kind = cells[1].lower()
            if kind not in {"shape", "held", "retired"}:
                raise RegistryError(f"{where}: unknown kind keyword {cells[1]!r}")
            holder = (_TOKEN.findall(cells[2]) or [None])[0]
            if holder:
                slugs.add(holder)
            note = cells[3] if len(cells) > 3 else ""
            if kind == "shape":
                shape.add(name)
            elif kind == "held":
                held[name] = holder
            else:
                if not holder:
                    raise RegistryError(f"{where}: a retired row must name the skill it left")
                tail = note.rsplit("was", 1)[-1] if "was" in note else ""
                retired.append(Retired(name, holder, frozenset(_TOKEN.findall(tail))))

    for (name, slug), values in narrowings.items():
        if name not in registered:
            raise RegistryError(f"{path}: narrowing for {name!r} ({slug}), which is not registered")
        if not values < registered[name]:
            raise RegistryError(
                f"{path}: {slug}'s {name!r} narrowing is not a proper subset of the canonical set "
                f"({' | '.join(sorted(registered[name]))})")
        if not allowed[name]:
            raise RegistryError(f"{path}: {name!r} is registered narrowing:no, so {slug} may not "
                                f"declare a subset of it")
    for slug in sorted(slugs):
        if not (r / slug / "SKILL.md").exists():
            raise RegistryError(f"{path}: registry names {slug}, which has no SKILL.md")

    return Registry(path=path, registered=registered, narrowing_allowed=allowed,
                    shape=frozenset(shape), narrowings=narrowings, held=held,
                    retired=tuple(retired))


def _body(text: str) -> str:
    """Everything after the frontmatter."""
    parts = text.split("---", 2)
    return parts[2] if len(parts) > 2 else text


def declared_slots(body: str) -> set[str]:
    return {m.group(1).strip() for m in _SLOT_ROW.finditer(body)}


# Words that are capitalised only because a sentence started with them. "If a slot is unfilled,
# stop and ask" is the pack's standard instruction, not a reference to a slot named "If a".
_SENTENCE_LEAD = frozenset((
    "if", "when", "where", "while", "then", "the", "a", "an", "this", "that", "these", "those",
    "each", "every", "any", "all", "either", "neither", "no", "one", "some", "and", "or", "but",
    "so", "also", "its", "our", "their", "first", "next", "last", "same", "other", "another",
    "check", "read", "answer", "use", "fill", "ask", "record", "note", "leave", "treat", "stop",
))


def _slot_label(phrase: str) -> str | None:
    """The slot name inside a `<phrase> slot` match, or None if the phrase is ordinary prose.

    Slot names are capitalised labels lifted from the table ("the Exclusions slot", "the
    **Mismatch markers** slot"). A capital that is merely sentence-initial is not a label, so the
    leading function words are stripped and what remains must still begin with a capital. Without
    this, `\\b[A-Z]… slot\\b` matched "If a slot", "Check the … slot" and "The first slot" — 105 of
    105 findings on the 83-skill pack were that shape, which is a rule with zero precision.
    """
    words = phrase.split()
    while words and words[0].lower() in _SENTENCE_LEAD:
        words.pop(0)
    if not words or not words[0][:1].isupper():
        return None
    if words[-1].lower() in _SENTENCE_LEAD:
        # "any IP-XACT the slot mentions" — "slot" is the subject of the next clause, not the noun
        # this phrase names. A label never ends in a determiner.
        return None
    return " ".join(words)


class FieldValue(str):
    """A field's raw value, carrying how the name was spelled and which fenced block it came from.

    A plain `str` subclass so that every existing caller keeps working: identity is normalised for
    comparison, but a finding must quote the spelling the author actually wrote, and must be able to
    say which block a field came from in the skills that emit three.
    """

    def __new__(cls, raw: str, spelling: str, block: int) -> FieldValue:
        self = super().__new__(cls, raw)
        self.spelling = spelling
        self.block = block
        return self


def report_fields(body: str) -> dict[str, FieldValue]:
    """Fields inside fenced blocks: {normalised field name: raw value}. Only fenced blocks count, so
    ordinary prose containing a colon is not mistaken for a handoff field."""
    out: dict[str, FieldValue] = {}
    for index, block in enumerate(_FENCE.findall(body)):
        for m in _FIELD_LINE.finditer(block):
            name = m.group(1).strip()
            if " " in name and len(name.split()) > 2:      # prose, not a field label
                continue
            out.setdefault(_ident(name), FieldValue(m.group(2).strip(), name, index))
    return out


# `phase : run — a trap is always a run-phase failure`. The pack already writes this shape; before
# it was parsed, such a line was invisible to every rule, which is how a narrowing hid in prose.
_REASON = re.compile(r"\s+[—–-]\s+")


def _enum(value: str, registered: bool = False) -> tuple[frozenset[str] | None, str | None]:
    """The alternatives in `a | b | c`, plus any inline reason after an em dash.

    A REGISTERED field may declare a single value (`phase : run`) — it has to, or a one-value
    narrowing hides from every rule. An unregistered name keeps a two-part floor, so an ordinary
    line like `kind : tool` is not promoted into an enum that could then collide with something.
    """
    if "<" in value:
        return None, None
    reason = None
    m = _REASON.search(value)
    if m:
        reason = value[m.end():].strip() or None
        value = value[:m.start()].strip()
    parts = [p.strip() for p in value.split("|")]
    if len(parts) < (1 if registered else 2):
        return None, None
    if not all(_VALUE.match(p) for p in parts):
        return None, None
    return frozenset(parts), reason


# Values that mean "I could not tell". They are shared vocabulary by nature, so counting them
# towards a synonym-field match would make C008 fire on every pair of honest enums.
_ESCAPE = frozenset((
    "unknown", "none", "n/a", "not-read", "unresolved", "not-checked", "not-checkable",
    "not-applicable", "not-measured", "undecided", "not-run", "not-yet-run",
))

# `` `dv-slug`'s `field` field `` — the pack cross-references sibling field names in a dozen skills.
_CITE = re.compile(r"`?(dv-[a-z0-9-]+)`?(?:'s|s')\s+`([a-z][a-z0-9 _-]{1,25})`\s+field")
_NEGATED = re.compile(r"\b(no|not|never|nor|neither|deliberately)\b")


@lru_cache(maxsize=None)
def _guarded_forms(name: str, vocab: frozenset[str]) -> re.Pattern[str]:
    """The shapes in which prose refers to a *field*, as opposed to using the same English word.

    Backticked, "the <name> field", and "the <name> is <one of its values>" — that last one is the
    third-occurrence class: `only when the ruling is disagrees`, which C004 cannot see because the
    value is not backticked and the field it belonged to has been renamed away. Bare unquoted
    occurrences are deliberately not matched: "checked against" is ordinary English in ten skills.
    """
    forms = [rf"`{re.escape(name)}`", rf"\bthe (?:`)?{re.escape(name)}(?:`)? field\b"]
    if vocab:
        alt = "|".join(re.escape(v) for v in sorted(vocab, key=len, reverse=True))
        forms.append(rf"\bthe (?:`)?{re.escape(name)}(?:`)? is\s+`?(?:{alt})`?\b")
    return re.compile("|".join(forms))


def _sentence(text: str, start: int, end: int) -> tuple[str, int]:
    """The clause a match sits in, and where it starts — enough context to tell a reference from a
    denial of one, and to see whether a sibling's slug came before the match or after it."""
    left = max(text.rfind(". ", 0, start), text.rfind("\n\n", 0, start), 0)
    right = text.find(". ", end)
    return text[left:right if right > 0 else min(len(text), end + 120)], left


def check_pack(root: str | Path, registry: Registry | None = None) -> list[ConsistencyFinding]:
    """Cross-file and intra-file consistency over a tree of skill directories."""
    r = Path(root)
    bodies: dict[str, str] = {}
    for skill_md in sorted(r.rglob("SKILL.md")):
        bodies[skill_md.parent.name] = _body(skill_md.read_text(encoding="utf-8"))

    if registry is None:
        registry = load_registry(r) if (r / REGISTRY_RELPATH).exists() else Registry()

    findings: list[ConsistencyFinding] = []

    # Parse every skill once. `enums[slug][field] = (values, inline reason)`.
    fields: dict[str, dict[str, FieldValue]] = {s: report_fields(b) for s, b in bodies.items()}
    enums: dict[str, dict[str, tuple[frozenset[str], str | None]]] = {}
    for slug, fs in fields.items():
        got: dict[str, tuple[frozenset[str], str | None]] = {}
        for name, value in fs.items():
            e, reason = _enum(value, registered=name in registry.registered)
            if e:
                got[name] = (e, reason)
        enums[slug] = got

    shared_names = {n for n in {k for g in enums.values() for k in g}
                    if sum(1 for g in enums.values() if n in g) >= 2}

    # C000 — the registry is the premise of eight rules below. If it is absent on a tree that has
    # names to adjudicate, say so rather than reporting a clean pack.
    if not registry.loaded and shared_names:
        findings.append(ConsistencyFinding(
            "C000", "warn", "pack",
            f"no handoff-field registry at {r / REGISTRY_RELPATH}, so every enum name is treated as "
            f"unregistered and the vocabulary rules are inert",
            "Restore skills/_shared/handoff-vocabulary.md. A green run against a missing registry "
            "means nothing was checked, not that nothing was wrong."))

    # C001/C002 — slots must be declared and used, in both directions.
    for slug, body in bodies.items():
        slots = declared_slots(body)
        table_end = body.find("\n## ", body.find("[[FILL:")) if "[[FILL:" in body else -1
        after = body[table_end:] if table_end > 0 else ""
        for slot in sorted(slots):
            # a slot is "used" if its name, or a distinctive word from it, appears after the table
            key = slot.lower()
            head = key.split()[0]
            if key not in after.lower() and head not in after.lower():
                findings.append(ConsistencyFinding(
                    "C001", "warn", slug,
                    f"slot {slot!r} is declared but no step ever uses it",
                    "Either consume it in the procedure or drop the row — a slot table that asks for "
                    "facts the skill never spends sends the reader to interrupt someone for nothing."))

    # C003 — a registered field must emit values the registry carries. Decidable against one file by
    # one agent working alone, which is why it may block a wave.
    for slug in sorted(bodies):
        for name, value in sorted(fields[slug].items()):
            canonical = registry.registered.get(name)
            if canonical is not None:
                e = enums[slug].get(name)
                if e is None:
                    # Free text under a registered name is out of scope by Rule 8, and by
                    # measurement: 40 occurrences on this pack, nearly all benign — `window` alone
                    # is six ordinary time windows. Free text is never token-compared and therefore
                    # cannot mismatch. The one dangerous shape, a single value wearing a sentence,
                    # is C009's, which is scoped to values that are canonical tokens.
                    continue
                outside = e[0] - canonical
                if outside:
                    findings.append(ConsistencyFinding(
                        "C003", "error", slug,
                        f"registered field {name!r} emits {', '.join(repr(v) for v in sorted(outside))}, "
                        f"which the registry does not carry ({' | '.join(sorted(canonical))})",
                        "These blocks are compared by exact token, so a value the registry does not "
                        "carry can never be matched. Use the canonical spelling — "
                        "skills/_shared/handoff-vocabulary.md lists the known synonyms — or, if the "
                        "value is genuinely new, widen the registry with the sign-off that needs."))
            elif name in registry.shape and name in enums[slug]:
                findings.append(ConsistencyFinding(
                    "C003", "error", slug,
                    f"{name!r} is a registered spelling lock with no enum, but this skill gives it a "
                    f"token list ({' | '.join(sorted(enums[slug][name][0]))})",
                    "Pick a name of your own for the classification. The locked name has to keep "
                    "meaning one thing across the pack."))

    # C006 — an unregistered name carrying a token list in two or more skills. SPLIT BY WHETHER THE
    # VALUE SETS AGREE; do not collapse it back into one error level.
    #
    # The harm the registry states is precise: "a reader who sees the same field label assumes the
    # tokens are commensurable". Where the sets DIFFER that assumption is false and the finding is an
    # error — a consumer pasting both blocks into one column gets a token one side can emit and the
    # other structurally cannot, which is the defect that shipped. All nine real collisions on this
    # pack were that shape.
    #
    # Where the sets are IDENTICAL the assumption is simply true. Nothing can mismatch, no join is
    # wrong, and no consumer is misled today — so blocking on it asserts a harm that does not exist,
    # and it blocks the commonest correct fixture there is: two skills built from one body constant,
    # identical by construction. What remains is a real but *advisory* observation, so it warns: two
    # skills agreeing on a name and its values is either pack-wide vocabulary that should be
    # REGISTERED (which arms C003 against the next skill that disagrees) or an accidental agreement
    # between two different questions that should be renamed before a third skill copies it. Both
    # repairs are worth prompting for; neither is grounds for refusing to publish.
    unregistered: dict[str, dict[str, frozenset[str]]] = defaultdict(dict)
    for slug, got in enums.items():
        for name, (values, _) in got.items():
            if not registry.knows(name):
                unregistered[name][slug] = values
    for name, by_slug in sorted(unregistered.items()):
        if len(by_slug) < 2:
            continue
        distinct = set(by_slug.values())
        if len(distinct) > 1:
            detail = "; ".join(f"{s}: {' | '.join(sorted(v))}" for s, v in sorted(by_slug.items()))
            findings.append(ConsistencyFinding(
                "C006", "error", ", ".join(sorted(by_slug)),
                f"unregistered field {name!r} carries a DIFFERENT token list in {len(by_slug)} "
                f"skills — {detail}",
                "These blocks are compared by exact token, so one label promising two value spaces "
                "is a value a consumer can never match. Either rename all but one — qualify the "
                "name with the axis it classifies — or, if the field passes the one-column test, "
                "register it in skills/_shared/handoff-vocabulary.md with one canonical set."))
        else:
            findings.append(ConsistencyFinding(
                "C006", "warn", ", ".join(sorted(by_slug)),
                f"unregistered field {name!r} carries the SAME token list in {len(by_slug)} skills "
                f"({' | '.join(sorted(next(iter(distinct))))})",
                "Nothing mismatches today, so this does not block a wave — but the agreement is "
                "unwritten and nothing holds it in place. Decide which it is: pack-wide vocabulary, "
                "in which case register it in skills/_shared/handoff-vocabulary.md so the next skill "
                "that disagrees is caught; or two different questions that happen to share a "
                "vocabulary, in which case rename all but one before a third skill copies it."))

    # C007 — a proper subset of a canonical enum. Safe for joins, unsafe for denominators, so it has
    # to be declared: a registry row, or an inline reason on the value line. Where the registry says
    # narrowing is not allowed the dropped token is the honesty escape hatch, and that is an error.
    for slug in sorted(bodies):
        for name, (values, reason) in sorted(enums[slug].items()):
            canonical = registry.registered.get(name)
            if not canonical or not values < canonical:
                continue
            if registry.narrowings.get((name, slug)) == values or reason:
                continue
            allowed = registry.narrowing_allowed.get(name, False)
            dropped = " | ".join(sorted(canonical - values))
            findings.append(ConsistencyFinding(
                "C007", "warn" if allowed else "error", slug,
                f"registered field {name!r} drops {dropped} without saying why",
                "Declare it: add a narrowing row to skills/_shared/handoff-vocabulary.md, or write "
                "the reason on the value line (`phase : run — a trap is always a run-phase "
                "failure`). A consumer counting rows needs to know this skill structurally cannot "
                "produce those values."
                if allowed else
                "This field is registered narrowing:no because the missing token is the honesty "
                "escape hatch — without it the next reader has to guess. Emit the full set."))

    # C008 — the synonym FIELD: the same question about the same object under a different name. No
    # name-identity rule can see it, which is why this one looks at the values instead.
    for slug in sorted(bodies):
        for name, (values, _) in sorted(enums[slug].items()):
            if registry.knows(name):
                continue
            for registered_name, canonical in sorted(registry.registered.items()):
                shared = (values & canonical) - _ESCAPE
                if len(shared) >= 2:
                    findings.append(ConsistencyFinding(
                        "C008", "warn", slug,
                        f"field {name!r} shares {len(shared)} values with the registered field "
                        f"{registered_name!r} ({' | '.join(sorted(shared))}) under a different name",
                        "Either this is the registered field wearing a disguise — in which case use "
                        "its name and its canonical set — or it is a different question and must "
                        "stop reusing its tokens. A reader who sees the same values assumes the same "
                        "column."))

    # C009 — a single value followed by commentary. The shape hides a narrowing from every other
    # rule, because a line with no pipe was never an enum to begin with.
    for slug in sorted(bodies):
        for name, value in sorted(fields[slug].items()):
            canonical = registry.registered.get(name)
            if not canonical or "<" in value:
                continue
            if all(_VALUE.match(p.strip()) for p in value.split("|")):
                continue                                  # already a clean token list
            head = value.split()[0].strip("`.,;:") if value.split() else ""
            if head in canonical:
                findings.append(ConsistencyFinding(
                    "C009", "error", slug,
                    f"registered field {name!r} is written as {head!r} followed by commentary, so no "
                    f"rule can see that it narrows the enum",
                    f"Write `{value.split(':')[0] if ':' in value else name} : {head}` on its own, "
                    "declare the narrowing in skills/_shared/handoff-vocabulary.md, and move the "
                    "sentence below the block."))

    # C010 — the only prospective rule. It fires the first time a held noun is misappropriated,
    # BEFORE a second skill exists to collide with, which is the only moment the fix is one rename
    # instead of a pack-wide reconciliation, and the only moment the author is still thinking about
    # the field. Scoped to enum-valued fields, so the same nouns used as prose produce no noise.
    for slug in sorted(bodies):
        for name, (values, _) in sorted(enums[slug].items()):
            if registry.knows(name) or name not in registry.held:
                continue
            holder = registry.held[name]
            if holder == slug:
                continue
            whose = f"held by {holder}" if holder else "held and unclaimed"
            findings.append(ConsistencyFinding(
                "C010", "warn", slug,
                f"field {name!r} is a held bare noun ({whose}), and this skill classifies something "
                f"else with it ({' | '.join(sorted(values))})",
                "Qualify the name with the axis it classifies — `match key`, `card result`, "
                "`input parity`, `req chain`. A bare generic noun reads as a universal column, and "
                "renaming it now costs one edit rather than a reconciliation across two skills."))

    # C011 — a stale reference to a field that has moved. Two triggers, both scoped tightly: the
    # third-occurrence class this module exists for is invisible to C004, because the value in the
    # sentence is not backticked and the field it belonged to no longer exists.
    for slug in sorted(bodies):
        body = bodies[slug]
        prose = _FENCE.sub(" ", body)
        own_values = {v for values, _ in enums[slug].values() for v in values}
        watched: dict[str, frozenset[str]] = {
            n: registry.registered.get(n, frozenset()) for n in
            set(registry.registered) | set(registry.shape)}
        for row in registry.retired:
            if row.slug == slug:
                watched[row.name] = row.values
        for name, vocab in sorted(watched.items()):
            if name in fields[slug] or name in own_values or name not in prose:
                continue                    # it is a field here, a value of one, or simply absent
            hit = None
            for m in _guarded_forms(name, vocab).finditer(prose):
                context, offset = _sentence(prose, m.start(), m.end())
                if _NEGATED.search(context):
                    continue                # "there is deliberately no `class` field"
                lead = context[:m.start() - offset]
                if re.search(r"\bdv-[a-z0-9-]+", lead):
                    # A sentence that OPENS with a sibling's slug is about the sibling, not about
                    # this skill's block: "`dv-sim-log-first-error` produces a repro block whose
                    # `log` and `run id` fields are…". Measured on the pack, the position of the
                    # slug separates all three occurrences correctly — the two real findings both
                    # name the sibling after the fields ("the block reuses `signature` … from
                    # `dv-sim-log-first-error`"). It is a heuristic, and its failure mode is a
                    # missed finding rather than a false one.
                    continue
                hit = m
                break
            if hit:
                findings.append(ConsistencyFinding(
                    "C011", "warn", slug,
                    f"prose names the {name!r} field, but no fenced block in this skill has one",
                    "A renamed field leaves references behind that no value-level rule can see, "
                    "because the value in the sentence is not backticked and the field it belonged "
                    "to is gone. Update the sentence or restore the field."))
        for m in _CITE.finditer(body):
            other, cited = m.group(1), _ident(m.group(2))
            if other in fields and cited not in fields[other]:
                findings.append(ConsistencyFinding(
                    "C011", "warn", slug,
                    f"this skill cites {other}'s {cited!r} field, and {other} has no such field",
                    f"Read {other}'s handoff block and name a field it actually carries, or drop the "
                    f"cross-reference. A routing instruction that names a field nobody emits sends "
                    f"the reader to look for something that is not there."))

    # C012 — registry hygiene, maintainer-facing. Vocabulary that is dead, premature, or overdue.
    for name, canonical in sorted(registry.registered.items()):
        if not canonical:
            continue
        users = sorted(s for s in enums if name in enums[s])
        if len(users) < 2:
            findings.append(ConsistencyFinding(
                "C012", "warn", "registry",
                f"registered enum {name!r} is used as a token list by {len(users)} skill(s)",
                "Registration commits every skill in the pack. A registered name only one skill "
                "uses is either premature or left over from a rename; hold it in the shape/held "
                "table instead."))
    for (name, slug), values in sorted(registry.narrowings.items()):
        if slug not in fields or name not in fields[slug]:
            findings.append(ConsistencyFinding(
                "C012", "warn", "registry",
                f"narrowing row for {name!r} in {slug} names a field that skill no longer emits",
                "Drop the row. A registry that describes fields nobody writes stops being the file "
                "an author can trust after one bounded read."))
    for name, holder in sorted(registry.held.items()):
        if holder and (holder not in fields or name not in fields[holder]):
            findings.append(ConsistencyFinding(
                "C012", "warn", "registry",
                f"held noun {name!r} is declared as held by {holder}, which does not use it",
                "Either the holder renamed it and the row is stale, or the noun should be held with "
                "no holder until someone claims it."))
    promotions: dict[str, dict[frozenset[str], list[str]]] = defaultdict(lambda: defaultdict(list))
    for slug, got in sorted(enums.items()):
        for name, (values, _) in got.items():
            if not registry.knows(name):
                promotions[name][values].append(slug)
    for name, variants in sorted(promotions.items()):
        for values, users in sorted(variants.items(), key=lambda kv: sorted(kv[1])):
            if len(users) >= 3:
                findings.append(ConsistencyFinding(
                    "C012", "warn", ", ".join(sorted(users)),
                    f"unregistered field {name!r} carries the same enum in {len(users)} skills "
                    f"({' | '.join(sorted(values))})",
                    "Two skills agreeing is a coincidence you can leave alone; three is a convention "
                    "that will keep being copied. Write it down in "
                    "skills/_shared/handoff-vocabulary.md before it drifts."))
    # Retirement is per skill, not pack-wide: `mechanism` left dv-signal-trace-localisation and is
    # still the right name in dv-ams-view-binding-audit, which holds it. Firing on the holder too
    # would make the rule tell the pack to un-name eleven fields it just named.
    for row in registry.retired:
        if row.slug in fields and row.name in fields[row.slug] and not registry.knows(row.name):
            findings.append(ConsistencyFinding(
                    "C012", "warn", row.slug,
                    f"{row.name!r} is retired from this skill but is still a field of it",
                    "Finish the rename, or take the name off the retired list. A name that is both "
                    "retired and live tells the next author two different things."))

    # C005 — an enum value no step ever assigns is dead: the reader can never legitimately produce
    # it, so it is either a missing branch in the procedure or a value that should not exist.
    #
    # SCOPED TO UNREGISTERED FIELDS ON PURPOSE (ADR-011). Do not "restore" the wider rule: on a
    # REGISTERED name the reasoning above is not merely weaker, it is inverted. A registered field's
    # value set is fixed by governance, not by what one skill's procedure happens to reach, so an
    # unreachable canonical value is not a defect this skill may repair. `class` is registered
    # `design | infrastructure | unknown` with narrowing:no, which means every skill MUST offer all
    # three; a skill whose procedure only ever assigns `design` and `unknown` would get a C005 warn
    # whose only "fix" — dropping `infrastructure` — is a wave-blocking C007 error. Measured on this
    # pack the contradiction was 62 of 205 C005 warns (42 `phase`, 20 `class`): every one of them
    # unfixable by the skill it was reported against.
    #
    # The registry-driven rules already cover the ground C005 was reaching for here. A canonical
    # value a skill structurally cannot reach is a DECLARED NARROWING where T1 says `declared`
    # (C007 warns until it is declared, in the registry or as an inline reason), and simply required
    # where T1 says `no` — because there the dropped token is the honesty escape hatch. C005 keeps
    # firing normally on unregistered, skill-owned names, which is exactly where its rationale holds:
    # nobody but the author fixed that value set, so an unreachable value is the author's bug.
    for slug, body in bodies.items():
        outside = _FENCE.sub(" ", body).lower()      # the procedure, minus the blocks themselves
        for name, value in fields[slug].items():
            if registry.knows(name):
                continue
            e, _ = _enum(value)
            if not e:
                continue
            for val in sorted(e):
                if len(val) < 3 or val in {"unknown", "none", "n/a"}:
                    continue                          # explicit escape hatches need no branch
                if val.lower() not in outside:
                    findings.append(ConsistencyFinding(
                        "C005", "warn", slug,
                        f"handoff field {name!r} offers the value {val!r}, but no step in the "
                        f"procedure ever tells the reader to assign it",
                        "Either add the branch that produces it, or drop the value. A value the "
                        "procedure cannot reach is one two engineers will fill in differently."))

    # C002 — a step that names a slot the table never declares sends the reader looking for a fact
    # nobody asked them to collect.
    for slug, body in bodies.items():
        slots = {s.lower() for s in declared_slots(body)}
        if not slots:
            continue
        for m in re.finditer(r"\b([A-Z][A-Za-z-]+(?: [a-z-]+){0,3}) slot\b", body):
            label = _slot_label(m.group(1))
            if label is None:                    # ordinary prose ("If a slot is unfilled…")
                continue
            named = label.lower()
            if named not in slots and not any(named in s or s in named for s in slots):
                findings.append(ConsistencyFinding(
                    "C002", "warn", slug,
                    f"a step refers to the {label!r} slot, which the table does not declare",
                    "Declare it in the slot table or rename the reference to the slot that exists."))

    # C004 — a value named in prose for a known field must be one of that field's legal values.
    for slug, body in bodies.items():
        for name, value in fields[slug].items():
            e, _ = _enum(value, registered=name in registry.registered)
            if not e:
                continue
            for m in re.finditer(rf"`{re.escape(value.spelling)}:\s*([a-z][a-z0-9-]*)`", body):
                if m.group(1) not in e:
                    findings.append(ConsistencyFinding(
                        "C004", "error", slug,
                        f"prose refers to `{value.spelling}: {m.group(1)}` but that is not one of "
                        f"{value.spelling}'s legal values ({' | '.join(sorted(e))})",
                        "A renamed or re-split field leaves stale references behind; this is the "
                        "third-occurrence class that eyeball review reliably misses."))

    return findings


def render(findings: list[ConsistencyFinding], registry: Registry | None = None) -> str:
    # One header line, always. Without it a green run is indistinguishable from a run against a
    # registry that parsed to nothing: eight of the twelve rules are consequences of the registry, so
    # an empty vocabulary makes every one of them pass and prints the same "pack is self-consistent"
    # a genuinely clean pack does. Naming the file and the count separates "checked and clean" from
    # "not checked". When no registry is supplied the header says that rather than guessing — this
    # function is given findings, not a tree, and must not claim a provenance it cannot see.
    if registry is None:
        header = "registry: not supplied — this output cannot name the vocabulary that was checked\n"
    else:
        header = (f"registry: {registry.path or 'none'} — {len(registry.registered)} field(s) "
                  f"registered, {len(registry.held)} noun(s) held\n")
    if not findings:
        return header + "pack is self-consistent"
    lines = [f"{len(findings)} pack-consistency finding(s)", ""]
    for f in findings:
        lines.append(f"  {f.level.upper():5} {f.rule}  {f.slug}")
        lines.append(f"        {f.message}")
        lines.append(f"        fix: {f.fix}")
    return header + "\n".join(lines)
