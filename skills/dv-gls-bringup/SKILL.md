---
name: dv-gls-bringup
description: Bring gate-level simulation up on a synthesised or post-layout netlist in staged rungs, then classify every timing-check violation and every X into one owner. Use when GLS is being stood up for the first time this project, when a netlist run fails in ways the RTL run never did, when the design goes all X after reset in gates but not in RTL, when the simulator reports thousands of setup, hold, recovery or removal violations, or when a GLS run passes suspiciously fast and you suspect the SDF never annotated.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Gate-Level Simulation Bring-Up and Timing-Violation Triage
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-08-12
  semiskill-tags: gls, gate-level, sdf, timing-checks, x-propagation, netlist, bring-up
---

# Gate-Level Simulation Bring-Up and Timing-Violation Triage

Gate-level simulation happens once or twice a project, always late, and always to someone who last
did it two projects ago. It fails in ways RTL simulation structurally cannot: the design goes all X
because a pin absent from the RTL was never tied off, a timing check fires ten thousand times at
reset deassertion, or — worst — it passes in RTL time because the SDF never annotated and nobody
looked. The output is **a rung, a symptom, a classified population of violations with a denominator,
and one owner per surviving bucket** — not "GLS is up", and not a wall of violation lines.

## When to use something else

- **A GLS log whose first error you have not found** — `dv-sim-log-first-error` first; it is cheaper
  and produces the signature this report reuses. Come here once the failure is known to be gates.
- **A netlist that will not compile or elaborate** — `dv-build-filelist-hygiene`, with
  `phase: compile` or `phase: elab`. **A night of failures** — `dv-regression-triage-routing`.
- **Shrinking one GLS failure** — `dv-minimal-reproducer`, with a caveat it cannot know: its
  hierarchy axis usually does not exist here, because a lower tier has no netlist.
- **A register access that mismatches** — `dv-ral-bringup`; a back-door path into a netlist is a
  different problem from a wrong register model, and it handles both doors.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Netlist and SDF set | [[FILL: the paths of the netlist and of each SDF for this block, which is post-synthesis and which post-layout, and which corner each SDF holds]] | physical-design owner |
| Annotation evidence | [[FILL: where the SDF annotation report lands, and the strings our simulator prints when it starts annotating and when a construct in the SDF matches nothing in the netlist]] | DV infra owner |
| Timescale and units | [[FILL: the time precision our GLS build compiles with, and the time unit the SDF header declares]] | DV infra owner |
| Test-mode tie-offs | [[FILL: which netlist pins must be held at which value for a functional GLS run — scan enable, test mode, bypass, memory margin — and where the testbench drives them]] | DFT owner |
| State initialisation | [[FILL: how our flow initialises netlist state before the first clock edge — a memory preload, a force list, an init sequence — or that it does not]] | DV infra owner |
| Violation marker | [[FILL: the exact string our simulator prints for one timing-check violation, and which fields that line carries and in what order]] | DV infra owner |
| Timing exceptions | [[FILL: where our multicycle paths, false paths, asynchronous crossings and clock groups are recorded, and how each entry names its two endpoints]] | timing or STA owner |
| Netlist naming | [[FILL: the standard-cell library this netlist uses, what its sequential and combinational cells call their output pins, and how RTL hierarchy names and bus bits are spelled after synthesis]] | synthesis owner |
| GLS scope | [[FILL: which tests are the agreed GLS set, the wall-clock runtime we accept for one of them, and what counts as GLS complete for this block]] | verification lead |

Six pack-wide facts are deliberately **not** repeated above and come from `_shared/team-profile.md`:
**Log location**, **Pass marker**, **Fatal markers**, **Run identity**, **Area to owner map** and
**Simulator**. The last is load-bearing — annotation strings and violation-line layout differ by
vendor — and **Annotation evidence** has no counterpart in the profile at all. **Violation marker is
narrower than Fatal markers, and is usually a different string at a different severity**: most
simulators print a timing-check violation at warning severity, so a run can print thousands and still
reach the end and print the **Pass marker**. Treat the two as one fact and step 5 searches for a
string the log never contains while step 2 reads a warning-free log as healthy. **If a slot is
unfilled, stop and ask** — an invented tie-off pin name or corner assignment answers confidently
about the wrong netlist, and whoever unpicks it is the timing owner two weeks before tape-out.

## Retrieval budget — read this before opening anything

A post-layout netlist is millions of lines and its SDF is larger; a GLS log carries one line per
violation and can outgrow both. The caps for one pass are **4 Glob, 14 Grep and 8 windowed Read**
calls, and no step may borrow from a later one.

