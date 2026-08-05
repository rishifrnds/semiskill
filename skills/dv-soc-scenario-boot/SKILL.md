---
name: dv-soc-scenario-boot
description: Read a multi-agent SoC scenario against an embedded core's boot, then trace a failing software register write link by link from the firmware source to the RTL. Use when a scenario has to coordinate several agents plus a core's boot or init sequence, when firmware writes a register and the design does not respond, when the core appears to hang before the test starts, when background traffic races the boot code, or when nobody can say whether a lost write belongs to firmware, the interconnect or the RTL.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Multi-Interface Scenario Orchestration and Bare-Metal Boot Correlation
  semiskill-function: design-verification
  semiskill-role: soc-dv-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-09-16
  semiskill-tags: soc, scenario, virtual-sequence, boot, firmware, interconnect, register-trace, debug
---

# Multi-Interface Scenario Orchestration and Bare-Metal Boot Correlation

At SoC level a test stops being one sequence. It is several agents, a core running real firmware, and a
bring-up order nobody wrote down in one place — and when it fails, the sentence in the log is almost
always that a register write did not take effect. The three people who could settle that (firmware,
integration, RTL) each have good reason to believe it belongs to one of the other two, so the write gets
handed round for a week. The bug is rarely the expensive part; the handing round is.

This procedure reads the scenario's orchestration and says whether the synchronisation it depends on
held, then walks the failing write along a five-link chain — **issued, routed, accepted, applied,
observed** — stopping at the first link that cannot be confirmed from a file on disk. The output is that
break point, an evidence line under every link before it, and **one** owner.

## When to use something else

Come here when a scenario coordinates agents *and* a core, or when a software write has to be traced into
hardware. For a single failing log you have not triaged, start with `dv-sim-log-first-error` — it produces
the signature this skill carries. Once the failure is known to turn on a register's *semantics* — a policy
string, a map offset, an adapter, a predictor — that decision tree is `dv-ral-bringup`, and step 7 routes
there rather than repeating it. A night of failures belongs to `dv-regression-triage-routing`, shrinking
one you have already signed to `dv-minimal-reproducer`, and a build that never elaborated to
`dv-build-filelist-hygiene`.

## Fill this in for our team

Five facts spent here are pack-wide. They live **once**, in `_shared/team-profile.md`, and are read from
there — a second copy of a marker string drifts, and nothing can then say which copy is stale.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Log location** | steps 2, 3 and 6 — every log Grep runs against it |
| **Fatal markers**, **Pass marker** | step 2, telling a boot that stopped from a run that finished |
| **Run identity** | the handoff block, step 8 |
| **Register model source** | step 5, the other half of the address comparison |
| **Area to owner map** | step 8, when the break lands in design hierarchy rather than in firmware |

Nine more are specific to this procedure, so they are asked for here and nowhere else:

| Slot | What to fill in | Who knows |
|---|---|---|
| Scenario entry point | [[FILL: which virtual sequence or test class our multi-interface scenarios start from, and where those files live]] | SoC DV lead |
| Synchronisation points | [[FILL: how our scenarios order agents against the core — named events, barriers, or a shared configuration object — and what each named point is meant to mean]] | SoC DV lead |
| Bring-up order | [[FILL: the order this subsystem's clocks, resets and power domains come up, and which of them the core's release from reset waits on]] | integration owner |
| Firmware image and load | [[FILL: which image the core boots, how it reaches memory — back-door preload or front-door write — and at what point in the scenario that happens]] | firmware owner |
| Boot milestone markers | [[FILL: the strings or scratch-register writes our firmware emits at each boot milestone, and which file they land in]] | firmware owner |
| Symbol map | [[FILL: whether a link map or a disassembly listing is written to disk for the image we boot, and where]] | firmware build owner |
| Address header | [[FILL: which header the firmware includes for register addresses, what it is generated from, and whether that is the same description our register model is generated from]] | register owner |
| Memory attributes | [[FILL: how device or strongly-ordered regions are declared for this core, and where in the boot code they are set up]] | firmware owner |
| Bus trace | [[FILL: what our interconnect and bus monitors print per transaction, at which verbosity, and whether that verbosity was on in the failing run]] | SoC DV lead |

**Boot milestone markers is narrower than the profile's Fatal markers and Pass marker, and is not a second
name for them.** Those are what the *flow* prints about the simulation; boot milestones are what the
*firmware* prints about itself, and on many benches the two do not land in the same file — record both.
**Address header is likewise not the profile's Register model source**: the header serves the compiler,
the model serves the testbench, and step 5 exists because they can disagree.

