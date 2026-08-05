---
name: dv-coverage-hole-closure
description: Turn a merged coverage text report into a ranked, owned closure plan — hole groups classified as never sampled, model defect, unreachable or genuine stimulus gap, each with one named fix and one owner. Use when a merged regression has parked short of its coverage goal and nobody has read the report, when sign-off asks which holes actually block it, when someone proposes another thousand random seeds, or when you need to know which holes are real before writing a single directed test.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Coverage Hole Classification and Closure Planning
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-03-12
  semiskill-tags: coverage, closure, covergroups, exclusions, sign-off, planning, ranking
---

# Coverage Hole Classification and Closure Planning

A merged coverage report is the artifact everybody quotes and nobody reads. The number at the top is a
weighted average over metrics of wildly different value, and most of the rows beneath it are not
stimulus problems at all — they are bins that were never sampled, bins that cannot be hit as written,
and toggles no configuration of this block can reach. Throwing seeds at that mixture is how a team
spends three weeks moving a percentage by one point.

The output is a **ranked list of hole groups**, each with a hole class, one named fix, one owner, and
one line saying how much of the report was actually read. Not a list of holes, and not a percentage.

## When to use something else

This skill stays at the **group** level across every metric the report carries and stops at a ranked
plan with an owner per group. Once a group is ranked and someone has to classify its bins one at a time
and draft the covergroup edit or the waiver text, `dv-coverage-hole-disposition` is the step down. If
the question is instead whether the merged number can be trusted, or why it moved this week, that is
`dv-coverage-merge-report`; step 1 here pins only the merge's identity and takes the merge as sound.

If the regression behind this database was red, stop — coverage merged from runs that did not finish is
not a closure input, and `dv-regression-triage-routing` comes first. A single failing log is
`dv-sim-log-first-error`; a failure you want smaller is `dv-minimal-reproducer`. A coverage model that
never reaches the build is `dv-build-filelist-hygiene`, and step 3 routes it there. If you do not yet
know where coverage lands in this repo, `dv-repo-orientation` maps it.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Coverage report | [[FILL: which text report our flow exports from a merged database, which metrics it contains, and where it lands]] | coverage owner |
| Report sections | [[FILL: the exact heading strings our report prints above the total score, the per-module code metrics, the covergroup summary, the per-instance detail, and the assertion cover-directive section if our report prints one]] | coverage owner |
| Hole notation | [[FILL: how our report writes an uncovered row, which column holds the hit count, and whether it prints the at_least value]] | coverage owner |
| Sign-off metrics | [[FILL: which metrics count toward sign-off for this block and the numeric goal for each]] | verification lead |
| Plan linkage | [[FILL: where our verification plan lives, whether it is a file that can be read, and the key tying a plan item to a covergroup or coverpoint name]] | verification lead |
| Exclusion records | [[FILL: where our exclusion and waiver files live, their format, and what one record is required to carry]] | DV lead |
| Configuration axis | [[FILL: the parameter sets, modes or build configurations this block is signed off in, and which of them a nightly merge normally contains]] | block owner |
| Trend record | [[FILL: whether our flow records coverage per regression over time in a file that can be read, and where it lands]] | DV infra |

Four more facts are pack-wide and live in `_shared/team-profile.md`; read them there rather than
re-interviewing anyone. **Run identity** fills the plan's run line, and **Area to owner map** is used
verbatim in step 6 — this skill has no owner slot of its own. Two others sit close to a slot above
without being the same fact. The profile's **Coverage output** says where the merged *database* lands;
**Coverage report** asks which *text export* our flow produces from it, because a coverage database is
binary and nothing here can open one. The profile's **Sign-off** says who signs off and on what
evidence; **Sign-off metrics** is a list of metric names and numeric goals — a person is not a
threshold, so record both. The profile's **Known-issue list** is deliberately absent: this skill files
nothing and matches nothing against it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented section heading sends
every Grep below into a report that never contains it, and an invented goal number turns a closure plan
into an argument nobody can win.