1. **Grep, Read and Glob work on files on disk.** If the violation lines or the netlist arrived
   pasted into the chat, ask for the path they came from, or for that text to be saved to a file and
   be given the path. Until a path exists you may read the pasted lines by eye — say that is what you
   did, and mark every finding provisional.
2. **Never open a netlist, an SDF or a GLS log with Read first.** Grep fixes a line number; Read
   opens a bounded window around it.
3. Allocation: step 1 up to **3 Glob**; step 2 **1 Grep**, **2 Read** (a 60-line log window, a
   20-line SDF header); step 3 **1 Glob**, **2 Grep**, **1 Read** of 60 lines; step 4 **6 Grep**, one
   per trace hop, and **2 Read** of 40 lines; step 5 **4 Grep**, **2 Read** of 80 lines; step 6
   **1 Grep**. Step 7 opens nothing. That is 4, 14 and 7, leaving one spare Read.
4. **Anchor every netlist Grep.** `n123` is a substring of `n1234`, and an unanchored short name
   returns tens of thousands of hits. Match the connection syntax around the name, or a word
   boundary, and escape brackets and backslashes (Gotchas) or the pattern matches the wrong thing.
5. **On the violation Grep a large hit count is the finding, not an error.** Elsewhere in this pack
   over ~200 hits means the pattern is too broad; here it means the design produced a flood, which
   step 5 exists to bucket. But **a result that hit your runtime's limit is not a count** — record it
   as "at least N, truncated" and never write a truncated number into the report as a measurement.
6. **Stopping rule, then state what you covered.** Stop when the rung and symptom are named,
   annotation is proved or disproved, and either one X is traced to a driver or the population is
   bucketed with a denominator. A netlist is the easiest artifact in DV to invent about, because
   nobody can read enough of it to catch you — so every count in the report carries a denominator.

## Procedure

### 1. Fix what is being simulated, and name the rung

**Glob** the paths in the **Netlist and SDF set** slot to confirm each file exists and record its
real path — up to three calls, one per artifact. Do not open them. Then name the rung; every later
step means something different on each, and most bad GLS reports are one rung's result written up as
if it came from another.

1. **`rung: zero-delay`** — no SDF, checks off. Proves the netlist elaborates, the testbench connects
   and the test runs at all; proves nothing about timing.
2. **`rung: annotated-no-checks`** — SDF annotated, checks off. Proves annotation landed and the
   design still functions with real delays.
3. **`rung: annotated-checks`** — annotated, checks and notifiers on. Triage and X floods live here.
4. **`rung: min-corner`** — the fast SDF, for hold. Setup is a slow-corner question and hold a
   fast-corner one, so a block signed off on one corner has tested half of what it claims.

Confirm the test is one of the agreed set **GLS scope** names, and take the log path from the
profile's **Log location**. The agent cannot start a simulation, elaborate a netlist or open a
waveform: **ask the engineer to run the agreed GLS test at the rung you name, to give you the path
the log went to, and to say how long it took** — that last number means nothing except against the
accepted runtime the same slot records, which is why the slot asks for both.

### 2. Prove the SDF annotated, before believing any other result

The highest-value step here, and the one most often skipped. The cheapest tell costs no budget: a run
that finished in a small fraction of **GLS scope**'s accepted runtime did not simulate delays. That
is a prompt to check, never a conclusion. **One Grep** on the log — or on the report the **Annotation
evidence** slot names — alternating the annotation-start string, the unmatched-construct string and
the SDF's own base name; then **one Read** of ~60 lines at the first hit. Three outcomes:

- **No annotation string at all.** The task never ran, or ran at a scope that does not exist. This
  run is `rung: zero-delay` whatever anyone intended, and every timing conclusion from it is void.
- **Annotation started, many unmatched constructs.** SDF hierarchy prefix and netlist instance
  hierarchy disagree, usually by a wrapper level present in one and not the other. Report the count;
  most simulators only warn, so the run continued with those cells at zero delay.
- **Annotation started, unmatched count zero or small.** Proceed.

The first two are what step 7 records as `symptom: annotation-failed`. Then check **Timescale and
units** with **one Read** of the SDF's first 20 lines, where the header declares its time unit. If
the compile precision is coarser than the smallest delay in the file, those delays round to zero and
the run is a slow zero-delay simulation wearing an SDF's clothes. The header's unit and the compile
precision are separate numbers; quote both.

### 3. Make the netlist start — the connectivity rung

