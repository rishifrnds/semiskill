---
name: dv-safety-mechanism-verification-map
description: Decompose every safety mechanism in the safety concept into its three verification obligations — that it operates, that it detects the fault class it claims, and that it reports inside the stated fault-tolerant time interval — then map each obligation to evidence on disk. Use when someone asks whether a safety mechanism is verified, when a fault campaign result has to be checked against what the FMEDA claims, when a work-product review is coming and the safety verification plan lists exactly one test per mechanism, or when a mechanism passes at block level and nobody can say what the SoC does when it fires.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Safety Mechanism Verification Map: Function, Detection, Reporting"
  semiskill-function: design-verification
  semiskill-role: safety-verification-engineer
  semiskill-level: senior-staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-07-09
  semiskill-tags: functional-safety, iso-26262, safety-mechanism, fault-injection, fmeda, diagnostic-coverage, ftti
---

# Safety Mechanism Verification Map: Function, Detection, Reporting

A safety concept names mechanisms, a verification plan names one test per mechanism, and a review
asks whether the mechanisms are verified. One test almost always answers only the easiest of the
three questions a mechanism raises — that it operates at all — and leaves the two that decide
whether it is worth anything: whether it catches the faults it claims, and whether anything
downstream hears about it in time to react. This splits every mechanism into those three obligations
and maps each to a file and a line, so the empty cells surface before the work product is signed.

The output is **three cells per mechanism, an evidence path behind every filled cell, and an honest
denominator**. It is not a safety analysis and it produces no metric.

## When to use something else

This checks that claims already made have verification evidence. It does **not** compute
single-point or latent fault metrics, re-derive diagnostic coverage, or replace the FMEDA — if the
argument itself is in question, that belongs to whoever owns the analysis.

For a single failing simulation log start with `dv-sim-log-first-error`; a failing campaign run is
still just a failing run. For a night of failures use `dv-regression-triage-routing`; to shrink one
campaign failure into something a designer will look at, `dv-minimal-reproducer`. When the reporting
obligation dead-ends in an error-status or error-enable register that reads back wrong, that is a
register problem and `dv-ral-bringup` has the decision tree. If the campaign never built,
`dv-build-filelist-hygiene`. If you cannot find any of this collateral, `dv-repo-orientation` first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Safety concept location | [[FILL: where our technical safety concept and safety requirements live, and in which format — a text or markup file that can be read, or a document or requirements-tool export that cannot]] | safety manager |
| Mechanism ID convention | [[FILL: the identifier pattern a safety mechanism carries in our documents and in our source, so it can be searched for]] | safety manager |
| Safety verification plan | [[FILL: where the per-mechanism verification plan lives, and how a test, coverpoint or assertion declares which mechanism it claims]] | verification lead |
| FMEDA export | [[FILL: where a readable export of the FMEDA lands, which column carries the claimed diagnostic coverage, and which column carries the fault class that coverage is claimed against]] | safety analyst |
| Fault campaign collateral | [[FILL: where the fault campaign configuration, fault list and results summary land, and which fields in them name the fault model, the injection locations and the detection criterion]] | safety DV owner |
| Error-collection unit | [[FILL: the block that collects mechanism error outputs, and the signal or register naming convention a mechanism uses to report into it]] | SoC safety architect |
| Timing budget source | [[FILL: where the fault-tolerant time interval and its detection and reaction sub-intervals are recorded per safety goal, what we call each of them, the units, and the margin rule]] | safety manager |
| Safe-state reaction | [[FILL: what reaction each safety goal requires, and where that is written down]] | safety manager |

Pack-wide facts — **Log location**, **Run identity**, **Area to owner map**, **Sign-off** — live in
`_shared/team-profile.md`; read them there, this skill does not re-ask them. Two rows above are
deliberately narrower than a profile row and are **not** the same fact. **Fault campaign collateral**
is narrower than Log location: a campaign writes its own configuration, fault list and summary,
usually not where simulation logs land — if for us it is the same directory, write that down rather
than leave it assumed. **Safety verification plan** is narrower than Regression summary: a summary
says which tests passed, this slot must say which *mechanism* each test claims, a link no pass/fail
table carries. The profile's Sign-off row says who signs; this map is evidence for that person.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented mechanism identifier
or time budget produces a map that looks complete and is worthless.

## Retrieval budget — read this before opening anything

Fault lists run to millions of rows and an FMEDA export to thousands. Nothing here is read whole.

