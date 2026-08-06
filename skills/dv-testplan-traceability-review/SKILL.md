---
name: dv-testplan-traceability-review
description: Audit a verification plan's feature to test to coverage to checker chain across the files actually on disk, and decide whether a milestone coverage claim is supported by evidence. Use when you are about to approve a block's verification plan, when someone hands you a coverage percentage to sign off, when plan rows read like test names rather than behaviours, or when you suspect features are being stimulated but never checked.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Verification Plan Review and Feature-to-Coverage Traceability Audit
  semiskill-function: design-verification
  semiskill-role: verification-lead
  semiskill-level: lead
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-07-09
  semiskill-tags: testplan, vplan, coverage, traceability, review, milestone, sign-off
---

# Verification Plan Review and Feature-to-Coverage Traceability Audit

Plan reviews are usually done by reading the plan, which is why they catch wording and miss the two
failures that decide whether a block is verified: a feature nothing tests, and a feature everything
tests that nothing checks. Neither is visible in the plan document, and neither is visible in the
coverage report. They appear only when the plan row, the test source, the coverage item and the
checker are laid side by side and one of the four turns out to be missing.

The output is **a findings list keyed to plan rows, plus one explicit call on the milestone claim**,
with a stated audited fraction under it — not a summary of the plan, and not the coverage percentage
read back to whoever quoted it.

## When to use something else

- **Requirement tags are not plan rows.** Tracing numbered hardware safety requirements through to
  tests and evidence for an assessment is `dv-safety-req-trace-audit`, the safety-verification skill,
  which may not be in your copy of the pack yet. That one asks whether every requirement is traced in
  both directions and nothing has gone stale; this one asks whether the plan is a *good plan* and
  whether its coverage number means anything. Do not build a safety matrix out of these blocks — the
  obligations and the field names differ.
- A night of regression failures behind the milestone: `dv-regression-triage-routing`. One failing
  test blocking sign-off: `dv-sim-log-first-error`. No idea where the plan, tests or coverage output
  live: `dv-repo-orientation` maps the machinery, and this procedure assumes that map exists.
- Closing named uncovered bins is stimulus work, not review work. This says *which* rows deserve it.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Plan export | [[FILL: where our verification plan is exported to a file that can be read from disk, in what format, and which columns hold the feature description, the owning test, the coverage item and the status]] | verification lead |
| Test-to-plan link | [[FILL: how a test declares which plan row it implements — a tag in a header comment, a naming rule, a column in the plan export, or nothing at all]] | verification lead |
| Coverage report | [[FILL: the text coverage report our flow writes, which tool writes it, and the section headings that separate code coverage from functional coverage from assertion coverage]] | coverage owner |
| Exclusion record | [[FILL: where our coverage exclusions and waivers live, whether the report we are handed is before or after they are applied, and what justification each one must carry]] | coverage owner |
| Checker vocabulary | [[FILL: how a check is recognised in our source — the scoreboard class names, the assertion label convention, and the macros our comparisons are written with]] | block DV owner |
| Merge provenance | [[FILL: what our merged coverage database records about the runs that went into it, and whether runs that ended in a failure are dropped before the merge]] | DV infra owner |
| Coverage goals | [[FILL: the per-metric goals this block signs off against, and whether they are stated per feature or only as one block-level number]] | verification lead |
| Out-of-scope record | [[FILL: where we record features deliberately not verified at this level, and who accepts that risk]] | verification lead |
| Milestone criteria | [[FILL: what this milestone actually requires — which metrics, which thresholds, and what evidence sign-off expects to see]] | verification lead |

Four pack-wide facts are read from `_shared/team-profile.md` and are not re-asked here: **Coverage
output** (step 1), **Regression summary** (step 7), **Area to owner map** and **Sign-off** (step 8).

Two rows above sit next to a profile fact and are **not** the same fact. **Coverage report** is
narrower than the profile's *Coverage output*: the profile records where merged coverage lands, which
is usually a database directory, and a database cannot be read here — this row asks for the text
report a person generated from it, its tool and its section headings. **Checker vocabulary** is not
the profile's *Fatal markers*: fatal markers are what a failing run prints, while checker vocabulary
is what a check looks like in source whether or not it ever fires — and a check that never fires is
exactly what this review hunts.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented column name sends the
audit down the wrong column, and every row after it is then wrong in the same direction, which reads
as a pattern rather than as a mistake.

## Retrieval budget — read this before opening anything

A hierarchical coverage report for one block runs to hundreds of thousands of lines and a plan export
can carry a thousand rows. This review samples; it does not traverse.

1. **Grep, Read and Glob open files on disk.** A plan held only in a planning tool, a wiki or a
   spreadsheet cannot be searched here, and neither can a coverage database. Step 1 resolves both to
   paths or states plainly which check became impossible.
