---
name: dv-spec-interpretation-ledger
description: Take one genuine protocol ambiguity, write it as a question a standards workgroup can answer without asking us anything back, record the answer with the authority behind it, and propagate that answer into every artifact it touches. Use when two readings of a clause both look legal, when our VIP and a customer's design disagree about what the protocol requires, when a reviewer asks why a checker fires on something the spec appears to permit, when someone says we already decided this but nobody can find where it was written down, or when you are about to bake an interpretation into a checker that ships to customers.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Spec-Ambiguity Ledger: Raise, Resolve, Propagate"
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: principal
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-07-09
  semiskill-tags: spec, ambiguity, protocol, vip, interop, errata, ledger, sign-off
---

# Spec-Ambiguity Ledger: Raise, Resolve, Propagate

A clause two competent engineers read differently is not a bug waiting to be found — it is a decision
waiting to be made, and in Verification IP that decision ships to everyone who buys the VIP. The
expensive failure is never the ambiguity; it is an interpretation settled in one engineer's head,
baked into one checker, and found eighteen months later by a customer whose design is legal under the
other reading.

The output is three things: **a question a workgroup can answer without asking us anything back, an
answer recorded with the authority behind it, and a propagation list naming every artifact the answer
had to land in.** Not an opinion about which reading is nicer.

## When to use something else

This skill handles **one** question, end to end. The pack splits that work deliberately:

- **Producing the question list from a whole chapter** is `dv-spec-feature-extract`. It emits the
  `reading a` / `reading b` pair this skill consumes, and it already records whether errata and the
  prior revision were checked. Arrive from there rather than repeating it.
- **A published ECN or errata that changes many clauses at once** is `dv-spec-ecn-delta` — that is a
  sizing job across the whole surface, not a single question.
- **Writing the checker rule** once an answer exists is `dv-protocol-checker-rule`; **the compliance
  test** is `dv-compliance-test-authoring`; **the coverage bins** are `dv-vip-coverage-model`; **the
  release classification and migration note** are `dv-vip-release-compat`. Step 8 routes to all four
  rather than duplicating them.
- **An interop failure with no signature yet** starts at `dv-sim-log-first-error`, then
  `dv-customer-escalation-isolation`. Come here once the failure is a statement about the protocol.
- **A register access-policy disagreement** is `dv-ral-bringup` step 5 — most are a correct model
  describing a misremembered policy, and settle without troubling a workgroup.
- **The spec is clear and our implementation does not match it.** That is a bug: file it under the
  team profile's **Bug convention**. A ledger padded with our own defects stops being read.
- **The document is our own architecture spec, not a published protocol.** The procedure works, but
  every authority above `authority: local` is unavailable — say so rather than dressing a local
  decision up as a settled one.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Ledger location | [[FILL: where our spec-interpretation ledger lives, how each entry is keyed, and whether it is a file that can be read or a page a person must search]] | VIP lead |
| Spec identity | [[FILL: which document our VIP is written against — name, revision and amendment level — and where a readable text copy of it lives, if one does]] | VIP lead |
| Errata source | [[FILL: where published errata and corrigenda for that document are recorded for us, and whether that record is a readable file]] | standards representative |
| Workgroup channel | [[FILL: how a question reaches the external standards workgroup, who submits it on our behalf, and the turnaround we should plan for]] | standards representative |
| Interpretation tag | [[FILL: the comment tag our VIP source carries wherever an interpretation was chosen, so prior decisions can be found in the code]] | VIP architect |
| Knob convention | [[FILL: how a configurable protocol behaviour is named, defaulted and documented in our VIP]] | VIP architect |
| Compliance list | [[FILL: where our protocol compliance test list lives, and how one row is keyed to a clause]] | VIP verification owner |
| Release-note convention | [[FILL: where a customer-visible behaviour change is recorded, and which release note a change landing mid-cycle goes into]] | release manager |

**Bug convention**, **Sign-off**, **Known-issue list** and **Area to owner map** are pack-wide facts
and live in `_shared/team-profile.md` — read them from there rather than asking again.

Two rows look like a sibling's slot and are not. **Workgroup channel** is the route to the *external*
standards body; `dv-spec-feature-extract`'s question routing reaches *our own* architects — different
people, different turnaround. **Interpretation tag** is a comment string in source code, found with
Grep over the VIP; it has nothing to do with the profile's **Fatal markers** or **Infra markers**, and
filling it from either sends every search in step 2 to the wrong place.

