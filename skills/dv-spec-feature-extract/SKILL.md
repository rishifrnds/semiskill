---
name: dv-spec-feature-extract
description: Turn a protocol spec chapter or IP databook into a normalised feature table plus the ambiguity questions that must go to architects, every row traceable to a clause and a line. Use when a new or revised chapter lands, when you are scoping VIP work from a databook, when you need to separate mandatory requirements from optional knobs before planning, or when you are about to ask an architect something the errata already answers.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Turning a Protocol Spec Chapter into a Feature and Ambiguity Table
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-09-14
  semiskill-tags: spec, protocol, databook, requirements, feature-extraction, ambiguity, vplan, vip
---

# Turning a Protocol Spec Chapter into a Feature and Ambiguity Table

A new chapter arrives as a few hundred pages of prose whose obligations are scattered, conditional,
and occasionally at odds with each other, and the usual response is to read it end to end and write a
tidy summary. A summary is not a verification plan input: it drops the clause reference, flattens
conditional obligations into unconditional ones, and turns every optional feature into something
everybody later assumes was covered. What this produces instead is **two tables** — one row per
obligation, traceable to a clause and a line, and one row per genuine ambiguity, each stated well
enough that an architect can answer it in a single pass.

**What this does not do.** It reads text files. It cannot open the original if that original is a
PDF, a viewer page or a licensed portal, it cannot decide what the product will support, and it does
not write tests, assertions or a coverage model. It produces the input those are built from, and
every step needing a person ends in a named handoff.

## When to use something else

This is the front of a chain, and each `produces` value in step 4 names where that row goes next:
`dv-protocol-checker-rule` for a row that becomes a numbered checker rule with a negative test,
`dv-compliance-test-authoring` for one that becomes a directed test, and `dv-config-space-coverage`
then `dv-vip-coverage-model` for the knob axes from step 5.

This skill only *raises* ambiguities. Once one matters more than the table — because a shipping
checker turns on it — `dv-spec-interpretation-ledger` poses it so a workgroup can answer it, records
the answer with the authority behind it, and propagates it. And sizing a revision or an ECN is
`dv-spec-ecn-delta`, not this; re-extracting a whole chapter to discover what changed is the
expensive way round, which is why step 7 stops short of it. For a failing simulation, a regression
night, or an unfamiliar repository — `dv-sim-log-first-error`, `dv-regression-triage-routing`,
`dv-repo-orientation`. None of those is a spec question.

**Do not hand-extract a register chapter into feature rows.** A databook's register map is
machine-readable somewhere — the team profile's **Register model source** fact names what ours is
generated from, and `dv-ral-bringup` works from that generated model. Four hundred rows typed out of
a register table are four hundred chances to mistype an offset, and they go stale at the next
revision. Extract the chapter's *behavioural* clauses here; leave the register map to the generator.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Chapter and revision | [[FILL: the document name, its revision, the chapter or clause range we are ingesting, and the path to the plain-text copy on disk we are allowed to read]] | VIP lead |
| Normative vocabulary | [[FILL: the modal verbs this document declares as normative and the clause that defines them, plus the words it uses for reserved, prohibited, ignored and undefined behaviour]] | spec owner |
| Clause numbering | [[FILL: how clause headings, tables and figures are numbered and formatted in the plain-text copy, so a heading can be matched by pattern]] | whoever produced the text copy |
| Informative sections | [[FILL: which parts of this document are declared informative rather than normative — overviews, notes, examples, annexes — and the clause that says so]] | spec owner |
| Feature id convention | [[FILL: how a feature is identified in our verification plan, where that plan lives, and whether it is a file that can be read]] | verification lead |
| Supported option set | [[FILL: which optional protocol features our VIP is contracted to support, at which revision, and where that support matrix is recorded]] | product owner |
| Errata and interpretations | [[FILL: where errata, interpretation rulings and prior revisions of this document are kept, and whether they are files that can be read]] | spec owner |
| Question routing | [[FILL: who answers a protocol-interpretation question for this document, and how a question and its answer are recorded so the answer outlives the thread]] | VIP lead |

Two pack-wide facts in `_shared/team-profile.md` are read from there rather than re-asked: **Register
model source** decides the routing above, and **Sign-off** — who signs off and on what evidence — is
what the mandatory subset of this table eventually feeds. **Question routing is not the profile's
Area to owner map.** That map takes a failing area of *our* design to its owner; this takes a
question about *someone else's document* to whoever is entitled to interpret it, and at an IP company
those are routinely different people. Filling one from the other sends protocol questions to a block
owner who has no standing to answer them.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented modal-verb
convention, clause numbering or option matrix produces a table that looks authoritative and is wrong
in a way nobody catches until a customer runs the VIP against real traffic.

