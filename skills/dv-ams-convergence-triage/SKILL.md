---
name: dv-ams-convergence-triage
description: Triage a mixed-signal run that aborted on a convergence failure or slowed to a crawl when the analog timestep collapsed, by reading the solver's own diagnostics — worst-converging nodes, rejected timepoints, minimum-step hits — and classifying the cause as boundary, model, circuit or solver setup. Use when the analog solver reports non-convergence, when a run stops advancing simulated time but never errors, when a transient is hours behind the stop time it was meant to reach, when the operating point will not solve, or when someone proposes loosening reltol to get a run through.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Analog Solver Convergence and Timestep-Collapse Triage in Mixed-Signal Runs
  semiskill-function: design-verification
  semiskill-role: ams-verification-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-06-30
  semiskill-tags: ams, mixed-signal, convergence, timestep, solver, verilog-a, triage
---

# Analog Solver Convergence and Timestep-Collapse Triage in Mixed-Signal Runs

A mixed-signal run fails in two shapes that read alike and are almost never the same bug. One aborts: the
solver cannot meet its tolerances, halves the timestep to the floor and gives up. The other never errors —
the steps shrink until the transient is far short of its stop time and someone reports "the simulation is
slow". The output is **a class, the evidence behind it, and one change to try**.

## When to use something else

An ordinary failure — assertion, scoreboard miscompare, testbench error — is `dv-sim-log-first-error`'s, as
is anything at `finalise` or `post`; a night of them is `dv-regression-triage-routing`'s; a `compile` or
`elab` break is `dv-build-filelist-hygiene`'s. `dv-minimal-reproducer` shrinks the case afterwards, but
shrinking analog changes the numerics. If step 5 lands on the boundary, the connect rules themselves are
`dv-connect-module-discipline-debug`'s, and **a run with no analog solver in it cannot have this failure** —
in pure real-number modelling nothing converges, so the model is `dv-rnm-authoring-correlation`'s.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Analog solver | [[FILL: which analog solver our mixed-signal runs use, whether the digital kernel or the analog one owns the top level, and which configurations of this testbench contain no analog solver at all]] | AMS lead |
| Solver diagnostic markers | [[FILL: four separate strings — what our solver prints on a convergence failure, on a rejected timepoint, on a minimum-timestep hit, and on the worst-converging-node report — and whether each is printed by default or needs solver verbosity raised]] | AMS lead |
| Solver statistics | [[FILL: where the end-of-run analog statistics land, same log or separate file, and whether accepted and rejected timepoint counts are among them]] | AMS lead |
| Progress line | [[FILL: the line our runs print periodically giving simulated time reached, and what its print interval is keyed on]] | AMS lead |
| Options file | [[FILL: which file sets our analog tolerances, integration method and minimum timestep for this testbench, and which of those we set rather than leave at the solver default]] | DV infra |
| Boundary configuration | [[FILL: where our connect rules and their supply and transition parameters are declared, and which rule set this testbench selects]] | AMS lead |
| Behavioural model location | [[FILL: where the Verilog-A and Verilog-AMS models for this block live in our tree]] | block owner |
| Stop time | [[FILL: the simulated stop time this test is meant to reach, and where that is written down]] | block DV owner |

Seven facts come from `_shared/team-profile.md`: **Log location**, **Fatal markers**, **Pass marker** and
**Infra markers** in step 1; **Build log location**, where our elaboration output lands, in step 5;
**Known-issue list** and **Run identity** in step 9. **If a slot is unfilled, stop and ask** — an invented
marker makes every Grep return nothing. **Solver diagnostic markers is narrower than Fatal markers**: three
of its four strings are not failures, so a collapse counted against the wrong one reads as clean.

## Retrieval budget — read this before opening anything

A collapsing analog run is the worst case in this pack for log size: the solver can print a line per rejected
timepoint and there can be millions. Reading forward through one is impossible, not slow.

1. **Grep and Read work on files, not on chat text.** A convergence failure pasted into the chat is a
   fragment, nearly always the abort line rather than the onset. Ask for the path under the profile's **Log
   location**; until one exists you may reason over the pasted lines by eye, but say so and call every
   conclusion provisional. Never Read the log first: every Read is a window around a Grep hit.
