---
name: dv-signal-trace-localisation
description: Localise an RTL failure from a text signal export when the agent cannot open the waveform database — decide what to export, reason over the exported values against a named reference, then name the exact next signals to export. Use when a scoreboard miscompare or an assertion has fired and you need to know which signal went wrong first, when someone tells you to just look at the waves and you cannot, when an X appears somewhere it should not, or when a handshake stalls and nobody can say which side dropped it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Waveform-Free Failure Localisation from an Exported Signal Report
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.2.0
  semiskill-review-by: 2027-07-29
  semiskill-tags: waveform, signal-trace, localisation, fan-in-cone, x-propagation, handoff, debug
---

# Waveform-Free Failure Localisation from an Exported Signal Report

A waveform database is the one DV artifact an agent genuinely cannot open. The binary formats are out
of reach outright; VCD is text but is a value-change stream keyed by short printable-ASCII aliases —
one or two characters on a small dump, three or four on an SoC — whose name map sits only at the top,
so grepping a signal name finds its declaration and never its values. The reflex — paste a screenshot, or scroll — throws away exactly what an agent is good at:
deciding *which* signals are worth exporting, and reasoning precisely over text a human exported.
The output is **the frontier** (the shallowest signal proven wrong and the shallowest proven right),
what the fault between them is localised as, and **the next export request** with a prediction on
every signal in it.
Not a description of the waveform.

## When to use something else

Come here with a failure already triaged. For a log you have not opened yet, use
`dv-sim-log-first-error`; it produces the signature and cause line step 1 starts from. For a night of
failures needing sorting, use `dv-regression-triage-routing`. A register-access failure belongs to
`dv-ral-bringup` — its front-door-versus-back-door and volatile-field rows end in exactly the
waveform handoff this skill picks up, so finish its source checks and come here only for the timing
question it cannot settle. Before asking anyone to dump a six-hour run, shrink it with
`dv-minimal-reproducer`: export cost falls with run length. If no database exists because the build
never completed, that is `dv-build-filelist-hygiene`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Waveform database location | [[FILL: where our waveform databases land, how one is named against a run, and how long it survives before deletion]] | your mentor |
| Dump scope | [[FILL: what our default dump records — which hierarchy depth, whether arrays, memories and unpacked structures are included, and at what simulated time dumping starts]] | DV infra owner |
| Export format | [[FILL: the text format our waveform tool can write, whether one row of it carries one signal at one time or every signal at one time, and whether an unchanged value is repeated on every row or omitted until it changes]] | DV infra owner |
| Export cost | [[FILL: how many signals and how much simulated time one export can cover before it stops being readable, and how long producing one takes]] | DV infra owner |
| Export owner | [[FILL: who can open the waveform database and write a text export out of it, and how we ask them]] | your mentor |
| Time unit and radix | [[FILL: the time unit our logs print, the time unit our exports print, whether those are the same, and the default radix a multi-bit value comes out in]] | DV infra owner |
| Clock and reset names | [[FILL: the clock and reset signal names for this block, and which of them each interface under suspicion is sampled on]] | RTL designer |
| RTL source root | [[FILL: where the RTL for this block lives, and which parts of it are generated rather than hand-written]] | block owner |

Five pack-wide facts come from `_shared/team-profile.md` and are deliberately not re-asked above:
**Log location** and **Fatal markers** in step 1, **Run identity** in steps 1 and 3, **Area to owner
map** in step 9, and **Rerun convention** in step 2, for a database never dumped or dumped without the
visibility you need. No row above duplicates one of them: the profile records where *logs* land, this
table where *waveform databases* land — usually a different directory with very different retention —
and **Time unit and radix** covers the export's units as well as the log's, which the profile records
nowhere. **If a slot is unfilled, stop and ask. Do not guess a convention.** An invented dump path,
radix or clock name gives a localisation that is internally consistent and points at the wrong module.

## Retrieval budget — read this before opening anything

An export is small only if the request was small. A hundred signals over a million cycles is a second
log, and this procedure refuses to produce one.

1. **Grep and Read reach text files on disk and nothing else** — not the database, not a screenshot.
   Values typed back to you in chat are not searchable: reason over them by eye if you must, say so,
   and mark every conclusion resting on them provisional. Never open the export with **Read** first;
   **Grep** for whichever of a signal name and a timestamp the export's shape makes greppable — rule
   3 settles which — to get line numbers, then Read a bounded window there.