Every row is spent: Ledger location in steps 2 and 9; Spec identity in steps 1, 3 and 5; Errata source
in step 3; Workgroup channel in step 5; Interpretation tag in steps 2 and 8; Knob convention in steps
7 and 8; Compliance list in step 8; Release-note convention in step 8.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented clause number or errata
source produces a question the workgroup answers with "that clause does not say that", and the six
weeks you waited are gone.

## Retrieval budget — read this before opening anything

A protocol document runs to a thousand pages and a mature VIP to hundreds of thousands of lines.
Neither is readable end to end, and neither needs to be.

1. **Grep and Read work on files on disk.** A clause quoted in a chat message, a slide or a customer
   email cannot be searched. Get a path, or say plainly that the quotation came from a person and mark
   every finding resting on it *provisional*.
2. **One Glob** to locate four things: the ledger, the readable text copy of the spec if one exists,
   the errata record, and the root of the VIP source. Everything after this is targeted.
3. **At most seven Greps**, allocated in advance: two in step 2 (the ledger, then the Interpretation
   tag in the VIP source), two in step 3 (the readable spec text, then the errata record), and at most
   three in step 8 for propagation targets — which has more targets than Greps on purpose.
4. **At most five bounded Reads of about 60 lines**: the matching ledger entry, the clause window, the
   VIP code window around the chosen interpretation, and two spares for step 8.
5. If a Grep returns more than about 150 hits, the pattern is a substring of something common. Anchor
   it on the clause number or the exact defined term before reading anything.
6. **Stopping rule.** If the budget is spent and you still cannot write down *both* readings from text
   you actually read, stop and name the one thing still needed. A half-formed question comes back from
   a workgroup in six weeks as a request for clarification, and you have lost a release.
7. State what you covered — which clause text you read from a file, and which arrived from a person.

## Procedure

### 1. Resolve the question to text, and name what cannot be opened

Use the **Glob** from budget rule 2 against the **Spec identity** and **Ledger location** slots. Record
the document's name, revision **and amendment level** exactly as printed on it — never "the 2023
version". Two engineers reading two amendment levels is the most common cause of an "ambiguity" that
turns out to be a version difference.

If the document is a format **Read** cannot open — a PDF, a licensed portal, a printed binder — say so
now. Every clause quotation then becomes a handoff: ask the standards representative for the sentence,
record who supplied it and when, and mark the entry provisional. A clause quoted with no file and no
line is not evidence and must never be written up as though it were.

### 2. Search the ledger and the source before writing anything new

Two **Greps**. First the ledger, for the clause number and for a distinctive term from the behaviour in
question — an entry may already exist carrying an answer nobody propagated. Second the VIP source for
the **Interpretation tag**, which finds the places where someone already chose a reading and left a
note. If either hits, **Read** one 60-line window and stop: the job is now propagation (step 8), not a
new question.

If the ledger is a page a person must search rather than a file, say the check is pending their answer.
Do not call the question new on the strength of not having found it.

### 3. Rule out the four things that look like ambiguity and are not

Most raised ambiguities die here, cheaply. Cheapest disqualifier first.

1. **A normative-keyword misread.** Specs separate requirement from recommendation from permission with
   a small keyword set and declare that set in an early conventions clause. Find that clause and read
   it before arguing. If the sentence says an implementation *may* do something, there is no ambiguity
   — there is an option, and the response is a knob plus coverage of both settings, not a question.
2. **A clause elsewhere that settles it.** Chapters are written by different owners, so the constraint
   you want is often in a different chapter from the behaviour it constrains. One **Grep** of the
   readable spec text for the defined term, not for the clause number, then read one window.
3. **An erratum that already answers it.** One **Grep** of the **Errata source**. If you arrived from
   `dv-spec-feature-extract`, its `checked` field already records this and the prior-revision check —
   read it and spend the Grep elsewhere rather than doing the work twice.
4. **A revision mismatch between the two parties.** For an interop case, get the revision and amendment
   level *both* implementations were built against before comparing behaviour. Two correct
   implementations of two revisions disagree exactly like one buggy implementation does.

### 4. Confirm the two readings, and find the scenario that separates them

Each reading must be written as *what an implementation does*, not as what the sentence means:
"Reading A: the completer may reorder these two responses. Reading B: it must not." Arriving from
`dv-spec-feature-extract`, carry its `reading a`, `reading b` and `differs by` across **verbatim** —
re-wording them is how a question and its answer stop matching.

