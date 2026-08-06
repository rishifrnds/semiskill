---
name: dv-memory-perf-bandwidth
description: Reconcile a measured bandwidth, latency and efficiency result against the databook claim, attribute the shortfall to a named overhead with the counter that proves it, and compare like-for-like against the previous release. Use when a performance number misses the number we publish, when bandwidth or latency has moved since the last release, when someone asks whether two performance numbers are even comparable, or when a performance result has to be reproducible by another engineer.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Bandwidth, Latency and Efficiency Measurement Against the Databook
  semiskill-function: design-verification
  semiskill-role: memory-ip-dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-09-24
  semiskill-tags: performance, bandwidth, latency, efficiency, ddr, memory-controller, regression
---

# Bandwidth, Latency and Efficiency Measurement Against the Databook

When the product claim *is* the performance number, a measurement nobody can repeat is worth nothing,
and a comparison between two numbers sampled at different points is worse than nothing. Almost every
"we missed the databook" escalation is one of three things: the two numbers were taken somewhere
different, the traffic never saturated the interface, or the configuration moved while the RTL stood
still. The output is **a reconciled number, every lost percent attributed to a named overhead with
the counter behind it, and a statement of what is comparable to what** — not an opinion about whether
the design is fast.

**What this cannot do.** It reads performance reports, counter dumps and configuration files already
on disk. It cannot start a simulation, drive a traffic generator, open a waveform or sweep a
parameter; every step needing one of those ends in a named handoff and says so.

## When to use something else

- The run **failed** rather than being slow — start at `dv-sim-log-first-error`.
- A **JEDEC timing check actually fired** during traffic — a correctness failure, not a performance
  shortfall, and it belongs to `dv-mem-timing-check-triage`.
- Initialisation or training never completed, so there is no steady state at all — `dv-memory-model-training`
  first, then come back once traffic is flowing.
- The loss is refresh scheduling, self-refresh or power-down entry and exit — attribute it here, then
  hand the mechanism to `dv-mem-refresh-lowpower-audit`.
- Controller and PHY each blame the other at their shared boundary — `dv-dfi-boundary-blame`.
- A whole night of results needs sorting first — `dv-regression-triage-routing`.
- `dv-minimal-reproducer` shrinks a *failure*; shrinking a performance run changes the number, so it
  does not apply here.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Databook claim | [[FILL: which document and clause states the bandwidth, latency and efficiency numbers we publish for this configuration, and whether it is a file that can be read from disk]] | IP product owner |
