---
name: dv-formal-property-authoring
description: Turn a spec extract and an RTL interface into a reviewable formal property set — asserts, assumes and covers decomposed one obligation at a time, every assume justified against a named clause and paired with a cover proving it did not delete the behaviour. Use when you are writing SVA properties for a block for the first time, when a formal run proves everything on the first attempt and you suspect over-constraint, when a reviewer asks where an assumption came from, when covers went unreachable after you added a constraint, or when you need an assume register somebody can sign off. Reads source files and saved proof reports; it cannot start a formal engine.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Spec-to-Property Decomposition and Assertion Authoring Discipline
  semiskill-function: design-verification
  semiskill-role: formal-verification
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-06-17
  semiskill-tags: formal, sva, assertions, assumptions, cover, over-constraint, review
---

# Spec-to-Property Decomposition and Assertion Authoring Discipline

A property set that proves clean on its first attempt is more often over-constrained than correct.
The expensive failure is never an assert that fails — it is an assume nobody could justify, sitting
quietly under twenty asserts and making all of them true for free. What makes a set reviewable is
not its size but whether a second person can see, for every constraint, which sentence of the spec
put it there and which cover proves it did not delete the behaviour it was meant to leave alone.

The output is **a drafted property set, one record per property, and a set-level review record**
naming every unjustified assume. Not a wall of SystemVerilog.

**What this does not do.** It reads files and drafts property text. It cannot start a formal engine,
open a waveform, or check a proof, and it is read-only — the drafted text goes back to the engineer
to put in the file. Every step that needs an engine ends in a handoff to a named human.

## When to use something else

A whole spec chapter with no feature table yet is `dv-spec-feature-extract` — it produces the
clause-traceable rows this skill decomposes, and starting here instead means re-reading the chapter
badly. A normative sentence that needs a passive simulation-side checker in a VIP rather than a
formal property is `dv-protocol-checker-rule`; this skill deliberately reuses that skill's block
field names so a property and its simulation-side twin read side by side. Two readings of a clause
that both look legal is `dv-spec-interpretation-ledger` — resolve the ambiguity before writing a
property against a guess. An ECN or errata against a released revision is `dv-spec-ecn-delta`.
Deciding which reset and clock scenarios are worth proving at all is
`dv-reset-clock-scenario-matrix`.

If the property file will not compile or elaborate, that is a build break — hand it to
`dv-build-filelist-hygiene` with the first diagnostic line. If what you actually have is a failing
simulation rather than a proof, start at `dv-sim-log-first-error`.

