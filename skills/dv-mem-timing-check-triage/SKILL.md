---
name: dv-mem-timing-check-triage
description: Classify a memory-model timing-check violation, trace the value it enforced back to the file that set it and to the mode-register writes behind it, and name one owner. Use when a DDR, LPDDR or HBM memory model or protocol monitor reports a timing violation such as tRCD, tRP, tRFC, tFAW, tCCD or tWTR in the middle of traffic, when the controller team and the memory IP team each think the other is misconfigured, or when you need to know whether a violation is a real scheduling bug or two configurations disagreeing about the same part.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Timing-Check Violation Triage from Memory Model Logs
  semiskill-function: design-verification
  semiskill-role: memory-ip-dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-06-03
  semiskill-tags: memory, ddr, lpddr, jedec, timing-check, mode-register, triage, debug
---

# Timing-Check Violation Triage from Memory Model Logs

A memory model fires a timing check and prints a parameter name, a value it required and a value it
observed. The reflex is to file it against whoever wrote the scheduler, and most of the time that is
wrong: the commonest cause is two sides configured for different parts — the model told one speed
bin, the controller programmed for another — and the violation line alone cannot tell you which side
moved. The second commonest cause is that the violation was never real, because it fired before the
part was initialised.

This produces **a classification, the file and line that set the value, and one owner**. Its hardest
rule is the one that makes it trustworthy: **every number it reports is read out of a file, and any
number it did not read is written as unknown rather than recalled.**

## When to use something else

For a failing simulation log whose first error is not yet known, start with
`dv-sim-log-first-error` — come here once the first error is known to be a timing check. For a whole
night of failures to sort and route, use `dv-regression-triage-routing`. For a compile or elaboration
break, use `dv-build-filelist-hygiene`. Once the class is settled and you want the smallest run that
still shows it, use `dv-minimal-reproducer`.

Two neighbours matter more than any of those. If the run never got through initialisation and
training, the failure is bring-up and belongs to `dv-memory-model-training`; this skill assumes a
part that came up and then misbehaved under traffic. If the violations cluster around refresh,
self-refresh or power-down entry and exit, the sequence is the subject rather than the parameter, and
`dv-mem-refresh-lowpower-audit` owns it. Step 1 and step 3 route to both.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Timing-violation markers | [[FILL: the strings our memory model or protocol monitor prints when a timing check fires, and at what severity it prints them]] | memory IP DV owner |
| Init-complete marker | [[FILL: the string that marks the end of initialisation and training, after which a violation is a real one]] | memory IP DV owner |
| Model source | [[FILL: where the memory model and its timing-parameter include files live in our tree, and whether they are readable text or a protected or pre-compiled library]] | DV infra |
| Speed-bin selection | [[FILL: how our build chooses the part and speed bin the model is configured with, and the file that records the choice for a run]] | DV infra |
| Controller timing config | [[FILL: where the controller-side timing values are set for a run, and whether they are written as cycle counts or as absolute time]] | block DV owner |
| Mode-register trace | [[FILL: how a mode-register write becomes visible to us — what the model or monitor prints when it decodes one, or the file our init sequence lives in]] | memory IP DV owner |
| Mode-register decode source | [[FILL: which datasheet or model header gives the field encoding for our part, and whether it is a file that can be read]] | memory IP DV owner |
| Timing-check build options | [[FILL: whether our build leaves timing checks enabled, the timescale precision the model is elaborated at, and where both are recorded]] | DV infra |

Log location, Run identity, Pass marker and Area to owner map are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than asking again.

**Timing-violation markers is narrower than the profile's Fatal markers**, and the two are not the
same fact. Many models print timing violations through their own message macro at a severity below
whatever the flow treats as fatal, so a run can be full of them and still be reported as passing. It
is also not `dv-ral-bringup`'s Mismatch markers, which are what register sequences print on a data
comparison — a different check, in a different component. If any two of the three happen to be the
same string here, record that they are, rather than leaving a skill to assume it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** A guessed marker searches the log
for something it never printed and returns a clean result, which is the most expensive wrong answer
available in this procedure.

## Retrieval budget — read this before opening anything

A memory traffic log is one line or more per command and routinely runs to hundreds of megabytes;
the model source is machine-generated and just as unreadable end to end. The whole ledger is **one
Glob, at most seven Greps, and at most six bounded Reads** — one window of about 80 lines in the log
and five windows of about 40 lines elsewhere. It is spent like this:

1. **Grep, Read and Glob work on files on disk.** They cannot search a log pasted into the chat. If
   the violation arrived as pasted text, ask for the path it came from, or ask for it to be saved to
   a file and be given that path, before anything is Grepped. Until then you can reason over the
   pasted lines by eye, but say that is what you did — the log has not been searched.
2. **No retrieval at all** — step 1 opens by reading the filled **Timing-check build options** slot,
   whose two answers are standing facts it carries. If your slot records them per run instead, ask
   for that run's values and note who supplied them; do not spend a Grep chasing them.
3. **Grep 1** — step 1, one alternating pattern over the timing-violation markers, the init-complete
   marker and the profile's Pass marker.
4. **Read 1** — step 2, the 80-line window at the earliest violation that matters.
5. **Grep 2** — step 3, the census of which parameter names fired and how often.
6. **Glob 1 plus Grep 3 and Read 2** — step 4, locating the model source and the definition of the
   parameter the message named.
7. **Grep 4 and Read 3** — step 4, the speed-bin or part selection that chose that definition.
8. **Grep 5 and Read 4** — step 5, the mode-register writes.
9. **Grep 6 and Read 5, conditional** — step 5, the field encoding, spent *only* when the
   **Mode-register decode source** slot names a readable file. Where it names a datasheet instead the
   pair goes unspent and step 5 ends in a handoff: the ledger comes in under budget, which is a
   result to state rather than a saving to reinvest elsewhere.
10. **Grep 7 and Read 6** — step 6, the controller-side timing configuration and the clock period.

If any Grep returns more than about 200 hits the pattern is too broad — narrow it before reading
anything. The ledger covers steps 4, 5 and 6 once each and does not stretch to a second pass, so
step 3 chooses the order. **Stopping rule:** when the ledger is spent without the class settling,
stop, say which of the three traces is still missing, and name the one fact you would need. Past that
point the numbers get invented, and an invented timing value is indistinguishable from a measured one
in the report.

State what you actually covered — how many violations were triaged out of how many the census
counted, and which values came from a person rather than from a file. An unstated shortcut is far
worse than a stated one.

## Procedure

### 1. Establish that a check really fired, and that it fired after initialisation

If the violation arrived pasted into the chat rather than as a path, resolve that first — budget
rule 1, using the profile's Log location to ask for the path under it.

Then, before any pattern is Grepped, write into `build checks` the two answers the filled
**Timing-check build options** slot gives you: whether this build leaves timing checks enabled, and
the timescale precision the model was elaborated at. Both are load-bearing — a Grep that finds
nothing means nothing if the checks were compiled out, and step 2 cannot judge how large a violation
is against a precision it does not have. If the slot is unfilled, say so there, and mark every "no
violations" statement in the report unverified rather than clean.

Spend **Grep 1** on one pattern alternating the **Timing-violation markers**, the **Init-complete
marker** and the profile's Pass marker. From the hit list, record three things: how many violations
the log carries, the line number of the init-complete marker, and the line number of the earliest
violation *after* it.

Three outcomes end the procedure here rather than continuing it:

- **No violation lines at all.** This is only a clean result if `build checks` says the checks were
  enabled and the precision is finer than the amounts in question. If it says they were disabled, or
  if the slot was unfilled, the honest report is that the run carries no evidence either way, and the
  next action is to get a build with the checks on — not to close the question.
- **No init-complete marker at all.** The part never finished initialisation and training, so the
  rules the checks enforce were never the rules in force. That is bring-up — hand it to
  `dv-memory-model-training` with the line number of the last thing the log did show.
- **Violations only before the init-complete marker.** Reset and initialisation sequences
  legitimately drive command spacings that steady-state checking forbids, and models differ in how
  much of that they suppress. Say how many there were and that they precede initialisation; do not
  triage them as traffic bugs.

If the log also carries the Pass marker, note it. A run reported as passing with timing violations in
it means the violations print below the severity the flow acts on — worth saying in the report,
because it changes how long the problem has been there.

### 2. Read the violation verbatim and take it apart

Spend **Read 1** on about 80 lines starting roughly 60 lines before the earliest violation that
matters. Copy the message **verbatim**, then separate it into these parts without paraphrasing any
of them:

- the parameter name exactly as the model spells it, including any suffix
- the value the check required and the value it observed, each with its unit, exactly as printed
- the simulation time
- the location — rank, bank group, bank, and the command pair, to whatever depth the model names
- the severity it printed at