2. **The log budget is one Grep and one windowed Read of about 80 lines, in step 1, and no more** —
   the run identity comes out of that one window if it happens to be in it, and otherwise from the
   block that routed the failure here, never from a second Grep. Anything deeper in the log belongs
   to `dv-sim-log-first-error`.
3. **Per round, the budget over the export is six Greps and four windowed Reads of about 80 lines.**
   *How* they are spent depends on which of two shapes the **Export format** slot describes, and you
   settle that from the slot before opening anything, at no retrieval cost.
   **Name per row** — every value row carries the signal's name, so a name is greppable: one **Grep**
   each for the clock, the reset and the window's last timestamp in step 3; one for the suspect
   signal in step 5; two spare for step 7's handshake pair or X search.
   **Row per timestamp** — one row per time step, one column per signal, so a name Grep returns the
   header row and no values. That hit is not wasted: the header names every column, so one **Grep**
   of the clock name fixes the clock, the reset and the suspect signal's column position together,
   and the reset Grep is not spent. The remaining calls go on timestamps, which sit on every row
   under both shapes: the window's last timestamp in step 3, two in step 5 to bracket the divergence
   point, two spare for step 7. Six either way.
   Of the Reads, one at the start of the window in step 4, one at the divergence point in step 5, two
   spare — read down one signal's rows under the first shape, across the columns of each row under
   the second. Step 3's other three checks — absent signal, run identity, radix — compare the slot
   table and the two paths you already hold against what step 1 recorded, and cost nothing. That is
   the whole arithmetic; no step may open the export for anything not listed here.
4. **Step 6 is the only step that opens RTL** — at most four **Greps** and three windowed **Reads**
   of about 60 lines, each entered through a Grep for an exact name, never by browsing a file.
5. If any **Grep** returns more than about 200 hits the pattern is too broad. A bare leaf name
   usually is — anchor it with whatever separator the **Export format** slot says surrounds a name.
   A timestamp needs the same treatment for the same reason: unanchored, `1400` matches `141250`
   and every other time it is a substring of.
6. **Cap the exercise at three export rounds**; each costs a human's afternoon as well as yours.
   **Stopping rule:** if a round does not move the frontier, stop and report the frontier you have,
   the localisations it leaves open, and the one export that would separate them.
7. State what you covered — how many exported signals you read, how many rounds the frontier took.
   An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Take the observation point and the failure time from the log, not from the report

Use **one Grep** of the failing log for the **Fatal markers** in `_shared/team-profile.md` (found
under its **Log location**), take the lowest hit, and **Read** one window that *starts* about 80
lines before that hit and runs on through the marker line and the lines that continue it — the only
log window this skill spends. Both ends of it are load-bearing: the pack's canonical layout in
`_shared/failure-signature-schema.md` puts the marker on one line and `expected N got N` on the
*next* line, which carries no marker and so never appeared in the Grep output. A window that stops at
the hit loses the expected value, which step 5 calls the strongest of its four references. Record
verbatim the **observation point** (the component, assertion or checker that reported the failure,
and the signal it named), the **observation time**, the **expected value** if the message carries
one, and the **run identity** per the profile's **Run identity** fact *if it happens to fall inside
that same window*.

Usually it does not. Seed, test name and build tag print in a banner at the top of the log, often
hundreds of thousands of lines above a late failure, and this skill will not spend a second Grep
chasing them. So take the run identity instead from the block that routed the failure here —
`dv-sim-log-first-error` and `dv-regression-triage-routing` both emit a `run id` field — or from the
person who handed you the failure. If neither has it, write `run id : unknown` in step 9 and record
that step 3's identity check was **not performed**. Do not go back into the log for it, and do not
let a later step quietly assume it exists.

The observation point is where the failure was *detected*, not where it was caused; the distance
between those two is what this procedure measures. Compare the log's time unit against the **Time
unit and radix** slot — if log and export print different units, every timestamp below is off by a
fixed factor and you will localise confidently into the wrong cycle. If a signature already exists
from `dv-sim-log-first-error`, take it as written; step 9 carries the same string forward. If nothing
upstream produced one, derive it here from the marker line and its continuation, using the four
fields and the normalisation order of `_shared/failure-signature-schema.md` and nothing paraphrased,
and write `?` in any field this one window does not carry — that file requires the `?` in place of a
guess, and a guessed field matches no one else's signature anyway.

### 2. Choose what to export, and ask for it

Author the request in this shape, so the next round is a diff of it:

```
scope   : <the instance path this export is taken from>
window  : <observation time minus a margin> to <observation time plus a few cycles>
clock   : <the clock these signals are sampled on, from the slot table>
reset   : <that domain's reset, from the same slot>
signals : <one per line, each with the reason it is in this round>
radix   : <the radix each multi-bit value should come out in>
format  : <the text format the Export format slot records, and which of its two row shapes>
```

- **The clock and the reset go in every round.** Without the clock in the same file there is no way
  to say which cycle a change belongs to, and the value at the sampling edge is the only value the
  design ever sees. An export without its clock is a list of numbers.
- **Size the list against the Export cost slot, not against curiosity.** If a readable export is a
  dozen signals, a request for forty comes back unusable.
- **Widen the window backwards, never forwards.** Corruption precedes detection, always.
- **If the format is row-per-timestamp, size the rows as well as the signal list.** Four 80-line
  Reads reach about 320 rows, and that is the entire budget for walking a column back to the earliest
  wrong value. Ask for the window in cycles rather than in microseconds, and for values printed once
  per active edge of the named clock rather than once per delta, so what comes back can be read
  rather than sampled at random.
- **Include one signal you expect to be correct.** A round where everything is wrong is usually the
  wrong window, scope or database, and that signal is what tells you which.
- **Check retention from the Waveform database location slot first.** A request against a database
  deleted overnight comes back empty an hour later.

Then the handoff: **ask the export owner named in the slot table to open that database in the viewer,
write the listed signals over the listed window out as text, and give you two paths — the export file
they wrote, and the waveform database they took it from.** Ask for the second path in the same
message; step 3 has no other way to tie the export to a run, and an export text file carries no
identity of its own. If the **Waveform database location** slot says the path does not encode which
run a database came from, ask them to state the run outright instead. The agent cannot open a viewer
or start a simulation, and must never describe what an export would have contained. With no database
at all, the request is instead a re-run with dumping enabled, using the profile's
**Rerun convention**.

### 3. Prove the export is usable before believing anything in it

Three **Greps**, each catching a way the round is already wasted. **The clock name** — no hits means
step 4 cannot be done and edges must not be guessed from data transitions, so go back to step 2.
**The reset name** — a window starting inside reset explains every X and zero in it and explains
nothing about the failure. **The window's last timestamp** — stopping short of the observation time
means the tool truncated it, the dump ended before the run did, or the window was mis-transcribed.

Then three checks the file cannot settle by itself, none of which costs a Grep or a Read — each
compares things you are already holding. **An absent signal means one of three things and the file
distinguishes none of them** — the dump depth never reached it, dumping started after it settled, or
the format omits an unchanged value until it changes; **Dump scope** and **Export format** tell those
apart, and absence is never evidence that a signal did not change. **The database path against the
run identity**: read which run the database belongs to off the path step 2 asked the export owner
for, using the naming rule in the **Waveform database location** slot, and compare it with the run
identity step 1 recorded — a dump from another seed reproduces nothing about today's failure. And
**the radix used against the radix asked for**: a hexadecimal value read as decimal agrees with
nothing and looks exactly like data corruption.

The identity check is the one that most often cannot be made, and saying so beats faking it. It is
**not performed** — not passed — if step 1 could not capture a run identity, if the slot's naming
rule does not put the run in the path and the export owner did not state it, or if all you were given
is the export file, which inherits nothing from the database it came out of. Record which of the six
you actually ran; conclusions from a round whose identity check was not performed are provisional on
it, and say so in `notes`.

If any of the six fails, say so and stop the round. Reasoning over a bad export yields a confident,
well-evidenced localisation of a fault that is not there.

### 4. Build the reference frame — timestamps into sampling edges

The export is keyed on simulated time; the design is keyed on clock edges, and converting between
them goes wrong in one particular way. **A signal that changes at the same timestamp as an active
edge was sampled with its old value.** Non-blocking assignment semantics place the sample before the
update inside one time step, so the value printed at edge time T is what the *next* stage sees after
T, not what this edge captured. Read a post-edge value as the sampled one and the whole trace shifts
a cycle — landing you exactly one pipeline stage too far along, everything still self-consistent.

Two rules follow. **Several changes at one timestamp are delta cycles, and their printed order is
dump order, not causality** — never say A caused B because A is listed above B at the same time. And
**a combinational net settles through intermediate values inside one timestamp**, so a wrong value
that does not survive to a sampling edge is a glitch, not the bug — unless an asynchronous reset, a
latch or a clock gate samples it, which are the three places it does matter. Spend one windowed
**Read** at the start of the window to fix the edge period and phase, then work in cycles counted
relative to the observation rather than in absolute time.

