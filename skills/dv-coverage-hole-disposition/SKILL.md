---
name: dv-coverage-hole-disposition
description: Classify every unhit bin in a merged functional-coverage report as a stimulus gap, a constraint blockage, a bin-definition defect, an out-of-scope configuration or genuinely unreachable, then draft the one artifact that closes it — a test change, a covergroup fix, or an exclusion with a justification that survives lead review. Use when a coverage report has holes you have been told to close, when a covergroup sits at 60 percent and nobody knows why, when a cross has hundreds of empty bins, or when someone asks you to write a waiver for a bin you cannot hit.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Functional Coverage Hole Disposition and Closure
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.2.0
  semiskill-review-by: 2027-04-30
  semiskill-tags: coverage, covergroup, bins, exclusions, waivers, closure, cross-coverage
---

# Functional Coverage Hole Disposition and Closure

A report with two hundred unhit bins is almost never two hundred missing tests. Some describe values
the design cannot produce, some a feature this configuration does not build, a great many are
automatic bins nobody meant to write, and a handful are real stimulus you owe. The expensive mistake
is treating them uniformly — tests written for bins that are bin bugs, exclusions written for bins
that are real holes — and arriving at lead review with a percentage instead of an argument.

The output is one **disposition per bin**: a class, the evidence behind it, the single artifact that
closes it, and a line saying how many of the report's holes you actually reached.

## When to use something else

If **nobody has read the report yet** and what is wanted is a ranked closure plan across every metric,
that is `dv-coverage-hole-closure` — it works on hole groups and the whole report; this skill starts
from the handful of bins you were told to close. If the question is whether the merged number is
trustworthy at all, `dv-coverage-merge-report` comes first.

If the tests that should hit these bins are **failing**, the holes are a symptom, but not because a
failing test covers nothing — coverage is sampled during simulation whatever verdict the run ends on.
A run that stopped early sampled only what it reached, and whether a failed run's database is written
and merged at all is a flow policy, which is what the **Merge scope** slot records. Start at
`dv-sim-log-first-error`, or `dv-regression-triage-routing` for a whole night of them. If the covergroup is absent from the report entirely, rather than present with
zero hits, suspect its source never reached the build and check `dv-build-filelist-hygiene`. If you
cannot yet locate the coverage output or the covergroup sources, spend twenty minutes on
`dv-repo-orientation`. Unhit bins in a generated register covergroup whose accesses are themselves
mismatching are `dv-ral-bringup`, not this.

## Fill this in for our team

Four facts this procedure spends are pack-wide and live **once**, in `_shared/team-profile.md`. A
second copy of an owner map drifts silently and nothing can say which is stale.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Coverage output** — where merged coverage lands | step 1, locating the report |
| **Run identity** — what identifies one run for us | step 8, the `run id` line |
| **Sign-off** — who signs off, and on what evidence | step 7, addressing the exclusion draft |
| **Area to owner map** | step 8, the only thing routing is allowed to key on |

Ten more are specific to bin disposition and are asked for here and nowhere else.

