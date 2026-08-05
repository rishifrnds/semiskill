---
name: dv-regression-triage-routing
description: Turn a night of regression results into ranked failure buckets with an infrastructure-versus-design split, known-issue matches, and one routed owner per bucket. Use when the nightly regression came back with dozens of failures, when you are about to paste several logs into a chat one at a time, or when you need to say which failures block the release and who owns each one.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Nightly Regression Bucketing and Owner Routing
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-02-05
  semiskill-tags: regression, triage, bucketing, routing, known-issues, nightly
---

# Nightly Regression Bucketing and Owner Routing

Forty failing tests are almost never forty bugs. They are usually three or four bugs, one build
break, and a farm hiccup — and the expensive part of the morning is not the debugging, it is finding
out which is which before anyone starts. The habit this replaces is pasting logs into chat one at a
time and matching known issues from memory, which is exactly how the same bug gets filed twice.

The output is a **ranked bucket table**, not a list of failing tests: one row per distinct failure,
each with a signature, a class, a novelty verdict, a rank, and an owner.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Regression summary | [[FILL: where the nightly summary lands — the per-test status table, not the logs]] | DV infra |
| Summary format | [[FILL: what a pass row and a fail row look like, and which columns hold test name, seed and log path]] | DV infra |
| Infra markers | [[FILL: the strings that mean our environment broke — licence, disk, host, queue, build]] | DV infra |
| Known-issue list | [[FILL: where our known-issue list lives and how each entry is keyed]] | DV lead |
| Area to owner map | [[FILL: which block or area maps to which owner, and where that map is written down]] | verification lead |
| Blocking rule | [[FILL: what makes a bucket release-blocking here — gating test, milestone, coverage dependency]] | verification lead |
| Baseline regression | [[FILL: which prior regression is the comparison baseline when deciding what is new]] | DV lead |
| Report destination | [[FILL: where the morning triage summary is posted and in what format]] | your mentor |

**If a slot is unfilled, stop and ask. Do not guess.** A guessed owner sends a real bug to the wrong
person for a day, and a guessed summary path sends this whole procedure down the wrong file.

## Retrieval budget — read this before opening anything

The input is the regression **summary**. The logs are evidence, sampled under a cap. A night of
results is hundreds of megabytes; the summary is a few thousand lines at worst.

1. **Glob** for the summary first. If it cannot be located, stop and ask for the path. Do not fall
   back to opening logs — reading logs to reconstruct a summary burns the entire budget on step one.
2. **Read** the summary in bounded windows. If it exceeds roughly 1500 lines, **Grep** it for the
   fail marker instead and Read only around the hits.
3. Per failing test the log budget is **two Greps and one windowed Read of about 80 lines** — markers,
   earliest hit's line number, the window before it. Enough to sign a failure, not enough to debug
   one, and debugging is a different task.
4. Cap the whole exercise at **15 logs opened**. Spend the budget first on failing tests whose
   summary lines look unlike anything already signed.
5. Stop early when three consecutive logs fold into buckets that already exist. Sign whatever remains
   from summary lines alone and mark those signatures provisional.
6. If any single **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it before
   reading anything.
7. State the coverage — "signed 11 of 47 from logs, 36 from summary lines only". An unstated
   shortcut is far worse than a stated one.

## Procedure

### 1. Locate the summary and build the failing-test list

Use **Glob** against the summary slot, then **Read** it. Extract, per failing test, the test name,
the seed or run identifier, the log path, and the status string. Note the totals — passed, failed,
and anything the summary reports as not started, killed, or skipped. If the summary distinguishes
"failed" from "did not run", carry that distinction all the way through. A test that never started
did not fail.

### 2. Decide first whether this is one environmental event

Before signing anything, use **Grep** on the summary for the infra markers slot. Ask three questions:

- Did the compile or build step fail? If it did, every downstream test is **unrun**, not failing.
- Did a very high fraction of tests fail, including tests in unrelated blocks that pass every night?
- Do the failures share a marker that names a host, a licence, a queue, or a filesystem?

Two or three yeses means one bucket, class `infrastructure`, and an empty design queue for the night.
Say that plainly in one paragraph and stop the ranking — producing forty design buckets from one
licence outage is the most common way this task is done badly.

### 3. Sign each failure individually, before any grouping

For each failing test inside the budget, use **Grep** on its log for the failure markers, take the
**lowest** line number, then one windowed **Read** starting about 60 lines before it.

Produce one failure signature per failing test, following `_shared/failure-signature-schema.md`
exactly — same field order, same normalisation rules. Every field must be traceable to text that was
actually in the log; write `?` for anything that is not.

Do not group yet. Grouping before signing is how two different bugs that print the same message get
merged into one bucket and one of them is lost for a week.

### 4. Group by exact signature

Bucket signatures that are **character-for-character identical**. Nothing else merges. If two
signatures differ only in `where`, they stay separate — record each as the other's neighbour so the
owner can decide.

If a bucket is enormous and its `what` is generic, the normalisation was too aggressive — push
`where` one level deeper and regroup rather than accept a bucket that explains nothing.

