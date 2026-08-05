---
name: dv-reset-clock-scenario-matrix
description: Decide which reset, clock-gating, frequency-change and clock-mux scenarios a block or subsystem actually has to survive, then write them down as a ranked matrix where every row carries a stimulus, an observation point, a pass criterion and an owner. Use when you are writing or reviewing the reset and clock section of a verification plan, when someone asks whether the block survives a reset in the middle of a transaction, when clock gating or dynamic frequency scaling is being added, when a block that only ever saw one ideal clock is being integrated into a subsystem with several stoppable ones, or when a reset or clock bug escaped and you need to know what else was never tried.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Reset, Clock-Gating and Clock-Mux Scenario Matrix
  semiskill-function: design-verification
  semiskill-role: soc-dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-09-14
  semiskill-tags: reset, clock-gating, clock-mux, frequency-scaling, low-power, cdc, rdc, verification-plan
---

# Reset, Clock-Gating and Clock-Mux Scenario Matrix

Most blocks are never verified against the reset and clock behaviour they will actually meet. The
block bench drives one ideal clock and one ideal reset, deasserts that reset at time zero and never
asserts it again — then the block lands in a subsystem with four clocks, three of them stoppable, a
reset controller that can reset it independently of its neighbours, and firmware that changes a
divider while a burst is in flight. This turns "test reset properly" into an enumerated, ranked
matrix in which every row names a stimulus, an observation point, a pass criterion and an owner.

The output is **a scenario matrix plus the selection rule behind it** — explicitly not a full cross
product, and explicitly not a claim that any row has passed.

## When to use something else

This skill decides *which* scenarios to run; it does not debug one. A reset or clock test that has
already failed, with a log, is `dv-sim-log-first-error`; a night of them is
`dv-regression-triage-routing`; shrinking one you have already signed is `dv-minimal-reproducer`. If
the symptom is registers reading wrong values after a reset, that is `dv-ral-bringup` — its
hardware-reset check is the thing being described, and this skill only decides which resets precede
it. A build that will not compile is `dv-build-filelist-hygiene`. If you cannot yet point at the
clock and reset controller RTL or the testbench's clock generator, spend an hour in
`dv-repo-orientation` first; steps 1 and 2 assume you can.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Reset inventory | [[FILL: every reset reaching this block, its source, whether it asserts asynchronously or synchronously, and which state it deliberately does not clear]] | RTL designer |
| Clock inventory | [[FILL: every clock reaching this block, its source, its legal frequency list, and which of them can be stopped, gated or re-sourced at runtime]] | clock-controller owner |
| Clock control surface | [[FILL: which registers or pins select a source, change a divider or gate a domain, and what in our testbench is able to drive them]] | block DV owner |
| Quiescence handshake | [[FILL: whether this block implements a request-and-accept handshake before a gate or a switch, what our RTL calls those signals, and what the block may still do while a request is outstanding]] | RTL designer |
| Mandatory sequences | [[FILL: the reset, gating and clock-switch sequences our integration guide or IP release notes require, and the clause of that document stating each]] | IP integration owner |
| Static sign-off status | [[FILL: whether clock-domain and reset-domain crossing analysis has been run on this block, where the report lands, and who owns its waivers]] | static sign-off owner |
| X handling | [[FILL: whether our simulations run with X-propagation pessimism enabled, and whether a gate-level run of this block exists]] | DV infra owner |
| Scenario record | [[FILL: where our verification plan records one scenario row, and which fields a row must carry to be accepted]] | verification lead |

Three facts this procedure spends are pack-wide, live in `_shared/team-profile.md`, and are
deliberately not repeated above: **Area to owner map** routes each row in step 7, **Sign-off** decides
in step 7 what evidence a row must produce, and **Coverage output** is where step 8 looks for the bins
that close the matrix. Nothing in the table above narrows a profile fact, because the profile records
no clock or reset facts at all — this is the only place in the pack they are asked for.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented reset name, frequency
list or gating register produces a matrix that looks authoritative and describes a different design;
unlike a wrong debug answer, nobody finds out until sign-off.

## Retrieval budget — read this before opening anything

