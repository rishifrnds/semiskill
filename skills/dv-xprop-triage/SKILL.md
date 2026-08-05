---
name: dv-xprop-triage
description: Classify every X source in an X-propagation-enabled simulation as a real unknown, as tool pessimism, or as a value that is undriven by design, then apply the standard fix or draft a scoped waiver. Use when enabling X-propagation lights up a run that was clean without it, when a checker reports an X or Z inside a compared value, when a flop or a memory reads back all X long after reset, when hundreds of X errors appear at once and none of them looks like the source, or when someone proposes a blanket X waiver to make a milestone.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "X-Propagation Classification: Real X versus Tool Pessimism"
  semiskill-function: design-verification
  semiskill-role: static-signoff-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-04-09
  semiskill-tags: xprop, x-propagation, unknown-value, reset, initialisation, waiver, signoff
---

# X-Propagation Classification: Real X versus Tool Pessimism

The first X-propagation-enabled run on a block that was clean without it produces a wall of errors,
and the wall is almost always one or two sources fanned out into a few hundred symptoms. The
expensive failure is not missing a real bug — it is spending a week walking cones of logic that were
never wrong and then, exhausted, waiving the whole block.

The deliverable is **one row per X source**, not one per error: the head of the cloud, what it is,
whether hardware would have been defined there, the one named fix or the scoped waiver, and an
honest count of how many of the reported X sites that actually accounts for.

## When to use something else