| Claim conditions | [[FILL: the traffic pattern, read/write mix, address map and speed bin each published number is claimed under]] | architect |
| Measurement point | [[FILL: where each of our performance numbers is sampled — the controller port, the DFI boundary, or the DRAM data bus — and which monitor emits each one]] | performance owner |
| Performance report | [[FILL: where a run's performance report and its counter dump land, and what format each is in]] | DV infra |
| Counter names | [[FILL: the exact counter labels our monitor prints for data beats, activates, precharges, refreshes, direction changes, idle cycles, queue occupancy, and commands issued per window]] | performance owner |
| Window markers | [[FILL: the strings that mark the start and the end of the steady-state measurement window in our report]] | performance owner |
| Traffic profile | [[FILL: where this run's traffic-generator profile is recorded; which setting caps outstanding requests; whether that cap is a request count or a byte budget; and where the bytes one request moves is recorded]] | VIP owner |
| Address map config | [[FILL: where the address-map and timing configuration used by this run is recorded]] | controller owner |
| Noise band | [[FILL: how many repeats we require for a performance number, and what run-to-run spread we treat as noise rather than a regression]] | DV lead |
| Release baseline | [[FILL: where a previous release's performance reports are archived, and how a release is identified]] | release owner |

**Run identity** and **Rerun convention** are pack-wide facts and live in `_shared/team-profile.md` —
read them from there rather than re-asking. **Performance report is narrower than the profile's Log
location**: it is the performance report and counter dump, which may or may not land beside the
simulation log. Do not assume the two are the same directory, and do not treat them as the same fact.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented counter label or an
invented claim condition produces a confident percentage that no one can reproduce, and unpicking a
published wrong number costs more than having no number.

## Retrieval budget — read this before opening anything

A counter dump can be one line per cycle, and a long performance run produces hundreds of megabytes
of them. Work in this order and stop as soon as step 6 accounts for the gap to within the noise band:

1. **Grep and Read work on files, not on chat text.** If the number arrived pasted into the
   conversation, ask for the path under the Performance report slot. Until a path exists you may
   reason over the pasted figures by eye — say that is what you did, and mark every derived
   percentage provisional.
2. **Never open a counter dump or a trace with Read.** Locate the summary block with **Grep**, then
   Read only a bounded window around the line number it returns.
3. **Every Read is positioned by a Grep that has already been spent**, and the order below is the
   order the procedure spends them in. The whole budget is **one Glob, three Greps and four windowed
   Reads of about 60 lines each**:
   - **Glob** (step 1) — this run's report, the archived previous-release report, the traffic profile
     and the configuration file.
   - **Grep C** (spent in step 1; its hit also serves step 3) — the databook extract, **only** if that
     slot resolved to a readable text file. If it is a PDF or a deck, skip it and treat the claim as
     a handoff.
   - **Grep A** (spent in step 2; its hits also serve steps 4 and 6) — one pattern alternating the
     window markers, the counter names and the measurement-point monitor label, over both reports at
     once. Nothing is read before it: its hits are the line numbers Reads 1 and 2 open at.
   - **Read 1** (steps 2, 3, 4, 6, 7) — this release's summary block at the window-end marker.
   - **Grep B** (spent in step 5; its hits also serve steps 6 and 8) — one pattern alternating the
     outstanding-request setting, the bytes one request moves, the read/write mix and the address-map
     mode, over the traffic profile and the configuration file. Its hits position Reads 3 and 4.
   - **Read 3** (steps 6, 8) — the address-map and timing configuration window.
   - **Read 4** — the spare, spent wherever the attribution lands, usually the traffic profile.
   - **Read 2** (step 8) — the same summary block in the previous release's report, at Grep A's hit.
4. More than about 200 hits from one Grep means the pattern matched a per-cycle field rather than a
   summary label. Narrow it before reading anything.
5. Stopping rule: once the four windows are spent and the residual in step 6 still exceeds the noise
   band, stop — report the fraction attributed, the residual, and the one artifact still needed.
6. State what you covered: how many claimed numbers were reconciled and how many repeats each rests
   on. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the claim, and both numbers, to files on disk

Before any arithmetic, settle which databook number is being tested, what the **Claim conditions**
slot says it is claimed under, and where this run's report is. Use the single **Glob** to locate the
report, the archived previous-release report, the traffic profile and the configuration file.

If the Databook claim slot points at a readable text file, spend **Grep C** on it for the claimed
figure and its stated conditions. If it points at a PDF, a spreadsheet or a deck, **Read** cannot open
it — ask the IP product owner for the figure, its units and its conditions, record who supplied them,
and mark every comparison resting on them provisional. A claim with no file and no clause must never
be written up as though it had one.

### 2. Pin the measurement point before reading a single number

This is where the escalation usually dies, so do it before the numbers are in your head. **Spend
Grep A here, first** — one pattern alternating the Window markers, the Counter names and the monitor
label named in the **Measurement point** slot, over this run's report and the archived one in the
same call. Nothing below can be positioned until it comes back: its hits are the line numbers
**Read 1** and **Read 2** open at, so no Read happens before this Grep.

Then open **Read 1** on this release's summary block and record where the number was sampled,
verbatim, mapped onto exactly one token:

- the controller port, where the interconnect presents traffic — `measured at: port`
- the DFI boundary between controller and PHY — `measured at: dfi`
- the DRAM data bus itself, the DQ bus the memory model sees — `measured at: dq-bus`

If the report names a monitor rather than a point, resolve the monitor through the **Measurement
point** slot before choosing a token; never infer the point from the monitor's name. Numbers taken at
different points are not comparable, and no later arithmetic makes them so. If the report does not
say, write `measured at: not-stated`, treat every comparison below as provisional, and report that
gap in the flow as a finding in its own right.

### 3. Establish the theoretical peak, and the units, from first principles

Derive the peak rather than copying it: a double-data-rate interface transfers twice per clock, so
peak equals the transfer rate in MT/s times the bus width in bytes. A 64-bit channel at 6400 MT/s
carries 51.2 GB/s decimal, which is 47.7 GiB/s binary — a "shortfall" of exactly that 7.4% is a units
disagreement, not a design problem. Write the units beside every number from here on, and state which
efficiency denominator you are using, because there is more than one and the databook rarely says.

This is the one number the procedure calculates rather than locates, so it gets a check of its own.
Record the data rate and the bus width you multiplied, each with the file they came from, so the next
reader re-derives the peak instead of trusting it. Then reconcile it once: if **Read 1** or the
databook extract already in hand from **Grep C** prints a peak of its own, yours must agree with it
to the digit. A disagreement is the finding — usually a width that silently counts a second channel,
a rate quoted per pin against a peak quoted per channel, or the decimal-and-binary gap above — and
until it is settled every efficiency below rests on the wrong denominator. If no file prints a peak,
say exactly that: the peak is derived and unchecked, and every percentage resting on it inherits it.

### 4. Confirm the window is steady state

**Grep A** is already spent — step 2 made that call, and its Window-marker hits across both reports
are in hand. Do not issue another. Working from those hits, check in **Read 1** that the window
excludes initialisation and training at the front and the drain at the back, and that both reports
use the same marker strings.

A window that includes initialisation drags the average down by an amount that depends on run length,
so the same design yields a different number from a longer test. If the window is not marked, nothing
derived from it is reproducible — that is the finding, so **ask the engineer to rerun with the window
markers enabled and give you the path to the new report** rather than averaging over the whole file.

### 5. Check the traffic actually saturated the interface

An unsaturated generator measures the generator. Sustained bandwidth equals the **bytes** in flight
divided by round-trip latency, so the bytes the generator is allowed to keep outstanding must be at
least the target bandwidth times the observed latency. Both sides of that inequality are bytes — and
the **Traffic profile** slot says whether the cap is written in bytes or, far more often, as a
*count* of outstanding requests. A count is not a byte quantity: multiply it first by the bytes one
request moves (burst length times the data-bus width, which the same slot records) and compare the
product. Setting a cap of 64 against 51.2 GB/s compares two different things and always answers yes.

Spend **Grep B** here — the outstanding-request setting, the bytes per request, the read/write mix
and the address-map mode, across the traffic profile and the configuration file in one call — then
work the inequality against the latency already in **Read 1**. Put both sides, in bytes, into `notes`
so the next reader re-checks the comparison instead of repeating the run, and branch:

- the byte budget clears bandwidth times latency — `saturation: demonstrated`.
- it does not — stop. **Ask the engineer to rerun with more outstanding requests and send back the
  path to the new report**, and record `saturation: generator-limited` until they do.
- a side is missing: no latency inside the window, no cap in the profile, or a cap whose unit the
  slot does not settle — `saturation: not-measurable`, naming which of the three was absent. That is
  a gap in the flow and a finding of its own, never a verdict about the design.

Excellent latency together with disappointing bandwidth is the generator-limited case almost every
time. Reporting a generator-limited number as a design shortfall is the most expensive wrong answer
available here.

### 6. Attribute the loss, one overhead at a time

Efficiency is achieved over peak. The useful work is saying where the rest went. Take the counter
values out of **Read 1** — every label in the **Counter names** slot, queue occupancy and commands
issued per window included — and the map and timing settings out of **Read 3**, opened at Grep B's
hits in the file the **Address map config** slot names. Work down this table; each row is settled by
evidence you already have open.

| Overhead | What settles it | The tell |
|---|---|---|
| Refresh | the refresh counter over the window, against the refresh interval and duration in use | roughly constant across traffic patterns; grows with device density and with high-temperature derating |
| Row miss | activate and precharge counters against the read and write command counts | activates per access approaching one; page hit rate near zero |
| Bus turnaround | direction-change count times the turnaround penalty | scales with the read/write mix and disappears at a single direction |
| Activate rate cap | activates per window against the four-activate window and the activate-to-activate delay | only at high data rates with scattered addresses; the activate counter sits at the cap |
| Bank-group timing | which address bits the map assigns to bank group | back-to-back accesses landing inside one bank group |
| Command bandwidth | the controller-to-DRAM frequency ratio against commands issued per window | command slots run out before the data bus does |
| Scheduler or arbitration | queue-occupancy counters, and port idle while the DRAM bus is busy | the port stalls while the data bus still has gaps |
| Testbench limit | the outstanding-request setting against step 5 | latency excellent, bandwidth low |

Write the residual — the percentage you could not attribute — explicitly. A residual under the noise
band is a finished attribution; a residual of twenty points means the table has not been worked, not
that the design has a mystery.

### 7. Report latency as a distribution, never as a mean

From the same **Read 1** window, take p50, p95, p99 and the maximum, and say how many samples the tail
rests on: a p99 quoted over three hundred transactions is three samples and cannot support a claim.

Say whether the figure is loaded or unloaded. Latency near saturation is *supposed* to be far worse
than latency at low load — that is queueing, not a defect. Quoting a loaded measurement against an
unloaded claim, or the reverse, manufactures a regression out of nothing.

### 8. Compare against the previous release like-for-like — configuration first

Open **Read 2** on the archived previous-release report under the Release baseline slot. Then, before
comparing any number, diff the configuration: spend the remaining half of **Grep B** and **Read 3** on
the address map, the timing settings, the speed bin, the read/write mix and the outstanding-request
setting. A performance move with an unchanged RTL revision is a changed configuration until proven
otherwise, and the address map moves the number further than most RTL changes do.

Only once the configurations match do the numbers mean anything. Apply the Noise band slot: a
difference inside the band is not a regression, it is a request for more repeats. If the number of
repeats behind either figure is unknown, say so — **ask the engineer for the repeat count and the
spread**, and leave the comparison open rather than declaring a regression on one run each.

Then settle the verdict against the databook claim itself, using that same band:

- the measurement point, the window and the conditions all match the claim's, and achieved sits
  inside the band of the claimed figure — `vs claim: meets`.
- achieved falls short of the claim by more than the band — `vs claim: below`. Step 6's attribution
  is what turns that into a finding rather than a complaint; without it there is nothing to act on.
- achieved beats the claim by more than the band — `vs claim: above`. Do not bank it. A number better
  than the databook almost always means a measurement point nearer the DRAM than the claim's, refresh
  disabled, a friendlier pattern than the **Claim conditions** slot states, or a peak derived at the
  wrong data rate — re-check steps 2, 3 and 5 and say in `notes` which of the four you eliminated.
- the measurement point, the window or the conditions differ from the claim's, or either figure came
  from a person rather than a file — `vs claim: not-comparable`, naming which.

### 9. Record the finding

Fill in this block. `class`, `run id`, `config diff` and `notes` reuse the field names from
`dv-sim-log-first-error` and `dv-minimal-reproducer` so the blocks read side by side; the rest are
this skill's own.

```
claim       : <the databook figure, its units, and the document and clause it came from>
conditions  : <traffic pattern, read/write mix, address map and speed bin the claim is stated under>
measured at : port | dfi | dq-bus | not-stated
window      : <the start and end markers, and the span everything below rests on>
peak        : <theoretical peak, the data rate and bus width it was derived from, and the units>
achieved    : <the measured figure, in those same units>
efficiency  : <achieved over peak as a percentage, with the denominator named>
saturated   : confirmed | not-confirmed | not-measurable
latency     : <p50, p95, p99, max, sample count, and loaded or unloaded>
attribution : <each overhead row with the counter that settles it, and the unattributed residual>
vs claim    : meets | below | above | not-comparable
prev release: <the archived release compared against, and its identifier>
config diff : <every difference between the two runs' configuration, including the cosmetic ones>
class       : design | infrastructure | unknown
run id      : <whatever identifies this run for us>
report      : <path, and the line range worth reading>
coverage    : <how many claimed numbers were reconciled, how many repeats each rests on, and which
               figures came from a person rather than from a file>
notes       : <anything the next person would otherwise have to rediscover>
```

Leave a field empty rather than filling it plausibly. `vs claim: not-comparable` is a useful, honest
result and is the correct answer whenever the measurement point, the window or the conditions differ
from the claim's — say which of the three, so the next run can be set up properly.

## Gotchas

- **Decimal and binary units differ by 7.4%.** JEDEC transfer rates are decimal, and half the tools
  that print bandwidth divide by a power of two. A regression of exactly that size is a units change.
  Quote GB/s or GiB/s explicitly on every figure, including the databook's.
- **Efficiency has a denominator, and it is usually not written down.** Data-bus efficiency counts
  beats on the DRAM bus against the beats the data rate could carry; port efficiency counts bytes
  accepted at the controller port against the same peak, and additionally loses everything the
  controller drops to arbitration and to the clock ratio. Checking a port measurement against a
  data-bus claim reads as a shortfall of ten to twenty points that does not exist.
- **Excellent latency plus low bandwidth is a testbench limit, not a design limit.** The generator
  that is not allowed enough outstanding requests keeps every one of them fast. Check the setting
  before reading anything into the bandwidth.
- **Refresh overhead is roughly the refresh duration over the refresh interval, and it is not a
  constant.** The duration grows with device density, and the interval halves when the model is
  derated for the high-temperature range — so the same RTL loses noticeably more bandwidth on a
  larger part or a hotter model. A figure measured with refresh disabled is not the databook's figure.
- **Read/write turnaround is the largest lever in any mixed profile.** Every direction change costs
  the turnaround time, and the scheduler recovers it only by grouping accesses. Efficiency at a
  balanced mix is far below efficiency at a single direction, and a claim quoted at one must never be
  checked with the other.
- **The address map moves the number more than the RTL does.** A map that spreads sequential addresses
  across banks and bank groups converts row misses into hits; a map that concentrates them into one
  bank collapses efficiency. Diff the map before you diff the design.
- **Same-bank-group accesses are slower than different-bank-group ones** in the DDR families that
  define both column-to-column delays. A profile whose addresses happen to land inside one bank group
  is a worst case no databook quotes — check the bits the map assigns to bank group before reporting
  a shortfall.
- **The activate rate is capped independently of the data bus.** The four-activate window and the
  activate-to-activate delay limit how many rows can be opened per unit time, so a random-access
  pattern at a high data rate can be command-limited while the data bus still has gaps. That is a
  JEDEC limit, not a controller defect.
- **The measurement window is part of the result.** Including initialisation, training or the drain
  makes the answer depend on run length, which is why the same build "improves" when someone
  lengthens the test. If the window is not marked in the report, nothing derived from it is
  reproducible.
- **Two runs of one build differ.** Without a stated repeat count and a noise band, a single-run
  comparison cannot separate a two-percent regression from ordinary spread — and a move smaller than
  the band is a request for repeats, not a finding.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the measurement point is stated for **both** numbers being compared, and they are the same point
- the theoretical peak was derived from a data rate and a bus width that appear in a file, with units
  written next to it, and the efficiency denominator is named
- `saturated: confirmed` rests on the outstanding-request setting compared against bandwidth times
  latency — not on the traffic profile merely being described as heavy
- the window excludes initialisation, training and drain, and both compared runs use the same markers
- every attributed overhead names the counter that settles it, and the residual is written down
- latency is a distribution with a sample count, and its load condition matches the claim's
- the configuration diff was done **before** the number diff, and the difference exceeds the noise band
- anything supplied by a person rather than by a file is attributed and marked provisional

A wrong answer typically compares a port measurement against a data-bus claim; declares a regression
from one run each with no spread; reports a generator-limited bandwidth as a design shortfall; blames
the RTL for what an address-map change did; or quotes a single mean latency against a claim stated at
a different load.

## Done when

You can name the number, the point it was measured at, every percent it lost and to what, and whether
it is comparable to the claim at all.