The temptation here is to read a clock controller end to end. Do not: the matrix is decided by a dozen
signal names and four structural questions.

1. **Grep, Read and Glob work on files on disk.** A specification in a document system, an unexported
   integration guide, a clock tree drawn in a slide deck — none can be opened. Those facts come from a
   person, and every row resting on one is marked provisional and attributed.
2. **Glob** first, paths only, at most **6 patterns**, each scoped to one directory: clock and reset
   controller RTL, the block's own RTL, the testbench code that drives clock and reset, and the static
   sign-off report directory. Never Glob the whole tree for source files.
3. The **Grep** budget is **12 calls**, and this is the whole ledger: up to 6 on the names in the two
   inventory slots (step 2); 1 on the quiescence handshake signals and 1 on the static sign-off report
   for this block (step 5, the second only if that report is a file on disk); 2 on the clock control
   registers and the testbench clock and reset tasks (step 6); 2 on the merged coverage report for bin
   names (step 8). If the inventories name more than six signals, Grep the six that appear in the
   mandatory sequences and record the rest as unconfirmed.
4. **Read** at most **six bounded windows of about 60 lines**: the reset synchroniser (step 2), the
   clock gate or mux instantiation (step 5), the testbench reset task and its clock generator
   (step 6), and two spare for wherever a pass criterion turns out to live.
5. A **Grep** returning more than about 200 hits means the name is a substring of something common — a
   three-letter reset name matches half the tree. Anchor it on the punctuation your RTL puts around a
   port connection before reading anything.
6. **Stopping rule.** Stop when every row marked `row status: must` carries a stimulus, an observation
   point and a pass criterion, or when the budget is spent. A matrix with more rows than criteria is
   not further along; it is further behind, because the extra rows read as coverage.
7. **State what you confirmed.** "13 of 19 inventory signals confirmed in RTL, 6 taken from the
   clock-controller owner" is a useful line. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Fix the boundary and the tier before naming a single scenario

Say what is inside the matrix: one block, or a subsystem including its clock and reset controller. The
boundary decides who generates the stimulus — with the controller outside it, every reset row is
something done *to* the block by a model you must ask for; inside it, the same rows are register
writes.

Then say which **tier** the rows are written for. This is the sentence people skip and it invalidates
everything downstream: a block bench with one ideal clock and an ideal reset physically cannot produce
most of the interesting rows, so a matrix written for it proves far less than its row count suggests.

Use **Glob**, one directory at a time, to locate the controller RTL, the block RTL and the testbench
code driving clock and reset. Record paths only. Fill **Reset inventory** and **Clock inventory** from
what the owners say; step 2 checks them.

### 2. Confirm the inventory against the RTL, and classify each reset by style

One **Grep** per name from the two inventory slots, up to the six the budget allows. Each name lands
in one of three states, and they are not interchangeable:

- **Present as a port or controller output.** Usable; note which module drives it.
- **Present but tied off at this tier.** The scenario is not waived, it is *unproducible here* — a
  statement about the bench, not the design. Record file and line; step 7 needs it as evidence.
- **Absent.** The inventory is stale, or this is a different tier or revision. Resolve that before
  writing rows: a matrix built on a stale inventory is worse than none, because it will be signed.

Then spend one bounded **Read** window on the reset synchroniser and place each reset in one style:

- **Asynchronous assert, synchronous deassert** — the correct and common arrangement. Assertion needs
  no clock; deassertion is retimed onto the destination clock so recovery timing is met. The
  load-bearing consequence: **deassertion requires clock edges in the destination domain**. Gate that
  clock before the reset releases and the block stays in reset indefinitely with nothing printed.
- **Fully synchronous** — both edges need the clock, so the reset is simply ignored while the domain is
  gated. Rows about asserting a reset into a stopped domain are meaningless here.
- **Asynchronous both edges** — deassertion is unretimed, recovery and removal timing are unmet by
  construction, and flops leave reset in different cycles. That is a finding for the RTL designer, not
  a scenario to verify. Say so and move on.

A reset that flops in one domain see and their neighbours do not is a **reset domain crossing**, and
it belongs to step 5.

### 3. Lay out the four axes, then refuse the cross product

