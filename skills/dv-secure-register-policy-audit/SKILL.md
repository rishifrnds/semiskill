---
name: dv-secure-register-policy-audit
description: Cross-check a register map's declared security attributes — secure and privileged access, lock bits, write-once, sticky-until-reset — against the register model and the negative tests that exercise them, and list every register whose declared policy is unrepresented, misrepresented or untested. Use when the register spec revs, before a registers-freeze review, after a protected-register bug escape, or when someone asks whether the lock bit is actually tested and nobody can answer.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Secure Register Access-Policy Audit: Spec versus Model versus Tests"
  semiskill-function: design-verification
  semiskill-role: security-verification-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-08-19
  semiskill-tags: security, registers, access-control, lock-bits, negative-testing, ral, audit
---

# Secure Register Access-Policy Audit

A register's security attributes are declared in one place, represented — or quietly dropped — in a
second, and exercised in a third, and the three drift apart independently. The declaration is usually
a sentence of prose in the register description; the register model has no native way to say "secure
only" and the generator discards what it cannot express; and the negative test that would catch the
gap is the one test nobody misses when it silently stops testing anything, because it passes either
way.

The output is **one row per register that declares a security attribute**, saying which of the three
sources agree, plus a coverage line saying how many of them you actually opened.

## When to use something else

For a register mismatch that is still a bring-up problem — addressing, adapter, predictor, reset
values — use `dv-ral-bringup` first. This skill assumes a model that already reads and writes
correctly and asks a different question: not *does this register work* but *who is allowed to work
it*. For architecturally defined control and status registers and their write-any-read-legal
behaviour, use `dv-csr-warl-access-audit`; that audit is about which **values** a field may hold,
this one about which **agents** may write it, and the two find different bugs on the same register.
For authoring the missing tests this audit names, use `dv-security-negative-tests` — this skill finds
which are missing and states what each must demonstrate, that one writes them. For proving that a
protected value cannot reach an observable output at all, that is an information-flow question and
belongs to `dv-asset-flow-property-authoring`. A single failing run belongs to
`dv-sim-log-first-error`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Policy source | [[FILL: which file our register description keeps the security attributes in, its format, and whether it is text that can be opened from disk]] | register owner |
| Attribute names | [[FILL: the exact property or column names our register description uses for secure access, privileged access, lock, write-once and sticky-until-reset]] | register owner |
| Access qualifier | [[FILL: how the security and privilege qualifier reaches this block on our bus, which member of the bus item carries it, and which polarity means non-secure]] | block DV owner |
| Lock relationships | [[FILL: where we record which lock bit protects which registers, and whether that record is a file on disk or only prose in a document]] | register owner |
| Negative test area | [[FILL: where our illegal-access, lock and write-once tests live, and how they are named or tagged so they can be found]] | block DV owner |
| Refusal markers | [[FILL: the string our environment prints when an access is correctly refused, and the string it prints when an expected refusal did not happen]] | DV lead |
| Waiver list | [[FILL: where a deliberately unimplemented or untested security attribute is recorded, and what a valid entry must contain]] | security architect |
| Sticky reset domain | [[FILL: which reset our sticky-until-reset attributes survive and which one clears them, named exactly as our description names them]] | RTL designer |

**Register model source**, **Log location**, **Area to owner map** and **Sign-off** are pack-wide
facts and live in `_shared/team-profile.md` — read them from there rather than re-asking anyone.

Two rows above are narrower than a profile row and are **not** the same fact. **Policy source** is
narrower than the profile's *Register model source*: the profile records what the model is generated
from, this asks which part of that source carries the security attributes, which in most formats is
a vendor extension or an extra column the generator may never read. **Refusal markers** is narrower
than the profile's *Fatal markers*: a correctly refused access is a **pass** for a negative test, so
it is usually printed at a lower severity than anything on the profile's fatal list. If on your flow
they do turn out to be the same string, record that they are — do not assume it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** A guessed attribute name makes
the whole audit read as complete while silently skipping every register that uses the real one.

## Retrieval budget — read this before opening anything

A generated register model runs to tens of thousands of machine-written lines and a register
description to thousands of rows. Work in this order and stop when the budget is spent:

1. **Grep and Read work on files on disk.** If the register description exists only as a spreadsheet
   page or a document pasted into the chat, there is nothing to Grep. Ask for an exported form that
   is text on disk; until then every "declared" cell is hearsay and the audit is provisional.
2. **Glob first, never Read first.** At most three **Glob** calls — the register description, the
   generated model, the negative-test area.
