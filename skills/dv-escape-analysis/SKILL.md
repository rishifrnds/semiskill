---
name: dv-escape-analysis
description: Audit a field, interop or silicon escape — reproduce it pre-silicon, answer the three questions that decide what actually failed (stimulus, checking, coverage), and produce the artifact updates that must exist before it can be closed. Use when a customer or a silicon bring-up found a bug our regression never failed on, when an interop event exposed behaviour our verification IP never generated, when someone asks why we did not catch this, or when you are about to close an escape with a design fix and no new test.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Verification Escape Analysis and Corrective Action
  semiskill-function: design-verification
  semiskill-role: verification-lead
  semiskill-level: senior-manager
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-09-24
  semiskill-tags: escape-analysis, corrective-action, silicon-escape, interop, coverage-hole, sign-off, systemic
---

# Verification Escape Analysis and Corrective Action

An escape is a defect that got past sign-off and was found by somebody else — a customer, an interop
event, a silicon bring-up. The instinct is to fix the design and close the ticket, which leaves the
hole that let it out exactly as wide as it was. What has to be produced instead is an answer to three
independent questions — was the condition ever created, would anything have complained, did the
coverage model even ask — plus **a ledger of six artifacts that must exist on disk before anyone may
call it closed**. Each audit answer carries a file and a line. Not a narrative of how the bug was fixed.

## When to use something else

- A **single failing log from our own regression** is `dv-sim-log-first-error`. It produces the
  signature step 2 here consumes, and auditing a failure our own environment caught is ceremony with
  no information in it — that is verification working.
- A **night of regression failures** to sort and route is `dv-regression-triage-routing`.
- A reproducer too slow or too large to hand over is `dv-minimal-reproducer`, once step 2 has one.
- A **register access** escape goes through `dv-ral-bringup` first to classify the symptom, then comes
  back here. A build break is `dv-build-filelist-hygiene`.

Come here only once the defect is known to have been found **outside** our own pre-silicon flow.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Escape record | [[FILL: what a field, interop or silicon escape arrives as for us — report, ticket or note — and whether that is a file that can be read from disk]] | your manager |
| Escape register | [[FILL: where our closed escapes are recorded, how each entry is keyed, and which audit answers each entry stores]] | verification lead |
| Shipped revision | [[FILL: how we name the design revision that shipped or taped out, and whether a build from it can still be produced]] | your manager |
| Stimulus surface | [[FILL: where our sequences, constraints and test configuration for this block live, and which knob decides whether a scenario can be generated at all]] | block DV owner |
| Checker inventory | [[FILL: where our assertions, scoreboard rules and reference-model checks for this block live, and how a check is switched off in our flow]] | block DV owner |
| Coverage model source | [[FILL: which files hold the covergroups and coverage properties for this block — the files that declare the questions, not the place merged results land]] | coverage owner |
| Exclusion and waiver records | [[FILL: where coverage exclusions and check waivers live, what each entry records as its justification, and whether it carries a date and an owner]] | DV lead |
| Verification plan | [[FILL: where our verification plan for this block lives, what one row is keyed on, and whether it is a file that can be read]] | verification lead |
| Regression list | [[FILL: which list a new test must appear in before it runs nightly, and where that file lives]] | DV infra owner |

Five pack-wide facts are spent here and are **not** re-asked: **Log location**, **Fatal markers** and
**Pass marker** sign the reproducer log in step 2, **Area to owner map** routes the corrective actions
in step 8, and **Sign-off** — who signs off, on what evidence — is the closure gate. Read all five
from `_shared/team-profile.md`.

Three rows above sit next to a profile fact and are **not** that fact. **Coverage model source**
declares which questions get asked; the profile's **Coverage output** is where the answers land —
step 5 needs both, and they usually have different owners. **Regression list** is the input deciding
which tests run; the profile's **Regression summary** is the output saying what they did. **Escape
register** records defects that got past sign-off; the profile's **Known-issue list** records failures
our own regression is producing right now and we have chosen to live with. A known issue never
escaped — it was known. If your team genuinely keeps one list for both, write that down rather than
filling two rows with one answer and letting a later reader assume they were checked separately.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented coverpoint name or
waiver location produces an audit answer that reads as evidence and is not one.

## Retrieval budget — read this before opening anything

Merged coverage reports run to tens of thousands of lines, a verification plan to thousands of rows,
and a coverage database is not text at all.

1. **Grep, Read and Glob work on files on disk.** An escape almost never arrives as one — it arrives
   as a call, a mail, or a line in a tracker. Ask for the report to be saved to a file and be given
   that path. Until one exists you may reason over what you were shown, but say that is what you did,
   and mark every finding resting on it provisional.