1. **Grep, Glob and Read work on files on disk.** A concept pasted into the chat or a summary quoted
   in a mail cannot be searched. Ask for the path; until one exists you may reason over the pasted
   text by eye, but say so and mark every cell it produced provisional.
2. **Glob** first for the concept, the FMEDA export, the verification plan and the campaign
   collateral. Never open any of them with **Read** as the first move.
3. **Three shared Greps** for the whole exercise: the mechanism identifier in the safety concept and
   again in the FMEDA export (step 2), and the time-budget key (step 7).
4. **Three Greps per mechanism**, one per obligation: the identifier in the verification plan
   (step 4) and in the campaign collateral (step 5), and the error-signal name in the integration
   source (step 6).
5. **Reads are bounded**: at most three shared windows of about 60 lines — the concept's first
   mechanism entry, the error-collection unit's input list, the time-budget table — plus at most one
   60-line window per mechanism, spent only where a Grep hit cannot be judged without context.
6. **Ceiling: eight mechanisms per pass** — 27 Greps and 11 windowed Reads. A concept with forty
   mechanisms takes five passes, and saying so is the correct answer.
7. More than about 150 hits on an identifier means it is a substring of something common; anchor it
   before reading anything.
8. Stop at the ceiling or the Read budget, whichever comes first, and report the denominator: mapped
   n of m mechanisms, and where the m came from. An unstated shortcut in a safety document is far
   worse than a stated one.

## Procedure

### 1. Resolve the safety concept to files that can actually be opened

**Glob** for the Safety concept location. If it resolves to a document, a spreadsheet or a
requirements-tool page, **Read** cannot open it — say so before going further and treat every
attribute from it as a handoff: ask the safety manager for the value, record who supplied it, and
mark every cell resting on it provisional. A claimed diagnostic coverage with no file and no line
must never enter the map as though it had one. Same test for the FMEDA export: a live spreadsheet is
not evidence this procedure can cite, a saved export of it is.

### 2. Enumerate the mechanisms and freeze the denominator

One **Grep** with the Mechanism ID convention pattern over the concept. That hit list is the
denominator for everything after it — record `m` now, before any evidence is found, or the map ends
up silently covering only the mechanisms that happened to have tests.

One further **Grep** of the same pattern over the FMEDA export, and compare the two lists. Three
mismatches are findings in their own right, reportable before any obligation is examined:

- **In the concept, absent from the FMEDA** — claimed but contributing to no metric: either the
  analysis is stale or the mechanism is decorative.
- **In the FMEDA, absent from the concept** — a metric resting on something no requirement asks for,
  so nothing obliges anyone to keep it working.
- **In both, different protected element** — the two documents disagree about what it covers, and
  every downstream number is drawn from one of them.

For each mechanism carried forward record, from the concept, what element it protects, the fault
class it claims, and which safety goal it serves. Spend the first shared **Read** window here if the
entry needs its surroundings.

### 3. Write the three obligations down before hunting for evidence

Quote the claim in the mechanism's own words first, and only then look for evidence. The other way
round lets the evidence define the claim and every mechanism passes — whatever the test happened to
do becomes what the mechanism promised.

| Obligation | The claim it discharges | What can be evidence | What cannot |
|---|---|---|---|
| Function | on a fault-free part it operates as specified, and stays silent | a directed test with the mechanism enabled and a result on disk; an assertion that fired for the right reason | a test named after the mechanism whose result nobody read |
| Detection | it detects the claimed fault class, at the claimed locations, at the claimed rate | a campaign whose model, fault list and detection criterion all match the claim | a campaign that injected a different model, or observed detection inside the mechanism |
| Reporting | detection reaches the required reaction inside the time budget | a trace from error output to collector to reaction, plus arithmetic on the intervals | an error output that terminates in the block-level testbench |

These are not degrees of one thing. They fail independently, need different evidence, and usually
belong to different people — which is why the middle and right columns stay empty while the left
fills up on its own.

### 4. Function — evidence that it operates, and that it stays quiet

One **Grep** for the identifier across the Safety verification plan and the testbench source.
Classify each hit before counting it: a test claiming the mechanism, a coverpoint, an assertion, or
a comment. Only the first three can be evidence, and only with a result on disk.

Two configuration traps decide whether the test exercised anything, and both look like a pass:

- **The mechanism is disabled by reset default.** Most are. If the test never sets the enable, the
  mechanism was absent for the whole run and the log says nothing either way.
- **The protected element was never used.** Error correction on a memory the test never writes and
  never reads has nothing to check. Look for the traffic, not just the enable.

