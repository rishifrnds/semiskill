---
name: dv-power-aware-sim-debug
description: Separate a genuine power-intent bug from a power-format description error when a power-aware simulation fails, using the log, the power intent files and the power-control timeline. Use when signals corrupt to X after a power-down, when a retention register comes back with the wrong value, when the tool reports a missing or ineffective isolation or level shifter, when a test passes without power intent and fails with it, or when a power-aware run corrupts nothing at all and you suspect the intent was never applied.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Power-Aware Simulation Failure Debug
  semiskill-function: design-verification
  semiskill-role: static-signoff-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-09
  semiskill-tags: power-aware, low-power, upf, isolation, retention, level-shifter, corruption, debug
---

# Power-Aware Simulation Failure Debug

A power-aware simulation failure looks like a design bug and usually is not one. The simulator is
faithfully executing a description somebody wrote, so the first question is never "why did this value
go X" but "does the power intent describe the design we actually built". Get that backwards and a
one-line path typo in a power format file goes to an RTL designer, who correctly bounces it back two
days later while a real unisolated crossing waits in the queue behind it.

The output is a **classification into intent, description or correct behaviour**, the file-and-line
evidence behind it, one owner, and a line saying how much of the power intent you actually opened.

## When to use something else

Where nobody has yet established that the failure is power-related, start with
`dv-sim-log-first-error` and come here once the first error is a corruption, an isolation complaint or
a retention mismatch. To trace an X back to its driver through exported signal values, use
`dv-signal-trace-localisation` — that skill localises the X, this one decides whether the power intent
caused it. For a netlist that goes X after reset, use `dv-gls-bringup`. For deciding which power,
reset and clock scenarios the block must survive in the first place, use
`dv-reset-clock-scenario-matrix`. A build that failed before the power intent was loaded belongs to
`dv-build-filelist-hygiene`; a build that failed *while* loading it stays here, and is step 3.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Power format and revision | [[FILL: which power format our intent is written in, and which revision of the standard our flow reads it against]] | low-power lead |
| Power intent files | [[FILL: where our power intent files live in the tree, and which file the flow loads first]] | power architect |
| Power-intent diagnostics | [[FILL: the heading or message prefix our simulator prints its power-intent elaboration diagnostics under, and whether those land in the simulation log or in a separate file]] | DV infra |
| Corruption markers | [[FILL: the strings our simulator prints when it corrupts a value, reports an unisolated crossing, or reports a retention save or restore]] | DV lead |
| Always-on and retention supplies | [[FILL: which supply sets or supply nets are always on in this design, and which one retention hangs from]] | power architect |
| Power sequence source | [[FILL: what drives the power-control signals in this testbench — a controller in RTL, a sequence, or testbench drive — and the path to that file]] | block DV owner |
| Non-retained registers | [[FILL: how we record which registers are deliberately not retained across a power-down, and where that list lives]] | power architect |
| Power domain owner map | [[FILL: who owns each power domain's intent, and how that differs from the profile's area-to-owner map, which is keyed on design hierarchy rather than on domain]] | low-power lead |

Log location, Pass marker, Run identity, Simulator and Sign-off are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than re-asking. Two rows above are
deliberately **narrower** than a profile row and are not the same fact. **Corruption markers** is
narrower than the profile's Fatal markers: a corruption message is often a note the general flow never
counts as a failure at all. **Power-intent diagnostics** is narrower than the profile's Log location:
on several flows these land in a separate elaboration file. If you are unsure whether two strings are
the same string, ask — do not merge them.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented strategy or supply-set
name produces a confident classification aimed at the wrong person.

## Retrieval budget — read this before opening anything

Power intent files are small; power-aware logs are not, and a corruption marker can fire tens of
thousands of times in one run. Work in this order and stop when the classification settles.

1. **Grep and Read work on files on disk.** If the log or the power intent arrived pasted into the
   conversation, ask for the paths, or for the text to be saved to files and be given those paths.
   Until then you may reason over the pasted lines by eye, but say so — nothing has been searched and
   every finding is provisional.
2. **Never open the simulation log with Read first.** Grep for line numbers, then read one bounded
   window.