2. **Log budget: five Greps, three 80-line windows.** One Grep to step 1, two to step 2, one to step 3
   whichever branch it takes, one to step 4. Windows go to steps 2 and 3, the third held for the onset.
3. **Our-files budget: one Glob, four Greps, two 40-line windows.** Step 5 spends two Greps, one per source
   it checks; steps 6 and 7 are alternatives, so only the one step 5 picks spends a Grep and a window, and
   step 7 also spends the Glob. Step 8 gets the last Grep and window, and one further Grep is held for step
   9, spent only if the known-issue list is a file rather than a tracker.
4. **Count, never list.** Any Grep for a per-timepoint diagnostic is a counting Grep; more than about 200 hits
   when you were not counting means the pattern was wrong.
5. **Stopping rule, then coverage.** With the budgets spent and no class settled, stop and name the
   measurement still missing and who must take it — usually a waveform across the onset. Then state which
   windows were spent, what was never opened, and what came from a person rather than a file.

## Procedure

### 1. Establish there is a solver, then whether it aborted or is still crawling

Read the **Analog solver** slot first: it says which kernel owns the top level and therefore whose log the
solver diagnostics and progress line land in, and if this configuration has no analog solver, stop — there
is no Newton iteration to fail. Then **Grep** once, alternating the profile's **Pass marker**, **Fatal
markers** and **Infra markers** with the convergence-failure string from **Solver diagnostic markers**.

- **The convergence-failure string is present** — an abort. Continue.
- **No fatal, no pass, the log ends on a progress line** — a crawl; the branches separate at step 3. The trap
  is a crawl killed by a wall-clock or queue limit, which carries a fatal marker and reads as an abort: if
  the last diagnostic is not one of the solver's own strings, treat it as a crawl.
- **An infra marker** — licence, host, queue, disk — goes back to `dv-sim-log-first-error` with
  `class: infrastructure`. **Nothing at all** means the run died before the solver started, or the strings
  are wrong.

### 2. Measure the collapse instead of describing it

Two **Grep** calls, counting rather than listing: the rejected-timepoint and minimum-timestep strings
together, then the **Progress line**, taking its last hit for the furthest simulated time the log admits to.
Then one 80-line **Read** window on the **Solver statistics** block if that slot says it lands here; if the
counts land elsewhere or are off by default, say so and **ask the engineer to rerun with the statistics
enabled and give you the path to the new log**.

- **Rejections are normal** — every healthy transient rejects steps, so the count alone says nothing and the
  rejected-to-accepted *ratio* says a great deal. **A minimum-timestep hit is not**: the solver ran out of
  room to retry, and even one is a finding. Many rejections and no minimum-step hits is a run working slowly.
- **Progress against the Stop time slot is the crawl's only honest measure**: time reached against time
  intended, as a fraction, never "it is slow".

### 3. Read the first diagnostic, not the ten-thousandth

One **Grep** for line numbers, then one 80-line **Read** window 60 lines before the lowest. **On an abort**,
Grep the convergence-failure string. **On a crawl** there is no such string — that absence is what made it a
crawl — so Grep the minimum-timestep string, and if step 2 counted none of those either, the
rejected-timepoint string, whose first hit is the nearest thing to an onset; say so, because a first
rejection is not a failure.

From the window record verbatim, with line numbers: the simulated time reported, every node named, and — on
an abort — the iteration count it gave up at and **which quantity failed**: a voltage update, a current
residual, or a charge. That last is load-bearing and usually skipped: an update failure says the iteration
was still moving when the limit ran out, a residual failure says it settled somewhere off the solution.

**A non-zero simulated time** is a transient failure. **Time zero, or no time at all**, means the operating
point never solved, so the cause list differs — a node with no conductive path to ground, a bistable node, a
loop of ideal sources, a supply not yet defined. Choosing among the homotopy remedies is an experiment:
**ask the engineer to retry the operating point with conductance stepping, source stepping or a
pseudo-transient ramp and send back that log's path**, then rejoin at step 4.