If the run failed and you do not yet know X is involved, start with `dv-sim-log-first-error` — it
finds the true first error and says whether this is even an X problem. A whole night of failures to
sort and route is `dv-regression-triage-routing`; shrinking an identified X source to its smallest
run is `dv-minimal-reproducer`. A register that reads back all X is more often addressing or adapter
than X-propagation, so `dv-ral-bringup` gets there faster — come back once the register path is
proven. A build that never elaborated belongs to `dv-build-filelist-hygiene`, and a repository you
cannot navigate yet to `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| X-propagation mode | [[FILL: which X-propagation semantics our flow enables — the merge style that yields X only on the bits where the two branch results differ, or the force style that yields X on the whole result whenever the condition is X — and the exact name our flow calls it]] | DV infra |
| Instrumented scope | [[FILL: which modules our flow instruments and which are deliberately excluded — testbench, VIP, memory models, encrypted or black-boxed IP]] | DV infra |
| X report | [[FILL: whether our flow writes a separate X-propagation summary alongside the log, where it lands, and what one row of it contains]] | DV infra |
| X markers | [[FILL: the strings our checkers and our flow print when a compared or sampled value contains X or Z]] | DV lead |
| Time-zero window | [[FILL: how long after time zero X is legitimate here, and the event in the log that marks the end of that window]] | block DV owner |
| Reset specification | [[FILL: which registers in this block are specified to leave reset with a defined value, and which are deliberately left unreset]] | RTL designer |
| Memory initialisation | [[FILL: which memories and register files start uninitialised in our environment, and what is supposed to write them before anything reads them]] | block DV owner |
| Waiver list | [[FILL: where our X waivers live, how one entry is scoped and keyed, and which fields an entry must carry]] | DV lead |
| X sign-off rule | [[FILL: what X-cleanliness our milestone actually requires — zero X sites, zero unwaived X sites, or a budget]] | verification lead |

Log location, Run identity and the Area to owner map are pack-wide facts living in
`_shared/team-profile.md` — read them from there rather than re-asking. Two rows above are narrower
than a profile row and are **not the same fact**. **X markers** is narrower than the profile's Fatal
markers: only what our code prints when a value contains X or Z, which is frequently a different
string from what the flow prints on a general failure — search for the general one and you find
every failure except the X ones. **X sign-off rule** is narrower than the profile's Sign-off row:
that row records who signs and on what evidence, this one records how much residual X the milestone
tolerates, which is the only part step 8 needs.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented mode name or waiver
format produces a report nobody can act on, and an invented reset specification sends a real
power-on-state bug to the person who does not own it.

## Retrieval budget — read this before opening anything

An X-propagation run's log is the ordinary log plus one message per X site per cycle, so it is
routinely larger than the run that produced no X at all. Reading it is not an option.

1. **Grep and Read work on files on disk.** If the errors arrived pasted into the conversation, ask
   for the path under the profile's Log location, or for the text to be saved to a file and be given
   that path. Until a path exists you may reason over the pasted lines by eye — but say that is what
   you did, and treat every X verdict below as provisional.
2. **Prefer the X report to the log.** If the X report slot resolves to a file it is a summary and
   orders of magnitude smaller; enter there and open the log only for the site being classified.
3. The whole allowance is **one Glob, six Greps, five windowed Reads**. The Greps, itemised: (a) the
   X markers, step 1; (b) the event that ends the time-zero window, step 2; (c) the head signal's
   declaration, step 4; (d) and (e) two more for whichever row of step 5 you land in — its driver,
   its port connection, or its case statement; (f) the waiver list, step 7, and only when that list
   is a file that can be read. The Reads: one window of about 60 lines in the log or report, three
   of about 40 lines in source, one of about 40 lines in the waiver list.
4. More than about 200 hits normally means the pattern is too broad. The X-marker Grep is the
   exception — a cloud reprints every cycle, so thousands of hits is a fact about X rather than a
   mistake in the pattern. Do not read them; go to step 3 and get the head instead.
5. **Stopping rule.** If the allowance is spent and the X verdict is still open, stop, report the
   sites you did classify, and name the one thing missing — for a cloud whose head is not visible in
   source that is a waveform trace-back, and no amount of further Grepping substitutes for it.
6. State what you covered: how many X sites the report listed, and how many you classified.

## Procedure

### 1. Confirm this is an X-propagation run, and find the earliest X

X-propagation is a simulation mode, not a property of the design, so the first question is whether
the artifact on disk came from a run with the mode on. If it predates that, nothing below applies —
**ask the engineer to repeat the run with our X-propagation mode enabled and to save the log, plus
the X report if our flow writes one, where they can be read from disk**.

Then spend **one Grep** for the **X markers** over the report if there is one, otherwise over the
log. Record how many sites it names: that number is the denominator of the coverage line in step 8,
and quoting it later without having counted it now is the easiest thing here to get wrong. Then one
windowed **Read** of about 60 lines around the earliest hit.

Earliest means earliest in **simulated time**, not lowest line number. Those agree only when the log
is one run's output written in order — see the gotchas for when they do not.

### 2. Rule out the time-zero window before triaging anything

Almost every design is X for a while after time zero and is specified to be. The **Time-zero window**
slot says how long that is here and which event ends it; spend **one Grep** for that event to get its
line number and simulated time, and compare it against the time on the earliest X.

If every X site sits before that event and none survives it, there is nothing to triage — say that
plainly rather than manufacturing a finding. If some survive, they are the working set from here on,
and the ones inside the window are noise you must state you excluded, with the count.

### 3. Find the head of the cloud, not the loudest symptom

One X source puts X on everything in its fan-out cone, so the site with the most errors is usually
the far end of the cone rather than its source. Rank the surviving sites by earliest simulated time,
then — among sites at the same time — by proximity to a state element or a module boundary: an X on
a flop output or an unconnected port is a source, an X on a combinational result is a consequence.

The reliable way to walk a cone backwards is a waveform, and this agent cannot open one. So the
handoff is explicit: **ask the engineer to trace the X on the top-ranked signal back through the
waveform to the first signal in the cone that is X while its own inputs are not, and to give you
that signal's full hierarchical name** — or, if a value dump saved as text exists, the path to it.

Record which of the two you got. A head named from a waveform by a person is evidence; a head you
picked by ranking alone is a hypothesis and must be labelled one.

### 4. Read the driver of the head signal

One **Glob** to bound the block's source files, then **one Grep** for the head signal's name to get
its declaration and its assignments. Use the last two levels of the hierarchical path from step 3 as
the key — the full path contains instance names that never appear in the source.

Then a windowed **Read** of about 40 lines at whichever assignment drives it, looking for a row of
step 5 in this order: is the signal a state element with no reset, a port with no driver, the output
of a conditional, or the output of an expression that can produce X on its own.

### 5. Classify the X source

The `Evidence` column says what each row can be settled from. `source` is the RTL and the
instantiation; `log` is the saved run; `wave` means a human has to finish it, per step 3.

| Symptom | Evidence | Check first | Usual cause | X verdict |
|---|---|---|---|---|
| Every signal inside one instance is X from time zero and never clears | log + source | whether that instance's own clock or reset is itself X or unconnected | a top-level connection the testbench never drove | `class: infrastructure` — fix it, never waive it |
| X on a flop output with no reset, first sampled long after reset | source | whether that register is in the unreset set of the **Reset specification**, and what was supposed to write it | uninitialised state read before anything wrote it | `x verdict: real-x` if anything downstream branches on it — step 6 |
| X read from a memory or register file at an address never written | source + log | **Memory initialisation** — what preloads it in the real system, and whether the test did that | the model returns X by design and the test skipped the preload | `x verdict: undriven-by-design`; the fix is in the test |
| X on every bit of a conditional whose two branches would produce the same value | source | the **X-propagation mode** — force style or merge style | force-style semantics X-ing a result hardware would define | `x verdict: pessimism` |
| X only on the bits where the two branch results differ | source | whether the condition can be X in hardware at that moment | merge-style semantics working correctly — the condition is the bug | chase the condition; this signal is a consequence |
| X out of an arithmetic result with no X on any operand | source | a divide or modulo whose divisor can reach zero | a zero divisor makes the whole result X | `x verdict: real-x` unless the divisor is guarded upstream |
| X out of an indexed read while the array's data is defined | source | the index expression's range against the array's declared bounds | an out-of-range or X-valued select reads as X, and an out-of-range write is dropped | `x verdict: real-x` |
| X on a net with more than one driver | source | how many drivers the net has and what their enables are | contention, or two procedural blocks assigning one signal | `x verdict: real-x`, or infrastructure if one driver is a testbench force |
| X only in modules the flow does not instrument, or only in testbench code | source | **Instrumented scope** — which modules are in and which are out | X from an uninstrumented model, or the mode reaching non-synthesizable code | `x verdict: pessimism` — the scope needs the change, not the design |
| X on a signal crossing into another clock domain, and only on some seeds | log + wave | whether a synchroniser model here deliberately injects X or randomises the sampled value | a deliberate metastability model, or a genuinely missing synchroniser | unresolved until the waveform handoff comes back |
| A branch was taken that no defined selector could have chosen, and the output is a wrong value rather than X | source | whether the case statement uses the wildcard style that treats X in the selector as a match | wildcard matching against an X selector | `x verdict: real-x`, presenting as a wrong value rather than an X |

### 6. Real X, pessimism, or undriven by design — the test that decides

Every row above reduces to one question, and it is not "is this bit X".

**X in simulation means unknown. In silicon that bit holds some definite value nobody told you.** A
flop reset does not clear leaves power-on as a stable 0 or a stable 1; the simulator shows X because
it cannot say which, not because the hardware is undefined. So the real question is whether anything
downstream behaves differently for 0 than for 1 before a known value is written in. If nothing does,
this is not a bug. If something does, it is a power-on-state dependency — real, and the class of bug
that reproduces on some parts and not others.

That splits the three verdicts cleanly:

- `x verdict: pessimism` — hardware is defined here and the simulator is not. The two producers are
  force-style semantics on a conditional whose branches agree, and the mode reaching code that is
  not part of the hardware at all. Neither is a design change.
- `x verdict: real-x` — hardware is defined but arbitrary and the design depends on which value it
  took, or the value is genuinely undriven in hardware too, which is contention or a missing
  connection.
- `x verdict: undriven-by-design` — undefined until an initialisation step the real system performs
  and this test did not. The fix belongs to the stimulus, and the assumption that the step happens
  has to be written down, because next year nobody remembers it.

Name which of the three, and the sentence justifying it. An X verdict with no sentence is a
preference.

### 7. Apply the standard fix, or draft the waiver — not both, and never neither

- **Infrastructure** — connect the port, drive the clock, deassert the reset. Name the file and
  line, hand it to whoever owns the testbench top, and stop: every other X in that cone is
  unreadable until this is done, and re-triaging them first is wasted work.
- **`x verdict: real-x` from an unreset flop** — either the flop gets a reset, which is an RTL and
  area decision, or the design gates the read until the write has happened, or the stimulus
  guarantees the write first. Three different owners; name one, with the evidence line.
- **`x verdict: real-x` from an expression** — a guarded divisor, a bounded index, a resolved
  contention. An RTL change, and a small one.
- **`x verdict: pessimism`** — the narrowest possible change to the mode or to the **Instrumented
  scope**, recorded as a decision with its reason, never a global relaxation. A mode narrowed once
  to clear a milestone is never narrowed back.
- **`x verdict: undriven-by-design`** — a waiver, and the waiver carries its own guard.

Where the answer is a waiver, spend the last **Grep** on the **Waiver list** to confirm this is not
already waived, one windowed **Read** to copy the format, and draft the entry in that format for a
human to add. If the list is not a file that can be read, draft it in the shape below and say the
duplicate check did not happen.

```
scope    : <the narrowest instance path or signal this covers, never a module-wide match>
x source : <the step-5 row it was classified as>
why      : <why hardware is defined here, or what initialises it before anything reads it>
guard    : <the check that fires if that assumption is ever violated>
owner    : <who owns the assumption, from the profile's area to owner map>
expires  : <the date or milestone at which this is argued again>
evidence : <file and line, or log line and simulated time>
```

A waiver with no guard is a silent hole; a waiver with no expiry outlives the person who understood
it. Both are how a block reaches sign-off X-clean and fails in the lab.

### 8. Record the finding and state your coverage

Write the signature following `_shared/failure-signature-schema.md` — same field order, same
normalisation rules; `kind` for this class of failure is `xprop`. Then fill in this block, which
reuses the field names from `dv-sim-log-first-error`'s repro block so the two read side by side.

```
signature   : <phase>|<kind>|<where>|<what>
phase       : compile | elab | run | finalise | post
class       : design | infrastructure | unknown
x verdict   : real-x | pessimism | undriven-by-design | unresolved
x source    : <the step-5 row, quoted>
head        : <the most upstream signal that is X, and whether a person traced it or you ranked it>
first x     : <verbatim first X-marker line, with line number and simulated time>
mode        : <the X-propagation mode this run used, from the slot>
fix         : <the one named change, or the waiver entry drafted in step 7>
owner       : <the one person or team, from the profile's area to owner map>
run id      : <whatever identifies this run for us>
log         : <path, and the line range worth reading>
coverage    : <n of m X sites classified; how the rest were grouped and why they were not opened>
notes       : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

