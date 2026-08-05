---
name: dv-real-signal-behavioural-checks
description: Add real self-checks to a mixed-signal test that only passes because nothing is comparing the analog behaviour — tolerance bands, threshold crossings with hysteresis, settling and overshoot windows, and monotonicity over a swept code. Use when a real-number model test passes but nobody can say what it proved, when a regulator or DAC or PLL output is only ever printed and never compared, when a comparator check chatters on ripple, or when you are asked to justify a tolerance number you did not choose.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Behavioural Checks over Real-Valued Signals: Tolerance, Settling, Monotonicity"
  semiskill-function: design-verification
  semiskill-role: ams-verification-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-04-09
  semiskill-tags: mixed-signal, real-number-modelling, checkers, tolerance, settling, monotonicity, hysteresis
---

# Behavioural Checks over Real-Valued Signals: Tolerance, Settling, Monotonicity

A mixed-signal test that passes is not the same as a mixed-signal block that works. The digital side
has a done bit, a status register and a scoreboard; the analog side is a handful of real-valued nets
sampled into a log line, plotted once, and never compared. This procedure inventories those nets, says
which are checked, and drafts the one check that was missing — with its numbers traceable to the spec.

**What this does not do.** It reads model source, testbench source, spec extracts and saved logs. It
cannot start a simulation, open a waveform database, or measure a settling time. Every measurement
below is quoted from text on disk or handed off to a named human, and the report says which.

## When to use something else

- The test **failed** and you need the first real error out of the log — `dv-sim-log-first-error`;
  come back once the failure turns out to be "nothing was checking".
