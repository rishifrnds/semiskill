---
name: dv-emulation-dump-strategy
description: Plan what an emulation run will capture before you spend it — trigger, window, restore point and probe list — and verify the hierarchical paths the round rests on against the source before you spend it. Use when an emulation or prototyping run takes hours and the dump you got does not cover the failure, when the trace buffer filled before the interesting cycle, when a trigger never fired, when you are about to add signals to the probe list, or when you have been round the export-and-analyse loop three times and are no closer.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Debugging with Limited Visibility: Trigger, Window and Restore Strategy"
  semiskill-function: design-verification
  semiskill-role: emulation-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-04-09
  semiskill-tags: emulation, prototyping, visibility, trigger, waveform, checkpoint, debug
---

# Debugging with Limited Visibility: Trigger, Window and Restore Strategy

In simulation, visibility is free and the loop is minutes. On an emulator it is neither: you see the
signals you asked for, over the cycles you asked for, and finding out you asked wrong costs another
compile and another run. Ten rounds of one-signal-at-a-time is how a week disappears, and none of
those rounds failed for a clever reason — they failed because a path did not survive synthesis, a
trigger never fired, or the window sat on the wrong side of it.

The output is **one capture plan per round**, with the visibility mode this build actually gives you,
the trigger, the window, the restore point and a probe list checked against a file — plus an honest
line saying which paths were checked and which were taken on trust.

**What this does not do.** It reads source files, probe lists, run logs and capture reports. It
cannot compile a design for the emulator, arm a trigger, start a run, upload a memory or open a
waveform. Every one of those ends in a handoff to the engineer at the console, and says so.

## When to use something else

If the failure reproduces in simulation at all, **do not debug it here** — visibility is free there
and this whole procedure is a tax. Take it to `dv-sim-log-first-error` for the first error and the
signature, then to `dv-minimal-reproducer` to shrink it. Come here only for what needs the scale:
long-running firmware, real software workloads, deep post-reset behaviour, anything whose failure is
hours of simulated time in.

For a night of regression failures that need sorting before anyone books emulator time, use
`dv-regression-triage-routing`. For a failure already known to be a register access, use
`dv-ral-bringup`. For an emulation build that will not compile at all, `dv-build-filelist-hygiene`
covers the front end of that flow, though not its synthesis stage.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Visibility mode | [[FILL: which visibility our flow gives us — reconstruction from captured state, a bounded hardware trace buffer, or a probe list fixed at compile time — and which of those needs a recompile to change]] | emulation infra owner |
| Probe list location | [[FILL: where our probe, trace and capture-control files live in the tree, and which of them the compile actually reads]] | emulation infra owner |
| Trace budget | [[FILL: how much capture our platform gives us, in the units it reports — signals, samples, depth or bytes — and whether that budget is per run or shared across the whole design]] | emulation infra owner |
| Trigger mechanism | [[FILL: how a trigger is expressed for us — a file, a condition on named signals, a call from the testbench — and the strings our flow prints when it arms and when it fires]] | emulation lead |
| Run log and markers | [[FILL: where the emulation run log and its capture report land, and the strings that mean the run failed and that it finished clean]] | emulation lead |
| Name mapping | [[FILL: whether our flow writes a file mapping RTL hierarchical names to the names the emulator database uses, and where it lands]] | emulation infra owner |
| Checkpoint convention | [[FILL: whether our flow can save and restore emulator state, at what cadence it saves, where the saves land, and what is not inside one]] | emulation infra owner |
| Turnaround costs | [[FILL: what a recompile, a run, a trigger-armed rerun and an export each cost us in wall clock]] | emulation lead |
| Export handoff | [[FILL: what our export step produces, which viewer reads it, and whether exporting is a separate step from the run]] | emulation infra owner |

Two pack-wide facts have no row above because this skill narrows neither. The profile's **Run
identity** fills the plan's run id line in step 8, and its **Area to owner map** fills the owner
line; read both from `_shared/team-profile.md`.

