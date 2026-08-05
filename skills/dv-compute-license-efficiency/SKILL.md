---
name: dv-compute-license-efficiency
description: Turn a regression that costs more every month into a defensible trimming proposal — a baseline in one named cost unit whose counted and sampled parts are kept apart, a cost per verified feature over a denominator somebody actually counted, a per-test contribution ledger, a ranked candidate list, and a projected saving whose risk and reversal are both stated. Use when regression cost is growing faster than coverage, when someone asks why the nightly still takes eleven hours, when the farm or the simulator licence pool is questioned before a renewal, or when you have to defend removing tests to a verification lead.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Compute and Licence Efficiency: Cost per Verified Feature"
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: principal
  semiskill-owner: dv-guild
  semiskill-version: 1.2.0
  semiskill-review-by: 2027-09-03
  semiskill-tags: regression, cost, licences, farm, coverage-ranking, seeds, tiering, efficiency
---

# Compute and Licence Efficiency: Cost per Verified Feature

Every regression grows and none of them shrink, because adding a test is one line and removing one is
an argument. By the time anyone notices the curve, the answer — which tests are paying for themselves
— is spread across artifacts nobody joins: a scheduler's accounting rows, a test list, and a coverage
ranking most teams generate once and never open again.

The output is a **trimming proposal**: one named cost unit, a baseline whose counted, sampled and
asked-for parts are separated, that baseline divided by a denominator somebody actually counted — the
cost per verified feature this skill is named for — and a ranked candidate list where every candidate
carries its evidence, what stops being produced if it is accepted, and the single edit that puts it
back. Not a percentage.

## When to use something else

This is about the *cost* of a regression, not its results. A night of failures to sort is
`dv-regression-triage-routing`; one failing log is `dv-sim-log-first-error`. Which tier a test belongs
in and how many seeds it gets is `dv-regression-tiering-farm` — that decides the shape, this prices
it. A disputed coverage number, or a hole needing classification before anything is trimmed, is
`dv-coverage-merge-report`. If one slow failure is the expensive thing, `dv-minimal-reproducer`
shrinks that run; if the cost is rebuilding rather than simulating, `dv-build-filelist-hygiene`; and
if you cannot yet say which file defines the tier, start with `dv-repo-orientation`.

Closest neighbour, and the one to get right: making *one run* cheaper — profiling where its time and
memory go, and deciding whether switching off coverage collection or waveform dumping is worth it for
that run — is `dv-regression-runtime-tuning`. It tunes a run; this decides which runs are worth
paying for. The two meet in step 6 and step 7: a debug setting left on by default, or a
`stop-collecting` candidate, is priced here and then handed to that skill to size and to change, and
"the nightly does not fit its window" belongs there when the fix is per-run runtime and here when the
fix is how many runs there are.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Cost and status columns | [[FILL: which columns of our regression summary carry wall-clock, CPU time, core count and memory, whether it reports them at all, and what its status column writes for a job killed at a wallclock or memory limit]] | DV infra |
| Farm accounting | [[FILL: whether our job scheduler or licence manager writes a per-job accounting file we can read, where it lands, what one row holds, and whether rows are written in submit order]] | CAD / IT |
| Licence model | [[FILL: how many simulator seats we hold, whether the pool is an annual purchase or metered, how many seats one multicore run occupies, and — where any part of it is metered or rented — the rate we are charged, per what, and who owns that contract]] | verification manager |
| Tier definitions | [[FILL: which tiers we run, how often each runs per week, and the entry rule that decides which tier a test belongs to]] | verification lead |
| Test list source | [[FILL: which file defines the tests and the seed count per test in each tier, and how a seed count is written there]] | DV infra |
| Closure record | [[FILL: where we record which verification-plan features or coverage items changed to closed in a period, whether that record is a file we can read or a tracker a person must query, and who can give us the count]] | verification lead |
| Ranking report | [[FILL: whether we produce a per-test coverage ranking, whether it is a greedy incremental ranking or a per-test unique count, and where its text report lands]] | coverage owner |
| Coverage model revision | [[FILL: how we record which revision of the coverage model a merged database was built against]] | coverage owner |
| Bug-find record | [[FILL: whether we record which test and which seed found each bug, where that record lives, whether it is a file we can read or a tracker a person must query, and who can answer for it]] | DV lead |
| Trim authority | [[FILL: who approves removing, re-tiering or re-seeding a test, and what evidence they require before they will]] | verification lead |