### 5. Find the earliest wrong value, not the most obviously wrong signal

"Wrong" needs a reference; without one you are describing a waveform. The legitimate ones, strongest
first: the expected value the check itself printed, recorded in step 1; the same signals exported
from a passing run over the same window; a protocol rule that holds independently of data — a request
that must stay asserted until it is accepted, a one-hot state with exactly one bit set, a counter
that must not wrap past zero; or X and Z where the design should be driving a known value. Name which
one you used, and if none is available say the localisation is unreferenced rather than inventing an
expected value.

Then **Grep** the export for the suspect signal and take the **earliest** timestamp at which it holds
a value the reference forbids — not the largest excursion, and not the value the checker quoted,
which is by construction the last one. **Read** a bounded window there and record the value at the
sampling edge *before* it too. A signal already wrong at the first edge in the window means the
window is too late, and the next round widens backwards instead of moving up.

### 6. Walk one layer up the cone — in the RTL, not in the export

The export holds only what was already asked for; what drives it is in source, under the **RTL source
root** slot. **Grep** that root for the wrong signal's leaf name and separate the two things the hits
mix together: the **declaration** (a port or a net) and the **drivers** (its occurrences on the left
of an assignment). Collect every driver — a name assigned in one branch and again in another, or
inside a generate block, has several, and taking the first hit is how a session localises into code
that never executed on this path. If that root is generated rather than hand-written, say so: the fix
belongs to whatever produced it, not to the file.

Then **do not step one level at a time. Bisect.** Module ports are the natural bisection points:
there are few, they are already named, and a value at a port is unambiguous in a way an internal net
is not — so pick the port roughly midway between the observation point and the deepest source you
suspect. Record the **frontier** after every round as two names, the shallowest signal **proven
wrong** at a sampling edge and the shallowest **proven right** at that same edge. The fault is
between them, and a round that fails to shorten that distance spent someone else's afternoon for
nothing.

### 7. Name what the fault localises as

| What the export shows | `localised as` | What settles it, and where |
|---|---|---|
| value wrong, every driver right at the sampling edge | `data` | the combinational logic between them, in source — or step 4 was read a cycle out |
| a driver already wrong at that edge | not here | move the frontier up; do not classify yet |
| X at the output, every input known at that edge | `x-source` | an uninitialised flop, an out-of-range index, an unconnected input port, a selector with no default — all in source |
| X at the output, X on an input | not here | the first X with known inputs is the source; keep walking |
| data correct, the transfer never happened or happened twice | `control` | the handshake, enable or credit pair over the same edges |
| data right but one edge late or early against the check | `sampling` | the check's own clock and edge, and whether the value had crossed a synchroniser yet |
| the signal never leaves its reset value, or never appears | `undriven` | only after step 3 ruled out dump scope and export format |
| three rounds spent, frontier unmoved | `not-localised` | say it plainly rather than picking the nearest row |

Two rows deliberately refuse to classify. Localising at a signal whose own driver was already wrong
names the fault in the wrong place, and that is the most common wrong answer this procedure prevents.

### 8. Write the next export request, with a prediction per signal

Reuse the block from step 2 and attach one line per signal saying what it will show if the current
hypothesis holds: if it is already wrong at the edge before the divergence time, the fault is
upstream and it becomes the new shallowest-wrong frontier; if it is right there, the fault lies
between it and the current shallowest-wrong signal. **A signal with no prediction attached does not
belong in the round.** That rule keeps the request at a dozen signals rather than four hundred, and
makes a surprise legible: a signal matching neither branch of its own prediction says the model of
the design is wrong, which is worth more than the round was. Carry the clock, the reset and the
known-good control signal forward every time, and widen the window backwards by a few more cycles if
step 5 found the signal already wrong at the first edge.

### 9. Record the localisation

```
signature   : <phase>|<kind>|<where>|<what>, per the shared schema
observation : <the check that reported it, the signal it named, and its time>
reference   : <which of step 5's four references was used>
divergence  : <the earliest wrong value — signal, sampling edge, value and radix>
frontier    : <shallowest proven wrong> then <shallowest proven right>
localised as: data | control | x-source | sampling | undriven | not-localised
class       : design | infrastructure | unknown
owner       : <from the area-to-owner map, keyed on the frontier, or blank plus candidates>
run id      : <whatever identifies this run for us, or unknown if step 1 could not capture it>
log         : <path, and the line range worth reading>
export      : <export path, database path, and the window, scope and radix it actually covers>
next export : <the step 8 request, or the word none if it is localised>
coverage    : <n of m exported signals read; rounds spent of the three allowed>
notes       : <anything the next person would otherwise rediscover>
```