## Retrieval budget — read this before opening anything

An extracted chapter is commonly tens of thousands of lines, and a full databook far more. Reading it
whole is neither possible nor useful, and the deliverable is expected to be partial and to say so.

1. **Grep and Read work on files on disk.** A PDF, a document-portal page, or a chapter pasted into
   the conversation cannot be searched. Resolve it to a plain-text path first (step 1). Until one
   exists you may reason over a pasted fragment by eye, but say that is all you did.
2. **Glob first, paths only — at most 4 patterns**: the extracted chapter, our verification plan, the
   errata area, and any prior-revision text copy. Do not open anything during the survey.
3. **Never Read the chapter.** Every Read is a window of about 60 lines anchored on a line number a
   Grep returned. **At most 12 windows**, spent roughly: 1 on the document's own revision and scope
   statement (step 1), 1 on its definitions clause (step 3), up to 8 on clause clusters (steps 4 and
   5), 1 in the verification plan (step 6), 1 in the errata (step 7).
4. **At most 12 Greps**, and they are already allocated: 1 for the clause-heading pattern (step 2),
   up to 5 for the modal verbs — one each, because you need the counts separately — and 1 whose
   pattern alternates the reserved, prohibited, ignored and undefined words (step 3), up to 3 into
   the verification plan (step 6), and 2 across errata and the prior revision (step 7).
5. A modal-verb Grep returning several hundred hits is **not** a sign to narrow the pattern — that is
   simply what a normative chapter looks like. Work the clause range in order and record where you
   stopped. **A hit count that hit your runtime's display limit is not a count**: write it as "at
   least N, truncated" and never divide by it in step 8.
6. **Stopping rule.** Stop when the 12 windows are spent, or when the clause range is exhausted,
   whichever comes first. Everything unread at that moment is named in the coverage line, not
   silently omitted.
7. State what you actually covered. A table over four clauses of nine that says so is useful; the
   same table without that line reads as a complete answer and is not one.

## Procedure

### 1. Resolve the chapter to text on disk, and pin the revision

**Glob** for the plain-text copy named in the **Chapter and revision** slot. If the only copy is a
PDF, a viewer page or a portal, stop and **ask the engineer to produce a plain-text copy of the
chapter by whatever means our documentation team supports, and to give you its path** — no amount of
cleverness lets Grep search a document that is not a file of text.

Then spend one **Read** window on the document's own revision and scope statement and record the
revision string **verbatim**, from the document rather than from the filename. Filenames lie, and a
chapter taken from a draft differs from the ratified one in exactly the clauses that matter.

Two constraints apply from here on. **Licensed specification text must not be copied into our
tracker, plan or tickets** — reference clause number and title, and quote only the shortest fragment
that carries the obligation; that is a licensing constraint, not a style preference. And **check what
the extraction did to tables and figures**: an encoding or state table becomes column-shuffled runs
of digits and a figure becomes nothing at all, so count how many fall in range for step 8.

### 2. Index the clauses before reading any prose

One **Grep** for the heading pattern from the **Clause numbering** slot. That single call gives you
every clause heading in range with its line number, and that index is the map every later windowed
Read is anchored to. Record the clause range and the heading count — that count is the denominator
the coverage line divides by, and it is the only honest one available.

If the pattern returns nothing, the extraction flattened the headings; say so and stop rather than
reading forward hoping to recognise a boundary. Without an index every later step is unbounded.

### 3. Separate normative from informative, then locate the obligations

First mark the informative ranges from the **Informative sections** slot against the clause index.
Overviews, notes, examples and most annexes are declared informative by the document itself, and a
"shall" inside one is not a requirement — it is a restatement, and occasionally a wrong one.

Now one **Grep** per modal verb in the **Normative vocabulary** slot, separately, because the counts
are not interchangeable: the mandatory count sizes the checker list, and the permissive count sizes
the configuration space, which is the number that actually predicts schedule (step 5). Then one Grep
whose pattern alternates that slot's reserved, prohibited, ignored and undefined words — those hits
are where the negative tests and most of the real ambiguities live.

Spend one **Read** window on the definitions clause. The document's defined terms override ordinary
English, and reading "packet", "transaction", "valid" or "cycle" as English is the most reliable way
to produce a confidently wrong feature row.

### 4. Turn each obligation into one row, not one paragraph into one row