Then add the thing an internal question never needed: **one concrete transaction sequence in which the
two readings are observably different** — different bytes on the interface, a different response code,
a different ordering, at a stated moment. If you cannot write that sequence, you do not have an
ambiguity yet; you have a confusion, and sending it costs the team its standing with the workgroup.

Where the disagreement arrived as an interop failure, keep the failure signature from
`dv-sim-log-first-error` beside the readings. It is what makes this entry findable by the next person
who hits the same wall.

### 5. Write the question in workgroup-ready form

Everything the answerer needs and nothing else. Take the submission route from the **Workgroup channel**
slot; the agent cannot submit anything, so **ask the standards representative to send it** and record
the date it went.

```
document  : <name, revision and amendment level, exactly as printed on the document>
clause    : <clause number, plus the figure or table number if one is involved>
config    : <mode, width and negotiated options in force; an unpinned question returns
             "it depends on the configuration" six weeks later>
quoted    : <the sentence at issue, verbatim, or the name of whoever supplied it>
reading a : <what an implementation does under this reading, carried over verbatim>
reading b : <the other, and any third>
scenario  : <the one transaction sequence in which the readings are observably different>
at stake  : <what each reading costs an implementation that guessed wrong>
question  : <one sentence, posed so that naming a reading settles it>
meanwhile : <what we do until the answer arrives, and what we undo if it goes the other way>
```

`config` is the line people leave out, and leaving it out turns a six-week turnaround into twelve.
`meanwhile` is what makes the entry safe to act on: it states the cost of being wrong, in advance.

### 6. Rank the authority of the answer

What you may do with an answer depends entirely on where it came from. Highest first.

| `authority` | What it is | What it licenses |
|---|---|---|
| `published` | a published erratum, corrigendum or later revision | treat as spec text; cite it and close the entry |
| `ballot` | a recorded workgroup comment resolution, not yet published | implement it; expect the published wording to differ |
| `maintainer` | a written reply from the editor or chair, in a durable medium | implement it; re-check at the next revision |
| `vendor` | a statement about what another implementation does | tells you what to interoperate with, nothing about what is legal |
| `local` | our own decision, recorded and owned by us | implement it, keep the entry open, revisit every revision |
| `none` | no answer yet | the `meanwhile` line applies, and nothing else does |

A hallway conversation and a call with a customer's architect are both `authority: none` until someone
writes them down with a name and a date. The person who gave the answer will change jobs; the entry
will not.

### 7. Choose the implementation shape

| `shape` | When | What it obliges |
|---|---|---|
| `single` | the answer is decisive and one behaviour is legal | one checker, one coverage point, one compliance row |
| `knob` | both readings are legal | generation **and** acceptance of both, plus the default below |
| `provisional` | `authority: none` or `authority: local` | everything `single` obliges, and the entry stays open |

For `shape: knob` the default is the whole argument, and there is no free option. A permissive default
hides the case you just found and lets a customer ship a design that fails against a stricter partner.
A strict default breaks every existing customer's regression on the day they upgrade. Name the default
and name which of those two costs you chose; the patch-versus-major classification belongs to
`dv-vip-release-compat`, not here.

### 8. Propagate — the artifacts one answer touches

The step that gets skipped, and skipping it is why the same question is asked twice. One answer lands
in up to eight places, each with the skill that authors it:

1. the **checker or assertion** enforcing the behaviour — `dv-protocol-checker-rule`
2. the **coverage point** recording that the case occurred — `dv-vip-coverage-model`
3. the **generation side**, if a knob now has a second setting to produce
4. the **error injection** capability, if the answer made a construct illegal
5. the **Compliance list**, one row per reading now demonstrable — `dv-compliance-test-authoring`
6. the **Knob convention** artifacts: name, default, and its documentation
7. the **release note**, under the **Release-note convention** — classified by `dv-vip-release-compat`
8. the **Interpretation tag** comment at the code implementing the choice, naming the ledger entry

Spend the remaining **three Greps** and **two Reads** on at most three of these. Start with the checker,
the coverage point and the Compliance list, because those three can silently disagree with each other.
For every artifact you did not open, name it, name its owner from the profile's **Area to owner map**,
and hand it over. An unlisted artifact is an unpropagated one.

The agent drafts text and hands it on; it cannot edit the VIP, and must not report an artifact as
updated because a change for it was drafted.

### 9. Write the ledger entry

Keyed and stored per the **Ledger location** slot. Field names are shared with the rest of the pack
where they mean the same thing, so this reads alongside a triage table or a feature row.