Then the half that gets skipped: it must **not** fire in fault-free operation. A mechanism that
reports spuriously either desensitises whoever handles the error or trips the reaction in the field,
and both are safety outcomes rather than nuisances. Evidence is a long fault-free run with the
mechanism enabled and its error output quiet throughout — a different run from the one above.

The agent cannot start a simulation. Where a result is missing, **ask the engineer to run the
directed test with the mechanism enabled and to give you the path to the saved log**, then Grep that
log for the profile's markers rather than assuming what it printed.

### 5. Detection — the fault campaign, and the four places it goes hollow

This obligation cannot be discharged without fault injection, and the agent cannot inject a fault.
**Ask the engineer to run the fault campaign and to give you the paths to the campaign
configuration, the fault list and the results summary.** Then one **Grep** per mechanism into that
collateral — never a **Read** of a fault list, the largest file in the flow.

1. **Does the injected fault model match the claimed one?** A permanent stuck-at campaign is no
   evidence for a claim about transient upsets, and a single-bit-flip campaign none for a claim
   about permanent faults. Correction codes on a memory usually claim soft errors; stuck-at faults
   in the same array answer a different question and yield a number that is not the claimed one.
2. **Is the fault list drawn from the protected element or from the whole block?** A list scoped
   wider than the claim distorts the result both ways — faults outside the mechanism's scope drag
   the number down, faults it was never claimed to cover prop it up. List scope and claim scope must
   match, and both belong in the map.
3. **Where was detection observed?** If the criterion is that the internal comparator toggled, that
   is step 4's evidence wearing a detection test's name. Detection must be strobed at the
   mechanism's declared error output — the boundary the rest of the system sees.
4. **How were undetected faults classified?** Faults set aside as safe by argument rather than by a
   check are where diagnostic coverage numbers are made and where they collapse under review. A
   fault neither detected nor prevented from reaching the safety goal is a residual fault, not a
   safe one, and calling it safe moves the number without moving the silicon.

A mechanism also claiming **latent** fault coverage needs a second campaign with the fault injected
into the mechanism itself rather than the element it protects: undetected there, the mechanism is
silently absent while everything still looks correct. Its deadline is not the fault-tolerant time
interval but the multiple-point fault detection interval, which teams usually bind to a power-up
self test or a drive cycle. Record which interval each claim is against — they differ by orders of
magnitude and are routinely conflated.

### 6. Reporting — trace the error out of the block

One **Grep** for the mechanism's error-signal name, following the Error-collection unit convention,
across the integration source above the block; then a shared **Read** window on the collector's
input list. Three breaks account for most of what is found:

- **The error output is tied off or unconnected one level up.** The block environment terminated it
  itself, so block-level sign-off cannot see this and never will.
- **The error is latched but nothing acts on it.** A status bit with its interrupt masked, its
  channel disabled, or its reaction configured as no-action by reset default is indistinguishable
  from a working path in every log — the bit is set either way.
- **The reaction is not the one the safety goal requires.** Compare what the path actually causes
  against the Safe-state reaction slot. Reaching *a* safe state is not reaching *the* one, and
  degraded operation is a different claim again with its own tolerance interval.

If the path ends at an error-status or error-enable register whose read-back is wrong, stop and hand
it to `dv-ral-bringup` — a masked interrupt caused by a mis-declared access policy is a register
bug, not a safety-mechanism bug, and that skill classifies it in one pass.

### 7. The time budget — arithmetic in the open

The shape is fixed: detection interval plus reaction interval must fit inside the fault-tolerant
time interval, with the margin our process requires. The names, the margin and the units come from
the Timing budget source slot — teams spell these differently and the standard's own wording is not
something this procedure can quote — so read them there and spend one **Grep** on this safety goal's
row. Then do the arithmetic where it can be checked, with a source beside each number:

- An **always-on** mechanism — a comparator, an inline code check — detects in roughly the
  propagation delay to its error output, small enough that the reaction dominates.
- A **periodic** mechanism — a self test on an interval — has a worst case of a full interval *plus*
  the test's own duration, because a fault arriving just after a test waits for the next one.
  Quoting the typical, or the test duration alone, is the commonest error here and always optimistic.
- The **reaction** interval runs from error output to safe state and includes the collector, any
  software handling, and the actuator. A budget that stops at the collector must say so.

Convert to one unit before adding. Mixed clock cycles and milliseconds is the other way these go
wrong, and it survives review because both numbers look right on their own.

### 8. Score the cells and write the map

