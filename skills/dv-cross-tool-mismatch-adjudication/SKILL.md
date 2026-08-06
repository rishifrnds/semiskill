---
name: dv-cross-tool-mismatch-adjudication
description: Adjudicate a disagreement between two simulators, or between two modes of our own tool, on the same testcase. Reduce it to the divergence point, find the governing clause of the language standard, and rule it a tool bug, implementation-defined behaviour, unspecified behaviour the testcase should never have depended on, a testcase error, or a genuine gap in the standard. Use when a customer says our tool gives a different answer from another vendor's on their code, when optimised and debug builds of our own tool disagree, when a two-state run and a four-state run differ, when someone is about to file a defect against another vendor, or when you need to know which of two answers is the correct one before anybody fixes anything.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Cross-Tool Result Mismatch Adjudication Against the Language Standard
  semiskill-function: design-verification
  semiskill-role: eda-product-validation-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.2.1
  semiskill-review-by: 2027-07-06
  semiskill-tags: cross-tool, language-standard, adjudication, tool-validation, semantics, interop, conformance
---

# Cross-Tool Result Mismatch Adjudication Against the Language Standard

Two tools disagreeing on one testcase is not a defect report — it is an unanswered question about the
language, and the expensive mistake is answering it with an opinion. Most reported mismatches turn out
to be two runs that were never the same experiment. Of what survives that, a large share is behaviour
the standard deliberately leaves free, which makes the testcase the thing that is wrong. Only what
survives both filters is a defect, and then it matters a great deal whose.

The output is **one construct, one question, one clause and one ruling**, each with the evidence
behind it, plus a line saying how much of the two runs was actually searched. Not a description of the
difference, and never a ruling reasoned from memory of what the standard says.

## When to use something else

This skill decides **which of two behaviours is correct**. Several neighbours answer questions that
sound the same and are not.

- **Two builds of our own tool across a release** — did the tool change, and was the change intended?
  That is `dv-tool-release-behaviour-diff`. It classifies noise against intentional change against
  regression; it does not ask which behaviour the standard requires. Come here when its answer is
  `change: regression` and the tool's owner disputes that our new behaviour is wrong.
- **Only one side failed, and nobody has triaged it yet** — `dv-sim-log-first-error` first. A
  mismatch needs two results; a single failing log needs a signature.
- **The disagreement is about a protocol specification, not the language** — `dv-spec-interpretation-ledger`.
  Same discipline, different document, and it owns the workgroup question. When this skill rules
  `standard-ambiguity`, that skill's ledger is where the question belongs.
- **The two runs differ because the file sets differ** — step 1 sends that to
  `dv-build-filelist-hygiene`, and it is not a mismatch at all.
- **The ruling is `tool-bug` and R&D wants something smaller** — `dv-minimal-reproducer`. That is the
  normal way out of here, and it must preserve the divergence, not just the failure.
- **A whole cross-tool regression's worth of mismatches** — sort and rank with
  `dv-regression-triage-routing`, then bring one pair here.

## Fill this in for our team

Three facts this procedure spends are pack-wide. They live **once**, in `_shared/team-profile.md`,
and are read from there rather than re-asked here.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Run identity** | step 1 — proving the two runs are one experiment run twice |
| **Pass marker** | step 1 — catching a side that never reached the end |
| **Log location** | step 1 — finding both sides' output when only one path was given |

Ten facts belong to adjudication specifically, so they are asked for here and nowhere else.