3. **At most six Grep calls:** one for the declared attributes (step 2), two on the model — map
   construction, then the shortlisted register names (step 3), one on the negative-test area
   (step 5), one on a saved log if one exists (step 6), and one on the waiver list if it is a file
   on disk (step 7). Steps 4 and 8 spend none.
4. **At most seven windowed Reads:** two of about 50 lines in the register description, two in the
   model, two in the tests, and one of about 80 lines in a log. Steps 4 and 8 reuse windows already
   open rather than opening more.
5. **At most twelve registers in one pass.** If more than twelve declare an attribute, take the
   twelve highest-ranked by step 2 and say so; twelve rows that were actually read beat forty rows
   that were assumed.
6. If a Grep returns more than about 150 hits the pattern is too broad — anchor it before reading
   anything.
7. Stopping rule: when the budget is spent and a register is still unsettled, stop and write that
   register's row as unaudited with the one thing you still need. Past that point the rows get
   invented, and an invented audit row is worse than a missing one because it retires the question.

## Procedure

### 1. Resolve the three sources to paths, and name the one you cannot open

**Glob** for the three artefacts: the register description named by **Policy source**, the generated
register model (the profile's *Register model source* says what it is generated from — Glob for the
emitted files), and the **Negative test area**. Three Glob calls, and no Read yet.

If the Policy source is a spreadsheet, a document or a wiki page, Read cannot open it. Say so before
going further: ask the register owner for an exported text form, or accept that the declared column
of every row came from a person, record who supplied each value, and mark the audit provisional.

Note the revision stamp of each source as it appears in the first window you open on it in steps 2
and 3. Three sources at three revisions disagree for reasons that are not bugs, and that check is
the same one `dv-ral-bringup` makes at its step 1 — if the stamps differ, stop, because that is the
finding and everything below it is noise.

### 2. List only the registers that declare a security attribute

**Grep** the Policy source once, with a single alternation over the strings in **Attribute names**.
Not the whole register list: a block has hundreds of registers and perhaps twenty carrying a declared
attribute, and those twenty are the audit. If the Attribute names slot is unfilled, stop — Grepping
for the word "secure" hits comments, signal names and the word "insecure", and still misses a house
convention that spells the attribute some other way.

Then two bounded **Read** windows of about 50 lines each, placed on the densest clusters of hits, to
capture three things per register: which register, which attribute, and the **qualifying words**
around it — "writable in the secure state only", "locked by the configuration lock", "cleared by the
power-on reset only". Copy those words verbatim. The qualification is the part that gets lost, and it
is the part that decides what refutes the claim in step 4.

Rank before shortlisting to twelve. An access restriction or lock on a register that gates debug,
selects a boot mode, or exposes stored material outranks one on a status counter. If the description
records no criticality of its own, say plainly that the ranking is yours and ask the security
architect to confirm it — never present an invented ranking as the description's own.

### 3. Ask what the model can even represent, before asking whether it is right

The register model has no native attribute meaning "secure only". What it has is per-map **rights**
on the map entry, a per-field access policy string, and named reset kinds. Spend two **Greps** and
two **Reads** here.

One **Grep** for the map construction — `create_map`, `add_submap`, `set_base_addr` — and count the
maps. A block whose description declares a secure and a non-secure view but whose model builds one
map has no modelled non-secure path at all. That is not automatically wrong: the negative tests may
drive bus items directly, which is often the only way. It does mean the model is not where the policy
lives, and step 5 must read the test rather than the model.

One **Grep** alternating the shortlisted register names, for their `add_reg` lines and their
`configure` lines, then two **Read** windows. Record, per register: which maps it appears in, the
rights on each `add_reg`, the field's policy string, and the reset kind its reset value was declared
under. Then classify the representation as one of:

- **absent from the non-secure map** — the strongest modelling available, because it removes the read
  as well as the write.
- **present with RO rights** — models write protection only. If the declaration forbids the *read*,
  this is wrong, not partial.
- **a `W1` or `WO1` policy** — models write-once. It says nothing about who may write.
- **a distinct reset kind on the field's reset value** — the only native way sticky-until-reset
  appears; the model clears that field only when the block is reset with that kind.
- **recorded, not enforced** — a user attribute or a comment carries the attribute, nothing acts on
  it. Write those three words rather than "modelled".
- **absent entirely** — the generator dropped it. Report it as a generator finding, not a modelling
  mistake.

### 4. The five families — what each claims, what refutes it, and the false pass