What breaks on `rung: zero-delay` is connectivity and initialisation, never timing. In order, each
masking the ones below it:

- **Pins the RTL never had.** **One Grep** for the netlist's top module declaration, **one Read** of
  ~60 lines over its port list, compared against **Test-mode tie-offs**. Scan enable, test mode,
  bypass and margin pins are absent from the RTL top, so a testbench ported from RTL leaves them
  unconnected — and an unconnected input port is high impedance, which the first gate downstream
  resolves to X. One floating scan enable puts every flop's D at X on the first edge.
- **Hierarchical references that stopped resolving.** Forces, binds, probes and coverage samplers
  aimed at RTL paths do not survive synthesis. **One Grep**, anchored, for the RTL name in the
  netlist, read against **Netlist naming** — flattening, renaming and bit-blasting all change the
  string. A **Glob** of the name-map file, if that slot says one exists, is the pass's last Glob.
- **State that nothing initialises.** Consult **State initialisation**. Memories and hard macros
  start X and stay X until written; a behavioural RAM in RTL often had a preload the compiled macro
  does not. Flops without an asynchronous reset stay X until first clocked with a known D, and in
  gates there is no `initial` block to rescue them.

Do not advance a rung until this one reaches the profile's **Pass marker**. A run that never reaches
it — stopping during elaboration, or blackening before any checker samples anything — is
`symptom: did-not-start`, and no conclusion from steps 4 to 6 is meaningful until that is fixed.

### 4. Trace one X back to its driver, in at most six hops

An X at a checker has a specific source, and in a structural netlist that source is reachable by
**Grep** alone. One hop is one Grep; the budget allows six. Grep the netlist for the X-carrying net's
name, anchored inside a connection. Every net has many hits and one matters: the instance where the
net sits on an **output** pin — which pin names those are is the **Netlist naming** slot, and it is
library-specific. That instance is the driver; take its inputs and repeat. Two **Read** windows of
~40 lines cover instances whose connections the Grep output truncates. Stop at the first of these,
and say which:

- **A sequential cell.** Ask why that flop is X — three answers, and *when* the X appeared separates
  them: never initialised (step 3) if X from time zero and never cleared; D was X at the edge (keep
  tracing D); or its notifier fired on a violated check (step 5) if the X began at a specific time.
- **A primary input or a pin on the tie-off list.** The problem is the testbench, not the design.
- **Six hops spent.** Report the chain, name the net you stopped on, hand it over.

If the X you started from is one a checker, a scoreboard or an end-of-test comparison actually saw,
this run is `symptom: x-at-check` whichever of the three endings the trace reached. **Why this is
worth doing:** RTL is X-optimistic and gates are not. An `if` on an X select takes the else branch in
RTL and a `case` on an X selector falls to its default; the synthesised multiplexer propagates X
through both. An X appearing only in gates is usually a genuine initialisation hole RTL simulation
was structurally unable to show you. That is the main thing GLS is for.

### 5. Read the violation report as a population, not as lines

**One Grep** for the **Violation marker** gives the population size, subject to budget rule 5 on
truncation. Bucket it with at most **three further Greps**, narrowing on the fields the slot says the
line carries. The three that pay: **check type** — `$setup` and `$hold` are data-path checks,
`$recrem` is asynchronous reset against a clock edge, `$width` and `$period` are pulse-shape checks
on a clock or reset, and they have different owners; **simulated time window** — everything before
reset deassertion, and before the clock is declared stable, is a different class from everything
after; **instance prefix** — a thousand violations under one hierarchy prefix is one problem, a
thousand spread evenly is a clock or a corner problem. Spend the **two Read** windows of ~80 lines on
the *earliest* violation in the largest bucket, never the last one printed. Record its simulated time
and whether reset was still asserted then — that pair is the report's `window` field, and it decides
step 6.

A violation line is not itself a failure. It reports that a check was violated; what turns it into an
X is the notifier, and whether the library wires one is a property of the cell, not of the simulator.
"Violations but no X" and "X but no violation" are both ordinary and mean different things — the
first is what step 7 records as `symptom: timing-violation`, and where step 4 also traced an X into a
checker, `x-at-check` wins, because the X is what the design was actually judged on.

### 6. Filter against the exceptions, then route each survivor to one owner

**Gate-level simulation has never heard of a timing constraint.** The simulator compares observed
edge separation against the library limit and knows nothing about multicycle paths, false paths,
clock groups or asynchronous boundaries — each of which static timing analysis waives by a constraint
the netlist does not carry. A violation on a path the timing owner signed off is expected output, not
a contradiction, and arguing it before checking costs a day. **One Grep** of the file named in
**Timing exceptions** for the failing endpoint, keyed as that slot says entries are keyed, then
classify each bucket into the report's `exception` field:

