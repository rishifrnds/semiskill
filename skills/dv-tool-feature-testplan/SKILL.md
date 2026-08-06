---
name: dv-tool-feature-testplan
description: Turn one clause of a standard or one line of a tool feature spec into a minimal input, an expected result derived from the document rather than from the tool, and a golden comparison that survives release noise. Use when the design under test is the EDA tool itself, when a new feature or a newly ratified clause needs validation tests before release, when someone asks which test proves the product implements a clause, when a golden file was blessed from the tool's own output and nobody knows whether it is right, or when a test still passes on a build that does not implement the feature at all.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Decomposing a Tool Feature or Standard Clause into Validation Tests
  semiskill-function: design-verification
  semiskill-role: eda-product-validation-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.2.1
  semiskill-review-by: 2027-05-06
  semiskill-tags: tool-validation, conformance, standards, golden, traceability, test-authoring
---

# Decomposing a Tool Feature or Standard Clause into Validation Tests

When the design under test is the tool, what you are validating is a claim in a document — a clause
of a standard the product says it conforms to, or a sentence in a feature spec someone in R&D wrote.
The common failure is not a missing test; teams write plenty. It is a test whose expected result was
captured from the very tool it is supposed to judge, which can only ever detect *change* and never
*non-conformance*, and which goes red on the day the bug it enshrined is fixed.

The output is a **test card per normative statement** — minimal input, observable, expected result,
comparison rule and the provenance of that expected result — plus one coverage line saying how much
of the clause the cards actually cover. Not a description of the feature.

## When to use something else

