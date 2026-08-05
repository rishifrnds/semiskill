---
name: dv-regression-triage-routing
description: Turn a night of regression results into ranked failure buckets with an infrastructure-versus-design split, known-issue matches, and one routed owner per bucket. Use when the nightly regression came back with dozens of failures, when you are about to paste several logs into a chat one at a time, or when you need to say which failures block the release and who owns each one.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Nightly Regression Bucketing and Owner Routing
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-05-19
  semiskill-tags: regression, triage, bucketing, routing, known-issues, nightly
---

# Nightly Regression Bucketing and Owner Routing

Forty failing tests are almost never forty bugs. They are usually three or four bugs, one build
break, and a farm hiccup — and the expensive part of the morning is not the debugging, it is finding
out which is which before anyone starts. The habit this replaces is pasting logs into chat one at a
time and matching known issues from memory, which is exactly how the same bug gets filed twice.

The output is a **ranked bucket table**, not a list of failing tests: one row per distinct failure,
each with a signature, a class, a novelty verdict, a rank, and an owner.

## When to use something else

This one is for a night of results. For a single failing log, use `dv-sim-log-first-error` — it goes
deeper into one log than the sampling budget here allows. Once you already have a signature and want
the smallest run that still reproduces it, use `dv-minimal-reproducer`. Loading the wrong one of the
three feels like repetition; they differ in how much of one log they are willing to spend.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Regression summary | [[FILL: where the nightly summary lands — the per-test status table, not the logs]] | DV infra |
| Summary format | [[FILL: what a pass row and a fail row look like, and which columns hold test name, seed and log path]] | DV infra |
| Fatal markers | [[FILL: the strings our logs print on a real failure, beyond UVM_ERROR and UVM_FATAL]] | DV lead |
| Pass marker | [[FILL: the string a clean run prints at the end]] | DV lead |
| Infra markers | [[FILL: the strings that mean our environment broke — licence, disk, host, queue, build]] | DV infra |
| Known-issue list | [[FILL: where our known-issue list lives, whether it is a file on disk or a tracker or page that only a human can query, and how each entry is keyed]] | DV lead |
| Area to owner map | [[FILL: which block or area maps to which owner, and where that map is written down]] | verification lead |
| Blocking rule | [[FILL: what makes a bucket release-blocking here — gating test, milestone, coverage dependency]] | verification lead |
| Baseline regression | [[FILL: which prior regression is the comparison baseline, and whether its summary is still on disk]] | DV lead |
| Report destination | [[FILL: where the morning triage summary is posted and in what format]] | your mentor |

Fatal markers, Pass marker, Infra markers and the known-issue list are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than filling them in again here. Note that
`_shared/failure-signature-schema.md` separately asks for **our message prefixes**, which is the set
used when *normalising* a signature; it overlaps with Fatal markers but is not the same list, so
check both rather than copying one into the other. A signature normalised against one set of prefixes
will not match a table built against another.

**If a slot is unfilled, stop and ask. Do not guess a convention.** A guessed owner sends a real bug
to the wrong person for a day, and a guessed summary path sends this whole procedure down the wrong
file.

## Retrieval budget — read this before opening anything

The input is the regression **summary**. The logs are evidence, sampled under a cap. A night of
results is hundreds of megabytes; the summary is a few thousand lines at worst.

1. **Grep, Read and Glob work on files on disk.** They cannot search text pasted into a chat. If the
   night's results arrived as pasted text, get the path that text came from, or ask for it to be
   saved to a file and be given that path, before anything is Grepped. If neither is possible, the
   only evidence available is what is on screen — say so, and mark everything derived from it
   unverified.
2. **Glob** for the summary first. If it cannot be located, stop and ask for the path. Do not fall
   back to opening logs — reading logs to reconstruct a summary burns the entire budget on step one.
3. **Read** the summary in bounded windows. If it exceeds roughly 1500 lines, **Grep** it for the
   fail-row pattern from the summary-format slot instead, and Read only around the hits.
4. Per failing test the log budget is **two Greps and one windowed Read of about 80 lines** — one
   Grep for the markers (fatal and pass together), one to fix the earliest fatal hit's line number,
   then the window before it. Enough to sign a failure, not enough to debug one, and debugging is a
   different task.
5. Cap the whole exercise at **15 logs opened**. At full budget that is 45 tool calls before any of
   the summary work — already a full session's attention. Spend it deliberately: on failing tests
   whose summary lines look unlike anything already signed.
6. Stop opening logs when three consecutive logs fold into buckets that already exist. **The
   failures you did not open are not signed.** Never build a signature out of a summary row: a row
   carries a test name and a status, so `where` and `what` would both be `?` for every one of them,
   and step 4's exact matching would collapse the entire tail into a single bucket that explains
   nothing. Count them and group them by status string instead — step 5.