### 4. Take the ranked node list — and stop here if there is none

**Grep** for the worst-converging-node string. The abort line names whichever node the solver held when it
gave up, frequently a bystander; the ranked report names the nodes carrying the largest residual or update,
and that ranking is the evidence. Write the names exactly as the solver spells them — hierarchical names get
abbreviated by well-meaning people and then match nothing.

If that Grep returns nothing, or the slot says the report needs verbosity raised, **the classification stops
here** — the ordinary case for a crawl, because the solver never gave up and many flows never print a ranking
for one. **Ask the engineer to rerun with the worst-node report enabled and give you the path**, then go to
step 9 and write the block with `worst nodes: ranking pending`, `ams origin: unknown` and a coverage line
saying the collapse is measured but not classified. Steps 5 to 8 all consume the ranking, and the names in
the step 3 window are one timepoint's, not a ranking.

### 5. Boundary or interior — the one branch that matters

Spend two of the four our-files **Grep** calls on the top-ranked node name, one per source: the **Boundary
configuration** files, and the connect-module insertion listing inside our elaboration output, which the
profile's **Build log location** fact locates and which is usually a different file from the simulation log.

- **Worst nodes on the analog-digital boundary**, or carrying auto-inserted naming — step 6. **Worst nodes
  inside one analog block**, clustered on one net or loop — step 7.
- **Worst nodes scattered with no structure**, or the list is every node in the design — a global cause: a
  supply ramp faster than the decoupling follows, a corner setting, or a tolerance the design cannot meet.
  Go to step 8.

### 6. The boundary branch — what costs timesteps

Spend one **Grep** and one 40-line **Read** window on the rule set this testbench selects. Two things here
cost steps. **Transition time**: rise and fall parameters far shorter than anything the analog circuit
produces make every edge a near-step, so a clock crossing the boundary bounds the maximum timestep to a
fraction of its period whatever the tolerances say. **Edge rate**: count how many boundary nets toggle in the
onset window, because a slow analog side with one fast digital net crossing in is a partition problem.

### 7. The interior branch — the model, then the circuit

One **Glob** for the **Behavioural model location** tree, one **Grep** into the model owning the top-ranked
node, one 40-line **Read** window. In this order:

- **A conditional on a continuous quantity with nothing smoothing it.** Switching a contribution on a
  voltage comparison is a step in the equations whose derivative does not exist at the switch point. The
  Verilog-AMS language reference manual defines the smoothing filters that exist for this — transition, slew,
  absdelay — so a model using none is the finding. A crossing event is the same problem in event form.
- **Ideal elements** — zero on-resistance, a huge on-to-off ratio, a capacitor with no path to ground, an
  inductor looped with an ideal source — wreck the matrix conditioning.
- **A genuine circuit oscillation** — a comparator with no hysteresis crossing slowly, an uncompensated loop.
  **A design finding, not a solver finding**; the tells are worst nodes inside one feedback loop and a
  collapse starting at a stimulus. It cannot be settled without a waveform, which the agent cannot open, so
  **ask the engineer to plot the top-ranked nodes around the onset from step 3 and say which of three things
  they do — ring at a steady frequency, step, or drift** — and mark it provisional until they answer.

### 8. Tolerances and the integration method — deliberately last

Spend the last **Grep** and the last 40-line window on the **Options file**, recording which values we set
against which are solver defaults; conflating them sends someone to argue with a default nobody chose.

- **The tolerances are not interchangeable.** The relative one governs how small a change between iterations
  counts as settled; the absolute ones floor it per voltage and current, and a node below that floor never
  converges meaningfully while one far above it burns iterations.
- **Loosening a tolerance changes the answer.** A run that only completes at a looser relative tolerance
  produced different numbers, so every check that passed under it is provisional — it turns a failure into an
  unverified pass, and the proposal must say so.
- **The integration method can hide the bug you are hunting.** The trapezoidal rule can ring on a stiff node
  for numerical rather than circuit reasons; the backward-difference methods damp that ringing and damp real
  oscillation with it, deleting the evidence step 7 wanted.

