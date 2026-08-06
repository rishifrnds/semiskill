---
name: dv-memory-model-training
description: Bring a memory controller and PHY up against a vendor memory model without inventing a single number — find the timing set the build actually compiled, reconcile it against the controller's own timing and latency registers, place the failure on the initialisation and training ladder, and quote every value with the file and line it was read from. Use when initialisation never completes, when a training step fails or converges to a suspicious result, when the memory model prints a timing or protocol violation during bring-up, when write training fails while read training passes, or when one byte lane behaves differently from the rest.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Memory Model Configuration and Training Bring-Up
  semiskill-function: design-verification
  semiskill-role: memory-ip-dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-08-13
  semiskill-tags: memory, phy, mode-registers, training, bring-up, timing, jedec, controller
---

# Memory Model Configuration and Training Bring-Up

A memory bring-up fails twice: once in the design, and again in the report, when somebody writes down
a timing number they never actually read. The controller, the PHY and the vendor's model each carry a
separate transcription of the same datasheet table, made by different people at different times, and
most bring-up failures are two of those transcriptions disagreeing — not a logic bug. This procedure
locates the failing rung of the initialisation and training ladder, compares only values it has
actually read, and **emits no number that did not come out of a file**. The output is a finding
block: a ladder position, a classified symptom, an owner, a next step, and every number carrying its
file and line.

## When to use something else

- The build never produced a simulation — the model's files did not compile, or the include for its
  parameter file was missing: `dv-build-filelist-hygiene`.
- A simulation failed and the true first error has not been found: `dv-sim-log-first-error` first; it
  produces the signature this block carries. For a whole night of failures to sort before anyone
  opens a model file, `dv-regression-triage-routing`; to shrink a signature you already have,
  `dv-minimal-reproducer`. To find where the model, filelists and logs live, `dv-repo-orientation`.
- The mismatch is on the **controller's own** configuration registers, reached through a UVM register
  model: `dv-ral-bringup`. The memory device's mode registers are usually not a UVM register model —
  they are written by a command sequence — so that skill's decision tree does not apply to them.
- A timing check firing during ordinary traffic, long after bring-up closed, starts somewhere else:
  `dv-mem-timing-check-triage`. This procedure assumes the ladder itself is what is in question.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Model source tree | [[FILL: where the vendor memory model and its timing-parameter files live in our tree, and which of them are readable text rather than encrypted or binary]] | DV infra owner |
