---
name: dv-emulation-throughput-triage
description: Apportion an emulation run's wall clock across design step rate, transactor round-trips, trace capture, host-side testbench cost and per-job fixed cost, then rank the levers by recoverable time. Use when an emulation run is correct but too slow, when a nightly emulation job stops fitting its window, when someone asks why the design emulates at a fraction of the platform's quoted rate, when boot or memory preload eats hours, or when you are about to ask for more emulator capacity.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Emulation Wall-Clock Throughput Triage
  semiskill-function: design-verification
  semiskill-role: emulation-engineer
  semiskill-level: senior-staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-07-23
  semiskill-tags: emulation, co-emulation, throughput, wall-clock, transactors, trace, performance
---

# Emulation Wall-Clock Throughput Triage

An emulation run that is correct and slow gets triaged badly, because the one number everybody reaches for — total
wall clock — is a sum of five unrelated costs, and the cheapest to talk about is almost never the one paying the bill.
The step rate is fixed when the design is compiled onto the hardware and barely moves; what varies by an order of
magnitude between two runs of the same compile is how often the design stops to wait for the host.

This apportions one run's wall clock across those five terms, states how much none of them account for, and ranks the
levers by recoverable time — **an apportionment with an honest residual**, not a verdict. It reads files on disk and
cannot launch the emulator, profile it or time anything, so the two terms needing a comparison run are handoffs.

## When to use something else