**Run log and markers is deliberately not a copy of the profile's Fatal markers and Pass marker.**
Those describe the simulation flow. The emulation wrapper is usually a different program writing to a
different place, and the strings it prints on a failure may or may not be the ones the simulator
prints. Answer this slot on its own evidence. If the two genuinely are the same strings, write that
down here rather than leaving it to be inferred — an assumed match puts every Grep in step 2 on a
string that never appears.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented probe path or trigger
syntax does not fail loudly; it compiles, runs for four hours, and captures nothing.

## Retrieval budget — read this before opening anything

A probe list can hold thousands of entries, a run log tens of millions of lines, and a capture report
one number you actually need. Work in this order:

1. **Grep and Read work on files on disk.** A log tail, a probe list or a trigger condition pasted
   into the conversation cannot be searched. Ask for the path, or ask for the text to be saved to a
   file and be given that path. Until then you may reason over what you were shown by eye — but say
   that is what you did, and mark the plan provisional.
2. **Never open a probe list, a run log or a capture report with Read first.** **Glob** or **Grep**
   to a line number, then **Read** a bounded window around it. The capture report needs no **Grep**
   of its own: the **Run log and markers** slot names where it lands alongside the run log, so the
   second of step 2's two calls covers both files at once. One exception — if that call returns no
   hit in the report, **Read** its first 60 lines, because a report with no arm or fire line is
   either short or not the file you were promised, and both are worth knowing before step 4.
3. This is the whole allowance, and every step below fits inside it. **One Glob**, **at most eight
   Grep** and **at most four Read**, itemised:

   - **Glob** — the capture-control files named in the **Probe list location** slot (step 1). One.
   - **Grep** — one call alternating the failure and clean strings from **Run log and markers**, and
     one call over the run log and the capture report together for the arm and fire strings from
     **Trigger mechanism** (step 2). Two.
   - **Grep** — the source, for the declaration of the trigger signal (step 5). One.
   - **Grep** — the source and the name-map file, for probe-path verification, one call per
     hierarchy prefix (step 6). At most four.
   - **Grep** — the checkpoint configuration, for its cadence (step 7). One.
   - **Read** — the run log at the earliest failure hit and the capture report at its buffer line,
     about 60 lines each (step 2); the trigger signal's declaration in the source, about 40 lines
     (step 5); and one spare for whichever of steps 6 and 7 needs it. Four windows.

   Steps 3, 4 and 8 open nothing at all; they are arithmetic and drafting. Nothing here opens the
   probe list itself: step 1 **Glob**s it to establish that it exists, and step 6 checks its paths
   against the source, which is the file that can actually falsify them.
4. If a **Grep** returns more than about 200 hits, the pattern is too broad — anchor it on the
   instance name or the port keyword before reading anything.
5. Four **Grep** calls will not verify sixty probe paths. Group the paths by hierarchy prefix and
   spend one call per prefix, verifying the ones this round actually turns on. Count what you did not
   reach; step 8 asks for that number.
6. **Stopping rule.** If the budget is spent and the plan is still unsettled, emit the plan with
   every unchecked path listed as unresolved, name the one thing you still need, and stop. A path
   invented at this point costs a whole round.
7. State what you actually covered. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Establish what this build can already see, and what it costs to change

**Glob** the paths named in the **Probe list location** slot — one call — and classify the current
setup against the **Visibility mode** slot into exactly one of three. Steps 4 and 6 each branch on
the answer, and step 3 prices it, so settle it here and write the token into the plan's `visibility`
field in step 8:

- **Reconstruction from captured state → `full-replay`.** The platform stores state elements and
  recomputes everything else on demand. Any node is reachable, but only inside a reconstruction
  window anchored on a stored snapshot, and turning capture on costs throughput. There is no
  pre-selected signal set: what you commit to before the run is a window, not a list.