Where the regression summary lands and where merged coverage lands are pack-wide facts in
`_shared/team-profile.md` — read them there rather than asking again, and the profile's **Infra
markers** are reused as-is in step 6, on their own count. Four slots above are deliberately
**narrower** than, or simply different from, a profile fact, and are not the same question:

- **Cost and status columns** is narrower than the summary format, which records the test, seed and
  log columns; a summary can carry all of those and no resource column at all. Its status half must
  **not** be filled in from the profile's infra markers. An infra marker is a string the flow prints
  into a log when the environment failed — licence, queue, host, disk. A kill at a wallclock or memory
  limit is a status the scheduler or the summary writes *about the job*, usually a different word from
  a different producer, and step 6 needs both and counts them apart.
- **Ranking report** is narrower than the coverage-output fact, which records where the merged
  database lands — a merged database is not a ranking, and whether a ranking exists, and of which of
  the two kinds, is what step 5 turns on.
- **Closure record** is not a coverage fact at all. Coverage output says where a merged database
  lands; this says how many features or coverage items *changed to closed* between two dates. That
  count is the denominator step 1 fixes, and no merged database carries it.
- **Bug-find record** is not the profile's known-issue list. That list says which failures are already
  understood, keyed on a failure; this says which *test and seed* was credited with finding a bug,
  keyed on a test. Step 5 needs the second, and a known-issue list cannot answer it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented seat count or
per-run cost produces a proposal that is arithmetically tidy and wrong, and one caught wrong ends
the practice for two years.

## Retrieval budget — read this before opening anything

Accounting exports and ranking reports are among the largest text artifacts a DV team owns: one row
per job per night, one row per coverage item per test. Read them by pattern, never whole.

1. **Grep, Read and Glob work on files on disk**, not on a table pasted into a chat. If the numbers
   arrived pasted, ask for the path they came from before Grepping anything; if no path exists, say
   so and mark every figure taken from the paste unverified.
2. **Glob first, at most eight times** — the closure record; the tier definitions; the test list
   source, which is a second slot with a second owner and is often but not always the same file (where
   one file answers both, that Glob stays unspent); this period's summary; the comparison period's
   summary; the ranking report; the farm accounting export; the bug-find record.
3. **Never open one of these with Read first.** Over roughly 1500 lines, **Grep** for the row pattern
   the cost-and-status-columns slot describes and Read only around the hits.
4. **One whole-file operation is affordable and only one shape of it: a counting Grep** — asking for
   the *number* of matching lines rather than for the lines. It returns one integer whatever the
   file's size, that integer is exact, and it is the only **counted** figure this skill may quote over
   rows nobody read. It still spends one of the Greps below. Everything else that needs every row — a
   column summed, a maximum, a concurrency profile — is out of reach here and must be derived from a
   sample and labelled so, or asked for; step 3 says which, per figure.
5. Whole-exercise cap: **ten Greps and twelve windowed Reads of about 120 lines**, no more than four
   windows inside any one artifact.
6. The allocation, which no step may exceed: step 1 spends one Glob, one Grep and one window in the
   closure record, and nothing at all where that record is a tracker rather than a file; step 2, six
   Globs, one Grep and one window; step 3, two counting Greps and three windows; step 4, one Grep and
   one window; step 5, one Glob, three Greps and four windows — two Greps and three windows in the
   ranking report, one Grep and one window in the bug-find record, and neither where that record is a
   tracker; step 6, two Greps and two windows, **at most one of them in this period's summary**. Steps
   7 to 9 open nothing. That sums to eight Globs, ten Greps and twelve windows exactly.
7. The per-artifact window cap binds in exactly one place, and it is the reason step 6 is held to one
   window in the summary: on a team with **no** farm accounting export, step 3 falls back into this
   period's regression summary and spends three windows there, so step 6 may spend one and no more.
   Its second window goes in the test list or the tier file. Where a team has an accounting export,
   step 6 has the summary to itself and the cap is not near.