7. If any single **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it
   before reading anything.
8. State the coverage — "signed 11 of 47 failures from logs; 36 unsigned, grouped by summary status
   only". An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Locate the summary and build the failing-test list

If the results were pasted rather than pointed at, resolve that before anything else — budget rule 1.

Use **Glob** against the summary slot, then **Read** it. Extract, per failing test, the test name,
the seed or run identifier, the log path, and the status string. Note the totals — passed, failed,
and anything the summary reports as not started, killed, or skipped. If the summary distinguishes
"failed" from "did not run", carry that distinction all the way through. A test that never started
did not fail.

Many summaries have no not-started category at all. If ours does not, write `unrun not reported`
rather than working it out by subtraction. If the summary states a total larger than pass plus fail,
record the difference on its own line as `unaccounted (derived)` and do not call it `unrun` — a
computed number sitting in a field that everyone reads as a measured one is how a triage table starts
lying.

### 2. Decide first whether this is one environmental event

Before signing anything, use **Grep** on the summary for the infra markers slot. Ask three questions:

- Did the compile or build step fail? If it did, every downstream test is **unrun**, not failing.
- Did a very high fraction of tests fail, including tests in unrelated blocks that pass every night?
- Do the failures share a marker that names a host, a licence, a queue, or a filesystem?

Two or three yeses means one bucket, class `infrastructure`, and an empty design queue for the night.
Say that plainly in one paragraph and stop the ranking — producing forty design buckets from one
licence outage is the most common way this task is done badly.

### 3. Sign each failure individually, before any grouping

For each failing test inside the budget, use **Grep** on its log for the fatal markers and the pass
marker, take the **lowest** fatal line number, then one windowed **Read** starting about 60 lines
before it.

If the log carries the pass marker and no fatal marker while the summary calls the test failed, the
run reached its own end and something after it went wrong — the job was killed, the result was lost,
or the harness misread it. That is `infrastructure`, and it is the case the status column gets wrong
most often.

Produce one failure signature per failing test, following `_shared/failure-signature-schema.md`
exactly — same field order `<phase>|<kind>|<where>|<what>`, same normalisation rules. Every field
must be traceable to text that was actually in the log; write `?` for anything that is not. A
signature that ends up with `?` in both `where` and `what` cannot be bucketed against anything —
carry that test into the unsigned remainder in step 5 instead of letting it merge.

Do not group yet. Grouping before signing is how two different bugs that print the same message get
merged into one bucket and one of them is lost for a week.

### 4. Group by exact signature

Bucket signatures that are **character-for-character identical**. Only log-derived signatures are
bucketed here, and nothing else merges. If two signatures differ only in `where`, they stay separate
— record each as the other's neighbour so the owner can decide.

If a bucket is enormous and its `what` is generic, the normalisation was too aggressive — push
`where` one level deeper and regroup rather than accept a bucket that explains nothing.

### 5. Account for the failures nobody opened

Every failing test not opened under the budget is **unsigned**. It gets no signature, no bucket, no
rank and no owner.

Group the unsigned remainder by its summary status string, verbatim as the summary prints it, and
report each group as a count against that string. These groups never merge with a signed bucket: a
status column is a claim about a test, not evidence about a failure, and it is wrong exactly in the
case that matters most — the killed job with a clean log.

If an unsigned group is large, or its status string is unlike anything signed, that is the first
place to spend the next session's budget. Say which one.

### 6. Split infrastructure out before ranking

Classify every bucket as `design`, `infrastructure`, or `unknown`. Infrastructure buckets leave the
design queue immediately and carry their victims with them — tests killed by a farm or build problem
are unrun and their results are void, not evidence.

`unknown` is an allowed and useful answer. A bucket whose log shows no testbench activity at all is
not a design bug just because nobody can name the environment problem yet.

### 7. Rank by blast radius and novelty, not by count

Order the remaining design buckets on these keys, highest first:

1. Blocks everything else — a build, elaboration, or shared-component failure that prevents other
   tests from producing a verdict.
2. Hits a release-gating test, per the blocking-rule slot.
3. Novel — the signature does not appear in the baseline regression.
4. Blast radius — the number of **distinct areas** the bucket touches, not the number of tests.

Test count is the weakest signal available. One bug found by two hundred randomised seeds is one bug,
and the two hundred seeds mean it is easy to reproduce, not that it is important.

Key 3 needs the baseline summary to be filled in *and* still on disk. If it is neither, drop the key
and rank on the other three, and say the ranking had no novelty input.

