---
name: dv-rnm-authoring-correlation
description: Audit a real-number model of an analog block against the circuit simulation and the silicon data it claims to stand in for, then assemble the correlation evidence a model release needs. Use when you are writing or releasing a real-number model, when someone asks how you know the model is trustworthy, when the RNM and the transistor-level simulation disagree, when a model that correlated at nominal fails at a corner, or when you must state what a model does not represent before sign-off.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Real-Number Model Authoring and Correlation Evidence
  semiskill-function: design-verification
  semiskill-role: ams-verification-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-05-13
  semiskill-tags: rnm, real-number-model, mixed-signal, correlation, wreal, nettype, model-release
---

# Real-Number Model Authoring and Correlation Evidence

A real-number model is fast because it solves nothing: it is an event-driven program that emits numbers as
confidently for a condition its author never considered as for the one they fitted it to. Its trustworthiness
lives outside it, in a comparison against circuit simulation at named conditions and eventually against measured
parts. What fails six months later is never the arithmetic; it is a behaviour the model never had.

The output is **a test-point table with a modelled and a measured value per point, a classification for every
point outside its band, and a list of what this model does not represent**, plus one line on how much of that
rests on files actually read.

**What this does not do.** It reads model source, specification tables, measurement exports and saved data files; it
cannot start a circuit or mixed-signal simulation, open a waveform, or measure a part, so every such step ends in a
handoff to a named person and says so.

## When to use something else