- A whole night of failures to sort and route — `dv-regression-triage-routing`.
- The trim, enable and status registers around the block rather than its output — `dv-ral-bringup`.
- A failure you already have a signature for and want to shrink — `dv-minimal-reproducer`.
- The wrong view got compiled, or the model is missing from the filelist — `dv-build-filelist-hygiene`.
- You cannot find the model or the testbench at all yet — `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Real-net convention | [[FILL: how our real-valued nets are declared and named — which real type, and the naming pattern that identifies one]] | AMS modelling owner |
| Model source | [[FILL: where the real-number models for this block live, and which view this testbench actually compiles]] | AMS modelling owner |
| Spec numbers source | [[FILL: where this block's electrical limits live — tolerance, ripple, settling, overshoot — and whether it is a file that can be read or a document a person must quote]] | block owner |
| Unit convention | [[FILL: the units our real nets carry, and whether the model and the spec use the same ones]] | AMS modelling owner |
| Sample source | [[FILL: what our checkers sample real signals on — a checker clock, a fixed timestep, or the net's own events — and the period]] | AMS modelling owner |
| Check macro | [[FILL: the macro or task our behavioural checks report through, the string it prints, and whether it counts toward the run's error total]] | DV lead |
| Tolerance policy | [[FILL: how we record a tolerance and its provenance, and where a relaxed or waived limit is written down]] | verification lead |
| Assertion support | [[FILL: whether real-valued expressions are accepted inside assertions in the simulator version we compile against, or whether behavioural checks must be procedural]] | DV infra |

The **Log location** and **Pass marker** are pack-wide facts in `_shared/team-profile.md` — read them
there, do not re-ask. Two rows above are deliberately **narrower** than a profile row, not the same
fact. **Check macro** narrows **Fatal markers** to what an analog behavioural check prints when it
fires — often a house macro the general flow never emits, so record both if they differ. **Assertion
support** narrows **Simulator** to what that version does with a real expression inside an assertion.

**If a slot is unfilled, stop and ask. Do not guess a convention** — and above all do not guess a
number. An invented tolerance is indistinguishable from a measured one once it is in the testbench.

## Retrieval budget — read this before opening anything

A real-number model is small; the testbench around it is not, and a waveform dump is both enormous
and not text — **Read** cannot open one. Stop as soon as one net's family and numbers are settled.

1. **Grep and Read work on files on disk.** A model pasted into the chat, a limit quoted in a message
   and a picture of a waveform cannot be searched. Ask for the path, or say what rests on unread text.
2. **One Glob** first, for the model source and the testbench around it. Never open a testbench file
   with **Read** as the opening move.
3. **Five Grep calls and no more**, each with the step that spends it: the saved log, for the pass and
   check markers (step 1); the real-type declarations (step 2); the check macro (step 3); the spec
   extract, once it resolved to a readable file (step 5); the chosen net's own name (step 6). Steps 4
   and 8 spend none. Step 7 compares two logs the engineer returns after a handoff — a second pass of
   one Grep per log, outside these five.
4. **Four windowed Read calls** of about 60 lines each, all four on the **one** net you carry to a
   draft: its declaration (step 4); its driver, only if that falls outside the first window (step 4);
   the spec rows (step 5); the attachment point where the check will sit (step 6). No fifth, no spare.
5. **Inventory every net; draft for one.** Steps 2 and 3 are Grep-only, so two calls cover the block
   however many nets it holds; steps 4 to 6 each spend a Read window on one net, which is what four
   windows buy. A second net is a second pass — three hand-waved checks are worse than one real one.
6. If a Grep returns more than about 150 hits the pattern is too broad — a bare `real` matches every
   comment containing the word. Anchor on the declaration form before reading anything.
7. If after the four windows the net's promise is still unclear, stop and say what is missing. Draft
   nothing — an invented limit is the most expensive output this procedure can produce.
8. State your coverage: nets inventoried, nets drafted for, and which numbers came from a person.

## Procedure

### 1. Confirm the test really passes, and that nothing analog is being compared

Resolve everything to paths first — budget rule 1. The profile's **Log location** says where our logs
land, so ask for the path under it rather than for the log again.

Then **one Grep** of that log whose pattern alternates the profile's **Pass marker** with the string
from the **Check macro** slot. This procedure exists for one result: the pass marker present, **zero**
check-macro lines — not a passing test, a test with no opinion. If the log is not on disk, say so and
mark every later claim provisional.

### 2. Inventory the real-valued nets

**Glob** for the files named by the **Model source** slot and the testbench around them. Then **one
Grep**, anchored on the declaration form in the **Real-net convention** slot, for every real-valued net
in scope; write down each hit's name, type, file and line. That list is your coverage denominator.

### 3. Classify each net by what is actually done with it today

**One Grep** for the **Check macro** slot's macro across the testbench gives every site that compares
anything. Put each net from step 2 into one of three rows, using these exact words in the report:

- **checked** — its value reaches a comparison against a limit that came from somewhere.
- **sampled-not-compared** — printed, logged, binned, or assigned to a variable nobody reads. The
  largest row on most blocks, and the one people mistake for coverage. Sampling is not checking.
- **untouched** — nothing in the testbench mentions it.

A coverage bin on a real value proves it was *reached*, never that it was *right*. Both Greps so far
covered every net; from here the budget carries one.

### 4. Pick the check family from what the net promises

Choose the net to draft for — the highest-consequence **sampled-not-compared** or **untouched** row.
Take **one Read** window at its declaration, and a second at its driver only if the driver falls
outside that window. This table then picks the family, keyed on the promise not on the block name.

| What the net is supposed to do | `check family` | Numbers you need | The mistake to avoid |
|---|---|---|---|
| Hold a level — supply, reference, bias | `tolerance-band` | nominal, absolute and relative tolerance, unit, and the steady-state ripple the band must exceed | a band tighter than the specified ripple, which can never be met |
| Cross a level and stay crossed — comparator, power-good, undervoltage lockout, ready | `threshold-hysteresis` | rising threshold, falling threshold, minimum dwell time | one threshold, so a ripply net chatters thousands of times |
| Reach a new level after a stimulus — regulator step, DAC settle, loop relock | `settling-overshoot` | stimulus event, target, band, settle-by time, peak limit | sampling once at the deadline instead of across the window |
| Move one way as a code or input sweeps — DAC, ramp, gain step | `monotonicity` | the sweep variable, the direction, the allowed backstep | indexing on time rather than on the sweep variable |
| Exist at all | `activity` | any change, over the whole run | assuming an unconnected real net is visibly broken; it is not |

Copy the second column's token into step 8 exactly as spelled — `tolerance-band`,
`threshold-hysteresis`, `settling-overshoot`, `monotonicity` or `activity`, never the row's prose name.

The last row is not filler. A `real` variable has no unknown state, so an unconnected net sits at a
legal-looking `0.0` and satisfies every "below the maximum" band you write: every draft needs a
companion `activity` guard that the net moved at all. Some analog-extension net types do carry explicit
unknown and high-impedance states — which applies depends on the type named in the **Real-net
convention** slot, so read that row first.

### 5. Get the numbers, with their provenance, and never from the waveform

The **Spec numbers source** slot decides which branch you are in, and each names the `provenance`
token step 8 must carry:

- **A readable file.** **One Grep** of it for this block's parameter names, then one **Read** window
  over those rows. Quote each limit with its unit and its clause; record `provenance: spec-clause`.
- **A document only a person can quote.** Ask the block owner, record who supplied each number, mark
  the finding *provisional*, and record `provenance: engineer-quoted`. A limit with no file and no
  line is not evidence.
- **Neither — the only source is what the model does today.** Say so in the **Tolerance policy** slot's
  terms, record `provenance: observed-not-authoritative`, and label the check a *change-detector*: it
  passes a design wrong in exactly the way the model is wrong now.
- **Unfilled.** Stop. Do not proceed to step 6.

Cross-check the **Unit convention** slot first: a model in normalised units against a spec in volts
gives a check wrong by a factor nobody notices, because it still passes. Write every comparison as a
two-part band — `abs(v - target) <= atol + rtol * abs(target)`: relative alone dies as the target
approaches zero, absolute alone across a wide range, and equality on reals is beaten by rounding.

### 6. Draft the check against a fixed skeleton

**One Grep** for the chosen net's own name finds every place it is declared, driven and read; spend
the **last Read** window on the attachment point. Then draft the same six lines for every family:

```
sample   : the Sample source slot's clock or timestep, elapsed time from a real-valued time task
guard    : armed only between the arm event and the disarm event, so one window is one verdict
compare  : abs(v - target) is at most atol + rtol * abs(target) — never an equality on a real
state    : one verdict variable per window, updated per sample, reported once
report   : a single message per window through the Check macro slot's macro
vacuity  : the window held at least the minimum sample count AND the net moved during the run
```

The **Assertion support** slot decides the form: where real-valued expressions are not accepted inside
assertions in our compiled version, those six lines become a procedural checker instead.

### 7. Say how the check could fail, then get that proved

A check nobody has seen fail is decoration, and the commonest way one passes forever is that it was
never armed. Name **one** perturbation that must make it fire: move the target well outside the band,
shorten the settle-by time below what the model needs, or reverse a sweep step.

The moment the draft exists, write `falsified: not-yet-run`. That is the honest state of every check
here until a simulation has been done, and it is what the block says when you hand the draft over.

Then **ask the engineer to run the test twice — once as it stands, once with that single perturbation
— and to give you the paths to both logs.** The agent cannot start either run. When the paths come
back, **Grep** each for the **Check macro** slot's string: absent in the first and present in the
second is the proof, so change the field to `falsified: yes`. Present in both means it fires for an
unrelated reason and absent in both means it is vacuous — either way it is `falsified: no`.

### 8. Record the finding

```
net          : the real-valued net, its full path, its declared type, and what it promises to do
status now   : checked | sampled-not-compared | untouched
check family : tolerance-band | threshold-hysteresis | settling-overshoot | monotonicity | activity
numbers      : every limit used, each with its unit
provenance   : spec-clause | engineer-quoted | observed-not-authoritative
sample       : what the check samples on, and the period, from the Sample source slot
falsified    : the perturbation, and whether it has been seen to fire — yes | no | not-yet-run
signature    : <phase>|<kind>|<where>|<what> if a check has already fired, else ?
class        : design | infrastructure | unknown
owner        : <model owner | block owner | testbench integration>
run id       : <whatever identifies the run this rests on, if any>
coverage     : <n of m real nets inventoried; k drafted; which numbers came from a person>
notes        : <anything the next person would otherwise have to rediscover>
```

`signature` follows `_shared/failure-signature-schema.md` exactly — same field order and normalisation
rules — and is `?` until something has fired, rather than invented. `class` is `unknown` until then
too; once a check fires, decide it from what made it fire. A limit the model's own behaviour violates
is `class: design`; one that fired because the wrong view was bound, the net was never driven, or model
and spec disagree on units is `class: infrastructure`, however much it reads as an analog bug.

## Gotchas

- **A `real` has no X, so a broken connection looks like a good value.** It sits at zero, which passes
  almost every band; the activity guard is all that stands between you and a green empty testbench.
- **One threshold chatters; two in the wrong order are worse.** The hysteresis band must exceed the
  peak-to-peak ripple, with a minimum dwell on top; a band tighter than the specified ripple gets
  relaxed until it passes, and a falling threshold above the rising one fires on every sample.
- **A settling check that samples once at the deadline passes a signal on its way back out.** Require
  in-band from settle-by to the next stimulus; ringing that re-exits is what one sample cannot see.
- **Overshoot is a fraction of the step and it has a sign.** Compute it against target minus initial,
  not the final value, and track the extreme in the direction of travel — a checker hard-coded to the
  maximum reports zero overshoot on every falling step, forever, looking healthy doing it.
- **The sample period decides what exists.** A peak narrower than one sample interval is invisible. Ask
  for ten samples across the fastest edge, and report the period — a limit met coarsely is not met.
- **Take elapsed time from a real-valued time source, not an integer one.** An integer time value is
  rounded to the module's time unit, so settling numbers quantise, look reassuringly stable across
  seeds, and are wrong by up to a full unit.
- **Monotonicity belongs to the sweep variable, not to time.** Index on the swept code, require it
  stable when sampled, allow a backstep epsilon — time-indexed flags every code-transition glitch, and
  zero-epsilon fails on model numerical noise nobody can reproduce.
- **Per-sample error reporting destroys the run.** A failing band at a fast rate emits thousands of
  messages, and a house maximum-error setting kills the run before the window you cared about. One
  verdict per window, reported once.

## Human verification — what a wrong answer looks like

Before putting any of this in the testbench, check:

- every number carries a **unit** and a `provenance` token, and nothing observed is called a spec check
- the hysteresis band exceeds the ripple, and the rising threshold is above the falling one
- the settling check covers a **window**, not an instant, and names its stimulus and its deadline
- the monotonicity check is indexed on the sweep variable and states its backstep epsilon
- there is an activity guard, and it is not satisfied by a net sitting at zero
- `falsified` says the check fired on a named perturbation, or is still `not-yet-run` — not evidence
- the `coverage` line gives both numbers: nets inventoried, and checks drafted

A wrong answer drafts ten checks with limits read off the waveform, declares a block verified on a band
an unconnected net at zero satisfies, or calls a settling number quantised to the time unit measured.

## Done when

You can name each real-valued net, say whether it is checked, sampled-not-compared or untouched, and
show one drafted check whose every limit has a source and whose `falsified` line is truthful.