**A proof that will not converge is a different job.** Abstraction, case splitting, black-boxing,
engine selection and helper lemmas belong to `dv-formal-convergence`; route a row that came back
`proof status: inconclusive` there rather than blaming the property set for a capacity problem.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Spec extract | [[FILL: where this block's spec extract lives, and whether it is a file Read can open or a document that has to be quoted into one first]] | block architect |
| RTL interface | [[FILL: the file holding this block's port list, and the interface or protocol package our properties bind against]] | RTL designer |
| Property file convention | [[FILL: where our property and bind files live, how they are named, and whether properties sit inside the RTL or in a separately bound module]] | formal owner |
| Clock and reset | [[FILL: this block's clock, its reset, whether that reset is asserted high or low, and how long the environment holds it]] | RTL designer |
| Property id convention | [[FILL: how we name a property so it traces back to a spec clause, and where that mapping is recorded]] | formal owner |
| Assume register | [[FILL: where our justified assumptions are recorded for review, and what each entry must carry]] | verification lead |
| Proof report | [[FILL: where the formal tool writes its per-property status and depth table, whether one file is kept per run or each run overwrites the last, and how two runs are told apart on disk]] | formal owner |
| Depth policy | [[FILL: what proof depth our sign-off accepts as a bounded pass on this block, and who may waive it]] | verification lead |
| Engine state model | [[FILL: whether our engine reasons in two-state or four-state, which decides whether an X check means anything]] | formal owner |

Three pack-wide facts are read from `_shared/team-profile.md` rather than re-asked here: **Sign-off**,
which step 8 needs; the **Area to owner map**, which step 5 uses to name the owner of a sibling
block's obligation; and **Run identity**, which step 7 uses to tell the two status reports it asks
for apart. **Proof report is narrower than the profile's Log location**: a formal run emits
a per-property status table, not a simulation log, and even when both land in the same directory the
file to read is the status table. The profile's **Fatal markers** and **Pass marker** are therefore
deliberately not repeated in the table above — nothing here Greps a log for a marker, and step 7
Greps the status table for the property-id prefix instead.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented reset polarity or an
invented property naming scheme produces a set that looks reviewable and proves nothing.

## Retrieval budget — read this before opening anything

RTL files run to thousands of lines, spec extracts to hundreds of clauses, and a proof report has a
row per property. Work in this order and stop as soon as the obligations are drafted:

1. **Grep and Read work on files on disk.** A spec extract pasted into the conversation can be
   reasoned over by eye, but it cannot be searched and its clause numbers cannot be checked against
   anything. Ask for it to be saved to a file and be given the path. Until then, say so — every
   spec ref in the output is then provisional.
2. **Glob twice, at the start**: once for the interface or port-list file from the RTL interface
   slot, once for any existing property and bind files under the Property file convention slot.
   Never open either with **Read** first.
3. **Five Greps, each named, and not one of them per-obligation.** One in step 2 for the module or
   interface declaration, to get the port-list line number. Two in step 5, both batched over the
   whole draft rather than repeated per assume — one over the spec-extract file alternating every
   clause reference the assumes cite, one in the existing property file for the `assume` keyword,
   which returns every constraint already in force at once. Two in step 7, one in each of the two
   status reports, for the property-id prefix; each returns every row of that run at once. Five is
   the whole ledger whether step 3 produced two obligations or twelve — if you are about to Grep
   once per assume or once per property, batch it into an alternation instead.
4. **Five bounded Reads.** About 80 lines at the port list (step 2), about 60 lines of the spec
   extract (step 3), about 40 lines of the existing property file for house style (step 6), and at
   most two 40-line windows across the two status reports, at rows that are not plain passes
   (step 7).
5. If a Grep returns more than about 150 hits the pattern is too broad — anchor it on a leading
   `input`, `output` or the property-id prefix before reading anything.
6. **Obligation cap.** If the extract yields more than about twelve atomic obligations, draft the
   first batch and record which clauses were not reached. Do not open a second spec document to
   complete the picture; that is `dv-spec-feature-extract`'s job, not this one's.
7. **Stopping rule.** If the signal inventory does not settle who drives a signal named in an
   obligation, stop and ask. Never infer a direction from a signal's name. Likewise if the budget is
   spent with obligations undrafted — report the coverage rather than drafting from memory. And if
   step 7 comes back with one status report instead of two, do not spend a third Grep hunting for
   the other: record the assume pairings as unjudged and say why.

## Procedure

### 1. Resolve both inputs to paths before writing a single property

**Glob** for the interface file and for any existing property or bind files, using the RTL interface
and Property file convention slots. If the spec extract exists only as text in the conversation,
resolve that now under budget rule 1: ask for it as a file, and if none is forthcoming, say plainly
that the clause references rest on a pasted fragment and mark the whole set provisional.

An existing property file matters more than it looks. If this block already has properties, some of
your obligations are already drafted and some assumes are already in force — step 5 and step 6 both
read it, and re-deriving a constraint that already exists is how two contradictory assumes end up in
one file.

### 2. Build the signal inventory — who drives what decides assert from assume

**Grep** the interface file for the module or interface declaration to get its line number, then
**Read** about 80 lines from there. Write down every signal the obligations will touch, and against
each one: **design-driven**, **environment-driven**, or **both**, plus the clock and the reset.

This is the single most load-bearing artifact in the procedure. The direction, not the signal's
name, decides whether a statement about it is an assert or an assume, and a signal driven from both
sides — a shared bus, a bidirectional, a handshake where each side owns one wire — has to be split
by phase before either directive can be written. If it cannot be split from the port list, stop and
ask the RTL designer; budget rule 7 exists for exactly this.

### 3. Split the extract into atomic obligations

**Read** about 60 lines of the spec extract around the clauses in scope. Turn the prose into
numbered obligations, one per line, each with four parts: **trigger**, **obligation**, **window**,
**exception**. Split rather than merge:

- **"and"** joining two obligations is two rows. One property that checks both fails for two
  reasons and tells the RTL designer neither.
- **"unless" / "except when"** is an exception, and belongs in the qualifiers, not folded into the
  antecedent as an extra term — a reviewer must be able to see the exception without parsing an
  expression.
- **"until"** carries an implicit liveness obligation. Write it out: the thing that must eventually
  happen is a separate row from the thing that must hold meanwhile.
- **"while"** is a duration, not an edge, and usually wants `throughout` rather than an implication.
- A sentence with no trigger at all is an invariant — a good, cheap property, and often the one
  worth writing first.

Keep the verbatim fragment beside each row. The record in step 8 quotes it, and a paraphrase is what
turns a spec disagreement into an argument about your wording.

### 4. Decide the directive for each obligation

| The obligation says | Directive | Why |
|---|---|---|
| the design must produce or maintain something | assert | its failure is a bug in this block |
| the environment must not do something to the block | assume | the block is entitled to it, and it needs a clause |
| a legal behaviour must remain reachable | cover | it is the only evidence the assumes left the behaviour alone |
| something must eventually happen | assert, with the bound taken from the spec's own timeout | unbounded liveness rarely settles, and an invented bound is a false failure |

Three hard rules sit on top of that table, and every one of them is decided by the step 2 inventory
rather than by judgement:

- **Never assume anything about a signal the design drives.** The engine will restrict the design's
  own output to satisfy it and every assert downstream passes for free. This is the single most
  common way a property set becomes worthless.
- **Never assert something only the environment drives.** That is a check on the testbench, and it
  will fail the moment somebody legitimately changes the stimulus.
- **A cover is not optional decoration.** Step 5 and step 7 both consume them; a set with no covers
  cannot be reviewed at all, because nothing distinguishes it from a set that constrains everything.

### 5. Justify every assume, and pair it with a cover

An assume with no justification is not a constraint, it is a hole in the proof. Exactly four
justifications are legal, and `justified by` in the record carries which one:

1. **spec-clause** — a clause, quoted verbatim, with the document, revision and clause reference in
   our citation form. Confirm each one says what you remember, but do it once for the whole draft:
   list the clause references of every spec-clause assume first, then **Grep** the spec-extract file
   a single time with all of them alternated into one pattern. That is the first of step 5's two
   Greps, and it stays one Grep whether the draft has two such assumes or ten.
2. **integration-fact** — something signed off about what this block is actually connected to. Name
   who signed it. "The integrator said so in a meeting" is not this.
3. **sibling-obligation** — the neighbouring block asserts it. This is assume-guarantee, and it is a
   debt: record the property that must exist on the other side and the owner from the profile's
   **Area to owner map**. A debt nobody wrote down is how two blocks each assume the other.
4. **proof-convenience** — a constraint that exists only to make something converge. Legal, but it
   must be marked, listed against the properties it serves, and carry a date it comes out.

Anything else — "the testbench never does that", "it would be silly", "the old file had it" — is
`justified by: none`, and every one of those is a review finding. Before adding any new assume,
**Grep** the existing property file once for the `assume` keyword — the second and last Grep of this
step. One pass returns every constraint already in force; match your draft's signal names against
that list by eye rather than Grepping again per signal. That is what catches the constraint already
in force somewhere else in a slightly different form, and doing it per signal is how a
twelve-obligation draft quietly spends twenty Greps.

**Then pair it, and do not judge the pairing here.** Every assume gets a cover of the behaviour it is
supposed to leave alone, and that cover can only be judged *after* the assume is in force — which
means it is judged in step 7, against two runs, not in this step. Write the pairing down now (the
assume, the cover it protects, and `unjudged` until step 7 returns), because the covers have to be
written at the same time as the assumes rather than added later when nobody remembers what the
constraint was for. A cover the baseline run hit and the constrained run cannot names the assume that
killed it; that comparison is the whole mechanism, and it is the reason step 7 asks for two reports
rather than one. Record each pairing in the Assume register slot's shape so the set can be reviewed
without re-reading the property file.

### 6. Draft the properties — the mechanics that actually bite

**Read** about 40 lines of the existing property file to match house style, then draft. The shape,
with the naming from the Property id convention slot and the clock and reset from the Clock and
reset slot:

```
   property p_<id>;
     @(<the clock from the slot>) disable iff (<the reset, at the polarity the slot states>)
       <antecedent> |=> <consequent>;
   endproperty
   a_<id> : assert property (p_<id>);
   c_<id> : cover  property (<the antecedent alone, so a vacuous pass cannot hide>);
```

Set the record's `window` from the clause's own wording, not from whichever operator you reached for
first — the shape follows the window, never the other way round:

| The clause says | window | The shape it wants |
|---|---|---|
| the response is visible in the same cycle the trigger is | same-cycle | overlapping implication |
| the response is visible in the cycle after the trigger | next-cycle | non-overlapping implication |
| within N cycles, with N stated by the spec | within-n | a bounded range on the consequent |
| eventually, with the spec's own timeout as the bound | bounded-eventually | a bounded range, never an unbounded one |

A clause that bounds nothing is not a fifth window value; it is a clause that needs
`dv-spec-interpretation-ledger` before it becomes a property.

The mechanics that produce most authoring bugs, in the order they produce them:

- **Overlapping versus non-overlapping implication.** They differ by exactly one cycle. Overlapping
  evaluates the consequent in the same cycle the antecedent completes; non-overlapping starts it the
  next cycle. A spec that says "in the following cycle" needs the non-overlapping form, and the
  wrong one produces a counterexample on the first legal transaction.
- **Bounded windows.** "Within N cycles" is a bounded range on the consequent. Take N from the spec,
  never from what the RTL happens to do — a bound copied off the design proves the design agrees
  with itself.
- **Unbounded ranges** turn a safety property into a liveness property. Safety says something bad
  never happens and can be refuted by a finite trace; liveness cannot, and bounded engines usually
  return an inconclusive result rather than a proof.
- **`$past` before enough cycles have elapsed is undefined**, and a formal engine will pick whichever
  value produces a counterexample. Guard it with a reset-released counter rather than trusting the
  engine to be kind.
- **`$stable` and `$changed` on a multi-bit signal apply to the whole vector**, which is rarely what
  a clause about one field means.
- **Edge versus level.** A clause about a request arriving wants `$rose`; a level check fires every
  cycle the level is high and buries the interesting failure in hundreds of identical ones.
- **X checks depend on the engine state model slot.** Under a two-state engine an X check is not
  meaningful, and writing one anyway produces a property that passes for the wrong reason.

### 7. Hand the set over to be proved — twice — then read both reports back

The agent cannot start an engine and must not invent what one would have printed. **Ask the engineer
to run our formal tool over this property set twice — once with the step 5 assumes in force and once
with them disabled — and to give you the path to each per-property status report.** The Proof report
slot says where those land; the profile's **Run identity** fact is what tells the two apart. The run
without the assumes is the baseline, and it is the only thing that turns "this cover is unreachable"
into "this assume made it unreachable".

If only one report comes back, carry on and say so. Every status below is still readable from it, but
every assume pairing stays unjudged, no row may be classified `points at: over-constraint`, and the
set-level `survives` line records the gap instead of claiming a survival nobody measured.

One **Grep** of each report for the property-id prefix returns every row of that run at once — the
fourth and fifth Greps in the budget, and the last. Classify each row into `proof status`, using the
spellings `_shared/handoff-vocabulary.md` registers, then spend at most two 40-line **Read** windows
across both reports on the rows that are not plain passes:

- `proof status: proven` — an unbounded proof. Record it and move on.
- `proof status: bounded` — holds to some depth only. Put that depth in the record and compare it
  against the Depth policy slot. A depth-20 pass on a property whose antecedent first becomes
  satisfiable at cycle 34 has proved nothing, and it is indistinguishable from a real proof in a
  summary table.
- `proof status: falsified` — a counterexample trace exists. The one question is whether the trace is
  legal. If it does something the environment genuinely cannot do, the missing piece is a *justified*
  assume — go back to step 5 and justify it. Never delete the assert to make the trace go away.
- `proof status: vacuous` — the antecedent was never satisfiable, so nothing was checked. What a tool
  reports as vacuity, and whether that reporting is on by default, is a tool fact — ask rather than
  assume, which is why step 6 writes the antecedent cover by hand.
- `proof status: inconclusive` — the engine did not settle. That is a convergence problem and it
  belongs to `dv-formal-convergence`; route it rather than weakening the property.
- `proof status: not-read` — the row was not in the report at all, or the two Read windows ran out
  before reaching it. It is a reading status, not an engine outcome: keep it out of the `proven` and
  `falsified` counts rather than scoring it as a failure to prove.

**Covers wear the same six words, and the mapping is not obvious, so write it down once.** A cover the
engine hit is `proven` — the reachability claim has a witness trace. A cover the engine showed can
never be hit is `falsified` — the claim is refuted, and that refutation is the finding. A cover simply
not hit inside the depth is `bounded` with that depth recorded, which is evidence of nothing except
that the engine did not look far enough.

**Then say what each row points at.** `proof status` is what the engine concluded; `points at` is
whose problem that is, and it is the field the review routes on. It comes from the row plus the
baseline comparison, never from a hunch:

| The row | What you check before setting it | points at |
|---|---|---|
| `falsified` assert, trace is stimulus the environment can legally produce | nothing — the trace is the evidence | design |
| `falsified` assert, trace does something the environment cannot do | which justified assume is missing | under-constraint |
| `vacuous`, or an antecedent cover the baseline run could not hit either | that no assume constrains the antecedent's signals | property |
| `falsified` cover that the baseline run hit | which assume went in between the two runs | over-constraint |
| `falsified` cover the baseline run could not hit either, and the spec says the behaviour is legal | the clause, quoted | design |
| `falsified` cover the baseline run could not hit either, and the spec does not settle whether it is legal | the clause, quoted | spec-gap |
| `inconclusive`, or `bounded` short of the Depth policy slot's number | nothing — not settling is the point | undecided |
| `proven`, `bounded` at or past that number, or `not-read` | nothing | leave it empty — no finding to route |

`points at: under-constraint` and `points at: over-constraint` pull in opposite directions and are the
two that matter: the first says the set admits behaviour the real environment cannot produce, the
second says it has already deleted behaviour it can. A set carrying several of each is not half right
— its assumes were not derived from one source, and *that* is the review finding.

Then set `class` for the run as a whole — a formal run that died on a licence or a missing file is
`class: infrastructure` and belongs to nobody in this procedure.

### 8. Emit the review record

One record per property. The field names `spec ref`, `antecedent`, `obligation`, `window`,
`qualifiers` and `witness` are taken from `dv-protocol-checker-rule` on purpose, so a formal property
and its simulation-side checker rule can be compared line for line. `proof status` is the pack-wide
registered field from `_shared/handoff-vocabulary.md` and carries its full canonical set, so a row
from here drops into the same column as one from `dv-formal-apps` or
`dv-formal-overconstraint-credit` without anybody translating spellings.

```
property    : <the id, from the Property id convention slot>
directive   : assert | assume | cover
spec ref    : <document name, revision and clause, in our citation form>
obligation  : <what must hold, in one sentence, once the antecedent holds>
antecedent  : <the trigger, and the sampling event it is checked on>
window      : same-cycle | next-cycle | within-n | bounded-eventually
qualifiers  : <the reset, enable and mode conditions this property is disabled under>
signals     : <every signal named, and who drives each, from the step 2 inventory>
justified by: spec-clause | integration-fact | sibling-obligation | proof-convenience | none
witness     : <the cover that keeps this honest, whether it was hit, and whether the baseline hit it>
proof status: proven | falsified | bounded | inconclusive | vacuous | not-read
depth       : <the depth the report gave for a bounded row, empty otherwise>
points at   : design | property | over-constraint | under-constraint | spec-gap | undecided
class       : design | infrastructure | unknown
owner       : <who the finding goes to, from the profile's area-to-owner map>
notes       : <anything the reviewer would otherwise have to reconstruct>
```

Then one set-level record, which is what actually goes to the person named in the profile's
**Sign-off** row:

```
property set: <block, the spec revision drafted against, and the file this belongs in>
drafted     : <n asserts, m assumes, k covers, from c clauses>
unjustified : <every assume with justified by none — this count is the review's headline>
obligations : <every sibling-obligation assume, with the property owed and its owner>
antecedents : <how many implication asserts carry an antecedent cover, out of how many>
survives    : <how many assumes carry a paired cover; how many of those covers the baseline run hit;
               and how many were still reachable with the assume in force — or "unjudged: one report
               only" when the second run in step 7 did not come back>
not drafted : <obligations from the extract deliberately left out, and why>
coverage    : <n of m obligations drafted; which clauses were read; and whether the extract was a
               file that was searched or text pasted into the conversation, in which case every
               spec ref above is provisional>
```

**State the coverage honestly.** Five bounded Reads will not decompose a forty-clause chapter:
"drafted 9 of 31 obligations, clauses 4.2 to 4.5; the rest unopened" is a useful record, and an
unstated shortcut is far worse than a stated one.

## Gotchas

- **An assume on a signal the design drives is not a constraint, it is a lobotomy.** The engine
  restricts the design's own output until the assume holds, and every assert behind it passes for
  free. The port list is the arbiter of direction, never the signal's name.
- **The wrong reset polarity in `disable iff` silently disables the entire set.** If the reset is
  active low and the property disables on the raw signal, everything is disabled whenever the block
  is out of reset: every assert passes and every cover is unreachable. All-covers-unreachable is the
  tell, and a set that passes completely on the first attempt earns this check before it earns a
  celebration.
- **A pass on an implication whose antecedent never happens is not a pass.** This is why every
  implication assert gets an antecedent cover you wrote yourself: a tool's vacuity report is
  tool-specific, often off by default, and usually only catches the trivial case — and a cover that
  goes unreachable when an assume goes in names the assume, which no vacuity report does.
- **A cover the baseline run could not hit either is a finding about the design or the spec, not
  about your assume.** That is the entire reason step 7 asks for two runs: with one report,
  `points at: over-constraint` and `points at: design` are indistinguishable, and the cheap wrong
  move is to add an assume until the cover stops complaining — which converts a real discovery into
  a hidden one.
- **`restrict` is an assume wearing a formal-only badge.** It constrains the search exactly as an
  assume does and needs exactly the same justification and the same paired cover — record it as
  `directive: assume` and name the keyword in the notes. Its one real difference is that it does not
  become a checker when the same file is compiled into a simulation.
- **An assume copied from another block's property file arrives with that block's environment
  attached.** Reuse the text if it saves typing, but re-derive the justification: a constraint that
  was true on one side of an arbiter is routinely false on the other.
- **A concurrent assertion samples in the preponed region** — it sees the value each signal held just
  before the clock edge. A property comparing an output against a combinational input computed in the
  same cycle is comparing against the previous value, and the resulting counterexample looks like an
  off-by-one in the design.
- **Unbounded ranges in an antecedent start a separate evaluation thread per match.** For an assert
  that is usually intended. For a cover it multiplies the witnesses and the first one the tool shows
  is often the least informative; `first_match` around the antecedent bounds it.
- **A bounded pass and a proof look identical in a summary table.** Carry the depth in the record
  beside the result, every time, or the first person to build a dashboard will report both as green.

## Human verification — what a wrong answer looks like

Before the set goes to review, check:

- **no assume constrains a signal the step 2 inventory marks design-driven** — check this before
  anything else, because it invalidates every result behind it
- every assume carries one of the four justifications, and a `sibling-obligation` names both the
  property owed and its owner
- every assume has a paired cover, and that cover was judged against **both** step 7 runs — or the
  record says the pairing is unjudged because only one report came back
- every implication assert has an antecedent cover
- every `bounded` row carries its depth, and that depth was compared against the Depth policy slot
- `points at` was taken from the step 7 table rather than from an opinion — in particular, no row is
  marked `points at: design` on a counterexample whose legality nobody checked, and none is marked
  `points at: over-constraint` without a baseline run that hit the cover
- every spec ref resolves to text somebody can open — and if the extract was only ever pasted into
  the conversation, the whole set is marked provisional
- the coverage line gives both numbers: obligations drafted, out of obligations the extract contains

A wrong answer typically has more assumes than asserts; or reproduces a spec sentence verbatim as one
fat property that can fail for four different reasons; or reports a clean proof of a set whose covers
are all unreachable, which is not a verified block but a disconnected one.

## Done when

A reviewer can take any single assume in the set, name the clause behind it and the cover that proves
it left the behaviour alone, without asking you anything.
