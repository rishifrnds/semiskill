---
name: dv-isa-step-compare
description: Align a processor's retired-instruction trace against an instruction-set reference model, prove the comparison points and exclusions are trustworthy before believing any mismatch, then triage the first divergence to the RTL, to the model, or to the test. Use when a step-and-compare or lock-step co-simulation run reports a mismatch, when the reference model and the core disagree on a register or CSR value, when a trace comparison diverges and everything after the first line is noise, or when you need to decide whether a divergence is a real bug or an unmodelled interrupt, device load or performance counter.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Instruction-Set Reference-Model Step-and-Compare Verification
  semiskill-function: design-verification
  semiskill-role: processor-ip-dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-14
  semiskill-tags: processor, isa, reference-model, step-and-compare, co-simulation, trace, triage
---

# Instruction-Set Reference-Model Step-and-Compare Verification

A step-and-compare flow says a core is correct because an instruction-set model agreed with it
retirement by retirement. When the two disagree, the core is the least likely culprit: far more often
it is the alignment, the exclusion list, or something the model was never told — an interrupt taken
at a different boundary, a device load it cannot see, a counter that could never have matched. And
because architectural state is cumulative, everything after the first divergence is downstream of it,
so a comparison report with four thousand entries usually contains exactly one fact.

The output is **one classified divergence**, the two verbatim trace lines behind it, **one culprit** —
the RTL, the reference model, or the test and environment — and an honest line saying whether the
alignment was verified or assumed. Not a diff.

**What this does not do.** It reads trace files, comparison reports and configuration files already on
disk. It cannot start a simulation, step a model, produce a comparison, or open a waveform. Every step
needing one of those ends in a named handoff.

## When to use something else