- **Bounded trace buffer → `trace-buffer`.** A chosen set of signals is sampled into on-board
  memory. Depth and width trade against each other, and the set is fixed for the run — changing it
  needs a rerun but usually not a recompile.
- **Probe list fixed at compile time → `fixed-probes`.** What was not compiled in is not available
  at any price short of a recompile.

If the flow is two of these at once — a compile-time probe list feeding a bounded buffer is common —
write the one that decides what a change costs, which is the recompiling one, and say in `notes` that
the other is also in play. Never leave the token blank because the platform was awkward: every later
branch reads it, and a blank routes the reader down the `fixed-probes` path by default, which is the
most expensive of the three.

Write down which changes need a recompile and which only need a rerun. That single distinction is
what makes two rounds possible instead of ten, and step 3 spends it.

### 2. Fix the failure in time before choosing anything else

You cannot place a window without a number to place it around.

**Grep** the run log once for the failure and clean strings from the **Run log and markers** slot,
then **Grep** the run log and the capture report together — the same slot names where both land —
for the arm and fire strings from the **Trigger mechanism** slot. Two calls, the two the budget
allows. Then spend two **Read** windows of about 60 lines: one at the earliest failure hit in the run
log, one in the capture report at the buffer line the second **Grep** found, or at its head if that
call returned no hit there. Record four things:

- the **cycle or time of the failure, and the clock domain it is counted in** — a cycle number with
  no domain attached is not a locus, it is a rumour
- whether the trigger **armed**, and whether it **fired**; a run where it armed and never fired is a
  different diagnosis from one where it was never armed
- what the capture report says about the buffer — filled, wrapped, or partly used. A wrapped buffer
  means the earliest samples are gone, and the window was on the wrong side of the trigger
- whether the run reached its clean-finish string at all

**Now set the plan's `class` and `phase` from what those two windows already showed** — no further
searching, this costs no budget of its own.

`class` is `infrastructure` when the run never got as far as the design: no failure string and no
clean string in the log at all, a build or licence or queue or platform diagnostic, or a capture
configuration that did not load so nothing was ever armed. That finding still gets a capture plan —
it is aimed at the flow and goes to the emulation infra owner rather than the block owner, and its
`probes`, `window` and `trigger` lines will mostly be empty. `class` is `design` only when there is
real design activity near the failure. Everything else is `unknown`, including a plan drafted from a
pasted fragment under budget rule 1: `design` is the token that puts a block owner on the hook, so it
is never the default.

`phase` is one of the five tokens of `_shared/failure-signature-schema.md`, from how far this run
got: `compile` or `elab` when the build never produced a runnable image, `run` for anything the
emulator was still executing when it broke, `finalise` for an end-of-run report the emulator itself
printed, `post` for a step that could not have started until it exited — an export or a merge. If the
log supports none of them, write `?`.

### 3. Set the round budget before drafting a plan

Take the **Turnaround costs** slot and write out what this debug can afford: how many recompiles, how
many reruns, how many exports. Then hold one rule for the rest of the procedure — **at most one
recompile-class change per round, and every recompile-class change batched into it.**

Almost every ten-round debug is one shape — changed one signal, recompiled, ran, found its neighbour
was also needed, recompiled again. Decide the whole probe set now, including the signals you only
think you might want, and pay for them once.

### 4. Size the window against the trace budget

What you are sizing depends on the token step 1 settled, and the arithmetic is not the same one.

**On `trace-buffer` or `fixed-probes`**, capture is a product and the platform fixes it:

    signals captured  ×  samples kept per signal  ≤  the depth in the Trace budget slot

Pick any two and the third is decided. Do the arithmetic in the slot's own units; if it records bytes
rather than samples, convert using the signal widths from the source and say in the plan that you
converted, because a width you inferred is a number someone should check.