8. A **Grep** returning more than about 200 hits is too broad — narrow it, or ask for the count
   instead of the lines.
9. Individual run logs are out of scope: reconstructing a cost the summary never carried spends the
   whole budget on one row. Record that figure as unavailable instead.
10. State what was covered, per figure and not once for the document — "run count 640, exact, from a
    counting Grep; per-run cost sampled from three windows totalling 341 of those rows; peak a lower
    bound; ledger from a greedy ranking over 210 of 640 tests; bug-find checked on 9 of 14 candidates;
    the rest unassessed". An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Fix the unit, then go and count the denominator

Three things get called the cost of a regression and they do not move together:

- **Wall clock** — first submit to last result. What a person waits for. Bounded below by the
  longest single run plus that run's queue wait, so deleting a thousand two-minute tests cannot move
  it.
- **Core-hours** — runtime times cores held, summed over runs. What farm capacity is spent on, and,
  where that capacity is metered or rented rather than owned, what an invoice is written against.
- **Seat-hours** — simulator licences held, integrated over time. What caps how many runs are in
  flight, and what an annual licence pool is sized on.

Only the second and third have a contract behind them, and they have different ones: an annual pool
is a purchase already made, metered capacity is a bill still arriving. Step 8 turns on that
difference, so do not merge them here.

Ask which one the complaint is about, name it once at the top of the proposal, and put every later
figure in it. A saving in the wrong unit is dismissed on sight: "we cut 40% of core-hours" answers
nothing when the complaint was that results arrive at 11am.

Then fix the denominator, because cost *per verified feature* is the figure this skill is named for
and the one nobody has. It needs a denominator that does not move underneath the number — features
moved to closed in the verification plan this period, or coverage items newly closed. Coverage
**percentage** is a poor denominator: its own denominator changes whenever the coverage model
changes, and it saturates, so cost-per-percent climbs steeply at the end of every project for
reasons unrelated to efficiency.

Then go and get the count, because a denominator nobody counted is a denominator nobody will accept.
If the closure-record slot names a file, **Glob** for it once, spend **one Grep** for the closed-state
pattern the slot describes and **one windowed Read** around the hits, and record the count with its
file and line. If the slot names a tracker instead, this is a handoff: **ask the verification lead how
many features or coverage items changed to closed between the two dates of this exercise**, and record
the answer as asserted with their name against it. Both answers feed the step 9 proposal block:
`denominator` says what was counted, over which two dates, and from where; `cost per feature` is the
step 3 baseline divided by it, in the unit named above.

Three ways that division goes wrong, each survivable if it is stated:

- **Nothing closed this period.** Then there is no cost per feature. Write it not-available with the
  reason rather than dividing by a number rounded up to one.
- **Closure is lumpy and the work is not.** A feature that closed in March was worked on from
  January, so one period's ratio is noisy — quote it beside the previous period's figure from step 4
  rather than alone, and never to more than two significant figures.
- **The closure record and the coverage model moved together.** A re-cut model changes what an item
  *is*, so items closed either side of it are not the same unit. That is the first check in step 4,
  and it invalidates the ratio as well as the trend.

### 2. Establish scope — what actually runs, and how often

**Glob** for the tier definitions and, separately, for the test list source: two slots, two owners,
and on many teams one file — where the same file answers both, note that and leave the second Glob
unspent; where they are two, the tier file gives the entry rule and the run frequency and the list
file gives the tests and seeds, and step 6 needs both. In the same six Globs, locate this period's
summary, the comparison period's summary, the ranking report and the accounting export that steps 3
onwards will want. Then one **Grep** for the seed-count pattern the test-list-source slot describes
and one windowed **Read**. Record per tier: distinct tests, total runs (tests times seeds), and runs
per week.

Runs per week is the multiplier every later saving is stated against, and it dominates everything
else — thirty minutes saved nightly is worth roughly thirty times the same thirty minutes saved in a
tier that runs at each milestone. A candidate list ordered without it proposes the wrong changes in
a convincing order. If the tier is assembled at submit time by something no file records, say so:
scope is then whatever the summary shows, and every scope figure is derived rather than read.

### 3. Measure the baseline, and mark every figure counted, sampled or asked for

