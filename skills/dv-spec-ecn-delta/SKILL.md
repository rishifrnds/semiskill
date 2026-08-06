---
name: dv-spec-ecn-delta
description: Size an ECN or errata against a released spec revision by tracing every normative change into the verification plan, testbench, checker rules, coverage model, test suites and docs, then returning counts a lead can price. Use when a standards body publishes an ECN or errata, when a new spec revision is published and you must say how much VIP work it is, when someone asks whether a change is a patch or a major release, or when you need the list of tests that will correctly start failing.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: ECN and Spec-Revision Delta Impact Analysis
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-09-14
  semiskill-tags: ecn, errata, spec-revision, impact-analysis, vip, sizing, verification-plan, coverage
---

# ECN and Spec-Revision Delta Impact Analysis

An ECN arrives as four sentences and turns into six weeks, or arrives as forty pages and turns into
an afternoon. Which one it is has almost nothing to do with the size of the text and almost
everything to do with whether the change is retroactive, which direction it moves a constraint, and
how many places in the VIP already encode the old reading. This walks each normative change into the
six surfaces that can hold it and returns **counts** — rules, bins, rows, tests — which a lead prices
against our own rates rather than against a number invented here.

The output is an **impact register**, one row per normative change, plus a line saying how much of
the ECN was actually traced. Not a summary of the ECN.

## When to use something else

