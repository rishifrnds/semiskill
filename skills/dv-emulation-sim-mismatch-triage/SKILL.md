---
name: dv-emulation-sim-mismatch-triage
description: Classify a test that passes in simulation and fails in emulation, or the reverse, into one of five divergence classes — uninitialised state, a zero-delay race, two-state semantics, a silently transformed construct, or a substituted model — using the two logs, the emulation compile report and the two filelists. Use when a test that has passed nightly for months fails the first time it runs on the emulator, when emulation is green and simulation is red on the same commit, when someone says the emulator is wrong, or when a bring-up is stuck deciding whether to debug the RTL or the emulation build.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Simulation-versus-Emulation Divergence Triage
  semiskill-function: design-verification
  semiskill-role: emulation-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-06-22
  semiskill-tags: emulation, acceleration, x-propagation, two-state, races, transactors, bring-up
---

# Simulation-versus-Emulation Divergence Triage

A test that passed in simulation for six months and fails the first time it reaches the emulator is more often
the two builds not being the same design than a bug only the emulator can find — though the long scenarios only
emulation reaches do find real ones, and telling those apart is the job. Every divergence leaves evidence in a
readable file, so the output is **one named class, the file and line behind it, and the experiment still
outstanding**.

## When to use something else

- A single failing simulation log with no emulation side — `dv-sim-log-first-error`, which produces the failure
  signature this procedure compares across platforms.
- A night of regression failures to sort and route — `dv-regression-triage-routing`.
- Shrinking a failure you have already signed — `dv-minimal-reproducer`, after the Gotcha on shrinking here.
- The emulation **compile** failed rather than the run — `dv-build-filelist-hygiene` owns compile and elab.
- The two sides disagree about a register read — `dv-ral-bringup` classifies the register symptom first; come
  back only once the symptom is known and the platforms still differ.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Emulation platform | [[FILL: which emulation or acceleration platform we use, what its compile step is called, and the opening words its compile report prints for each row of the step 5 table — that table holds paraphrases, not strings any tool emits]] | emulation owner |