If the message names a parameter but prints no numbers, write the observed value as **`not printed`**
— that exact token, which is what the step 8 block expects, and which claims something stronger than
"unknown" would: not that you failed to find the number, but that the model never emitted one. The
trace in step 4 can still recover what the model *required*; nothing recovers what it saw, and a
required value quoted beside an inferred observed value reads as a measurement.

Where both numbers are printed, take their difference and compare it against the elaborated precision
from `build checks`. A shortfall smaller than one precision unit was already rounded before the model
compared it, and there is nothing under it to debug.

The lines before the violation are the evidence for whether the spacing was genuinely short: find
the previous commands to that same bank and note their times. This is the only place in the
procedure where the log itself can support or contradict the check.

**Every number that leaves this step is one you just read in that window.**

### 3. Census — one parameter, or all of them

Spend **Grep 2** on the timing-violation markers across the whole log and count how many distinct
parameter names appear and where they start. The shape decides the order of the remaining steps.

| What the census shows | What it usually means | Go to |
|---|---|---|
| One parameter, one bank, once or twice | a scheduling corner, or a genuinely tight case | 4, then 6 |
| One parameter, everywhere, from the first traffic | that one parameter's value disagrees between the two sides | 4 |
| Many parameters, all violating, all from the first traffic | the clock period or the part itself is not what the traffic assumes | 6 first |
| Many parameters, starting partway through a clean run | something changed at that point — find the event before anything else | 5 first |
| Violations grouped around refresh or a low-power exit | the sequence, not the parameter | `dv-mem-refresh-lowpower-audit` |

Write down which row you are in before opening a single source file. A junior triage that skips this
step spends its whole budget on the parameter in the first message, when the census would have said
in one Grep that forty others fired at the same time.

### 4. Trace the required value to the file that sets it

**Glob** for the model source per the **Model source** slot. If it is protected or pre-compiled,
**Read** cannot open it: that is a handoff, not a blocker. Ask the memory IP owner for the timing
table the current configuration selects, record who supplied it, and mark every finding that rests on
it *provisional*. **Do not reconstruct the value from a recollection of the standard** — that is the
single failure this skill exists to prevent.

With the source readable, spend **Grep 3** on the parameter identifier *exactly as the message
spelled it*, then **Read 2** on about 40 lines at its definition. You are deciding which of two
shapes it has:

- **Selected** — the value comes from a per-part or per-speed-bin table. The question becomes which
  entry was selected, which is the **Speed-bin selection** slot: spend **Grep 4** on that define or
  configuration name and **Read 3** where it is set for this run. A model configured for a different
  part than the controller was programmed for produces exactly the "one parameter, everywhere"
  census row, one parameter at a time, as each disagreeing entry gets exercised.
- **Derived** — the value is computed from other settings, commonly as the greater of a cycle count
  and an absolute time, or as a sum involving a latency or burst setting. Then the wrong number may
  be an input rather than this parameter, so write down which inputs the expression reads and carry
  that list into steps 5 and 6. Read the expression rather than assuming the usual one; the
  composition differs between generations and between models of the same generation.

Record the file path and line beside every value you quote. A value with no path is a recollection.

### 5. Trace the mode-register writes behind it

Mode registers are how the part is told which latencies and features to enforce, so a model can be
built from the right table and still check the wrong number because it was programmed to.

Spend **Grep 5** on the **Mode-register trace** slot's string, and **Read 4** on about 40 lines
around the last mode-register write before the first violation. Establish three things, all from
text:

- which mode-register addresses were written, and with what values, verbatim
- whether every one of them landed **before** traffic started. A write that lands afterwards changes
  the rules mid-run and is the leading candidate for the "starting partway through" census row
- what the field actually encodes — which is the **Mode-register decode source** slot, and which of
  the two paths below you take depends on what that slot says the source is

**If the decode source is a readable file** — a model header, a package of parameter definitions, a
generated configuration file — spend the ledger's conditional pair on it: **Grep 6** for the register
address or field identifier *as the trace spelled it*, then **Read 5** on about 40 lines at the hit,
and quote the encoding with its file and line like any other value. Two cases collapse that pair to
nothing, and both are worth saying out loud: the decode source may be the file the trace already came
from, so Read 4's window holds the table; or the model may print the decoded meaning beside the raw
value, so neither Grep nor Read is needed.

**If the decode source is a datasheet or licensed specification text** rather than a readable file,
this is a handoff: give the address and the value to the person who holds it and ask what they
encode, record who answered, and mark the finding *provisional*. The conditional pair goes unspent.