**If a slot or a profile fact is unfilled, stop and ask. Do not guess a convention.** An invented base
address or milestone string produces a chain that looks traced and is fiction.

## Retrieval budget — read this before opening anything

An SoC log is the largest artifact in this pack — hundreds of megabytes, most of it bus traffic — and a
disassembly listing is not far behind. Nothing here is read whole.

1. **Grep, Read and Glob open files on disk.** They cannot search a log tail pasted into the conversation.
   Ask for the path, or for the text to be saved to a file and be given that path. Until a path exists you
   may reason over the pasted lines by eye — say so, and mark every link resting on it provisional.
2. **Never open a log, a listing or a generated header with Read first.** Glob to locate, Grep for a line
   number, then Read a bounded window around it.
3. The whole ledger is **1 Glob, 9 Greps and 8 windowed Reads**: scenario source — 1 Glob, 1 Grep and one
   60-line Read (step 1), then 1 Grep and one 60-line Read (step 4); the log — 2 Greps and one 80-line
   Read (step 2), 1 Grep and one 80-line Read (step 3), 1 Grep and one 80-line Read (step 6); the firmware
   side, all in step 5 — 1 Grep with a 30-line Read of the address header, 1 Grep with a 40-line Read of
   the firmware source, 1 Grep with a 40-line Read of the symbol map. Steps 7 and 8 open nothing; they
   reason over windows already read and end in handoffs.
4. If a Grep returns more than about 200 hits the pattern is too broad. Two here reliably are: a register
   name that is also a field name in fifty sibling headers, and a bare address literal that appears on
   every transaction line of a busy interconnect. Anchor the first on the header's define spelling, the
   second on the write direction.
5. **Stopping rule.** Once the log allowance is spent with the break point unsettled, stop. Report the
   links confirmed, the first unconfirmed one, and the single artifact that would settle it. Past that the
   answer is invented, and an invented answer sends a firmware bug to an RTL designer.
6. State the coverage: which links you confirmed from a file you searched, which came from a person, which
   are unknown. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Read the scenario before reading the log

**Glob** the **Scenario entry point** slot, one **Grep** for where the sub-sequences are started, one
60-line **Read** around it. Write down two lists: the intended order of the phases, and every active
master — the core is one, and so is any agent that can write the block firmware configures. That second
list is what makes step 7's last candidate findable. What you have is the *intended* order, in source;
steps 2 to 4 check it against the log, and skipping that because the source reads sensibly is how a race
survives review. The agent also cannot know which of several hundred writes is suspect, so **ask the
engineer which write is believed to have failed, in what source file and line, and what made them believe
it**.

### 2. Establish how far the boot actually got, before tracing anything

One **Grep** of the log alternating the profile's **Fatal markers** with its **Pass marker**, one **Grep**
for the **Boot milestone markers** slot, one 80-line **Read** at the last milestone hit. The highest
milestone reached bounds everything after it: a write in code that runs later was never issued, and the
chain breaks at the first link for reasons that have nothing to do with the register.

- **No milestone at all.** The core never ran the image, or not from where you think. Go to step 3 and do
  not go to step 5.
- **Milestones that stop partway and repeat.** An exception or reset loop, not slow progress — the tell is
  the same short group of lines recurring.
- **Milestones complete.** The write is genuinely in play; continue.

If the slot says milestones land in a separate console file, Grep that instead — the same one Grep, spent
elsewhere. If it says firmware signals progress by writing a scratch register rather than printing, then
milestone evidence *is* bus-trace evidence and step 6's Grep finds it. Say which of the three you used.

### 3. Compare the bring-up that happened against the one the scenario claims

One **Grep** of the log alternating the image-load line from **Firmware image and load** with the
reset-release line from **Bring-up order**, then one 80-line **Read** at the earlier hit.

- **The image was loaded after the core began fetching.** A back-door preload is instantaneous and prints
  one line near time zero; if nothing makes the core's release wait on it, the ordering is luck. The core
  executes whatever memory held at time zero — zeroes, or X — and excepts at its first instruction.
- **The core left reset before what it fetches through did.** With the interconnect or memory controller
  still in reset, some fabrics hold the request until it lifts and some error it; the two look nothing
  alike in the log.
- **The clock source has not locked**, so the core runs divided or gated: correct, a hundred times slower,
  and arriving dressed as a timeout.
- **A power domain holding the target block is still off.** Invisible here; it surfaces in step 6 as an
  error response, or as a write accepted and lost.

A front-door load is not a preload spelled differently — it is thousands of transactions and it moves the
whole timeline. Never judge it against a schedule that assumed a preload.

### 4. Check that the synchronisation held, not merely that it exists

