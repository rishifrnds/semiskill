---
name: dv-safety-req-trace-audit
description: Rebuild the bidirectional chain from hardware safety requirements through the verification plan to test source and regression evidence, then report every untraced requirement, orphan test and stale piece of evidence with the file and line behind it. Use when a safety audit or assessment is coming, when someone asks whether every safety requirement is actually covered, when a requirement has been renumbered or deleted and nobody knows which tests still point at it, when the trace matrix was last reconciled by hand two releases ago, or when sign-off has to rest on a named regression run instead of a spreadsheet.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Hardware Safety Requirement to Test Traceability Audit
  semiskill-function: design-verification
  semiskill-role: safety-verification-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-03-24
  semiskill-tags: safety, traceability, requirements, verification-plan, evidence, audit, sign-off
---

# Hardware Safety Requirement to Test Traceability Audit

A trace matrix decays quietly. Requirements get renumbered, tests get renamed, a test written for a
requirement that was deleted last quarter keeps running and keeps passing, and the sheet that says
everything is covered was last reconciled by hand two releases ago. This procedure rebuilds the chain
from the artifacts actually on disk — requirement source, verification plan, test source, regression
result — and reports where it breaks, in **both** directions.

The output is **a per-requirement trace row, a list of orphan tests, and a coverage line stating how
much of the requirement list was really crossed**. It is not a percentage, and a percentage produced
without that coverage line is the thing this procedure exists to stop.

**What this cannot do.** It cannot start a regression, open a requirements-management tool, read a
spreadsheet, or judge whether a check is any good. It establishes that links exist. Whether the test
behind a link verifies anything is a review question for a human, and it stays one.

## When to use something else

- One failing safety test, and you need the true first error → `dv-sim-log-first-error`.
- A whole night of failures to sort and route → `dv-regression-triage-routing`.
- Fault-injection campaigns and diagnostic-coverage figures → `dv-error-injection-ras`. Traceability
  says a requirement has a test attached; it says nothing about fault metrics. The two get conflated
  in the same review meeting every time, and they are different evidence with different owners.
- You do not yet know where the plan, the tests or the results live → `dv-repo-orientation` first.
  This procedure assumes step 1 can resolve four paths.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Requirement source | [[FILL: where our hardware safety requirements live in a form Read can open; if they live in a requirements tool, who exports them and to which path]] | safety manager |
| Requirement tag shape | [[FILL: the exact shape of one requirement identifier as the requirement source writes it — prefix, separator, digit count, and what terminates it]] | safety manager |
| Tag-in-test convention | [[FILL: how a test source file declares which requirement it verifies — the keyword, attribute or comment form, and the exact tag spelling used in code]] | DV lead |
| Verification plan | [[FILL: where our verification plan lives, whether it is a file Read can open, and which of its columns carry the requirement and the test]] | verification lead |
| Plan-to-test key | [[FILL: what a plan row uses to name a test — test name, class name, sequence name, or directory]] | verification lead |
| Result-to-test key | [[FILL: which column of our regression summary names the test, which column holds the verdict, and the exact strings that column prints for a pass and for a fail]] | DV infra |
| Evidence run | [[FILL: which single regression run our safety case cites as evidence, and how that run records its own identity]] | safety manager |
| Waiver record | [[FILL: where a requirement deliberately verified by review or analysis rather than by test is recorded together with its rationale, and whether that record is a file on disk]] | safety manager |
| Revision stamps | [[FILL: how the requirement source and a test source each record when they last changed, in a form Read can see]] | DV infra |

Three further facts are pack-wide and live in `_shared/team-profile.md` — read them there rather than
re-interviewing anyone: **Regression summary** (where per-test results land), **Area to owner map**
(who a gap is routed to) and **Sign-off** (who signs, and on what evidence).

Two rows above are deliberately narrower than the profile's. **Evidence run** is narrower than
Regression summary: the profile says where summaries land, this asks *which one run* the safety case
rests on. **Result-to-test key** is narrower again — it is about the columns inside that one file,
which the profile does not record at all.