| Slot | What to fill in | Who knows |
|---|---|---|
| Version banners | [[FILL: the exact line each side prints to identify its own version, and where in each output it appears — including the other vendor's tool, whose banner our profile could never record]] | validation lead |
| Standard and edition | [[FILL: which language standard our tool is validated against, which edition, and whether either side prints the edition it targets in its own output or whether that is documentation-only]] | tool product owner |
| Standard text access | [[FILL: whether we hold a copy of that standard's text that can be opened and read from disk, its path if so, and who supplies clause wording when we do not]] | standards representative |
| Reference side | [[FILL: which of the two runs we treat as the reference for a comparison like this, and on what authority]] | validation lead |
| Mode semantics | [[FILL: which of our tool's modes are documented to change observable behaviour rather than only speed or memory, and where that list is written down]] | tool product owner |
| Comparison method | [[FILL: what our cross-tool comparison actually compares — full output text, a filtered print set, a value dump, a checker report — and what it normalises away first]] | validation lead |
| Difference markers | [[FILL: the strings our comparison writes to open one difference in its output]] | validation lead |
| Randomisation policy | [[FILL: which randomised values, if any, our cross-tool comparisons are allowed to compare, and which are excluded before comparing]] | validation lead |
| Precedent record | [[FILL: where our past adjudications are recorded, how each entry is keyed, and whether it is a file that can be read or a page a person must search]] | standards representative |
| Escalation path | [[FILL: who files a defect against our own tool, who raises one with the other vendor, and who submits a clarification request against the standard]] | validation lead |

**Difference markers is not the profile's Fatal markers.** Fatal markers are what a *simulation*
prints when a run fails; these are what the *comparison* prints when two runs that both succeeded
disagree. Most mismatches worth adjudicating carry no fatal marker at all, on either side. If your
flow happens to use the same strings for both, record that as a finding rather than assuming it.

**Version banners is not the profile's Simulator row either.** That row says which simulator we run
and how a build is launched; this asks what each tool prints *about itself* at start-up, which is the
only evidence of what actually ran. It is a local slot rather than a profile fact for the reason that
makes this skill different from its siblings: half of every comparison here is somebody else's tool,
and no profile of ours will ever hold that vendor's banner. Fill both sides or the step-1 Grep
half-misses.

**If a slot is unfilled, stop and ask. Do not guess a convention** — and never guess a clause. An
invented clause number is the one error here that survives review, because it looks exactly like
research.

## Retrieval budget — read this before opening anything

Two runs means two outputs of hundreds of megabytes, plus a comparison that can be larger than
either. Work in this order and stop as soon as one construct and one question are named.

1. **Grep, Read and Glob work on files on disk.** Two runs means two paths. A pasted excerpt of one
   side is not a run, and there is nothing to search until both are on disk. If only one path exists,
   say plainly which half you never searched and mark the ruling provisional.
2. **The agent cannot difference two files.** Read, Grep and Glob open files; they do not compare two
   of them. Either the flow already wrote the comparison the **Comparison method** slot describes, or
   the comparison degrades to markers under rule 4 and is coarser. Say which one you did.
3. **Never open either output with Read first.** Grep for a line number, then Read a bounded window
   around it.
4. The whole budget, and nothing outside it: **two Greps** in step 1, one per side, each alternating
   the **Version banners** slot's string for that side, the edition marker the **Standard and
   edition** slot names for that side *if that slot says one is printed at all*, the profile's Run
   identity string and the profile's Pass marker; **one Grep** of the comparison for the
   **Difference markers** in step 2 — or **two**, one per side for the **Comparison method**'s
   result strings, when no comparison file exists; **two windowed Reads** of about 80 lines in step
   3, one per side; **two Greps** and **two windowed Reads** of about 60 lines in the source in step
   4; **one Grep** of the **Precedent record** in step 6, and in that same step — only when
   **Standard text access** names a readable copy — **one Grep** for the clause identifier a person
   gave you and **one Read** of at most 60 lines around it. Eight Greps, five Reads. Steps 5, 7, 8
   and 9 open nothing new.
5. **One bisection iteration is priced, and exactly one.** Step 3 may ask for a tightened pair of
   runs, and two new outputs are two new files that rule 4's tally does not cover: **one Grep** per
   new output, for the **Difference markers** or the **Comparison method**'s result strings, then
   **one windowed Read** of about 80 lines per side. Two Greps and two Reads, once. So the ceiling is
   ten Greps and seven Reads with that iteration taken, eight and five without it. A second
   tightening is not a second helping: the reduced pair is a fresh adjudication that re-enters at
   rule 1 with the budget reset, and the coverage line says how many iterations were spent here.
6. **What no marker can show is a question, not a search.** Defines, the filelist, compile and run
   options, and library and VIP versions appear in none of the markers step 1 greps for, and step 1
   has no Read. The seed appears only if the profile's **Run identity** fact includes it. Step 1
   therefore asks the engineer for whatever is left. Asking costs nothing from this budget; answering
   it from a guess costs the whole adjudication.
7. **Never browse the standard.** Enter it only at a clause identifier someone supplied. A search of
   the standard's text for a construct name returns hundreds of hits across syntax, semantics and
   annexes, and picking one of them is inventing a clause with extra steps.
8. If a Grep returns more than about 200 hits, the pattern is too broad — narrow it before reading
   anything.
9. **Stopping rule.** When the windowed Reads this budget allows are spent — five, or seven if the
   bisection iteration of rule 5 was taken — without a single construct and a single question, stop.
   Report the divergence point, how far the reduction got, and the one thing still needed. A mismatch
   adjudicated past this point is an opinion with a clause number stapled to it.
10. **State the coverage** — which of the two outputs you actually searched, whether the divergence
    came from a comparison file or was inferred from markers, how many bisection iterations were
    spent, and whether the clause was read from a file or supplied by a person. An unstated shortcut
    is far worse than a stated one.

## Procedure

### 1. Prove the two runs are one experiment run twice

This step kills more reported mismatches than every step after it, and skipping it is how an
escalation reaches another vendor and comes back the same afternoon.

Spend **one Grep per side**, each pattern alternating three things: the tool's own version banner,
the profile's Run identity string, and the profile's Pass marker. If only one side's path was given,
the profile's **Log location** says where the other should be. Then answer four questions in order:

- **Are these the two things we meant to compare?** Quote both version banners verbatim.
- **Is everything except the tool identical?** The Grep above shows three things and no more: the
  version banners, the run identity and the pass marker. Defines, the filelist, compile and run
  options, library and VIP versions and the seed are in none of them, and this step has no Read to
  spend hunting for them — so this question is not one the agent can answer. **Ask the engineer to
  confirm, side by side, that the source revision, the defines, the filelist, the options, the
  library and VIP versions and the seed all match, and to say which of those they checked rather
  than assumed.** If the file sets differ, this is a build difference and belongs to
  `dv-build-filelist-hygiene`; if anything else moved, record `ruling: not-comparable` and stop. If
  the answer has not come back, name the unconfirmed axes in the coverage line and mark everything
  below provisional — do not silently treat unconfirmed as identical. Two variables, no conclusion.
- **Do both sides target the same edition of the standard?** From the **Standard and edition** slot.
  A tool validated against one edition and a tool validated against a later one are not obliged to
  agree, and step 7 has a row for exactly that. Record both targets now, before anyone gets attached
  to a verdict.
- **Did both sides finish?** A side with no pass marker was truncated, so every difference after the
  truncation point is an artefact of the kill. Record which side carried the marker.

Record which side the **Reference side** slot makes the reference. That is a statement about
authority, not about correctness — the reference is wrong roughly as often as the other side, and
step 7 does not care which is which.

### 2. Get the difference onto disk and measure it before opening it

**Grep** the comparison for the **Difference markers**. What you want is the count and the line
numbers, not the content.

Where no comparison file exists, ask the engineer to produce one with whatever our flow uses and to
give you the path it was written to. If that cannot happen today, the comparison degrades to one
**Grep** per side for the **Comparison method**'s result strings, compared by eye — which finds
changed results and misses changed detail. Say which you did.

Let the count set expectations. A handful of differences is a real disagreement; several hundred
almost always means one systematic difference repeated per line — a path prefix, a print format, a
collection printed in a different order — and the **Comparison method** slot says which of those the
comparison was supposed to normalise away and evidently did not. Never treat a missing comparison
file as no differences; absence of an artifact is not evidence.

### 3. Find the divergence point, not the first printed difference

The first line where the two outputs differ is an upper bound on the divergence, not the divergence.
The two runs' states parted company at or before it, in whatever the testcase happened to print — and
if the testcase prints sparsely, that bound is weak. Say how weak.

Take the earliest differing line and **Read** one window of about 80 lines in each output ending
there. You are looking for the last thing the two sides agreed on that carries state — a transaction,
a value, a phase transition, a check that passed on both — and for what each side did next. Record
both, with line numbers, on both sides.

To tighten the bound, **ask the engineer to repeat both runs with printing added between the last
agreement and the first difference, or with a value dump over that window, and to give you the two
new paths**. That bisection is a loop a human drives; the agent proposes the window and reads the
result. Do not present an untightened bound as a divergence point.

### 4. Reduce it to one construct and one question

Read the source at the divergence point: one **Grep** for the enclosing scope named in step 3, one
windowed **Read** of about 60 lines; then one **Grep** for the declarations of every identifier the
suspect expression touches, and one more window of about 60 lines. Widths, signedness, four-state
versus two-state types, static versus automatic lifetime, and which process writes each of them are
the facts that decide most of these, and none of them are visible at the use site.

Then write **one question**. This is the whole discipline of the step. "The two tools disagree about
this assignment" is not a question the standard can answer. These are:

- Is this operand position self-determined, or does it widen to the context — and to what width?
- Does an unsigned operand here make the whole context-determined set unsigned?
- Does the standard fix the order of these two processes, both made runnable in the same region at
  the same simulated time?
- Is the value read here required to be the one sampled before this time step's updates, or the
  current one?
- Does the standard pin the algorithm behind this randomisation source, or leave it open?

A question phrased so that naming a reading settles it is one a clause can answer. Anything vaguer
comes back as "it depends on the configuration" six weeks later.

### 5. Clear the confounders before opening the standard

Six of these, in cost order. Every one is cheaper than a clause lookup and each is settled from the
windows already open plus the slot table — this step opens nothing new. Opening the standard first is
how a week goes.

1. **Not the same experiment.** Already answered in step 1. If it moved, nothing below applies.
2. **The comparison compared what it should have normalised.** Paths, timestamps, host names, elapsed
   and memory figures, print field widths, the default radix, how each tool renders a real number.
   The **Comparison method** slot says what it strips; anything left in is `ruling: testcase-error`
   against the comparison, not against either tool.
3. **A randomised value reached the comparison.** Check the **Randomisation policy** slot. If a value
   the policy excludes is in the difference, the comparison is invalid for that difference — say so
   and drop it, rather than adjudicating a number neither tool owed anyone.
4. **A mode is doing what it is documented to do.** Check the **Mode semantics** slot before anything
   else about our own tool. Two-state against four-state, timing on against off, race detection on,
   an optimisation level that a mode note says changes observable behaviour — a divergence that the
   list already predicts is a comparison that should never have been made.
5. **The testcase has a race.** Two processes in the same time step where one writes with a blocking
   assignment what the other reads, and no ordering discipline between them. Both orders are legal;
   this is `ruling: unspecified-behaviour` and the fix is the testcase.
6. **Something was read before it was driven.** An uninitialised variable, an unconnected port, a
   value read before reset released. What each tool then shows is a consequence of the first five
   rows, not a disagreement about the language.

### 6. Check precedent, then find the governing clause

**Grep** the **Precedent record** for the construct name and for the distinctive fragment of the
question. A ruling that already exists is the cheapest answer available and it is also the consistent
one — two adjudications of one construct that disagree cost more than either was worth. If the record
is not a file that can be read, hand the question to whoever can search it and say the check is
pending; if the slot is unfilled, say the check did not happen. Do not call a question new.

Then the clause, and there are exactly three honest ways to get one:

- **A readable copy exists**, per **Standard text access**. **Grep** for the clause identifier a
  person gave you, **Read** at most 60 lines around it. Enter at an identifier; never browse.
- **No readable copy.** Ask the standards representative for the clause identifier and its wording,
  record who supplied it and when, and mark every finding resting on it **provisional**.
- **The slot is unfilled.** Stop and ask. There is no fourth way, and in particular reciting a clause
  number from memory is not one — a wrong identifier sends the next reader to a clause that says
  something plausible about a different construct, and that error has a long half-life.

Record the edition alongside the identifier, always. A clause identifier without an edition is not a
citation, because clauses are renumbered and rewritten between editions.

**Do not paste the standard's text into a defect report, a customer-visible note or another vendor's
tracker without asking.** The document is licensed. Cite the edition and the clause identifier and
paraphrase the requirement in our own words; ask the standards representative before quoting.

### 7. Classify what the clause says, and rule

The standard's own drafting vocabulary decides this, not how strongly the clause reads. Requirement
words, permission words and recommendation words mean different things in a standards document, and
the difference between them is the difference between a defect and a preference. Read the row off
the clause's wording, write the middle column verbatim into `clause says`, and take the ruling from
the row you landed on — the token is what the next reader checks the ruling against, so it is not a
place to paraphrase.

| What the governing clause turns out to say | Write into `clause says` | Ruling | What follows from it |
|---|---|---|---|
| a requirement — the clause obliges an implementation to behave one way | `requirement` | `tool-bug` | one side violates it. Name which, and set its output against the clause |
| explicitly implementation-dependent, implementation-specific, or left to the implementation | `implementation-dependent` | `implementation-defined` | both sides conform. The testcase is what has to stop depending on it |
| explicitly undefined or unspecified, or an ordering the clause itself calls arbitrary | `undefined` | `unspecified-behaviour` | the testcase asked for something no implementation owes it |
| a recommendation rather than a requirement | `recommendation` | `implementation-defined` | quality of implementation, not a defect. Worth an enhancement, never an escalation |
| the construct is legal and the clause simply does not address this case | `silent` | `standard-ambiguity` | both defensible. Raise a clarification request and record what we do meanwhile |
| the two sides are held to different editions and the text changed between them | the token for the edition **our** side targets, with the other edition's wording in `notes` | `not-comparable` | each is correct against its own target. The comparison is the defect |
| the clause is unambiguous and **neither** side matches it | `requirement` | `tool-bug` | against both, and the testcase is right. See the Gotchas |

Two of those tokens get written for each other. `silent` is for a clause that legislates around this
case and never contemplates it; `undefined` is for a clause that contemplates it and deliberately
declines to constrain it. Writing `silent` because the clause was hard to find is how a real defect
becomes a clarification request nobody answers for a year.

`testcase-error` is decided in step 5, not here — it is the ruling for a comparison artefact, a wrong
expected value, or stimulus that was never the same on both sides. Only the two rows above that
produce `not-comparable` and `unspecified-behaviour` reach this table, and they reach it because the
clause is what exposed them.

### 8. When both sides are our own tool

Two modes of one product cannot rule `implementation-defined`. There is one implementation, so "the
standard permits both" excuses nothing. Striking that one ruling out leaves three, and all three are
live:

- the mode is on the **Mode semantics** list as changing observable behaviour, in which case the
  divergence is a documented consequence and step 5 should already have caught it; or
- `unspecified-behaviour`, which stays available and is worth checking honestly, because a testcase
  leaning on an arbitrary ordering can genuinely fall differently under two optimisation levels —
  but it needs the same clause evidence as any other ruling, not a shrug about scheduling, and it is
  the answer people reach for when they do not want to write the third one; or
- it is `tool-bug`, and it is ours.

Resist the pull of "it only happens at high optimisation". For a shipping product that raises the
priority rather than lowering it: the mode most customers run is the one that is wrong.

### 9. Record the ruling and route it

Write the failure signature first, following `_shared/failure-signature-schema.md` — same field
order, same normalisation rules — then fill in this block. `signature`, `phase`, `log` and `notes`
are the field names `dv-sim-log-first-error` and `dv-minimal-reproducer` already use, `coverage` is
`dv-minimal-reproducer`'s, and `document`, `clause` and `question` are the ones
`dv-spec-interpretation-ledger` uses, so a ruling handed to any of them keeps its vocabulary. The
rest are local to this skill, and `runs` is local for a reason: it is plural because a mismatch
carries two run identities, two version banners and two target editions where a single-failure
block carries one of each. Do not collapse it to one identifier to make it paste more neatly — the
pair travelling together is half of what this block is for.

```
signature   : <phase>|<kind>|<where>|<what>, per the shared schema
phase       : compile | elab | run | finalise | post
runs        : <both run identities, both version banners, both target editions, both seeds>
reference   : <which side the Reference side slot makes the reference, and on what authority>
divergence  : <earliest differing line on each side, and the last agreed state before it>
construct   : <the one language construct it reduces to, with file and line>
question    : <the one sentence from step 4, posed so that naming a reading settles it>
document    : <standard name and edition, exactly as printed on the document>
clause      : <clause identifier, and who supplied it if it was not read from a file>
clause says : requirement | implementation-dependent | undefined | recommendation | silent
ruling      : tool-bug | implementation-defined | unspecified-behaviour | testcase-error | standard-ambiguity | not-comparable
precedent   : <matching entry key> | not-matched | record-not-readable
next        : <the one escalation this ruling implies and to whom, from the Escalation path slot>
log         : <both paths, and the line range worth reading in each>
coverage    : <which outputs were searched; comparison file or markers; clause read or supplied>
notes       : <anything the next person would otherwise have to rediscover>
```

`phase` is the phase the **divergence** sits in, not the phase either run reached, and the two are
routinely different — a disagreement seeded at elaboration usually only becomes visible mid-run.
Set it from where the two sides stopped agreeing: a disagreement about whether the source is legal
at all, or about a constant expression folded before simulation, is `compile`; one about parameter
values, generate resolution or which module bound where is `elab`; one about a value, a delay or an
ordering while time advances is `run`; one about an end-of-run report or a final check is
`finalise`; and one about what a post-processing or reporting step made of two outputs that
themselves agreed is `post` — and that last one is a comparison defect far more often than a tool
defect, so re-read step 5 before ruling on it.

There is deliberately no `class` field. The sibling blocks use it to separate a design bug from an
infrastructure one, and a tool defect is neither — forcing this ruling into that vocabulary would
make every entry read `class: unknown` and teach the next reader nothing.

`clause says` is deliberately not the registered `strength` field and must never borrow its
modal-verb tokens, because that field grades the normative force of a statement a checker is built
from while this one records which drafting category the governing clause falls into, including the
case where the clause does not address the question at all.

Route on the ruling, using the **Escalation path** slot: `tool-bug` against us goes to our own
defect flow, `tool-bug` against the other side goes through whoever owns that relationship,
`standard-ambiguity` goes to whoever submits clarification requests, and the two testcase rulings go
back to whoever owns the testcase. Then draft the precedent entry in whatever shape that record
keys things by, and **ask whoever maintains the Precedent record to add it** — including the ones
ruled `not-comparable`, which are the ones most likely to be reported again next quarter. Drafting
the entry is yours; putting it into the record is theirs, for the same reason step 6 could only
read that record and never amend it.

## Gotchas

- **Same seed, different tool, different numbers.** Before any randomised value is allowed into a
  cross-tool comparison, confirm from the clause which randomisation sources the standard pins to a
  reference algorithm and which it leaves open — the answer differs between sources and is not
  something to recall. What the standard does constrain, for the sources it defines, is the seeding
  *structure*: which generator an object or a process draws from, and when it is re-seeded. So "the
  two tools produced different values" is never a finding, while "one side re-seeded where the other
  did not" can be a real one.
- **A different constraint solution is not a wrong one.** The obligation on a solver is to produce a
  solution satisfying the constraints, not a particular solution, and directives that order the solve
  change the distribution rather than the solution set. Only two comparisons mean anything: did
  either side produce a solution that violates a stated constraint, and did either side report no
  solution where the other found one. Chasing distribution differences consumes weeks and settles
  nothing.
- **Width and sign are properties of the whole expression, not of the operand.** Some operand
  positions are self-determined and take their own width regardless of context; the rest are
  context-determined and widen to the largest operand in the expression, which includes the
  assignment target. Signedness follows the same split. Which positions are which is a *list* in the
  standard, not a principle to be extrapolated from the nearest similar operator — read it. This is
  where genuine tool defects concentrate, precisely because the rule is exact enough to be violated.
- **The event regions fix a lot of ordering and deliberately leave some of it free.** Two processes
  made runnable in the same region at the same simulated time may execute in either order, and the
  standard says so. A divergence that reduces to that ordering is never a tool defect, however much
  the testcase's author wanted one order — and every such testcase is one edit away from failing on
  the tool it currently passes on.
- **A two-state run and a four-state run are not the same experiment.** Two-state execution replaces
  unknown values with a defined one by construction. The standard does not describe that mode and is
  not being violated by it, so comparing the two is comparing a tool against a deliberate
  approximation of itself.
- **Formatting is not behaviour.** Field widths, default radix, how each tool renders a real number
  and where each breaks a line differ, and a textual comparison reports every one of them as a value
  mismatch. Settle what the comparison normalises before anything printed is called a difference.
- **"Both tools are wrong" is a real ruling and it is under-used.** Two implementations with shared
  heritage, or two that copied the same widely-believed reading, often diverge from the clause in the
  same direction. If the clause is unambiguous and neither side matches it, the finding is against
  both and the testcase is the only correct thing in the room.
- **The first printed difference is not the divergence.** State parted earlier, in whatever the
  testcase did not print. Reporting the first differing line as the divergence point sends R&D to
  read the consequence, and the narrower the testcase's printing, the further off it is.
- **A clarification request is not a way to avoid deciding.** It takes months. Record what our tool
  does today, why that reading is defensible, and exactly what we would change if the answer goes the
  other way — otherwise the reply arrives and nobody remembers which build it applies to.
- **An adjudication nobody can find gets made again.** The precedent record is the deliverable that
  outlives the ticket, and the entries most worth writing are the boring ones: the third time a
  construct is reported, the entry is what stops the third investigation.

## Human verification — what a wrong answer looks like

Before acting on the ruling, check:

- both version banners and both target editions are quoted **from the outputs themselves**, and
  `ruling: not-comparable` was genuinely ruled out rather than skipped
- the build-equivalence answer in step 1 came back from a person and names what they checked — an
  adjudication that assumed the two builds matched is an adjudication of two different experiments
- `clause says` carries the token step 7's table maps that row to, and the ruling on the line below
  it is the one that row produces; a `clause says` and a `ruling` from two different rows means the
  clause was read to fit a verdict somebody already held
- the clause carries an **edition** and an identifier, and says whether it was read from a file or
  supplied by a person — a citation with no edition is not a citation
- no clause number appears that was not read or supplied; nothing was recited from memory
- the ruling follows from what the clause *says*, not from which side we would rather be right, and a
  recommendation has not been reported as a requirement
- the construct is named with a file and a line, and the question is one sentence a clause can answer
- nothing randomised, nothing purely formatting, and nothing on the **Mode semantics** list has been
  adjudicated at all
- for two modes of our own tool, `implementation-defined` does not appear — it is not available
- the coverage line says which outputs were searched, whether a real comparison file or only markers
  were compared, and whether the divergence bound was ever tightened

A wrong answer names a tool bug from the first differing line without ever reducing to a construct;
or cites a clause nobody opened; or rules `implementation-defined` on two modes of our own product,
which is the most comfortable wrong answer available and closes a real defect as a non-issue.

## Done when

One construct, one question, one cited clause with its edition, one ruling and one named escalation —
and a coverage line that says how much of both runs was actually opened.
