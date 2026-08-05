---
name: dv-emulation-test-porting-audit
description: Score simulation tests for emulator suitability on runtime, timed-testbench dependence, checker acceleratability and expected payoff, then emit a ranked porting list naming the rework each port needs. Use when emulator slots are scarce and someone has to say which tests get them, when the plan is to port the slowest tests first, when a firmware boot or a long soak run will never finish in simulation, or when a test was ported and the speed-up never appeared.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Emulation Suitability Audit of a Simulation Test List
  semiskill-function: design-verification
  semiskill-role: emulation-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-07-09
  semiskill-tags: emulation, acceleration, porting, test-selection, transactors, planning
---

# Emulation Suitability Audit of a Simulation Test List

Emulator time is the scarcest thing a verification team owns, and it is usually spent on whichever
tests take longest in simulation. That rule picks wrong more often than it picks right: a test is
slow either because the design has a great many cycles to grind through, which emulation fixes, or
because the testbench around it is doing expensive work on the host, which emulation does not touch
at all. Telling those two apart is a reading job, and it is far cheaper than the failed port that
follows from skipping it.

The output is a **ranked porting list** — one row per candidate carrying a decision, the payoff
arithmetic behind it, the rework it needs and who owns that rework — plus an honest count of how many
candidates were actually opened.

## When to use something else

This is the *prospective* audit, done from simulation-side evidence before anything is ported. Three
siblings pick up afterwards and none of them substitutes for this one. Once a job is running on the
emulator and is merely slow, its own wall clock has to be apportioned from its own log — that is
`dv-emulation-throughput-triage`, and it settles the crossing cost this skill can only estimate. Once
a ported test disagrees with its simulation result, that is `dv-emulation-sim-mismatch-triage`. Once
a ported test fails and the trace did not cover it, that is `dv-emulation-dump-strategy`.