### 5. Split infrastructure out before ranking

Classify every bucket as `design`, `infrastructure`, or `unknown`. Infrastructure buckets leave the
design queue immediately and carry their victims with them — tests killed by a farm or build problem
are unrun and their results are void, not evidence.

`unknown` is an allowed and useful answer. A bucket whose log shows no testbench activity at all is
not a design bug just because nobody can name the environment problem yet.

### 6. Rank by blast radius and novelty, not by count

Order the remaining design buckets on these keys, highest first:

1. Blocks everything else — a build, elaboration, or shared-component failure that prevents other
   tests from producing a verdict.
2. Hits a release-gating test, per the blocking-rule slot.
3. Novel — the signature does not appear in the baseline regression.
4. Blast radius — the number of **distinct areas** the bucket touches, not the number of tests.

Test count is the weakest signal available. One bug found by two hundred randomised seeds is one bug,
and the two hundred seeds mean it is easy to reproduce, not that it is important.

### 7. Match against the known-issue list, not memory

Use **Grep** on the known-issue file for the `where` and the distinctive fragment of `what` from each
bucket. Compare exactly. Mark the bucket `known-issue <id>` only when the recorded signature and the
bucket signature are the same string.

If the known-issue slot is unfilled, mark every bucket `novelty unknown` and say so. Claiming "new"
without a baseline is an invented fact.

### 8. Route each bucket to an owner

Route on the signature's `where` field via the area-to-owner map — never on the test name. Test names
follow the testbench; the bug usually lives in a block the test merely exercises.

If `where` is a testbench component rather than design hierarchy, the owner is that component's DV
owner. If the map yields nothing, leave the owner blank, list the candidates it makes plausible, and
ask. A blank owner gets fixed in one message; a wrong owner costs a day.

### 9. Draft the report

```
regression : <name, date, build tag, all taken from the summary>
totals     : <pass> pass / <fail> fail / <unrun> unrun of <total>
verdict    : environmental | mixed | design
coverage   : signed <n> of <fail> failures from logs
buckets    : <count>
```

Then one block per bucket, in rank order:

```
bucket    : B1
signature : <phase>|<kind>|<where>|<what>
class     : design | infrastructure | unknown
tests     : <count> across <n> areas — <up to five test names, then "+k more">
novelty   : new | seen-in-baseline | known-issue <id> | unknown
rank      : <n> because <blocking / gating / novel / breadth>
owner     : <name from the area map, or blank plus candidates>
evidence  : <log path>, line <n>
```

Leave any field blank rather than filling it plausibly. A blank `owner` is a question; an invented
one is a wrong answer that looks right.

### 10. Hand back what needs a machine

State the handoffs explicitly at the end of the report rather than implying them:

- ask the engineer to rerun bucket B1's representative test with waves enabled and paste the tail of
  the new log
- ask the engineer to confirm the build tag matches the baseline and paste the summary header
- ask the infra owner to confirm the licence or host event and paste the queue status

## Gotchas

- **A build failure is one bucket, not two hundred.** Every test downstream of it is unrun. Counting
  them as failures inflates the design queue and hides the single line that matters.
- **Grouping before signing loses bugs.** Two scoreboards printing the same MISCOMPARE text are two
  bugs; they only look alike until `where` is filled in.
- **Timeouts are the most deceptive bucket.** A farm slowdown and a real hang look identical in the
  summary. Distinguish by whether the log shows testbench progress right up to its final line.
- **The same signature in several blocks after a shared-file change is one bug.** Check whether the
  `where` values descend from a common base class, package, or VIP before filing several reports.
- **One failing seed is not a flaky test.** It may be the only seed that reached the corner. Flaky
  requires the same test both passing and failing on the same build.
- **Summary status and log verdict disagree when a job is killed.** A wallclock kill often shows as a
  fail with a clean log. Trust the log's last lines over the summary's status column.
- **Known-issue matching is exact string comparison.** "This looks like the DMA thing from last
  month" is a memory, not a match, and it is precisely how duplicate bugs get filed.
- **Novelty needs a baseline.** Without the baseline slot filled, every bucket is `unknown`, and the
  ranking falls back on blast radius alone. Say that rather than quietly ranking as if it were known.

## Human verification — what a wrong answer looks like

Before sending the report, check:

- the bucket count is far below the failure count — if they are nearly equal, grouping did not happen
- no signature carries a seed, a timestamp, an absolute path, or a beat index
- the night's build status is reflected — a green table of design buckets on a night the build broke
  is wrong before any of it is read
- every `known-issue` mark carries an entry id from the list, not a recollection
- every owner name appears in the area map; none was inferred from a test name
- ranks are justified by breadth or gating, not by descending test count
- the coverage line is present and honest about how many logs were actually opened

A wrong answer usually looks like a tidy table of twenty buckets, ranked by test count with an owner
confidently named for each — produced on a night when one licence server went down and nothing else was wrong.

## Done when

The table can be posted as-is and each named owner has one bucket to look at, or one question to answer.