**Requirement tag shape and Tag-in-test convention are two facts, not one, and filling them in as one
is a real defect.** The identifier a requirement document prints and the string a test writes in a
comment are often spelled differently — a separator swapped, a leading zero dropped, a prefix
shortened. Treating them as identical is the commonest reason an audit reports a fully traced block
as untraced. If they genuinely are the same string here, write that down explicitly rather than
leaving it implied.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented tag shape yields a
confident and wholly false gap list, and a safety manager will act on it before anyone rechecks it.

## Retrieval budget — read this before opening anything

A requirement export runs to thousands of lines and a regression summary to tens of thousands. Both
are machine-written and neither rewards reading. Work in this order and stop when the budget is spent:

1. **Grep and Read work on files on disk.** A requirements tool, a wiki page or a spreadsheet is none
   of those. Resolve each artifact to a path in step 1; if one cannot be resolved, the audit still
   runs, with that link reported as unchecked rather than as a gap.
2. **Never open the requirement export, the plan or the summary with Read first.** **Glob** to
   locate, **Grep** to enumerate, **Read** only a bounded window at a line number a Grep returned.
3. **At most three Glob calls** (step 1) and **at most eight Grep calls**, allocated exactly: one to
   size the requirement set and one to enumerate it (step 3), one for the forward link (step 4), two
   for the backward link (step 5), one for the plan (step 6), one for the evidence (step 7), and one
   spare, normally spent on the revision stamps (step 8).
4. **At most six Read windows of about 60 lines**, entered only at a line number a Grep returned.
5. If a Grep returns more than about 200 hits, the pattern is unanchored — fix it in step 2 rather
   than reading anything. An unanchored tag pattern is the exact defect this budget exists to catch.
6. **Two consecutive Greps returning nothing means the convention is wrong, not that the tree is
   empty.** Stop and ask. "All 340 requirements untraced" is almost always a bad pattern, and it is
   the most expensive wrong answer available here.
7. If the inventory is larger than the remaining budget can cross-check, audit a **declared
   contiguous slice** — name the first and last identifier — and report the fraction. Do not sample
   at random, and never extrapolate a rate from the slice to the whole.
8. State what you actually covered. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve four artifacts to four paths

Use **Glob** — at most three calls, combining patterns rather than one guess per call — to find the
export named by the **Requirement source** slot, the **Verification plan**, the test source root, and
the regression summary for the **Evidence run**.

If the requirement source or the plan is a spreadsheet, a tool page, or any format Read cannot open,
say so now and **ask the engineer to export it to plain text and hand you that path**. Never audit
against a remembered copy; a trace matrix reconstructed from memory is exactly the artifact this
procedure was written to replace.

Record which of the four resolved. Anything unresolved is carried as `test evidence: not-checked` or
as an unchecked link in the final block — never silently as a gap. Missing evidence and missing
verification are different findings with different owners.

### 2. Fix the tag pattern before searching for anything

Take the **Requirement tag shape** and write one anchored pattern. **Anchor on the terminator.** A
bare prefix-plus-digits pattern makes every short identifier a prefix of a longer one, so a
requirement numbered 12 collects every hit belonging to 120 and 1234, and every count downstream is
inflated in the direction that looks like good news.

Write the pattern down in the report. A reviewer who cannot see the pattern cannot tell an audit from
a guess, and the pattern is the one thing every number below depends on.

### 3. Inventory the requirements — one Grep to size, one to list

First **Grep** in counting mode over the requirement source. That count is the denominator for
everything that follows and it is also the first test of the pattern from step 2: a count wildly
above or below what the safety manager expects means the pattern is wrong, not that the document is.

Then a second **Grep** listing the identifiers with their line numbers. If the list exceeds what the
remaining budget can cross-check, apply budget rule 7 now — pick the contiguous slice and name its
endpoints — rather than discovering the shortfall at step 7.

Spend at most one 60-line **Read** window here, and only on a genuine oddity: a duplicated
identifier, or a gap in the numbering large enough to suggest a deleted requirement that step 5 will
later surface as an orphan tag.

### 4. Forward link — requirement to test source

**Grep** the same anchored pattern across the test source root, returning file names and line
numbers. This is the forward direction everybody runs, and on its own it is half an audit.

Every identifier in the step 3 inventory that appears in no test file is a **candidate** untraced
requirement — candidate, because the plan (step 6) and the **Waiver record** may still account for
it. Do not report anything as untraced before step 9.