- **`exception: sta-waived`** — the endpoint pair is in the list. Expected. Not a bug.
- **`exception: synchroniser`** — the destination is a clock-domain synchroniser's first stage, which
  exists precisely because that flop may go metastable. It violates by construction on every
  asynchronous edge, for ever. Teams disable checks on those instances; nobody fixes them.
- **`exception: testbench-driven`** — driven by the testbench at, or too near, the active clock edge.
  Harmless in RTL; at the netlist's real input delays it is a hold violation on every transfer. A
  testbench fix, and the most common real finding of a first bring-up.
- **`exception: none-found`** — survives the filter, and gets an owner below.
- **`exception: not-checked`** — the slot is unfilled or names something Read and Grep cannot open. A
  tracker makes this a handoff: put the endpoint pairs in the report and ask the timing owner to
  compare them. Do not call anything real without having checked.

Route survivors on the failing endpoint's hierarchy through the profile's **Area to owner map**,
never on the test name: **timing or PD** for a real setup or hold violation at the SDF's corner, a
clock-tree or interconnect problem, a path no exception covers; **RTL** for an initialisation hole, a
reset-less flop feeding a checker, a step 4 X source no tie-off explains; **DV testbench** for
tie-offs, hierarchical references, stimulus at the clock edge, asynchronous reset release, missing
preload; **library or IP release** for a cell whose checks or notifiers behave unlike its siblings, a
macro with no timing model, an SDF from a release that does not match the netlist revision. Two
owners on one bucket means this step is unfinished — say what would split them.

### 7. Classify the symptom, then report

Assign `symptom` from the outcomes above — **the first that applies**, in this order, so that two
engineers writing up the same run reach for the same token:

1. **`symptom: did-not-start`** — step 3: the run never reached the **Pass marker**. Nothing below
   was observable, so nothing below may be claimed.
2. **`symptom: annotation-failed`** — step 2: no annotation string at all, or an unmatched-construct
   count large enough that the cells in question ran at zero delay.
3. **`symptom: x-at-check`** — step 4: an X reached a checker, and the trace names a driver instance
   or the nets it stopped between.
4. **`symptom: timing-violation`** — step 5: a violation population with a denominator, and step 4
   found no X at a checker.
5. **`symptom: rtl-passes-gates-fail`** — none of the four: the run started, annotation is *proved*,
   no X reached a checker, and every bucket left step 6 filtered out, yet the same test that passes
   on RTL fails in gates. A functional gates-only mismatch — synthesis, a library model, or a
   testbench timing assumption RTL was too loose to expose. Rarest and most expensive, and explicitly
   not `annotation-failed`: you only reach it by having proved annotation first.

Write the signature with `_shared/failure-signature-schema.md` — same field order, same normalisation
rules — then fill in this block. `signature`, `first err`, `phase`, `class`, `run id`, `log`,
`coverage` and `notes` are the field names `dv-sim-log-first-error` emits, so a GLS failure routed
from there keeps its vocabulary; `rung`, `symptom`, `window`, `exception` and `netlist` are local.
`phase` is `run` for nearly everything here; a netlist that will not build is `compile` or `elab` and
belongs to the sibling above, an end-of-run drain or final-state check that only fails in gates is
`finalise`, and a violation summary a later step writes after the simulator exits is `post`. `class`
is `design` for a netlist or RTL defect, `infrastructure` for a tie-off, hierarchical-reference,
build, SDF-release or library-model problem, and `unknown` where step 6 could not decide.

```
signature : <phase>|<kind>|<where>|<what>, per the shared schema
rung      : zero-delay | annotated-no-checks | annotated-checks | min-corner
symptom   : x-at-check | timing-violation | rtl-passes-gates-fail | annotation-failed | did-not-start
first err : <verbatim first fatal or first violation line, with line number>
phase     : compile | elab | run | finalise | post
class     : design | infrastructure | unknown
window    : <simulated time of the earliest violation, and whether reset was still asserted then>
exception : sta-waived | synchroniser | testbench-driven | none-found | not-checked
owner     : <timing or PD | RTL | DV testbench | library or IP release>
netlist   : <netlist path and revision; SDF path, corner and unmatched-construct count; or "not annotated">
run id    : <whatever identifies this run for us>
log       : <path, and the line range worth reading>
coverage  : <violations classified of violations reported; hops traced of hops needed; truncation stated>
notes     : <anything the next person would otherwise have to rediscover>
```