Two **counting Grep** calls and at most three windowed **Read**s, in the accounting export if the
slot says one exists, otherwise the summary. **Prefer the accounting export.** A scheduler row
carries real occupancy — submit, start, end, cores, memory — while a summary usually carries only the
simulator's own reported runtime, which excludes queue wait, build and post-processing. Those are
different quantities and must never be added into one total; say which source each number came from.

Spend the first **Grep** in count mode on the row pattern for the period: it returns the exact number
of matching rows without returning the rows, which is **total runs**, and it also says roughly where
the file ends. Spend the second the same way on that pattern narrowed to the tier under analysis.
Those two figures are counted rather than sampled and may be quoted flat. Then three windowed
**Read**s: the first rows, the last rows — aimed a little inside the line number the count implies,
so the offset lands in the file — and one interior window for per-run cost. What those windows can
and cannot support, in the unit chosen in step 1:

- **Tier wall clock**, first submit to last completion, is readable from the first and last windows
  **only if the export is written in submit order**, which the farm-accounting slot records. If rows
  are grouped by tier, by host, or by nothing, those two windows are not the extremes: write wall
  clock not-available and **ask the engineer for the scheduler's own report for the period** instead.
- **Core-hours** — runtime times cores, over every run — cannot be summed from three windows, which
  at about 120 lines each reach roughly a fifth of a 1500-row export. Take the mean per-run cost from
  the rows actually read, multiply by the exact run count from the counting Grep, and mark the product
  derived with its sample size beside it. Where a true total is wanted, that is a handoff: **ask CAD
  for the accounting system's own period total** and take the number from there.
- **Peak concurrency** cannot be recovered from a sample at all, and this is the one people get
  wrong. It needs every job's start and end interval across the whole period; a contiguous window can
  only show that the peak was *at least* what that window held. A peak counted here is therefore a
  **lower bound** and must be written as one. A lower bound supports "we hold at least this many at
  once" and "there is a burst"; it can never support "we can free seats", which is exactly the claim
  step 8 needs. For that, **ask whoever runs the licence manager or the scheduler for its own
  peak-checkout figure for the period and the time it occurred** — that report exists and it is one
  number.

Say on the `peak` line which of the three it is: a full-period figure from that report, a lower bound
from the windows read, or not-available. Peak, not average, is what sizes a licence pool — a trim
that lowers average occupancy and leaves the nightly burst intact frees no seats. Then write the
`baseline basis` line, which is where the counted, the derived and the asked-for parts of this step
are separated for the reader who has to defend the number without you in the room.

If a resource column is absent, write it absent. No memory column means memory-driven waste — jobs
holding large-memory hosts they never needed — is not assessable here, and saying so beats dropping
the category silently.

### 4. Establish the trend, and whether the two periods are comparable

One **Grep** and one windowed **Read** in the comparison period's summary. "Cost is growing faster
than coverage" is a claim about two dates on one basis, and three things break that basis silently:

- **The coverage model changed** — new covergroups, changed exclusions, a different merge scope; see
  the coverage-model-revision slot. A model that grew makes identical verification look less complete
  and cost-per-item look worse, with no operational change at all.
- **The test list changed** — tests added, seeds raised, a tier re-cut. Cost that grew because scope
  grew is not inefficiency, and conflating the two is how a good team gets accused of one.
- **The farm changed** — a different host class or core count. The same runtime on faster hosts is
  not the same work.

If any of the three moved, report the trend as not comparable, say which one moved, and give a
scope-adjusted per-run figure instead. A trend line drawn straight across a coverage-model change is
the most defensible-*looking* wrong number in this exercise.

### 5. Build the contribution ledger, and find out which kind of ranking you have

**This step decides whether the proposal is defensible.** Cost data alone never justifies removing a
test; the justification is always that something else already covers what it covered.

Per-test contribution cannot be derived by reading files — it comes from merging per-test coverage
databases and ranking them, which needs the coverage tool. **Ask the engineer to produce the
per-test ranking report from the merged databases, to give you the path to the text report, and to
say which of two kinds it is.** They support opposite conclusions:

- **A greedy incremental ranking** orders the tests and reports, for each, only what no test above
  it already provided. A tail whose incremental contribution is zero is redundant *given everything
  above it is kept*, so that tail may be proposed as one change.
- **A per-test unique count** reports coverage no *other* test provides at all. Zero here means only
  "somebody else has it", and two tests each showing zero can be the only two holding a bin between
  them — dropping both loses it. From a unique-count report, propose one removal at a time and ask
  for a re-merge, or propose only removals where a named survivor is shown to hold the coverage.

Getting those two the wrong way round is the most expensive error available here.

Spend one **Grep** on the report's own header — the line saying which kind it is and against which
merge — one on the zero-contribution rows, then up to three windows either side of the zero boundary.

**Write the answer into the block before using it.** From that header line, set
`rank kind: greedy-incremental` where the report gives each test only what the tests above it did not
already provide, or `rank kind: per-test-unique` where it gives coverage no other test holds at all.
If the header does not say and the engineer cannot either, set `rank kind: none` and treat the report
as unusable for removals — every candidate then has to come from step 6 instead. Every candidate in
step 7 inherits that one token: `greedy-incremental` is what licenses proposing a whole tail as one
change, `per-test-unique` licenses only one removal at a time with a named survivor, and `none`
licenses neither.

Two properties hold for either kind:

- A ranking describes **one merge, at one revision, at one moment**, and it ages. One taken before a
  feature landed will cheerfully recommend deleting the tests written for that feature.
- It measures **coverage**, which is not all a run produces. A constrained-random test that has added
  no coverage since seed 40 may still be the only thing driving the design into the state that fails
  on seed 917. Read the bug-find record beside the ranking: a test that has caught bugs recently is
  not redundant merely because it is coverage-redundant, and holding that line is most of what makes
  a proposal survive review.

### 6. Sweep for the waste that needs no coverage data at all

Visible in the list and the summary, and the cheapest wins precisely because none of them puts
coverage or stimulus at risk:

- **Runs that never produce a verdict** — killed at a wallclock or memory limit every period, paying
  full price for nothing. One **Grep** over the summary for the status string the
  cost-and-status-columns slot records, and for the profile's **Infra markers** in the same pass,
  **counted on two separate lines**: a job killed for running too long is a test problem and is
  trimmable here, a job that died for want of a licence, a host or a disk is an environment problem
  and belongs on another queue. Merged into one number, they are how a proposal ends up asking to
  delete tests that a full filesystem killed.
- **Permanently failing or waived tests** — full price nightly for a result nobody reads.
- **Duplicates** — the same test in two tiers, or one seed set entered twice in one list.
- **Mis-tiered work** — a long directed test running nightly when the entry rule puts it weekly.
- **Seed counts nobody has revisited** — chosen at bring-up, multiplied by every list edit since.
- **Debug settings left on by default** — waveform dumping, high verbosity, full instrumentation,
  each costing runtime on every run and each normally wanted only on a re-run.
- **Work repeated per run that could happen once** — a build or an image rebuilt per test rather than
  shared across the tier.

Two **Grep** calls and two windows here. Record a count and a measured cost per hit; if a category
needs more budget than that, name it and leave it unassessed rather than estimating it.

### 7. Rank candidates by saving against risk, not by saving

Highest first:

1. **Nothing at risk** — the step 6 categories. Propose these first and as a separate list; they can
   be approved without the coverage owner in the room. Most of them are not removals at all: where
   the waste is a defect in how the run is set up rather than in the test's existence — a hang killed
   at the limit every night, waveform dumping left on by default, a duplicate list entry, an image
   rebuilt per test instead of once per tier — write `trim action: fix-and-keep`. The test still runs
   and still returns the same verdict, only cheaper, so nothing stops being produced and there is
   nothing for the coverage owner to weigh. Say `fix-and-keep` rather than `drop` even where the
   saving is identical: a reviewer who reads `drop` against a test they rely on stops reading there.
2. **Ranking-evidenced redundancy**, each with a named survivor — `trim action: drop`, and only at
   the granularity step 5's `rank kind` licenses.
3. **Seed reductions** on tests whose incremental contribution has flattened, each with a floor —
   `trim action: reduce-seeds`.
4. **Re-tiering** rather than removal — `trim action: re-tier`, weakest risk of all, since the test
   still runs.

