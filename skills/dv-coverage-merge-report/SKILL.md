---
name: dv-coverage-merge-report
description: Audit a coverage merge across seeds, configurations and engines, establish what the merged number actually measures, and draft the weekly trend row with its movement attributed. Use when the weekly coverage number has to be produced and defended, when coverage jumped or fell and nobody can say why, when results from several configurations or more than one engine have to become one picture, or when someone asks whether this week's rise was tests or exclusions.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Coverage Merge Across Seeds, Configs and Engines, and the Weekly Report
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-05-28
  semiskill-tags: coverage, merge, seeds, configurations, engines, exclusions, trend, weekly-report
---

# Coverage Merge Across Seeds, Configs and Engines, and the Weekly Report

Merged coverage is the number a project steers by, and the easiest number in verification to move without
doing any verification: a failed run still wrote a database most flows will merge, an exclusion file shrinks
the denominator, and an edited covergroup breaks comparison with last week. The output here is **an audited
input list, a metric breakdown, and an attributed trend row**.

**What this cannot do.** A coverage database is binary and **Read** cannot open it. The agent cannot merge,
export a report, or open a viewer: every number below is from a text file some tool wrote, or it is a handoff.

## When to use something else

Use this weekly, on a regression that mostly passed. If the night was red, sort it with
`dv-regression-triage-routing` first; one failing log is `dv-sim-log-first-error`, and a merge step that died
after the simulator exited is that skill's `post` phase. If the merge keeps consuming the wrong runs because
of how tiers and run directories are named, that is `dv-regression-tiering-farm`. Hand the holes on to
`dv-coverage-hole-closure` (ranked plan) and `dv-coverage-hole-disposition` (per-bin waiver text); several
blocks rolled into one status is `dv-status-rollup`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Merge invocation | [[FILL: what merges our coverage databases, what exports a readable text report, and whether that export runs automatically or has to be asked for]] | DV infra owner |
| Merge log | [[FILL: where the merge and export steps write their own logs, and how long those are kept]] | DV infra owner |
| Merge warnings | [[FILL: the strings our merge tool prints for a model or design mismatch, a skipped database, and a dropped or renamed scope]] | DV infra owner |
| Summary join | [[FILL: how one coverage database is named, which column of the regression summary carries that same identifier, the pattern that marks one per-run row in that summary, and the pattern that marks a row as passing]] | DV infra owner |
| Metric set | [[FILL: which coverage metrics we collect, which of them the headline number combines and at what weights, where those weights are set, and the per-metric target this block signs off against]] | coverage owner |
| Report layout | [[FILL: what a total line and a per-scope row look like in our exported text report, and the string that marks a zero-coverage row]] | coverage owner |
| Exclusion files | [[FILL: where our exclusion and waiver files live, their format, and whether each entry carries a reason and an owner]] | coverage owner |
| Config axis | [[FILL: which configurations we run for this block, and which parts of the coverage model each one can legitimately reach]] | verification lead |
| Engine inputs | [[FILL: which engines besides simulation contribute coverage here, what each contributes, and how those results reach the merge]] | verification lead |
| Weekly archive | [[FILL: where last week's exported report and weekly summary are kept, so this week can be compared against them]] | coverage owner |

Four pack-wide facts come from `_shared/team-profile.md`. Its **Regression summary** row gives step 2 that
file and its format; **Summary join** is narrower, asking for three literals *inside* it — the identifier
column, what one per-run row looks like, and what marks a row as passing. That last is **not** the profile's
**Pass marker**, which is what a run's own log prints at its end, so Grepping a summary for it finds nothing
and both must be filled in. **Run identity** separates a seed from a configuration change in step 4,
**Sign-off** names who step 8's report goes to, and **Coverage output** is where merged coverage lands —
neither the **Merge log** nor the export. **If a slot is unfilled, stop and ask**: an invented command or
marker yields an authoritative report about the wrong files.

## Retrieval budget — read this before opening anything

An exported hierarchical coverage report runs to tens of thousands of lines for a block; exclusion files run
to thousands. None of it can be read whole.

1. **A coverage database is binary, and Read, Grep and Glob reach only text.** With no text export this stops
   at step 1 with a handoff; a pasted percentage is repeatable but not searchable, so ask for a path.
2. **Glob** at most **5** times: merge log, export and regression summary in step 1, then the exclusion files
   and the weekly archive in step 7.
3. **Grep** at most **14** times, never opening a report with **Read** first. Thirteen are itemised — step 2:
   the summary's per-run rows, its passing rows, the merge log's input list. Step 3: the **Merge warnings**
   pattern. Step 4: the configuration name across the input list, then whatever names a non-simulation input.
   Step 5: the total line. Step 6: the zero-coverage marker, then one narrowing pattern in the top scope. Step
   7: the exclusion entry pattern, its reason field, the archived total line, the archived count.
4. **Read** at most **8** windows of about 80 lines: one in step 5, three in step 6, two in step 7, two spare.
   Counting Grep hits is not reading them: the counts in steps 2 and 7 need no window. Over 200 hits, narrow.
5. **Stop, then say where you stopped.** Classify at most the top **10** holes, stop when the budget is spent,
   and state the coverage — "3 of 41 zero-coverage scopes opened, the rest counted only". Unstated is worse.

## Procedure

### 1. Get a text export on disk, and say plainly that the merge itself is a handoff

**Ask the engineer to perform the merge and the text export named in the Merge invocation slot, and to give
you the path of the merge log and the path of the exported report.** The agent can do neither and must not
describe what a merge "would have" printed. Then **Glob** three paths: the merge log, the export, and the
regression summary the profile names. With no export, stop here: repeating a percentage read off a viewer as
though checked is the failure this exists to prevent. Given only a pasted one, mark all of it provisional.

### 2. Count three numbers before believing any percentage

They are rarely equal and the gaps are the finding: **a**, runs the regression summary says executed; **b**,
runs it says passed; **c**, databases the merge consumed. Three **Grep** calls, read as hit counts — **a**
from the summary's per-run row pattern in **Summary join**, **b** from that slot's passing-row pattern over
the same file, **c** from the merge log's input list. Count passing rows directly: a summary normally carries
rows that are neither pass nor fail — killed, skipped, retried — so deriving **b** by subtracting a fail count
from **a** promotes every one of them to a pass. Then join the input list to the summary on the identifier
**Summary join** records: a database and a summary row are the same run only when that identifier matches,
never because the names look alike.

- **c above b** — databases from failing runs were merged: stimulus that reached the logic with no verdict
  attached. Write `inputs: includes-failing` with the count and ask for a re-merge without them.
- **c equal to b, every merged identifier matching a passing row** — the only case earning
  `inputs: passing-only`. Equal totals alone do not: a missing database and a merged failure cancel exactly,
  so write this from the identifier match, never from the arithmetic.
- **c below b** — databases are missing: a killed job, a full filesystem, collection off for one configuration.
  Name those runs; never repair the gap by subtraction.
- **the identifier is absent from one file** — no join is possible: write `inputs: unknown`, naming it.

Report all three; **a** minus **b** sizes what **c** may have swallowed. A run that *passed* with its checkers
off carries the defect of a failing one and is invisible to all three counts — ask a person.

### 3. Read the merge log's warnings before the report's numbers

One **Grep** for the **Merge warnings** strings alternated into a single pattern. Three classes:

- **Model or design mismatch** — a covergroup edited, a bin added, or the design re-elaborated, so one
  database's model differs from another's. Some tools error, some merge only the shared part, some keep both
  as separate scopes; either way the denominator is not the one the reader assumes.
- **Skipped or unreadable database** — truncated by a killed job, or version skew: a missing input for **c**.
- **Dropped or renamed scope** — present in one database, absent in another, so the merged view carries a
  scope no current design has, permanently at zero.

### 4. Name the axes — seeds, configurations, engines — and treat them differently

Separate them with the profile's **Run identity** fact: one **Grep** of the input list for the configuration
name, one for whatever names a non-simulation input.

- **Seeds** are the safe axis: same test, build and model, so the union of hit bins is what merging is for.
  Marginal contribution needs a per-test ranking — the step 8 handoff.
- **Configurations** are not. Two configurations of one block have different *reachable* spaces, so one merge
  across all of them makes a bin unreachable everywhere look like a hole and a bin reachable only in a
  configuration nobody ships look like coverage. Take the mapping from **Config axis**, keep each
  configuration's own total, and report the union beside them, not instead. Write `merge mode: per-config`
  when each configuration was merged and totalled on its own, and `merge mode: single-merge` when one merge
  combined them all — that token says which hazard applies below. A seed sweep that also changed a plusarg
  belongs here, not under seeds.
- **Engines** are stated, never summed: their percentages share no denominator. From **Engine inputs** record
  what each contributed and to which metrics. A formal engine reasons about *reachability* — its proofs are a
  legitimate source of exclusions, but "covered" there is not stimulus with checking on, and an emulator's
  code coverage is coarser still.

### 5. Read the totals, and record how the headline number was weighted

One **Grep** for the total-line pattern from **Report layout**, then one **Read** window. Record every metric
on its own line — line, branch, condition, toggle, FSM state and transition, assertion, covergroup. One number
is not a coverage result: the headline is weighted twice, in the source on covergroups and coverpoints and
again by the tool between metrics, and **Metric set** records both plus the sign-off target.

The trap is per-instance versus type-level covergroup coverage. Without `per_instance`, hits from every
instance pool into the type, so a type at 100% can contain an instance never sampled once. If the export has
only type-level rows, write `functional: type-level-only` and say the per-instance question is unanswered; if
it has per-instance rows, write `functional: per-instance-available` and name the worst — that is the finding.

### 6. Classify the holes far enough to stop calling them gaps

One **Grep** for the zero-coverage marker from **Report layout**, one narrowing **Grep** in the top scope, at
most three **Read** windows. Five reasons a bin reads as uncovered — write the token, not a paraphrase:

1. **No stimulus** — nothing ever drove it: `reason: no-stimulus`. The only one that becomes a test.
2. **Unreachable** — not exercisable in any configuration: `reason: unreachable`. It belongs in an exclusion
   file with a reason and an owner, not on the test backlog.
3. **Reachable only in a configuration this merge left out**: `reason: config-not-merged`. A merge-input
   problem, named in step 4, not a stimulus problem.
4. **Never sampled** — the covergroup was built but its sampling call never fires, or it was never
   constructed: `reason: never-sampled`. A testbench bug that looks precisely like a stimulus gap.
5. **Not implemented** — the RTL feature is not there yet: `reason: not-implemented`. A schedule item.

Reasons 1 and 4 separate on one test: partial coverage anywhere in a covergroup proves it sampled, so a
covergroup at zero across *every* bin is a sampling bug until proven otherwise. Rank on whether the scope is
named in the plan, then blast radius, then size, never on percentage: a 0% scope of two bins is smaller news
than a 60% scope of four hundred. One line each; named fixes go to `dv-coverage-hole-closure`.

```
hole   : <scope path exactly as the exported report spells it, and which metric it is in>
reason : no-stimulus | unreachable | config-not-merged | never-sampled | not-implemented
size   : <uncovered bins of total bins in that scope>
rank   : <n> because <plan / breadth / size>
owner  : <from the profile's area-to-owner map, or blank plus candidates>
```

### 7. Audit the exclusion delta, then attribute the trend

**Glob** the **Exclusion files** and the **Weekly archive**. One **Grep** for the exclusion entry pattern, one
for its reason field, one of the archived report for step 5's total-line pattern, one of the archived summary
for its exclusion count, and at most two **Read** windows around the densest clusters. An exclusion adds no
coverage; it removes bins from the denominator — both raise the percentage and only one is verification. Count
the entries and how many carry both a reason and an owner; an entry with neither is the finding, and a set
written for the block does not automatically hold at the top. **Read, Grep and Glob cannot diff two revisions
of a file**: what is available is this week's count against the archived one, plus Grepping for entries the
archive's list does not name — say which you did.

Then attribute the movement to four buckets, leaving what does not fit in a fifth: **stimulus** (new tests, or
more seeds); **exclusions** (the delta above, moving the denominator); **model change** (a covergroup edited,
a bin added, a design re-elaborated — step 3 saw it first); **merge-input change** (more or fewer databases, a
configuration or engine added); and **unattributed**, more useful stated than absorbed into another. A fall is
usually a configuration dropped, an exclusion retired, or a model change that added bins — in that order. Last
week's number is comparable only if the metric set, weights and exclusion set are all unchanged; if any moved,
write `trend` as not comparable.

### 8. Draft the weekly report, and state the handoffs

```
merged     : <c databases, from a runs executed and b passed, varying on which axes>
inputs     : passing-only | includes-failing | unknown
merge mode : per-config | single-merge
engines    : <which engine contributed which metrics, and what reached no merge at all>
headline   : <the one number, and exactly which metrics and weights it combines>
per metric : <line, branch, condition, toggle, fsm, assertion, covergroup — each on its own>
functional : type-level-only | per-instance-available
excl count : <n entries, n added since the archive, n of those carrying a reason and an owner>
trend      : <this week against the archived week, per metric, or not comparable and why>
attributed : <stimulus / exclusions / model change / merge-input change / unattributed>
coverage   : <how much of the report was opened, what was only counted, and which runs never reached the merge>
next       : <the one named action, and the one thing to ask for>
```

Leave a field empty rather than filling it plausibly, and address it to whoever **Sign-off** names. Then state
these rather than implying them: ask the engineer to re-merge without the failing runs' databases and give the
new export's path; ask for a per-test contribution ranking and its output path — the only honest way to say
whether more seeds still pay — and for a per-configuration export wherever step 4 found `single-merge`.

## Gotchas

- **Coverage from a failing run merges silently and counts fully** — the run drove the logic, nothing checked
  the result, and most flows merge whatever is in the run area, so this is the default state, not the rare one.
- **An exclusion moves the denominator, a test moves the numerator, and the percentage cannot tell you which
  happened.** A week where the number and the exclusion count both rose needs both reported, or it proves nothing.
- **A type-level covergroup at 100% can hide an instance never sampled**, and a covergroup at zero across
  every bin is a sampling bug, not a stimulus gap, until partial coverage somewhere proves it sampled at all.
- **`option.at_least` and `auto_bin_max` move the number with no change in stimulus** — one raises the hits a
  bin needs, the other the bin count of an implicit coverpoint; both are one-line edits that read as regression.
- **Toggle coverage is mostly bus width**, carrying more bins than the other code metrics together, so
  widening a bus moves the headline number, and that movement is not progress.
- **Merging databases from different elaborations is the quiet one**: the tool may error, merge only the
  common part, or keep two parallel scopes, and only the first is visible without reading the merge log.
- **More seeds is the cheapest axis and the first to stop paying** — without a per-test ranking, "we added two
  hundred seeds" is an input, not a result.

## Human verification — what a wrong answer looks like

Before sending the report, check:

- every number traces to a line in an exported report, or is attributed to whoever read it off a viewer
- all three of step 2's counts appear, each from its own Grep, and `inputs` says which case holds —
  `passing-only` only where identifiers were matched one by one, never from equal totals
- the headline carries its metric set and weights, and no two engines' percentages have been added or averaged
- every classified hole carries one of the five `reason` tokens spelled exactly, not a low percentage
- the exclusion count says how many were added, how many carry a reason and an owner, and how that was checked
- `trend` reads as not comparable wherever the metric set, weights or exclusion set moved, and `coverage`
  states how much of the report was actually opened

A wrong answer is a single rising percentage with no denominator behind it, from a merge that quietly included
eleven failing runs and a new exclusion file. The next most common is the report's zero-coverage rows ranked
by percentage, with a formally-proven-unreachable scope at the top of the backlog.

## Done when

The weekly number can be defended line by line — what merged into it, what moved it, and which of its holes is
worth handing to someone as a real gap.