Leave a field empty rather than filling it plausibly. `netlist` carrying "not annotated" beside
`rung: zero-delay` and `symptom: annotation-failed` is a complete, useful, honest report; the same
run written up as `rung: annotated-checks` is the most expensive wrong answer this skill can produce.

## Gotchas

- **An SDF that did not annotate produces a fast, clean, meaningless pass.** Most simulators warn
  rather than error when an SDF construct matches nothing in the netlist, and a run carrying
  thousands of those warnings still prints the pass marker. Check the annotation report before the
  result, every time. The same silence hides a timescale problem: if the compile's precision is
  coarser than the smallest delay in the SDF those delays become zero and nothing says so, so a
  design annotated in picoseconds compiled at nanosecond precision is a zero-delay run with an SDF
  beside it.
- **The violation does not inject the X — the notifier does.** A `$setuphold` or `$recrem` declared
  with a notifier argument toggles that net when violated, and the cell's sequential primitive drives
  its output X in response. A library whose cells declare checks without notifiers reports every
  violation and carries correct data through regardless. Know which yours does before calling a
  violation harmless.
- **Unconnected is not zero.** An input port left unconnected is high impedance, and the first gate
  downstream turns that into X. One missed scan-enable tie-off blackens an entire netlist while the
  RTL testbench it was copied from stays perfectly healthy.
- **Reset deassertion is the first flood and most of it is the testbench.** Recovery and removal
  checks fire on every flop whose asynchronous reset releases near an active clock edge. If the
  testbench releases reset asynchronously that is a testbench fix, and the flood disappears entirely.
  Do not bucket it as a design problem until reset release has been moved.
- **Synchroniser first stages violate for ever, by design.** A two-flop synchroniser is built on the
  premise that its first flop may go metastable. GLS reports that on every asynchronous edge, and a
  wired notifier injects an X the second stage forwards into the design. This is the largest single
  source of "the netlist is broken" reports that are not.
- **Gate-level X-pessimism runs the other way too.** A multiplexer whose two data inputs are equal
  returns that value in RTL even with an X select, because the language merges agreeing bits; built
  from gates it returns X. Not every gates-only X is a design hole — the tell is that both branches
  carry the same value. A related trap prints nothing at all: path pulse control turns a glitch
  shorter than the path delay into nothing, or into an X, depending on the reject and error limits in
  force, so a reset or clock that looked clean in RTL can vanish or blacken in gates with no
  violation anywhere.
- **The corner is recorded in the file, not in its name.** Directory and file names are the least
  reliable statement of which corner an SDF holds, and a min-corner run reported as max is a hold
  sign-off that never happened. Read the header, quote it, treat setup and hold as two runs.
- **Escaped identifiers and bus bits break naive Greps.** A netlist writes bit-blasted and
  hierarchical names in forms the RTL never used, and an escaped identifier is terminated by a
  literal space that is part of the name. In a regex, brackets are a character class unless escaped,
  so a search for a bus bit written with brackets matches something else and hands back a confident
  wrong driver. Anchor and escape, or the step 4 trace lies to you.

## Human verification — what a wrong answer looks like

- **annotation was proved from the annotation report**, not assumed because an SDF path appeared in
  the invocation or because the run took a plausible length of time, and the unmatched-construct
  count is quoted with the run it came from
- the `rung` is stated, no timing conclusion is drawn from a `rung: zero-delay` run, and `symptom` is
  the first token in step 7's order that the evidence actually supports
- every violation called benign names the exception entry, the synchroniser instance, or the
  testbench driver covering it — `exception: not-checked` is honest, "looks like reset noise" is not
- an X is traced to a **named driver instance** with the hops listed; "X propagation from
  uninitialised logic" with no instance is a restatement of the symptom
- the `coverage` line gives classified over reported, and says whether the hit count was truncated
- `owner` names one party, and the simulated time in `window` is quoted from the log rather than
  inferred from where reset "should" be

A wrong answer usually reads as "GLS is up, 4,000 violations, all timing noise" — from a run where
the SDF matched nothing, so there was no timing at all. The second-most common blames a real X flood
on the physical-design team when a single test-mode pin was never tied off, which step 3 finds free.

## Done when

The rung and symptom are named, annotation is proved or disproved from the report, every surviving
violation bucket has one owner and a denominator behind it, and the report says how much of **GLS
scope**'s definition of complete this run actually covers.