| Speed-bin selection | [[FILL: how the model's speed bin, density and organisation are chosen for a build — the define, parameter or include file — and where that value is actually set]] | DV infra owner |
| Model check controls | [[FILL: which of the model's timing checks and which of its protocol or state checks are compiled in by default here, and the define or plusarg that switches each group]] | DV infra owner |
| Model message markers | [[FILL: the strings this model prints for a timing violation, for a protocol or state violation, and for a completed initialisation]] | DV infra owner |
| Controller timing config | [[FILL: where our controller's timing and latency register values are set for a run — a config file, an init sequence, or generated firmware — and whether that source is readable text]] | controller DV owner |
| Training ladder | [[FILL: the ordered list of initialisation and training steps our controller and PHY actually run, in our own names for them, and which are skipped by default]] | PHY integration owner |
| Training completion evidence | [[FILL: what our flow prints or writes when each ladder step completes, and where the per-lane and per-bit result values land]] | PHY integration owner |
| Init bypass | [[FILL: whether our bench can skip initialisation or training and preload the results, how that is selected, and which regressions use it]] | verification lead |
| Datasheet availability | [[FILL: which of the memory datasheet, the standards clause text and the controller databook exist as files we are permitted to read and to quote from]] | IP program owner |

Six pack-wide facts come from `_shared/team-profile.md` and are not repeated above: **Log location**
(step 1), **Fatal markers** and **Pass marker** (step 5), **Run identity** and **Area to owner map**
(step 8), and **Rerun convention** (step 8's `next` line). The profile's **Register model source** row
is unused here: it describes the generator behind our UVM register model, and the device's mode
registers do not come from it.

**Model message markers is narrower than the profile's Fatal markers.** It is what the *vendor's
model* prints, which is neither what our flow prints on a failing run nor what our compiler prints on
a build break — three lists, none of them fillable from another. If two do share a string, record
that as a finding rather than assuming it.

**If a slot is unfilled, stop and ask. Do not guess.** An invented define name sends the reader to a
build knob that does not exist. An invented timing number is worse, because it looks like evidence.

## Retrieval budget — read this before opening anything

A vendor model carries every speed bin it supports; a bring-up log prints per-command traffic for the
whole ladder. Both are far past what can be read. Work in this order:

1. **Grep, Read and Glob work on files on disk.** They cannot search text pasted into a chat. If the
   log or the config arrived pasted, ask for the path, or for it to be saved and be given that path.
   Until a path exists you may reason over the pasted lines by eye — say that is what you did, and
   treat every conclusion as provisional.
2. **Never open a model file or a log with Read first.** Glob to locate, Grep to get a line number,
   then Read a bounded window around it.
3. The whole ledger for one pass is **four Globs, fourteen Greps and six windowed Reads**. Broken
   out: step 1 at most two Globs and two Greps; step 3 one Glob, three Greps and one 40-line window;
   step 4 one Glob, at most six Greps — one per parameter — and two 40-line windows; step 5 two
   Greps and one 80-line window; step 6 the one spare 40-line window and no new Greps; step 7 one
   Grep and one 60-line window.
4. **One parameter per Grep.** Never Read a timing table whole to "see what is in it" — that is how a
   number from the wrong speed bin ends up in a report. If a Grep returns more than about 200 hits,
   the pattern is too broad; narrow it before reading.
5. **Stopping rule.** If the ledger is spent and the symptom is still unclassified, stop. Report the
   rung reached, the one fact still missing, and who has it — past that point numbers get invented.
   Then state what you covered: how far up the ladder, and how many parameters were compared out of
   how many. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Get the evidence onto disk, and find out whether the ladder even ran

If the log arrived pasted, resolve that first — budget rule 1. The profile's **Log location** says
where ours land; use **Glob** there rather than asking for the log again.

Then settle the **Init bypass** slot's selector. Spend one **Grep** for it against the log; only if
the run does not echo its configuration into the log, spend one further **Glob** for the file the
slot names and one further **Grep** inside it. That is all of step 1's ledger — at most two Globs and
two Greps — and it is the cheapest question here, because it invalidates everything downstream when
the answer is yes: a run that preloaded training results never exercised the ladder, so no rung of it
can be the cause and steps 5 to 7 have nothing to read. Say so plainly and ask for a run with the
bypass off before going further.

### 2. The number rule — no timing value or register encoding without a file and a line

This is the discipline the rest of the procedure exists to protect.

- Every timing value, latency, delay count and mode-register field encoding is quoted **with the path
  and line it was read from** — including the ones you are confident about.
- Three sources produce numbers here. The model's parameter file and the controller's configuration
  are usually files, so they are evidence. The datasheet, the standards clause text and the databook
  usually are not — settle that with the **Datasheet availability** slot. Where they are unreadable,
  or licensed material this pack may not quote from, a number from them is a **handoff**: ask the
  owner, record who supplied it and the clause by name, and mark the finding provisional.
- **A converted number is a derived number.** Timings specified as the greater of a time and a clock
  count change their clock count with tCK, so anything you convert is labelled `(derived)` alongside
  the tCK it was derived at and where that tCK itself was read from.
- If a number is neither on disk nor supplied by a named person, write `?`. A plausible invented
  timing number reads as evidence, gets pasted into a ticket, and costs the RTL owner a day.

### 3. Read the model's configuration as the build actually selected it

**Glob** the **Model source tree** slot's path for the parameter file. Do not open it yet. The model
holds several timing sets and compiles exactly one, chosen by the symbol named in the **Speed-bin
selection** slot. Two **Grep** calls settle which: one for that symbol in the build configuration or
filelist, to get the value actually set, and one for that value inside the parameter file, to get the
line where its block begins. Then **one 40-line Read** at that block, and nothing else. The selector
and the numbers it selected are quoted together in the report or neither is.

Spend the third **Grep** on the **Model check controls** slot's defines. A model whose timing checks
were compiled out reports nothing, and the run looks like the cleanest bring-up anyone has seen.
Record which check groups were in — the finding block has a field for it. If the parameter file turns
out to be encrypted or binary, say so and stop reading it; its values are then handoffs under step 2.

### 4. Read the controller's side of the same numbers

Use one **Glob** for the **Controller timing config** slot's source, then **at most six Greps — one
per parameter you actually need**, and at most **two 40-line Reads** around the hits.

Compare only fields you have read from **both** sides. Two independent transcriptions of one
datasheet table are the bug class this step exists for, and a report claiming the controller is wrong
on the strength of one side is a coin toss dressed as an analysis.

Latency deserves its own pass, because it lives in three places and only one is a mode register: the
value programmed into the device, the controller's own latency register, and the latency the
controller is told to assume across its interface to the PHY. Two of the three agreeing proves
nothing. Read all three or report the third as `?`.

### 5. Place the failure on the ladder

The **Training ladder** slot gives the ordered rungs in our own names; use those names and no others,
because the report is read by the people who own the ladder.

Two **Greps** on the log. The first alternates the **Model message markers** with the profile's Fatal
markers and Pass marker — one call, not three. The second looks for the per-step completion strings
from the **Training completion evidence** slot. Then **one 80-line Read**, starting before the first
rung that did not report completion.

Name two rungs: the last that reported completion and the first that did not. If nothing reported
completion, the ladder never started and this is an initialisation problem rather than a training one
— the first rows of step 6 apply. A rung that reported completion is not a rung that worked; step 7
is where you find out whether it converged or merely stopped.

### 6. Classify the symptom

The `Evidence` column says what each row can be settled from. `source` is the model, controller and
testbench files; `log` is the saved bring-up log. `log + wave` means the agent can narrow it and a
human has to finish it — **ask the engineer to capture a waveform over that rung and read the result
back to you**, and record in the report that the answer came from a person. `source + log + wave`
opens with a source check the agent settles alone, and falls through to that same handoff only when
the source check comes out clean.

| Symptom | Evidence | Check first | Usual cause |
|---|---|---|---|
| The device never leaves reset; the init handshake never completes | log + source | whether the reset and clock-enable ordering the model requires was followed, and whether the model printed a state violation before the hang | an init step ordered wrongly, or a model input the bench never drove |
| Init runs but the first mode-register write is rejected | log | the model's state at that point, and which preceding step it was waiting for | a step of the init sequence skipped |
| Every rung fails identically, on every lane | source | configuration, not connectivity — drive strength, termination and latency on both sides | one wrong mode-register field |
| One byte lane fails, the rest pass | source | that lane's path through the interconnect and the model instantiation | a byte-lane or strobe swap |
| One bit inside a lane fails | source | whether per-bit deskew is part of our ladder at all | a bit swizzle a ladder without per-bit deskew cannot absorb |
| A rung reports completion with its result at the end of its range | log + source | whether the value sits at a delay-line end stop | it saturated rather than converged; the pass is false |
| Read training passes, write training fails | source | the three latency values from step 4, then write termination | a write-latency or termination mismatch |
| A timing violation fires during the ladder, not during traffic | source | which parameter the model names, then both sides' value for that one parameter | the controller programmed more aggressively than the compiled model set |
| A timing violation names a parameter both sides already agree on | source + log + wave | that the two values really are equal — that part is source — and only then what the command spacing at the pins actually was | the tCK the model was given is not the period the PHY drives, so a correct number is enforced against the wrong clock |
| One rung lands on a different result on repeated runs of one build | log + wave | whether the results differ by more than the ladder's own step size, then what the strobe-to-data edge relationship looks like across that rung | a marginal edge relationship no log can show — injected jitter, an unconstrained delay, or a race in how the bench drives the model |
| Everything passes, then traffic miscompares immediately | log + source | whether the model's checks were compiled in at all, per step 3 | the run proved nothing |
| Passes at one frequency set point, fails after a switch | source + log | whether the ladder is re-run, or its results re-applied, on the switch | per-set-point results not restored |
| Passes cold, fails after a low-power exit | source + log | whether the exit path restores what the entry path saved | training state lost across the exit |
| Rank 0 passes, rank 1 fails | source | the per-rank settings, termination above all — they are usually asymmetric | rank 1 configured by copying rank 0 |

Take the one spare 40-line **Read** here, wherever the row sends you. The two rows whose Evidence ends
in `wave` are where the agent stops: narrow them as far as source and log reach, then hand off rather
than reasoning about edges you cannot see.

### 7. Read the results out, without judging them

The **Training completion evidence** slot says where per-lane and per-bit results land. One **Grep**
there — the results file if there is one, otherwise the log — and **one 60-line Read**. Record the
values **verbatim** with the line they came from: do not average them, convert them to time, or round
them.

Two things can be settled from the values alone. Whether any result sits at the extreme of its range,
which is saturation rather than convergence and turns a reported pass into a finding. And whether the
spread across lanes is wildly uneven, which points at connectivity or loading rather than at timing.
One thing cannot: **whether a margin is adequate**. That needs the databook's criterion, a handoff
under step 2. Calling a margin healthy without it is the same invented number in a different costume.

### 8. Record the finding

Write the signature per `_shared/failure-signature-schema.md` — same field order, same normalisation
rules — then fill in this block. `signature`, `class`, `run id`, `log` and `notes` are the fields
`dv-sim-log-first-error` emits, so a failure routed from there keeps its vocabulary.

```
signature : <phase>|<kind>|<where>|<what>, per the shared schema
ladder    : <last rung that reported completion, and first that did not, in our own names>
symptom   : <the step 6 row, quoted>
class     : design | infrastructure | unknown
owner     : <controller configuration | PHY integration | model configuration | testbench connectivity | external IP release>
evidence  : <file and line for every number above; (derived) plus the tCK for anything converted; a person's name for anything from a datasheet>
checks    : <which of the model's check groups this build compiled in, and which it did not>
bypass    : <whether this run ran the ladder or used the init bypass>
run id    : <whatever identifies this run for us>
log       : <path, and the line range worth reading>
coverage  : <how far up the ladder this rests on; how many parameters were compared out of how many; which values are still ?>
next      : <the single named change, and what to ask the engineer to rerun>
notes     : <anything the next person would otherwise rediscover, including every value that came from a person rather than a file>
```

`owner` is free text across this pack — `dv-ral-bringup` and `dv-build-filelist-hygiene` carry
different candidate sets, because the plausible owners differ by failure domain. These five are a
third set, not an enum to match mechanically; the profile's **Area to owner map** turns the one you
pick into a name.

`class` is `infrastructure` when the fault is in how the bench configured the model or the bypass,
and `design` when the controller or PHY genuinely violates the contract. Write `unknown` when the
evidence settles neither — both transcriptions agree and the rung still fails, or the ledger ran out
before the rung could be placed. A coin toss between the other two is the wrong answer here.

`next` is the one change you would make, named as a specific edit to one named file, define or
register field — "investigate the PHY" is the absence of a next step — followed by what to ask the
engineer to rerun with it, in the profile's **Rerun convention**. Where the step 6 row ended in a
waveform handoff, `next` is that handoff: name the rung and the signals to capture, and say the
answer is owed back by a person. Where the ledger stopped early, `next` is the missing fact and its
holder.

## Gotchas

- **The model holds every speed bin and compiles one.** Quoting a number out of the wrong block is
  the most common wrong answer available here, and it is invisible in the report unless the selector
  is quoted next to the number. Find the selector's value first, then the block it selects.
- **A timing given as the greater of a time and a clock count changes with tCK.** The same datasheet
  row yields a different register value at a different frequency, so a config carried over from a
  previous project is wrong the moment the frequency moves — and wrong in the direction that still
  passes at the slower bin, which is why it survives.
- **Latency lives in three places and only one is a mode register.** Device, controller and the PHY
  interface each hold a copy. Two agreeing is the normal state of a broken system.
- **A rung that reported completion has not necessarily converged.** Delay lines have end stops, and
  a search that runs out of range commonly reports its last position as a result.
- **Timing checks and protocol checks are usually switched separately.** A build can compile one out
  and keep the other, so a run can be silent about timing and loud about nothing at all. Absence of a
  violation is evidence only once you know which groups were in.
- **The init bypass makes training bugs unreachable.** Most regressions use it, and rightly — a full
  ladder costs a great deal of simulated time. The consequence is that the ladder is exercised by a
  handful of runs, so a bug in it survives a green regression untouched. Establish which kind of run
  you are looking at before concluding anything about training.
- **"DQ swizzle within a byte is always harmless" is folklore, not a rule.** The array returns
  whatever bit positions it was given, so ordinary traffic is indifferent — but anything that
  interprets bit position is not: a fixed pattern the device itself sources or compares during
  training, data-bus inversion, and anything the controller computes across bit positions. Which
  swaps your generation permits is a databook question, not a memory-of-last-project question. Strobe
  and command swaps present instead as a whole-lane failure.
- **Several training modes restrict which commands are legal**, and a controller that leaves its
  refresh scheduler running through one produces a protocol violation naming the refresh rather than
  the rung that made it illegal. The first line that fires is not the line to read.
- **A simplified or bypass PHY model changes the question.** Many benches substitute one to keep
  runtime down, and against it the ladder cannot fail the way it fails in silicon. Confirm which PHY
  this build compiled before drawing any conclusion about training quality.
- **Neither transcription is automatically the bug.** When the model's set and the controller's
  registers disagree, the finding is the disagreement plus which one the datasheet supports — and
  that third part usually needs a person, so say so rather than picking the side you read second.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- **every number carries a file and a line**, or is marked `(derived)` with its tCK, or is attributed
  to the person who supplied it, or is `?`. A bare number here is a defect in the report.
- the speed-bin selector's value is quoted next to any number taken from the model's parameter file.
- both rungs are named — the last that completed and the first that did not — in the ladder's own
  names, not paraphrases.
- the `checks` line is filled. A clean log from a build with the model's timing checks compiled out
  supports no conclusion whatsoever.
- the `bypass` line says whether the ladder actually ran. A training verdict from a run that
  preloaded its results is not a training verdict.
- a latency finding shows all three values, or says plainly which one is `?`, and no margin is called
  adequate without the databook criterion behind it.
- the `coverage` line gives its denominators — parameters compared out of parameters needed, and how
  far up the ladder the answer rests.
- the `next` line names one change to one named file, define or register field plus what to rerun, or
  names the waveform handoff, or names the missing fact and its holder. A `next` line that could have
  been written before reading anything is not a next step.

A wrong answer typically quotes a confident timing number with no source, names a controller register
as wrong without having read the model's compiled set, or declares training healthy from a run whose
results were preloaded and whose checks were switched off.

## Done when

You can name the failing rung, the one parameter or setting behind it, its owner, the next change to
try, and every number in the report opens at the file and line printed beside it.