2. **Never open the coverage report with Read first.** Its header is the one exception: the first
   60 lines carry the provenance and are worth a Read.
3. Orientation costs **3 Globs and 2 Reads** — the plan export, the coverage report and the exclusion
   record, plus the report header and the plan header.
4. Choosing the sample costs at most **2 Greps and 3 windowed Reads** of about 80 lines over the plan.
5. The step 4 walk costs **3 Greps per sampled row** with the sample capped at **10 rows** — 30
   Greps. Step 5 adds at most **4 windowed Reads** of about 60 lines, for covergroup definitions, the
   report section behind a disputed number, and the exclusion record. Step 7 adds at most **5 Greps**
   of the regression summary.
6. The ledger is about 3 Globs, 39 Greps and 9 Reads — near 50 calls, a full session's attention.
   No step in this procedure exceeds it.
7. If a **Grep** returns more than about 200 hits the pattern is too broad: anchor the coverage item
   name, or scope the search to one directory, before reading anything around the hits.
8. **Stopping rule.** Stop at ten audited rows or when the ledger is spent, and **state the
   fraction** — "audited 10 of 214 rows; the functional-coverage section was never opened below its
   top level". An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Get the three artifacts onto disk, or name the one you could not

- **The plan export.** The **Plan export** slot says where ours lands and which column is which; use
  **Glob** to find it. If the plan lives only inside a planning tool, ask the plan owner to export it
  to a text or delimited file and to give you the path. Record its export date or revision.
- **The coverage text report.** The **Coverage report** slot names it; the profile's *Coverage
  output* says where the database behind it lives. The agent cannot open a coverage database or
  produce a report from one — **ask the engineer to generate the text report from the merged database
  the claim actually rests on, and to give you the path it was written to**.
- **The test sources.** Already in the repository; nothing to request.

If one of the three cannot be produced, say which checks became impossible rather than substituting a
neighbouring artifact. A plan audited against last quarter's report is a fabricated review.

### 2. Establish the provenance of the number before reading the number

**Read** the first 60 lines of the coverage report — tool, version, generation date, the databases
merged, whether exclusions were applied. Then **Grep** the report once for the exclusion file's name
and **Glob** for the **Exclusion record** itself. Four questions, all answerable before any
percentage matters:

1. **Which runs went into the merge**, and were runs that ended in a failure dropped first? That is
   the **Merge provenance** slot. If failing runs were kept, part of this number came from runs whose
   checkers never reached the end.
2. **Before or after exclusions?** If after, the exclusion record is evidence and is reviewed in
   step 5, not taken on trust.
3. **Which build and RTL revision**, and does it match the one the milestone is claimed against?
4. **Which is older, the report or the plan export?** Rows added after the report was written cannot
   have coverage in it; rows deleted since are still being counted.

A percentage with no provenance is not evidence, and this is the cheapest place to say so.

### 3. Choose the sample, and write down how you chose it

Ten rows out of hundreds is a sample, and a sample chosen by scrolling is a biased one. Take **every
row the milestone claim names as closed** — those rows *are* the claim; **the error, reset and
back-pressure rows**, the least-planned corner of every plan; and **two rows chosen for no reason at
all**, as a control on the other two groups.

If the export is under about 400 rows, **Read** it in bounded windows; above that, **Grep** for the
status value the claim uses and Read only around the hits. Write the sample rule into the review — a
reader who knows the sample was drawn from claimed-closed rows reads the findings correctly, and a
reader who thinks it was random does not.

### 4. Walk the four links, and report the first one that breaks

Per sampled row, at most three **Grep** calls: **the test name** from the row across the test sources;
**the coverage item name** from the row in the coverage report; and **the Checker vocabulary
strings**, scoped to the file the test resolved to or the environment directory the row names.

The **Test-to-plan link** slot says how a test declares the row it implements. If the honest answer is
"nothing", the link is by name alone and every match is provisional — say that once in the review
rather than per row.

Report only the **first** broken link. The rest are consequences: a row with no test also shows an
uncovered item and an idle checker, and filing three findings for one hole sends three people to look
at one thing.

| First broken link | What the coverage report shows | What it actually means |
|---|---|---|
| no test named, or the named test is nowhere in the sources | the item sits at zero, or is absent entirely | planned and unstimulated, or the plan is stale and names a retired test |
| test exists, no coverage item named | nothing — the feature has no line in the report | the test runs, and nobody can say whether the interesting case ever occurred |
| coverage item named but reported at zero | a visible zero | stimulus never reached the condition — the honest failure, and the easiest to act on |
| coverage item high or full, no checker found | the best-looking row in the table | **stimulated and unchecked** — the most expensive row in the plan, and why this procedure exists |
| checker found but demoted to a warning, disabled by a knob, or waived | a passing test and a full bin | the check is present in source and absent in effect |
| item full only because its bins are excluded or ignored | full | the denominator moved; the design did not |