**On `full-replay` there is no signal-count term to trade**, so do not invent one — nothing is
pre-selected, the left-hand side of that product does not exist, and sizing a signal set here buys
nothing. What the **Trace budget** slot buys instead is *reach*: how much stored state the platform
keeps, and therefore how far back from a snapshot a reconstruction window can be asked for. The
constraint is `locus − nearest snapshot ≤ the reach in the Trace budget slot`; step 7 establishes the
cadence, so on `full-replay` settle step 7 before closing this line. Write `probes` as the paths you
intend to ask the viewer for after the run, and say in `notes` that it is a query list, not a
capture list.

Two decisions come out of this, and they are the ones people get backwards:

- **The sample rate.** Capturing every cycle of the fastest clock buys resolution you may not need.
  If the failure is a protocol-level event, sampling the slower domain multiplies the window by the
  clock ratio for free. On `full-replay` this decision may not exist — reconstruction is per-cycle
  inside its window by construction. If the slot does not say the platform offers a rate at all,
  write "not applicable" on the `window` line rather than a rate you assumed.
- **The pre-trigger and post-trigger split.** A trigger on the failure itself needs an almost
  entirely pre-trigger window — the evidence is behind it. A trigger on a precursor needs a
  post-trigger one. Getting this backwards produces a full buffer with nothing in it, and it is the
  single commonest wasted round. On `full-replay` the same choice appears as which snapshot the
  window anchors on, and it is just as easy to get backwards.

### 5. Choose a trigger you can afford to have fire late, never one you cannot afford to miss

A trigger that never fires costs the entire round, and you find out at the end of it.

- Build the condition out of **state elements in one named clock domain**. The platform samples it on
  an edge of that clock, so a condition that is only briefly true, or that mixes domains, may never
  be observed as true even though the design did the thing.
- Prefer a condition **already observed in a previous log** over one that is merely logically certain.
  Step 2's window is the best source of those.
- If the condition fires thousands of times, use the counted form the **Trigger mechanism** slot
  describes — the nth occurrence — rather than narrowing the condition until it is fragile.
- **Specify a fallback arm.** An unconditional capture of the last window before the run ends, or a
  count-based trigger at roughly the locus from step 2, turns a missed trigger from a lost round into
  a degraded one. If the mechanism cannot express a fallback, say so in the plan: the round is a
  gamble and the person spending it should know.

To confirm the trigger signal exists and is what you think, **Grep** the source for its declaration —
the one call budgeted to this step — and **Read** about 40 lines around it, the third of the four
windows. Then hand it over: **ask the engineer to arm this condition and give you the path to the
resulting run log and capture report.**

### 6. Verify probe paths against a file — this is the round you save

This is the step that pays for the skill, and the one an agent does better than a tired human at five.
What it is worth depends on the token from step 1, so decide the scope before spending the calls:

- **`fixed-probes`** — verify every path on the plan. A path that did not survive synthesis gets
  compiled in, captures nothing, and you find out four hours and one recompile later. The whole
  four-call budget belongs here.
- **`trace-buffer`** — verify every path too, for the same reason one level cheaper: a wrong path
  costs a rerun rather than a recompile, and it still burns depth a real signal wanted.
- **`full-replay`** — there is no pre-committed list to check before the run, so the failure mode
  moves rather than disappearing: a source name that did not survive synthesis is unreachable in
  reconstruction too, and you meet it at the viewer instead of at the compile. Verify only the paths
  this round's conclusion rests on, spend one or two calls rather than four, say in the coverage line
  that the check was scoped that way, and leave the rest of the budget for step 7's cadence — that
  is what actually bounds a replay window.

For each hierarchy prefix in scope, **Grep** the source for the instance and signal names, and
**Grep** the file named in the **Name mapping** slot for the same names. Up to four calls total;
group the paths so that one call clears a whole prefix. Classify every path as one of:

- **verified** — found in the source, with a file and line
- **mapped** — found only in the name map, under a different post-synthesis name; carry the mapped
  name into the plan, not the source name
