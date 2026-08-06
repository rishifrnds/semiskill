---
name: dv-mem-refresh-lowpower-audit
description: Audit a decoded memory command trace against the low-power state machine — refresh interval budget and postponement, per-bank versus all-bank refresh, and self-refresh and power-down entry and exit ordering — quoting every timing number from your own databook rather than from this skill. Use when refresh scheduling looks wrong, when a self-refresh or power-down entry or exit failed, when a retention or timing check fired near a low-power window, or when you need to know whether the transitions in a trace are legal at all.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Refresh, Self-Refresh and Power-Down Entry and Exit Sequence Audit
  semiskill-function: design-verification
  semiskill-role: memory-ip-dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-16
  semiskill-tags: memory, dram, refresh, self-refresh, power-down, low-power, trace-audit, protocol
---

# Refresh, Self-Refresh and Power-Down Entry and Exit Sequence Audit

Low-power bugs are rarely loud. The refresh the controller postponed while the device sat in
power-down, the self-refresh window held one command too short, the entry issued while a bank was
still open — each is fully visible in the command trace, and each routinely survives a whole
regression without producing one error line, because the check that would have caught it was never
written. This procedure audits the trace against the state machine, and treats a violation that
nothing flagged as two findings rather than one.

Every timing value comes from the team's databook slots. This skill supplies the rules and the
arithmetic and supplies no numbers; a report containing a number the skill invented is wrong on its
face, however plausible it looks.

## When to use something else

If a simulation failed and you do not yet know what broke, start with `dv-sim-log-first-error` and
come here once the failure is known to sit near a refresh or a low-power transition. A whole night of
failures belongs to `dv-regression-triage-routing`; shrinking a failure you have already signed
belongs to `dv-minimal-reproducer`. A mode-register or configuration-register access that reads back
wrong is a register problem, not a low-power one, and belongs to `dv-ral-bringup`. If the trace does
not exist because nothing builds, that is `dv-build-filelist-hygiene`.