3. The whole budget is **six Greps, two Globs and five windowed Reads**: Grep 1 the log markers
   (step 1), Grep 2 the load command in the run scripts (step 2), Grep 3 the power-intent diagnostics
   (step 3), Grep 4 the corruption marker narrowed by domain or signal (step 4), Grep 5 the power
   commands across the intent files as one alternation (step 5), Grep 6 the control-signal names in
   the power sequence source (step 6); Glob 1 the intent files and Glob 2 the run script or filelist
   (both step 2); one 80-line window in the log (step 4), three 40-line windows in the power intent
   (steps 5, 6, 7), one 40-line window in the power sequence source or RTL (step 6). Steps 8 and 9
   open nothing new.
4. An intent file under about 200 lines may be read whole, counting as one of the three intent
   windows. Do not read them all whole: successive refinement means most of it has been superseded.
5. If a Grep returns more than about 200 hits, narrow it with the domain name or instance path before
   reading anything. The corruption marker is the one that explodes.
6. Stopping rule: once the budget is spent with no settled classification, stop and report what is
   known, the single thing still needed, and the coverage. Past that point answers get invented.
7. State your coverage: how many intent files were loaded, how many you opened, and how many of the
   reported corruptions you classified.

## Procedure

### 1. Establish that the run was power-aware at all

Spend **one Grep** on the log alternating the profile's Pass marker, the **Corruption markers** slot,
and the prefix from the **Power-intent diagnostics** slot. Three outcomes, three destinations:

- **No power-intent diagnostics anywhere.** The intent was never loaded, so the run says nothing about
  low power whatever else it says. That is `class: infrastructure`, and it finishes here.
- **Diagnostics present, nothing corrupted, and the test does power something down.** That is a
  finding, not a pass — go to step 5 and check the simulation state. A green power-aware regression on
  a design nobody has ever seen go X is the most expensive false negative in low power.
- **Diagnostics and corruption both present.** Continue.

Record the phase using the five tokens in `_shared/failure-signature-schema.md` and no others: an
intent that failed to load is `elab`, a corruption during the test is `run`.

### 2. Establish which intent files were in force, and in what order

**Glob** the **Power intent files** slot, **Glob** the run script or filelist, and **Grep** that for
the load command the **Power format and revision** slot names. Record the ordered file list and the
scope each was loaded at.

Successive refinement means a later file may re-specify what an earlier one set, and the last
specification wins. A strategy found in the block's file may have been replaced at top level, and a
classification quoting the replaced one blames a file that is correct.

If the loaded set cannot be reconstructed from disk — a wrapper builds the command line, or the scope
came from an environment variable — **ask the engineer for the exact invocation used for this run, or
for the tool's own power-intent report saved to a path you can read**. The agent cannot start the tool
or query its in-memory power database. Everything downstream is provisional until that answer arrives.

### 3. Read the elaboration diagnostics before the run-time corruption

Description errors announce themselves here, and settling one costs a single **Grep** against the
**Power-intent diagnostics** location. The class of message to look for:

- a strategy whose element list or object query matched no objects
- an instance, net or port path named in the intent that does not exist in the elaborated design — an
  RTL rename is the usual cause, and the intent file still reviews clean
- a supply net created and never connected, or a supply port left with no driver
- a strategy superseded by a later file, or applied at a scope that no longer exists
- a power state or supply expression the tool could not resolve

A hit here is almost always `power origin: description`, settled without a waveform and without an
argument. Take the Grep output as the evidence; spend an intent window only if a message names a file
and line you need in context.

Silence is weaker evidence than it looks. Whether a strategy that matches nothing is reported at all
is a property of the tool and its message suppression, not of the power format — which is exactly why
the **Power-intent diagnostics** slot exists. A quiet section is not proof that every strategy landed.

### 4. Put the first corruption on the power-control timeline

**Grep** the log for the corruption marker narrowed by domain or signal name, take the **lowest** line
number, and spend the single 80-line window there. Then place that time against the power-control
events, which the same window usually shows. Where the first corruption sits is the most information
available for the least reading:

| Where the first corruption sits | Reading |
|---|---|
| From time zero, before any power-control activity | a supply is undriven or unresolved, not a power-down — step 5 |
| At the supply-off event, inside the switched domain | expected; the only question is whether it escaped — step 6 |
| At the supply-off event, on a net read by an always-on receiver | an isolation question — step 6 |
| After power-up, in a register that was supposed to retain | a retention question — step 7 |
| Long after power-up, nowhere near a power event | probably not a power failure; back to `dv-sim-log-first-error` |