- **A — the event**, and *which edge of it*. Assertion, deassertion and a complete pulse are three
  scenarios. A matrix carrying only "apply reset" rows has never tested deassertion, where the bugs
  are.
- **B — the clock state at the instant of the event**: running at nominal, at the slowest legal
  frequency, at the fastest, gated, stopped, mid-switch, or with its source relocking.
- **C — the activity state**: idle, one outstanding transaction, at the declared maximum outstanding,
  an error response in flight, mid-burst, or partway through a low-power entry or exit.
- **D — the domain relationship**: a single domain, or which side of a crossing sees the event first.

The product runs to thousands of cells and nobody runs it, so **the deliverable is the selection rule,
not the product**. Select on three tests in order: a document requires the row (step 4); two
independent controllers can both act inside it; or it has a pass criterion someone else can check
(step 6). A cell failing all three is not a scenario, it is a cell.

### 4. Seed the mandatory rows, then add the corners that find bugs

Take **Mandatory sequences** first and give each required sequence a row, citing the clause — "all
clocks running while reset is asserted", "reset held for at least N cycles of the slowest clock",
"quiesce before switching". If that document is not on disk, ask its owner for the clauses verbatim
and attribute them. A mandatory sequence you got slightly wrong is indistinguishable from one the
design violates.

Then the corners. These repeatedly find real bugs across many blocks:

- reset **deasserted while the domain clock is gated or stopped**, then the clock restored — does the
  block leave reset at all
- reset asserted at the maximum outstanding count on every interface, and again between the address
  and data phase of one write
- a reset pulse **shorter than the synchroniser depth**, and a second reset asserted before the first
  deassertion finished propagating
- a gate requested with a transaction outstanding — it must be refused or deferred, never granted
- a gate requested with an interrupt or error pending, and an ungate driven only by that condition
- a **switch to a source that is stopped**, and a switch away from a stopped source
- a second switch requested before the first handshake completed
- a divider changed with traffic in flight, and both extreme legal ratios including one-to-one
- both sides of a crossing reset independently, once in each order
- the destination clock of a synchroniser gated while the source keeps producing pulses

Every one is a concurrency corner — two controllers acting in the same window. That is the pattern to
keep generating from when the list runs out.

### 5. Take the structural rows out of the matrix

Some of those properties cannot be settled by simulation at all, and leaving them in buys false
confidence at full price. Read **Static sign-off status**, **Grep** the report it names for this block
(one call, only if it is a file on disk), and move these out to that owner:

- **Clock-domain crossings.** Whether a crossing is synchronised at all is structural; simulation at a
  fixed ratio will pass a missing synchroniser for a year.
- **Reset-domain crossings.** A flop reset by one reset feeding a flop reset by another can capture a
  changing value whenever the first asserts and the second does not — which a testbench that always
  asserts both together never produces.
- **Glitch-free mux and gating structure.** Confirm the shape with one bounded **Read** window on the
  instantiation, then let the static tool prove it. A gate built from a plain AND on an unlatched
  enable emits runt pulses; a latch-based integrated clock gate, sampling the enable on the inactive
  phase, cannot.
- **The quiescence handshake's protocol.** One **Grep** for the signal names in **Quiescence
  handshake** finds where it lives. Whether the block *may* accept new work after granting a quiesce
  request is a protocol property; whether it *does* is a scenario, and only the second stays here.

Say which rows left and where they went. A row deleted with no forwarding address comes back as an
escape.

### 6. Give every row an observation point and a pass criterion

A row without a criterion is an intention, not a test. Name three things per row: what drives it,
where the answer is read, and what must be true. One **Grep** for the registers in **Clock control
surface**, one for the testbench's clock and reset tasks, then up to two bounded **Read** windows,
establish whether the bench can produce the stimulus at all. "Needs testbench work" is a legitimate
result and usually the most actionable line in the document.

Criteria that are actually checkable, strongest first:

- every register is back at its reset value — that is `dv-ral-bringup`'s hardware-reset check, so name
  it rather than re-specifying it
- the protocol checker on each interface stays silent across the event, and nothing is left
  outstanding once the block is running again