- **unresolved** — found in neither. This is not automatically an error: optimisation legitimately
  merges and removes nets, so a node may simply not exist in the emulator database. It is, however,
  a path that will silently capture nothing, and it must be listed as unresolved rather than left on
  the plan looking healthy.

If a **Grep** hit is ambiguous — the same signal name declared in two modules, and the prefix does
not separate them — spend the spare **Read** window on the declaration rather than guessing which one
the path means. That is the fourth window, and step 7 is the only other claim on it.

If the **Name mapping** slot says our flow writes no such file, say so and mark every path
source-verified only. That is the weaker claim, and the plan should carry it as such.

### 7. Pick the restore point, and say what the restore does not restore

Read the **Checkpoint convention** slot, then **Grep** the checkpoint configuration for its cadence —
one call — and, if that does not settle it, spend the spare **Read** window there.

Choose the **nearest save before the locus from step 2**. A save taken after the divergence is worth
nothing, and the cadence decides how close you can get: if saves are an hour apart and the failure is
fifty minutes in, restoring buys you ten minutes, not fifty.

Then write down, explicitly, what the restore leaves behind. This is the list that turns a
"non-reproducible after restore" mystery into a known limitation:

- host-side testbench, transactor and co-model state, unless the flow checkpoints both sides together
- open files and their positions, and anything that was streaming to or from the host at save time
- memory contents loaded by a preload step, if that preload happens outside the checkpointed state
- the capture configuration itself, if trace is armed after the restore rather than before it

If any of those carries the precondition for the bug, a restore will hide it, and the round is spent
proving the design is fine.

### 8. Write the capture plan

One block per round. Leave a field empty rather than filling it from assumption. Three fields are
already decided and are only being transcribed here: `visibility` is the token step 1 settled,
`class` and `phase` are the ones step 2 set. If any of the three is still open when you reach this
block, the step that owns it did not finish — go back to it rather than picking a token now.

```
capture plan : round <n> of <the round budget from step 3>
signature    : <phase>|<kind>|<where>|<what>, per the shared schema
phase        : compile | elab | run | finalise | post
class        : design | infrastructure | unknown
visibility   : full-replay | trace-buffer | fixed-probes
locus        : <failure cycle or time, and the clock domain it is counted in>
trigger      : <the condition, written the way our trigger mechanism expresses it>
arm fallback : <what still captures something if the trigger never fires, or "none">
window       : <samples before the trigger, samples after, and the sample rate>
probes       : <n> requested, <n> verified in source, <n> mapped, <n> unresolved
restore      : <the save this round starts from, or "cold start", and what it does not restore>
recompile    : <yes or no, and every recompile-class change batched into this round>
export       : <what the engineer should send back, and where it should land>
run id       : <whatever identifies this emulation run for us>
log          : <path, and the line range worth reading>
owner        : <the area map's owner for the failing block, or blank plus candidates>
coverage     : <paths checked against a file, paths taken on trust, and what the budget missed>
notes        : <anything the next person would otherwise have to rediscover>
```

The `signature`, `phase`, `class`, `run id`, `log`, `owner` and `notes` field names are the ones the
rest of the pack already uses, so a plan drafted here reads side by side with a repro block from
`dv-sim-log-first-error`. Derive the signature from `_shared/failure-signature-schema.md` as written;
if the failure has none yet, leave it empty and say the plan is aimed at finding one.

Take the export line from the **Export handoff** slot and finish with the handoff itself: **ask the
engineer to compile with this probe list, arm this trigger, run it, export, and give you the path to
the run log, the capture report and the exported dump.**

## Gotchas

- **Emulation is two-state; simulation is four.** There is no X propagation, and an uninitialised
  register holds whatever definite value the platform gave it. A bug that lives on X will not appear
  here, and one that appears only here may be an initialisation the emulator supplied and the
  simulator did not. Confirm what our platform does rather than assuming — some flows offer limited
  X modelling at a cost.