One failing mixed-signal log starts at `dv-sim-log-first-error`, which owns the log and produces the failure
signature; this skill never opens a log. A whole night of failures goes to `dv-regression-triage-routing`, a model
that will not elaborate to `dv-build-filelist-hygiene`, one long failing test to shrink to `dv-minimal-reproducer`.
Come here when the question is not "why did this run fail" but "does this model deserve to be believed".

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Model source and language | [[FILL: which language and net kind our real-number models use — SystemVerilog user-defined net types, Verilog-AMS wreal, or a mix — where the model files live, and whether that net kind carries any unknown or high-impedance state beyond a plain numeric value]] | AMS methodology owner |
| Analog spec table | [[FILL: where this block's specification parameter table lives, and whether it is a file that can be read or a document a person must read]] | analog design owner |
| Circuit-sim measurement export | [[FILL: where extracted measurement values from a circuit simulation land, in what text format, and which column carries the value and which the unit]] | analog design owner |
| Correlation corners | [[FILL: the process, voltage and temperature conditions our sign-off requires a model to be correlated at, and which of those this block is marginal at]] | analog design owner |
| Tolerance convention | [[FILL: how we state a correlation band — absolute, relative, or per quantity — how we state it near zero, and who sets the number]] | AMS methodology owner |
| Connect-rules set | [[FILL: which connect-rules set our mixed-signal runs use, and where its thresholds and supply values are recorded]] | AMS infra |
| Quantisation convention | [[FILL: the amplitude and time step our models use for a ramping quantity, and whether it is a parameter or hard-coded]] | AMS methodology owner |
| Silicon measurement data | [[FILL: where bench or tester measurements for this block land, the unit of each column, and how many parts and conditions the set covers]] | silicon validation |
| Model release record | [[FILL: where a released model's version, correlation evidence and known-unmodelled list are recorded, and whether it is a file that can be read]] | AMS methodology owner |

**Sign-off** is a pack-wide fact and lives in `_shared/team-profile.md`; read it there. Two rows above are
deliberately narrower than a profile row and are **not** the same fact: *Circuit-sim measurement export* is a numeric
export written by an analog engine, not the profile's *Log location* where simulation logs land, and *Connect-rules
set* is not the profile's *Simulator* — a mixed-signal run also needs an analog engine and a rules set.

**If a slot is unfilled, stop and ask.** An invented tolerance, corner list or unit turns a model with no evidence
into a model with fabricated evidence — worse, because the first gets reviewed and the second ships.

## Retrieval budget — read this before opening anything

An extracted transistor-level netlist is machine-written and runs to tens of thousands of lines; a measurement
export from a corner sweep has one row per point per condition and is unbounded. Neither is read end to end. Work
in this order, and stop when the test-point table is filled or demonstrably not:

1. **Grep and Read work on files on disk.** A number in a chat message or a curve in a deck cannot be searched: ask for
   the path, and until there is one attribute the figure to whoever supplied it and mark the finding provisional.
2. **One Glob** for the model source under the Model source and language slot and for the export. Never **Read** either
   first, and never **Read** the circuit netlist at all: **Grep** for a line and enter at that line number.
3. **At most seven Greps**: two in step 1 (the model's version stamp; the revision stamp on the netlist or export),
   one in step 2 (port and net-type declarations), one in step 3 (parameter and constant declarations), one in step
   4 (parameter names in the Analog spec table, only where that slot says it is readable), one in step 6
   (test-point names in the export), one in step 7 (the silicon data file). More than about 200 hits means the
   pattern is too broad — re-anchor it on declaration syntax or an exact name and spend that Grep again.
4. **At most six bounded Reads**, 40 to 80 lines each: the interface (about 60), the parameter block (about 40), the
   Analog spec table at the step 4 hits (about 40, and not spent at all where a person must read it), two windows of
   the export (about 60 each), one of the silicon data (about 60).
5. Steps 5 and 8 spend no budget; they are handoff and authoring. If one appears to need a file, the fact belongs in
   a slot or in a request to a person, not in another Read.
6. **Stopping rule.** Budget spent with points unresolved: stop, say which points were compared from files and which
   were not, and name the one thing still needed — step 8's `coverage` line carries that. A correlation number
   invented past this point is the worst answer here: unlike a failing test, nothing ever contradicts it.

## Procedure

### 1. Pin both revisions, or the evidence cannot be falsified

Correlation is a claim about two artifacts: this model at this version against that netlist at that revision. Without
both it can never be checked later and, worse, never *invalidated* — the mechanism by which a model quietly stops being
true after a schematic change, nothing re-running and nothing failing. **Grep** the model source header for a version,
date or generator stamp and record it verbatim, then **Grep** the netlist or the Circuit-sim measurement export for its
own. If either is missing, say plainly that the correlation cannot be tied to a design revision, ask the analog design
owner which revision the measurements were taken at, and record who answered.

### 2. Read the interface before the body — the net kind bounds what can be modelled

One **Grep** for port and net-type declarations, then one **Read** window of about 60 lines over the interface. For
each port record its kind, what drives it, what loads it, and its value before anything drives it.

| Port kind | Can represent | Cannot represent, whatever the body says |
|---|---|---|
| digital | levels and event timing | any voltage or current value |
| single-value real net | one quantity, usually a voltage | loading, back-drive, or current at all |
| multi-field user-defined net type | a quantity and its companion — voltage with current, or with impedance | anything the record has no field for |
| electrical, through a connect module | the analog node itself | the thresholds and supply the connect-rules set imposes, which are not this model's |

A single-value real net **cannot** show loading, so a drive-strength defect at that node is structurally invisible. A
real net with more than one driver needs a resolution rule declared with the net type: without one, multiple drivers is
an elaboration error; with a careless one, a genuine conflict resolves to a plausible number and prints nothing.

### 3. Write the non-modelled list first, not last

Written last this list is an apology; written now it is the specification, because it says which questions the model may
be asked. **Grep** the parameter and constant declarations, **Read** about 40 lines, and list every effect not
represented, in two groups.

**Structural — absent because of what a real-number model is**: device noise, phase noise and jitter unless injected;
start-up, bias point and convergence failure, because there is no operating point to fail; current-dependent loading
unless the net kind carries a second field; impedance, settling and leakage; anything faster than the time step.

**Chosen — absent because this author left it out**: the temperature or supply dependence of a coefficient, a saturation
bound, a delay, a mode the block has and the model ignores. Record the Quantisation convention beside both lists: a ramp
is a staircase here, so the amplitude and time step chosen bound every timing number this model can produce.

### 4. Turn each claim into a test point with a band

A test point is not one until five columns exist: name, quantity with its unit, stimulus condition, the band from the
Tolerance convention slot, and the person who set it. A band nobody owns gets settled by whoever is most senior.

Take the claims from the Analog spec table, not from the model — values derived from the model being audited are
circular and yield a table that always passes. Where the Analog spec table slot says that table is a readable file,
**Grep** it for the parameter names and **Read** about 40 lines at the hits; where it says a person must read a
schematic or a slide, take each claim as a handoff and mark it provisional. That is the whole spec-table budget.

A claim whose behaviour is on step 3's structural list is still a row, and that row is `match: not-modelled`; dropping
it as "not a test point" is what makes a missing row and a knowingly-absent row look identical. Then say which of the
Correlation corners each point must hold at — nominal-only is dangerous for the point where the block is marginal.

### 5. Ask for the circuit-simulation evidence — it cannot be produced here

The agent cannot start a circuit simulation, so this step is a handoff and nothing else. **Ask the analog design
owner to run the circuit simulation at the step 4 conditions and to save the extracted measurements where they can
be read from disk** — the Circuit-sim measurement export slot says where those land and in what format. Ask for the
netlist revision, the corner each row was taken at, and the unit of each column; ask also whether every requested
condition produced a result, because a point that did not converge leaves no row, and a missing row read as agreement
is the easiest way to publish a model never compared. Do not invent what a simulation would have printed and do not
fill a gap from a plot; both produce numbers of exactly the shape a reviewer expects.

### 6. Classify every point against its band

One **Grep** of the export for the step 4 test-point names, then at most two 60-line **Read** windows entered at the
line numbers it returns. A point inside its band is `match: in-band` and needs nothing further; a point outside it is
`match: out-of-band`; a point whose condition produced no row, or whose reference did not settle, is
`match: not-measured` — a result, not a pass. Classify the *shape* of every out-of-band point, because the shape and
not the size names the cause. `Evidence` says what settles a row: `model` the model source, `export` the measurement
export, `both` the two side by side, `person` somebody at a waveform or a schematic.

| Shape of the discrepancy | Evidence | Check first | Usual cause |
|---|---|---|---|
| Every point wrong by the same factor of a thousand | both | the unit column of the export against the unit in the model | volts against millivolts, amps against milliamps |
| Every point wrong by a clean factor of two or one half | both | how the quantity is defined at each end | single-ended against differential, amplitude against peak-to-peak |
| Every point wrong by about 1.414, or about 1.732 | both | which amplitude convention each end reports | peak against RMS — about 1.414 for a sine, about 1.732 for a triangle, exactly 1 for a square, so it never appears as a clean factor of two |
| Correct at nominal, drifting steadily with one condition | model | whether that coefficient is a constant | a dependence fitted at nominal and hard-coded |
| Correct at DC, wrong on every transition | model | the time step from step 3 against the transition measured | the staircase — the model has no value between steps |
| Exactly 0.0 where the value should be non-zero | model | whether anything drives that net at all | 0.0 is what an undriven real net is worth; nothing distinguishes it from a driven zero |
| Only at the analog-to-digital boundary | model | the Connect-rules set thresholds and supply | the connect rules, not the block — a different owner |
| Only while a second driver is active | model | the resolution rule, or the missing current field | resolution or loading, from step 2 |
| Only after a long run, growing slowly | person | whether a state variable accumulates without bound | integration drift a short reference sweep never shows |

Two outcomes are not defects in the model. A discrepancy the connect-rules row explains is `class: infrastructure` owned
by whoever owns the rules set: the same model behaves differently under a different rules set with no source change and
no diff to point at. A `match: not-measured` point is `class: unknown` until a reference row exists — no evidence,
rather than bad evidence.

### 7. Silicon is a narrower check than circuit simulation, not a stronger one

Measured parts are the only evidence that the *circuit* simulation was right, so this step checks two things at once
and confuses them at its peril. One **Grep** of the Silicon measurement data file for the point names, one 60-line
**Read** at the hits. The set is narrow by construction: a few parts from one or two lots, at a few temperatures, on a
board with its own losses, instrumented where a probe fits rather than where the model has a node. A model-to-silicon
gap therefore has three candidate owners before it has one — the model, the circuit simulation it was fitted to, or the
measurement setup — and naming one needs the circuit-simulation number for the same point and condition. Without all
three, say the comparison is two-way and stop. Never widen a band because silicon disagreed: record the disagreement,
its size and its condition, because changing the band deletes the evidence.

### 8. Assemble the release evidence block

One block per test point, plus one header block for the model. It borrows `class`, `run id`, `cause`, `notes` and
`coverage` from the pack's other handoff blocks so the fields read the same way; `match`, `tolerance`, `corners` and
`unmodelled` are what this skill adds. Where a Model release record exists, this is what goes in it.

```
model      : <name, version and the file it was read from>
netlist    : <revision the measurements were taken at, verbatim from its stamp, or "unstamped">
point      : <test-point name from step 4>
modelled   : <value the model produces, with unit and where it came from>
measured   : <value from the export, with unit and the line number it was read at>
delta      : <the difference, in the units the band is written in>
tolerance  : <the band, and the person who set it>
match      : in-band | out-of-band | not-measured | not-modelled
cause      : <the step 6 row, quoted, or the verbatim line that settles it>
class      : design | infrastructure | unknown
owner      : <analog design | model author | connect rules | measurement setup>
corners    : <corners this point was compared at, and the required ones it was not>
silicon    : <the measured value and its condition, or "not compared">
unmodelled : <the effects from step 3 that bear on this point>
run id     : <whatever identifies the run the export came from>
coverage   : <n of m points compared from files; which values came from a person>
notes      : <anything the next person would otherwise rediscover>
```

Write `?` for anything not traceable to text on disk or to a named person. The counts of `match: not-measured` and
`match: not-modelled` rows belong in `coverage` beside the count actually compared — a reader shown only in-band and
out-of-band rows reads the table as complete. The profile's **Sign-off** row says who takes this.

## Gotchas

- **An undriven real net is worth 0.0, and nothing tells you which zero you have.** A block that was never connected
  reads as a correct chain of zeroes, and the net kind does not rescue you: in the base language an undriven Verilog-AMS
  `wreal` reads as 0.0 exactly as a SystemVerilog `real` does, and any unknown or high-impedance state above that comes
  from a tool extension or a user-defined net type someone wrote a validity field into. The Model source and language
  slot holds that answer; until it is filled, a zero is unexplained rather than evidence.
- **A single-value real net cannot be loaded.** Drive strength, back-drive, contention, and a divider formed by two
  impedances are all unanswerable at that node whatever the body computes. This is a property of the net kind, not a
  shortcut, and it is the commonest reason a model correlates and the silicon does not work.
- **A resolution rule turns a bus conflict into a plausible number.** Two drivers are resolved into one value and the
  run continues; sum, maximum and last-write-wins each give a different, believable answer and none prints a
  warning. If the block has a shared node, write the conflict check yourself.
- **Correlating at the PVT extremes is not correlating where the block is marginal.** Slow-cold and fast-hot are the
  corners that get automated; the one that matters has the least margin for this circuit and is often neither. That
  is why the Correlation corners slot asks for it separately.
- **The model has no operating point, so start-up cannot fail.** An RNM oscillator always oscillates and an RNM
  regulator always regulates, because someone wrote them that way. Coverage collected on a start-up sequence in a
  real-number environment measures the testbench, not the design, and reporting it builds a bring-up surprise.
- **Time quantisation aliases into every downstream sampler.** A comparator or ADC model sampling a staircase reports
  crossings quantised by the step chosen upstream, so any timing or jitter number from the model has a floor equal
  to that step — quote the step beside the number, or it reads as resolved to the picosecond.

## Human verification — what a wrong answer looks like

Before releasing on this evidence, check:

- both revision stamps are quoted verbatim, or the report says the correlation is not tied to a design revision
- every modelled and measured value carries a **unit**, the two units are the same one, and no band was widened after
  the measurement came back
- `match: not-measured` and `match: not-modelled` rows are counted in `coverage` and are not read as agreement, and
  step 3's list reached the release record
- the marginal corner was compared, not just the extremes, and any value that came from a person rather than a file
  is attributed and marked provisional

A wrong answer typically reports a model as correlated when half its points had no reference row; quotes a delta with
no unit; blames the model for a boundary discrepancy owned by the connect-rules set; treats a chain of zeroes from an
unconnected node as agreement; or claims start-up, noise or loading coverage the model cannot represent.

## Done when

You can name the model version, the revision it was correlated against, every point compared and every point not, and
the behaviours this model does not have — and someone can invalidate all of it with one file diff.