Propose **one** change — lowering the minimum timestep is not one, it only moves the abort later — then **ask
the engineer to rerun with it and send back the new statistics block**.

### 9. Check it against the known-issue list, then record the finding

Write the result as a failure signature following `_shared/failure-signature-schema.md` — simulated times and
node indices are exactly what it tells you to strip. Then compare it against the profile's **Known-issue
list**, not memory: if that list is a file on disk, spend the held Grep on it for the signature's `where` and
the distinctive fragment of `what`, naming any match by that list's own key. If it is a tracker Grep cannot
reach, or is unfilled, say so rather than calling the collapse new.

```
signature   : <phase>|<kind>|<where>|<what>
phase       : compile | elab | run | finalise | post
class       : design | infrastructure | unknown
failed as   : <abort, or crawl — and at the operating point, or in the transient>
ams origin  : <boundary, model, circuit, solver-setup, or unknown>
worst nodes : <the ranked nodes, spelled as the solver spells them, or "ranking pending">
onset       : <the FIRST solver diagnostic verbatim, with its log line number and simulated time>
progress    : <simulated time reached against the stop time it was meant to reach>
rejects     : <rejected timepoints counted, and minimum-step hits counted separately>
known issue : <the matching entry's key, or "pending a tracker search", or "not checked">
evidence    : <log path and line range, and a file path and line for every value quoted above>
run id      : <whatever identifies this run for us>
next        : <the ONE change to try, and a request to rerun and send back the statistics>
coverage    : <which windows were spent, what was never opened, what came from a person>
notes       : <anything the next person would otherwise rediscover>
```

The field names are `dv-sim-log-first-error`'s, so the two blocks read side by side, and `phase` is always
`run` here — the solver started — though the line carries the pack's full token set so the column joins.
Anything not fillable from disk gets `?`. `class: design` is reserved for the step 7 oscillation and a
boundary conflict the design creates; a tolerance or rule-set parameter takes `class: unknown`.

## Gotchas

- **The last progress line is not where it stopped.** Its interval is keyed on simulated time, so a
  collapsing run stops printing long before it stops. The final time in the log is the last interval it
  *reached*; the true stopping point is later and unknown.
- **A crawl usually has no worst-node report, and that is a fact about the flow, not the design.** Solvers
  print the ranking when they give up, so the crawl that most needs a ranking is least likely to have one.
- **A convergence failure at a connect-module instance is not a bug in that instance.** The auto-inserted
  name says where the boundary is, not what is wrong with it; step 4's ranking says which side.
- **Comparator chatter is a loop between the two kernels.** An analog node dithering around a threshold emits
  a digital event per crossing, each event is a breakpoint the solver must land on, and each landing resolves
  the node again. Neither kernel misbehaves; the tell is a net toggling faster than any clock explains.
- **The abort's simulated time is not the onset**, and two runs of one collapse never stop at the same time.
  The collapse began where the rejection rate first rose, which is what the held-back window is for.
- **If simulated time is not advancing and nothing is being rejected, the analog side is not the problem.**
  Nothing is rejected because nothing is attempted: a zero-delay loop on the digital side generates events at
  one timestamp and time never moves.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- `failed as` names both halves — abort or crawl, operating point or transient — and `rejects` keeps the
  minimum-step count separate from the rejection count.
- if `worst nodes` says `ranking pending`, `ams origin` says `unknown` and the coverage line says
  measured-but-not-classified — an origin asserted without a ranking is a guess wearing a class name.
- the node names came from the worst-node report rather than the abort line, spelled as the solver spelled
  them, and `progress` is a fraction of the intended stop time with its source named.
- exactly one change sits in `next`, a tolerance change says in the same breath that it makes the results
  provisional, and `known issue` separates a real search from one never done.

A wrong answer loosens the tolerance before anything is classified, blames the solver for a boundary net the
digital side toggles at clock rate, or files an oscillation as a solver setting.

## Done when

You can name the failure mode, the solver stage, the one origin — or say plainly the ranking needed to reach
one is missing — the evidence under it, and the one change you are asking for.