Either way, **never decode a mode-register field from memory.** Encodings are reused across
generations with different meanings, and a latency decoded from recollection is a wrong answer
wearing the costume of evidence. Note also what was never written: a register the sequence skipped
holds the model's own default, which is rarely the value anybody assumed.

### 6. Check the clock period and the controller's side

The model checks in time; the controller almost always schedules in cycles. Every comparison between
them passes through the clock period, so check it first and check the rest against it.

Spend **Grep 7** on the **Controller timing config** slot for this parameter's counterpart and
**Read 6** on about 40 lines around it. Then compare, in this order:

1. **The clock period the model was given against the period actually driven.** If those differ,
   every derived parameter is wrong simultaneously and nothing further down this list means anything
   — this is the "many parameters at once" census row, and it is the whole finding.
2. **The required value against the cycle count the controller was programmed with**, converted
   through that same period. Say which direction you converted and what rounding you assumed, or say
   that the rounding convention could not be determined. Mark the converted number *derived* and
   quote both inputs with their file and line.
3. **Whether both sides name the same part and speed bin**, from the two files you now have open.

A required value and a programmed count that differ by exactly one cycle are the classic conversion
disagreement — one side rounded up where the other truncated. Report that as a conversion
disagreement between two configurations, which it is, rather than as a scheduling bug, which it is
not.

### 7. Classify, then name one owner

| Timing source | What settles it | Owner it routes to |
|---|---|---|
| `model-config` | step 4 — the model's table or speed bin is not the one the traffic assumes | whoever owns the testbench memory configuration |
| `mode-register` | step 5 — a programmed value disagrees, or landed after traffic began | whoever owns the initialisation sequence |
| `controller-schedule` | steps 4, 5 and 6 all agree and step 2 shows the spacing really was short | the controller RTL owner |
| `tb-init` | step 1 — the violation precedes initialisation, or initialisation never completed | testbench integration |
| `clock-period` | step 6 key 1 — the model's period is not the driven one | testbench integration |
| `unresolved` | the ledger was spent without agreement | nobody yet — say what is still needed |

`controller-schedule` is the only row that requires all three traces to have been done and to agree.
Reaching it without having opened the model configuration is the standard wrong answer, and it costs
an RTL owner a day to disprove. Resolve the routed owner to a person through the profile's Area to
owner map; if the map yields nothing, leave the name blank and ask.

The block's `class` follows from the row, and the two are not the same question — one says what set
the value, the other says which side of the design line the fix lands on:

- `controller-schedule` is **design**: the RTL issued the command and nothing configured it to.
- `model-config`, `tb-init` and `clock-period` are **infrastructure**. A model built for the wrong
  speed bin feels like a design bug because a real part would have failed too, but what has to change
  is a testbench configuration, and filing it as design sends it to a queue that cannot fix it.
- `mode-register` splits on *who wrote the register*: programmed by the testbench initialisation
  sequence it is **infrastructure**, programmed by the DUT's own initialisation logic it is
  **design**. If step 5 could not tell which side drove the write, that is `unknown`, not a coin toss.
- `unresolved` is always `class: unknown`.

### 8. Write the triage block

```
signature    : <phase>|<kind>|<where>|<what>, per _shared/failure-signature-schema.md
first err    : <the violation line, verbatim, with its line number>
cause        : <the definition or configuration line that set the required value, verbatim, with file and line>
phase        : compile | elab | run | finalise | post
class        : design | infrastructure | unknown
timing source: model-config | mode-register | controller-schedule | tb-init | clock-period | unresolved
check        : <parameter name exactly as the model spells it>
required     : <value and unit verbatim from the message, plus the file and line that sets it>
observed     : <value and unit verbatim from the message, or "not printed">
census       : <n violations, m distinct parameter names, first at line k, k1 before initialisation>
build checks : <enabled or disabled, and the elaborated timescale precision, per the step 1 slot; or "slot unfilled">
mr trace     : <the mode-register writes bearing on it, verbatim, or who was asked to decode them>
run id       : <whatever identifies this run for us>
log          : <path, and the line range worth reading>
owner        : <the step 7 row's owner, resolved through the profile's area map, or blank>
coverage     : <triaged n of m violations; which census row; which values came from a person>
notes        : <anything the next person would otherwise have to rediscover>
```