## Retrieval budget — read this before opening anything

A merged report for one block runs to hundreds of thousands of lines, because it prints every instance
of every module and every bin of every covergroup. Reading it is not an option; locating inside it is.

1. **Grep, Read and Glob work on files on disk.** A coverage database is binary and none of them can
   open it; a report pasted into the conversation cannot be searched either. Resolve to a text report at
   a path first — step 1.
2. **Never open the report with Read first.** Every Read is entered through a Grep hit for a heading
   from the **Report sections** slot or a row matching the **Hole notation** slot. Step 3's heading
   Grep is one alternation over *all* of those headings with line numbers, so the section map that
   assigns every group's metric costs nothing beyond the Grep that step already spends.
3. Cap the exercise at **4 Globs, 14 Greps and 8 windowed Reads** of about 80 lines — 40 for a source
   window. The ledger spends 3 Globs, 13 Greps and all 8 Reads: step 1 one Glob and one Grep; step 2 one
   Grep and one Read; step 3 four Greps and three Reads; step 4 up to two Greps and two source Reads;
   step 5 two Globs, four Greps and two Reads; step 6 one Grep. One Grep stays in reserve.
4. If an earlier step overruns, **the two source checks in step 4 give way first** — record those groups
   unsettled rather than opening a fifteenth Grep.
5. A Grep returning more than about 200 hits is too broad. On a per-instance report that happens
   immediately: anchor on a heading string or a hierarchy prefix, never on a bare metric name.
6. **Stopping rule.** Stop when the budget is spent, or when three consecutive hole rows fold into groups
   that already exist. Rows you did not read are not classified and never become a plan item.
7. State what you covered — sections opened of sections present, rows read of rows reported. An unstated
   shortcut is far worse than a stated one.

## Procedure

### 1. Get a text report on disk, and pin what it is a report of

One **Glob** against the **Coverage report** slot. If only a database directory exists the analysis
cannot start: **ask the engineer to export the text report from the merged database, give you the path,
and say which runs went into the merge**. The agent cannot merge, export, or open a database.

Then one **Grep** for the report header, using the first heading in the **Report sections** slot. Record
verbatim the tool and version, the date, the build tag and the merged-input list. If the header names no
build tag or no input list, say the merge identity is unverified and mark every total below it
provisional — the gotcha on merging across builds is the failure this check exists to catch.

### 2. Read the totals once, against the goals, and never again

One **Grep** for the summary heading, then one **Read** window of about 80 lines.

Record each metric named in the **Sign-off metrics** slot with the number the report gives it and its
goal beside it. The per-metric gap ranks the work; the aggregate at the top does not, because it is
weighted and the weights were chosen by whoever set up the flow rather than by risk. Say plainly which
metrics the report contains — one with no functional-coverage section cannot support a functional
sign-off claim however green its code metrics are.

### 3. Group the holes — whole-group zeros first, then everything else

Two **Greps** and one **Read**. The first Grep is a single alternation over *every* heading string in
the **Report sections** slot, asked for with line numbers: that one hit list is the **section map**,
and it is what decides each group's metric at the end of this step. Then the zero-hit row shape from
the **Hole notation** slot, then a window over the covergroup summary.

A covergroup at zero across **every** bin is not a stimulus gap. It was never constructed, never
sampled, sampled in a component this test never built, or carrying zero weight. The same shape at module
level — zero line coverage on a module the test list says is exercised — is a build or instantiation
question and belongs to `dv-build-filelist-hygiene`. Settle it with one **Grep** of the testbench source
for the covergroup's name: a declaration with no matching construction or no sample call is the finding.
This comes first because every number underneath such a group is void until it is fixed, and no quantity
of seeds touches it.

Then one **Grep** for the per-metric hole rows and at most two **Read** windows over the densest hits.
The report already nests — bins under a coverpoint, coverpoints and crosses under a covergroup, rows
under a module and an instance path. Take that nesting as the grouping and go no finer: **rank rows and
you will plan four hundred items; rank groups and you will plan nine.** Record per group its parent, the
uncovered rows the report attributes to it, and how many of those rows you actually read. The last two
are different numbers and the plan prints both.