Work clause by clause down the index, inside the remaining Read windows. For each obligation, capture
the row below. One clause frequently carries three obligations bound on different parties; three rows,
not one summary.

```
feature id  : <our id from the Feature id convention slot, or a provisional id if the plan has none yet>
clause      : <clause number and title, and the line number in the text copy>
obligation  : mandatory | conditional | optional | recommendation | prohibition
condition   : <the predicate verbatim for a conditional row, empty otherwise>
applies to  : <which side the obligation binds, in the document's own words>
observable  : black-box | white-box | not-observable
produces    : checker | coverage | knob | stimulus | none
in plan     : new | matched | stale-ref | not-checked
question    : <the ambiguity id from step 8, or empty>
quote       : <the shortest verbatim fragment that carries the obligation>
```

`applies to` is load-bearing and is the field most often left blank. A VIP plays one side and checks
the other, so an obligation with no named party cannot become a checker — you cannot say whose
violation it would be. Use the document's own word for the party, not our word for it.

`observable` is the other one people skip. A requirement phrased over internal state is not visible
at the interface: either it maps to an observable sequence (`observable: black-box`) or it needs a
hook into the design (`observable: white-box`, and a negotiation with whoever owns that design). A row
nobody can see is `observable: not-observable`, and saying so now is far cheaper than discovering it
when the coverage model will not close.

### 5. Split the permissive space — every optional feature is a configuration axis

Take the permissive hits from step 3 and sort them into three shapes, because they cost completely
different amounts and are constantly conflated:

- **A capability the implementation may or may not have.** One knob, two settings, and the VIP must
  verify both — plus the interaction with every other knob already in the matrix.
- **A behaviour the implementation may choose per transaction.** Not a knob: both branches are legal
  in the same run, so both must be generated and both covered. Treated as a knob, the VIP generates
  one branch forever and the other is never seen until a customer produces it.
- **Permission granted to the other side.** No knob at all, and a stimulus requirement on us: the VIP
  must be able to drive that legal-but-unusual traffic, or the design is never asked the question.

Check each against the **Supported option set** slot. An option we are not contracted to support is
still a row — `produces: stimulus` at minimum, because a customer's traffic will contain it whether
or not our matrix does — but it is not a checker, and marking it one manufactures failures against
perfectly legal behaviour. If the matrix is silent on an option, that is a product question for step
8, not a decision to make quietly inside a table.

### 6. Cross-check against the verification plan we already have

Using the path in the **Feature id convention** slot, spend at most **three Greps** on the plan, and
spend them on clause references rather than on feature names: names get paraphrased, clause numbers
do not. Then one **Read** window where the hits cluster.

Three outcomes, all worth recording. A plan row already citing this clause makes the row
`in plan: matched`, and it needs no new id. A plan row whose clause reference does not exist in this
revision is `in plan: stale-ref` — **stale, not wrong.** Flag it for the plan owner and leave it
alone; deleting rows because a number moved is how coverage silently disappears. An obligation with
no plan row at all is `in plan: new`, which is the output this whole procedure exists to produce.

If the plan is not a file that can be read, every row is `in plan: not-checked` and the table says
so. Matching from memory produces duplicate features, which are more expensive than missing ones
because both get implemented.

### 7. Check errata and the prior revision before writing a single question

Two **Greps** here, and they save an architect an afternoon each. One into the **Errata and
interpretations** area for the clause number: a published erratum or interpretation ruling changes
the answer without changing a word of the chapter, and a large share of apparent ambiguities are
already settled there. One into the prior-revision text copy for the clause **title** — not its
number. Clause numbering is not stable across revisions, so a numeric diff reports churn that is
purely editorial and misses content that moved. Then one **Read** window on whichever hit matters.

This is a spot check on the clauses that raised a question, and it is **not** a revision delta.
Sizing a revision or an ECN across the plan, checkers, coverage model and test suite is
`dv-spec-ecn-delta`'s job; presenting two Greps as that analysis gives a lead a number that is wrong
by a factor, in the optimistic direction.

Anything still unresolved after both is a real question, and only now does it earn a row in the
second table.

### 8. Write the two tables, and the coverage line under them

The header block first, so the tables mean something in six months:

```
document    : <name and revision, verbatim from the document itself>
text copy   : <path read, and how the plain text was produced>
clauses     : <the clause range covered, and how many headings the step 2 index found>
normative   : <count per modal verb from step 3, and how many were turned into rows>
tables      : <how many tables and figures fall in range, and how many survived extraction legibly>
prior rev   : <the revision compared against in step 7, or that none was>
coverage    : <n of m obligations classified; which clauses were never opened; what is provisional>
```