2. **Never open a coverage report, a verification plan or a log with Read first.** Grep for the exact
   name, then Read a bounded window around the hits.
3. The whole ledger is **one Glob, at most 15 Greps and five windowed Reads — twenty-one calls**:
   1 Glob and one 80-line Read for the escape record (step 1); 2 Greps and one 80-line Read on the
   reproducer log (step 2); 3 Greps and one 60-line Read on the stimulus surface (step 3); 3 Greps
   and one 60-line Read on the checkers and waivers (step 4); 3 Greps and one 60-line Read on the
   coverage model, the merged report and the exclusions (step 5); 2 Greps of the escape register
   (step 7); 2 Greps for the plan row and the regression-list entry (step 8).
4. **A coverage database is binary and a merged report is enormous.** The single Grep step 5 spends on
   it searches for the exact coverpoint name and nothing else. If that report is not text on disk the
   Grep is unavailable — ask the coverage owner for the one number and record that a person gave it.
5. If any Grep returns more than about 200 hits the pattern is too broad — anchor it, or scope it to
   one directory, before reading anything around the hits.
6. **Stopping rule.** When the budget is spent, report the questions that were settled and name the
   ones that were not, each with the single artifact you would need. **Never infer one answer from the
   other two** — they are independent, and which of them failed is the entire product of this work.
7. State what was covered: which answers came from a file, which from a person, whether a reproducer
   log exists at all. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Get the escape onto disk, and decide whether it can exist here at all

Use **Glob** against the **Escape record** slot, then one bounded **Read**. Extract only what was
*observed* — the symptom, the configuration, the device or customer setup, the first moment anything
was known to be wrong — and keep it apart from the theory the reporter attached. The theory is usually
the first thing to be wrong, and it is what sends the audit to the wrong block. If no path can be
produced, say so plainly and mark every finding below provisional.

Some escapes are not representable at RTL by construction, and forcing a reproducer for one costs
weeks: metastability and synchroniser failure, which RTL simulation samples cleanly by definition;
anything decided by process, voltage, temperature, jitter or analog behaviour; an uninitialised-state
bug hidden by X-optimism, where a conditional propagates a defined value in simulation and garbage in
silicon; a path-delay failure with correct logic behind it. Mark those `repro: not-reproducible-here`
and name the sign-off flow that owns it — gate-level simulation, static clock- and reset-domain
sign-off, test and diagnosis, or silicon validation. Question one then has a real answer that is not a
test gap: our environment **cannot create the condition**, which is a larger corrective action than a
missing test rather than a smaller one.

### 2. Reproduce it pre-silicon — against the shipped revision, not the fixed one

Everything after this rests on a failing run in our own environment. Draft the stimulus the escape
requires in our own vocabulary — sequence, configuration, ordering, error injection — then **ask the
engineer to write that directed test, run it against the Shipped revision, and give you the path of
the log it wrote**. Ask for a second run of the same test against the fixed revision. The agent cannot
start a simulation and must not describe what one would have printed.

The pair matters more than either run alone. A test written after the fix and only ever seen passing
proves nothing: **it must be shown failing on the revision that shipped.**

With the failing log on disk, spend the two log **Grep** calls exactly as `dv-sim-log-first-error`
does — one for the profile's Fatal markers with the Pass marker, one to fix the lowest fatal hit's
line number — then one 80-line **Read** window starting before it, and derive the signature from
`_shared/failure-signature-schema.md`. If the directed test passes on the shipped revision the
reproducer is wrong, not the escape: mark `repro: not-reproduced`, say which stimulus assumption you
would change first, and do not run the three questions on a hypothesis.

### 3. Question one — stimulus. Could we ever have created this condition?

Up to three **Grep** calls over the **Stimulus surface**: the field or transaction attribute the escape
turns on, the sequence or scenario name that would drive it, the constraint or knob deciding whether
it can be generated at all. Then one 60-line **Read** at the deciding hit. Cite the line.

- `never-generated` — nothing in the sequence library or the configuration can produce it.
- `constrained-out` — a constraint, a zero weight, or a disabled scenario excludes it. Quote the
  constraint and find when it was added; one written to dodge an unrelated failure two years ago is
  the most common answer here.
- `generated-rarely` — reachable, but the combination needs a cross no directed test forces and no
  seed count makes likely. Say what makes it rare, not merely that it is.
- `generated-often` — it occurs on ordinary nights. Good news, and it moves the escape onto question
  two.

### 4. Question two — checking. Would anything have complained?