`signature` follows `_shared/failure-signature-schema.md` — same field order, same normalisation
rules. `class`, `run id`, `log` and `notes` are the fields `dv-sim-log-first-error` emits, so a
failure routed from there keeps its vocabulary — and that block is also where a `run id` this skill's
single log window did not catch should come from, rather than a second Grep. `class` is
`infrastructure` when step 3 found the export or the dump at fault rather than the design. Route on the frontier's hierarchy through the
profile's **Area to owner map**, never on the test name, and leave a field empty rather than filling
it plausibly.

## Gotchas

- **A signal changing at the active edge was sampled with its old value.** This produces the most
  fluent wrong answers: the trace shifts one cycle, every stage still looks consistent with its
  neighbour, and the report blames the module before the real one.
- **Absence in the export is not "it never changed".** Dump depth, dump start time and a format that
  omits unchanged rows all look identical — an empty region. Settle it from the **Dump scope** and
  **Export format** slots before reporting a signal as stuck.
- **A net optimised away has no values to export.** Simulators merge or delete nets not marked for
  dumping at compile time, and the export shows a constant or nothing. Ask the export owner which
  visibility setting the dump was taken under and ask for that scope to be re-dumped — a flag
  question for them, never one to guess — expecting a slower re-run that occasionally schedules
  differently.
- **X handling is optimistic in one place and pessimistic in another, and both mislead.** A
  conditional on an X takes the false branch, so RTL simulation can hide a real bug behind a clean
  path; an X on any operand of an arithmetic or shift operation poisons the whole result, so the
  export shows a wide X band the gates would never produce. Do not read band width as severity; do
  trust the *first* X that appears with all its inputs known.
- **A glitch is not a value.** Combinational nets settle through several deltas inside one timestamp;
  only what survives to a sampling edge reached a flop — except at an asynchronous reset, a latch or
  a clock gate, where a transient genuinely is captured.
- **Two clock domains in one export read as one broken design.** Values interleave against a single
  time axis and a correct crossing looks like corruption. Export one domain per round, or export both
  clocks and label every signal with its domain.
- **The database may not be from the run you are debugging.** Databases are named per run and deleted
  on a schedule, so the database *path* is the only thing tying an export to a run — the exported
  text carries no identity of its own, and neither does an export file written to a scratch name. Ask
  for that path with the export, not afterwards, once the owner has moved on. A run-identity mismatch
  invalidates every conclusion in the round, not some of them.
- **The checker's expected value is a claim, not a reference.** If the scoreboard's reference model is
  wrong, the "wrong" signal is right and the cone walk goes into perfectly good RTL. Confirm the check
  is one the team trusts on this interface before spending a round.
- **Back-pressure makes the guilty side the quiet one.** In a stalled handshake the wrong signal is
  the one that never asserted, not the one stuck asserted — and a signal that never changes produces
  no rows at all in a change-driven export. Ask for both halves of the pair explicitly.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the **frontier names two signals**, one proven wrong and one proven right. One name alone means no
  bisection happened and the report is a description.
- every value quoted carries a timestamp **and** the sampling edge it belongs to, and its radix.
- `localised as` is one of the block's tokens, and `undriven` was reached only after step 3 ruled out
  dump scope and export format.
- the reference used is named and is one of step 5's four. "It looked wrong" is not one of them.
- the next export request carries the clock, the reset, and a prediction on every signal.
- the `coverage` line states how many exported signals were read and how many rounds were spent, and
  nothing rests on a screenshot or on values typed into the conversation.
- step 3's identity check is reported as passed, failed **or not performed**, and the `export` line
  carries the database path it was made against. "The export is from the right run" with no path and
  no `run id` to compare it to is an assumption wearing a check's clothes.

A wrong answer typically names the module where the failure was *observed* as the module where it was
caused; or reads a post-edge value as the sampled one and blames the stage before the real one; or
declares "the signal is X" without naming the first point at which an X appears with known inputs.

## Done when

You can name the two signals the fault sits between, what the fault between them is localised as, and
the one export that would halve that distance again — or say plainly that three rounds did not move
it.