Then the feature rows from step 4, then one of these per ambiguity:

```
question id    : Q1
clause         : <clause number and title, and the line number in the text copy>
quote          : <the shortest verbatim fragment that shows the problem>
reading a      : <one interpretation a competent engineer could hold, and what it implies>
reading b      : <the other, and any third>
differs by     : <what the VIP does differently under each reading>
blocks         : checker | coverage | knob | stimulus | nothing-yet
checked against: errata | prior-revision | neither | not-readable
asked of       : <the person named by the Question routing slot>
answer         : <verbatim once it returns, with who answered and when, or empty while open>
```

A question is only worth an architect's time if it quotes the clause, gives **two readings a
competent engineer could actually hold**, and says what changes in the VIP depending on the answer.
Without those three it reads as "I did not understand this", and it gets answered with "read the
spec". Record the answer in the row itself — an interpretation that lives only in a thread gets
re-asked at the next revision by the next engineer. A row that turns out to matter to a shipping
checker has outgrown this table: it carries the clause, quote and both readings that
`dv-spec-interpretation-ledger` opens with, so hand it over rather than elaborating it here.

## Gotchas

- **A recommendation is not testable as a failure.** A checker that errors on a "should" produces
  false failures at a customer site, and the customer's fix is to switch the whole checker off. Route
  recommendations to coverage, or to a message whose severity the user raises deliberately; never to
  a check that fires by default. This is the single most common way a VIP loses a customer's trust.
- **Reserved, ignored and undefined are three different behaviours.** Reserved usually means the
  transmitter must send a defined value and the receiver must not act on it; ignored means anything
  may be carried and the receiver must not act on it; undefined means the document declines to say,
  so two compliant implementations legitimately differ. Confuse them and you either fail legal
  traffic or leave the exact hole real interop bugs come through. If the clause does not say which of
  the three it is, that is an ambiguity, not a default.
- **A conditional obligation without its condition captured verbatim is worse than no row.** The
  whole content is the predicate, conditions nest ("shall, when A, unless B"), and two clauses
  routinely carry near-identical obligations under different conditions. Paraphrasing merges them and
  one branch disappears with nothing to show that it did.
- **Tables and state machines carry most of the normative content, and extraction destroys them.**
  Never take a field width, an encoding or a legal transition from extracted table text. Mark it
  provisional and ask a person to read that table in the original document — a transposed encoding
  column is invisible in review and produces a VIP that is wrong in exactly one mode.
- **Clause numbers are not stable across revisions.** The same number is different content one
  revision later, and the diff is not textual. Anchor every row to clause *title* plus the obligation
  quote as well as the number, or the whole table silently rots at the next release.
- **The definitions clause outranks ordinary English**, and the same word can be defined differently
  in two chapters of one document. When a row turns on what a term means, quote the definition next
  to it rather than trusting the reading you had in your head at the time.
- **An optional feature is not a smaller job — it doubles an axis.** The permissive count, not the
  mandatory count, is what predicts how long the VIP takes, because each option multiplies against
  every other option already supported. Produce that count early and give it to whoever is
  committing to a date.
- **Backwards-compatibility clauses are features nobody extracts.** "A receiver shall accept the
  legacy encoding" is mandatory and appears nowhere in the clauses describing the new encoding, so
  reading only the new material misses it entirely — and it is exactly what a customer's existing
  traffic exercises on day one.

## Human verification — what a wrong answer looks like

Before this table goes into a plan, check:

- every row names a clause **and** a line number in the text copy that was actually read
- no width, encoding or transition came from mangled table text without being marked provisional
- every conditional row carries its predicate **verbatim**, not paraphrased
- no recommendation row is in the mandatory checker list, and no unsupported option is a checker
- every row names the party the obligation binds, in the document's own words
- each ambiguity row carries two genuine readings and a stated consequence for the VIP
- `in plan` was set from a Grep of the plan itself, or is `in plan: not-checked` on every row
- the header block names the revision, and the coverage line names both the denominator and the
  clauses that were never opened
- no licensed text beyond the shortest fragment needed appears anywhere in the output

A wrong answer reads as a fluent summary of the chapter — thirty tidy rows, no line numbers, every
obligation unconditional and every party unnamed. Its second signature is a question list that is
really a list of passages the reader skimmed, which an architect answers by quoting the clause back.

## Done when

The mandatory rows, the option axes and the open questions are each traceable to a clause and a line,
and the coverage line says exactly how much of the chapter that rests on.