No retrieval; this reads the windows already open. The **false pass** column is the reason this audit
exists at all.

| Attribute | What it claims | What refutes it | The false pass |
|---|---|---|---|
| Secure access only | a non-secure access neither changes it nor reveals it | a non-secure write that lands, seen on a read back through the permitted path or a back-door peek; or a non-secure read returning the real value | a non-secure read returns zero and is scored as a refusal — an undecoded address, an unimplemented register and a disconnected agent all return zero too |
| Privileged access only | an unprivileged access is refused, independently of secure state | an unprivileged access that succeeds while secure | the test moves one qualifier and leaves the other at its default, so it proved something about one combination and nothing about the axis it named |
| Lock bit | while the lock is set the protected registers ignore writes | a write landing while the lock is set | the write used the value already there; and the test never showed the register writable with the lock clear, so a permanently stuck register passes |
| Write-once | the first write after the named reset sticks, later ones are ignored | a second write with a different value landing | the test writes once — one write cannot tell write-once from RW |
| Sticky until reset | once set it holds until the named reset | any documented clear mechanism clearing it early, or the named reset failing to clear it | the test never tries to clear it, so a bit that is stuck-at-one passes |

Two axes, four combinations. Secure and privileged are independent, so a test that names one of them
must say which value the other held, or it has audited a corner rather than an attribute.

### 5. Read the negative test, and ask whether it can fail

**Grep** the **Negative test area** once, alternating the shortlisted register names with the member
name from **Access qualifier**. Then at most two **Read** windows. For each test found, four
questions in this order:

1. **Does it drive the denied path at all?** An access issued through the model on a map whose entry
   rights forbid it is refused *by the model*: in the register-layer versions that carry the
   map-rights check, that check runs before any bus traffic and reports an error the environment may
   already be demoting. Confirm that behaviour against the register-layer source we compile against;
   where it holds, the test never reached the design, and a real negative test has to build the bus
   item itself.
2. **Is there a positive control in the same test?** The identical access through the permitted path,
   shown succeeding. Without it, a dead sequence, a wrong address or an unconnected agent scores as a
   refusal.
3. **Does it check the side effect and not only the response?** Both axes: the value did not change —
   read back through the permitted path or **peek** it — and the refusal was reported the way the
   description says, whether that is an error response or the silence of read-as-zero, write-ignored.
   Checking one axis passes a design that reports an error and performs the access anyway.
4. **Can this test still fail?** Look at what it does with expected errors. A severity demotion or a
   report catcher installed for the whole test demotes every genuine failure in it as well.

If no test is found, that is a test gap — and state the Grep pattern that failed to find one.
"No test found" from a pattern that never matched the naming convention is the most expensive wrong
answer this procedure can produce.

### 6. If a run exists, read what it printed; otherwise say there is none

The agent cannot start a simulation. **Ask the engineer to run the negative-test list and give you
the path to the saved log** — the profile's *Log location* says where ours land. With a path, one
**Grep** for both strings in **Refusal markers** and one 80-line **Read** window at the first hit.

Check two things in that window: that refusals printed for the registers you shortlisted rather than
for some easier subset, and that the number of refusals matches the number of denied accesses the
test drove. Fewer refusals than denied accesses means some accesses were never issued, which looks
identical to a clean pass.

Without a log, say the audit is source-only. That is a legitimate result — most of this is decidable
from source — but "declared, modelled and tested" is a weaker claim than "observed refusing", and the
row must not blur them.

### 7. Check the waiver list before calling anything a gap

One **Grep** of the **Waiver list** if it is a file on disk. An attribute deliberately left
unimplemented or untested, with a dated and owned entry, is a decision rather than a finding, and
re-raising it costs the security architect an afternoon. An entry naming no owner and no expiry *is*
a finding — say which of the two you found. If the waiver list is a tracker or a page rather than a
file, Grep cannot reach it: produce the audit and mark those rows pending whoever can query it.

### 8. Write one row per register, then the coverage line

```
register  : <block and register name, spelled as the register model spells it>
attribute : <one of the five families in step 4>
declared  : <the register description's own words, verbatim, with file and line>
modelled  : <maps, rights, policy string, reset kind, with file and line — or recorded-not-enforced, or absent>
tested    : <test file and line, or no-test-found plus the Grep pattern used>
can fail  : <yes, or the reason this test cannot fail>
observed  : <log path and line where the refusal printed, or source-only>
finding   : <one of the five names listed under this block>
class     : design | infrastructure | unknown
owner     : <from the profile's area-to-owner map, or blank plus the candidates>
waiver    : <waiver entry key, or none, or list-not-readable>
notes     : <what the next person would otherwise have to rediscover>
```