If the run failed rather than dragged, the failure comes first — `dv-sim-log-first-error` for one log,
`dv-regression-triage-routing` for a night of them. Which tests belong in which tier is `dv-regression-tiering-farm`;
what the regression costs and which tests to stop paying for is `dv-compute-license-efficiency`. Those two decide *how
much work to submit*, this decides *why one job takes as long as it does*, and in that order — retiring work you ran
for no reason beats speeding it up. `dv-minimal-reproducer` bisects while holding a failure signature fixed; there is
none to hold here.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Emulation platform | [[FILL: which emulator we run on, and whether a job is launched interactively or through a queue]] | emulation lead |
| Run area | [[FILL: where an emulation job's log, end-of-run summary and any performance report land]] | emulation lead |
| Progress line | [[FILL: the string our runs print periodically carrying elapsed wall clock and design cycles or simulated time, and which column is which]] | emulation lead |
| Summary marker | [[FILL: the string that ends a completed emulation job and carries its totals]] | emulation lead |
| Compile report | [[FILL: where the emulation compile writes its report, and what it calls the achieved step rate and the clock-domain summary]] | emulation infra |
| Performance report | [[FILL: whether our flow can produce a run-time performance breakdown, what enables it, where it lands, and what it calls the achieved rate]] | emulation infra |
| Round-trip idiom | [[FILL: the exact call names our transactors use to cross between design side and host side, and the directories the design-side and host-side transactor sources live in, so a search can be scoped to them]] | transactor owner |
| Trace configuration | [[FILL: how capture is enabled for an emulation job, which file records that setting, and whether it applies to the whole job or a window]] | emulation infra |
| Host testbench | [[FILL: what runs on the host for us — reference model, scoreboard, file writing, logging — which directory its source lives in, and whether we have a way to reduce it to a no-op that still lets the test complete]] | block DV owner |
| Throughput target | [[FILL: the rate we treat as acceptable for this design, the unit it is stated in, and who set it]] | verification lead |

Pack-wide facts stay in `_shared/team-profile.md`: **Run identity** supplies the `run id` line, **Area to owner map**
the owner of the lever step 8 ranks first. **Run area is narrower than the profile's Log location** — an emulation job
writes into the emulator's own job directory, often on a different filesystem from where simulation logs land; if they
are the same place, say so and use the profile's value. **Fatal markers** and **Pass marker** are not used here: the
run was already judged correct. **If a slot is unfilled, stop and ask** — a guessed progress-line format gives an
apportionment whose arithmetic is clean and whose inputs are fiction.

## Retrieval budget — read this before opening anything

An emulation job's log is written continuously for hours and a capture database is not text at all. Locate first, read
narrowly, stop when the ranking stops changing.

1. **Grep and Read work on files on disk.** Progress lines get pasted into chat more than pointed at; resolve the
   paste to a path under **Run area** first. Until then read them by eye — say so, and mark shares provisional.
2. **One Glob** of the Run area for the log, the summary and any performance report; never **Read** the run log first.
3. **Six Grep calls and no more**, fixed in advance: progress line and summary marker together (step 2); the achieved
   rate and clock-domain strings (step 4); the round-trip idiom in the transactor directories, then the transaction
   counts in the log (two calls, step 5); the capture setting (step 6); the host testbench's work (step 7).
4. **Five windowed Reads of about 60 lines**: two in the run log — the first steady progress line and the summary —
   one in the compile or performance report, one at the busiest round-trip site, one spare for step 7.
5. **The 200-hit rule covers all six Greps, not just the log ones.** Over 200 hits, do not read them all: for the four
   file Greps (steps 2, 4, 6 and step 5's log count) sample the first, middle and last hit by line number — a rate is a
   difference between two lines, not a series — and for the two source-tree Greps (steps 5 and 7) take the first,
   middle and last file, saying the count was sampled. Both must be scoped to the directories the **Round-trip idiom**
   and **Host testbench** slots name; unscoped they are the likeliest way to blow this budget, so a slot with no
   directory in it is a stop-and-ask.
6. **Never Read a capture database, a memory image or a performance database.** They are binary or enormous, and
   nothing here needs their contents — only their path, size and whether they exist.
7. Stopping rule: when the budget is spent, stop, and state the coverage — how much of the job the window spans, and
   which numbers came from a file rather than a person. If fewer than two of the five terms were measured rather than
   bounded, say the apportionment is bounded and name the residual terms. Past that point the shares get invented.

## Procedure

### 1. Confirm the job finished, and get its artifacts onto disk

**Glob** the **Run area** for the log, the end-of-run summary and any performance report, then use the first **Grep**
(shared with step 2) for the **Summary marker**. No marker means the job was killed or still running, so every share
below is of an unfinished job and must say so. Note whether a performance report was found; step 4 prefers it to the
compile report.

Read the **Emulation platform** slot before trusting any elapsed number: a queued job carries a queue wait the queue's
accounting counts and the run log does not, an interactive session has neither, and the two totals get quoted
interchangeably.

### 2. Measure a rate over a window, never over the job

**Grep** the log once for the **Progress line** and the **Summary marker** together. Grep returns the matching lines
themselves, so the numbers are usually in hand without opening the log. Take three differences, not one average:

- **before the first progress line** — load, preload, reset, boot: fixed per job, immune to step-rate gains.
- **a mid-run pair**, clear of boot: cycles over wall clock between them — the steady rate, the only one worth quoting.
- **last progress line to the summary marker** — checkpoint write, capture flush, copy-out; also fixed per job.

Then compare the first mid-run pair against the last: a **flat** rate means the cost is per-cycle, a rate that
**degrades monotonically** means something on the host is growing with the run, which routes to step 7. Spend the
first two windowed **Reads** here only if the progress lines lack either number. If the steady rate already meets the
**Throughput target**, the fixed cost or the work submitted is what is slow — the second is `dv-regression-tiering-farm`.

### 3. Write the identity down before attributing anything

```
wall clock over the measured window
  = design-step time + transactor stall + capture overhead + host-testbench stall + residual
```

Only terms with a number behind them get attributed; everything else stays in the residual, named. The commonest
failure here is a residual quietly folded into whichever term the author suspected, turning a 30% measurement into a
100% story. Design-step time (step 4) and the round-trip count (step 5) come from files; capture overhead (step 6) and
host-testbench stall (step 7) need a comparison run, so until that log exists each stays in the residual, reported as
unmeasured.

### 4. Bound the design-step term from the compile, not from the run

**Grep** the **Compile report** — or the **Performance report** instead, on that same budgeted Grep, if step 1's Glob
found one, since it carries the rate the run achieved rather than the rate the build predicted — for the achieved rate
and the clock-domain summary, then spend one windowed **Read** around the hit. Design-step time over the window is
cycles retired divided by that rate; everything else is stall, and that subtraction carries the apportionment.

What holds the achieved rate down is compile-side and slow to change: the ratio between the fastest and slowest clock
the compile must resolve, clocks generated inside the design instead of driven from the flow's clock generator, and
memories that landed in logic rather than in the platform's memory resources. Use the report's own words, not another
platform's. If neither report is on disk, **ask the engineer for the path to the report the emulation compile wrote,
or to the breakdown the Performance report slot names**; without one the design-step term is unmeasured.

### 5. Count the transactor round-trips

Each crossing between design side and host costs a fixed latency orders of magnitude larger than a design cycle. **The
lever is the count, never the cost of one.** **Grep** the **Round-trip idiom** in one call, scoped to the directories
that slot names, for the call sites; then **Grep** the log for transaction counts, using whichever **Round-trip idiom**
string our transactors echo there — if none appears, the count is not on disk, so ask the transactor owner for it.
Round-trips over the window are roughly call sites per transaction times transactions; spend one windowed **Read** at
the busiest site:

- **blocking** — the design side stops until the host answers, so wall clock scales directly with the count.
- **pipelined or streaming** — the design keeps clocking; wall clock scales with queue stalls, not with the count.

For the latency itself, take the platform's documented figure or **ask the emulation lead for the measured one** — do
not assume a number. If neither exists, report the count and say the term is bounded by an unestablished latency.

### 6. Decide whether capture is paying for itself

**Grep** the file named in **Trace configuration** for the capture setting. Three questions in order: whether capture
was on at all; whether it was on for the whole job when a window would have done; and where the database was written,
because a capture stream landing on a shared network filesystem is an I/O problem wearing an emulation costume.

Capture cost is not uniform across platforms — on some, run-time capture is nearly free and the expense lands
afterwards in reconstruction; on others it throttles the step rate continuously. **Ask the engineer to repeat the same
test on the same compile with capture disabled, and to give you the path to the new log.** The difference in steady
rate is the capture term; without that log it is unmeasured and stays inside the residual. Reconstruction and upload
after the job never appear in its wall clock but always in the engineer's day — report them separately.

### 7. Find what the host does per transaction, then get that term measured too

Use the spare windowed **Read** here, entered through one **Grep** of the **Host testbench** sources — scoped to the
directory that slot names — for per-transaction work: printing and flushing, a file opened or closed per transaction,
a synchronous reference-model call, or a scoreboard lookup that walks a list.

The degradation signal from step 2 discriminates these, but it names the likely mechanism and **produces no number**.
A per-transaction print or file write is a flat cost and shows as a flat, low rate; a lookup that walks a growing
structure is quadratic and shows as a rate that decays monotonically, which is almost never the emulator.

**Ask the engineer to repeat the same test on the same compile with the host testbench reduced to the no-op the Host
testbench slot describes, and to give you the path to the new log.** The difference in steady rate is the
host-testbench term. Until that log exists the term is unmeasured: leave `host tb` as unmeasured, its cost inside
`residual`, the mechanism on `notes`. If we have no no-op reduction, say so — the share is then unrecoverable.

### 8. Rank the levers by recoverable wall clock

Rank by share times the fraction plausibly recoverable, over the cost and risk of the change; name one owner per lever
from the profile's **Area to owner map**. A term still in the residual cannot be ranked until its comparison lands.

| Term | What it looks like | Usual lever | Owner | What it costs |
|---|---|---|---|---|
| design-step | flat low rate, report agrees | clock definitions, memory mapping, repartition | emulation build | a recompile, hours to a day |
| transactor | flat rate, high round-trip count, blocking sites | batch beats per message, or move the loop design-side | transactor owner | testbench change plus a correctness re-run |
| capture | rate rises in the capture-off comparison | narrow the window, or move the database off a shared mount | emulation infra | none, if the debug need is truly narrower |
| host-testbench | rate rises in the no-op comparison | drop per-transaction printing, fix the growing lookup | block DV owner | small change, large recovery |
| fixed-cost | short jobs, long pre-progress gap | back-door memory preload, drop an unused checkpoint | emulation infra | none to moderate |

Any lever that changes **when** a message crosses relative to the design clock changes what the run means. Say so on
the same line and hand back the re-verification — the same test on the same compile, compared against the accepted
run.

### 9. Write the apportionment down

```
run id      : <what identifies this job and the compile it used, from Run identity>
wall clock  : <the window the shares cover, why that window, elapsed over it, and the line it came from>
rate        : <cycles retired over the window, simulated time if reported, and the resulting cycles per wall-clock
              second, against the Throughput target>
design step : <share, and the report line behind it>
transactor  : <share, round-trip count times the platform's round-trip latency>
capture     : <share from the step 6 capture-off comparison, or unmeasured — then it sits in residual>
host tb     : <share from the step 7 no-op comparison, or unmeasured — then it sits in residual, mechanism on notes>
fixed cost  : <per-job cost outside the window — load, preload, flush, copy-out, queue wait>
residual    : <what none of the measured terms account for, including every term marked unmeasured above>
dominant    : design-step | transactor | capture | host-testbench | fixed-cost | residual
lever       : <the one change with the largest expected recovery, and its owner>
re-verify   : <what has to be re-run and compared before that recovery is believable>
evidence    : <a file path and line, or a log line number, for every number above>
coverage    : <window length against job length; which numbers came from a file and which from a person; which terms were never measured>
notes       : <anything the next person would otherwise have to rediscover>
```

`dominant` may only name a term that has a number behind it; if the largest measured share is smaller than the
residual, `dominant` is `residual`. `run id`, `evidence`, `coverage` and `notes` match `dv-sim-log-first-error` and
`dv-ral-bringup`; `class` and `phase` are not reused — their values classify a failure, which this is not.

## Gotchas

- **Wall clock over a whole job is not a rate.** Design load, preload, checkpoint and copy-out are fixed per job; on a
  short test they are most of the total, and every gain in step rate then recovers nothing.
- **A rate that decays monotonically is the host, not the emulator** — a scoreboard or coverage object growing per
  transaction, seen only on long runs. The shape says which comparison to ask for; it is not itself a share.
- **Round-trip count is the lever; round-trip latency is a constant.** Halving the messages halves the term; nothing
  done to an individual message makes it meaningfully cheaper, and time spent trying is wasted.
- **A blocking crossing stops the design clock**, so the emulator idles for the full round trip while its own report
  shows a healthy rate over the steps it did take. Healthy step rate plus terrible throughput is the mark of stall.
- **Front-door memory preload through a transactor is the classic catastrophe** — thousands of round-trips to place an
  image a back-door load writes once, before the first progress line, so no rate measured afterwards can see it.
- **A fast clock the design barely uses is charged on every cycle of the slow one**, and a clock made inside it — a
  behavioural divider, a phase-locked loop model — is ordinary logic to evaluate, visible only in the report.
- **Capture can be free at run time and expensive afterwards, or the reverse, and which one is a platform property.**
  Never assume; step 6's comparison is the only honest answer, and reconstruction time is a separate number.
- **Two jobs of different lengths cannot be compared by wall clock, and two on different compiles cannot be compared
  at all.** The compile fixes the step rate, so a rate quoted without its build identity proves nothing.
- **More parallel jobs on one emulator can lower every job's rate.** When jobs share a host or a link the contention
  surfaces as transactor latency inside each, and each engineer concludes their own testbench is fine.

## Human verification — what a wrong answer looks like

Before acting on the apportionment, check:

- the shares sum to at most the window, with the leftover on `residual`, not in the term the author suspected
- the rate was taken between two mid-run progress lines, not by dividing total wall clock by total cycles
- the design-step share rests on an achieved rate quoted with a file and line, not on a platform figure from memory
- the `capture` and `host tb` lines cite their comparison run or say unmeasured — never a `dominant` without one
- any round-trip latency is attributed to the platform's documentation or to the person who measured it
- the `coverage` line says how much of the job the window spans, and every timing-changing lever carries its re-verify

A wrong answer quotes an average rate over a job that spent forty minutes loading, blames the step rate without
opening the compile report, or reports a saving inferred from a shape rather than measured.

## Done when

You can name the dominant term with the line behind it, the one lever worth pulling, its owner, what it would recover,
which comparison runs are still owed, and how much of the job you actually measured.