One **Grep** of the scenario source for the name in the **Synchronisation points** slot, one 60-line
**Read** covering every trigger site and every waiter; record them as pairs with file and line. A point
with a waiter and no trigger, or a trigger and no waiter, is the finding — stop there. Four shapes, all of
which read as a hang rather than an error:

- **A trigger nobody was waiting for yet.** A plain event triggered before the other thread reached its
  wait is lost and the waiter blocks forever. A persistent flag — a state that can be *tested* rather than
  only waited on — does not have this failure; establish which of the two the scenario uses.
- **A barrier whose participant count excludes the boot.** The core's boot is not a sequence: it raises no
  objection and joins no barrier unless somebody wrote a thread that watches for a milestone and joins on
  its behalf. Where nothing does, the barrier releases mid-init.
- **Objection asymmetry.** Agent sub-sequences raise and drop objections; the DUT does not, so the run
  phase ends when the last *agent* finishes. A drain time long enough to paper over that hides the next
  bug too.
- **A fork that races the configuration.** Threads started together have no ordering, so traffic sometimes
  arrives before the block is programmed — and the failure rate then tracks host load rather than seed,
  which is the fingerprint to look for.

### 5. Resolve the software address to a bus address

Three artifacts, three **Grep** calls, three small **Read** windows — before searching the log, since
searching for the wrong number is how the budget gets spent proving a write never happened.

1. **Address header** slot — Grep the register name, Read about 30 lines. Read the window, not the line:
   the base is usually a define elsewhere in the same header and the offset alone means nothing.
2. **The firmware source** — Grep the same name, Read about 40 lines. Two things matter more than the
   address: whether the pointer is volatile, and whether the write sits inside a branch step 2 proved was
   reached.
3. **Symbol map** slot — Grep the map or listing for the symbol, Read about 40 lines, confirm the image on
   disk is the one those addresses were computed for. If no map is written, treat the address as software's
   *claim* rather than the image's content and **ask the firmware build owner to produce the map for this
   image and give you its path**.

Then account for what sits between core and target, because the bus address is usually not the header's
number: a translation stage, if the boot code enables one before this write; a boot remap window — address
zero aliased to ROM at reset and switched later, so one number names two targets at two times; a
per-master offset in the interconnect; and the access size, since a byte store into a register that only
decodes word writes is a design behaviour, not a lost write. Finally compare the header's number against
the profile's **Register model source**: generated from one description at one revision they cannot
disagree, so a disagreement *is* the finding, the owner is whoever owns that description, and step 6 need
not happen.

### 6. Find the transaction, or prove it never happened

One **Grep** of the log for the resolved address, one 80-line **Read** at the first hit — or, with no hits,
at the milestone nearest where the write should have appeared.

- **Nothing, and the Bus trace slot says that verbosity was off in this run.** You have learned nothing.
  **Ask the engineer to rerun with the interconnect monitor's verbosity raised and to give you the path of
  the new log.** Declaring "the write never happened" from a log that would not have printed it is the most
  expensive wrong answer available here.
- **Nothing, verbosity on.** The write never left the core; the chain breaks at the first link. Candidates
  in order: the code path was not reached (step 2); the pointer is not volatile and the store was dropped
  or hoisted; the store sits in a write buffer because the region is not marked device or strongly ordered
  — the **Memory attributes** slot. Owner is firmware.
- **A transaction at a different address.** Second link; step 5's list names which stage moved it.
- **A transaction with an error response.** Third link. Decode hole, target still in reset or clock-gated,
  power domain off, or a privilege or security attribute this master does not carry.
- **A transaction with a clean response.** The write reached the target and nothing readable here has
  broken. Go to step 7.

### 7. Separate a lost write from a write the design was right to ignore

With the transaction on the bus and answered cleanly, two links remain and neither is decidable from a log.
**Did the storage change**: the field may be RO, W1C, or under a lock an earlier write set; a staged or
shadow register does not take effect until a commit bit is written; an unlock key sequence may have been
missed or done out of order; the block's own clock may be gated, so the fabric answered on its behalf. The
register-semantics half of this is `dv-ral-bringup`'s access-policy table — use it rather than re-deriving
it, and route there outright if the answer turns on a policy string or a map entry. The rest needs
something the agent cannot open: **ask the engineer to open the waveform at that transaction's time and
report whether the write strobe reached the block and whether the storage changed**, or to add a back-door
read there. Never describe a waveform you were not told about.