**Then assign each group's `metric` from the section map, never from how the row reads.** A hole row
rarely names its own metric, and one source line surfaces under three of them with three different
fixes. The token follows from which two headings the row's line number falls between:

- **Per-module code metrics.** The statement column gives `line`; the decision column `branch`; the
  expression column `condition`; state and transition rows `fsm`; net and port bits `toggle`. The three
  that get confused: a `branch` hole is an arm of an if, case or ternary never taken, a `condition` hole
  is one operand of a multi-operand expression that never took both values — the two land on the
  identical source line and need different fixes — and a transition never taken is `fsm`, not `branch`,
  even where the branch driving it is uncovered as well. If the report prints no expression column,
  record that with step 2's metric list instead of filing those holes as `branch`.
- **Covergroup summary.** A row whose parent is a coverpoint is `covergroup-bin`; a row whose parent
  names a cross — the report spells it with the crossed coverpoint names — is `cross-bin`. Splitting
  these two matters more than it looks: a `covergroup-bin` hole is one bin's worth of stimulus, while a
  `cross-bin` hole is usually a filtering problem, per the gotcha on unfiltered crosses below.
- **Assertion cover-directive section.** Every row there is `cover-property`, because a cover directive
  is one object with one hit count and no bins — so its rows-read equals its rows-reported and its only
  fix is stimulus or deletion. If the **Report sections** slot records no such heading, our report does
  not carry this metric: say that beside step 2's totals and let no group take the token, since an
  unstated absence reads as zero cover-directive holes rather than none measured.

A row under a section the map does not name gets no metric token: quote the report's own column name in
that group's `evidence` and leave the field empty. Guessing between two tokens costs more than a blank,
because the token is what decides which gotcha below a reviewer applies to the group.

### 4. Classify each group into one of six hole classes

The class decides who fixes it and how. Nothing else here matters as much.

| Hole class | How it looks in the report | What settles it | Closes by |
|---|---|---|---|
| `not-sampled` | every bin of a group at zero | step 3's source check | a testbench fix; numbers under it are void until it lands |
| `model-defect` | a bin unhittable as written — a value outside the field's range, a cross carrying combinations the protocol forbids, a coverpoint sampled after the value changed back | reading the bin definition beside the signal it samples | a covergroup edit, owned by whoever owns the model |
| `unreachable` | a toggle, branch or state no stimulus can reach in this build — tied-off inputs, unused upper bits of a width-parameterised bus, a mode this parameter set disables | a source check of the parameter or tie-off, or a formal unreachability run, which is a handoff | an exclusion record naming the parameter that makes it unreachable |
| `config-absent` | reachable only under a configuration this merge does not contain | step 1's merged-input list against the **Configuration axis** slot | running that configuration, or narrowing the claim to what was merged |
| `no-stimulus` | reachable, sampled, model correct, hit count zero or below at_least | everything above ruled out | a constraint change or a directed test |
| `excluded` | present but already waived | the exclusion record, from step 5 | a waiver re-review, or nothing |

Only `no-stimulus` is a class more seeds could ever close, and step 6 decides whether they would.

Two **Greps** and two 40-line source **Reads** are available here, each entered through a Grep for the
exact signal, field or parameter name a hole row names — never by browsing. Spend them on the
`unreachable` and `model-defect` candidates, the two a wrong answer sends to the wrong person for a
week. Formal unreachability is a handoff: **ask the engineer to run it over the named targets and give
you the path to its output**. A group you could not settle from a file is recorded unsettled, never
`no-stimulus` by default.

### 5. Cross-check the exclusions already there, and link each group to a plan item

Two **Globs**, four **Greps** and two **Read** windows, split between the **Exclusion records** and
**Plan linkage** slots.

