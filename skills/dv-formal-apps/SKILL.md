---
name: dv-formal-apps
description: Choose and read the packaged formal apps - connectivity, register, coverage unreachability and post-ECO sequential equivalence - without being a formal specialist, by checking the inputs, reading the report by proof status, and telling a real design bug from a wrong reference table. Use when someone asks you to prove that these pins are connected, when the control registers need checking against the register spec and nobody is going to write properties, when coverage will not close and someone suggests waiving the unreachable items, or when a late ECO has to be shown equivalent to the model that was already signed off.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Packaged Formal Apps: Connectivity, Register, Unreachability and Equivalence"
  semiskill-function: design-verification
  semiskill-role: formal-verification
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-07-07
  semiskill-tags: formal, connectivity, registers, unreachability, equivalence, eco, coverage-exclusion
---

# Packaged Formal Apps — Connectivity, Register, Unreachability and Equivalence

Four formal apps are worth reaching for even if you have never written a property, because each of
them takes a document your team already has and turns it into an exhaustive check. What makes them
dangerous is the same thing that makes them cheap: the reference document *is* the specification, the
constraint set *is* the definition of what the design is allowed to do, and both are written by
people. A packaged app that reports a hundred percent proven is telling you about the setup at least
as much as about the RTL.

This skill picks the right app, checks the inputs before a licence is spent, and then reads the
report by **proof status** rather than by pass count. The one result it deliberately slows down is
unreachability: those rows end up deleted from the coverage number that ships, so they leave here as
a **candidate list with a sign-off request attached**, never as an exclusion.

## When to use something else

Four formal siblings sit immediately around this one, and each owns a question this skill
deliberately stops short of.

- **Upstream — which block, and is an app the right claim at all:** `dv-formal-target-scoping`. It
  ranks candidates and hands anything it lands on `claim: connectivity`, `claim: unreachability` or
  `claim: equivalence` straight to here; where such a record exists, its `bound`, `assumes` and
  `owner` lines say what the plan expected, and step 3 compares them against what the run actually
  did. Arriving without one is fine —
  step 1 re-derives the routing from the question. One correction if you read that skill first: its
  routing paragraph describes this one as *running* the packaged apps. It does not. Step 3 hands the
  run to a named engineer, and every step after it reads only the report that comes back.
- **After step 4, for a bounded or inconclusive status:** `dv-formal-convergence`. This skill records
  that status and its depth and stops — choosing between a black box, a parameter reduction, a helper
  property or a decomposition, and naming which direction each moves soundness in, is that skill's
  subject. Take the report path and the per-status counts with you.
- **Before anyone claims credit for a proven result:** `dv-formal-overconstraint-credit`. Gate 2 of
  step 6 asks one narrow question — is this constraint set a defensible basis for deleting coverage
  items? Whether a counterexample is an environment artifact, whether the assumption set left the
  passing checks vacuous, and how much sign-off credit the run earned are the broader audit and belong
  there. The vacuity Gotcha below is the symptom; that skill is the audit.
- **A property you have to write yourself:** `dv-formal-property-authoring`. The moment the answer
  needs an assert nobody packaged, you have left this skill — see the last bullet.
- A UVM register-model bring-up that failed in **simulation** is `dv-ral-bringup`. It and the register
  app read the same register description and answer different questions from it; step 5 says how they
  meet.
- One failing simulation log is `dv-sim-log-first-error`. A whole night of them is
  `dv-regression-triage-routing`.
- The app itself failed to compile or elaborate: that is `dv-build-filelist-hygiene`. Formal apps
  consume the same filelists the simulation build does and break in the same ways.
- You do not yet know where the filelists, the coverage area or the run areas live:
  `dv-repo-orientation`.
- **Still the specialist's call, sibling skill or not.** A hand-written property, an abstraction, a
  decomposition, a proof that will not converge, or a judgement about whether a constraint is
  legitimate is formal-specialist work. The four formal siblings above give it a written shape and are
  pitched at senior readers; none of them removes the need for the formal owner's judgement, and
  reaching for a packaged app because the real question is hard is how a wrong green result gets into
  a sign-off review.

