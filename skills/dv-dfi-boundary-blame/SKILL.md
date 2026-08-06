---
name: dv-dfi-boundary-blame
description: Reconcile both sides of the DFI controller-PHY boundary from text evidence and name the side that broke the contract — initialisation and training handshake stalls, read and write enable timing, frequency-ratio mistakes, and update or low-power handshake deadlocks. Use when the controller team and the PHY team each say the other is wrong, when initialisation stops partway and nothing further prints, when read data comes back at the wrong cycle or not at all, or when changing a latency constant makes the failure move instead of disappear.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Controller-PHY Boundary Debug and Blame Assignment
  semiskill-function: design-verification
  semiskill-role: memory-ip-dv-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-09-30
  semiskill-tags: dfi, memory, ddr, phy, controller, boundary, handshake, training, latency, blame
---

# Controller-PHY Boundary Debug and Blame Assignment

The boundary between a memory controller and its PHY is where two teams — often two companies — meet
a contract written as a handful of handshake signals and a table of latency constants. When it stalls
or returns data at the wrong cycle, each side reads its own log, sees itself behaving exactly as its
own document says, and returns the ticket. This procedure reconciles the two text records against one
time anchor and ends with **a named side, the contract term it broke, and the line on each side that
proves it** — not a summary of either log.

## When to use something else