This is also not a substitute for the memory model's own timing checks. If the model fired a check,
that firing is the evidence and it names the parameter for you. This audit earns its keep on the
transitions the model checks loosely or not at all, and on the interval budget, which no
single-command check can see.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Device family and databook | [[FILL: which memory family and generation this trace is from, which speed bin, and the databook name and revision every number must be quoted from — by document name and clause]] | memory IP owner |
| Timing parameters | [[FILL: our databook's own names and values for refresh interval, refresh recovery all-bank and per-bank, precharge-to-refresh, minimum self-refresh residency, self-refresh exit to a first command, the longer exit for a command needing a locked DLL or retraining, power-down exit, minimum clock-enable low and high pulse, and the minimum delay to a power-down entry after a read, a write, a mode-register write and a calibration]] | memory IP owner |
| Refresh postponement allowance | [[FILL: how many refresh commands our databook lets us postpone and how many pull in, the maximum spacing between two refreshes that follows, and whether the allowance re-bases on self-refresh exit]] | memory IP owner |
| Command mnemonics | [[FILL: the exact strings this trace prints for activate, precharge, all-bank precharge, all-bank refresh, per-bank refresh, self-refresh entry and exit, power-down entry and exit, mode-register write and calibration]] | VIP or memory-model owner |
| Trace format | [[FILL: which column holds the timestamp, its unit, whether it is absolute or a delta, which columns carry rank, channel and bank, and whether clock-enable and termination state appear in the trace at all]] | VIP or memory-model owner |
| Refresh policy | [[FILL: whether our controller issues all-bank refresh, per-bank refresh or both, and whether the bank is named by the command or advanced by a counter inside the device]] | controller owner |
| Power-down variants | [[FILL: which power-down modes this design enters, whether a mode-register bit selects the fast or the slow exit, and how the trace distinguishes them]] | controller owner |
| Trace location | [[FILL: where the decoded command trace for one run is saved, and whether it is one file per rank and channel]] | your mentor |
| Waiver list | [[FILL: where a deliberately accepted deviation is recorded and how each entry is keyed]] | DV lead |

Log location, Run identity and the log markers are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than re-asking. **Trace location is narrower
than the profile's Log location**: the decoded command trace is written by the memory model or the
bus monitor, often into a different directory than the simulation log and often disabled by default,
so a team whose logs are found does not yet have a trace. If for us they are genuinely the same
directory, record that in the profile row rather than leaving it to be assumed.

Every row is spent — Trace location and Trace format in step 1, Command mnemonics in step 2, Device
family and databook, Timing parameters and Power-down variants in steps 3 to 5, Refresh postponement
allowance and Refresh policy in step 6, Waiver list in step 8.

**If a slot is unfilled, stop and ask. Do not guess a convention, and above all do not supply a
timing value from memory** — the number you remember belongs to some other speed bin, and every
conclusion resting on it is wrong in the same direction.

## Retrieval budget — read this before opening anything

A command trace covering a few milliseconds of simulated time runs to hundreds of thousands of lines.
It is a table, not prose, so nearly all of it is answerable by counting rather than by reading. Work
in this order and stop as soon as the finding is settled:

1. **Grep and Read work on files on disk.** A trace pasted into the conversation cannot be searched.
   Resolve it to a path first, or say plainly that the audit rests on the fragment you were shown and
   mark every conclusion provisional.
2. **Never open the trace with Read first.** The only unbounded Read allowed is about 40 lines at the
   top of the file, in step 1, to learn the column layout.
3. Budget over the trace: **four Greps** — the census in step 2, the transition list in step 3, the
   refresh list in step 6, and one spare for a mnemonic the census showed was mis-spelled — and **at
   most six windowed Reads of about 30 lines**, spent in steps 4 and 5 on at most three entries and
   their three exits.
4. Two further Greps outside the trace: the run's own log in step 7, and the waiver list in step 8
   when that list is a file rather than a tracker.
5. If a Grep returns more than about 400 hits, cap it, audit the capped span, and say in the coverage
   line which span that was. Do not widen the budget to cover a long trace; narrow the claim.
6. Stopping rule: if after those four Greps and six windows the entries and exits still do not
   reconcile, stop. That pattern almost always means the file interleaves ranks or channels, and a
   seventh window will not fix it — it will produce a confident, impossible sequence.
7. State what you covered: which span, how many transitions were opened, and which checks were
   skipped because the trace does not record the state they need.

## Procedure

### 1. Get the trace on disk, and learn its grammar before trusting a line of it

Resolve the path from the **Trace location** slot. If the trace was never written, this is a handoff,
not a dead end — ask the engineer to repeat the run with the memory model's command logging enabled
and to give you the path to the trace file. The agent cannot start a simulation and must not
reconstruct what one would have printed.

Then **Read** about 40 lines at the top of the file and settle the **Trace format** slot against what
is actually there: timestamp column and unit, absolute or delta, and which columns carry rank,
channel and bank. Confirm the file holds **one rank and one channel**, or that a column identifies
them. Everything after this step is pairing and subtraction, and both are meaningless across
interleaved ranks.

The unit is the most expensive thing to get wrong. A databook value in nanoseconds compared against a
trace stamped in picoseconds or in clock cycles is wrong by orders of magnitude and still looks like
a number. If the stamps are cycles, record the clock period and the conversion direction in the
notes, and convert the databook value into cycles rather than the trace into time — one conversion,
done once, is auditable.

### 2. Census the commands before analysing any of them

One **Grep**, in counting mode, over an alternation of every mnemonic in the **Command mnemonics**
slot. It is cheap, and it decides what the rest of the audit can claim.

Read the census for absences first. A mnemonic returning zero everywhere is not a design finding: it
is either a feature this run never exercised, worth reporting as a coverage gap, or a wrong string in
the slot, which invalidates every later Grep that uses it. Settle which before going on — a slot bug
reported as a design bug costs somebody a day.

### 3. Pair every entry with its exit

One **Grep**, with line numbers, over an alternation of the four transition mnemonics: self-refresh
entry and exit, power-down entry and exit. The result is the state machine's skeleton in time order,
small enough to reason over in full. Walk it once and check that:

- every entry has a later matching exit; a trailing unpaired entry is legitimate only if the run
  genuinely ended in that state, so say which of the two it is rather than dropping it
- no entry appears inside an open window of the same kind, and no entry of one kind appears inside a
  window of the other — the device does not slide between the two low-power states without an exit,
  and the databook's state diagram is the authority on which direct transitions this family has
- each window's residency, exit stamp minus entry stamp, meets the minimum residency in the **Timing
  parameters** slot, and the gap from an exit to the next entry meets the minimum clock-enable high
  pulse while the residency meets the minimum low pulse

A too-short residency is a controller finding, not a stimulus finding. Traffic arriving one cycle
after entry is legal stimulus; holding the state for the minimum is the controller's job, and an idle
timer tuned to enter aggressively is exactly how this gets generated.

### 4. Audit the entry preconditions

Choose at most three entries — the first, the shortest-residency one, and one immediately preceded by
a data burst — and **Read** a window of about 30 lines ending at each entry line. In each window:

- **Bank state.** An all-bank refresh and a self-refresh entry require every bank precharged.
  Reconstruct bank state from the activates and precharges inside the window only. If the window does
  not reach back far enough to close the last activate, say the precondition was not established
  rather than assuming it held — an unproven precondition reported as a pass is the worst output here.
- **Which power-down.** The **Power-down variants** slot decides this. A precharge power-down needs
  the banks closed; an active power-down does not, and the two have different exit parameters, so
  misreading which is in force makes every conclusion in step 5 wrong while looking rigorous.
- **Command-to-entry delays.** The last read burst must have finished, the last write must have met
  its recovery, and a mode-register write or a calibration has its own delay before an entry is
  legal. All four numbers are in the **Timing parameters** slot.
- **Refresh in flight.** An entry may not be issued until the refresh recovery time has elapsed after
  the previous refresh command.
- **Clock and termination**, only if the **Trace format** slot says they appear. Clock stability
  around entry and exit is usually a PHY-level property a decoded command trace cannot show at all —
  then ask whoever can read the PHY interface trace or the waveform, record that the answer came from
  a person, and do not report the check as passed.

### 5. Audit the exit-to-first-command delays

For the same windows, **Read** about 30 lines starting at each exit line and classify the **first**
command after the exit. The constraint is per command class, not one number: most families give a
short exit to any valid command and a longer one to a command needing a locked DLL or completed
retraining, and a read is usually the one that needs it. Applying the short number to a read is the
classic false pass, and it passes silently for years. Check the second command too — a legal first
command does not make the second legal if the second carries the longer constraint.

Report the measured delta in the trace's own unit alongside the databook value converted into that
same unit. Never put two units in one sentence.

Two exit shapes are worth naming. If the first command after a self-refresh exit is a refresh, it
belongs in step 6's arithmetic and often explains a gap there. If the first command after an exit is
another entry, the finding is a residency or pulse-width one and belongs in step 3.

### 6. Audit the refresh budget

One **Grep**, with line numbers, for the refresh mnemonics, capped per budget rule 5. Then three
checks, weakest first, and report which you actually did:

- **The average** — refreshes counted over the audited span against that span divided by the refresh
  interval. Cheap, and nearly worthless alone: a trace can meet the average while hiding a gap of
  many intervals inside it.
- **The worst gap** — subtract consecutive refresh stamps and take the largest. The **Refresh
  postponement allowance** slot gives the maximum spacing this family permits; it follows from how
  many commands may be postponed and pulled in, and it is not the number you remember from a
  different family.
- **The running deficit** — walk the stamps once, adding what elapsed time required and subtracting
  each refresh issued. The deficit must never exceed the allowance and must return to zero.
  Postponement is a credit line, not a licence, and a controller that postpones and never catches up
  produces a retention failure at temperature months later with no failing trace to show for it.

Two windows change the accounting, in opposite directions, and this is the heart of the audit. Inside
a **self-refresh** window the device refreshes itself: no refresh commands are expected, the
controller's interval clock is suspended, and whether a refresh is required immediately before entry
or after exit — and whether the deficit re-bases at exit — is in the allowance slot. Inside a
**power-down** window the device does **not** refresh itself: the interval clock keeps running and
the controller must exit to issue a refresh. A trace whose refresh gaps are all comfortable except
across power-down windows is that bug, exactly.

Finally, per-bank versus all-bank, from the **Refresh policy** slot. With per-bank refresh each bank
carries its own rate, so a healthy-looking total can hide one bank being skipped and the arithmetic
has to be per bank. Where the device advances an internal counter instead of taking a bank from the
command, the trace's bank column may be blank, zero, or the controller's guess, and the audit is then
over count and sequence only. Say which of the two it was.

### 7. Cross-check what the run itself flagged, and what it did not

One **Grep** of the run's log — the profile's Log location — around the timestamp of each finding,
for the fatal and error markers the profile records.

The silence is the second finding. A trace-visible violation that produced no assertion, no error and
no timing-check firing means the check does not exist, is not bound to this interface, or is disabled
by configuration. That is usually the more expensive of the two, because every other run in the
regression has been passing this too, and it is filed against the testbench rather than the
controller. If the check exists but printed at warning severity, say that instead — a different fix.

### 8. Record the finding

One violation, one block. Write the signature per `_shared/failure-signature-schema.md` — same field
order, same normalisation rules, so stamps become `T` and bank and row indices become `i`. The block
reuses field names from `dv-sim-log-first-error` so the two read side by side.

```
signature : <phase>|<kind>|<where>|<what>
phase     : compile | elab | run | finalise | post
class     : design | infrastructure | unknown
rule      : <the ordering rule or databook parameter that was broken, in the databook's own name>
window    : <entry line and stamp, exit line and stamp, residency, in the trace's own unit>
measured  : <what the trace shows, with the trace line numbers it was read from>
required  : <the databook value, converted into the same unit, with document and clause named>
budget    : <refreshes issued of refreshes required over the audited span; worst deficit against the allowance; worst gap>
pairing   : <n entries, n exits, n unpaired, and what the unpaired ones are>
flagged   : <the check that fired and its log line, or "nothing fired" — step 7>
owner     : <the one owner — controller RTL, memory model or VIP configuration, or the test sequence>
waiver    : <key from our waiver list, or not-matched, or list-not-readable>
run id    : <whatever identifies this run for us>
trace     : <path, and the line ranges opened>
coverage  : <span audited of span available; transitions opened of transitions found; checks skipped and why>
notes     : <unit, clock period and conversion direction; anything the next person would otherwise rediscover>
```

Findings here are `phase: run` in practice; the field keeps the pack's five tokens unchanged so the
block compares exactly against the ones the sibling skills produce. A trace bug — wrong mnemonics,
interleaved ranks, a monitor that mis-decodes — is `class: infrastructure`, and saying so early saves
the controller owner an afternoon. If a line cannot be filled from text on disk, write `?`. **State
coverage honestly**: "audited the first 400 refreshes of about 9000, spanning the first two of eleven
power-down windows" is a useful report, and an unstated shortcut is far worse than a stated one.

## Gotchas

- **Power-down does not refresh; self-refresh does.** Nearly everything else about the two looks
  alike in a trace, and this is the difference that decides whether a refresh gap is a violation or
  the expected shape of a correct window.
- **A postponed refresh is not a skipped refresh — until it is.** The allowance is a credit line that
  has to be repaid, so the only meaningful check is the running deficit. Every trace that passes on
  average and then fails at temperature failed that one.
- **Units bite twice** — once when a databook value in time meets a trace stamped in cycles, and
  again when the trace comes from a different speed bin than the databook page, which silently
  re-scales every cycle-based conclusion. The clock period belongs in the notes line.
- **Active and precharge power-down have different exit constraints**, and a mode-register bit often
  selects a fast or a slow exit within one of them. Auditing exits without settling which is in force
  produces a rigorous-looking pass that means nothing.
- **A per-bank refresh blocks one bank, not the device.** An activate to another bank inside the
  per-bank recovery window is legal. Flagging all of them is the commonest false positive here, and a
  false-positive machine destroys trust in an audit faster than a missed bug does.
- **The bank field on a per-bank refresh may be a fiction.** Where the device advances the bank with
  an internal counter, that column is whatever the monitor chose to print. Do not audit round-robin
  order from it unless the Refresh policy slot says the number is real.
- **The interval clock starts after initialisation, not at line 1.** Auditing the deficit from the
  top of the file, through init and training, manufactures a deficit that was never there. Find where
  normal traffic begins and start the arithmetic at that line.
- **Mixing all-bank and per-bank refresh in one run is constrained**, and the constraint usually
  touches the internal bank counter. If the census shows both, raise it as a question against the
  databook rather than deciding it — families genuinely differ here.
- **A trace is a decode, not the truth.** A missing rank or channel column, or a mis-decoded chip
  select, turns two devices' legal command streams into one impossible sequence that reads as a
  spectacular controller bug. Confirm one rank per file before believing any pairing.
- **Nothing firing is a result, not a clean bill.** A trace-visible violation with a silent log means
  the check is missing, unbound or disabled, and that finding outlives the bug that exposed it.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every timing number appears **twice** — measured, with trace line numbers, and required, from the
  databook slot with its document and clause — and both in the same unit
- no number in the report came from this skill, from recollection of a standard, or from another
  speed bin
- an entry-precondition finding names the bank and the line of the activate that left it open;
  "banks were open" with no line is not a finding
- the pairing counts reconcile — entries equal exits plus unpaired — and each unpaired one is
  explained as end-of-trace or as a finding
- the refresh conclusion says which of the three checks was done, over which span, and per bank where
  the policy is per-bank
- no activate to a bank other than the one being refreshed is reported as a violation
- the `flagged` line is filled in, so a silent check is visible as its own finding
- the coverage line is present and its denominator is the whole trace, not the audited span

A wrong answer typically quotes a remembered interval instead of the databook's, compares a
time-valued parameter against cycle-stamped lines, calls a legal activate during a per-bank refresh a
violation, or declares the refresh budget met from a whole-trace average while a power-down window
hides a gap of ten intervals.

## Done when

You can name one violated rule, the two lines of trace that prove it, the databook clause it breaks,
the one owner who fixes it, and how much of the trace you actually audited.