Not whether a check exists somewhere: whether one would have fired **on this behaviour, in this
configuration, in the runs we shipped on**. Up to three **Grep** calls over the **Checker inventory**
and the **Exclusion and waiver records** — the property or signal name, the scoreboard rule comparing
it, that same name in the waiver records — then one 60-line **Read** at the deciding hit.

- `no-checker` — nothing anywhere describes the correct behaviour. The corrective action is a check,
  not a test.
- `checker-off` — a check exists and was disabled, waived, excluded, or compiled out of the shipped
  configuration. Quote the waiver entry with its date and owner from the slot's own fields. This is a
  governance finding, and it recurs.
- `checker-wrong` — a check exists, ran, and passed. Either it compares the wrong thing, samples at
  the wrong moment, or it was written from the same reading of the specification as the design — that
  last case is step 6.
- `checker-correct` — it would have fired had the stimulus reached it. Then question one is the whole
  story.

### 5. Question three — coverage. Did we even ask the question?

Coverage has two halves living in different files, and conflating them is how this question gets
answered wrongly. Three **Grep** calls: the coverpoint or cross name in the **Coverage model source**;
that same name in the profile's **Coverage output** merged report, exact name, one call, and only if
that report is text on disk; and the name in the **Exclusion and waiver records**. Then one 60-line
**Read** at the covergroup declaration.

- `no-coverpoint` — the model never asked. Nothing about the coverage number that was signed off is
  evidence about this escape, in either direction.
- `uncovered` — the question was asked, the answer was no, and sign-off happened anyway. Quote the
  exclusion or waiver that made that acceptable; if there is none, the finding is that an uncovered
  bin was signed off with no record.
- `covered-but-blind` — the bin reads as covered and the claim is empty. Three ways, all common: the
  covergroup samples at a moment when the condition is trivially true; the bin is wider than the
  interesting case and is filled by its boring neighbours; or the runs that filled it had their
  checking off, so it records that the stimulus happened and says nothing about whether the behaviour
  was right.
- `covered-and-true` — filled by runs whose checkers were on, and the escape still got out. The model
  asked a question that was not the one that mattered; the action is a new coverpoint, not a new bin.

### 6. The fourth question, asked only when the first three exonerate everyone

If the answers come out `generated-often`, `checker-correct` and `covered-and-true`, the audit has not
finished — it has found a **specification** escape. Design, reference model and coverage model were
all written from one reading of the document, they agree with each other, and the reading is wrong or
the document is ambiguous. No new test finds this, because every artifact that would judge the test
shares the misreading. Record `spec: ambiguous` or `spec: wrong`, cite the clause by document name and
clause number, and make the corrective action an independent reading — the specification owner, the
architect, or the third party in an interop case — rather than another sequence. For an interop escape
this is the *usual* answer: our verification IP and the other device are both models of the same
document, and the escape sits in the gap between two legal readings of it.

### 7. Has this class escaped before, and where else is the same shape?

An escape that has escaped before means the previous corrective action did not work, which is a larger
finding than today's defect. Two **Grep** calls on the **Escape register**, if it is a file on disk:
one for the audit-answer strings from steps 3 to 5, one for the area from the signature's `where`.
Compare exactly. If the register is not a file on disk this is a handoff — put the three answers in
the report and ask its owner to compare them. "This feels like the arbitration thing from last year"
is a recollection, and it is how one systemic problem gets counted as three unrelated ones.

Then say where else the same **shape** of hole is. One escape is a sample of a class: an untested
error path on one interface almost always means the same untested shape on its siblings. Name that
sweep as a separate action with its own owner.

### 8. Build the artifact ledger, then write the report

An escape is not closed by a design fix. It is closed when it can no longer escape. Every row must be
filled; one that does not apply says why in a sentence rather than being left blank.

| Artifact | What must exist | How you verify it here |
|---|---|---|
| Reproducer test | the directed test from step 2, checked in | **Grep** the **Stimulus surface** for its name; cite file and line |
| Independent check | an assertion, scoreboard rule or model rule firing on the behaviour without needing that one test | **Grep** the **Checker inventory**; cite file and line |
| Coverage question | the coverpoint or cross that asks it, plus removal of any exclusion that hid it | **Grep** the **Coverage model source** and the exclusion records |
| Nightly membership | the test named in the **Regression list**, so it runs on a schedule forever | one **Grep** of that list for the test name |
| Plan row | the **Verification plan** row linking requirement, test, check and coverpoint | one **Grep** of the plan for the requirement key |
| Register entry | an **Escape register** entry carrying the three audit answers, so the next count is possible | named as an action if the register is not readable text |