### 5. Backward link — test to requirement

Two **Grep** calls, and this is the direction that gets skipped.

First, Grep the **Tag-in-test convention** keyword across the test tree to collect every tag any test
claims. Any claimed tag absent from the step 3 inventory is an **orphan tag** — a renumbered,
deleted, or mistyped requirement. The test behind it is still being scheduled, still consuming farm
time, and still reporting green against nothing.

Second, Grep the test declaration idiom itself to list the safety tests that exist. A test in that
list carrying no tag at all is `orphan: untagged`: it may be verifying a requirement perfectly well
and simply never say which, which is a documentation defect, not a verification one.

Spend one 60-line **Read** window at the declaration of the first orphan to see whether the tag sits
in a stale file header rather than next to the check it claims to describe.

### 6. The plan in the middle

**Grep** the **Verification plan** for the anchored pattern, and read the test named on each matching
row through the **Plan-to-test key** — the plan and the test source rarely name a test the same way,
which is why that slot exists separately.

Three outcomes, and they must not be merged into one mismatch count:

- a plan row **and** a tagged test → `req chain: full`
- a plan row with no tagged test → `req chain: plan-only`, a commitment nobody implemented
- a tagged test with no plan row → `req chain: test-only`, work done but not documented
- neither, and no waiver → `req chain: broken`

One 60-line **Read** window is available here for the columns around a row whose test name the Grep
could not resolve.

### 7. Evidence — did that test run, and pass, in the run sign-off cites

If step 1 did not resolve the summary, **ask the engineer for the regression summary of the Evidence
run, saved where it can be read from disk**, and pause this step until it arrives. The agent cannot
launch a regression and must not describe what one would have printed.

**Grep** the summary using the **Result-to-test key** — that slot names both the column identifying
the test and the exact strings the verdict column prints, so a pass is recognised by the string the
flow actually emits rather than by the word "pass". Assign `test evidence: pass`, `fail`, or
`absent` when the run has no row for that test at all. Spend one 60-line **Read** window on the
header if the column positions are not obvious from the Grep hits.

`absent` is not `fail` and is much worse in an audit: a failure was seen and judged, an absence was
never seen at all.

### 8. Staleness — compare the right two stamps

Use the spare **Grep** and one **Read** window on the **Revision stamps**. Evidence is
`test evidence: stale` when the **Evidence run** predates the last change to the requirement text
**or** the last change to the test source — either one is enough.

The wrong comparison is the popular one: that the run is recent, or newer than the previous
regression. A test untouched for a year, passing in last night's run, against a requirement reworded
last week, is stale despite both those facts being true.

### 9. Classify each requirement exactly once

One requirement gets one `req chain` value and one `test evidence` value. Three counting errors to
avoid, in the order they occur: a requirement covered by three tests is one traced requirement, not
three; a test covering four requirements is one orphan if its tag is bad, not four; and a requirement
recorded in the **Waiver record** is `req chain: waived`, not `req chain: broken` — verified by
review or analysis is differently traced, not untraced. If the waiver record is not a file on disk,
say the distinction was not made rather than filing every waiver as a gap.

### 10. Write the audit

```
audit scope  : <requirement source path and stamp; plan path; test tree root; evidence run id>
tag pattern  : <the anchored pattern from step 2, verbatim>
requirements : <n> in the source, <m> audited, <k> waived
untraced     : <count, req chain broken plus req chain plan-only>
orphans      : <count, unknown-tag plus untagged>
stale        : <count>
coverage     : <m of n crossed all four links; which slice; what the budget did not reach>
```

Then one row per requirement that is not `req chain: full` with a passing, fresh result:

```
requirement  : <identifier, verbatim as the requirement source spells it>
req chain    : full | plan-only | test-only | broken | waived
plan row     : <plan file and line, or empty>
test         : <test file and line carrying the tag, or empty>
test evidence: pass | fail | absent | stale | not-checked
run id       : <the evidence run, from the Evidence run slot>
owner        : <name from the profile's area-to-owner map, or blank plus candidates>
notes        : <what the next person would otherwise rediscover, including any fact that came from a person rather than a file>
```