This sizes a change before anyone builds it. Once the change is in and one test is failing, use
`dv-sim-log-first-error`; when the branch comes back with dozens of failures to sort and route, use
`dv-regression-triage-routing`; to shrink one of those for a designer, use `dv-minimal-reproducer`.
A branch that will not compile is `dv-build-filelist-hygiene`. If the ECN only moves a capability or
status register — new field, new reset value, new access policy — that row's work belongs to
`dv-ral-bringup`; size the rest here and hand it over. And if you cannot yet say where this VIP keeps
its checkers, coverage model and test list, start with `dv-repo-orientation`; the budget below
assumes you already know.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| ECN source | [[FILL: where approved ECNs and errata for this protocol land in a form that can be read from disk, and which base spec revision our released VIP currently claims]] | standards liaison |
| Clause reference convention | [[FILL: how our VIP source, checkers, vplan and tests cite a spec clause — a comment tag, a rule-ID prefix, a vplan column — and whether that citation records the revision it was written against]] | VIP architect |
| Checker rule identity | [[FILL: how one protocol rule is named or numbered in our checker code, and where the list of rule identifiers lives]] | checker owner |
| Verification plan location | [[FILL: where this protocol's vplan lives, whether it is a file that can be read or a tool database a person must query, and what each row is keyed on]] | verification lead |
| Coverage model location | [[FILL: where this protocol's covergroups and bin definitions live in the source tree]] | coverage owner |
| Revision gating knob | [[FILL: the configuration our VIP uses to select spec revision or enable an ECN feature, its legal values, and what it defaults to]] | VIP architect |
| Test list location | [[FILL: where this protocol's test list lives, and how a test records which clause or feature it covers]] | block DV owner |
| Docs set | [[FILL: which documents must change when observable VIP behaviour changes — user guide, release notes, compliance matrix — and where they live]] | VIP release owner |
| Release compatibility policy | [[FILL: what we may change in a patch release versus a minor versus a major, for customers already integrated against the released VIP]] | VIP release owner |

Pack-wide facts live in `_shared/team-profile.md` and are read from there, not re-asked: the **Area
to owner map** routes each row in step 9, **Sign-off** says what evidence closes the ECN, and the
**Regression summary** is what step 7 asks the engineer for. Two rows above resemble profile rows and
are **not** the same fact. **Coverage model location** is the *source* of covergroups and bins; the
profile's **Coverage output** is where *merged results* land, and step 6 needs the first. **Test list
location** is this protocol's list, which at an IP house is narrower than whatever the regression
wrapper sweeps.

Every row is spent: ECN source in step 1; Clause reference convention in steps 2 and 5; Revision
gating knob and Release compatibility policy in step 4; Verification plan location, Checker rule
identity, Coverage model location, Test list location and Docs set in steps 5 and 6.

**If a slot is unfilled, stop and ask. Do not guess a convention** — and never quote a clause number,
a parameter value or a rule name from memory of the protocol. An invented clause reference survives
review, lands in a customer release note, and is found by the customer.

## Retrieval budget — read this before opening anything

A protocol VIP is tens of thousands of lines across agent, checkers, coverage and tests, and the spec
is longer than all of it. Work in this order and stop when the register is filled:

1. **Grep and Read work on files on disk.** An ECN arriving as a PDF, an email, a slide or a
   colleague's chat summary cannot be searched. Step 1 resolves it to a path or marks the whole
   register provisional; there is no third option.
2. **Cap the change list at 12 normative changes.** If the ECN carries more, take the first 12 in
   document order and say how many were left unsized. Twelve rows traced beat forty guessed.
3. **Two Glob calls** — one for the ECN and base-revision files in step 1, one for the six surfaces
   in step 5.
4. **Eight Grep calls**: two in step 4 (the gating knob, and any earlier ECN tag already in the
   tree), six in step 5 — one per surface, each an alternation over all the clause keys from step 2
   rather than one call per clause. Never open a surface with Read first.
5. **Six windowed Read calls of about 60 lines**: two in step 2 on the ECN's change list, four in
   step 6 at the densest hits. Steps 7 to 9 reuse what is already open.
6. A Grep returning more than about 200 hits is too broad — anchor it on the **Clause reference
   convention** tag before reading anything.
7. Stopping rule: once two Globs, eight Greps and six Reads are spent with the register unfilled,
   stop, report the rows you did fill, and name the one artifact you still need. Past that point the
   remaining rows get invented, and an invented row is what a lead prices.
8. State what you covered — how many changes were traced, and which surfaces were never opened.

## Procedure

### 1. Resolve the ECN to text, and pin the base revision it edits

Use **one Glob** under the **ECN source** slot's path for the ECN or errata document and for the base
revision it applies against. An ECN is meaningless without that revision — the same clause number
means different things two revisions apart. Three outcomes, not equivalent:

- **A readable text file.** Proceed; the register will be evidence-backed.
- **A PDF, a slide, or a licensed document Read cannot open.** Ask the engineer to extract the change
  list — clause reference, old text, new text, one row per change — into a plain text file and give
  you that path. Do not paraphrase the protocol from memory to fill the gap.
- **Described verbally, or pasted into the chat.** You may reason over what you were shown, but say
  so: every row is provisional, no clause number in it came from a file, and the register must not be
  circulated as a sizing until someone confirms it against the document.

Record the ECN identifier and the base revision verbatim; both go in the register's `ecn` field.

### 2. Split the ECN into normative changes, one row each

Spend **two windowed Read calls** on the ECN's own change list or summary of changes. One row per
*normative* change — a change to what an implementation must, must not or may do. Wording that does
not change conformance is a single `editorial` row, however many pages it spans.

Capture verbatim, per row, the clause reference edited and the sentence that changed. Write the
reference in the form the **Clause reference convention** slot says our tree uses, so step 5's Greps
match. If the ECN renumbers clauses, record **both** numbers — the old one is what our tree cites
today, the new one is what it will cite tomorrow, and a Grep on the new number alone finds nothing.
Past 12 rows, stop and note the remainder (budget rule 2).

### 3. Classify each row

The class drives the sizing. Read the row's new text, not its title.

| `delta` | What changed | Usually costs | The trap |
|---|---|---|---|
| editorial | wording only, conformance unchanged | docs, and clause citations | renumbering silently breaks every citation in the tree |
| clarification | text was ambiguous, behaviour always this | one checker, many tests | our checker may hold the *other* reading, so passing tests passed wrongly |
| tightening | a legal value or range becomes illegal | checker, bins, constraints | we are now under-constrained, and nothing fails to tell you |
| relaxation | a reserved or illegal value becomes legal | checker gating, bins, stimulus | our checker fires on legal customer traffic, today |
| new-optional | a capability a device may implement | knob, sequences, both-ways coverage | the disabled case still needs a check that the feature is absent |
| new-mandatory | a capability every device must implement | all six surfaces, plus compliance | the default configuration moves, so every existing test changes context |
| removal | behaviour becomes illegal or reserved again | checker, retired tests, retired bins | old tests are not wrong, they are wrong *for the new revision only* |
| default-change | a reset value or default behaviour changes | one line, every test | nothing in the diff shows the blast radius |
| parameter | a min, max or timeout number moves | one package constant | boundary bins now sit on the wrong side of the limit |
| state-machine | a state or transition added or removed | monitor, checker, transition bins | transition goals shift and historical data stops merging |

A row fitting two classes becomes two rows. Merging them is how the cheap half hides the expensive
half.

### 4. Decide retroactivity, then gating — in that order

**Retroactivity first.** Does the row change what was already correct behaviour under the base
revision? Errata and clarifications usually do — the text is being corrected, so the behaviour was
always meant to be this. New features usually do not. Retroactive rows are the ones where a green
regression is evidence of a problem rather than of health, and step 7 depends on the answer.

**Gating second**, and it follows. Spend **one Grep** for the **Revision gating knob** slot's
configuration name to see which values exist and what the default is. A retroactive correction
normally applies unconditionally. A new optional or mandatory feature must be gated on the revision
or capability the customer's configuration names, and must never default to the newest behaviour —
every integrated customer would see new checks fire on an unchanged testbench. The **Release
compatibility policy** slot then says whether the row ships as a patch, a minor or a major.

Spend **one Grep** for any earlier ECN tag on the same clause already in the tree. An ECN folded into
a later revision is usually reworded and occasionally narrowed; implementing it twice leaves two
checkers that agree everywhere except the boundary that matters.

### 5. Trace the change list into the six surfaces

**One Glob** for the surfaces named by the **Verification plan location**, **Checker rule identity**,
**Coverage model location**, **Test list location** and **Docs set** slots, plus the testbench
configuration holding the gating knob. Then **one Grep per surface** — six calls — each an
alternation of every clause key from step 2, anchored on the **Clause reference convention** tag.

Record hit counts per surface per row. A row with hits in one surface and none elsewhere is usually
not cheap; it usually means the other surfaces never cited the clause, which is a finding about our
traceability rather than evidence of low impact. Say which it is.

The surface that most often reads as zero and is not zero is the vplan. If its rows are not keyed on
clause references the Grep finds nothing, and the honest register entry is "vplan not clause-keyed,
rows cannot be found mechanically" — never "no vplan impact".

### 6. Size each surface in countable units

Spend the remaining **four windowed Read calls** at the densest hits. Count; do not estimate hours.

| Surface | Count these |
|---|---|
| Verification plan | rows citing the changed clause; rows with no clause key, so unfindable |
| Testbench and configuration | knob values added; classes touched; whether the default moves |
| Checker rules | rules to add, change, gate by revision, retire — and separately, rules correct for the old text and now wrong |
| Coverage model | bins added, bins whose meaning changes, bins retired; whether a cross with the gating knob is now required |
| Test suites | tests to add, modify, retire, re-run because the default moved, and tests that will now fail correctly |
| Docs | documents to change, and whether the change is observable enough to need a release note |

Two cells carry more risk than their count suggests. "Rules correct for the old text and now wrong"
is the entire cost of a clarification. "Bins whose meaning changes" is what makes coverage recorded
before and after the change non-comparable — see the Gotchas.

### 7. Predict the expected-failure set, and price its triage separately

The agent cannot start a simulation, launch a regression or merge coverage, and must not invent what
one would have printed. What it can do is name, from step 6's test counts, the tests expected to fail
*correctly* after the change, with a reason each.

Then hand over: **ask the engineer to build the branch with the change, run this protocol's
regression, and give you the path to the resulting summary** — the profile's **Regression summary**
row says where that lands and in what shape. Failures you predicted are the cost of the change;
failures you did not predict are either a surface missed in step 5 or a real defect in the
implementation, and the register must say which.

Size the triage of that set as its own line. A three-line checker change that turns four hundred
tests red costs far more in confirming those four hundred than in writing the three lines, and an
estimate omitting it is wrong by an order of magnitude rather than by a margin.

### 8. Rank by direction of error, not by size of diff

Two rows with identical counts can have opposite urgency, and the tell is which way the constraint
moved.

- **Over-constraint** — the ECN permits what our checker forbids. This is breaking a customer today,
  on traffic that is now legal, and it arrives as an escalation. Rank first, always.
- **Under-constraint** — the ECN forbids what our checker permits. Nothing fails. The VIP stays green
  and quietly stops catching a class of real bug, found later and much further downstream.
- **Neither** — editorial rows, and additive features nobody has enabled yet.

Rank over-constraint, then under-constraint on mandatory clauses, then new-mandatory, then breadth
across surfaces, then new-optional, then editorial. Give the reason next to the rank.

### 9. Write the impact register

One block per row of the change list, ranked. Field names are shared with the pack's other handoff
blocks wherever they mean the same thing, so the blocks read side by side.

```
ecn       : <the ECN or errata identifier, and the base spec revision it applies against>
change    : <the ECN's own identifier for this change, and the clause it edits, both verbatim>
delta     : editorial | clarification | tightening | relaxation | new-optional | new-mandatory | removal | default-change | parameter | state-machine
retro     : retroactive | prospective | undecided
gating    : unconditional | revision-gated | feature-gated | undecided
risk      : over-constraint | under-constraint | both | none
vplan     : <rows citing the clause; rows unfindable because the vplan is not clause-keyed>
config    : <knob values added; classes touched; whether the default moves>
checkers  : <rules to add / change / gate / retire, and rules now wrong>
cov model : <bins added / redefined / retired; cross with the gating knob needed or not>
tests     : <add / modify / retire / re-run / will-fail-correctly>
docs      : <documents to change; release note needed or not>
release   : <patch, minor or major, per our compatibility policy>
rank      : <n> because <over-constraint / mandatory / breadth / compliance>
owner     : <name from the area map, or blank plus candidates>
evidence  : <file path and line for every count above; ECN clause for every quoted sentence>
coverage  : <n of m normative changes traced; surfaces never opened; provisional or confirmed>
notes     : <anything the next person would otherwise rediscover, including any fact that came from a person rather than a file>
```

Write `?` in any field that cannot be filled from text you actually read. Under the last block, put
one line giving the totals across all rows in counts, not hours. The **Sign-off** row of the team
profile says what evidence closes the ECN.

## Gotchas

- **An editorial change is not reliably zero work.** If our checkers and vplan cite clause numbers
  and the revision renumbers them, every citation now points at the wrong clause and nothing fails.
  Confirm what the **Clause reference convention** slot records before writing a row off.
- **A clarification is the most expensive class per line of text.** "It always meant this" means our
  checker may hold the other reading, and every test that passed under that reading passed wrongly.
  It is the one class where a green regression after the change is evidence of a problem.
- **Relaxation breaks customers immediately; tightening breaks them silently.** Same diff size,
  opposite urgency. Rank by direction, never by line count.
- **Reserved does not mean unused.** Most protocols define reserved as write-zero, ignore-on-read,
  which is exactly the rule letting a later ECN assign meaning to those bits without breaking
  conformance. A checker flagging a non-zero reserved field is over-constrained the moment the ECN
  lands, and must stay strict for the old revision — so the fix is gating, not deletion.
- **Applying a new optional feature unconditionally is the classic VIP field bug.** Every integrated
  customer sees new checks fire on a testbench they did not change, and cannot tell our regression
  from their bug. The knob defaults to the revision their configuration names, not to our newest.
- **Redefining a coverage bin invalidates every merge across the change.** Data recorded before and
  after a bin's meaning changes cannot be combined honestly — the merge either errors or, worse,
  keeps one definition and reports a number nobody can reproduce. Retire the old bin under a new name
  rather than editing it in place, and say in the release note what stopped being comparable.
- **An illegal bin added retroactively fires on replayed old tests.** If an encoding becomes illegal
  only from the new revision on, that bin has to be crossed with the gating knob, or our own
  regression starts reporting still-legal old-revision traffic as an error.
- **The ECN text and the next revision's text are not the same words.** Folded into a revision, an
  ECN is usually reworded and occasionally narrowed. Implementing both without diffing them leaves
  two checkers that agree everywhere except the boundary case the ECN existed to fix.
- **A parameter change is cheap to make and easy to mis-size.** The number lives in one package, so
  the diff looks trivial; the cost is in the coverage model, where the old boundary bins now sit
  inside the legal range and the new boundary is hit by no existing test.
- **A new mandatory feature moves the default configuration**, so every existing test runs in a
  context it was not written for. Those tests are not modified and not retired — they are the
  "re-run" column of step 6, and forgetting that column is why re-run cost is missing from most ECN
  estimates.

## Human verification — what a wrong answer looks like

Before circulating the register, check:

- every row's clause reference was **read from a file**, not recalled — and if step 1 landed on the
  verbal or pasted case, the register is labelled provisional at the top
- the sizing is in counts, with a file path and line behind each one; nothing in it is in hours
- every non-editorial row names a risk direction, and the ranking puts over-constraint first
- every row carries a gating decision, and no new optional or mandatory feature is unconditional
- retroactive rows say explicitly that existing passing tests may have been passing wrongly
- the coverage line gives traced-of-total and names the surfaces never opened
- a vplan showing zero hits is reported as "not clause-keyed" when that is what it was, not as "no
  impact"

A wrong answer typically calls a four-sentence ECN small because the diff is four sentences; sizes a
clarification at one checker and no tests; leaves the expected-failure triage out of the estimate
entirely; applies a new optional feature to every customer at once; or quotes clause numbers
belonging to the revision *after* the one the ECN was written against.

## Done when

A lead can read the register, price each row against our own rates, and choose the release vehicle
without opening the ECN themselves.