Before porting anything, ask whether shrinking is the cheaper answer — `dv-minimal-reproducer` holds
a failure signature fixed while cutting the run down, and a test small enough after that never needs
an emulator slot at all. A single failing simulation log is `dv-sim-log-first-error`; a night of them
is `dv-regression-triage-routing`; not knowing where the test list and filelists live is
`dv-repo-orientation`. When the emulator's own compiler rejects the design,
`dv-build-filelist-hygiene` is the nearest sibling but not an exact fit — its slots describe the
simulator's compile and elaboration flow, and synthesis and partitioning diagnostics are a different
tool's vocabulary. Say so rather than routing a hardware-compile break there silently.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Emulator and co-emulation mode | [[FILL: which emulator we use, and whether our flow drives the design signal by signal from the host or through transaction-level transactors]] | emulation infra owner |
| Synthesizable subset | [[FILL: which SystemVerilog and assertion constructs our emulator compiler accepts into hardware, and where that list is written down]] | emulation infra owner |
| Existing transactors | [[FILL: which of this design's interfaces already have a synthesizable transactor, and where those live in the tree]] | emulation infra owner |
| Design top instance | [[FILL: the instance name our testbench gives the design under test, and the file that instantiates it]] | DV lead |
| Rate pair | [[FILL: the design cycles per second our regression achieves in simulation, and the cycles per second our emulator reaches on a design this size — both measured here rather than taken from a datasheet]] | emulation infra owner |
| Compile cost | [[FILL: how long a full emulator build of this design takes, and what forces a full rebuild rather than an incremental one]] | DV infra owner |
| Capacity and memory mapping | [[FILL: how much capacity headroom this design leaves, and whether our large memories map to emulator memory or stay behavioural]] | emulation infra owner |
| Runtime columns | [[FILL: which columns of our regression summary carry measured wall clock and simulated time, and whether either is recorded at all]] | DV lead |
| Emulator time allocation | [[FILL: how emulator access is rationed here — how many parallel jobs, for how long, and who decides]] | verification lead |
| Target workload | [[FILL: the workloads emulation exists to run for this project — firmware boot, long soak, performance measurement, power sequences]] | verification lead |

Four facts this procedure spends are pack-wide, live **once** in `_shared/team-profile.md`, and are
deliberately not copied into the table above.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Regression summary** — where it lands, and its format | step 1; it is both the candidate list and the only measured cost data on disk |
| **Filelist convention** — nesting, and what a relative path resolves against | step 2, separating what compiles into hardware from what stays on the host |
| **Run identity** — what identifies one run | step 8, naming the representative run behind each payoff number |
| **Area to owner map** — and what it is keyed on | step 8, routing each rework line to the person who has to do it |

**Runtime columns is narrower than the profile's Regression summary row.** The profile records where
the summary lands and its format; this slot asks only which two of its columns carry measured wall
clock and simulated time, and whether either is recorded at all. A summary can have a well-documented
format and still carry no time column anywhere, and that one fact decides whether step 4 is
arithmetic on files or a handoff to a person. The first slot above overlaps
`dv-emulation-throughput-triage`'s **Emulation platform** only on the emulator's name — that slot
also covers how a job is launched, this one also covers the co-emulation mode.

**Design top instance is not part of the profile's Filelist convention fact**, which covers nesting
and relative-path resolution and nothing more. A filelist enumerates source paths; it is not obliged
to carry a hierarchy, and mostly does not. Step 3's back-door row needs the top instance name, so
that name comes from somebody who knows it rather than from an assumption about what a `.f` file
happens to contain. **Both halves of Rate pair are spent**: the emulator rate gives step 4 its
predicted emulator wall clock, and the simulation rate gives step 4 its host-share cross-check, which
is what turns the crossing cap from `unknown` into a number.

**If a slot or a profile fact is unfilled, stop and ask. Do not guess a convention.** An invented
emulator rate turns the whole ranking into fiction that reads like a measurement, and nobody finds
out until a quarter of porting effort has gone to the wrong tests.

## Retrieval budget — read this before opening anything

A regression summary runs to thousands of rows and the testbench behind it to thousands of files.
Nothing here is read whole. Stop when the ranked list is cut to the emulator jobs actually available.

1. **Grep, Read and Glob work on files on disk.** A test list pasted into the conversation cannot be
   searched. Ask for the path the summary was written to, or for the pasted text to be saved to a
   file and be given that path. Until a path exists, the only ranking available is over the rows in
   front of you — say so, and mark every payoff number unverified.
2. **Locating the inputs costs two Globs** — one for the regression summary, one for the filelists.
   If either cannot be located, stop and ask for the path rather than sweeping the tree.
3. **The summary costs at most three windowed Reads and at most one Grep.** Read the window the
   candidates are in; if three windows do not reach the end of the file, Grep for the row pattern
   recorded with the profile's Regression summary format and Read only around the hits. **The
   boundary check in step 2 costs two Greps and one 60-line Read.**
4. **The construct sweep in step 3 is one pass over the environment, not one per test** — **ten
   Greps**: six rows swept over the testbench tree only, and two rows swept over the testbench tree
   *and* the design file set, which is two Greps each. Add **at most one narrowing call per sweep
   Grep**, and at most two 60-line Reads at the worst hit, so the sweep costs ten to twenty Greps.
   Every candidate reads its verdict out of that single sweep, and step 6 spends nothing of its own.
5. **Per candidate the budget is two Greps and one 60-line Read**, and candidates are capped at
   **12**. Rank the whole list on summary numbers first — step 4 costs no tool calls at all — then
   spend the twelve on the top of that ranking.
6. **The ceiling is two Globs, forty-seven Greps and eighteen windowed Reads**, which is rules 3 to 5
   added up: Greps 3 + 20 + 24, Reads 4 + 2 + 12. Report what was actually spent on the `ledger` line
   in step 8, against those three numbers.
7. If a Grep returns more than about 200 hits the pattern is too broad. Anchor it, or scope it to one
   directory, and count that as that Grep's one narrowing call. **If it is still over 200 hits after
   that call, stop narrowing it** — record the row as `unknown` in the sweep table with the hit count
   as the reason, and say so on step 8's `coverage` line. The delay operator and the top instance
   name followed by a dot both return hundreds of hits in any sizeable environment, so expect the
   narrowing allowance to be spent rather than spare.
8. **Stopping rule.** If the step 3 sweep finds a hard stop belonging to the shared environment
   rather than to one test, stop scoring candidates and report that instead. One missing transactor
   blocks every test on the list, and twelve individual scores will never say so.
9. **State the coverage.** "Scored 9 of 143 candidates from source; the other 134 ranked on summary
   numbers only" is a useful report. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the candidate list to a path, and find out whether it carries time at all

If the list arrived pasted rather than as a path, settle that first — budget rule 1.

Use **Glob** against the profile's Regression summary fact, then **Read** it in windows — at most the
three rule 3 allows — against the format recorded alongside it. If three windows do not reach the end
of the file, switch to the one **Grep** for the row pattern that format defines and Read only around
its hits; the row count where that happens is a property of the file, not a number this skill gets to
assert. Extract per row the test name, the status, and whatever the **Runtime columns** slot says
carries wall clock and simulated time. Three outcomes, and they are not equivalent:

- **Both columns present.** Step 4 is arithmetic and the entire list can be ranked.
- **Wall clock only.** You can rank on cost but not on payoff, because payoff needs simulated time.
  Name the column you are missing rather than ranking on the one you have and calling it payoff.
- **Neither.** Step 4 becomes a handoff — ask the engineer for a per-test wall-clock and
  simulated-time report and for the path it was written to. Rank nothing until it arrives.

### 2. Draw the hardware and host boundary before scoring anything

What gets compiled into the emulator is the design file set. Everything else — the test, the
sequences, the scoreboard, any reference model — stays on the host, and every crossing of that line
costs time no clock rate recovers.

Use **Glob** to locate the filelists, then two **Greps** to separate design entries from testbench
entries, applying the profile's Filelist convention for nesting and for what relative paths resolve
against. One 60-line **Read** at the head of the top-level filelist records how it nests — which
sub-filelists it pulls in, and which side of the line each falls on. Write both sets down: step 3
sweeps each of them, with different patterns. Take the design's top instance name from the **Design
top instance** slot rather than expecting the filelist to carry it; if that slot is unfilled, ask.
Guessing an instance name silently turns step 3's back-door row into a Grep that finds nothing and
reports clean.

Read the **Emulator and co-emulation mode** slot now, because it sets how much that boundary costs.
Signal-level co-simulation consults the host every cycle and the achievable rate collapses towards
the host's; transaction-level transactors let the design run thousands of cycles between crossings.
The same test scores differently by an order of magnitude under the two, so an audit that does not
name the mode is not an audit.

**Record that slot's answer into step 8's `co-emulation` field now, using one of its three tokens
exactly.** `co-emulation: transaction-level` when the slot says transactors carry whole transactions;
`co-emulation: signal-level` when the host drives the design signal by signal, cycle by cycle;
`co-emulation: unknown` when the slot is unfilled or names both modes without saying which this
design uses. Fill it before scoring anything — it is an input to step 4's crossing cap, not a label
on the report.

### 3. Sweep the environment once for hard stops

Six **Greps** over the **testbench tree** from step 2, one per row. Record the file and line of every
hit — later steps read this table instead of searching again.

| What the sweep looks for | Why it matters | Grep for |
|---|---|---|
| absolute-delay stimulus | the emulator has no notion of a delay that is not a clock edge, so stimulus written as delays must be re-expressed against a clock before the test means anything in hardware | the delay operator and `wait` in the driver and test files |
| force and release into the design | simulator operations on a hierarchy the emulator has compiled into gates; some flows offer a bounded equivalent at a cost per access, which is the **Synthesizable subset** slot's business rather than an assumption | `force`, `release` |
| back-door reach-in through the hierarchy | a testbench that preloads a memory or writes a register by hierarchical reference is doing it from the host, once per access | the **Design top instance** slot's name, followed by a dot |
| four-state dependence | emulators are two-state, so an unknown resolves to a definite 0 or 1 and an X check either passes vacuously or fails for a reason not in the design | `$isunknown`, `===`, and the x and z literal forms |
| host-side reference models | every call across the boundary is a crossing, and the crossing rate is what caps the speed-up | `import "DPI`, `export "DPI` |
| where the checks live | this row decides step 6 on its own, so record each hit with its path and line | `assert property`, `bind` |

**Then two more rows, swept over the design file set as well as the testbench tree — four Greps.**
These two constructs live predominantly on the design side, in gate-level netlists, hard-IP wrappers
and analog behavioural models, and a sweep scoped to the testbench would report a clean audit on a
design the emulator compiler is going to reject.

| What the sweep looks for | Why it matters | Grep for |
|---|---|---|
| timing constructs | zero-delay cycle-based hardware has nothing to back-annotate, and a hold check has no meaning in it; these almost always sit inside a delivered gate-level or IP model rather than in testbench code | `specify`, `$setuphold`, `$sdf_annotate` |
| real-number and analog modelling | outside every emulator's synthesizable subset; a real-valued port is a host-side model wherever it appears, and an AMS wrapper puts one inside the design file set | `real`, `shortreal`, `wreal` |

Record the side with every hit, because it changes what the hit means. A design-side hit blocks the
whole port until the model is swapped for a synthesizable one, which is the IP or analog owner's
work. A testbench-side hit of the same pattern is usually a host-side model that stays on the host
and costs crossings rather than blocking anything.

**These two rows are not a synthesizability check and must not be reported as one.** The authority on
what the emulator compiler accepts is the compiler, reached through step 8's handoff. Everything else
about RTL synthesizability — inferred latches, unsupported operators, partitioning, capacity — is out
of scope here, and step 8's `sweep scope` line says so rather than implying a pass.

A hit is a **candidate** hard stop, not a verdict. For each, ask whether it sits in code the audited
test actually exercises or in an unrelated agent that will simply be switched off: the first blocks
the port, the second is noise. Cross-check the four-state and real-number rows against **Capacity and
memory mapping**, since a behavioural memory array is a two-state question and a capacity question at
the same time.

### 4. Rank the whole list on payoff headroom — arithmetic, not reading

This step opens nothing. Every number came from step 1's Read and the **Rate pair** slot.

- **Predicted emulator wall clock** — simulated time divided by the emulator rate. If the summary
  records simulated time rather than cycles, convert using the design's clock period and say which
  you used. This is a **floor**, never an estimate: it assumes the design never once waits on the host.
- **Headroom** — measured simulation wall clock divided by that floor. A row whose headroom is near 1
  already runs about as fast as emulation could make it.
- **The host share, from the other half of Rate pair.** Divide the row's simulated time by the
  **simulation** rate: that is what the run would have taken had it been nothing but design work. Its
  gap to the measured wall clock is host testbench work, and the host share is that gap over the
  measured wall clock. Two sanity conditions, and failing either makes the answer `unknown` rather
  than a small number — a design-only figure *larger* than the measured wall clock means the
  regression-average rate does not describe this test, and a gap inside the summary's own timing
  resolution means the share is unresolved, not zero.
- **The crossing cap.** Speed-up is bounded by the share of the run that stays on the host, whatever
  the headroom says: if a tenth of the wall clock is host testbench work, no hardware arrangement
  makes that run more than ten times faster. The cap is one divided by the host share above, and
  under `co-emulation: signal-level` it is lower again, because the host is consulted every cycle
  rather than every transaction — say so beside the number instead of quoting a transaction-level cap
  for a signal-level flow. **The smaller of cap and headroom is the honest number**, and step 7 ranks
  on it.
- **Amortisation.** Add the **Compile cost** slot's build time once, on the first run. A test saving
  two hours a run behind a six-hour build pays back on the fourth run, not the first — so the real
  question is never "is this faster on the emulator" but "how many times will it be run".

The host share derived above is a coarse figure — the simulation rate is an average over a regression
whose tests do different amounts of host work — so label it as derived, and never let it displace a
measurement. If it fails either sanity condition, or if **Rate pair** carried no simulation-side
number, ask the engineer for a profile of where the simulation wall clock goes and the path the
profiler wrote it to; until that arrives, record the cap as unknown and say the headroom is an upper
bound only.

### 5. Score timed-testbench dependence, per candidate

Per candidate, two **Greps** and one 60-line **Read**: Grep the test's own file for the sequence or
driver it starts, Grep that sequence's file for the delay and wait forms from step 3's first row,
then Read around the class declaration to see which interface it reaches.

- **transactor-backed** — the interface appears in **Existing transactors**. The port is a
  configuration change rather than a rewrite. Cheapest, and by a distance the likeliest to happen.
- **cycle-driven** — the testbench drives the interface signal by signal on a clock with no absolute
  delays. Portable, but only once somebody writes the transactor, and that somebody is the
  interface's owner rather than whoever is running this audit.
- **delay-driven** — stimulus expressed as absolute delays against no clock at all. Every one must be
  re-expressed before the test means anything in hardware. Most expensive, and the class most
  reliably underestimated by people reading a test's name instead of its body.

`unknown` is a legitimate answer when two Greps do not settle it. Write it. The gap between
transactor-backed and delay-driven is the gap between an afternoon and a quarter, and a guess either
way wrecks the plan this list exists to support.

### 6. Score checker acceleratability from the sweep you already have

Step 3's **where the checks live** row already recorded the hits, so classify without opening
anything further.

- **in-hardware** — assertions bound into the design and accepted by the **Synthesizable subset**
  slot's list. Effectively free while they hold; their reporting still crosses to the host, so an
  assertion firing on most cycles is not free at all.
- **host-side** — a scoreboard, a reference model behind DPI, or a coverage sampler: one crossing per
  compared item. This decides most ports. A test comparing ten million beats through a host-side
  scoreboard is bound by the boundary, and the emulator's clock rate is irrelevant to it.
- **end-of-run** — the check is a comparison of a file the run wrote at the end. Cheapest of all, and
  the shape worth converting a scoreboard into when a test is otherwise a strong candidate.
- **mixed** — say which side dominates, justified by the item counts each compares, not by impression.

`checkers: unknown` is the honest answer in three cases: when budget rule 7 left that row `unknown`
for returning too many hits to narrow; when its hits sit in shared code and nothing already read says
whether the audited test exercises them; and when the classification turns on whether the
**Synthesizable subset** slot accepts a construct and that slot is unfilled. Write it in all three,
and do not borrow a candidate's step 5 budget to settle it — that budget belongs to tb-coupling, and
spending it here breaks rule 5 for the candidates further down the list.

A candidate scoring `checkers: host-side` on high headroom is not a rejection. It is the most
valuable finding this audit produces, because the rework lives in the checker and is usually worth
doing once for a whole family of tests rather than for one.

### 7. Decide and rank

Order on these keys, highest first:

1. **Workload fit.** A candidate named by **Target workload** outranks one that is not, whatever the
   arithmetic says. Emulator time exists to reach workloads simulation cannot, not to run the same
   nightly regression faster.
2. **Free of hard stops.** A candidate carrying a step 3 hard stop takes `decision: blocked` and
   leaves the ranking entirely. It is not ranked last; it is not on the list. A **design-side** hit
   from the second table blocks every candidate at once, so it belongs on the header's `sweep scope`
   line and in budget rule 8's stopping rule, not repeated down eleven `blocker` fields.
3. **The smaller of headroom and crossing cap, after build amortisation**, from step 4.
4. **Rework cost**, from steps 5 and 6 — transactor-backed ahead of cycle-driven ahead of delay-driven.

Cut the ranked list at the number of jobs **Emulator time allocation** records, and report everything
below the cut anyway, with its rank. A list that simply ends at the cut hides the case that matters
most to whoever reads it — that the eleventh candidate scored nearly as well as the third.

Assign `decision: port` above the cut with no rework, `decision: port-after-rework` when the rework
is named and owned, `decision: keep-in-simulation` when the honest number never clears the build
amortisation, and `decision: blocked` when step 3 says so.

### 8. Emit the porting list

One header block:

```
audit        : <block or subsystem, date, and the summary path the candidate list came from>
co-emulation : signal-level | transaction-level | unknown
rates        : <simulation and emulator cycles per second, and where each number came from>
compile      : <one full build, from the Compile cost slot, or unknown>
sweep scope  : <which sweep rows ran on the design file set; RTL synthesizability beyond them is not audited here>
candidates   : <n> on the list, <m> scored from source, <k> ranked on summary numbers only
coverage     : <which numbers were read from a file and which a person reported, and any sweep row left unknown for hit count>
ledger       : <Globs, Greps and Reads actually spent, against the budget's two, forty-seven and eighteen>
```

Then one block per candidate, in rank order:

```
test        : <name exactly as the summary spells it>
decision    : port | port-after-rework | keep-in-simulation | blocked
blocker     : <the step 3 hard stop with its file and line, and whether it landed design-side or testbench-side, or empty>
payoff      : <simulated time; wall clock; headroom; crossing cap; runs to pay back the build>
tb-coupling : transactor-backed | cycle-driven | delay-driven | unknown
checkers    : in-hardware | host-side | end-of-run | mixed | unknown
rework      : <the named change, or empty>
rank        : <n> because <workload fit / payoff / rework cost>
run id      : <the representative run, per the profile's Run identity fact>
evidence    : <file path and line, or summary row, behind every claim above>
notes       : <anything the next person would otherwise rediscover>
```

Route each non-empty `rework` line to an owner through the profile's Area to owner map, keyed on
whatever that map is keyed on. Leave the owner blank and list candidates rather than inferring one
from a test name — a blank owner is fixed in one message, a wrong one costs a week of somebody else's
plan. Then state the handoffs rather than implying them:

- ask the emulation infra owner to compile the current design file set and give you the path of the
  compile report, so capacity headroom becomes a measurement rather than the slot's recollection, and
  so the synthesizability this audit deliberately did not judge is judged by the tool that decides it
  — step 3's two design-scoped rows narrow that report's likely contents, they do not stand in for it
- ask them for the cycles per second a short run actually reached and the path that run wrote to, so
  the **Rate pair** slot can be replaced by a measured number
- ask the DV lead for the per-test time report if the summary carried no time column
- ask each interface owner whether a synthesizable transactor exists for the interface named in that
  candidate's rework line — **Existing transactors** goes stale faster than any other slot here

## Gotchas

- **The slowest test is not automatically the best candidate.** Simulation wall clock splits into
  design work, which emulation removes, and host testbench work, which it does not. A test slow
  because its scoreboard compares every byte in SystemVerilog gains almost nothing from a port; the
  change that pays there is in the checker.
- **Speed-up is capped by the crossing rate, not the emulator clock.** With transaction-level
  transactors one message carries a whole packet and the design runs thousands of cycles between
  crossings; under signal-level co-simulation the host is consulted every cycle. Both are called
  emulation and their payoff arithmetic differs by orders of magnitude.
- **Emulators are two-state.** Unknowns do not propagate and uninitialised state reads as a definite
  0 or 1. Every test whose pass criterion is that no X reached an output, every reset-initialisation
  check and every `$isunknown` assertion changes meaning on the way across — and the failure mode is
  a vacuous pass, which nobody investigates.
- **Zero-delay means no timing.** Back-annotation, `specify` blocks and hold checks have nothing to
  act on in cycle-based hardware. Gate-level timing tests stay in simulation, and so does anything
  whose failure signature is a timing violation rather than a functional one.
- **Asynchronous clocks become fixed ratios.** Emulator clocks are usually derived from one master
  clock by integer division, so two nominally asynchronous domains land in the same phase
  relationship run after run. A crossing test relying on that phase drifting stops finding what it
  used to, and its silence reads exactly like a pass.
- **A chatty design pays for every message.** Text printed from inside the accelerated part must
  cross to the host to be printed at all, so a test logging per transaction can lose most of its
  speed-up to message traffic. Lowering verbosity for the emulated run fixes that and changes what
  the log contains — anything downstream that greps that log has to be told.
- **Compile cost is the real gate on short tests.** An emulator build is a synthesis, partition and
  place-and-route pass measured in hours. A twenty-minute simulation test saves nothing on its first
  run and pays only if it will run hundreds of times or shares a build with tests that will.
- **Random stimulus does not port cycle for cycle.** The host still generates the constrained-random
  stream, but the cycle each transaction lands on shifts with the transactor's buffering and
  pipelining, so one seed does not reproduce one internal interleaving. Treat an emulated run as a
  new experiment, not a replay of the simulation that motivated it.
- **The memory model decides whether the design fits.** A sparsely indexed behavioural array is free
  in simulation and a real capacity question in hardware. Check **Capacity and memory mapping**
  before promising any port on a design with large memories — the answer moves the whole list rather
  than one row of it.
- **Debug turnaround is asymmetric.** Simulation records everything and pays in runtime; emulation
  runs fast and gives a bounded trace window, so a failure at hour six may need another run with the
  trace armed differently. A test only useful when you can see everything is a poor early port
  whatever its headroom.

## Human verification — what a wrong answer looks like

Before anyone plans around this list, check:

- every payoff number traces to a summary column **Runtime columns** says exists; a headroom computed
  from an invented simulated time is the failure this whole procedure exists to prevent
- the smaller of headroom and crossing cap was ranked on, not the larger, and the cap is marked
  unknown wherever the host share could not be read
- the build amortisation appears in each `payoff` line as a number of runs, not as an adjective
- `co-emulation` carries one of `signal-level`, `transaction-level` or `unknown` — step 2's three
  branches — and every rate is attributed to a measurement or to the person who gave it
- no candidate carrying a step 3 hard stop appears anywhere in the ranking
- the two design-scoped sweep rows were actually swept over the design file set and not only over the
  testbench; a `sweep scope` line that does not name that side means the timing and real-number hard
  stops were never looked for where they usually live
- `tb-coupling` and `checkers` say `unknown` wherever the budget did not settle them, rather than
  defaulting to the flattering value
- the coverage line says how many candidates were opened, and the ledger line matches the budget's
  two Globs, forty-seven Greps and eighteen Reads rather than an unstated larger spend

A wrong answer is a confident top five sorted by simulation runtime, on a testbench whose stimulus is
delay-driven and whose scoreboard is host-side. Every one of those five is months of rework wearing a
payoff number, and the list reads perfectly until the first port lands and returns a speed-up of
about two.

## Done when

Someone can take the top of the list into a planning meeting, defend each rank with a number that
came from a file, and name for every porting row the one person who has to do the rework.