The field is `req chain` and not `chain` on purpose. dv-testplan-traceability-review reports a
`plan chain` over verification-plan rows, and the two chain reports are related but not comparable
value-for-value — its `complete` and this field's `full` answer different questions about different
objects. A person mapping one onto the other does it by hand and says that they did.

Then one block per orphan:

```
orphan       : unknown-tag | untagged
test         : <path and line of the declaration>
tag found    : <the tag string verbatim, or empty>
nearest      : <closest identifier in the step 3 inventory, or empty>
action       : <the question for the owner — renumbered, deleted, or mistyped>
```

Leave a field empty rather than filling it plausibly. A blank `owner` is a question someone answers
in one message; an invented one is a wrong answer that reads as right and travels into the safety
case. Post the audit where the profile's **Sign-off** row says the evidence goes.

## Gotchas

- **A tag in a file is not evidence the file checks anything.** Grep matches the string; it cannot
  see that the check below it was commented out, made unconditional, or left behind when the file was
  rewritten. A tag sitting in a stale header block is the commonest false pass in this whole audit,
  and it is why step 5 opens a window at the declaration instead of trusting the hit.
- **Substring collision is the defect that makes an audit look good.** Unanchored, requirement 12
  absorbs every hit for 120 and 1234, so the identifiers most likely to be genuinely untraced are the
  ones most likely to be reported as covered. Anchor on the terminator, always.
- **Bidirectional means two audits, not one audit run twice.** The forward pass finds requirements
  with no test. Only the backward pass finds tests pointing at requirements that no longer exist —
  and those tests pass every night, which is precisely why nobody notices them.
- **A green result proves nothing until you know which run produced it.** A sandbox run, a build with
  the safety mechanism disabled, or one with assertions compiled out all print the same pass string.
  Carry the run identity next to every verdict or the verdict is decoration.
- **Requirements verified by review or analysis are not gaps.** Filing them as gaps floods the list
  and buries the real ones. Only the waiver record separates "no test needed" from "nobody wrote
  one", and where that record is unreadable the honest output is that the two were not distinguished.
- **The plan and the code drift in opposite directions.** A plan row with no test is an unkept
  commitment owned by the verification lead; a tagged test with no plan row is undocumented work
  owned by the block. One count covering both routes the whole list to the wrong person.
- **Staleness is a comparison, and the wrong pair is nearly always chosen.** Compare the evidence run
  against the requirement's last change and the test's last change — not against the previous
  regression, which tells you only that time passed.
- **Derived requirements decompose one to many, and the parent then looks untraced** because it
  carries no tag of its own anywhere in the tree. Decide the rule before counting — parent satisfied
  by its children, or not — and state which rule you applied, because the two produce very different
  totals from identical files.
- **The plan's test name and the summary's test name are usually different strings.** Wrapper tests,
  parameterised variants and per-configuration suffixes mean a literal match finds nothing and every
  requirement reports `test evidence: absent`. Settle the key once from the slot rather than
  rediscovering it per requirement.
- **A percentage with no denominator is the deliverable's failure mode.** "94% traced" out of an
  inventory the audit only crossed a third of is worse than no number, because it survives into the
  assessment pack long after everyone has forgotten which third.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the **anchored tag pattern is printed in the report**, and the requirement count it produced is the
  number the safety manager recognises. Everything below rests on those two lines.
- every untraced requirement names the identifier verbatim, and every orphan names a file and line —
  a gap list with no paths is a hypothesis wearing an audit's clothes.
- `req chain` and `test evidence` are separate verdicts on every row. A row calling a documentation
  gap a verification gap has merged them.
- nothing in the **Waiver record** appears as `req chain: broken`, and nothing missing from that
  record appears as `req chain: waived`.
- the `coverage` line names the slice actually audited, and no percentage appears anywhere without
  that denominator beside it.
- any fact that came from a person rather than a file is attributed in `notes`, and the row resting
  on it is treated as provisional.

A wrong answer typically reports a clean matrix built from an unanchored pattern; counts one
requirement three times because three tests carry its tag; files every review-verified requirement as
a gap; or declares evidence fresh because the regression ran last night, without ever comparing it to
when the requirement was last reworded.

## Done when

Every requirement in the audited slice carries one `req chain` value and one `test evidence` value
backed by a file and a line, every orphan test has a named question attached, and the coverage line
says exactly how much of the list that rests on.