One further action exists and it is the narrowest in the set: `trim action: stop-collecting`, which
stops a tier *collecting coverage* while leaving its stimulus running unchanged. Propose it only
where the instrumentation is a measured share of a run's cost — `warrant: instrumentation-share` —
and where the tier is re-run mainly to hunt bugs rather than to close items, and only under one hard
precondition, named on that candidate's `covered by` line: an instrumented sample still runs at least
once per period. Without that surviving sample it is not a trim at all, it is deleting the evidence
this whole exercise runs on, and step 5 has nothing to read next quarter.

Prefer `trim action: fix-and-keep`, `trim action: re-tier` and `trim action: reduce-seeds` over
`trim action: drop` wherever they capture most of the saving. A reversible change is approved in one
meeting; a deletion is argued about for three.

State the arithmetic plainly: projected core-hour saving is the sum of measured per-run costs times
runs per week, and it is an **upper bound**. It is not a wall-clock saving — queueing is not linear
and the critical path may not move at all — and it is not money, which is step 8.

### 8. Convert compute into money honestly, or do not convert it

Where an otherwise good analysis overreaches and loses the room:

- **Seats already bought are already paid for.** Taking an annual pool from 95% to 60% utilisation
  saves nothing this year. The honest claims are a deferred purchase at the next renewal, freed
  capacity for another project, and shorter turnaround — say which, and say the date the money
  actually changes.
- **Seat count is sized on peak, and only a full-period peak may be spent here.** Only a trim that
  lowers the peak reduces seats needed; if the peak is one burst, the fix is scheduling, not
  trimming, and it belongs on its own line. Read the `peak` line before writing any of this: where it
  says lower bound, no seat-reduction claim may be made at all, because a lower bound is consistent
  with a real peak twice as high. Say instead that the seat question is open pending the licence
  manager's own figure, and name who was asked for it.
- **Metered or cloud capacity does convert directly**, at whatever rate the licence-model slot
  records and only at that rate.
- **Wall clock has value that appears on no invoice** — engineer wait, and how many fix-verify turns
  fit in a day. State it as turns per day, not currency, unless someone who owns the contract has
  given you a rate; then name them, and mark every other money line derived rather than measured.

### 9. Write the proposal

```
proposal    : <name, date, and the tier these numbers describe>
unit        : <the one unit chosen in step 1, used by every figure below>
baseline    : <the total in that unit, with source file and line, and its date>
baseline basis : <counted from a counting Grep, or sampled per-run cost times that exact count with the sample size, or the scheduler's own period total>
cost source : <accounting-export or regression-summary — never the two added together>
scope       : <tests, runs, seeds, and runs per week>
denominator : <what verified was counted in, the count, the two dates, and where the count came from>
cost per feature : <baseline divided by that count, in the stated unit, or not-available and why>
peak        : <peak concurrent runs and seats, and whether it is a full-period figure, a lower bound from the windows read, or not-available>
trend       : <the comparison period's figure, or not-comparable plus which check moved>
rank kind   : greedy-incremental | per-test-unique | none
unassessed  : <tests and cost categories not examined, as a count and a share of the tier>
approver    : <the person from the trim-authority slot, and the evidence they asked for>
```

Then one block per candidate, in the order set by step 7:

```
candidate   : C1
change      : <the test, seed count, tier entry or flow setting proposed for change>
trim action : drop | reduce-seeds | re-tier | stop-collecting | fix-and-keep
cost now    : <the measured figure in the stated unit, times runs per week>
saving      : <the arithmetic, and what it explicitly does not include>
evidence    : <file and line for every number on the two lines above>
warrant     : <waste-category, ranking-evidenced, seed-slope, instrumentation-share or scheduling>
risk        : <the coverage and the stimulus that stop being produced, both named>
covered by  : <the surviving test shown to hold it, the surviving instrumented sample for a stop-collecting candidate, or none-identified>
bugs found  : <what the bug-find record says this test has caught, or not-recorded>
reversal    : <the one edit that puts it back, and the file it lives in>
certainty   : <measured, derived or asserted>
```