Quote two times in the finding: when the control changed, and when the corruption appeared. A
classification carrying only one of them cannot be checked by anybody.

### 5. Supplies and simulation states, before any strategy

**Grep** the intent files once, alternating domain creation, supply creation and connection, power
states, and the three strategy kinds. Then spend a 40-line intent window on the failing domain's
supply definitions. Two things settle here, and both are routinely mistaken for design bugs.

**An undriven supply is not an off supply.** A supply net created and never connected, or a top-level
supply port the testbench never drives, is undetermined, and many flows corrupt on undetermined
exactly as they corrupt on off — so the log is indistinguishable from a design that powered down at
time zero. Confirm the supply has a driver before reading a single strategy. This is
`power origin: description`.

**Corruption is a property of the declared simulation state, not of the voltage.** Each power state
carries a simulation-state attribute, and it is that attribute — not the supply value — that tells the
simulator to corrupt. A domain whose off state carries a non-corrupting attribute runs clean straight
through a power-down. Confirm the exact attribute spellings against the revision named in the **Power
format and revision** slot: they were extended across revisions of the standard, and reasoning from
the nearest similar-looking name is how a wrong verdict gets written down. If the state the test
drives was never declared at all, say so rather than assuming the tool defaulted it in your favour.

### 6. Isolation — the crossing, the coverage, the location, the enable

Spend a 40-line intent window on the strategy, then **Grep** the **Power sequence source** for the
control-signal names and spend the last 40-line window there. Four independent parts, different owners:

- **Is there a strategy for this crossing at all?** If the architecture says it is isolated and no
  strategy covers it, the file is incomplete — `power origin: description`. If nobody ever decided
  whether it should be isolated, that is an architecture gap — `power origin: intent` — routed through
  the **Power domain owner map**.
- **Does the strategy cover this net?** The element list, the source and sink filters, the
  input-or-output selector and any different-supply-only qualifier all narrow what is covered. A
  strategy covering a set that excludes this net is a description error whose symptom is identical to
  a missing strategy.
- **Is the cell on the right side of the boundary?** The location argument decides which domain the
  isolation cell itself lives in. A clamp placed inside the domain being switched off is corrupted
  with everything else and drives X into the receiver it was meant to protect — syntactically valid,
  reviews clean, textbook symptom of no isolation at all.
- **Was the enable asserted, and in the right order?** It must be asserted while the source domain is
  still powered, and released only after the source is powered, stable and out of reset. An enable
  arriving after the supply is gone is itself corrupt, so the clamp value is X. That is
  `power origin: intent`, living in the power sequence source. Check sense as well as timing: a
  strategy naming the enable with the opposite polarity to the controller is the same symptom with the
  opposite owner.

Separately, **the clamp value is a protocol decision, not a safety default**. Clamping a request, a
valid, or an active-low reset to its asserted level starts a transaction into a block whose partner is
off. The file does exactly what it says; the value was chosen wrong — `power origin: intent`.

### 7. Retention — five ways a value is lost, two of which are bugs

Spend the last intent window on the retention strategy.

- **The register was never retained.** Only elements the strategy names retain; the rest are
  corrupted, correctly. Check the **Non-retained registers** slot first — `power origin: correct` is
  the honest answer more often than anyone expects.
- **The retention supply is itself in the switched domain.** The saved state dies with the rail.
  Compare against the **Always-on and retention supplies** slot: the intent naming the wrong set is
  `description`; no always-on rail reaching those cells at all is `intent`, and an architecture change.
- **Save or restore in the wrong order.** Save must complete while the domain is still powered;
  restore must follow the supply being back and stable. Ordering is `intent`, in the power sequence.
- **Save or restore sense inverted in the intent relative to the controller.** Same symptom,
  `description`, one line to fix.
- **The restored value is overwritten immediately afterwards.** An asynchronous reset still asserted
  through power-up, or firmware re-initialising the block, wipes a correctly retained value a few
  cycles later; the log shows the right value briefly and then the wrong one. Found by comparing the
  time the value changed against the restore event, not by reading the intent file — which is why
  people who start in the file lose a day to it.

### 8. Level shifters — why the run-time log will not settle this

A missing or wrongly directed level shifter usually corrupts nothing in an RTL power-aware run: RTL
carries no voltage on a data net, so the value crosses intact and the run is clean. What it does
produce is a structural complaint at elaboration (step 3), a gate-level failure, or a static
low-power finding.

