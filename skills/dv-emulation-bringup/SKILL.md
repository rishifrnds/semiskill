---
name: dv-emulation-bringup
description: Triage an emulation bring-up - which compile stage reported, which stage owns the fault, what got silently black-boxed, which array stopped being a memory, and where the transactor split is wrong - then separate emulator behaviour differences from real design bugs. Use when porting a simulation environment onto an emulator, when the emulation compile dies at synthesis, partitioning or routing, when the design no longer fits, when a memory model will not map, when the first test on the emulator fails although the same test passes in simulation, or when emulation throughput has collapsed back to simulation speed.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: 'Emulation Bring-Up: Synthesisable Testbench, Transactors and Compile Triage'
  semiskill-function: design-verification
  semiskill-role: emulation-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-06-16
  semiskill-tags: emulation, co-emulation, transactor, synthesisable-testbench, partitioning, memory-model, compile-triage
---

# Emulation Bring-Up: Synthesisable Testbench, Transactors and Compile Triage

An environment that works in simulation is the wrong shape for an emulator and does not fail in one place: it
fails across compile stages with different owners, then again at run time for reasons that are not design bugs.
The mistake is attacking the error that was *reported* instead of the decision upstream. Output: **reporting
stage, owning stage, one cited upstream line, fault class, owner**, plus the reports never opened.

## When to use something else

- The **simulation** build broke: `dv-build-filelist-hygiene`, `phase: compile` in its block. The emulation
  analysis stage prints the same diagnostics against its own filelist, so route that half there; only
  *unsupported-construct* diagnostics at `analysis` stay here.
- A **simulation** run failed and you need the true first error: `dv-sim-log-first-error`, whose five-token
  `phase` vocabulary this block reuses.
- Compile **clean**, platforms disagree on a test: `dv-emulation-sim-mismatch-triage`, which step 7 hands to.
  Correct but **slow**: `dv-emulation-throughput-triage`. Which tests to port at all:
  `dv-emulation-test-porting-audit`. Signals the trace lacks: `dv-emulation-dump-strategy`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Emulation flow | [[FILL: which emulator we target, which compile stages our flow runs and in what order, and the coding guide its synthesis and memory inference follow]] | emulation infra owner |