## Fill this in for our team

Five facts this procedure spends are pack-wide and live **once** in `_shared/team-profile.md`. They
are read from there and deliberately not copied below.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Filelist convention** | step 2 — the app compiles the design from the same filelists the build does |
| **Register model source** | steps 2 and 5 — the register app's reference is that same document |
| **Coverage output** | step 6 — the uncovered items an unreachability run is given come from there |
| **Area to owner map** | step 8 — routing a confirmed design bug to one person |
| **Sign-off** | step 6, as the general rule the narrower slot below sits inside |

Eight facts are specific to formal apps, so they are asked here and nowhere else:

| Slot | What to fill in | Who knows |
|---|---|---|
| App inventory | [[FILL: which packaged formal apps we are licensed for, their exact names in our tool set, and which blocks are already set up for each]] | formal owner |
| Report location | [[FILL: where each app writes its report, what that file is called, and whether it is text we can read or a database only the tool opens]] | formal owner |
| Proof status strings | [[FILL: the exact strings our reports print for a full proof, a counterexample, a bounded proof and its depth, an inconclusive result, and a vacuous check]] | formal owner |
| Connectivity table | [[FILL: where our connectivity specification lives and what each column means — source, destination, enabling condition, latency, bit mapping]] | integration owner |
| Constraint set | [[FILL: where the formal setup and constraint files for this block live, and who owns each constraint]] | formal owner |
| Exclusion destination | [[FILL: where coverage exclusions live, how each entry is keyed, and what our flow says invalidates one]] | coverage owner |
| Formal sign-off | [[FILL: who signs off a formal constraint set and an unreachability candidate list, and what evidence they require]] | verification lead |
| ECO model pair | [[FILL: how we name and store the pre-ECO and post-ECO models, and where the ECO's intended change is written down]] | implementation owner |

Two of these look like profile facts and are not. **App inventory is not the profile's Simulator** —
a formal engine and a simulator are different tools, often from different vendors, and filling one
from the other sends step 3 to ask for a run nobody can start. **Proof status strings are not the
profile's Fatal markers** — the markers are what a *simulation run* prints into a log, these are what
a *formal report* prints into a report file; they are different files in different vocabularies, and
copying one into the other makes step 4 search for strings the report never contains.

**Formal sign-off is narrower than the profile's Sign-off.** The profile records who signs off and on
what evidence in general. This asks specifically who signs a formal *constraint set* and an
unreachability candidate list, which is frequently the formal owner rather than whoever signs the
coverage number. If your team gives both to one person, write that down rather than assuming it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented app name, report path
or status string produces a confident reading of a file that was never opened.

## Retrieval budget — read this before opening anything

A connectivity report for a subsystem carries thousands of rows; an unreachability report carries one
row per uncovered item and can be larger than the coverage database it came from. None of them is
readable end to end. Work in this order and stop as soon as the origin of one finding is settled.

1. **Grep, Read and Glob work on files on disk.** If the report arrived pasted into the conversation,
   ask for the path it was written to. If the **Report location** slot says the app writes a database
   rather than text, no Grep can reach it either — ask the engineer for a text export and the path it
   landed at, and until then say plainly that nothing has been searched.
2. **Never open a report with Read first.** Locate it with **Glob**, find rows with **Grep**, then
   Read a bounded window around specific line numbers.
3. Step 2 costs at most **3 Globs** — the filelist entry point, the app's reference input, the
   constraint directory — and **2 Greps** across them.
4. Step 4 costs **1 Glob** for the report, **2 Greps** for the proof-status strings (one alternating
   the conclusive statuses, one the inconclusive ones), and at most **3 windowed Reads** of about 80
   lines.
5. Whichever of steps 5, 6 and 7 applies — only one does — costs **2 Greps and 2 Reads** of about 60
   lines over at most **4 constraint files**, plus at most **3 Greps and 3 Reads** of about 40 lines
   cross-checking at most **3 report rows** against the RTL or the reference document.
6. That is the whole ledger: **4 Globs, 9 Greps, 8 Reads**, one app, one pass, three rows. Scope every
   call to one directory; a recursive search from the repository root returns tens of thousands of
   paths. If a **Grep** returns more than about 200 hits the pattern is too broad — narrow it before
   reading anything.
7. **Stopping rule.** When the ledger is spent and the origin of the finding is still open, stop, write
   `origin: undecided`, and name the one thing still needed. Past that point the answers get invented.
8. **State what you actually covered** — rows opened out of rows in the report, constraint files read
   out of files the run used. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Decide which of the four questions this is — and whether it is an app question at all

Route on the question, not on the tool. Each app answers exactly one, from a document you supply.

| The question | Answered from | What it can never tell you |
|---|---|---|
| Does this pin reach that pin, in this mode, after this many cycles? | a connectivity table | whether the table describes the intended design |
| Does the RTL match the register spec — reset values, access policy, decode? | the register spec | anything about a register the spec does not list |
| Is this uncovered coverage item reachable at all? | uncovered items plus a constraint set | whether that constraint set matches silicon |
| Do these two models behave the same after the ECO? | the two models plus a mapping | whether either model is correct |

If the question is none of these — a protocol to prove, an arbiter to show is fair, a deadlock to rule
out — it is not a packaged app, and the honest move is a handoff to the person named in the **Formal
sign-off** slot rather than bending one of the four into shape.

App names are vendor vocabulary. Take the exact name from the **App inventory** slot; the agent does
not know what your tool set calls these and must not guess one.

### 2. Confirm the inputs exist, and say plainly what you could not confirm

Use **Glob** for the three things the run needs, scoped one directory at a time: the filelist entry
point (the profile's **Filelist convention** says how ours nest and what relative paths resolve
against), the app's own reference input, and the **Constraint set** directory for this block.

The reference input depends on the app: the **Connectivity table**, the profile's **Register model
source**, the merged area under the profile's **Coverage output**, or the pair named in the **ECO
model pair** slot. Then two **Greps**: one for this block's name inside the constraint set, one for
this block's rows inside the reference document. A reference document with no rows for the block is
the finding — the run would have proved an empty set.

Anything you could not locate goes into the report as *not confirmed*, not as *missing*. And if the
app fails at compile or elaboration rather than producing a report, that is a build break:
`dv-build-filelist-hygiene`, with the first diagnostic.

### 3. Hand the run off, and ask for the setup that produced the report

The agent cannot start a formal engine, take a licence, or submit to a compute farm. Ask the engineer
to run the app named in the **App inventory** slot and to send back five things:

1. the path on disk of the report it wrote
2. the constraint and setup files the run **actually read** — not the ones sitting in the repository
3. the tool and version string the report prints
4. the effort or time limit, and whether the run hit it
5. the RTL revision the run compiled

Items 2 and 5 are not bookkeeping. A proof result without its constraint set and its revision is a
number with no claim attached, and it cannot be re-checked by anyone later.

If this target arrived on a `dv-formal-target-scoping` record, that record's `assumes` and `run id`
lines already say what capacity, licence and revision the *plan* expected. They are the comparison,
not the answer: still ask for all five items above, then say whether the run matched the plan. A run
that quietly took a different revision or a smaller effort limit than the plan assumed is a finding
in itself.

### 4. Read the report by proof status, never by row order

Use **Grep** for the **Proof status strings** — two calls, one alternating the conclusive statuses and
one the inconclusive ones. Count the hits and write the counts down *before* opening a single row.

| Status | What the run established | What you may claim |
|---|---|---|
| full proof | the check holds in every reachable state under this constraint set | it holds under those constraints — name them |
| counterexample | there is a state sequence that violates the check | something disagrees; steps 5 to 7 decide what |
| bounded proof to depth N | no violation within N cycles of reset | nothing about cycle N+1. Record N |
| inconclusive | the engine stopped without deciding | nothing at all |
| vacuous | the check's precondition can never hold | the check never ran — a setup bug |

Then reconcile: the five counts must add up to the number of checks the run was given. If they do not,
rows are being printed in neither column — usually paths into a black-boxed memory or analog block —
and finding them comes before believing any of the others.

Two statuses are read wrongly more than the rest. A **bounded** result looks like a pass in a summary
table, and a **vacuous** one looks like a pass in every table. Neither is a proof.

Where bounded or inconclusive rows dominate the counts, this procedure's contribution is finished at
those counts and their depths. Deciding what to change so the next attempt converges is
`dv-formal-convergence`; asking here for a longer run is the move that spends another night for three
more cycles of depth.

### 5. Connectivity and register failures — the reference is a document somebody wrote

On a new table or a new register spec, a large share of the first failures are reference failures.
Cross-check at most three rows, under the budget in rule 5, before anyone files a bug.

| Connectivity symptom | Check first | Usual cause |
|---|---|---|
| a whole group of paths falsified together | the enabling condition shared by the group | the paths exist only in a mode nothing constrained the design into |
| falsified, and the counterexample shows both ends holding still | the direction of the row | source and destination swapped in the table |
| falsified on some bits only | the bit mapping | a bit range written the other way round in the table |
| falsified at the first cycles, holding later | the declared latency | a registered path written as combinational |
| proven, but the source can only ever be one value | whether the source is tied off at this level | both ends are the same constant and no path was tested |
| every path through one hierarchy inconclusive | whether that hierarchy is black-boxed | a memory or analog block with no model |
| paths hold only with the test pins at one value | the scan and test-mode constraints | DFT muxing — a constraint question, not a bug |

| Register symptom | Check first | Usual cause |
|---|---|---|
| reset mismatch on one register | three values — spec, RTL, report | spec and RTL built from different revisions |
| reset mismatch on every register | the reset sequence in the setup | the run never entered reset, or never left it |
| the app says writable where the spec says read-only | whether hardware writes that field | a hardware-updated field the spec never marked volatile |
| a clear-on-write or clear-on-read field reported as mismatching | whether the app models that side effect | the policy is right and the model of it is not |
| an indirect or windowed register reported as broken | whether the app supports indexed access | usually unsupported; exclude it in the setup and say so |
| one address decoding to two registers | the offsets in the spec and the block base | overlapping offsets in the reference |
| a lockable register mismatching | the lock's constraint | nothing constrained the lock, so the app wrote through it |

The register spec here is the profile's **Register model source** — the same document
`dv-ral-bringup` reads. That skill debugs a simulation that already failed; this one proves the RTL
against the document exhaustively. When the two disagree about a reset value, the document is where
the disagreement is settled, and neither result outranks it.

### 6. Unreachability — the one result you may not turn into an exclusion

An unreachability result is a claim of a very specific shape: *under this constraint set, in this
configuration, on this RTL revision, this item cannot be covered.* Every clause carries weight, and an
exclusion file carries none of them forward. Three gates, all three, before a single candidate leaves.

**Gate 1 — the status is a proof.** Only a full proof counts. A bounded result says no covering
sequence exists within N cycles, and an item first reachable after a long initialisation sequence sits
far past the depth a default run reaches. An inconclusive result says the engine gave up. Both print
as "still not covered" in a summary column, and both are routinely swept into exclusion lists.

**Gate 2 — the constraint set is one that sign-off would accept.** Every constraint is an assumption
about the world, and an over-constrained run makes reachable items unreachable. The four that produce
the most false unreachables: a mode or strap pin held at one value; a parameter or configuration fixed
at one setting; test and scan pins constrained inactive; an interface constrained to a subset of the
legal protocol. Each is entirely reasonable when proving a property and wrong when proving
unreachability, because what gets removed here is removed from the number that ships. Read the
**Constraint set** slot for who owns each constraint, and name where each one is discharged —
a constraint nobody discharges is a hole with a proof in front of it.

This gate is narrow by design: it asks only whether the constraint set is a defensible basis for
deleting coverage items. The wider audit — whether the assumption set left the passing checks vacuous,
whether a counterexample is an environment artifact, and how much credit the run has earned — is
`dv-formal-overconstraint-credit`, and an unreachability candidate list heading for a milestone review
is usually worth taking through it as well as through this gate.

**Gate 3 — the person in the Formal sign-off slot has signed both the constraint set and the candidate
list.** If that slot is unfilled, stop and ask; do not fall back on the profile's general **Sign-off**
entry, which is about evidence for a milestone rather than about whether a constraint over-constrains.
The agent cannot make that judgement, and neither can a junior engineer in their second week — that is
the whole reason this gate exists rather than a warning in the notes.

**Unreachable is a finding before it is a waiver.** The most valuable row in an unreachability report
is usually one that *should* have been reachable: a parameter set wrong, a mode never brought up, a
feature enabled nowhere. Ask "should this be reachable?" of every candidate, and route the ones where
the answer is yes as design findings rather than as exclusions.

Record, beside each candidate, the RTL revision, the parameter set and which constraint files the run
read, keyed however the **Exclusion destination** slot says entries are keyed — and note what that slot
says invalidates an entry. The deliverable of this step is that candidate list plus the sign-off
request. This skill declares no Write tool, and that is deliberate: the exclusion file is written by a
person who signed for it.

### 7. Post-ECO equivalence — read the mapping before you read a single counterexample

Take the two models from the **ECO model pair** slot and read the report in this order. The order is
the whole value of the step; the counterexamples are last because three cheaper things explain most
of them.

1. **Unmapped points.** Count the state points the tool could not pair up. A renamed, added, removed
   or retimed register is unmapped, and an unmapped point is *unverified*, not equivalent. Zero
   non-equivalent points beside forty unmapped ones is a report that compared almost nothing.
2. **The intended difference.** An ECO is a deliberate change. Unless that intent reached the tool —
   as a constraint, a don't-care, or an expected-difference list — the intended change is reported as
   a non-equivalence, and someone spends an afternoon confirming the ECO did what it was for. The
   **ECO model pair** slot says where the intent is written down; read it before the report.
3. **The setup constraints.** Scan chains, test-mode muxing and clock gates inserted after the
   reference model make the two designs genuinely different unless the test pins are constrained
   inactive. That constraint is ordinary setup, not cheating — but it must be written down, because
   the same run then proves nothing about test mode.
4. **The counterexample, last.** Only now ask whether the difference sits in a don't-care: an unused
   output, an uninitialised value the reference leaves unknown and the implementation resolves to a
   constant, or a state the design cannot reach from reset.

What "sequential" buys over the cheaper comparison is state points that do not pair up one-to-one —
retiming, a changed pipeline depth, clock-gating insertion, FSM re-encoding. Where every register does
pair up, the combinational comparison is usually enough and much faster; which to use is the
specialist's call, not this procedure's.

And the sentence that belongs in every equivalence report: **it proves the two models match each
other, not that either is right.** An ECO implementing the wrong intent passes with a clean report.

### 8. Record the finding

Write the `where` field by the rules in `_shared/failure-signature-schema.md` for that field — the
most specific stable location, last two hierarchy levels — so a formal finding and a simulation
finding on the same block land on the same string. Do **not** synthesise a full
`phase|kind|where|what` signature from a formal report: that schema normalises a message printed by a
run, a report row is not one, and a manufactured signature matches nothing and pollutes the triage
table. If this bug already has a simulation failure, copy that failure's signature into `notes`
verbatim rather than deriving a second one.

```
app          : connectivity | register | unreachability | equivalence
tool         : <exact app name from the App inventory slot, and the version string the report prints>
proof status : proven | falsified | bounded | inconclusive | vacuous
checks       : <counts per proof status, and the number of checks the run was given>
where        : <hierarchy path, by the shared schema's rules for that field>
finding      : <one sentence, and the report line number it rests on>
origin       : reference | constraint | setup | design | undecided
class        : design | infrastructure | unknown
setup        : <constraint files the run actually read, and the RTL revision it compiled>
owner        : <the area owner from the profile map, or blank plus candidates>
sign-off     : <who must sign, from the Formal sign-off slot — mandatory for unreachability>
run id       : <whatever identifies this run for us>
log          : <report path, and the line range worth reading>
coverage     : <rows opened of rows in the report; constraint files read of files the run used>
notes        : <anything the next person would otherwise rediscover>
```

`class` uses the same three values the rest of the pack uses, so a formal finding routed into triage
keeps its vocabulary: `class: infrastructure` for a setup, licence or black-box problem, and
`class: design` only where a counterexample was traced to RTL. `app`, `proof status`, `origin` and
`sign-off` are local to this skill — the field is spelled `proof status` rather than `status` on
purpose, because several siblings already use a bare `status` for something else entirely and these
blocks are compared by field name. Leave a field blank rather than filling it plausibly.

## Gotchas

- **A green report is a claim about the constraint set, not about the design.** Over-constrain and
  everything proves in minutes. The first number to look at is not the proven count, it is the
  runtime — a block that simulates for hours and proves in ninety seconds usually has a hierarchy
  black-boxed or a mode pin held at one value.
- **A bounded proof is the status people misread most.** "Proven to depth 40" says nothing about cycle
  41. Record the depth next to the result or the result is unreadable a week later, and never let a
  bounded row satisfy a check that a full proof was asked for.
- **A vacuous check is a passing check that never ran.** Connectivity rows whose enabling condition
  the constraints make unsatisfiable pass this way in bulk, silently. Ask for the tool's vacuity or
  trigger report rather than reading the pass column.
- **The connectivity table is the specification, so a table typo is reported as an RTL bug.** Swapped
  direction, a bit range written the other way round, a mode condition nobody wrote down — prove the
  row before you file the bug.
- **A connectivity row whose source is tied off can pass with no path at all.** Both ends hold the
  same constant, the check is satisfied, and nothing was tested. Confirm the source can take both
  values under the run's constraints.
- **Formal and simulation disagree about unknown values.** A formal engine typically treats an
  uninitialised value as free and will find a sequence a two-state or optimistic simulation never
  produces. A formal-only failure on an uninitialised register is usually real, and usually about
  reset coverage rather than about the tool.
- **An unreachability result expires.** It is bound to an RTL revision, a parameter set and a
  constraint file, and most exclusion formats record none of the three. A line-keyed exclusion slides
  onto a different line after the next edit, so the item it now removes is not the item that was
  proved unreachable.
- **Dead code is a finding before it is a waiver.** Excluding an item that *should* have been
  reachable closes coverage on a feature nobody has verified — and it closes it quietly, because the
  number goes the right way.
- **Scan and test logic make two functionally identical designs non-equivalent.** Chains, test muxes
  and inserted clock gates are genuine differences. Constraining the test pins inactive is normal
  setup, but the run then proves nothing about test mode and the report must say so.
- **Sequential equivalence is most convincing exactly when it is least useful.** An ECO that
  implements the wrong intent passes with zero non-equivalent points. Checking intent is a human
  reading the ECO description against the change, and no app performs it.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every claim of "proven" is stated **with its constraint set** — the files the run actually read, not
  the ones in the repository
- no bounded, inconclusive or vacuous row is being counted as a pass, and the bounded depth is written
  down wherever a bounded row appears
- the five status counts add up to the number of checks the run was given
- for a connectivity or register failure, the reference row was cross-checked before the RTL was
  blamed, and `origin` says which of the two moved
- **no exclusion has been written**, and every unreachability candidate carries a named signer from
  the Formal sign-off slot, an RTL revision and a parameter set
- every unreachability candidate has been asked "should this be reachable?" and the ones where the
  answer is yes left the step as design findings
- for an equivalence result, the unmapped-point count is quoted before the non-equivalent-point count
- the `coverage` line is present with both its denominators

A wrong answer is a tidy table saying every connectivity path is proven, produced by a run with the
mode pin tied to one value; or an exclusion list generated straight from the "not covered" column,
carrying bounded and inconclusive rows into a coverage number nobody can now defend. The second one is
worse, because it looks like progress and is invisible until silicon.

## Done when

The report is read by status rather than by pass count, one origin is named with the line it rests on,
and anything heading for a coverage exclusion is a candidate list waiting on a signature — never a
file this procedure produced.