On exclusions, ask two questions per group, in order. Is any part of it already excluded — in which case
the report is quietly counting it closed and the group is `excluded`? And is that exclusion still true
given what step 4 found? An exclusion written against a parameter value the block no longer uses is a
hole wearing a waiver, and it surfaces at sign-off rather than now. Report exclusion files you could not
read as unchecked: "no stale exclusions" over a file you never opened is a claim, not a finding.

On the plan, if it is not something Read can open — a spreadsheet, a wiki page, a tracker — say so, carry
every group as unmapped, and ask the verification lead to map them. A group with no plan item is one of
two things and they are not close: a model artifact nobody meant to measure, or a feature nobody wrote a
requirement for. The first is deleted from the goal; the second is the most valuable thing this procedure
finds. Do not merge them into "unmapped" and move on — say which you believe and what would settle it.

### 6. Decide whether more seeds could ever help, then rank

The seeds question is the one the meeting is actually about, and it is answerable only for
`no-stimulus` groups; for every other class the answer is no, by construction. If the **Trend record**
slot names a readable file, spend the last **Grep** on it and compare the last several regressions for
this metric. If the number moved by less than its own run-to-run spread while seed count kept climbing,
the stimulus has saturated and more of it closes nothing. If the slot is unfilled or unreadable, record
`unmeasured` — the report carries one merged snapshot and cannot show a trend. Then apply the judgement
no trend can: a bin needing a three-way coincidence the constraints make individually rare will not
arrive by waiting, whatever the curve is doing.

Then order the groups on these keys, highest first:

1. **Sign-off gap** — the group sits under a metric short of its goal in **Sign-off metrics**. A group
   under a metric already at goal is not urgent however many bins it holds.
2. **`not-sampled` and `model-defect` before everything else remaining.** They make the report lie, they
   are cheap, and every figure ranked below them moves when they land.
3. **Unmapped**, from step 5 — it needs a decision from a person before anyone can size it.
4. **Cheap unlock** — bins closed per change. One constraint edit opening two hundred bins outranks a
   directed test opening three.
5. **Bin count, last.** Counts are an artifact of how the model was written: a cross with three hundred
   holes and a coverpoint with three are routinely the same afternoon's work.

Route each group's owner on the hierarchy path in its `where` field through the profile's **Area to owner
map** — never on the test name, never on who last edited the covergroup. If the map yields nothing, leave
the owner blank and list the candidates; a blank owner is fixed in one message.

### 7. Draft the closure plan

Author it as text for the engineer to paste; nothing here writes a file. One header block, then one block
per group in rank order:

```
report     : <the text report path, its tool and version, and the build tag from step 1>
scope      : <which metrics it contains, and which configurations the merge inputs cover>
totals     : <each sign-off metric, its reported number, and its goal>
holes      : <g> groups from <r> rows read of <n> rows reported
run id     : <whatever identifies this merged run for us>
coverage   : <sections opened of sections present; which checks were handed off and to whom>
```

```
group      : C1
metric     : line | branch | condition | fsm | toggle | covergroup-bin | cross-bin | cover-property
where      : <instance path, module or covergroup, exactly as the report spells it>
hole class : unreachable | not-sampled | model-defect | config-absent | no-stimulus | excluded
holes      : <rows in this group, and how many of them were read>
evidence   : <report line number for every count, plus file and line for every source check>
plan item  : <the item from the plan linkage, or "unmapped" plus which of the two kinds you believe>
closes by  : <the one named change — an exclusion record, a covergroup edit, a constraint, a directed test, or a configuration to run>
seeds help : yes | no | unmeasured
rank       : <n> because <sign-off gap / report-distorting / unmapped / cheap unlock>
owner      : <name from the area-to-owner map, or blank plus candidates>
```

Leave a field empty rather than filling it plausibly, and write the `coverage` line even when it is
embarrassing. "Read 340 of 4,100 uncovered rows; the per-instance section was never opened" is a useful
plan; the same plan without that line reads as a complete audit and is not one.

## Gotchas