**Did software see it**: a read-back through a cache or an undrained write buffer — the classic missing
barrier between write and check; a value the compiler kept from a non-volatile pointer; a read path
returning a shadow or a status alias; or a second master overwriting it. That last is why step 1 listed the
active masters — the scenario's own traffic is the first suspect, not the last, and the overwriting write
is usually further down the same log.

### 8. Record the chain, the break, and the one owner

Write the signature by `_shared/failure-signature-schema.md`, then fill this in. The first six lines reuse
the field names `dv-sim-log-first-error` and `dv-minimal-reproducer` emit, so the three read side by side;
the rest is this skill's extension.

```
signature  : <phase>|<kind>|<where>|<what>
phase      : compile | elab | run | finalise | post
class      : design | infrastructure | unknown
run id     : <whatever identifies this run for us>
log        : <path, and the line range worth reading>
notes      : <anything the next person would otherwise have to rediscover>
scenario   : <the entry point, and the active masters it coordinates>
boot        : <the highest milestone reached, verbatim, with its line number>
sync       : <each synchronisation point checked, trigger and waiter sites, with file and line>
broke at   : issued | routed | accepted | applied | observed
sw address : <the number the header gives, with file and line>
bus address: <the address and response the log shows on the bus, with its line number, or empty>
owner      : <one of firmware, integration, RTL, register description — one only>
coverage   : <links confirmed from a file you searched, links taken from a person, links unknown, and
              whether the bus trace verbosity was on>
```

The `phase` line keeps all five tokens so this block matches the ones its siblings emit; in practice
everything diagnosed here is `run`, and a run that never reached the testbench is a build break for
`dv-build-filelist-hygiene`. Leave a field empty rather than filling it plausibly — a blank `bus address`
is a question answered in one message, an invented one costs a day.

## Gotchas

- **The image is loaded by the testbench, not by the design**, and nothing in the RTL waits for it. If the
  scenario does not hold the core in reset until the load finishes, the ordering is luck — and it changes
  the day somebody adds a front-door load.
- **A non-volatile pointer is the most common report of "the RTL lost my write".** The compiler may drop a
  store whose value is never read, or keep it in a register. Check the listing before the bus — and note
  that volatile is only a compiler contract: it stops elision and reordering against other volatile
  accesses and does nothing whatever about the core's write buffer.
- **Device or strongly-ordered attributes, not volatile, are what push a store out to the bus.** On a core
  with a write buffer, a store into a region left normal-cacheable can be merged, reordered or simply held.
  This is the bug most often filed against the interconnect and least often owned by it.
- **A read-back that "proves" the write failed may be reading something else.** Registers with separate
  write and read paths — shadow, holding, status alias — legitimately return a different value, and a
  write-only register returns nothing meaningful at all.
- **Repeating boot milestones are an exception loop, not slow progress.** Vector table not populated, stack
  pointer never set, or an unaligned access early; the same short group of lines every few thousand cycles
  is the shape.
- **An SoC timeout usually names one waiter, not one hang.** Find the thread still waiting before hunting
  the design: a lost event trigger and a genuinely stuck design produce the identical silent log, and only
  step 4 tells them apart.
- **Objections do not cover the core.** The DUT keeps running whether or not anything is objecting, so the
  run phase can end mid-boot — and the end-of-test checks then report confidently on a machine that never
  finished starting.
- **A byte or halfword store into a word-decoded register is a design behaviour.** Check the access size on
  the transaction line before filing anything.
- **Two masters, one register.** A write that "did not stick" is very often one overwritten a hundred cycles
  later by the scenario's own traffic — evidence further down the same log, not in the RTL.
- **The address header and the register model drift independently.** Both are generated, usually by
  different flows on different schedules, and a header regenerated a week after the model is exactly the
  failure where everything works except one register at one offset.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the chain names **one** break point, and every link before it carries a real evidence line — a file path
  and line number, or a log line number
- a "the write never happened" verdict was reached only on a run whose bus trace verbosity was on
- the boot milestone quoted is the **last** one reached, verbatim, with its line number — not the one the
  reader expected the boot to reach
- nothing about the storage changing is claimed from a log alone; it came from a waveform or a back-door
  read, and whoever supplied it is named
- every synchronisation point in the block has both a trigger site and at least one waiter site, or is
  itself reported as the finding
- the owner is one name — "firmware or RTL" means step 6 was not finished
- the coverage line says which links were read and which were reported to you

A wrong answer usually reads as a confident "the RTL drops the write", derived from a log whose bus monitor
was silent, on a run where the boot never reached that code at all. The second most common is a beautiful
synchronisation review of a scenario whose core never left reset.

## Done when

You can name the link that broke, the evidence line under every link before it, and the one person who owns
it — and say which links you never confirmed.