| Compile reports | [[FILL: where each emulation compile stage writes its report or transcript, where the resource-utilisation and memory-mapping summary lands, what that summary's columns count, and how long these are kept]] | emulation infra owner |
| Stage markers | [[FILL: the strings our emulation compiler prints to open each stage and to mark an error, a warning, and an unresolved or black-boxed module]] | emulation infra owner |
| Black-box policy | [[FILL: which modules we deliberately black-box for emulation, what replaces each one, and where that list is recorded]] | emulation infra owner |
| Memory swap list | [[FILL: which memory and macro models we substitute for emulation, where the substitutes live, and how the substitution is selected]] | emulation infra owner |
| Memory load path | [[FILL: how memory contents reach the emulator at run time, and who owns the image that is loaded]] | emulation infra owner |
| Clock plan | [[FILL: where our emulation clock definitions live, which clocks are declared to the compiler, and which are derived inside the design]] | emulation infra owner |
| Transactor inventory | [[FILL: which transactors this environment uses, whether each is vendor-supplied or ours, and where the timed HDL side and the untimed host side of each live]] | emulation infra owner |
| Co-emulation mode | [[FILL: whether we run with the testbench on the host, a synthesisable embedded testbench, or in-circuit, and which co-emulation interface standard and version our transactors are written to]] | verification lead |
| Signal visibility | [[FILL: how a signal becomes visible in our emulation waveform database, and whether adding one afterwards needs a recompile]] | emulation infra owner |

**Run identity**, **Rerun convention**, **Area to owner map** and **Filelist convention** come from
`_shared/team-profile.md`. Two rows are narrower than a profile row: **Emulation flow** names the emulation
compiler and its stages, not the simulator and build command the profile's **Simulator** row names; **Stage
markers** are the *emulation* compiler's strings, not the profile's **Fatal markers** (a simulation's) nor
`dv-build-filelist-hygiene`'s **Error markers** (the simulation compiler's). **Memory swap list** says which
*model* compiled; **Memory load path** says how *contents* arrive at run time. **If a slot is unfilled, stop
and ask** — an invented stage name or report path sends the reader to a file that does not exist.

## Retrieval budget — read this before opening anything

1. **Grep and Read work on files on disk.** A pasted transcript cannot be searched: ask for the path under
   **Compile reports**, or for the text to be saved to a file. Until then reason over the pasted lines by
   eye — and say that is all you did.
2. **Never open a stage transcript with Read first.** **Grep** the **Stage markers** for stage boundaries as
   line numbers, then read bounded windows inside one stage.
3. Cap one pass at about **twelve Grep calls** and **ten windowed Reads of about 60 lines**, covering
   everything this skill opens — *including the simulation log* step 7 compares against, for which reserve 2
   Greps and up to 3 Reads, what `dv-sim-log-first-error` spends on the same job.
4. **Steps 4 to 7 are alternatives, not a sequence.** Step 2's classification table names which one applies;
   step 3 runs on every pass regardless. A pass entering more than two of steps 4 to 7 has stopped triaging
   and started browsing — that is the stopping rule.
5. Read a report whole only under about 300 lines, else Grep the section heading and read a window; over about
   200 hits the pattern is too broad, and scope every **Glob** to one directory. Stop once the failing stage,
   one cited upstream line and one owner are settled, and **state what you covered** — every count carries a
   denominator, and `coverage` names the reports never opened.

## Procedure

### 1. Get the reports on disk and find the stage boundaries

Resolve the pasted-text case first, per budget rule 1. Then **one Grep** alternating the **Stage markers** —
stage-open strings and the error string — in a single call: the hits give the line each stage began and the
line of every error, and an error's stage is the last stage-open line above it. No stage-open marker at all
means the compile never started. Record which stage reports exist on disk; one never opened goes in `coverage`.

### 2. Decide which stage broke — and do not assume it owns the fault

| Stage | Its diagnostics cite | What the stage is about | Where the fault usually is |
|---|---|---|---|
| `analysis` | a source file and a line | reading the HDL — syntax, macros, includes, unresolved names | the emulation filelist, or an unsupported construct |
| `synthesis` | a source construct, module or net | representing the design in the emulator's primitives | the synthesisable subset, step 4 |
| `partition` | partitions, domains, net counts across a cut — often no source line | fitting the design into the available resources | one decision made at `synthesis`, step 5 |
| `route` | interconnect or fabric resources | wiring the partitions together | almost always upstream of itself |
| `runtime` | the run control, a transactor, or nothing at all | the compiled design not progressing | contents, clocks or the split, steps 5 to 7 |

**The stage that reports is rarely the stage that owns.** A capacity failure at `partition` is normally an
array that stopped being recognised as a memory at `synthesis`. Read the upstream report first: step 8 records
the two stages as separate fields, and inferring one from the other is the mistake this skill exists to stop.

### 3. Read the black-box list before believing anything else

Runs on every pass, including one where the compile succeeded. **Grep** the transcript for the
unresolved-or-black-boxed marker from **Stage markers** and compare the hits to **Black-box policy** in both
directions. **In the report but not on the list** is a finding and usually the whole answer: an analog block, a
clock generator, a pad cell, encrypted IP with no emulation-ready view, a module whose source never arrived. A
black box has no internal logic, so its outputs sit at constants while the compile stays clean. **On the list
but absent from the report** is equally a finding — the real unsynthesisable model compiled, or a stale
substitute did. Absence of an error is not evidence a module is present.

### 4. Unsupported constructs, clocks and resets

**Read** one bounded window at the first `synthesis` error. What each class means, not what it says:

- **Delays.** Every `#` is gone; an emulator is cycle-based with no timing model, so an `always` block
  toggling a clock through a delay cannot exist. Clocks arrive from the emulator's resources at the design's
  clock ports, reset from the run control rather than a testbench initial block.
- **Unsupported types, operators and nets**: real-valued variables, non-constant part-selects, division or
  modulo by a non-constant, dynamic types, and internal bidirectionals, which usually must be resolved into an
  input, an output and an enable before crossing a partition boundary. **Inferred latches** are expensive.
- **Combinational loops**, which a synchronous compute model cannot settle. Reported as *broken* is not a fix:
  the tool cut the loop so the design would compile, and that node now differs from simulation.

Then **Grep** the clock report, if the flow writes one, against **Clock plan**. A clock in the report but not
the plan is either accidental — a flop clocked by a data signal — or a divider the compiler failed to
recognise, and **the unrecognised derived clock is the dangerous case**: recognised, a divider or gating cell
converts to enables and stays cycle-accurate; unrecognised, the tool either errors or treats a generated clock
as data, and the second compiles. The agent cannot rewrite RTL and call it verified: name the construct, file
and line for its owner from the profile's area map.

### 5. Memory models — the array that became logic, and the contents that never arrived

**Inference lost.** **Grep** the utilisation and memory-mapping summary named in **Compile reports** for its
memory section and read one window. Every large array should appear mapped to a memory resource; one that does
not was built from flops, at roughly the ratio of the array's bits to a memory resource's cost — enough that
one array explains a design that no longer fits. The shapes that lose the inference are tool-specific and the
authoritative list is the guide named in **Emulation flow**; the usual suspects are an unregistered read
address, contents loaded from an initial block, a second write port, or bit-level write enables finer than the
resource supports. **Grep** the RTL for that array's declaration and read one window to say which shape it is
in. That is the finding — not "the design is too big".

**Contents never arrived.** A memory image loaded by an initial block or a file-read task inside the RTL
generally does not survive into a mapped memory resource; contents must come through the **Memory load path**
at run time, before reset is released. A boot ROM full of zeroes fails nothing like a memory bug — the design
fetches, decodes a zero and dies elsewhere. Neither fault is **read-during-write**, where a behavioural array
returns new data in the write cycle and a hard memory resource returns old or undefined data: check that
against the **Memory swap list** model that compiled first.

### 6. The transactor split

**Co-emulation mode** branches this step. Under **host-based** co-emulation each transactor is a **timed,
synthesisable HDL side** driving and sampling pins every clock plus an **untimed host side** that generates,
randomises, scoreboards and prints, with transactions rather than signal events crossing between. A
**synthesisable embedded testbench** has no host side to get wrong, so the round-trip bullet does not apply and
step 4's subset rules cover the testbench too; **in-circuit** takes stimulus from real hardware through a rate
adapter, so neither bullet applies and the adapter's clock ratio and handshake, which replace them, belong to
the emulation infra owner.

For host-based, **Glob** the paths in **Transactor inventory**, **Grep** each side for the boundary
declarations — imported and exported subprograms, and the clock-control call — and read one window per side.
The emulator side owns the protocol state machine, cycle-by-cycle pin driving and sampling, and protocol timing
checks; the host side owns sequences, generation, scoreboard, coverage and all printing. Sequences, scoreboard
and coverage move across largely unchanged, but the driver and monitor *bodies* are rewritten as the
synthesisable half — porting a class-based driver instead is how a two-week bring-up becomes two months, and
only a subset of the direct programming interface will cross at all: fixed-width packed arguments, per-call
width limits, no dynamic strings or class handles.

**Crossing the boundary every cycle** is the other expensive mistake. The HDL side stops the controlled clock
while it waits for the untimed side, so a transactor that yields every cycle gives back the entire speed-up:
the run is bounded by host round trips, not the emulator. Batch a whole transaction — a burst, a packet, a
frame — not a beat; one that never yields deadlocks instead. **Ask the engineer to run the case and report the
throughput figure and the fraction of time the controlled clock was stopped**, recording which numbers came
from a person rather than a file.

### 7. It compiled, and the first test still fails

Eliminate the differences that are not bugs before filing against the RTL. **Two-state versus four-state**: a
two-state emulator starts registers at a defined value, so the X-pessimism that finds uninitialised state in
simulation is absent, and a test passing on the emulator while failing in simulation is usually a real reset
bug the emulator cannot see. Then **memory contents** never loaded (step 5), **a black box** driving constants
(step 3), **zero-delay ordering** and reset length (step 4), and **assertions**, which may not be in at all.

Then the comparison worth more than all of it: **ask the engineer to run the same test in simulation and save
the log where it can be read from disk** — the 2 Greps and 3 Reads budget rule 3 reserves — derive a signature
from each side by step 8 and compare exactly. **The same signature both sides means a design bug and emulation
is not the story.** A different signature is an environment difference; `dv-emulation-sim-mismatch-triage`
sorts it into one of five classes and its `divergence class` field carries that finer verdict, so hand it this
block; here it stays `behaviour-difference`. Before promising a waveform, spend **Signal visibility**: where
visibility is a compile-time decision a signal nobody made visible is not in the database and cannot be added
by reading harder, which is a recompile request and belongs in `next`.

### 8. Normalise into a signature, classify, and report

`_shared/failure-signature-schema.md` is the authority, applied here to **every** finding above, not only step
7's. `phase` is `compile` for anything the compiler printed at `analysis`, `synthesis`, `partition` or `route`,
`run` for anything after the design was loaded. `kind` is `tool` for a compiler diagnostic, which keeps a
build-side break out of the `fatal` bucket. `where` is the module, net or array named, cut to the last two
hierarchy levels — or, where no design object is named, as in most `partition` and `route` messages, the stage
and partition it reported on, else `?`. In `what`, on top of the schema's rules, utilisation percentages and
resource counts become `N`, partition and instance numbers become `i`, the compile identifier is dropped.

`class` is pack-wide, and the local mapping is that a substituted, missing or unloaded model is
**`infrastructure`** — an unexpected black box (step 3), a stale or wrong **Memory swap list** entry, contents
that never arrived through the **Memory load path** (step 5), a transactor split or throughput fault (step 6) —
however much its symptom feels like a design bug. **`design`** is for what the RTL must change: an
unsynthesisable construct or unrecognised clock (step 4), or a failure step 7 showed produces the same
signature in simulation. **`unknown`** when budget ran out before an upstream report settled it, or you are
reasoning from a pasted fragment — never `design` by default.

`emu stage` is the stage whose report printed the diagnostic quoted in `first err`: the *reporting* stage, the
only one readable straight off a transcript. `owning stage` is the stage whose decision caused it, equal to
`emu stage` only when cause and complaint sit in the same report — a capacity failure caused by a lost memory
inference is `emu stage: partition` with `owning stage: synthesis`. Write `owning stage: not-established` when
you never opened the upstream report. `emu fault` names the fault, not the reporting stage: a `route` failure
whose cause step 2 traced upstream takes that cause's token — `memory-inference`, `capacity` or
`partition-cut` — and only a routing failure surviving clean synthesis and partition reports is `route-resource`.

```
signature    : <phase>|<kind>|<where>|<what>, per the shared schema
phase        : compile | elab | run | finalise | post
class        : design | infrastructure | unknown
emu stage    : analysis | synthesis | partition | route | runtime
owning stage : analysis | synthesis | partition | route | runtime | not-established
emu fault    : <unsupported-construct | blackbox | memory-inference | memory-contents | capacity |
                partition-cut | route-resource | clock | transactor-split | transactor-throughput>
first err    : <verbatim diagnostic, with the report path and line>
cause        : <the upstream report line or source line that explains it, verbatim>
owner        : <module owner from the area map | emulation infra | testbench integration | external IP>
sim-vs-emu   : <same signature both sides | different signature | simulation side not run>
run id       : <whatever identifies this compile or run for us>
log          : <report path, and the line range worth reading>
coverage     : <which stage reports were opened and which were not; how many errors were classified>
notes        : <anything the next person would rediscover, including figures a person supplied>
next         : <the single named change, and the recompile or rerun to ask for>
```

`behaviour-difference` is the tenth `emu fault` token, for a step 7 environment difference. The five-token
`phase` column is offered whole because it is pack-wide, but this skill structurally reaches only `compile` and
`run`: the flow reports no separate elaboration step of its own, so nothing here is `elab`, and nothing in
scope runs after the emulator stops, so nothing is `finalise` or `post` — leave this skill out of those three
denominators. Other shared fields keep the meanings `dv-sim-log-first-error` and `dv-build-filelist-hygiene`
give them; what no file supports is `?`, never invented.

## Gotchas

- **A black box compiles clean** — no error, no warning severity anyone notices, outputs at constants. Absence
  of a diagnostic is not evidence the module is in the design.
- **The reported stage is not the responsible stage.** A design that stops fitting at `partition` or fails at
  `route` was almost always decided at `synthesis`; reading the routing report harder gives a fluent
  explanation of a symptom, and a block whose two stage fields wrongly agree.
- **One array losing memory inference can cost more than the rest of the block put together**, and the change
  that lost it — a read address that stopped being registered, a second write port — is a one-line edit that
  fails nothing until routing.
- **Initial-block and file-read memory loads do not survive**, so the design boots from zeroes and dies
  somewhere that looks nothing like a memory problem. **Read-during-write** is likewise a model difference, not
  an RTL bug: check the model that actually compiled before filing anything.
- **A transactor that talks to the host every cycle is slower than simulation, not faster**, because the round
  trip dominates and the emulator sits with its controlled clock stopped.
- **A combinational loop reported as broken is not fixed**, and **clock gating written as plain combinational
  logic** may be converted, recognised or treated as data — in both cases the silent outcome is a node that no
  longer matches simulation, so any check on it is unreliable.
- **X and Z do not survive into a two-state emulator side** — they arrive as zero, so a check written on
  `$isunknown` there is dead code, and concurrent assertions may not be in the emulated design at all.
- **Waveform visibility is often a compile-time decision** — a signal nobody made visible costs a recompile
  measured in hours, which is why **Signal visibility** is spent in step 7, before a debug session is promised.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the failing stage is named, with the report path and line number cited for it
- `emu stage` and `owning stage` are answered separately, and `owning stage` is `not-established` rather than a
  copy of `emu stage` whenever the upstream report was never opened
- the black-box list was opened and every entry is matched to **Black-box policy** or reported as a finding, in
  both directions, and `class` follows step 8 — a substituted or unloaded model is `infrastructure`
- a capacity finding names the *change* that stopped it fitting, not the total resource number, and a memory
  finding says which of the two it is — inference or contents, never both
- the signature carries no utilisation percentage, partition number or compile identifier, and `sim-vs-emu`
  rests on a simulation log that was read rather than on memory of last week's run

A wrong answer explains a routing diagnostic in fluent detail while the black-box list named the missing module
on line 12; sets both stage fields to `route` without opening the synthesis report; files a read-during-write
difference as an RTL bug; reports "the design does not fit" rather than what made it stop fitting; or quotes a
throughput figure nobody measured.

## Done when

You can name the reporting stage, the owning stage, the one upstream line behind it, the fault class, the
person who fixes it, and which stage reports you never opened.