Leave a field blank rather than filling it plausibly, and state the handoffs rather than implying
them: ask the engineer for the ranking report and its kind; ask the licence-manager or scheduler
owner for the full-period peak; ask CAD for the accounting system's own period total if a counted
rather than derived baseline is wanted; ask the verification lead for the closure count if that
record is a tracker; ask whoever owns the licence contract for the rate and the renewal date; and ask
the trim authority which of the four step 7 groups they want first.

## Gotchas

- **Trimming short tests does not shorten the night.** Wall clock is bounded by the longest single
  run plus its queue wait. Find that run and ask what it waits on before deleting anything else.
- **Average utilisation is the wrong meter for licences, and a sampled peak is not the peak.** Seats
  are sized on peak concurrency, so a trim halving the daytime average while leaving the 2am burst
  intact frees nothing at renewal. And a peak counted from three windows of an accounting export is
  a lower bound: it can argue that seats are needed, never that seats can be released. Get the
  licence manager's own full-period figure before any seat claim leaves the building.
- **Coverage-redundant is not bug-redundant.** A ranking says a test adds no coverage; it says
  nothing about the stimulus it generates. Cross-check every constrained-random candidate against
  the bug-find record before proposing removal.
- **Zero unique coverage does not mean removable.** In a per-test unique count, two tests can each
  show zero and still be the only two holding a bin. Only a greedy incremental ranking supports
  dropping a whole tail in one proposal.
- **A ranking is a snapshot of one merge and it ages.** Regenerate it after any coverage-model change
  or feature landing, or the proposal will recommend deleting exactly the tests written last.
- **Coverage collection is not free, and switching it off removes the evidence.** `stop-collecting`
  is a legitimate candidate where instrumentation is a measured share of a run, but only with one
  named instrumented sample per period surviving; without that survivor the next ranking cannot be
  produced and this analysis stops being repeatable after exactly one quarter.
- **Timeout kills cost more than their runtime.** They hold a seat for the full limit, usually at the
  worst moment with everything queued behind them, and return no verdict for the money.
- **Removing tests does not remove the build.** Where tier cost is dominated by a shared compile and
  elaboration step, cutting runs leaves it untouched — that is `dv-build-filelist-hygiene`.
- **Seed counts are where the money usually is.** Doubling seeds doubles cost and adds coverage
  sublinearly, and nobody ever schedules the review that halves it back.
- **A percentage with no unit and no baseline file is not a finding, and neither is a cost per
  feature with no closure count behind it.** Two people quoting different units at each other is the
  normal failure mode of this conversation; a ratio whose denominator nobody counted is the second,
  and it is worse, because it looks like a measurement. Both are why step 1 comes first.

## Human verification — what a wrong answer looks like

Before sending the proposal, check:

- the unit is named once and every figure in the document is in it
- every baseline number carries the file and line it was read from and says whether it came from the
  accounting export or the summary — and the two were never added together
- every total says whether it was counted, sampled or asked for, and every sampled total carries the
  sample size beside it — a sum presented flat over rows nobody read is the failure this step exists
  to catch
- the peak line says whether it is a full-period figure or a lower bound, and no seat-reduction claim
  anywhere in the document rests on a lower bound
- the denominator is named with its count, its two dates and its source, and cost per feature is
  either divided from those or written not-available with the reason
- the ranking's kind is stated as one of the three tokens, and the trim logic used matches that kind
- no candidate rests on cost alone: each names a step 6 waste category or a named survivor
- every risk line names the stimulus at risk as well as the coverage
- every candidate has a reversal, and re-tiering was considered before removal
- money claims say whether the seats are already paid for and when the money would change
- trend claims say whether the periods were comparable, and which of the three checks moved
- the unassessed line is present and its share of the tier is stated

A wrong answer is a tidy table promising a 42% saving, computed by summing the runtime of every test
with zero unique coverage, in a year when the seats are already bought, from a ranking generated
before the last two features landed. The subtler wrong answer is the same table with honest
arithmetic on top of a peak that was counted from three windows and quoted as though it were the
period's, and a cost per feature divided by a denominator nobody was ever asked for.

## Done when

The trim authority can approve or reject each candidate on its own line without asking you for a
number, and the unassessed remainder is visible as a stated share rather than hidden.