Then compare the residual against the **X sign-off rule** and say in one line whether this block
meets it, in the rule's own words. Anything not fillable from text on disk is `?`.

## Gotchas

- **X in simulation is unknown; X in silicon is a definite value you were not told.** Every argument
  about whether an unreset flop matters is really an argument about whether the design behaves the
  same for both values of that bit before it is written. Say which, and the argument ends.
- **A run clean without the mode and failing with it has not regressed.** The default `if` and case
  semantics in RTL simulation are X-optimistic — an X condition quietly takes the else branch —
  while gate-level simulation is X-pessimistic and smears X forwards. The mode closes that gap
  early, so the wall of new errors is the point rather than a side effect.
- **A comparison against X does not compare.** In SystemVerilog `==` and `!=` yield X when either
  operand has an X or Z bit, and a condition that is X counts as false, so a scoreboard written as a
  check on `!=` reports nothing at all for an all-X payload. Use the case-equality operators or an
  explicit unknown-value check when the point is to detect X.
- **X in an assertion's antecedent is false, not unknown.** A property whose antecedent goes X
  passes vacuously and those vacuous passes count as passes in the report, so an X window can look
  assertion-clean; a coverage hole where you expected hits is often that same X.
- **Merge-style semantics can hide the bug it was meant to expose.** Removing X where both branches
  agree is right for a mux — but if the condition went X because an FSM state was corrupted and both
  branches happen to write the same value, the corruption leaves the log entirely and resurfaces
  cycles later somewhere else. A merge-style run clean where a force-style run is not is data.