If the run failed rather than diverged — it died, hung, or printed errors — start with
`dv-sim-log-first-error`; come here only once the failure is known to be a comparison mismatch. A
whole night of failures to sort belongs to `dv-regression-triage-routing`, and shrinking a divergence
you have already classified belongs to `dv-minimal-reproducer`. Once the shape is known, three
siblings go deeper than this one does: an unexpected trap or interrupt is `dv-trap-exception-triage`,
a control- and status-register field question is `dv-csr-warl-access-audit`, and a multi-hart ordering
surprise is `dv-memory-ordering-litmus` — a single-hart step-and-compare cannot adjudicate ordering at
all. If the disagreement turns out to be a question about the specification rather than about either
implementation, record it with `dv-spec-interpretation-ledger`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Reference model | [[FILL: which instruction-set model is our golden checker, its build or version, and the file that pins the extensions and options it was launched with]] | core DV owner |
| Trace format | [[FILL: what one line of our RTL retirement trace and of our model trace contains — which fields, in what order, and which field is the retire index]] | DV infra |
| Artifact locations | [[FILL: where one run's RTL trace, model trace and comparison report land]] | your mentor |
| Compare tool | [[FILL: which step compares the two traces, what it prints on a divergence, and where its report lands]] | DV infra |
| Exclusion list | [[FILL: which registers, counters and address ranges our comparison excludes, where that list lives, and whether it is a readable file]] | core DV owner |
| Injection points | [[FILL: how asynchronous interrupts and load values from ranges the model does not model are forced into the model, or whether they are not]] | DV infra |
| Compared region | [[FILL: which part of the run is compared — does it start at reset or at a marker, is boot code skipped, and how many harts are compared]] | core DV owner |
| Core configuration | [[FILL: the machine-readable configuration this core is built from, and whether the model is configured from that same file]] | core owner |
| ISA revision | [[FILL: which ratified specification revision and clause numbering this core targets]] | core architect |

**Log location**, **Run identity** and the **Area to owner map** are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than re-asking. Three rows above are
deliberately *not* the profile's rows and must not be filled from them:

- **Artifact locations** is not the profile's Log location. Traces and the comparison report are
  separate per-run artifacts, frequently written to a different directory from the simulation log, and
  frequently kept for fewer days.
- **Compare tool**'s divergence string is not the profile's Fatal markers. The comparison usually runs
  after the simulator has exited and prints strings of its own. Record both; never assume one is the
  other, and if you are unsure, ask.
- **Reference model** is not the profile's Simulator. The simulator runs the RTL; the model is a
  second program with its own version and its own configuration, and version skew between them is one
  of the three culprits step 8 has to choose between.

**If a slot is unfilled, stop and ask. Do not guess a convention.** A guessed trace column or a
guessed exclusion turns a correct core into a filed bug, which costs more than no answer.

## Retrieval budget — read this before opening anything

An instruction trace for a serious test is millions of lines, and there are two of them. Reading
either one whole is impossible; diffing them by eye through this tool set is not a plan. Work in this
order and stop as soon as one divergence is classified.

1. **Grep and Read work on files, not on chat text.** If a trace excerpt or a comparison report
   arrived pasted into the conversation, ask for the paths on disk. Until they exist you may reason
   over the pasted lines by eye — but say that is what you did, and mark every finding provisional.
2. **Never open a trace with Read first.** Glob to locate, Grep to convert a key into a line number,
   then Read a bounded window around that line.
3. The whole allowance: **one Glob** in step 1; **four Greps** — one in step 4 on the exclusion list,
   one in step 5 on the comparison report, and one per trace in step 6; and **six Read windows** — two
   of about 20 lines at the head of each trace in step 2, one of about 40 lines on the exclusion list
   in step 4, two of about 60 lines at the divergence in step 6, and one spare of about 40 lines in
   step 8 for whichever file settles the culprit.
4. If a Grep returns more than about 200 hits, the pattern is too broad — anchor it on the retire
   index or on a full instruction address before reading anything.
5. Stopping rule: once that allowance is spent with no settled culprit, stop. Report the shape of the
   divergence, the one fact still missing, and the coverage line from step 9. Past that point the
   answers get invented, and an invented reading of a trace column is indistinguishable from a real
   one.
6. State what was actually covered — how many divergences the report listed, how many were opened, and
   whether the alignment in step 3 was verified or assumed.

## Procedure

### 1. Resolve the run to artifacts, and decide which comparison produced this

One **Glob** under the Artifact locations slot for the four things this procedure needs: the RTL
retirement trace, the model trace, the comparison report, and the configuration the Reference model
was launched with. Do not open any of them yet.

What comes back decides the comparison mode, and the two modes are triaged differently:

- **Offline trace comparison** — both traces exist as files and a separate step compared them. The
  divergence lives in the comparison report, and because that step ran after the simulator exited, the
  signature's phase is `post`.
- **Online lock-step** — the model is stepped inside the simulation and the mismatch was printed by
  the simulator itself. There is often no model trace file at all. The evidence is in the simulation
  log, at the profile's Log location, and the phase is `run`.

If the Artifact locations slot points at a directory that no longer holds this run's traces, stop:
traces are usually the first thing a flow deletes. Ask the engineer to re-run with trace capture
enabled and to give you the new paths, rather than triaging a report whose traces are gone.

### 2. Prove both sides executed the same program before comparing anything

Two **Read** windows of about 20 lines, one at the head of each trace. Establish, in this order:

- the first retired address on each side, and whether it is the reset address or a later marker
- the memory image each side loaded, if the trace names or stamps it
- the model's version banner, and the configuration it reports being launched with
- where each trace *starts logging*, against the Compared region slot — one side beginning at reset
  while the other begins after boot code is a fixed offset, not a bug

If the two do not begin at the same instruction, nothing below is meaningful. A divergence at the
first compared index is an alignment failure until proven otherwise, and the fastest way to settle it
is to ask the engineer which image each side loaded and to compare those two answers, not the traces.

### 3. Fix the comparison point and the alignment key

The model is atomic and untimed; the RTL is pipelined, may commit several instructions in one cycle,
and has executed and discarded many more. Only one boundary is comparable.

- **Compare at architectural commit — retirement — never at fetch, issue or writeback.** A flushed or
  speculatively executed instruction has no architectural effect and must not appear in either trace.
  A trace that logs at issue will show instructions the model never sees.
- **Align on retire order, never on time.** The retire index from the Trace format slot is the key.
  Simulation time, cycle counts and model step counts are unrelated quantities; matching on any of
  them produces a divergence report that is pure noise.
- **One retirement is not always one line.** An instruction can change more than one architectural
  location — a paired load, a read-modify-write atomic, a trap entry that updates several status
  registers at once. If the format records a single destination per line, the rest of that
  instruction's effect is not being compared, and a bug inside it is invisible.
- **More than one hart means one comparison per hart.** A merged trace interleaves independent
  orders, so the retire index is ambiguous and every alignment is a coincidence.

Record the alignment key and where it came from — it goes in the report's `alignment` field. If the
Trace format slot is unfilled, stop here: a field's meaning cannot be inferred from its position, and
misreading one column is exactly how a correct core gets a bug filed against it.

### 4. Read the exclusion list before believing any mismatch

One **Grep** of the Exclusion list slot's file for the register or range named in the report, then one
**Read** window of about 40 lines around it. A comparison is only as trustworthy as what it agreed not
to compare, and these are the items that legitimately cannot agree:

- **free-running cycle and wall-time counters** — the model is untimed and can never match them
- **performance-event counters**, which count microarchitectural events the model does not have
- **the retired-instruction counter**, which *can* match, but only where both sides count the same
  events; trapped instructions and wait-for-interrupt instructions are where the two definitions part
- **externally driven status bits**, such as interrupt-pending, sampled at different moments
- **hart identity and any implementation-defined identification register**
- **anything sourced from hardware entropy**
- **device and memory-mapped ranges**, whose read data the model cannot predict

Then read the Injection points slot, because two of those are usually handled by injection rather than
exclusion: asynchronous interrupts, and load data returned from ranges the model does not model. If
either injection is absent, the matching divergences are expected noise and must be named as such
before any triage — not triaged and then explained away.

**An exclusion is also how a real bug hides.** A register excluded because it was noisy is a register
that ships unverified, and an excluded item and a correct one produce the identical output: nothing.
Record in step 9 which exclusions were actually in force for this run.

### 5. Take the first divergence and nothing else

One **Grep** of the comparison report for the Compare tool slot's divergence string — not the
profile's Fatal markers, which belong to the simulator and may be different strings entirely. Take the
**lowest** retire index, and note the report's total count; that total is the denominator of the
coverage line.

If the Compare tool slot is unfilled, stop and ask for the string. Grepping for a marker nobody was
asked to define is how a skill reports "no divergences" on a report full of them.

### 6. Open a bounded window on each side

One **Grep** per trace to turn the retire index or the diverging address into a line number, then one
**Read** window of about 60 lines per trace, starting about 40 retirements *before* the divergence.
Take five things from those windows:

- the diverging line, verbatim, from each trace, each with its line number
- the last retirement the two agreed on, and its address
- the control flow immediately before — the last branch, jump, load or trap in the window
- whether either side entered or returned from a trap inside the window
- whether the diverging address appears here for the first time or the thousandth; inside a loop, the
  interesting question is which iteration, and the answer is in the preceding window

### 7. Classify the shape of the divergence

One row applies. The shape decides what is worth opening next, and three of the six rows are settled
without opening anything further.

| `mismatch shape` | What the two lines look like | Check first | Usually means |
|---|---|---|---|
| `pc` | same index, different retired address | the last branch or trap in the window, then whether an interrupt was injected at this boundary | control flow diverged here; if every compared value agreed up to this line, the cause is *at* this instruction, not before it |
| `instruction-word` | same address, different encoding | step 2's image identity, before anything else | the two sides are not running the same bytes — image skew, memory initialisation, code modified at run time, or an instruction-cache coherence fault in the RTL |
| `register-value` | same address, same encoding, different destination value | the operand values in the preceding window, then the specification's definition of this instruction | the narrowest and most useful case: one side computed the wrong result, and which one is decidable from the ISA rules |
| `csr` | only a control or status register differs | whether this register is in the exclusion list, then whether the model shares the Core configuration | configuration skew or a missing exclusion far more often than a design fault |
| `trap` | one side took a trap the other did not, or a different one | whether the trap is synchronous or asynchronous | synchronous is a genuine disagreement about this instruction; asynchronous is nearly always injection alignment, not a design fault |
| `trace-length` | one trace ends first, everything before it agrees | the tail of the shorter trace, then the run's own log at the profile's Log location | one run stopped early — a hang, a timeout, a trap loop, or a trace file truncated when the writer was killed |

### 8. Name one culprit, with the evidence it requires

Three-way, and each has an evidence bar that must be cleared before it is written down. Spend the
budget's spare **Read** window here, on whichever single file settles it — the core configuration, the
exclusion list, or the model's launch options.

- **`culprit: rtl`** — the RTL's architectural result contradicts the specification and the model's
  result matches it. Quote the clause, by document name and clause number, from the ISA revision slot.
  If you cannot quote it, say so and mark the finding provisional; "the model says so" is not a reason
  the design owner has to accept.
- **`culprit: reference-model`** — the model contradicts the specification, or is not a model of this
  core. The tells are specific: the model's build predates the extension under test; its launch
  options disagree with the Core configuration slot; or the divergence sits in a field the
  specification leaves to the implementation, which the model has hard-coded one way.
- **`culprit: test-or-environment`** — nothing about the instruction is in dispute. The images
  differed, a device load was not injected, an interrupt was injected at the wrong boundary, an
  excluded item was compared anyway, the compared region started in the wrong place, or the test
  depends on memory nobody initialised.

Where the specification leaves the behaviour implementation-defined, unspecified or reserved,
**neither side is wrong**. That is not a fourth culprit — it is a specification question, and it
belongs in `dv-spec-interpretation-ledger` with the clause that leaves it open, not in a bug against
either implementation.

Route the finding on the design hierarchy the divergence names, through the profile's Area to owner
map — never on the test name. Test names follow the testbench; the divergence lives in whatever unit
retired the instruction.

### 9. Record the finding

Write the signature per `_shared/failure-signature-schema.md` — same field order, same normalisation
rules. `kind` is `scoreboard`: the reference model is the scoreboard for this run, and the schema has
no processor-specific kind, so inventing one would stop the signature matching anything.

```
signature   : <phase>|<kind>|<where>|<what>
compare mode: online lock-step | offline trace compare
alignment   : <the key the two traces were matched on, and the slot or file it came from>
first div   : <the lowest diverging index, and the verbatim line from each trace with its line number>
mismatch shape: pc | instruction-word | register-value | csr | trap | trace-length
culprit     : rtl | reference-model | test-or-environment
phase       : run | post
class       : design | infrastructure | unknown
owner       : <name from the area map, or blank plus candidates>
run id      : <whatever identifies this run for us>
excluded    : <the exclusions actually in force, and the file they were read from>
traces      : <both paths, and the line range worth reading in each>
coverage    : <divergences listed in the report; how many opened; alignment verified or assumed>
notes       : <anything the next person would otherwise have to rediscover>
```

`phase` is deliberately narrower here than in `dv-sim-log-first-error`, which accepts all five tokens:
a step-and-compare divergence can only be reported by the simulator during the run or by the
comparison step after it exited, so `compile`, `elab` and `finalise` are unreachable from this
procedure. `signature`, `class`, `owner`, `run id` and `notes` carry exactly the meanings their
siblings give them, so a divergence routed onward keeps its vocabulary.

Leave a field blank rather than filling it plausibly, and **state the coverage honestly** — "opened 1
of 4,113 listed divergences; alignment verified against the trace format" is a useful report, and an
unstated shortcut is far worse than a stated one.

## Gotchas

- **Every divergence after the first is downstream of the first.** Once one architectural value
  differs, every later instruction may read it. A report with four thousand entries and one with a
  single entry are routinely the same bug. Rank by index, never by count and never by which line looks
  worst.
- **Cycle counters and instruction counters are different animals.** An untimed model can never match
  a free-running cycle counter, and a retired-instruction counter matches only where both sides agree
  on what retires — whether a trapped instruction counts, and whether a wait-for-interrupt instruction
  counts, is exactly where two reasonable definitions part company.
- **Asynchronous interrupts are taken at whichever boundary the RTL chose.** The model has no timing
  and cannot pick the same one unaided; it has to be told which retirement. An interrupt injected one
  retirement late lands as a `pc` divergence at the handler entry and reads exactly like a
  branch-resolution bug in the core.
- **A load from a range the model does not model must be back-propagated.** The value the RTL read has
  to be forced into the model, because the model has nothing to read. Without that, every device
  access diverges, and the first one buries whatever real bug came after it.
- **Floating point diverges in the last bit for reasons that are not bugs** — the payload of a
  generated quiet NaN, the boxing of a narrower value inside a wider register, the rounding mode
  actually in force, and how each side handles subnormals. Compare the accumulated exception flags as
  carefully as the result: a correct value with wrong sticky flags is a real bug, and a value-only
  comparison misses it completely.
- **A write to the always-zero register is not a write.** Some formats log the destination the
  instruction encoded, others log the write that architecturally happened. Two formats that disagree
  about this diverge on every instruction targeting that register, and none of those is a bug.
- **Compressed and expanded encodings are the same instruction.** If one side logs the short encoding
  as it sat in memory and the other logs the expanded form it executed, every compressed instruction
  produces an `instruction-word` divergence. Fix the comparison, not the core.
- **An excluded item is not a verified item.** "The comparison passed" and "the comparison never ran"
  produce the identical output — nothing. Before signing anything off, read the exclusion list as a
  list of unverified state, because that is what it is.
- **The model's configuration is part of this core's specification.** A model launched with a
  different register width, a different extension set, a different count of protection or trigger
  entries, or different field legalisation is not a golden model of this core; it is a golden model of
  a different core, and it will be confidently wrong in exactly the places the two differ.
- **A self-checking test that passes does not overrule the comparison.** A test can reach its own pass
  marker for the wrong reasons — a signature that matches because two errors cancelled, or a checker
  that never sampled. If the test passed and the trace comparison diverged, the divergence is the
  stronger evidence.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- exactly **one** divergence was analysed, and its index is the lowest in the comparison report
- both diverging lines are quoted **verbatim**, one per trace, each with a line number
- the alignment key is named with its source; if alignment was assumed rather than verified, every
  field above the coverage line is provisional
- the exclusions in force are recorded, and nothing that step 4 lists as legitimately incomparable has
  been filed as a bug
- `culprit` names exactly one of the three — "could be either" means step 8 was not finished — and an
  `rtl` verdict cites the clause it contradicts by document and number
- an implementation-defined or unspecified behaviour has been routed as a specification question
  rather than filed against either side
- the coverage line gives the report's own total, not just the one divergence that was opened

A wrong answer typically classifies the loudest or the last entry in a long comparison report; blames
the RTL for a counter that could never have agreed; calls an interrupt-injection skew a
branch-prediction bug; reports "the model is wrong" without naming the clause it contradicts; or
quietly compares two traces that began at different instructions.

## Done when

You can name one divergence, its shape, one culprit with the evidence behind it, the person who owns
it, and how much of the comparison report that rests on.