For a single failing log where the first error is not yet known, start with `dv-sim-log-first-error`
and come back once the failure is known to sit on this boundary. A whole night of failures needs
`dv-regression-triage-routing` first; to shrink a boundary failure you have already signed, use
`dv-minimal-reproducer`. A mismatch on the controller's own configuration registers is
`dv-ral-bringup`. A JEDEC timing check fired by the memory model mid-traffic is about the command
stream the controller issued, not the boundary — that is `dv-mem-timing-check-triage`, and refresh
and low-power behaviour on the memory side is `dv-mem-refresh-lowpower-audit`. No boundary activity
at all means the clocks or resets may never have started: `dv-reset-clock-scenario-matrix`. A build
that never elaborated is `dv-build-filelist-hygiene`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Boundary signal names | [[FILL: the exact identifiers our build uses on this boundary for initialisation-complete, training status, write enable, read enable and read valid, and the prefix they carry]] | PHY integrator |
| Boundary timing parameters | [[FILL: the exact names of the latency and enable-window constants on this boundary, and their configured values]] | PHY integrator |
| Frequency ratio | [[FILL: the controller-clock to memory-clock ratio this build runs at, where it is set, and which of the two clocks each parameter above is counted in]] | memory controller owner |
| Training step map | [[FILL: how our PHY reports training progress in text — step codes or message strings — and where the code-to-step mapping is written down]] | PHY vendor contact |
| PHY-side log | [[FILL: where the PHY's own text output lands, and whether the PHY is delivered as readable source or encrypted]] | PHY integrator |
| Boundary monitor markers | [[FILL: what our boundary protocol monitor prints on a violation, which rule identifiers it uses, and whether it is enabled by default]] | DV lead |
| Parameter dump | [[FILL: where the configured boundary parameter values are printed or written during a run, if anywhere]] | DV infra |
| Boundary ownership | [[FILL: which team owns the controller side, which owns the PHY side, and who owns the configuration that sets the parameters]] | your mentor |
| Interface revision | [[FILL: which revision of the interface specification each side claims to implement, and where that claim is recorded]] | PHY integrator |

Log location, Fatal markers, Pass marker, Infra markers, Run identity, Known-issue list and the
Area-to-owner map are pack-wide facts in `_shared/team-profile.md` — read them there. Three rows above
are **narrower than a profile row and are not the same fact**: **PHY-side log** narrows Log location,
because a PHY's training firmware often writes its own file outside the run directory and that file
is the only record of the PHY's view; **Boundary monitor markers** narrows Fatal markers, because a
boundary monitor emits rule identifiers the general flow never prints and is often off by default;
**Boundary ownership** narrows the Area-to-owner map, which resolves this whole boundary to one node
where blame needs three names — controller, PHY, and whoever owns the configuration between them.

**If a slot is unfilled, stop and ask. Do not guess a signal name or a parameter value.** Every
identifier here differs between builds, vendors and specification revisions, and a name quoted from a
specification instead of read from this build is how a signal that exists in neither side's source
ends up in a defect report.

## Retrieval budget — read this before opening anything

A training log carries one line per step, per lane, per delay setting; it reaches hundreds of
thousands of lines and about forty of them matter. Work in this order and stop once a side is named:

1. **Grep and Read work on files on disk.** Both sides of this argument usually arrive as a dozen
   lines pasted into a mail thread. Resolve them to paths first, or ask for the text to be saved and
   be given the path. Until a path exists you may reason over the pasted fragments by eye — but say
   that is what you did, and treat every conclusion as provisional. You have not searched either log.
2. At most **two Glob calls** — one for the run directory's logs, one for the PHY-side log when it
   lands somewhere else.
3. At most **eight Grep calls**, itemised: two in step 2 (one marker Grep per side), one in step 3
   (the anchor event), one in step 4 (the parameter dump), two in step 6 (one per side for the
   boundary signal names), one in step 8 (the known-issue list, only when it is a readable file), and
   one spare.
4. At most **five windowed Reads of about 60 lines** — one at the parameter dump (step 4), one per
   side at the boundary-signal region (step 6), and two spare for the anchor region and for wherever
   the family lands.
5. **Never open a boundary log with Read first.** Grep for line numbers, then Read a window around
   one of them. A Grep returning more than about 200 hits means the name is a substring of a wider
   signal family — anchor it before reading anything.
6. Stopping rule: budget spent with no side named, stop and report `side: undecided` with the one
   artifact that would settle it and how much of the boundary you covered. Past that point the answer
   is invented, and an invented blame assignment costs two teams a week.

## Procedure

### 1. Get both sides on disk, and admit which one you do not have

Resolve any pasted text to a path first — budget rule 1. Then **Glob** the run directory for the
logs, and **Glob** once more for the **PHY-side log** if that slot says it lands elsewhere.

Record what you hold. If the **PHY-side log** slot says the PHY is delivered encrypted, its source
cannot be read at all: all you will know of that side is its own text output plus the integration
document. Say so now, not in the conclusion, because it limits what the final claim may be. A
one-sided analysis can still show that one side violated its own contract, but it cannot assign
blame, and it ends at `side: undecided`.

### 2. Establish how far initialisation got, on each side separately

**One Grep per side**, each alternating the profile's Pass marker, Fatal markers and Infra markers
with the **Boundary monitor markers** and the **Training step map** strings. Two calls, and they are
the two the budget allows. Record both **Interface revision** answers while you are here — they cost
no budget, coming from the slot rather than a search, and step 7 needs them.

Do not merge the two records yet. For each side write down its last progress point with a line
number, in its own words. The most common error in this whole procedure is made here, by reading the
two logs as one narrative before step 3 has established that they can be compared at all.

If the **Boundary monitor markers** slot says the monitor is off by default, a clean boundary log is
not evidence — **ask the engineer to repeat the run with the boundary monitor enabled and give you
the path to the new log**, and mark everything until then as unmonitored.

### 3. Anchor the two time bases before comparing a single number

The two logs count time differently: a different zero, a different unit, sometimes a different clock.
**One Grep** for an event both must contain — reset deassertion, or the first mode-register write —
gives the pair of stamps and therefore the constant offset between them. Write the offset down.

With no common event the two time bases cannot be reconciled and **no timestamp comparison may appear
anywhere in your output**: compare ordering within each log only, and mark the finding provisional.
This is the step that gets skipped under pressure, and skipping it is how the effect gets placed
before the cause and the wrong side gets blamed.

### 4. Read the contract, not the code

The boundary is a set of constants both sides agreed to. **One Grep** of the **Parameter dump** for
the **Boundary timing parameters** names, then **one windowed Read** of the surrounding block — they
are usually printed together, so one window gets the set. With no parameter dump the values live only
in the configuration source: **ask the engineer for that path** rather than inferring a latency from
a waveform you cannot open.

Write each parameter down with three facts: its value, which clock its units are counted in (the
**Frequency ratio** slot answers this), and **which side supplied it**. Who supplied a number and who
must honour it are usually different teams, and that distinction is the whole blame assignment.

### 5. Classify into exactly one family

| Family | How it reads in text | Check first | Usual cause |
|---|---|---|---|
| init-handshake | a request seen, no response, then a timeout with nothing else complaining | which side drives the response, and whether its precondition was met | a precondition never met — a clock, a calibration, a required ordering |
| write-path | write accepted, read-back shifted by a whole burst or holding the previous data | the write-latency and write-enable constants against the placement observed | the constant honoured, but counted in the other clock |
| read-path | read data absent, or arriving at the wrong cycle, reported as a data mismatch rather than a protocol error | the read-enable window and the read-latency constant | the window opened in the right controller cycle but the wrong phase |
| ratio | an error that is an exact multiple or divisor of the ratio | every constant's unit clock, before any logic | one table in memory-clock units consumed as controller-clock cycles |
| update-lowpower | both sides waiting, nothing printed after | which side requested first, and whether either side may refuse | two requests overlapped and the arbitration rule is not what one side implemented |

Name one family. When two fit, the read-path or write-path row is nearly always the consequence and
the init-handshake or ratio row the cause — a boundary that started wrong stays wrong. If you are
keyed on a training step code the **Training step map** does not decode, **ask the PHY vendor contact
what that code means** and record that the answer came from a person.

### 6. Assign a side with the three-fact rule, then a class

Take the one signal at the centre of the family and record three facts, each with a path and a line:
**who drives it**, **who samples it**, and **which constant governs its placement, and which side
supplied that constant's value**. Spend **one Grep per side** for the **Boundary signal names**, then
at most **two windowed Reads** in the regions those hits point at. The three facts decide the side:

- the driver placed the edge somewhere other than the agreed constant says → the driving side, so
  `side: controller` or `side: phy` depending on which drives that signal
- the placement matches the constant, and the constant's value is wrong here → `side: integration`
- both sides behave exactly as their own tables say, and the two tables disagree → `side: integration`
- none of the three facts is demonstrable from text → `side: undecided`, plus the one artifact that
  would settle it

Quote the driver, never the reporter: the monitor sits on one side and reports what it sees, but the
side that placed the edge is the side that broke the contract.

`class` is a separate question — where the repair lands, not who is at fault. An edge placed against
the agreed constant by either side's logic is `class: design`. A wrong constant value, a unit taken
in the wrong clock, a tie-off, a configuration setting or a revision mismatch — anything repaired
outside either side's logic — is `class: infrastructure`, where most `side: integration` findings
land. If the side is undecided, or step 2 recorded the boundary as unmonitored so no placement is
demonstrable, write `class: unknown` rather than guessing.

### 7. Cross-check the revision and the optional-signal tie-offs

The specification is a superset and every real integration uses a subset, so an unconnected optional
signal is not by itself a bug; whether a tie-off is legitimate is a fact about the integration
agreement, and the **Boundary ownership** slot names who can answer it.

Now spend the two **Interface revision** answers from step 2. A signal whose meaning changed between
revisions, or that exists only in the later one, produces a failure in which neither side violates
anything — each is correct against its own document. That is `side: integration`, and naming both
revisions is what stops the week-long argument. This step opens nothing.

### 8. Check it against the known-issue list, not memory

What you can do depends on what the profile's Known-issue list resolved to. A readable file gets
**one Grep** for the signature's `where` and the distinctive fragment of `what`, compared exactly. A
tracker that Read cannot reach gets the block below handed to whoever can query it, and the check is
recorded as pending their answer. Unfilled means the check did not happen — say so, and do not call
the failure new.

### 9. Write the blame block

```
signature : <phase>|<kind>|<where>|<what>, per the shared schema
phase     : run | finalise
class     : design | infrastructure | unknown
family    : init-handshake | write-path | read-path | ratio | update-lowpower | undecided
side      : controller | phy | integration | undecided
symptom   : <the step 5 row, quoted as written>
anchor    : <the event both logs contain, and the offset between their time bases, or "none found">
evidence  : <path and line for every signal name, constant value and cycle count quoted above>
run id    : <whatever identifies this run for us>
log       : <controller-side path and line range, then PHY-side path and line range>
coverage  : <which of the two sides was actually read, and how many handshakes of how many>
notes     : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

Derive `signature` from `_shared/failure-signature-schema.md` — same field order, same normalisation
rules — and write `?` for any field not traceable to text in a log. `phase` is `run` for almost every
boundary failure and `finalise` only when the boundary check fires in the end-of-run report; the
other schema phases are dropped for the reason on that line. State `coverage` honestly: "controller
side read, PHY side not on disk; 1 handshake of 4 checked" is a useful report, and an unstated
shortcut is far worse than a stated one.

Six field names — `signature`, `phase`, `class`, `run id`, `log` and `notes` — are shared with
`dv-sim-log-first-error`'s repro block, so rows from both can be poured into one table. They sit at
different positions in the two blocks, so **join on the field name, never on row order**. `family`,
`side`, `symptom`, `anchor`, `evidence` and `coverage` are this skill's own, and that block's
`cause`, `first err` and `to repeat` have no counterpart here.

## Gotchas

- **A stall that clears when a latency constant is increased has not been diagnosed.** Widening a
  window usually hides an ordering bug by letting a late precondition arrive in time. Before
  accepting the increase, **ask the engineer to step the constant back by one, repeat the run and
  give you the path to that log** — the failure should return exactly at that boundary. A fix with no
  reversibility test is a guess wearing a number.
- **In a ratio mode a boundary signal is a vector of phases, and a check written per controller cycle
  cannot see a phase error.** The command lands in the right controller cycle and the wrong memory
  clock — the failure that survives every cycle-granular assertion and then presents as data on the
  wrong beat.
- **Units are the most common single mistake here.** A table given in memory-clock units and consumed
  as controller-clock cycles produces an error that is an exact multiple of the ratio — check that
  arithmetic before checking any logic. The tell: if logs from two builds at different ratios are on
  disk, the size of the error tracks the ratio.
- **A read-path timing error does not look like a timing error.** It arrives as a scoreboard data
  mismatch and someone debugs the data path for a day. If the mismatch is a whole-burst shift, or is
  the previous transaction's data, suspect the enable window long before the data path.
- **A training pass code is a status, not a margin.** A PHY that centred on a marginal eye reports the
  same code as one that centred on a wide one; the margin numbers are separate output and decoding
  them needs the **Training step map**. A pass code early and a data failure later in one run are no
  contradiction, and quoting the pass code as evidence of a healthy boundary is wrong.
- **The PHY's timestamps are not your timestamps**, and two sides agreeing on a number is not the
  same as agreeing on the quantity. Its stamps may be counted in its own clock from its own zero; and
  both sides may read one configuration file with one of them converting units on the way in, so
  identical values in the two parameter dumps still describe different delays.
- **An encrypted PHY leaves one column of the blame table permanently empty.** You can prove the
  controller violated its own stated contract; you cannot prove the PHY did, only that it behaved
  differently from its document. Those are different claims — the second goes to the vendor as a
  question, not to a tracker as a defect.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every signal name, constant value and cycle count is quoted with a path and a line number, and none
  is a name recognised from a specification rather than read from this build
- the `anchor` field is filled, and if it says none was found then no timestamp comparison appears
  anywhere in the output
- `side` names exactly one side, and the evidence under it identifies the **driver** of the signal,
  not the component that reported the error
- `class` says where the repair lands rather than restating the side — a wrong constant value is
  `infrastructure` even when the PHY supplied it
- the family named is the earliest that fits, not the loudest — a read-path row with an unexplained
  init-handshake stall above it in the same log has not been finished
- where the PHY source is unreadable, the conclusion says it behaved differently from its document,
  rather than that it is wrong
- `coverage` says which of the two sides was actually read, and the six shared field names are
  spelled exactly as the sibling block spells them

A wrong answer typically blames whichever side printed the message; compares raw timestamps from two
logs with no anchor; treats a widened latency constant that made the symptom vanish as a root cause;
or quotes a plausible signal name that appears in neither side's source.

## Done when

You can name one side, the one constant or edge that breaks the contract, and the line on each side
that proves it — and the other team can check your claim without asking you anything.