- **Out-of-range and X-valued selects are legal, not errors.** A read past an array's declared
  bounds returns X and a write past them is discarded silently, so one bad index shows up as an X
  now and a missing update later, and the two look like unrelated bugs.
- **Memories are X on purpose.** A model returning X for an address never written is correct; the
  bug is a test that reads before writing, or a preload boot firmware performs in the real system
  and nobody modelled. Filing it against the memory model costs a day and ends with the model right.
- **No X reported is not no X.** The report names only sites where something looked. A signal that
  goes X and is overwritten before anything samples it leaves nothing behind, which is why the
  sign-off argument has to rest on the checks that exist rather than on a quiet log.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- there is **one row per X source**, not one per error, and the coverage line's denominator is the
  number of sites the report actually named
- the `head` says whether a person traced it in a waveform or the agent ranked it, and a ranked head
  is being treated as a hypothesis
- every `x verdict: pessimism` names which of the two producers it is — force-style semantics on a
  conditional whose branches agree, or the mode reaching code that is not hardware
- every `x verdict: real-x` carries the sentence saying what behaves differently for 0 than for 1
- every waiver is scoped to an instance or a signal and carries a guard and an expiry, and the sites
  excluded as inside the time-zero window are counted rather than silently dropped
- the sign-off line quotes the **X sign-off rule** instead of asserting the block is clean enough

A wrong answer typically classifies a symptom at the far end of the cloud instead of its head; calls
an X pessimism because the branches "probably" agree without reading them; treats an all-X compare
the scoreboard never reported as evidence nothing was wrong; or waives a whole module to clear a
milestone with no guard left behind to fire when the assumption breaks.

## Done when

Every surviving X site is accounted for by a named source with an X verdict, and each source has
either one named fix with an owner or a scoped waiver with a guard and an expiry.