### 8. Match against the known-issue list, not memory

What you can do depends on what the known-issue slot resolved to:

- **A file on disk.** Use **Grep** on it for the `where` and for the distinctive fragment of `what`
  from each bucket. Compare exactly. Mark the bucket `known-issue <key>` using whatever key that list
  itself uses — the slot records how entries are keyed, so use that, and do not assume entries carry
  numeric ids.
- **A tracker query, a page, or anything else not on disk.** This procedure cannot reach it: Read,
  Grep and Glob open files, and this skill has no network. Matching becomes a handoff — put each
  bucket's signature in the report and ask the person who can query the list to compare them. Until
  that answer comes back, every bucket is `novelty unknown`.
- **Unfilled.** Mark every bucket `novelty unknown` and say so. Claiming "new" without a list to
  check against is an invented fact.

### 9. Route each bucket to an owner

Route on the signature's `where` field via the area-to-owner map — never on the test name. Test names
follow the testbench; the bug usually lives in a block the test merely exercises.

If `where` is a testbench component rather than design hierarchy, the owner is that component's DV
owner. If the map yields nothing, leave the owner blank, list the candidates it makes plausible, and
ask. A blank owner gets fixed in one message; a wrong owner costs a day.

### 10. Draft the report

```
regression : <name, date, build tag, all taken from the summary>
totals     : <pass> pass / <fail> fail / <unrun, or "unrun not reported"> of <total>
verdict    : environmental | mixed | design
coverage   : signed <n> of <fail> failures from logs; <m> unsigned
buckets    : <count>
```

Then one block per bucket, in rank order:

```
bucket    : B1
signature : <phase>|<kind>|<where>|<what>
class     : design | infrastructure | unknown
tests     : <count> across <n> areas — <up to five test names, then "+k more">
novelty   : new | seen-in-baseline | known-issue <key> | unknown
rank      : <n> because <blocking / gating / novel / breadth>
owner     : <name from the area map, or blank plus candidates>
run id    : <the representative run, from the summary's test and seed columns>
log       : <that run's log path, and the line range worth reading>
```

Then one block for everything that was never opened:

```
unsigned  : <m> failures, grouped by summary status only — not signatures
  "<status string, verbatim>" : <count> — <up to five test names, then "+k more">
```

Leave any field blank rather than filling it plausibly. A blank `owner` is a question; an invented
one is a wrong answer that looks right.

### 11. Hand back what needs a machine or another person

State the handoffs explicitly at the end of the report rather than implying them:

- ask the engineer to rerun bucket B1's representative test with waves enabled and paste the tail of
  the new log — and to give the path it was written to, so it can be Grepped
- ask the engineer to confirm the build tag matches the baseline and paste the summary header
- ask the infra owner to confirm the licence or host event and paste the queue status
- if the known-issue list is not a file on disk, ask its owner to compare the listed signatures and
  send back the matching entry keys

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
  fail with a clean log. Trust the log's last lines over the summary's status column — which is
  precisely why the failures whose logs were never opened stay unsigned instead of being signed from
  the column this bullet tells you not to trust.
- **Known-issue matching is exact string comparison.** "This looks like the DMA thing from last
  month" is a memory, not a match, and it is precisely how duplicate bugs get filed.
- **Novelty needs a reachable baseline.** If the baseline slot is unfilled, or the baseline summary
  is no longer on disk, every bucket is `unknown` and the ranking falls back on blast radius alone.
  Say that rather than quietly ranking as if novelty were known.

## Human verification — what a wrong answer looks like

Before sending the report, check:

- the bucket count is far below the failure count — if they are nearly equal, grouping did not happen
- no signature carries a seed, a timestamp, an absolute path, or a beat index
- no signature has `?` in both `where` and `what` — that test belongs in the unsigned block
- signed plus unsigned equals the failure total, and the coverage line says both numbers
- no unsigned failure appears in a ranked bucket, and no unsigned group carries an owner
- the night's build status is reflected — a green table of design buckets on a night the build broke
  is wrong before any of it is read
- every `known-issue` mark carries the entry key exactly as the list records it, not a recollection
- every owner name appears in the area map; none was inferred from a test name
- ranks are justified by breadth or gating, not by descending test count

A wrong answer usually looks like a tidy table of twenty buckets, ranked by test count with an owner
confidently named for each — produced on a night when one licence server went down and nothing else
was wrong. The second-most common wrong answer is a table where the last thirty rows all share one
signature, because they were signed from the status column instead of from a log.

## Done when

The table can be posted as-is, each named owner has one bucket to look at or one question to answer,
and the failures nobody opened are visible as a stated count rather than hidden inside a bucket.