```
mechanism : <the identifier, exactly as the safety concept spells it>
protects  : <the element, and the safety goal it serves>
claim     : <the fault class and the claimed diagnostic coverage, quoted with its source>
works     : evidenced | claimed-not-evidenced | not-checked
detects   : evidenced | claimed-not-evidenced | not-checked
reports   : evidenced | claimed-not-evidenced | not-checked
evidence  : <path and line for every cell above marked evidenced>
timing    : <detection plus reaction against the interval, all three with sources, one unit>
gap       : <the largest missing obligation, in one sentence>
signature : <phase>|<kind>|<where>|<what>, per the shared schema, when an obligation failed in a run
class     : design | infrastructure | unknown
owner     : <who closes the gap, from the profile's area map, or blank plus candidates>
run id    : <whatever identifies the campaign or run the evidence rests on>
coverage  : <mapped n of m mechanisms; where the m came from; what was not opened and why>
notes     : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

`signature`, `class`, `owner`, `run id`, `coverage` and `notes` are the field names
`dv-sim-log-first-error` and `dv-ral-bringup` already use, so a failed obligation routed onward keeps
its vocabulary, and `signature` follows `_shared/failure-signature-schema.md` exactly rather than
being re-derived here. The rest are local to this skill.

Use `claimed-not-evidenced` where the concept or FMEDA makes the claim and nothing on disk
discharges it, and `not-checked` where the budget ran out first. They are different answers to
different people and merging them hides which. The most valuable row is never the one with three
cells evidenced — it is `works: evidenced`, `detects: not-checked`, `reports: not-checked`, because
that is the mechanism everyone currently believes is verified.

## Gotchas

- **A passing test named after a mechanism proves the mechanism ran**, and nothing about what it
  caught. A memory-protection test that never corrupts a stored word is a function test wearing a
  detection test's name, and the name is why nobody re-reads it.
- **Most mechanisms are off after reset.** A test that never sets the enable produces a clean log
  from a part with no mechanism in it, which is what everyone was hoping to see.
- **Diagnostic coverage is per fault class, not per mechanism.** A percentage with no fault class
  beside it is not a claim that can be verified — step 5's first question has no answer.
- **Detection observed inside the mechanism is not detection.** The comparator toggling is
  interesting; the error output asserting is the obligation. Campaigns strobed on internal nodes
  report high numbers and pass reviews that never look at the strobe point.
- **An undetected fault reclassified as safe by argument moves the number, not the silicon.** Ask
  what check the classification rests on; if the answer is a paragraph rather than a file, the map
  says provisional.
- **The error output tied off one level up is the commonest reporting break there is**, and block
  level cannot see it by construction — the block environment is the thing terminating it.
- **Worst-case detection for a periodic test is a full interval plus the test's duration.** A fault
  arriving one cycle after a test completes waits out the whole next interval; typical times in a
  safety budget are not conservative, they are wrong.
- **Latent-fault coverage needs the fault in the mechanism, not the protected element**, and its
  deadline is the multiple-point fault detection interval, not the fault-tolerant one. Mixing them
  makes a mechanism that self-tests once per power-up look as if it meets a millisecond budget.
- **A mechanism sharing a clock, reset or supply with what it protects can be removed by the same
  fault.** That is a dependent-failure question, but it lands here as a mechanism whose three cells
  are all evidenced and whose claim is still untrue — note it and route it to that analysis's owner.

## Human verification — what a wrong answer looks like

Before acting on the map, check:

- every cell marked `works: evidenced`, and every other evidenced cell, carries a path and a line —
  or is attributed to the person who supplied it and marked provisional
- no mechanism has all three cells evidenced from one test; that is one test counted three times
- the claimed fault class is quoted from the concept or the FMEDA, never inferred from what the
  campaign happened to inject
- detection was strobed at the mechanism's error output, not at an internal node
- the time budget uses one unit throughout and the worst case for anything periodic
- the `coverage` denominator is the number of mechanisms in the concept, not the number that had
  evidence, and every mechanism recorded `detects: not-checked` is counted in it

A wrong answer is a map where every mechanism is green because each has a passing test; a diagnostic
coverage percentage repeated with no fault class beside it; a reporting cell marked evidenced from a
block-level environment that terminates the error output itself; or a denominator quietly reduced to
the mechanisms that turned out to have collateral.

## Done when

Every mechanism in the concept has three cells, every filled cell has a file and a line behind it,
and the empty cells are named as gaps with an owner rather than left blank.
