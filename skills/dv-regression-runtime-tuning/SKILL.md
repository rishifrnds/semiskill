---
name: dv-regression-runtime-tuning
description: Find where a slow or memory-hungry simulation actually spends its time, change one thing at a time, and report a speedup that survives being checked. Use when the nightly stops fitting its window, when one test takes hours and nobody can say why, when a run is killed for exceeding its memory limit, when someone proposes switching off coverage or waveform dumping to go faster, or when a customer reports that simulation got slower after an upgrade.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Simulation Runtime and Memory Bottleneck Diagnosis
  semiskill-function: design-verification
  semiskill-role: applications-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-04-09
  semiskill-tags: runtime, performance, profiling, memory, turnaround, regression
---

# Simulation Runtime and Memory Bottleneck Diagnosis

When the complaint is turnaround rather than correctness, the first honest question is how much of the quoted
number the simulation ever had. Wall clock carries queue wait, licence wait, build, elaboration, model load, the
run itself and post-processing, so a threefold win inside a stage worth a tenth of the total moves the nightly
window by minutes. And a speedup is a *measurement* — most reported ones compare runs that did different work.

The output is **a stage split, one named bottleneck with its evidence, and one change with a measured before and
after**, plus what it cost in verification value. This cannot start a simulation, profile one, watch a queue or time
anything: every number is read out of a file or labelled as reported, and each step needing a machine ends in a handoff.

## When to use something else

- The test is **failing**, not slow — `dv-sim-log-first-error` for one log, `dv-regression-triage-routing` for
  a night of them. Tuning a failing test optimises something nobody will keep.
- **`dv-minimal-reproducer` is the near neighbour and the easy one to load by mistake.** It shrinks a run so a
  *failure signature is preserved*; this one speeds up a run that must keep **passing**, so its stopping test is a measured ratio, not a signature.
- **Which tests are worth running at all** is `dv-compute-license-efficiency` — it stops tests, this one makes
  the survivors cheaper. If the answer here is "remove the test", hand it there.
- **Which tier a test sits in, its seed count, or what its job asks the scheduler for** is
  `dv-regression-tiering-farm`. A run killed for exceeding memory is diagnosed here, fixed there.