A test appearing in no regression list is a test that ran once; a check living only inside the
reproducer fires only when someone already suspects the bug. Route each row to an owner through the
profile's **Area to owner map**, keyed on the signature's `where` — never on the test name.

```
escape    : <the escape record's own key, verbatim, and where it was found>
signature : <phase>|<kind>|<where>|<what>, from the reproducer log, per the shared schema
phase     : compile | elab | run | finalise | post
class     : design | infrastructure | unknown
repro     : reproduced | not-reproduced | not-attempted | not-reproducible-here
stimulus  : never-generated | constrained-out | generated-rarely | generated-often
checking  : no-checker | checker-off | checker-wrong | checker-correct
covpoint  : no-coverpoint | uncovered | covered-but-blind | covered-and-true
spec      : clear | ambiguous | wrong
owner     : <one owner per ledger row, from the area map, plus whoever signs off>
run id    : <whatever identifies the reproducer run for us>
log       : <path, and the line range worth reading>
artifacts : <the six ledger rows, each present with a path and line, or missing>
coverage  : <which answers came from a file, which from a person, which not at all>
closure   : ready | not-ready
notes     : <the sibling sweep, and anything the next person would otherwise rediscover>
```

`signature`, `phase`, `class`, `run id`, `log` and `notes` are the field names
`dv-sim-log-first-error` emits, and `repro` carries the four values
`dv-customer-escalation-isolation` uses, so an escape arriving through either keeps its vocabulary.
`closure: ready` is written only when all six ledger rows are present **and** the evidence named in
the profile's **Sign-off** fact exists. Leave a field blank rather than filling it plausibly.

## Gotchas

- **A fixed design is not a closed escape.** The fix removes today's defect; the ledger removes the
  route it left by. Closing on the fix alone is invisible until the next escape of the same shape.
- **A test written after the fix and only seen passing proves nothing.** A green run on fixed RTL is
  equally consistent with a test that exercises nothing at all. Show it failing on the shipped one.
- **Full functional coverage is not a defence.** Coverage measures stimulus, not correctness: a bin
  filled by runs whose checking was waived records only that something happened. That pairing is what
  `covpoint: covered-but-blind` exists to name.
- **A covergroup sampling at the wrong moment reads as complete and asks nothing.** Check the sampling
  event before believing the number — a bin sampled at end of test usually records a steady state, not
  the transition the escape needed.
- **Three artifacts written from one wrong reading of a document all agree.** Design, reference model
  and coverage model built by one person from one paragraph are a single opinion in three files.
- **A nightly that went red and stopped being read is a process escape, not a coverage hole.** Check
  whether a failure of this shape was already appearing and was tolerated; that answer has a
  completely different corrective action, and no new coverpoint fixes it.
- **Waivers and exclusions outlive their justification.** "Excluded for this milestone" survives three
  milestones and two owners, which is why the slot asks for the date and the owner on the entry.
- **Interop escapes usually live between two legal readings, not in a defect.** Our verification IP
  encodes one reading and the other device another, so the action is a variation matrix across the
  ambiguous options rather than one more sequence against our own interpretation.
- **Counting escapes by block hides the pattern; count them by audit answer.** Three escapes all
  answering `checker-off` are one governance problem wearing three block names.

## Human verification — what a wrong answer looks like

Before an escape is signed as closed, check:

- each audit answer cites a **file path and a line**, or names the person who supplied it and is
  marked provisional — a bare answer with no citation is an opinion
- `repro: reproduced` appears only if a log at a path that was actually searched carries the
  signature; a test written but never run is `not-attempted`
- the reproducer was demonstrated **failing on the shipped revision**, and that run's log path is in
  the report — not merely passing on the fixed one
- `covpoint: covered-and-true` is claimed only where the runs that filled the bin had their checking
  on; otherwise the honest answer is `covered-but-blind`
- the ledger has all six rows, each saying present-with-a-path or missing-because; a blank row is not
  a pass, and `closure: ready` is absent whenever one is missing, whatever the fix's status
- the sibling sweep is named with its own owner, or its absence is justified in `notes`

A wrong answer is a fluent write-up that identifies the design line that was wrong, answers all three
questions as "we did everything right, it was simply a rare corner", and closes with a fix and no new
test. Its second signature is `covpoint: covered-and-true` on a bin filled by runs with the checker
waived — the same escape certified impossible on the very evidence that let it out.

## Done when

Every one of the six ledger rows exists on disk with a path, the reproducer has been seen failing on
the revision that shipped, and the three audit answers are specific enough that a repeat escape would
be recognised as a repeat.