```
ledger id  : <the key this entry gets, per our ledger convention>
raised by  : <who raised it, and whether from implementation, review, extraction or interop>
document   : <name, revision and amendment level>
clause     : <clause number, and the figure or table if one is involved>
question   : <the one sentence from step 5>
state      : <open, asked, answered or superseded>
authority  : <published, ballot, maintainer, vendor, local or none, per step 6>
answer     : <the reply verbatim, who gave it, when, and in what medium>
shape      : <single, knob or provisional, per step 7>
knob       : <name and default if the shape is a knob, otherwise empty>
propagated : <each artifact touched, with its path; each one not touched, with its owner>
signature  : <phase|kind|where|what of the failure that raised this, or empty if raised in review>
owner      : <who carries the propagation to completion>
coverage   : <which clause text was read from a file, and which was supplied by a person>
notes      : <anything the next person would otherwise rediscover>
```

Anything not fillable from text on disk gets `?`, never an invention. The `superseded` state exists for
the case a later revision overturns an earlier answer — and when that happens, the `propagated` line is
the re-open checklist, which is the entire reason it is written down.

## Gotchas

- **A workgroup answer often arrives as proposed wording, not as "reading A".** The reply is a sentence
  for the next revision, and it can settle the question in a way neither reading anticipated. Read the
  wording rather than the covering note, and re-derive both readings against it before implementing.
- **Two ambiguities that look like one get one of them answered.** A clause can be ambiguous about
  *what* is required and separately about *when* it is checked. Asked together, the reply addresses one
  and the other silently stays open. Split them into two entries.
- **A figure is usually not normative.** Many documents state that figures and timing diagrams
  illustrate the text rather than constrain it, so a question resting on a figure alone comes back as
  "the figure is illustrative". Find the sentence — and if there is no sentence, *that* is the question.
- **Annexes carry a normative or informative label, and it is load-bearing.** An informative annex is a
  worked example, not a requirement, and a checker built from one over-constrains every customer.
- **Legality is decided by the spec; likelihood only ever decides a default.** "No real device does
  that" is a fine reason for a knob's default and never a reason for a checker to reject it. A VIP that
  generates only what today's devices do is the one that lets next year's device through.
- **Resolving toward "this is legal" must add a coverage point, not merely delete a check.** Removing
  the error leaves nothing recording that the case occurred, so the only evidence the scenario is
  exercised has been quietly deleted and a passing regression now proves less than it did.
- **A knob for "both readings are legal" needs the generation half too.** Teams routinely make the VIP
  *tolerate* reading B and never make it *produce* reading B. No test then exercises the customer's
  design against it, and the interop failure arrives from the field instead of from the regression.
- **An interop disagreement is three-way, not two-way** — our reading, their reading, and the spec. Pin
  the revision and amendment level each side built against before anyone argues; a large share of these
  dissolve into a version difference and never needed a workgroup at all.
- **An entry that is answered with an empty `propagated` line is more dangerous than an open one**,
  because the team now believes the work is finished. Treat an empty propagation line as still open.
- **`authority: local` decays.** It was reasonable when nobody could answer and becomes wrong the day a
  revision publishes. Record a revisit trigger against every local decision, or the ledger turns into a
  list of things the team believes that are no longer true.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- both readings say **what an implementation does**, and one concrete scenario separates them
  observably. If either is missing, step 4 was not finished.
- readings carried over from `dv-spec-feature-extract` are **verbatim**, not re-worded.
- the document is named with its **revision and amendment level**, and for an interop case both sides'
  revisions are recorded.
- every quoted sentence is traceable to a file, or attributed to the person who supplied it with the
  entry marked provisional.
- the authority reflects where the answer actually came from — a conversation is `authority: none`
  until it is written down with a name and a date.
- all four disqualifiers in step 3 were actually tried: a keyword misread, a clause in another chapter,
  an erratum, or a revision mismatch is not an ambiguity.
- the `propagated` line names all eight artifact classes from step 8, each with a path or with the
  owner it was handed to.
- the `coverage` line is present and honest about what came from a person rather than a file.

A wrong answer typically asks a workgroup something the conventions clause already settles; states a
reading with no scenario that distinguishes it; records a hallway agreement as though it were a
maintainer's reply; or closes an entry with the checker updated, the coverage point forgotten and the
compliance list never opened.

## Done when

The question is answerable without a follow-up, the answer is recorded with its authority, and every
artifact in the propagation list has either a path or a named owner.