- The **build is broken** — `dv-build-filelist-hygiene`. You cannot say where logs or coverage output land —
  `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Stage markers | [[FILL: the lines our flow prints as it enters and leaves each stage — build, elaboration, simulation start, simulation end, post-processing — and whether each carries a timestamp]] | DV infra owner |
| Resource summary line | [[FILL: the line our flow prints at the end of a run carrying wall clock, CPU time, peak memory and simulated time, and which of those four it actually reports]] | DV infra owner |
| Profiling controls | [[FILL: what our simulator's runtime and memory profiling options are called, where the report lands, and whether it is a text file that can be read]] | DV infra owner |
| Waveform controls | [[FILL: how our flow turns dumping on and off, how a dump is limited to a scope or a time window, and which of those need a rebuild]] | DV infra owner |
| Coverage controls | [[FILL: which coverage types our runs collect, which option each is behind, and whether any of them disables optimisation in our flow]] | coverage owner |
| Runtime target | [[FILL: the turnaround this complaint is measured against — a nightly window, a per-test cap, or what a customer was told]] | verification lead |
| Noise band | [[FILL: how much run-to-run variation our farm shows for the same test on the same build, and over how many runs that was measured]] | DV infra owner |

Nine pack-wide facts live in `_shared/team-profile.md` and are read from there, not re-asked: **Log location** and
**Run identity** (step 1), **Simulator** (step 3 — profiling option names are vendor vocabulary), **Area to owner
map** and **Sign-off** (step 6), **Fatal markers**, **Pass marker** and **Rerun convention** (step 7), and
**Regression summary** (step 8). Three more come from a sibling: **Resource summary line** above is the *same fact*
`dv-minimal-reproducer` asks as **End-of-run summary**; the summary's wall clock, CPU time, cores and memory columns
are `dv-compute-license-efficiency`'s **Cost columns**; the overrun policy is `dv-regression-tiering-farm`'s **Resource request**.

**Stage markers is not the profile's Pass marker** — a stage marker says a stage ended, a pass marker says the
test passed, and a run prints every stage marker on its way to failing. Its build-side lines are what
`dv-build-filelist-hygiene` asks as **Build-finished marker**; the rest are asked only here. **If a slot is
unfilled, stop and ask** — an invented profiling option produces a stage split with fabricated numbers in it.

## Retrieval budget — read this before opening anything

The artifacts are a log that may be hundreds of megabytes, a profile report whose long tail nobody needs, and a
regression summary. All three are read by pattern, from the top, never whole.

1. **Grep, Read and Glob work on files on disk.** A wall-clock figure quoted in a chat message cannot be checked;
   ask for the path it came from, and until one exists the figure is reported, not measured.
2. **Never open a log or a profile report with Read first.** Grep for the line, then Read a bounded window around it.
3. Steps 1 to 5 are **1 Glob, 5 Greps and 6 windowed Reads**, spent exactly so: step 1, one Grep and one
   60-line Read; step 3, one Glob, one Grep and two 60-line Reads; step 4, two Greps and two 40-line Reads;
   step 5, one Grep and one 60-line Read. Step 8 runs only when the complaint is the regression rather than one
   test, and adds a second Glob, a sixth Grep and a seventh Read — so the widest first pass is **2 Globs, 6
   Greps and 7 Reads**. Nothing else.
4. Each tuning iteration in step 7 is **two Greps and one 60-line Read** of the new log — one Grep for the stage
   markers with the resource summary line, one for the fatal and pass markers.
5. If a Grep returns more than about 200 hits the pattern is too broad; narrow it before reading.
6. **Stopping rule for the diagnosis.** If step 3's two windows do not name a unit, phase or category holding a
   stated share of the time, report the stage split alone — that is where most of these end honestly.
7. **Stopping rule for the tuning.** Stop at the first of: the **Runtime target** met, three consecutive changes
   measured inside the **Noise band**, or five iterations.
8. **State what you covered** — which numbers came out of a file, which were reported, and how many stages the split accounts for against how many it left blank.

## Procedure

### 1. Split the wall clock before you open a profile

Resolve the complaint to a path first: the profile's **Log location** says where ours land, so ask for the log
under it rather than for the number again. Read the run's identity off it using the profile's **Run identity**
fact and carry that into the report's `run id` — a split with no run attached cannot be compared with the next.

Use **one Grep** alternating the **Stage markers** with the **Resource summary line** — the only Grep this step
gets — then **Read** one 60-line window at the end-of-run block. Build the split from those hits: queue wait,
build, elaboration, simulation, post-processing, each with the marker pair it came from. Leave a stage blank rather
than deriving it by subtraction; "five stages at roughly a fifth each" is itself a finding, and no one change fixes it.

### 2. Decide whether this is a compute problem at all

Compare the two numbers already in hand. **CPU time close to wall clock** means the process was computing, and a
profile will say what it computed. **CPU time well below wall clock** means it was *waiting* — licence, queue,
filesystem, host contention, or its own memory pushing the host into swap — and no profile of the design shows which.
**CPU time above wall clock** is not a fault: that stage ran on several cores, as parallel builds and multi-threaded
elaboration do and step 1's split includes, so read that ratio against wall clock times cores instead.

Waiting is not this skill's fix. Record the gap, record the bottleneck as `licence-wait`, `queue-wait` or `io`,
and hand it to whoever owns the pool or the filesystem. A run killed rather than slowed belongs to
`dv-regression-tiering-farm`'s **Resource request** — what the job asked for, and the overrun policy.

### 3. Get a profile onto disk and read only its head

**Ask the engineer to repeat the run with the option from the Profiling controls slot enabled, and to give you
the path the report was written to.** The **Simulator** fact says whose vocabulary that option belongs to; never
search for another vendor's option name.

Then **Glob** that path, **Grep** it for its section headers, and **Read** at most two 60-line windows — the head of
the time-by-category table and the head of the time-by-unit table. The tail is one-per-cent entries and has never
changed an answer. Record the top entries with their **stated share**, verbatim; one with no percentage is an impression.

### 4. Classify the hot spot

| What the profile shows | Likely cause | What proves it | The change to propose |
|---|---|---|---|
| one design unit or instance holds most of the time | a clock, monitor or checker sampling far more often than the protocol needs | its sampling construct in source, next to the event count | sample on the protocol's own edge, not the fastest clock available |
| time spread evenly, no hot unit | the event count itself is the cost — precision, oversampling, zero-delay activity | the finest time precision in the build, and events per unit of simulated time | find the precision before touching any block |
| most time in the simulator kernel, not in any unit | dumping, coverage sampling or transaction recording | which of those the run had on, from its own options | switch off exactly one, or limit it to a scope or a window |
| most time in the constraint solver | a large or heavily ordered randomisation on the per-transaction path | the constraint block on the item randomised per transaction | narrow the ranges, or hoist the randomisation off that path |
| most time in assertions or checkers | many concurrent properties, or one long window, on a fast clocking event | the property count and the clocking event beside it | qualify the property; do not slow the clock |
| most time in foreign-language calls | per-call overhead, or allocation inside the imported routine | the call count printed next to the time | batch the calls, or move allocation off the per-call path |
| most time in the reporting path | verbosity, or a message formatted outside the macro guard | the verbosity setting and the log's own size | lower verbosity first, then look at call sites |

Two **Grep** calls and two 40-line **Read** windows are the whole budget for confirming a row in source; spend them
on the unit the profile named, not the file you already suspected. For the kernel row, **Waveform controls** decides
which half of it you may even try: it says how our flow turns dumping off, how a dump is narrowed to a scope or a
time window, and which of those need a rebuild — and a narrowing that needs one is priced `unknown` in step 6.

### 5. Memory — peak, and the shape of the climb

Peak memory decides which hosts a run fits on, and becomes a *runtime* problem the moment the host swaps, after
which the profile blames whatever ran during the swapping. **Grep** the memory profile named in **Profiling
controls**, or the repeated **Resource summary line** if the flow prints one periodically, and **Read** one
window. The shape names the cause:

- **Flat after elaboration** — a static cost: design size, the coverage model, or memory declared as a dense array
  over an address range mostly never written. An associative array allocates what is written; a packed one allocates the range.
- **A monotonic climb through the run** — something is retained: scoreboard queues that never retire an
  unmatched item, analysis FIFOs nobody drains, cloned transactions kept for matching, transaction recording,
  the waveform buffer. That is a defect, not a tuning axis — report it and stop tuning.
- **Step changes at phase boundaries** — a coverage model or memory image being built. A coverpoint with no
  explicit bins is split into `auto_bin_max` bins, 64 by default, so a three-way cross of unbinned coverpoints
  allocates 262,144 bins before one of them is hit.

### 6. Choose one change, state its ceiling, and price it

Turn the profile's stated share into a **ceiling** first: a stage holding two fifths of the time cannot yield better
than about 1.7x even if removed entirely. Write it beside the **Runtime target** it has to reach, so step 7's
measurement is allowed to disagree with both.

Then price the change in one of three words. **unchanged** — the run verifies exactly what it did: scope-limited
dumping, lower verbosity, a hoisted randomisation, a cheaper sampling edge. **reduced** — the run verifies less:
coverage off, a checker disabled, a shortened test; check **Coverage controls** and the profile's **Sign-off**
fact first, because a run that no longer produces the evidence sign-off needs is not faster, it is incomplete.
**unknown** — anything touching a compile-time option, because a debug build costs whether or not dumping is on, and
those two costs must be separated before any dumping win is claimed. Propose one change and name it, its stage, its
ceiling, its price, and its `owner` from the profile's **Area to owner map** keyed on the unit the profile named — where the change is a flow option that map does not reach it, so leave `owner` blank with candidates, never a guess.

### 7. Measure it the same way, twice

**Ask the engineer to make that one change, repeat the run using the invocation from the profile's Rerun convention,
and give you the path of each resulting log.** If that convention is unfilled, leave the repeat instruction empty
rather than inventing one. Per log: one **Grep** for the stage markers and resource summary line, one **Grep** for
the fatal and pass markers, one 60-line **Read**.

- **The tuned log must carry the pass marker and no fatal marker.** If it does not, tuning stops: derive a signature
  from the new log following `_shared/failure-signature-schema.md` — same field order `<phase>|<kind>|<where>|<what>`,
  same normalisation — and hand it to `dv-sim-log-first-error`.
- **The two runs must have done the same work** — same test, same seed, same simulated time reached. Where they
  did not, normalise (wall clock per unit of simulated time, or per completed transaction) and say so.
- **The ratio must beat the Noise band**, over the repeats that band was measured across. One run against one on
  a shared farm is not a measurement, and a first run after a build reads the model cold.

An improvement smaller than the band is unmeasured, not zero: say so in the report, **ask the engineer to put the change back as it was**, and move to the next candidate. Two changes at once means neither is measured.

### 8. If the complaint is the regression, the target is the critical path

**Glob** the profile's **Regression summary**, **Grep** it for the resource columns
`dv-compute-license-efficiency`'s **Cost columns** names, and **Read** a bounded window. If the summary carries no
resource columns, say so — per-test runtime then lives only in each log, and reading a pile of them is outside this budget.

A nightly finishes when its **longest chain** finishes, not when its average test does: cutting the mean by a
fifth while one test still takes nine hours moves the window by nothing. Rank candidates by hours removed from
the longest chain, and say plainly when one test governs everything.

### 9. Report

```
run id      : <what the profile's Run identity fact names, read off this log>
stage split : <queue wait; build; elaboration; simulation; post — each with its marker pair, blank where the flow reports nothing>
bottleneck  : compute | memory | io | licence-wait | queue-wait | post-processing | unknown
evidence    : <log path and line, or profile report path and line, for every number quoted below>
owner       : <the name the Area to owner map gives for the unit named above; blank plus candidates where it does not reach>
change      : <the one change, named exactly, and the stage it targets>
price       : unchanged | reduced | unknown
ceiling     : <the best this change could give, from the share the profile stated>
baseline    : <wall clock; CPU time; peak memory; simulated time reached — blank where not reported>
tuned       : <the same four parts after the change, measured the same way>
speedup     : <the measured ratio, the two numbers behind it, the noise band it beat, and how many runs each number rests on>
verified    : <the pass-marker line number in the tuned log, or "not confirmed">
coverage    : <which numbers came out of a file and which were reported; stages accounted for and left blank; iterations tried and put back>
notes       : <the complaint in the words it was reported in, and what was tried and put back, so nobody repeats it>
```

One block per change actually measured. A blank `baseline` is a question; an estimated one is a wrong answer that reads like a measurement.

## Gotchas

- **Wall clock is not simulation time.** Queue wait, licence wait, model load over a shared filesystem and the
  coverage merge all sit inside the complaint, and many of these end at step 1 with the simulation exonerated.
- **The CPU-to-wall ratio is read in both directions.** Below one it is waiting, which no profile of the design can
  explain; above one it is cores, and a parallel build reporting four CPU hours in one wall-clock hour is behaving.
  Profile only where the two are close in a stage you know to be single-threaded.
- **Time per transaction that grows through the run is a leak, not a slow design.** Retained items make every later
  lookup slower and memory climb together, so measure the rate at three points — an average hides that shape.
- **The message you filtered out can still cost you.** The UVM report macros test verbosity before evaluating their
  message argument, so a formatting call inside `uvm_info` is free when the message is filtered; building the string
  into a variable first moves that work outside the guard and you pay for every dropped message. Confirm the guard
  in the UVM source we compile against before rewriting anyone's call sites.
- **Time precision is set by the finest one anywhere in the build.** One IP compiled at femtosecond precision makes
  the whole simulation track femtoseconds and the event count moves with it. Nothing in the log announces this.
- **Full-visibility dumping is routinely the majority of runtime**, and **toggle coverage** is the expensive
  coverage type on a large netlist — but in some flows enabling any code coverage also disables optimisations, so
  ask what sign-off requires before switching either off.
- **The constraint solver does not look like itself in a profile.** Time attributed to a sequence is often time
  spent solving its item's constraints; the fix is the constraint, not the sequence.
- **A faster run that stopped earlier is not faster.** A test ending at less simulated time, or with fewer
  transactions, always wins a wall-clock comparison — the most common false speedup by a wide margin.

## Human verification — what a wrong answer looks like

Before sending the report, check:

- both numbers came from a **resource line at a path you searched**, measured the same way; one measured and one
  reported is not a comparison
- the two runs did the same work — same test, same seed, same end condition — or the ratio is normalised and says
  so, and **exactly one thing changed** between them
- the ratio beats the noise band, the repeat count behind each number is stated, and the tuned log carries the pass marker and no fatal marker, cited by line number
- `run id` and `owner` came from the profile's facts, not from the log's file name or from whoever complained
- the price is `reduced` wherever the run now verifies less, nothing sign-off needs was switched off to buy the
  speedup, and the stage split has blanks where the flow reports nothing rather than numbers got by subtraction

A wrong answer is "three times faster" from a run that ended early, or ran on a quieter host, or had coverage switched
off, or where two changes went in together and the report credits the interesting one. Its tell is a clean ratio with
no repeat count and no noise band beside it.

## Done when

The stage split, the named bottleneck, the one change and its measured ratio fit on one screen, and whoever pays for the change can see what it cost them in verification value.