- the block accepts and completes a new transaction within a stated number of cycles after the event
- no output leaves the block at X — this depends entirely on **X handling**. Under optimistic X
  semantics an unreset flop is absorbed by a conditional, so an X criterion means something only with
  pessimism enabled or on a gate-level run. Without either, record the criterion as unenforceable
  rather than writing it down as though it held.
- a pending interrupt is still pending after a gate-and-ungate cycle

**The observability trap that catches everyone.** A checker clocked on a gated clock stops evaluating
the moment the gate closes, so the window a gating row exists to examine is exactly the window nothing
is checking — and on ungate the first evaluation compares against stale state. Any row with
`clock: gated` needs its checker either on a free-running clock or explicitly disabled and re-armed
across the window. Write which, per row.

### 7. Classify, tier and route every row

Give each row a `row status`. Only two of the four values are cheap:

- `row status: must` and `row status: should` need an owner and a tier.
- `row status: waived` needs a named person who accepted the risk, per the profile's **Sign-off** fact.
- `row status: unreachable` needs **evidence** — the tie-off with file and line from step 2, an
  encoding the control register does not have, or a pin bonded to a constant. Unreachable claimed
  without evidence is how a matrix gets closed by assertion instead of by verification.

Give every row the **lowest tier at which it is producible**, from step 1. Rows needing real clock and
reset sequencing do not follow a block bench down, and saying so now stops a quarter being spent
proving something at a tier that cannot show it.

Route each row on the design hierarchy it observes, through the profile's **Area to owner map**, never
on the test name. A row observing a crossing has two candidate owners: name both and let them split
it.

### 8. Say how the matrix gets closed, and write it down

Give each `row status: must` row a coverage bin name, phrased in the same terms as the axes so a
reader can tell which cell is which. Then **ask the engineer to run the scenario regression and give
you the path of the merged coverage report** — the agent cannot start a simulation or merge a
database. Spend the budget's last two **Grep** calls on that path for the bin names and report bins
found, bins at zero, and bins absent from the report entirely. The third is the interesting one: it
means the bin was never constructed rather than never hit. The profile's **Coverage output** says
where merged coverage lands; **Scenario record** says what a row must carry to be accepted, so format
to that shape.

```
matrix   : <block or subsystem, the tier these rows are written for, author, date>
rows     : <n> must / <n> should / <n> waived / <n> unreachable, of <n> cells considered
selection: <the rule from step 3, in one sentence>
moved out: <the structural rows from step 5 and who now owns them>
coverage : <inventory signals confirmed in RTL of the total; which facts came from a person>
```

```
row       : R1
event     : reset-assert | reset-deassert | reset-pulse | gate-request | ungate | divider-change | source-switch
clock     : running | slowest | fastest | gated | stopped | switching | relocking
activity  : idle | one-outstanding | max-outstanding | error-in-flight | lowpower-transition
domains   : single | source-first | dest-first | simultaneous
row status: must | should | waived | unreachable
settled   : simulation | gate-level | static-signoff | formal | emulation | not-settleable
tier      : <the lowest tier at which this row is producible>
stimulus  : <what drives it, and whether our bench can produce it today>
observe   : <the interface, signal or register the criterion is read from>
criterion : <what must be true, in terms someone else can check>
evidence  : <file and line for a waived or unreachable row; the clause for a mandatory one>
owner     : <from the area map, or blank plus the candidates>
notes     : <anything the next person would otherwise rediscover>
```

Leave a field blank rather than filling it plausibly — a blank `owner` is answered in a minute, an
invented one costs a day and is never re-checked. The obligation field is called `row status` and not
the bare `status` several siblings use: those blocks each mean something different by that word, and
blocks compared exactly cannot carry four meanings under one name. `event`, `clock`, `activity`,
`domains` and `settled` are local here for the same reason; `owner`, `evidence`, `notes` and
`coverage` reuse the sibling spelling because they mean the same thing.

## Gotchas

- **A gated clock keeps a block in reset forever, silently.** With asynchronous assert and synchronous
  deassert, release needs edges in the destination domain. Gate that domain before the controller
  releases and the block never leaves reset — no error, no timeout, just a block that answers nothing.
  Enabling the clock before releasing the reset is the fix; the row that finds it is almost never
  written.