The field names are shared with `dv-sim-log-first-error` and `dv-ral-bringup` deliberately, so the
three blocks read side by side; `timing source`, `check`, `required`, `observed`, `census`,
`build checks` and `mr trace` are this skill's additions. In practice `phase: run` is the only value
this skill produces — a timing check fires while traffic is running, so nothing here ever assigns
`compile`, `elab`, `finalise` or `post`. All five tokens are kept so the block matches its siblings
exactly and a consumer counting phases across a shared table is not misled by a column that quietly
offers fewer. Write `?` in any field that cannot be filled from text on disk. Leaving a field blank
is a question the next person can answer; filling it plausibly is a wrong answer that looks right.

## Gotchas

- **A violation before initialisation completes is usually not a bug.** Models begin checking the
  moment they are instantiated, and the initialisation and training sequence legitimately drives
  spacings the steady-state rules forbid. Some models suppress checking until they have seen the
  sequence complete and some do not, so find where initialisation ended before triaging anything.
- **Timing checks can be switched off at build time and leave no trace.** A build that disables them,
  or a model elaborated at a timescale precision coarser than the differences it would be comparing,
  prints nothing — which is indistinguishable from a clean run. That is why step 1 records the
  Timing-check build options slot into `build checks` before it Greps anything: a clean Grep over a
  build with the checks compiled out is not evidence, and the report has to be able to say so.
- **A violation smaller than one precision unit is a rounding artefact, not a bug.** If the elaborated
  precision is coarser than the amount the model is complaining about, the numbers it printed were
  already rounded before it compared them. Step 2 makes that comparison; do it before filing, because
  the difference is a real number and the bug it implies is not.
- **Same-bank-group and different-bank-group limits are different parameters** — the `_L` and `_S`
  suffixed pairs in the DDR4 and DDR5 vocabulary, and their equivalents elsewhere. A same-bank-group
  limit firing between two commands the controller believed were in *different* bank groups is an
  address-mapping disagreement — which address bits select the bank group — and not a scheduling bug
  at all. It looks random in the log because it depends on the addresses the traffic happened to pick.
- **A rolling-window limit has no single offending command.** A limit on how many activates fall
  inside a moving window is broken by the window, and the command the message names is only the one
  that crossed the line. Quote the window and the commands inside it; naming that last command as the
  cause sends the controller owner to the wrong instruction.
- **Several parameters are specified as the greater of a cycle count and an absolute time.** Which
  half dominates changes with frequency, so a configuration that is exactly right at one speed is
  short by a cycle at another — and the failure appears only after a frequency change or a speed-bin
  bump, looking for all the world like a regression in the scheduler.
- **A mode-register write after traffic has started changes the rules mid-run.** Models generally
  apply the new value immediately, so violations begin at that instant and the log looks like a
  controller that suddenly got worse. The census row for that shape is the one that points at step 5.
- **The parameter name in a message is not always the parameter in the standard.** Models name their
  internal signals and parameters to suit themselves, and the same limit can appear under a house
  name, an abbreviation or a suffix. Grep the source for the identifier as printed, never for the
  name you expected it to have.
- **Protocol and state errors often print through the same message macro as timing checks.** A read
  to a closed bank is not a timing violation, it is an illegal command, and it has a different owner
  and a different fix. Separate them on the message text before counting anything in step 3.
- **Two violations at the same simulation time with different parameter names are usually one
  event.** One command that arrived early breaks every limit ending at it. Triage the earliest, and
  say the others share its time.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every number carries a source — a log line number, or a file path and line — and every number that
  came out of a conversion says so and shows both of its inputs
- no timing value appears anywhere that was not read out of a file, and none was recalled from the
  standard or from another part
- no mode-register field was decoded from memory; a decode read out of a readable decode source
  carries its file and line, and one supplied by a person is attributed to them and marked provisional
- `build checks` is filled, and any "no violations here" claim in the report is qualified by it. A
  clean census under a build with the checks disabled is the emptiest kind of good news
- the violation triaged is the first one **after** initialisation completed, and the count of the ones
  before it is stated rather than silently dropped
- `timing source` names one row. "Could be the configuration or the controller" means step 6 was not
  finished, and the honest value for that is `timing source: unresolved`
- a `timing source: controller-schedule` verdict shows the model configuration, the mode-register
  values and the clock period were each checked and each agreed
- the coverage line gives both numbers — how many violations were triaged, out of how many the census
  counted — and names the census row the triage assumed

A wrong answer typically quotes a required value from memory of the standard instead of from the
model source; blames the controller on a run where the model was configured for a different speed
bin; names the last command of a rolling-window violation as its cause; or triages a violation that
fired before the part was ever initialised.

## Done when

You can name the timing source row, the file and line that set the value behind it, the person it
routes to, and how many of the log's violations that rests on.