The five names `finding` accepts, and nothing else: **consistent** — declared, represented as far as
the model can represent it, and exercised by a test that can fail; **model-gap** — declared, with no
representation and no record; **test-gap** — declared and represented, but no test, or a test that
cannot fail; **spec-gap** — the model or the tests enforce something the description never declares;
**contradiction** — two sources that can both be read disagree. `class` is `infrastructure` when the
gap is in the model or the tests and `design` when the design does not enforce a policy both other
sources carry.

Under the rows, one coverage line: how many registers you audited out of how many declare an
attribute, which of the three sources you could actually open, and whether a log was read. A
registers-freeze sign-off resting on this audit needs that line attached — the profile's *Sign-off*
row says who signs and on what evidence, and rows without the coverage line are evidence of an
unknown fraction.

## Gotchas

- **Locking the model is not a lock bit.** The register layer's model-lock call freezes the *model's
  structure* so no further registers may be added; it has nothing to do with a hardware write-protect
  bit. A model that calls it has not modelled your lock, and grep hits on the word "lock" in the
  generated model are usually that call.
- **RO rights model write protection, not confidentiality.** A secure-only register left on the
  non-secure map with RO rights still returns its value to a non-secure read. If the declaration
  forbids the read, the register belongs off that map entirely.
- **The qualifier's polarity is inverted on several common bus encodings** — the bit is asserted for
  the *non*-secure access. So a test that "sets the secure bit" may be driving the opposite of what
  its name claims, which turns a negative test into a positive one that passes forever. Check the
  test against the **Access qualifier** slot's stated polarity, never against the test's own comment.
- **A zero read-back is not evidence of a refusal.** Only the same address returning a non-zero value
  through the permitted path, in the same test, makes a zero mean anything at all.
- **Expected-error handling is where negative tests go to die.** Prefer *counting* the expected
  refusals to suppressing them: a count that must equal the number of denied accesses driven fails
  when the accesses stop being driven, whereas a blanket demotion can never fail. Scope any catcher
  to one message id and the window around the denied access.
- **Sticky-until-reset needs the reset *kind*, not just a reset.** The model clears a field only when
  the block is reset with the kind that field's reset value was declared under. Leave every field on
  the default kind and each sticky field quietly clears on whichever reset the test happens to apply,
  so the model agrees with a design that has lost the stickiness. The **Sticky reset domain** slot is
  what tells you which kinds should exist.
- **Write-once cannot be tested with one write**, and a lock test that never clears the lock cannot
  tell "locked" from "stuck". Both need the leg that most tests omit: the second write, and the
  release.
- **The lock's protected set is usually written down nowhere.** The description says the bit locks
  "the configuration registers" and nobody records which ones. That set is what makes this audit
  finite, which is why **Lock relationships** is a slot — an auditor's guess at the set is worth
  exactly as much as no audit.
- **A missing attribute in the model is more often a generator finding than a modelling mistake.**
  Security attributes usually ride in a vendor extension the generator was never asked to read.
  Filing it against the block's DV owner sends it to someone with nothing to fix.
- **Two access views usually mean two address windows as well as two qualifiers.** Driving the secure
  address with a non-secure qualifier and driving the non-secure alias are different tests exercising
  different decode logic; a suite that has only the first leaves the second's decode wholly untested.

## Human verification — what a wrong answer looks like

Before acting on the audit, check:

- every `declared` cell quotes the register description's own words with a file and line — or names
  the person who supplied it, in which case that row says provisional
- no row calls a secure-only register modelled because it sits on the non-secure map with RO rights
- every `tested` cell states the Grep pattern that found the test, or the one that failed to
- no row is `consistent` while step 5's fourth question went unanswered — an unread test is a
  `test-gap` until someone reads it
- the coverage line carries both numbers, names which of the three sources was unreadable, and says
  whether any log was read
- nothing already covered by a dated, owned waiver has been raised again

A wrong answer typically audits the registers that were easy to find rather than the ones carrying
the attribute, scores a zero read-back as a refusal, calls a test present without asking whether it
can fail, or files a dropped attribute against the DV owner when the generator never carried it.

## Done when

For every register the description gives a security attribute, you can say whether the model
represents it, whether a test that can actually fail exercises it, and who owns the gap — with an
honest count of what you never opened.