- **Post-synthesis names are not source names.** Optimisation merges, renames and deletes nets, so a
  signal you can read in the RTL may have no node in the emulator database at all. That is why step 6
  checks the name map and not just the source, and why an unresolved path is reported rather than
  quietly compiled.
- **Combinational nodes are reconstructed, not recorded.** In a reconstruction flow the platform
  stores state and recomputes the rest, so a combinational node exists only inside a window anchored
  on a stored snapshot. Ask for one outside that window and you get nothing, which looks exactly like
  a signal that was never probed.
- **Sizing a signal set on a replay platform is wasted work.** The `signals × samples` product is a
  trace-buffer law, not a universal one. On `full-replay` nothing is pre-selected, so an engineer who
  applies it anyway spends the round trimming a list the platform never asked for, and still gets a
  window bounded by snapshot cadence — which is the number they should have been arguing about.
- **Memory contents are not in the waveform.** They come from a separate memory upload with its own
  cost and its own handoff. Probing a memory's data port bit by bit to rebuild its contents is the
  expensive way to discover this.
- **Turning capture on changes throughput.** Deep trace and state capture slow the emulator, sometimes
  enough to turn "one more round tonight" into "one more round tomorrow". Measure ours from a real
  run rather than assuming a traced run costs what an untraced one did.
- **An assertion that did not synthesise reports nothing.** Only a synthesisable subset makes it into
  the build, and a silently dropped assertion is indistinguishable from a passing one in the run log.
  Ask the emulation lead which of ours survived before reading a quiet run as evidence of anything.
- **Cycle counts belong to a clock domain.** A window written in the wrong domain's cycles is wrong by
  the ratio between them — on a slow peripheral clock, easily enough to place the whole capture past
  the event.
- **The emulation build is not the simulation build.** Clock gating, tie-offs, test logic and
  behavioural models swapped for synthesisable ones all differ, so two signatures from the two flows
  are not automatically the same bug. "It also fails in emulation" is a claim that needs one.
- **Restoring past the precondition hides the bug.** A save taken after the configuration write, the
  calibration or the one-time training that set the trap gives a clean run and a wasted round — the
  same shape as a checkpoint restore in simulation, and why step 7 asks what is not restored.
- **A wrapped buffer is a finding, not a failure.** It says the trigger fired later than the window
  needed, which tells you the split from step 4 was backwards. Read the capture report before
  concluding the probes were wrong.

## Human verification — what a wrong answer looks like

Before booking the run, check:

- `visibility` carries one of the three tokens, and it is the one step 1 derived from the **Visibility
  mode** slot rather than the one that sounded most familiar
- `class` is `infrastructure` for a run that never reached the design, `design` only where there was
  real design activity near the failure, and `unknown` wherever the log settled neither
- every probe path on the plan is **verified**, **mapped**, explicitly **unresolved**, or named in
  the coverage line as taken on trust — none is there merely because it looked plausible in the
  source, and on `full-replay` the coverage line says which paths step 6 chose not to check
- the window arithmetic matches the `visibility` token: a `signals × samples` product on
  `trace-buffer` or `fixed-probes`, a reach-against-cadence bound on `full-replay` — and it is in the
  **Trace budget** slot's own units and does not exceed the budget; any signal width that was
  inferred rather than read is called out
- the locus carries the **clock domain** its cycle number is counted in
- the trigger is a condition on state in one named clock domain, and either it was observed true in
  an earlier log or the plan carries a fallback arm — or says plainly that it cannot
- the restore line names what the restore does **not** restore
- this round contains **at most one** recompile-class change, and the plan says which round it is
- the coverage line is present and gives the number of paths not reached

A wrong answer typically puts a source hierarchy path on the plan that no longer exists after
synthesis; quotes a cycle number with no clock; sets an all-post-trigger window on a trigger that
fires at the failure; or proposes three consecutive recompiles and calls that a strategy.

## Done when

The engineer can compile once, run once and come back with a dump that contains the failure and the
cycles before it — and if it does not, the plan already names the line that was a guess.