| Compile report | [[FILL: where our emulation compile writes its transformation and warning report, what the file is named, and how long it survives]] | emulation owner |
| Emulation filelist | [[FILL: which filelist the emulation build consumes, and where it is written down which entries differ from the simulation build]] | emulation owner |
| Guard macros | [[FILL: the conditional-compilation macro names that select emulation-only source, and where the list of guarded files is recorded]] | emulation owner |
| Substituted models | [[FILL: which blocks are replaced for emulation — memories, clock generators, hard macros, pads, analog — and where that substitution list lives]] | emulation owner |
| Initialisation policy | [[FILL: what the emulation build initialises flops and memories to, and what our simulation build does about X — leaves it, randomises two-state, or forces a value]] | emulation owner |
| Clock handling | [[FILL: which clocks the emulator generates and which are derived inside the RTL, and what our build does with gated clocks]] | clocking owner |
| Comparison point | [[FILL: what the two sides actually compare and when — live through transactors, at an end-of-run drain, or offline over saved outputs; which checkers exist on each side; and where an emulation run writes its log when that is somewhere the profile's Log location does not reach]] | emulation owner |

Six pack-wide facts come from `_shared/team-profile.md`: **Log location**, **Fatal markers** and **Pass marker**
(step 1), **Run identity** (steps 2 and 8), **Filelist convention** (step 3) and **Area to owner map** (steps 1,
7 and 8) — every owner named here comes from that last one, so there is no owner slot. Four rows above
deliberately differ from a profile fact of a similar name: **Compile report** is the emulation compiler's
transformation report, not the profile's **Build log location** for a *simulation* compile; **Emulation
filelist** names *which* filelist the emulation build consumes, where **Filelist convention** only governs how
filelists nest; **Comparison point** carries an emulation log path only where **Log location** does not already
reach it; and **Initialisation policy** covers both platforms, because a slot holding only the emulation half
would send step 6 to a confident wrong answer in the case step 6 exists for. **If a slot is unfilled, stop and
ask** — an invented macro name buys a fluent story about a difference between two builds you never compared.

## Retrieval budget — read this before opening anything

An emulation compile report for a full SoC routinely carries tens of thousands of warning lines, and the two run
logs are the usual hundreds of megabytes. Stop as soon as one class has a file and a line.

1. **Grep, Read and Glob work on files on disk.** They cannot search a screenshot or a tail pasted into the
   conversation; ask for the path it was written to. Until a path exists you may reason over what you were shown
   by eye — but say so, and mark the class provisional.
2. **Never open a log or the compile report with Read first.** Grep to locate a line number, then Read a bounded
   window. A filelist under about 200 lines may be Read whole, costing one of step 3's two windows; any Grep
   returning more than about 200 hits is too broad.
3. The ledger, step by step: **two Greps** in step 1, one per log; **two windowed Reads** of about 80 lines in
   step 2, one per log; **one Glob and up to four Greps** in step 3 plus **two windowed Reads** of about 60
   lines; **three anchored Greps and two windowed Reads** of about 60 lines on the compile report in step 4;
   **one Grep and one windowed Read** of about 40 lines in step 6, and the same again in step 7. Steps 5 and 8
   open nothing — **eleven Greps, one Glob and eight windowed Reads** in all.
4. Never Grep the compile report for a bare warning marker; a full-chip compile emits them by the thousand.
   Anchor each of step 4's three Greps on a report wording the **Emulation platform** slot records, adding the
   failing block's hierarchy when the first attempt is too broad.
5. **Stopping rule.** If the compile-report windows and the two RTL windows have not settled a single class,
   stop with **two** candidates ranked and the one experiment that separates them; a third guessed class is not
   an answer. Either way, state which of the five classes were examined and which were never opened.

## Procedure

### 1. Prove the two runs are comparable, and that the failing check exists on both sides

This is the step people skip and the one that saves the week. Use the **Comparison point** slot to establish
that both sides ran the same test at the same revision on the same stimulus, and — the part routinely got wrong
— that the check firing on the failing side is even compiled into the passing side. Most assertions and
class-based scoreboards do not exist on the emulator; where the checking half runs on the host at transaction
granularity, a cycle-accurate protocol assertion that fails in simulation often has no counterpart there, so
"emulation passed" means "that check never ran".

Spend **one Grep per log**, its pattern alternating the profile's **Pass marker** with its **Fatal markers**:
the simulation log under **Log location**, the emulation log there too unless **Comparison point** names
somewhere else. A side carrying neither marker never got far enough to disagree. If the check is missing on one
side, stop — that is a gap in the emulation checking, routed to the owner **Area to owner map** gives for the
failing block, not a divergence.

### 2. Fix the direction and the phase, because they halve the candidate list

Take the lowest fatal line number from step 1 on the failing side and **Read** one window of about 80 lines
starting about 60 lines before it. Read the matching window on the passing side, around the point in the test
where the other side failed, to record what that side reported there. Derive the four signature fields for each
side per `_shared/failure-signature-schema.md`, writing `?` for any field the log does not carry, and record the
profile's **Run identity** for both. The **Comparison point** slot also fixes the phase: a disagreement the logs
show mid-test is `phase: run`; one only an end-of-run drain or final check reports is `phase: finalise`; one
found after both runs ended by comparing saved outputs is `phase: post`.

- **`direction: sim-pass-emu-fail`.** Look first at what is different about the *build* — guarded source, a
  substituted model, a transformed construct, or a race the simulator resolved favourably; steps 3, 4 and 7.
- **`direction: emu-pass-sim-fail`.** Look first at unknown state: a two-state platform cannot hold an X or fail
  an X check, so its pass is weak evidence. Steps 5 and 6 carry the weight, and read the first two Gotchas
  before concluding the simulation is merely pessimistic.

### 3. Compare the two builds before reading any RTL

The cheapest explanation is that the two sides are not the same design, and it is also the most common. Use
**Glob** once to locate the simulation and emulation filelists the **Emulation filelist** slot names, then up to
**four Greps** across them:

- the **Guard macros** slot's macro names, in both filelists and in the source directories the emulation
  filelist names — an emulation-only shortcut is the commonest cause of a one-platform divergence
- each name from the **Substituted models** slot that plausibly touches the failing area, and the revision or
  release stamp each filelist points at
- the failing block's own module or file name in both filelists, to see whether the two builds reach the same
  file at all

Apply the profile's **Filelist convention** when a nested entry looks identical on both sides: the same relative
entry reached from two filelists resolves to two different files — a build difference wearing a match's
clothing. Report what you compared as a fraction: "same block filelist at the same release, 4 of 4 entries
checked" is a finding, "they look the same" is not.

### 4. Read the emulation compile report, anchored — never browsed

Open the file the **Compile report** slot names. It is the one artifact that says, in the compiler's own words,
what it built differently from what simulated, and the **Emulation platform** slot says which compiler wrote it
— two platforms describe the same transformation in different vocabulary, which is why that wording is a slot
rather than a constant here.

Use those recorded strings as **Grep** anchors — three Greps, chosen by what steps 2 and 3 suggest — then at
most two windowed **Reads** of about 60 lines around the hits naming the failing block's hierarchy. If the
wording is unfilled, step 5's table can be matched on meaning but not on text: say so and mark the
classification provisional. If the path the **Compile report** slot names holds no file — many flows discard it
after a clean compile — **ask the engineer to recompile with the transformation report kept, and to give you the
path it was written to**. The agent cannot start a compile, and until that path exists step 5's
transformed-construct row is a hypothesis.

### 5. Classify into one of five divergence classes

| Class | What it is | Where the evidence is | Direction it usually takes |
|---|---|---|---|
| `uninit-state` | a flop, memory or variable read before anything writes it. Simulation holds X; the emulator holds whatever the initialisation policy gives it, usually zero | the reset logic in RTL, plus both halves of the initialisation policy | `emu-pass-sim-fail`, because zero happens to be right |
| `zero-delay-race` | two processes ordered only by the simulator's event regions, resolved permanently the other way by a synchronous netlist that has no delta cycles | the two processes in RTL, plus the clock handling slot | either, but `sim-pass-emu-fail` more often |
| `two-state` | anything needing X or Z — tri-state nets, bus contention, `===` and `!==`, `$isunknown`, X-detecting assertions | the construct itself, and the compile report if the compiler rewrote it | `emu-pass-sim-fail`, and that pass is not evidence |
| `transformed-construct` | the compiler built something the simulator read differently — a dropped delay, an ignored initial block, a synthesis pragma the simulator treats as a comment, an inferred latch or memory | the compile report, quoted verbatim | `sim-pass-emu-fail` |
| `model-difference` | the two builds contain different logic — a guarded shortcut, a substituted memory or clock generator, a transactor in place of a VIP, or a stale revision | the two filelists and the substitution list | `sim-pass-emu-fail` |

Which rows are reachable depends on the **Emulation platform** slot, since a processor-based emulator and an
FPGA-prototyping platform transform different constructs and initialise differently. Pick the row you have a
**file and a line** for, not the one that sounds most like the symptom, and where two rows both carry evidence
rank `model-difference` first — if the builds differ, nothing below it is settled — then
`transformed-construct`, then the three needing a value comparison. A stale filelist entry written up as a race
costs a week.

### 6. Settle an unknown-state or two-state claim with the initialisation policy

Read both halves of the **Initialisation policy** slot before opening anything. Then one **Grep** for the
failing signal's declaration or its reset assignment, and one windowed **Read** of about 40 lines.

- Emulation initialises flops to zero and simulation leaves X: a signal with no reset assignment in that window
  is `divergence class: uninit-state` once you can show the assignment is absent. The design is wrong on both
  platforms; only one of them says so.
- Simulation randomises two-state initialisation instead of leaving X: the sides then differ by seed rather than
  by semantics, and a failure signature that moves between simulation seeds is the tell.
- Both halves define the value and the sides still disagree: not this class, so move on.

The decisive experiment is a handoff. **Ask the engineer to repeat the simulation with the initialisation
setting changed to whatever the emulation build uses, and to give you the path of the new log.** The agent
cannot start either platform, so until that log exists an unknown-state claim stays provisional.

### 7. Settle a race with two named processes, or do not claim one

A race is a finding only when you can name **the variable, the two processes that touch it, and the clock edge
they share**. One **Grep** for the variable and one windowed **Read** of about 40 lines, looking for the three
shapes that actually produce this:

- a sequential block assigning with `=` where another block reads the same variable on the same edge — the
  simulator's ordering decides who sees the new value, and the netlist has no such ambiguity
- a clock derived inside the RTL rather than taken from the emulator, per the **Clock handling** slot, so a flop
  on the derived clock and a flop on its source land in one time step
- an asynchronous reset released in the same time step as an active clock edge

Say plainly which reading each platform took. **Neither platform is wrong**: a race has no defined answer, so
"the emulator got it wrong" cannot be filed against the emulation build, and the fix is in the RTL, whose owner
comes from **Area to owner map**. What those windows cannot settle needs a waveform the agent cannot open —
**ask the block owner which process wrote the variable first on each side, from the two dumps at the divergence
cycle**, then record that the answer came from a person, not a file.

### 8. Write the divergence report

```
direction       : sim-pass-emu-fail | emu-pass-sim-fail
divergence class: uninit-state | zero-delay-race | two-state | transformed-construct | model-difference
signature       : <phase>|<kind>|<where>|<what>, from the side that FAILED, per the shared schema
passing side    : <the same four fields from the side that passed, or ? where it printed nothing>
phase           : run | finalise | post
class           : design | infrastructure | unknown
evidence        : <file path and line, or compile-report line number, for every claim above>
build diff      : <what step 3 compared, as a fraction, and what actually differed>
transform       : <the compile-report line quoted verbatim, or "report not on disk">
owner           : <from the profile's area map, or blank plus the candidates it makes plausible>
run id          : <the run identity of each side>
log             : <both paths, and the line range worth reading in each>
handoff         : <the one experiment a human must carry out, named>
coverage        : <which of the five classes were examined, and which were never opened>
notes           : <anything the next person would otherwise rediscover>
```

Six names are shared with `dv-sim-log-first-error`'s `signature` field and its neighbours — `signature`,
`phase`, `class`, `run id`, `log` and `notes` — so the two blocks sort together in one table. Two things about
that join must be stated rather than assumed. `signature` holds the **failing** side only, one block one
signature as the shared schema requires; what the other platform printed at the same point goes in `passing
side`, which is local here and joins with nothing. And `phase` offers three of the schema's five values, because
a compile-phase or elaboration-phase break is another skill's finding — these rows can never carry the other
two. Of the local names, take `class: infrastructure` for a substituted model, a guarded shortcut, a stale
filelist entry or a compiler transformation, all properties of the emulation build rather than the design;
`class: design` for a race, a missing reset or a reliance on X; and `class: unknown` while step 5 holds two
candidates.

## Gotchas

- **Emulation is optimistic about unknown state, not neutral about it.** A two-state platform cannot hold an X,
  so every X-detecting assertion is structurally unable to fire there; an emulation pass proves nothing about
  initialisation, contention or reset coverage, and quoting it at sign-off is expensive.
- **Simulation is optimistic about X too, in one place.** A conditional whose test is unknown takes the false
  branch and a case whose selector is unknown falls to its default — the model quietly choosing a definite path,
  not pessimism. That half is where the bugs both platforms miss are hiding.
- **A synthesis pragma is a comment to the simulator and an instruction to the emulation compiler.** A full-case
  or parallel-case pragma on a case statement that is neither builds different logic on the two platforms from
  identical text, silently, and survives for years because simulation stays green.
- **An incomplete sensitivity list holds its old value in simulation and does not in the netlist.** A legacy
  `always @(a)` block that also reads `b` simulates with a latch-like hold and elaborates as full combinational
  logic; rewriting it as `always_comb` changes the simulation and not the emulation.
- **A guarded emulation-only shortcut is a design change, not a build setting.** Shortening a calibration timer
  or bypassing a training sequence under a macro removes exactly the sequencing the failing test may depend on.
  Grep the **Guard macros** names before believing any subtler theory.
- **A substituted memory changes read latency and read-during-write, not just initial contents.** An inferred
  on-board memory commonly has a registered read port the behavioural array did not, so a combinational read
  lands a cycle late — surfacing as a protocol error hundreds of cycles downstream.
- **A dropped delay collapses sequencing that was never meant to be timing.** A small delay in a behavioural
  pad, clock generator or asynchronous handshake becomes zero in the emulation build, and two events ordered
  only by it now land in one cycle.
- **Shrinking a divergence usually destroys it.** The axes `dv-minimal-reproducer` reduces — time window,
  configuration, stimulus, tier — also decide which side of a race is taken and how long an uninitialised value
  survives. Establish the class first, then shrink, re-confirming the *divergence* at each step.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- step 1 really happened: the report says the failing check exists on **both** sides, or stops there saying it
  does not
- the build comparison in step 3 came **before** any RTL was read, and its result is a fraction
- a `divergence class: transformed-construct` verdict quotes a compile-report line **verbatim** — a
  transformation nobody read in the compiler's own words is a guess about what a compiler might do
- a `divergence class: uninit-state` or `divergence class: two-state` verdict names both halves of the
  initialisation policy, and says whether the changed-setting run was done or is still pending
- a `divergence class: zero-delay-race` verdict names a variable, two processes and one clock edge — three
  things, not a paragraph about scheduling
- `signature` holds the failing side and `passing side` the other, not the reverse; `class` follows step 8's
  mapping rather than sympathy; and the coverage line names which classes were never opened

A wrong answer typically declares a race because nothing else fitted, quotes no line from either side, and asks
the emulation team to check their model — which they will, for a day, and find nothing. The second most common
reports emulation passing on a check that was never built into the emulation image.

## Done when

You can name the divergence class, the file and line behind it, which platform's reading is the design's own
bug, and the one experiment still outstanding.