- **A covergroup at exactly zero across every bin is an integration bug until proven otherwise.** Never
  constructed, never sampled, or built in a component this test does not create. The tell is that its
  siblings in the same file are healthy. Seeds never move it, and people spend weeks on it.
- **`option.at_least` turns hit bins into holes.** A bin counts as covered only when its hit count reaches
  `at_least`, so a bin hit three times against a goal of ten reports uncovered. "Never hit" and "not hit
  enough" are different findings with different fixes — read the hit-count column, not the covered flag.
- **Automatic bins are noise wearing a coverage badge.** A coverpoint written with no explicit bins gets
  automatic ones up to `auto_bin_max`, 64 by default, so a wide field becomes 64 arbitrary buckets that
  map to no requirement at all. Holes there are a model decision, never a directed test.
- **An unfiltered cross is combinatorial fiction.** Crossing a 16-bin coverpoint with a 20-bin one creates
  320 bins, most of them combinations the protocol forbids. A cross at 8 percent with 300 holes almost
  always needs `binsof` and `intersect` filtering or `ignore_bins`, not 300 tests.
- **`ignore_bins` and `illegal_bins` are not interchangeable.** `ignore_bins` drops a bin from the count
  silently; `illegal_bins` errors the moment it is hit. Shrinking a denominator with `illegal_bins`
  converts a coverage decision into a runtime failure, on some seed nobody is watching.
- **Type coverage and instance coverage answer different questions.** A module figure merged over forty
  instances can read 100 percent while every instance sits at 60, and the reverse happens too.
  Per-instance data exists only if `option.per_instance` was set before the run. Say which one your number
  is; a sign-off argument built on the wrong one collapses in review.
- **Toggle coverage on a parameterised bus is unreachable by construction.** Unused upper bits of a
  width-parameterised port, tied-off configuration inputs and scan or debug signals dominate the hole count
  and none of them are stimulus. The exclusion must name the parameter that makes them unreachable, or it
  rots silently at the next width change.
- **An exclusion anchored to a file and line moves onto innocent code at the next edit.** The number stays
  green while the coverage underneath it moves. Prefer whatever anchor our exclusion format offers that
  survives a refactor, and re-review the file every time the block is merged into.
- **Merging across builds loses bins quietly.** Two runs built from different parameter sets or a changed
  coverage model do not merge into a superset; bins present in only one database land in a denominator
  that may or may not include them. Confirm one build tag before quoting any total.
- **100 percent of a model nobody reviewed is a number, not evidence.** Holes are the visible failure; the
  invisible one is the bin that was never written. A plan that never asks what is missing from the model
  itself ships a green report over an unverified feature.

## Human verification — what a wrong answer looks like

Before taking the plan to anyone, check:

- every group carries exactly one hole class, and `no-stimulus` was reached by ruling the other five out
  rather than by default
- no group is `unreachable` without a source line or a named handoff behind it — "looks unreachable" is
  how a real hole becomes a permanent waiver
- every `metric` came from the section the rows sit in rather than from the row's wording — a condition
  hole filed as `branch` sends one person to read an expression they will not find, and a cross hole
  filed as `covergroup-bin` sends a filtering problem to whoever writes the three hundred tests
- every count cites a report line number, and rows-read is smaller than rows-reported wherever the budget
  was actually spent
- the totals are quoted from the report and each is named against its own goal, not rolled into one number
- `seeds help` is `yes` only for a `no-stimulus` group whose trend was actually read, and `unmeasured`
  wherever the trend record was not readable
- every owner appears in the area-to-owner map, and none was inferred from who wrote the covergroup
- the `coverage` line is present, and the plan is not being read as an audit of the whole report

A wrong answer is a tidy table of forty rows, each with an owner and a directed test beside it, produced
from a report whose largest covergroup was never sampled and whose toggle holes are all tied-off pins. Its
second signature is a single percentage as the headline, with no statement of which metric it is, which
configuration produced it, or which builds were merged to get it.

## Done when

Each named owner has one group, one hole class and one change to make, and the plan says on its face how
much of the report that rests on.