If the thing under test is a *device* implementing a protocol and the suite is our shipped compliance
suite, that is `dv-compliance-test-authoring` — same shape, different subject, and its slot table is
about the VIP. Come here only when the artifact being judged is the tool that reads the design.
Before this one: `dv-spec-feature-extract` for a whole chapter with no feature table yet;
`dv-spec-interpretation-ledger` when the clause has two readings that both look legal, because a test
written on a guessed reading ships as evidence for the guess; `dv-spec-ecn-delta` when a revision or
errata has landed and the question is how much work it is; `dv-repo-orientation` when you cannot yet
name the suite root. After a drafted test runs: `dv-build-filelist-hygiene` for a build break,
`dv-sim-log-first-error` for a failing log, `dv-tool-version-migration` when a whole build's results
move. `dv-minimal-reproducer` shrinks a failure you already have; this builds a minimal input from a
document with no failure in hand, the opposite direction.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Spec source | [[FILL: which document and revision this claim lives in, where our licensed copy sits, whether it is a format the agent can open, and how much of its wording we may reproduce inside the repository]] | product owner |
| Requirement id | [[FILL: how one testable requirement is identified here — clause number, an id the document carries, or a house id — and whether that id includes the revision]] | validation lead |
| Tool under validation | [[FILL: which tool and which build this plan is written against, and how a testcase records the build it last ran on]] | release owner |
| Harness contract | [[FILL: what files one testcase directory must contain, how it declares its expected outcome, and how it pins the tool options and language mode it must be run with]] | harness owner |
| Golden convention | [[FILL: where a testcase's golden output lives, how it is named, and which stream or output file the harness compares]] | harness owner |
| Canonicalisation filter | [[FILL: the filter applied to tool output before comparison, and exactly which fields it removes]] | harness owner |
| Diagnostic identity | [[FILL: how our tool identifies one diagnostic — the id or tag form — and whether that id is contracted to stay stable across releases]] | tool R&D contact |
| Reference-result policy | [[FILL: whether we may derive an expected result from another implementation, which ones, and under what licence terms]] | validation lead |
| Known-deviation list | [[FILL: where we record a claim the product knowingly does not meet, how each entry is keyed, and whether it is a readable file]] | validation lead |

**Log location** and **Fatal markers** are pack-wide facts and live in `_shared/team-profile.md` —
read both from there. Step 7 needs the first to find the output the engineer returns and the second
to Grep it for whether the run died before it reached the observable at all.

Three rows above look like profile rows and are not. **Tool under validation is not the profile's
Simulator**: that row is the simulator our DV teams *use* to verify designs, this is the product
being qualified — sometimes the same binary at a different build, often a different tool entirely.
**Diagnostic identity is narrower than the profile's Fatal markers**: markers say a run failed, an
identity names one message so a negative test can pin it, and neither derives from the other.
**Harness contract is not the profile's Filelist convention**: the filelist decides what compiles,
the harness contract what one testcase directory must contain to run and be scored at all.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented option name or golden
path produces a test that looks finished, never runs, and is counted as coverage anyway.

## Retrieval budget — read this before opening anything

A standard runs to hundreds of pages and a validation suite to thousands of testcases; you are
answering one question about one sentence. Work in this order and stop as soon as the card can be
written:

1. **Grep and Read work on files, not on chat text.** If the clause arrived pasted into the
   conversation, or the only copy is a viewer document Read cannot open, ask for a path to a file
   holding the wording. If none exists, work from the quotation, say so, and mark every field that
   rests on it *provisional* — you have read a quotation, not the clause.
2. At most **two Glob calls**: one for where requirement text lives (step 1), one for the suite root
   (step 3). Both are spent by name; there is no third and no spare.
3. At most **seven Grep calls over our files**. Five are named: the requirement id in the readable
   spec copy (step 1); the requirement id across the suite and a distinctive feature keyword across
   the suite (step 3, two calls); the Known-deviation list (step 3); and the Canonicalisation filter
   or compare definition (step 6) — five allocations sitting in three steps, 1, 3 and 6, and none of
   them free for other work. The remaining two are anchoring retries, one for each of the two
   requirement-id Greps, spendable only under rule 5 and on nothing else. The output the engineer
   returns in step 7 costs one further Grep, and only then.
4. At most **four bounded Read windows**: about 60 lines around the clause (step 1); about 40 at the
   testcase step 3's search matched, opened before anything is called covered (step 3); about 40 at
   the Canonicalisation filter (step 6); and one spare of about 40 claimed by **exactly one** of step
   3's deviation entry or step 4's design question — whichever the card actually turns on, recorded
   in `notes`. Step 2 reuses step 1's window and spends no Read of its own; if the document's
   conventions clause has not been read, that is a question for the product owner, not a fifth
   window. After step 7's handoff, one further window of about 80 lines in the returned output.
5. Where the **Requirement id** slot's form is a bare clause number it is a substring of something
   common — it matches version strings, offsets and array bounds — so build the anchored pattern
   from the punctuation the document and the suite put around it *before* spending either
   requirement-id Grep, not after. If one goes out unanchored anyway and returns more than about 200
   hits, read nothing from it and re-issue that single Grep anchored: those retries are the two
   unnamed calls item 3 funds.
6. **Stopping rule.** If after the fourth window the claim has not reduced to a single statement with
   a decidable observable, stop. Write the card with `card result: not-yet-run` and name the one thing
   still needed. An invented expected result is worse than no test, because it is filed as evidence.
7. State what you covered: how many of the clause's normative statements got a card, whether the
   wording came from a file or a quotation, and how much of the suite you actually searched for
   duplicates. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Name the claim, its document, and whether Read can open it

Two kinds of claim arrive here and they have different sources of truth. A **standard clause** is
owned outside the company: the document is normative and our documentation is not. A **tool feature
spec** is ours: the feature spec plus the release notes are normative, and there is no external
appeal. Say which one you are in before anything else, because step 5 derives the expected result
from different places for each.

Use the **Spec source** slot for where the copy lives and what may be reproduced. If the licence
limits reproduction, cite the claim by its id and do not paste its wording into the testcase or the
card — an id plus a one-sentence paraphrase in our own words is what travels. If the document is a
format Read cannot open, say so and treat every number in it as a handoff: ask the product owner,
record who supplied it, and mark the card provisional.

If it is readable, spend the budget's first pair here: one **Glob** for where requirement text lives
under the **Spec source** slot — a licensed copy, a requirements export and a wiki dump land in
different trees and only one of them is the document — then one **Grep** for the requirement id in
whichever of those the slot names as authoritative. Then one bounded **Read** of about 60 lines so
you get the sentence *and* its neighbours: the paragraph above routinely carries the precondition the
sentence assumes. Record the **Requirement id** exactly as the document spells it, with its revision,
and the **Tool under validation** build this plan is being written against.

### 2. Split it into single normative statements, then classify each one on two axes

Count obligations, not sentences. "The tool shall accept A and shall report B when C" is two
statements, two cards and two rows. Splitting is cheap now; merged, it produces one red result later
that cannot be attributed to either half.

Then classify each statement twice, because the two questions are independent and collapsing them
loses the half that decides the test. **How binding** it is goes in `strength` — the pack-wide field
`_shared/handoff-vocabulary.md` registers, same five tokens and same meaning as in
`dv-compliance-test-authoring` and `dv-protocol-checker-rule`, so a card sorts into one column beside
their rows. **How determined the required outcome is** goes in `determinacy`, this skill's own field,
and that is what decides where step 5 may take the expected result from.

| The document's word | `strength` | What it produces here |
|---|---|---|
| shall, is required to | `shall` | one test that goes red if the tool does otherwise |
| shall not, is prohibited from | `shall-not` | a test that the tool declines to do the prohibited thing, stated over a named bound |
| should, should not | `should` | a report line; never a failing conformance test |
| may, optional, need not | `may` | a test that both behaviours are tolerated, plus a feature test if we claim to implement it |
| reserved | `reserved` | not a behaviour: what the tool owes a reserved construct comes from the conventions clause, and where that clause states an obligation the card is filed under *that* sentence's own word instead |

Record the document's own word, spelled as the shared field's token. A sentence reading **shall not**
is `strength: shall-not` — hyphenated, one token, never two words and never folded in with `shall`,
because these blocks are compared by exact token. Split it out deliberately: a prohibition is a
different test, not a weaker requirement, and it is the one that most often needs
`polarity: negative`, a pinned diagnostic identity and the bound the prohibition gotcha describes.
The two expensive errors are opposite and both common: a `strength: should` promoted into a failing
test makes the suite reject conformant behaviour, and a `strength: shall` demoted to a report is how
a real gap ships.

| What the document says about the outcome | `determinacy` | What it produces here |
|---|---|---|
| one answer, pinned by the sentence | `exact` | the expected result is that answer, taken straight from the sentence as `derived from: clause` |
| implementation-defined — the tool chooses and documents its choice | `implementation-defined` | the expected result comes from *our own documentation*; the test proves tool and document agree, and the obligation to document the choice is usually a `strength: shall` in its own right, which is a second card |
| unspecified — any member of a permitted set conforms | `unspecified` | assert membership of the set, never one exact output; the set is the document's, so the card is still `derived from: clause` |
| undefined, illegal — no requirement on the result | `undefined` | only robustness: no crash, no silent wrong answer, and whatever diagnostic we have promised. That promise is ours, so the expected result is `derived from: documented`, not `clause` |

The axes cross: "the tool shall document its treatment of X" is `strength: shall` with
`determinacy: implementation-defined`, and losing either half loses the test. Standards spell the
determinacy categories differently — record whichever word yours uses rather than translating it, and
classify from the document's own conventions clause rather than habit, since most standards define
their modal verbs and a few redefine them. If nobody has read that clause for *this* document, say so
on the card and ask the product owner: a classification resting on habit is cheaper to correct now
than a suite that rejects conformant behaviour for a year.

### 3. Search the suite before writing anything new

One **Glob** for the suite root, then two **Grep** calls: the **Requirement id**, and a distinctive
keyword from the feature. Then one **Grep** of the **Known-deviation list** if it is a readable file;
if it is a tracker, say the check is pending and ask the person who can query it.

**A Grep hit is a filename, not a test.** Before any hit retires this statement, open one — and name
which one: the requirement-id Grep's best hit, or, only where that Grep matched nothing, the keyword
Grep's. Exactly one match gets the budget's second window, about 40 lines, reserved for this and
nothing else. Read it for three things. What does it assert; where did its expected result come from;
and would it still pass on a build that dropped the behaviour?

Then: if it covers the statement, that settles it. If it does not, the statement stays uncovered and
`coverage` says how many matches went unopened. And if the window answers the first question but is
silent on the second — the common case, because provenance usually lives in a bless script or a
commit message rather than beside the assertion — the default is conservative, not generous: the
statement stays uncovered, the card gets written, and `notes` records that testcase by name and that
one window could not establish where its expected result came from. Retiring a statement on an
unopened Grep hit, or on an opened one whose golden nobody could trace, is the shortcut every other
step in this procedure exists to prevent.

Four outcomes once that window has answered. **One stops the work outright, one narrows it, and two
leave the whole statement to be written:**

- **Already covered.** The test you read reaches this statement's condition and its expected result
  came from the document. Stop, name the testcase, and write no new card.
- **Partially covered.** The test holds some of the statements this clause carries but not this one.
  This does *not* stop the work — it narrows it: carry on with the single statement that has no test,
  and say in `coverage` which statements the existing test already holds.
- **Covered by a test that would pass anyway.** The match exists but the window showed one of three
  things: its golden was blessed from the tool, it never reaches the condition, or its assertion is
  true of any build. Treat as not covered, write the card, and say in `notes` which of the three it
  was and which testcase it was — that testcase needs its own fix and this card is not it.
- **A registered deviation.** The Known-deviation Grep matched. The test is still worth writing, but
  it is registered as expected-fail against that entry rather than filed as a new defect, and the
  card quotes the entry's key. If the Grep line does not show the key, one bounded **Read** of the
  entry — one of the two permitted claims on the budget's spare window.

### 4. Design the minimal input and choose the observable

The input is the smallest thing the tool must consume for the statement to apply. Every construct in
it either exercises the statement or is required to make the input legal; anything else is a second
variable that will make the eventual failure unattributable.

Then decide **where the evidence appears**, and record it as one of the pack's phase tokens so the
card reads next to the rest: `phase: compile` for a front-end diagnostic, `phase: elab` for one
raised while the design is being built, `phase: run` for behaviour during execution, `phase: finalise`
for the tool's own end-of-run report, and `phase: post` for anything a later step produces —
a coverage merge, a report writer, a dump reader.

Prefer, wherever the statement allows it, an input that **checks itself**: it computes what the
clause requires, compares that against what the tool produced, and prints one unambiguous pass or
fail word. The golden is then a single line and immune to formatting drift, and the comparison logic
sits next to the claim it implements instead of in a filter three directories away.

Where the observable is a diagnostic, pin the **Diagnostic identity** — the id or tag, not the
wording. And write down the **mutation**: the specific wrong behaviour this test would catch, and
what it would print instead. A card whose mutation line cannot be written is a change detector
wearing a test's clothes.

Half of most clauses is what the tool must *reject*, so plan the `polarity: negative` case as
deliberately as the positive one — and every `strength: shall-not` statement is one. Its trap is that
any nonzero exit looks like success: a missing include file, an unavailable licence and the
diagnostic you meant are indistinguishable unless the card pins the identity and the source line the
diagnostic is reported against.

If the design turns on something unread — how a neighbouring testcase pins its options, what a
construct in the minimal input means here — that is the *other* claim on the budget's spare window.
Only one claim may be spent: if step 3 already read a deviation entry, this one becomes a line in
`notes` and a question for the harness owner.

### 5. Derive the expected result, and record where it came from

This is the step the whole skill exists for. Write the expected result so a person could check it by
hand, then record its provenance in `derived from`:

- `clause` — read out of the normative sentence. The only provenance that is conformance evidence.
- `documented` — from our own documentation, which is the right source for an implementation-defined
  choice and for a feature spec, and is not evidence about a standard.
- `hand-computed` — worked out by a person; name them in `notes`, because that person is the ground
  truth and nobody will remember in a year.
- `reference-tool` — another implementation's output, and only if the **Reference-result policy**
  slot permits it. Tool licences frequently restrict comparative use; ask, do not assume, and never
  treat agreement between two implementations as proof that either is conformant.
- `blessed-from-dut` — captured from the tool under validation. Legitimate as a tripwire, never as
  conformance evidence, and it must be labelled so nobody later mistakes it for one.

Step 2's second axis decides which of the five is available at all. `determinacy: exact` and
`determinacy: unspecified` may both read `derived from: clause` — the first because the sentence pins
one answer, the second because it pins the *set*, which the card asserts membership of instead of
picking a member. `determinacy: implementation-defined` may not: the source is our own documentation,
and if that documentation is silent the silence *is* the finding — raise it first, because a card
written anyway drifts to `blessed-from-dut` and is then filed as conformance evidence.
`determinacy: undefined` has nothing in the document to derive from, so its expected result is
whatever robustness we ourselves promised: `derived from: documented`.

### 6. Write the comparison so it survives the next release

Take the **Golden convention** for where the expected output lives and which stream is compared, and
the **Canonicalisation filter** for what is erased before comparing. Read the filter rather than
trusting its name: one **Grep** to locate it and one bounded **Read** of about 40 lines — the
budget's fifth Grep and its third window, both earmarked for this and nothing else. A filter named
for what it was written to strip in 2019 is not a statement about what it strips now.

Two rules decide whether this comparison is still working in a year. First, the filter must not erase
the thing under test: a test about a reported source line is worthless behind a filter that
normalises line numbers, and that is exactly the filter every team eventually writes. Second, prefer
a **named subset** — the specific lines this statement is about — over whole-output exact match,
which one new deprecation warning turns red across the entire suite, whereupon someone re-blesses
everything and quietly re-blesses the real changes too. Pair the subset with a whole-output check for
anything at or above a chosen severity, so a subset comparison cannot hide a new fatal.

What the filter removes is only what a rerun of the *same build on the same input* would change by
itself: timestamps, seeds, absolute and temporary paths, the version and copyright banner, elapsed
time and peak memory, host name and process id, and ordering produced by hashing or parallel work
rather than by the design. It stops there. In particular it does **not** remove data literals or
indices, which in tool output are usually the answer the card asserts, and it does not normalise
source line numbers. The wider list in `_shared/failure-signature-schema.md` erases those on purpose,
because a `signature` names a failure *class* so two runs can be recognised as the same failure —
which is the opposite of what a golden comparison is for. Use that schema in step 7 for `signature`;
do not import its list into `compare`.

### 7. Hand the run off, then read what comes back

The agent cannot start the tool, and must not describe output it has not read. **Ask the engineer to
run this testcase on the named build with the options the card pins, and to give you the path to the
output** under the profile's Log location. Say which options, so the run that comes back is the run
the card describes.

When the path arrives: one **Grep** for the observable and for the profile's fatal markers, then one
window of about 80 lines. Then record the result, and be slow about the third of these:

- `card result: as-expected` — the card is now backed by a run. Record the build.
- `card result: test-defect` — the first failure of a new test is usually the test. Check that the input
  is legal, that the options were the ones pinned, that the observable is actually produced at the
  phase claimed, and that the filter has not eaten the evidence, before anything else.
- `card result: disagrees` — only after the above. Normalise the failure per
  `_shared/failure-signature-schema.md` into `signature`, and hand the tool team the card plus that
  signature. Whether a genuine disagreement is a tool defect or a defensible reading of the document
  is a conversation with the tool owner and the document's maintainer, not a verdict this procedure
  gets to reach alone.
- `card result: known-deviation` — matched an entry from step 3; quote the entry's key.

If no run has come back, `card result: not-yet-run` and every field below `expected` stays
provisional.

### 8. Write the test card

One card per normative statement, in the **Harness contract**'s file layout. It reuses `strength`,
`phase`, `signature`, `coverage` and `notes` from the rest of the pack so the cards read beside a
compliance row and a repro block.

```
requirement  : <the id, exactly as the Spec source spells it, with its revision>
statement    : <the single normative statement this card covers, in one sentence>
strength     : shall | shall-not | should | may | reserved
determinacy  : exact | implementation-defined | unspecified | undefined
test id      : <the testcase name, to the Harness contract's naming rule>
input        : <the minimal input, one line per construct saying why it is there>
observable   : <the exact stream, file and text the harness looks at>
phase        : compile | elab | run | finalise | post
polarity     : positive | negative
expected     : <the expected result, written so a person could check it by hand>
derived from : clause | documented | hand-computed | reference-tool | blessed-from-dut
compare      : <the comparison rule, and the filter it runs behind>
mutation     : <the wrong tool behaviour this catches, and what it would print instead>
tool build   : <the build this was drafted against>
card result  : not-yet-run | as-expected | disagrees | test-defect | known-deviation
signature    : <phase>|<kind>|<where>|<what>, per the shared schema, only when card result is disagrees
coverage     : <n of m normative statements in this clause have a card; how much of the suite was searched>
notes        : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

Traceability has to work in both directions or it is decoration: from the id you must be able to
reach every card, and from a card you must be able to reach the sentence that justifies it. A card
covering two statements breaks the second direction and gets split.

## Gotchas

- **A golden blessed from the tool under validation agrees with today's behaviour by construction**,
  including today's bug — and it goes red the day the bug is fixed, which is when someone re-blesses
  it. It is a tripwire, not evidence. Label it `derived from: blessed-from-dut` every time.
- **An input can be reduced past the point where the clause still applies.** A tool is entitled to
  discard work whose result nothing observes; delete the print and the behaviour under test may
  simply never happen. Minimality has a floor — the observable must still depend on it.
- **A harness that searches only for a failure word scores a crashed run as a pass**, because a run
  that died in the front end prints neither word. Require a positive pass word *and* the exit status;
  absence of evidence is a failure.
- **Diagnostic wording is not a contract; the id may be.** Message text gets rewritten for clarity
  between releases. Ids are usually more stable — but "usually" is not a promise, so get the answer
  into the Diagnostic identity slot rather than assuming, and never match on wording alone.
- **Severity is frequently configurable.** A card asserting that a message arrives as an error can be
  flipped to a warning by a project-level setting, so the testcase pins the options it assumes
  instead of inheriting whatever the harness defaulted to this year.
- **Examples and notes in a standard are usually informative, not normative.** A test built from an
  example is a good test and weak evidence; trace it back to the sentence the example illustrates, or
  record it as a feature test rather than as conformance.
- **Conformance depends on which revision the tool was told to follow.** Language-mode and revision
  switches change what the right answer is, so a testcase that does not pin its mode is being
  compared against whatever the harness happened to default to. The revision belongs in
  `requirement`, the mode in the testcase.
- **Two implementations agreeing proves popularity, not conformance.** Both may inherit the same
  reading of an ambiguous sentence — which is a `dv-spec-interpretation-ledger` question, not a
  defect report.
- **Counting tests per clause overstates coverage.** Five cards all exercising the first sentence of
  a three-sentence clause is one statement covered, not five, and the `coverage` line's denominator
  is statements.
- **A prohibition needs a stated bound, because you cannot demonstrate absence over all inputs.** A
  `strength: shall-not` card that claims the tool never does X is claiming something no run can show.
  Name the inputs the card constructed and say how many: "not observed on the four inputs this card
  builds" is earned, "the tool does not do X" is not, and the difference is what an auditor reads.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every value in `expected` traces to the clause, to our own documentation, or to a named person —
  and `derived from` says which. Nothing labelled `clause` came out of a run of the tool.
- `strength` is the document's own word in the shared spelling — a sentence reading *shall not* is
  `strength: shall-not`, not `strength: shall` — and no recommendation has become a failing test.
- `determinacy` and `derived from` agree: an `implementation-defined` or `undefined` row cites our own
  documentation and never the clause, and an `unspecified` row asserts membership of a set rather
  than the one member the tool happened to produce.
- `mutation` is filled, and is a behaviour the tool could plausibly have — not the expected result
  restated with "not" in front of it.
- the observable still depends on the behaviour under test after the input was minimised.
- a `polarity: negative` card names a diagnostic identity and a source line, not just a nonzero exit.
- the Canonicalisation filter does not erase the field the card is about.
- the `coverage` denominator is the number of normative statements in the clause, not the number of
  cards written.
- nothing was retired as already covered on a Grep hit nobody opened — the statement that stopped the
  work names a testcase somebody read about 40 lines of.

A wrong answer typically restates the feature in the tool's own vocabulary and calls that a test
plan; labels a captured output as clause-derived; claims one card covers a whole clause; or produces
a negative test that would pass just as happily on a build where the feature is missing entirely.

## Done when

Someone else can take one card, build the input, ask for it to be run on the named build, get the
same card result you would — and find that card again from the requirement id a year later.