The agent can start none of those. Settle what the intent file can settle — the direction rule, the
location, whether the crossing is covered at all — then **ask the engineer for the static low-power
report or a gate-level run, saved to a path you can read**. Never report a clean RTL power-aware log
as evidence that level shifting is correct.

### 9. Decide the origin, then record the finding

One question decides it: **would this failure still happen in silicon if the power format file were
deleted?** Yes, and the design or its power control is wrong while the file merely revealed it —
`power origin: intent`. No, and the file describes an architecture we did not build —
`power origin: description`. Where the behaviour is what the architecture specifies and the failing
check is wrong, `power origin: correct`. Anything else is `power origin: unknown`, which is a
legitimate answer once the budget is spent.

Write the result as a failure signature following `_shared/failure-signature-schema.md` — same field
order, same normalisation rules, and `kind` is usually `xprop` for a corruption escape — then fill in
this block. It reuses field names from `dv-sim-log-first-error` and `dv-ral-bringup` so the three read
side by side.

```
signature    : <phase>|<kind>|<where>|<what>, per the shared schema
power origin : intent | description | correct | unknown
symptom      : <the step 4 row, quoted>
evidence     : <path and line for every strategy, supply and state quoted above; log line for every time>
class        : design | infrastructure | unknown
owner        : <power intent | RTL and power control | testbench and power sequence>
run id       : <whatever identifies this run for us>
log          : <path, and the line range worth reading>
coverage     : <n of m loaded intent files opened; a of b reported corruptions classified>
notes        : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

`class` here is about who is blocked, not how serious it is: a description error blocks the flow, so
`class: infrastructure`; an intent bug blocks the design, so `class: design`. If the wrong description
would also have been handed to implementation, say so in `notes` — that is a real silicon risk even
though this failure was not.

## Gotchas

- **A power-aware run that corrupts nothing is a failure, not a pass.** Either the off state carries a
  non-corrupting simulation state, or the domain never contained the instances you think it does.
- **A strategy that matches nothing is invisible.** An element list aimed at an instance path that no
  longer exists after an RTL rename covers zero objects, and the design then behaves exactly like one
  with no strategy — which is what makes it look like an RTL bug.
- **Isolation in the wrong location isolates nothing.** The clamp inside the domain being powered down
  is corrupted with everything else. Syntactically valid, reviews clean, worst possible symptom.
- **X from time zero is not a power-down.** An unconnected supply net or an undriven supply port is
  undetermined, not off, and most flows corrupt on both.
- **A retained register that is right at restore and wrong two cycles later did not lose retention.**
  An asynchronous reset held through power-up overwrites it. Compare against the restore time.
- **The clamp value is a protocol decision.** Clamping a request or an active-low reset to its
  asserted level starts a transaction into a block whose partner is off — correct file, wrong value.
- **Level shifters do not corrupt at RTL.** A clean run-time log is no evidence about level shifting.
- **The last intent file wins.** Establish the load order before quoting any strategy as the one in
  force, or you will file a bug against a top-level file that is correct.
- **Corruption granularity is a tool setting.** Whether the whole register, only its output, or only
  values that change get corrupted alters what the same design and the same intent will show — two
  engineers comparing logs taken with different settings will disagree about a design that is fine.
- **Ask for the same test with the power intent not loaded.** If it fails there too, power is not the
  cause. The agent cannot start that run — request it, and say in `notes` whether it exists.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the origin is one of the four tokens, and the "would it still happen with the file deleted" test was
  applied **in writing**, not implied
- every strategy, supply, state and clamp value is quoted with a path and a line number, from the file
  step 2 established was in force — not from the first file Glob returned
- two times are quoted from the log: when the control changed, and when the corruption appeared
- nothing the procedure calls correct behaviour has been filed as a bug — a register that was never
  retained, a corruption inside the domain that never escaped, or a clean RTL log on a level-shifter
  question
- the owner is one person or one file, not "the low-power flow"
- the coverage line names how many intent files were loaded and how many were opened

A wrong answer typically blames the RTL for a strategy that matched nothing, quotes a superseded
strategy from a block-level file, calls an undriven supply a power-down, declares the intent correct
on the strength of a run in which nothing was ever corrupted, or reports a level-shifter conclusion
that no artifact on disk could have supported.

## Done when

You can name the origin, the one file and line that produced it, the person who fixes it, and how much
of the power intent you actually read.