| Slot | What to fill in | Who knows |
|---|---|---|
| Unhit marker | [[FILL: the exact string our coverage text report prints on a bin with no hits, and how one per-bin row is laid out — bin name, hit count, goal]] | DV infra |
| Coverage summary heading | [[FILL: the heading our report prints above the per-covergroup summary table, and which columns that table carries — achieved percentage, weight, bins hit of bins total]] | DV infra |
| Merge scope | [[FILL: which tests and which build a merged report covers, how many seeds that is, and where that list is recorded]] | DV infra |
| Sign-off coverage list | [[FILL: which covergroups are on our sign-off list and the percentage each has to reach]] | verification lead |
| Coverage model source | [[FILL: where our covergroups live in the tree, and which of them are generated rather than hand-written]] | block DV owner |
| Test list | [[FILL: where our test and sequence list lives, and whether one row names the sequence it runs]] | your mentor |
| Constraint surface | [[FILL: where this block's sequence-item constraints and randomisation knobs live]] | block DV owner |
| Config identity | [[FILL: how a derivative or configuration is named for us, and where its enabled-feature list is recorded]] | block owner |
| Formal unreachability | [[FILL: whether we have an unreachability analysis flow, who runs it, and where its text output lands]] | DV infra |
| Exclusion file | [[FILL: where our coverage exclusions live, what each entry is keyed on, and what a justification must contain]] | DV lead |

**Sign-off coverage list is not the profile's Sign-off row.** The profile records *who* signs and on
what evidence; this slot records *which covergroups, to what percentage*. Fill both; copy neither
into the other.

**Unhit marker and Coverage summary heading describe two different layouts**, not one fact. The
first is a per-bin row — bin name, hit count, goal, and nothing about the covergroup around it, which
is why step 3 has to spend a **Grep** on the covergroup's own name to reach the right bin table. The
second is the per-covergroup table that carries the achieved percentage and, on some tools, the
weight. Step 2 cannot rank without the second, so if our report prints no such table, or prints it
without a percentage or a weight column, **say that in the slot** — the ranking then runs on what is
left rather than on invented numbers.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented bin path in an
exclusion file is the worst artifact here: it matches nothing, excludes nothing, and everyone believes
the hole is closed.

## Retrieval budget — read this before opening anything

A merged report lists every bin of every instance and routinely runs to hundreds of thousands of
lines. Reading one is impossible; the ranking in step 2 exists so you do not have to.

1. **Grep, Read and Glob work on files on disk.** They cannot search a report pasted into a chat. If
   the holes arrived as pasted text, get the path it came from, or ask for it to be saved to a file
   and be given that path. Until a path exists you may read the pasted rows by eye — say so, and mark
   every disposition provisional.
2. **Never open the report with Read first.** Step 1 spends one **Glob** and one **Read** of about 40
   lines at the header. Step 2 spends three calls: one **Grep** for the **Coverage summary heading**,
   one **Read** of about 60 lines over the summary table it lands on, and one **Grep** for the
   **Unhit marker**. Step 3 spends **two calls per covergroup opened** — one **Grep** for that
   covergroup's name, because the Unhit-marker hits are bare line numbers that do not say which
   covergroup they sit in, then one **Read** window of about 60 lines at the bin table that Grep
   found — capped at **three covergroups**.
3. **Once per session, not once per hole:** the merge covers one build, so the enabled-feature list
   named in **Config identity** is the same for every hole. Spend one **Grep** and one 40-line
   **Read** on it at the top of step 5 and compare every bin against the copy you hold.
4. Per hole: one **Grep** in the **Coverage model source** and one **Read** of about 40 lines at the
   declaration (step 4); then at most **two further Grep calls** in step 5 — one in the **Test list**,
   one in the **Constraint surface** — and one further 40-line **Read** at whichever hit matters.
   Step 5's configuration check spends nothing per hole; step 6 spends nothing at all, being a handoff.
5. Step 7 spends one **Grep** of the **Exclusion file**, once, covering every bin in the session.
6. **Cap the session at six holes** — about 44 tool calls at full budget, a whole session's attention,
   and most holes settle well before spending their share. The ledger: 2 in step 1, 3 in step 2, 6 in
   step 3, 12 in step 4, 20 in step 5 (2 once for the configuration list, then 3 per hole), none in
   step 6, 1 in step 7. Spend it on the holes step 2 ranked highest, not the first six in the file.
6. A **Grep** returning more than about 200 hits is too broad; anchor it on the bin name with its
   surrounding punctuation before reading anything.
7. **Stopping rule.** If a hole's budget is spent and the class is still unsettled, write
   `bin class: unsettled` with the one thing you still need and move on. Guessing past this point
   produces the exclusions that get found in an audit.
8. State the coverage — "disposed 6 of 214 unhit bins; the other 208 unexamined". An unstated shortcut
   is far worse than a stated one.

## Procedure

### 1. Confirm you are holding a merge, and know what it was merged from

**Glob** under the profile's **Coverage output**, then **Read** about 40 lines of the report header. A
per-test report is not a disposition input: a bin unhit by one test is routinely hit by another, so
every hole classed from it may be an artefact.

Check the header against the **Merge scope** slot — which tests, which build, how many seeds. If it
predates the covergroup edits in question, or covers a different build, stop and **ask the engineer to
merge the coverage databases for the test list this disposition is about and to give you the path to
the merged text report**. The agent cannot merge databases or produce a report, and must never
describe what one would have said.

### 2. Retrieve the two numbers the ranking needs, then rank

The ranking below turns on a covergroup's achieved percentage and its weight. **Neither is in a bin
row** — a bin row carries a bin name, a hit count and a goal, per the **Unhit marker** slot — so they
are retrieved here, once, before anything is ranked.

**Grep** the **Coverage summary heading**, then **Read** about 60 lines over the summary table that
Grep lands on. Record per covergroup, verbatim, the achieved percentage and — only if the table
prints a weight column — the weight. Then **Grep** the report for the **Unhit marker**: that yields
line numbers and a count, the denominator for step 8's coverage line.

If the report has no covergroup summary, or the table omits one of those columns, **say which number
is missing and rank without it**. A percentage or a weight that the report did not print, and that
you supply from an impression, is the same defect as an invented bin path.

Rank on, in order:

1. On the **Sign-off coverage list** and below its required percentage — the achieved percentage from
   the summary Read, against the percentage that slot records. Nothing else competes.
2. Weight. Coverage is a weighted average, so a bin's cost depends on its covergroup's weight and how
   many bins share the score with it, not on how alarming the row looks. **Where the summary prints
   no weight column this is an order-of-magnitude judgement, not a figure**: a four-bin covergroup
   and a two-hundred-bin cross are different orders, and that is the whole of what you may claim.
   Say which of the two you did.
3. Concentration. Fifty holes in one cross are usually one disposition; five holes across five
   covergroups are five.

Take the top six. Bins off the sign-off list still need a justified exclusion, so if none of the six
is on that list, say so rather than working the list you happen to have been handed.

### 3. Read the bin exactly as the report spells it

**Read** the 60-line window at the ranked covergroup's bin table and record, verbatim: covergroup
name, coverpoint or cross, bin name, hit count, and the value that count is compared against. Every
later artifact is matched against these strings by a tool, and a bin path retyped from memory matches
nothing.

Two rows that look alike are not: **zero hits and hits-below-threshold are different problems**. The
first can be anything below; the second is stimulus that already exists and needs more seeds. If the
row carries no hit count, say so — the **Unhit marker** slot is meant to describe that layout, and if
it does not, the slot is not finished.

### 4. Settle the bin definition in source, before blaming any test

Most holes handed to a junior engineer are decided here, and none are decided in the report. **Grep**
the **Coverage model source** for the bin or coverpoint name, **Read** about 40 lines at the
declaration, and check in this order:

- **Automatic bins?** A coverpoint with no explicit `bins` gets bins the tool invents from the value
  range, up to `option.auto_bin_max`. A hole in one names a bucket nobody intended to hit
  individually — `bin class: bin-defect`, closed by naming the bins.
- **Do the ranges fit the sampled expression?** A range wider than the field, or written for a
  previous encoding, can never be hit — also `bin class: bin-defect`, and the fastest to prove.
- **A cross?** A cross generates the product of its coverpoints' bins. Twelve crossed with twenty is
  240; if the protocol permits forty combinations the other 200 are a missing `binsof` and `intersect`
  filter, not 200 holes.
- **A transition bin?** `(2 => 3)` needs the sample where the value is 3 to be the *next* sample after
  the one where it was 2. Any sample of another value in between breaks it, so a transition hole is
  far more often a sampling-site problem than a stimulus problem.
- **Was the covergroup sampled at all?** An embedded covergroup never constructed, one with no
  clocking event and no explicit sample call, or an `iff` guard never true, all report zero
  everywhere. One bin anywhere in it with a non-zero count is the cheapest proof sampling happened.

`option.at_least`, `option.weight`, `option.per_instance` and the goal options change what the report
says without changing the design or the tests. Their defaults come from the standard; how our report
renders them is a fact about our tool, so read the layout **Unhit marker** describes and do not assume.

### 5. Stimulus, constraint, or configuration — the three remaining live classes

Spend the two Greps of budget rule 3 here, in this order, stopping at the first that settles it.

**Stimulus.** **Grep** the **Test list** for the feature or sequence the bin describes. Nothing that
ever asks for it means `bin class: stimulus-gap`. A test existing is not a test having run —
cross-check the name against the **Merge scope** list, because a test outside this merge makes the
hole an artefact, and the honest move is to ask for a merge that includes it rather than write
anything.

**Constraint.** **Grep** the **Constraint surface** for the field the coverpoint samples and **Read**
about 40 lines around the hit: a constraint pinning the field, a `soft` constraint nobody overrode, a
range excluding the bin's values, a knob gating the branch that drives it. A constraint that makes the
value impossible is `bin class: constraint-block`. **A distribution weight is not a blockage** — a
value weighted one against a thousand is reachable and needs seeds. "Cannot" and "did not, in the
seeds this merge covered" are different classes with very different costs; say which you mean and
quote the seed count from **Merge scope**, not from an impression.

**Configuration.** Some bins describe a feature this build does not have — a parameter set low, a mode
tied off, a block absent from the derivative. Compare what the bin needs against the enabled-feature
list named in **Config identity**. Absent means `bin class: out-of-scope`, and the fix is never a
blanket exclusion: either construct the covergroup conditionally so the bin does not exist here, or
scope the exclusion to this configuration by name. An unscoped one hides the same bin in the
derivative that does support the feature.

### 6. Unreachable — the one claim you cannot make alone

A bin is unreachable only if no input sequence of any length reaches it. That is a formal question,
and neither the agent nor twenty minutes of reading RTL can answer it. Two proofs are acceptable, and
both are handoffs:

- **Ask the owner named in the Formal unreachability slot to run the analysis and to give you the path
  to its text output.** Note what that flow proves: it reasons about RTL signals and cover properties,
  so a bin defined over testbench-side variables sits outside it, and restating the bin as a cover
  property is itself a step someone must do and get right. If the flow does not exist, say so rather
  than treating its absence as agreement.
- **Ask the block designer to confirm the encoding cannot occur**, and record who said it and when.

Until one comes back the class is `bin class: unsettled`, not `bin class: unreachable`. Reading source
and concluding "impossible" is the most expensive wrong answer available in this procedure.

### 7. Draft the one artifact that closes it

Each class has exactly one artifact, and using the wrong one is how a disposition fails review.

| Class | Artifact | Goes to |
|---|---|---|
| `stimulus-gap` | `fix kind: test-change` — the named test or sequence, and what it must drive | test owner |
| `constraint-block` | `fix kind: test-change` — the named constraint, and the relaxation | test owner |
| `bin-defect` | `fix kind: covergroup-fix` — the bins, cross filter or sample site to change | covergroup owner |
| `out-of-scope` | `fix kind: conditional-guard`, or `fix kind: exclusion-draft` scoped by name | covergroup owner |
| `unreachable` | `fix kind: exclusion-draft` with a proof | the profile's **Sign-off** approver |
| `unsettled` | `fix kind: none-yet` — the question, and who can answer it | whoever can answer it |

First **Grep** the **Exclusion file** once for every bin in this session: a bin already excluded and
still showing means the existing entry stopped matching, which is more urgent than a new hole. Then
draft each in the form that file requires.

```
bin           : <exact covergroup / coverpoint / bin path, as the report spells it>
scope         : <this configuration only, or every configuration — and which>
justification : <why this bin can never be hit, in one sentence a designer would sign>
proof         : <path to the formal output, or the designer who confirmed it and when>
review by     : <a date, and the event that invalidates this entry>
reopens if    : <the RTL or configuration change that makes the bin reachable again>
```

An exclusion with no proof line is a hole with paperwork.

### 8. Route it and emit one block per hole

Route on the artifact's owner via the profile's **Area to owner map**, never on the test name that
happened to be running. If the map yields nothing, leave the owner blank and list the candidates — a
blank owner is fixed in one message, a wrong one costs a day.

```
report      : <path to the merged text report>
covergroup  : <name exactly as the report spells it>
bin         : <bin name and its coverpoint or cross, exactly as the report spells it>
hits        : <the count the report shows, and the value it is compared against>
bin class   : stimulus-gap | constraint-block | bin-defect | out-of-scope | unreachable | unsettled
evidence    : <file path and line, or report line number, for every claim above>
proof       : <how unreachable or out-of-scope was established, and who said so>
fix kind    : test-change | covergroup-fix | conditional-guard | exclusion-draft | none-yet
owner       : <name from the profile's area-to-owner map, or blank plus candidates>
run id      : <what identifies this merge — build tag, test list, seed count>
notes       : <anything the next person would otherwise rediscover>
```

`bin class` and `fix kind` are **local to this skill**, and deliberately not the name the sibling
uses. `dv-coverage-hole-closure`'s `hole class` field classifies hole *groups* on a coarser
vocabulary; two class lists under one field name would be compared exactly and never match. The word
`disposition` was never available to either of us — `_shared/handoff-vocabulary.md` holds it for
`dv-tool-bug-testcase-extraction`, where it records what the vendor did with a testcase — so if you
see it on a coverage row, someone has pasted the wrong column. Map one class list onto the other by
hand when both reports meet, and say that you did. Close with one line for the session — bins in the
report, bins disposed, what the rest are. Leave any field empty rather than filling it plausibly.

## Gotchas

- **`ignore_bins` and `illegal_bins` are not interchangeable.** Both remove their values from the
  coverage score, but `illegal_bins` additionally makes the simulator report an error if the value is
  ever sampled. Using it for a merely out-of-scope value turns a quiet coverage hole into a nightly
  regression failure the first time someone enables that feature.
- **A `default` bin does not raise your number.** It catches values no other bin claims, and its
  contribution is excluded from the coverage calculation — so a coverpoint whose values all land in
  `default` reads as nearly empty while looking, in source, fully binned. `default` bins also do not
  participate in cross coverage, which is one way a cross ends up emptier than either input.
- **Chasing automatic bins is the classic junior time sink.** A hole in an auto bin is a hole in a
  bucket the tool invented from a variable's range: nobody wrote it, nobody signs it off, and no test
  can be written for it as such. Name the bins and most of those holes stop existing rather than
  getting closed.
- **A hole in a cross is usually one disposition, not two hundred.** Filter the cross with `binsof`
  and `intersect` so impossible combinations are never generated, instead of excluding them one at a
  time. Two hundred exclusion lines is a liability that outlives the project.
- **Weight decides what a hole costs and is invisible in the bin row.** It is a covergroup property,
  printed in the summary table if it is printed anywhere, which is why step 2 reads that table before
  ranking. A 200-bin cross nobody signs off on can dominate the overall percentage while a 4-bin
  covergroup on the sign-off list sits well under its target. Rank on the sign-off list, then weight
  — never on the number of red rows.
- **An exclusion keyed on a hierarchical name stops matching after a rename, and nothing announces
  it.** Coverage drops and everyone blames the tests; or the name gets reused and the exclusion now
  hides a genuine hole. Every entry needs the exact string the report prints, a review date, and the
  change that reopens it.
- **A covergroup that is never sampled looks exactly like a total stimulus gap.** Zero everywhere is
  the signature of a missing construction, a missing sample call, or an `iff` guard that is never true
  — not of a testbench that drives nothing.
- **Merging two builds whose covergroup shape changed is not a merge.** Bins present on one side only
  show up unhit and are an artefact. Whether our tool refuses, warns, or keeps the shapes apart is a
  fact about our flow — record it in **Merge scope** rather than assuming the number is comparable.
- **Instance merging hides asymmetry.** With per-instance coverage off, every instance of a covergroup
  type collapses into one row, so a bin hit in one instance and missed in all the others reads as
  closed. If the disposition depends on *which* instance, say the report cannot tell you.
- **Coverage and a passing regression are independent.** A bin can be hit by a test whose checker is
  switched off, and coverage records it happily. "Covered" means sampled, never verified — so closing
  a hole by pointing at a test nobody checks the result of has closed nothing.

## Human verification — what a wrong answer looks like

Before sending the dispositions, check:

- every bin path is quoted **exactly as the report spells it**, not retyped or tidied
- the report was a **merge**, and its scope is named — tests, build, seeds
- no `bin class: unreachable` exists without a proof line naming a formal output path or a person
- no `bin class: constraint-block` was assigned to a value that is merely improbable — a distribution
  weight is not a blockage
- `bin class: bin-defect` findings point at a line in the coverage model source, not at a test
- every `fix kind: exclusion-draft` carries a scope, a justification, a review date and a reopen
  condition, and none silently covers configurations nobody reasoned about
- every percentage and every weight the ranking cites was **read from the summary table**, and where
  the table printed neither, the ranking says so instead of carrying a number
- the coverage line gives both numbers — bins disposed and bins in the report
- no exclusion was drafted for a bin that step 4 showed to be an automatic bin

A wrong answer is a tidy table of six exclusions, each justified as "not applicable to this block",
covering bins the tool generated, in a covergroup that was never sampled, measured from one test's
report rather than the merge. It reads as a closure plan and closes nothing.

## Done when

Every hole you opened carries a class, the evidence behind it, one named artifact and one owner, and
the holes you never opened are a stated count rather than a hidden one.