- **A glitch-free clock mux needs both clocks running to complete a switch.** It deselects the current
  branch, waits for that to be observed in the current domain, then selects the new one in the new
  domain. Stop either clock mid-handshake and the mux parks with no output, which looks exactly like a
  hung block and gets diagnosed as one for days.
- **Gating a clock with a transaction outstanding hangs the initiator, not the block.** The slave stops
  responding, the master's outstanding counter never returns to zero, and the interconnect wedges. That
  is why the quiescence handshake exists, and why a row that grants a gate request without checking
  outstanding transactions is testing the wrong thing.
- **A single-cycle pulse crossing into a slower domain is not reliably captured.** A two-flop
  synchroniser samples on the destination clock, so a pulse narrower than a destination period can fall
  between edges — which is why event crossings use a toggle or a handshake. A divider change that
  slows the destination can turn a crossing that always worked into one that drops events. That is a
  frequency row, not a crossing row.
- **Ratio-locked crossings stop being safe when the ratio changes.** Two clocks derived from one source
  at a fixed integer ratio may legitimately cross with less than a full synchroniser. Change the
  divider and that assumption is gone, with nothing in the RTL to notice. Ask which crossings were
  signed off as ratio-locked before writing frequency rows, and give every one of them a row.
- **Timeouts and watchdogs count cycles, and cycles are not time.** Drop the frequency and a generous
  bus timeout becomes tight; raise it and a watchdog fires late. Both extremes of the legal frequency
  list belong in the matrix for this reason alone.
- **Not every flop is reset, and RTL simulation hides it.** Datapath flops are often left unresettable
  on purpose to save area. Under optimistic X semantics an X on a condition quietly takes a branch and
  the design looks fine; under X-propagation pessimism or at gate level it does not. An unreset-flop
  row means something only under the **X handling** slot's answer.
- **A functional or software reset is not a smaller cold reset.** It deliberately preserves state —
  sticky status, debug configuration, trim, a boot-mode latch. Which state survives is a design
  decision, and verifying a warm reset as though it cleared everything reports intended behaviour as a
  bug. Get the preserved list into **Reset inventory** before writing warm-reset rows.
- **Reset asserted during a clock switch resets the mux's own state.** The synchronisers inside a
  glitch-free mux are flops like any others; resetting them mid-switch can drop the output for a cycle
  or emit a short pulse. Whether the mux's reset is in the same domain as the block's is worth one
  Grep, and it is the row people forget because it sits between two owners.

## Human verification — what a wrong answer looks like

Before the matrix is reviewed or signed, check:

- every row carries an observation point and a criterion someone other than the author could check.
  "The test passes" is not a criterion; a row without one inflates the count without adding cover.
- reset rows distinguish assertion, deassertion and a complete pulse. If every one is "apply reset",
  deassertion — where the bugs are — is uncovered.
- every `row status: unreachable` row cites a tie-off, an absent encoding or a bonded pin, with file
  and line; every `row status: waived` row names the person who accepted it.
- the structural properties from step 5 are marked `settled: static-signoff` and routed, not left in
  the matrix as simulation rows.
- each row names the lowest tier that can produce it, and the tiers are believable. Sixty rows all
  producible on a bench with one ideal clock is wrong before the content is read.
- rows with `clock: gated` say what happens to the checker across the gated window.
- the coverage line gives the confirmed-versus-reported split from step 2, and every fact from a
  person rather than a file is attributed.

A wrong answer is a tidy two-hundred-row cross product, every cell `row status: must`, no criteria, no
tiers, no evidence behind a single unreachable claim — written without opening the RTL and impossible
to argue with precisely because it is exhaustive. The second-most common wrong answer is a short,
sensible matrix whose rows are all single-controller scenarios: reset alone, gating alone, a frequency
change alone, and not one window in which two controllers act.

## Done when

Every `row status: must` row has a stimulus, an observation point, a criterion, a tier and an owner;
the structural rows have left with a named destination; and the coverage line says how much of the
inventory was confirmed from RTL rather than reported.