A row where all four resolve is `plan chain: complete`. That asserts the four artifacts exist and
name each other — **not** that the checker is correct. Whether the check compares the right thing is the block
owner's answer to give, and claiming it here is the one overreach this review must not make.

### 5. Read the coverage numbers the way the tool computed them

Take the **Coverage goals** slot first: a block-level goal and a per-feature goal are different
claims, and a plan reviewed against the wrong one passes for the wrong reason. Then spend the four
windowed **Read** calls on whatever is actually disputed.

Four families sit in the report and get added together as though they were one number. Code coverage
— line, branch, condition, toggle, FSM — says which code ran. Functional coverage says which planned
situations occurred. Assertion coverage says which properties were exercised as well as never
violated. The plan's status column says what a human believes. Only the second is evidence about the
feature, and only the plan says whether the second asked the right question.

These move a number without changing any verification:

- **`ignore_bins` versus `illegal_bins`.** Both leave the total, but an `illegal_bins` hit is
  reported as an error while an ignored bin is silently gone. A bin moved from illegal to ignore
  during a coverage push turns a failing condition into a higher score.
- **`option.weight` and `type_option.weight`.** A weight of zero drops a coverpoint from its group's
  score while leaving it printed at whatever it reached. A group total of 100% above a coverpoint
  listed at 12% is this, nearly every time.
- **`option.at_least`** is the hit count a bin needs before it counts. Lowering it from ten to one is
  a coverage improvement that involved no verification.
- **Auto bins.** A coverpoint with no explicit bins gets automatically generated ones, capped by
  `auto_bin_max` — 64 by default. A wide coverpoint therefore reports against 64 arbitrary ranges,
  and full coverage over them says nothing about the values the feature cares about.
- **Crosses.** Crossing two coverpoints multiplies their bins and most products are unreachable, so
  an uncovered-bin count from an unbounded cross measures nothing. Look for `binsof` and `intersect`
  filtering, or an explicit ignore set, before quoting a cross percentage as a fact.
- **The exclusion record**, read against the slot's justification rule. An exclusion that grew between
  two milestones and a number that grew in the same window are usually one event.

### 6. Review the plan as a plan

The traceability walk cannot see these; only reading the rows can.

- **A row naming a test instead of a behaviour.** "Runs the descriptor-wrap test" is a claim about the
  testbench. "The descriptor ring wraps at the last entry and no beat is dropped" is a claim about the
  design, with an obvious bin and an obvious checker. The first cannot be reviewed, which is exactly
  why it survives review.
- **A row with no measurable outcome.** If nobody can name the bin or the assertion that settles it,
  the row is a sentence, not a plan entry.
- **The missing negative space.** Error responses, protocol violations, back-pressure and stall, reset
  during activity, low-power entry and exit, clock-ratio corners, X at the boundary. A plan holding
  only well-behaved traffic is a plan for a design that never meets a real integrator.
- **Stale owners and stale status**, checked against the report date from step 2.
- **No out-of-scope record.** The **Out-of-scope record** slot: an honest plan states what it is
  deliberately not verifying at this level and who accepted that risk. A plan without one is not
  complete, it is silent — and silence is read at integration as coverage.
- **Rows whose coverage item is a code-coverage metric** — a feature with no functional measurement,
  dressed as one.

### 7. Test the milestone claim against what you actually saw

Take the **Milestone criteria** slot and compare it metric by metric with the report from step 2. Then
spend up to five **Grep** calls on the profile's *Regression summary* confirming that the tests your
sampled rows named actually ran, and passed, in the regression the coverage came from. A row pointing
at a test that has been failing for three weeks is a closed row resting on a red result.

Two things must be handed back rather than assumed: **ask the engineer to confirm the coverage
database was built from the RTL revision the milestone names**, and, if the header did not say, **ask
the coverage owner whether the report you were given is the pre- or post-exclusion one**. Record which
answers came from a person rather than from a file.

### 8. Write the review

Leave a field blank rather than filling it plausibly.

```
plan       : <path, format, export date or revision>
cov report : <path, tool, generation date, and whether the numbers are pre- or post-exclusion>
sampled    : <n of m rows, and the rule the sample was drawn by>
```

One block per audited row, worst plan chain first:

```
row       : <the row identifier or feature text, verbatim from the export>
plan chain: complete | no-test | no-cov-item | no-checker | unresolved
test      : <file and line that implements it, or blank>
cov item  : <covergroup, coverpoint, bin or assertion name, and the report line>
score     : <the number the report gives that item, pre- or post-exclusion>
checker   : <the file and line that would catch this feature being wrong, or blank>
break     : <what is missing, in one sentence, and what the report looks like anyway>
owner     : <from the profile's area-to-owner map, or blank plus candidates>
```

`plan chain: unresolved` is a row whose links exist but could not be settled inside the budget. It
is not `plan chain: no-checker`: one says nobody looked, the other says somebody looked and found
nothing.

```
milestone   : <the claim being reviewed, quoted as it was made>
claim       : <the percentage claimed and where that number came from>
measured    : <what this report shows for the same metric, with its line>
gap         : <every difference between those two, itemised>
plan qual   : <the step 6 findings, worst first>
plan call   : approve | approve-with-conditions | evidence-missing | reject
conditions  : <what must be true before approval, each with a named owner>
coverage    : <n of m rows audited; which report sections were never opened; which answers came
               from a person rather than a file>
```

The field is `plan call` and not `decision` on purpose: sibling skills use `decision` for release
go/no-go and artifact-release vocabularies, and these blocks get compared exactly. A plan review must
never be matched against a release gate. Route each row's owner through the profile's **Area to owner
map**, never through the test name, and address the call to whoever the profile's **Sign-off** fact
names. `plan call: evidence-missing` is right far more often than it is used — it is what to say when
the artifacts could not be assembled, and it is far cheaper than a withdrawn approval.

## Gotchas

- **A hit bin proves stimulus, never correctness.** Coverage answers "did this situation occur" and
  has no opinion on whether the design responded correctly. A row with a full coverage item and no
  checker is 100% covered and 0% verified, and it looks better on every dashboard than the honest
  zero beside it.
- **Coverage from a failing run usually still merges.** Unless the flow drops databases from runs that
  ended in an error, a night with a fifth of its tests red still contributes their stimulus to the
  number. Confirm the merge policy before accepting a merged figure — this is the commonest way a
  coverage claim is quietly inflated.
- **Merging across builds is arithmetic, not evidence.** Databases from two RTL revisions, or two
  different define sets, merge into a number describing a design that never existed. Most tools will
  do it after a warning, and the report header is the only record of what went in.
- **Code coverage saturates long before functional coverage means anything.** Full line and branch
  coverage on a block whose plan has no covergroup for its error responses means the lines executed.
  That is not a statement about the feature, and it is the number most often quoted as one.
- **A covergroup sampled at the wrong moment looks better than one never sampled.** Never sampled
  reports zero and gets noticed. Sampled on the wrong event — every clock instead of on the handshake,
  or after the transaction has already been cleared — reports high numbers, fills every bin and hides
  the hole. No report can show this; only the sampling code can. A covergroup the environment never
  constructs under this configuration is worse still: it does not appear at all, so the feature reads
  as unplanned rather than as unmeasured.
- **Exclusions are an axis of their own.** A waiver moves the number with no verification attached.
  Always ask which report you were handed, and treat an exclusion carrying no written justification
  and no owner as an open finding rather than as bookkeeping.
- **The plan's status column is a belief, not a measurement.** It is edited by people under milestone
  pressure and is the field most likely to disagree with the report. When they disagree, the report is
  evidence and the column is a lead.
- **An orphan test is a finding in the other direction.** A test in the regression that no plan row
  claims is either verification nobody counts or a test nobody maintains, and the second fails
  silently for months. Step 4 only finds orphans in the plan-to-test direction — say so rather than
  implying the reverse sweep happened.

## Human verification — what a wrong answer looks like

Before the review is sent, check:

- every row's finding names the **first** broken link, not all of them
- no `plan chain: complete` was awarded on a name match alone when the **Test-to-plan link** slot
  said tests carry no tag — those rows are `plan chain: unresolved`
- every percentage quoted carries its report path, its date, and whether it is pre- or
  post-exclusion; a bare number in a review is the thing this procedure exists to stop
- the sample rule is stated, and the `coverage` line's denominator is the plan's real row count
- no claim is made about whether a checker is *correct* — only that one exists
- nothing about requirement tags or a safety matrix appears; that is a different skill
- any fact supplied by a person rather than read from a file is attributed on the `coverage` line

A wrong answer reads as a confident green table in which every sampled row is complete, produced
against a coverage report generated before the last two features were added to the plan. Its second
signature is `plan call: approve` on a claim whose provenance step 2 never established — the number
was never in doubt, only what it was a number about.

## Done when

Every audited row names its first broken link with a file and a line behind it, the milestone call is
one of the four values with its conditions owned, and the fraction of the plan you actually audited is
written where nobody can mistake the sample for the whole.
