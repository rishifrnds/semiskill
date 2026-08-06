---
name: dv-regression-triage-routing
description: Turn a night of regression results into ranked failure buckets with an infrastructure-versus-design split, known-issue matches, and one routed owner per bucket. Use when the nightly regression came back with dozens of failures, when you are about to paste several logs into a chat one at a time, or when you need to say which failures block the release and who owns each one.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Nightly Regression Bucketing and Owner Routing
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-06-04
  semiskill-tags: regression, triage, bucketing, routing, known-issues, nightly
---

# Nightly Regression Bucketing and Owner Routing

Forty failing tests are almost never forty bugs: some are one failure counted many times, some are one
environment problem wearing forty test names, and a few are real. The habit this replaces is pasting logs into
chat one at a time and matching known issues from memory — which is how the same bug gets filed twice. The
output is a **ranked bucket table**: one row per distinct failure, with a signature, a class, a baseline
comparison, a known-issue verdict, a rank and an owner.

## When to use something else

For a single failing log, use `dv-sim-log-first-error` — it goes deeper into one log than the sampling budget
here allows. For the smallest run that still reproduces a signature you have, use `dv-minimal-reproducer`.

## Fill this in for our team

Six facts this procedure spends are pack-wide. They live **once**, in `_shared/team-profile.md` — two copies
of the owner map drift apart silently, and nothing here can tell you which one is stale.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Regression summary** — where it lands, *and its format* | steps 1 and 3; it is the whole input |
| **Fatal markers** | step 2, signing each log that gets opened |
| **Pass marker** | step 2, catching the killed job with a clean log |
| **Infra markers** | step 1, the one-environmental-event check |
| **Known-issue list** | step 6 |
| **Area to owner map** | step 6 — including *what it is keyed on*, which changes the lookup |

Three more facts are specific to this skill:

| Slot | What to fill in | Who knows |
|---|---|---|
| Blocking rule | [[FILL: what makes a bucket release-blocking here — gating test, milestone, coverage dependency]] | verification lead |
| Baseline regression | [[FILL: which prior regression is the comparison baseline, and whether its summary is still on disk]] | DV lead |
| Report destination | [[FILL: where the morning triage summary is posted and in what format]] | your mentor |

Two slots in `_shared/failure-signature-schema.md` sit close to those facts. Its **Our message prefixes** is
used when *normalising* a signature — it overlaps with Fatal markers but is not the same list, so check both.
Its **Where known signatures are recorded** is the Known-issue list fact under a second name, so the profile's
answer fills it; the Pass marker has no counterpart there. **If a fact or a slot is unfilled, stop and ask** —
a guessed owner sends a real bug to the wrong person for a day.

## Retrieval budget — read this before opening anything

The input is the regression **summary**. The logs are evidence, sampled under a cap.

1. **Grep, Read and Glob work on files on disk.** They cannot search text pasted into a chat. If the results
   arrived as pasted text, get the path they came from, or ask for them to be saved and be given that path,
   before anything is Grepped. If neither is possible, say so and mark every claim derived from it unverified.
2. **Glob** for the summary first — one call. If it cannot be located, stop and ask; do not fall back to
   opening logs, because reconstructing a summary from logs burns the whole budget on step one.
3. **The summary costs at most three windowed Reads and two Greps.** Read it in windows, not whole; past
   roughly 1500 lines **Grep** it for the fail-row pattern recorded with the profile's Regression summary
   fact and Read only around the hits. The second Grep is step 1's infra-marker sweep.
4. Per failing test the log budget is **one Grep and one windowed Read of about 80 lines**. The Grep covers
   the fatal and pass markers together and reports line numbers, so the earliest fatal line is read off that
   same output instead of costing a second call; the Read is the window before it. Two calls per log.
5. Cap the logs at **15 opened**, which is 30 calls. The whole ledger: 6 on tonight's summary (one Glob,
   three Reads, two Greps); 2 on the baseline summary (step 5 key 3 — one Glob to find it, one Grep whose
   pattern is the alternation of the buckets' representative test names; zero when there is no baseline); 30
   on logs; 20 Greps on known-issue matching; 1 Read of the owner map. **Fifty-nine calls at full spend.**
6. **Known-issue matching is the one cost that grows after the logs are shut.** Step 6 spends up to **two
   Greps per bucket** — one for `where`, one for the distinctive fragment of `what` — and only when that list
   resolved to a file on disk; if it did not, this line of the budget is zero, because no Grep can reach it.
   Cap it at **20 Greps**: past that, match in rank order, stop, and name the buckets left uncompared.
7. Stop opening logs when three consecutive logs fold into buckets that already exist. **The failures you did
   not open are not signed.** Never build a signature out of a summary row: a row carries a test name and a
   status, so `where` and `what` would both be `?`, and step 3's exact matching would collapse the whole tail
   into one bucket that explains nothing. If any single **Grep** returns over about 200 hits, narrow it.
8. State the coverage — "signed 11 of 47 failures from logs; 36 unsigned, grouped by summary status only".

## Procedure

### 1. Read the summary, list the failures, and rule out one environmental event

If the results were pasted rather than pointed at, resolve that first — budget rule 1. Use **Glob** against
the profile's Regression summary fact, then **Read** it against the format recorded alongside it. Extract per
failing test: test name, seed or run identifier, log path, status string; note the totals, including anything
reported as not started, killed or skipped. Carry any "failed" versus "did not run" distinction through — a
test that never started did not fail. With no not-started category, write `unrun not reported` rather than
subtracting; and if the stated total exceeds pass plus fail, put the difference on the report's `unaccounted`
line, labelled derived as that line's shape requires, never in the unrun position of `totals`. A computed
number in a field everyone reads as measured is how a triage table starts lying.

Then, before signing anything, **Grep** the summary for the profile's Infra markers — the second summary Grep.
Did the compile or build step fail (if so every downstream test is **unrun**, not failing); did a very high
fraction fail, including blocks that pass every night; do the failures share a marker naming a host, a licence,
a queue or a filesystem? Two or three yeses means one bucket, `class: infrastructure`, `verdict: environmental`,
an empty design queue and no ranking — forty design buckets out of one licence outage is the classic error.

### 2. Sign each failure individually, before any grouping

For each failing test inside the budget, **Grep** its log for the profile's Fatal and Pass markers, take the
**lowest** fatal line number off that output, then one windowed **Read** starting about 60 lines before it. A
log with the pass marker and no fatal marker, on a test the summary calls failed, is `infrastructure`: the job
was killed or the result lost after the run ended — the case the status column gets wrong most often.

Produce one signature per failing test following `_shared/failure-signature-schema.md` exactly — same field
order `<phase>|<kind>|<where>|<what>`, same normalisation rules. Every field must trace to log text; write `?`
for anything that does not, and send a signature with `?` in both `where` and `what` to the unsigned remainder.
Do not group yet — grouping before signing merges two bugs that print one message and loses one for a week.

### 3. Group by exact signature, then account for what nobody opened

Bucket signatures that are **character-for-character identical**; nothing else merges. If two differ only in
`where` they stay separate — write each bucket's id in the other's `notes` field as its neighbour, so the owner
can decide. If a bucket is enormous and its `what` generic, push `where` one level deeper and regroup.

Every failing test not opened is **unsigned** — no signature, no bucket, no rank, no owner. Group the remainder
by its summary status string, verbatim, and count each group; these never merge with a signed bucket, because a
status column is a claim about a test, not evidence about a failure. Say which group to open first next time.

### 4. Classify each bucket, then set the night's verdict

Classify every bucket `design`, `infrastructure` or `unknown`. Infrastructure buckets leave the design queue
and carry their victims: tests killed by a farm or build problem are unrun, their results void. `unknown` is
useful — a log showing no testbench activity is not a design bug just because nobody can name the problem yet.

Then set the header's `verdict` from the classes now present, first rule that applies: every bucket
`infrastructure` → `verdict: environmental`, the step 1 outcome and the only case where the design queue is
genuinely empty; no bucket `infrastructure` → `verdict: design`; otherwise at least one `infrastructure` bucket
**and** at least one that is not → `verdict: mixed`, the ordinary night and the one people forget to say out
loud, because both queues have work. An `unknown` bucket counts design-side until somebody shows otherwise.

### 5. Rank by blocking power and blast radius, not by count

Order the remaining design buckets on these keys, highest first:

1. Blocks everything else — a build, elaboration or shared-component failure that stops other tests producing
   a verdict.
2. Hits a release-gating test, per the blocking-rule slot.
3. Not already failing in the baseline regression. **Glob** for the baseline summary, then **Grep** it for the
   buckets' representative test names — compare on the **test name and its status string**, never the
   signature, because a summary holds no log text. Set `vs-baseline` from that row: there and failing →
   `also-failed-in-baseline`; there and passing → `test-not-failing-in-baseline`; the name absent altogether →
   `not-checked`, since a baseline that never ran the test says nothing. The middle value is weaker than "new".
4. Blast radius — the number of **distinct areas** touched, not the number of tests.

Test count is the weakest signal: one bug found by two hundred seeds is one bug. Key 3 needs the baseline named
*and* on disk; if either is missing, drop it, rank on keys 1, 2 and 4, mark all `vs-baseline: not-checked`, say so.

### 6. Match against the known-issue list, then route each bucket

Matching depends on what the profile's Known-issue list fact resolved to. **A file on disk**: **Grep** it for
the `where`, and for the distinctive fragment of `what`, from each bucket — two Greps per bucket, inside budget
rule 6's cap. Compare exactly. An exact match marks the bucket `known-issue <key>`, using whatever key that
list itself uses; the profile records how entries are keyed, so use that rather than assuming numeric ids. If
both Greps return nothing, or return entries that do not compare exactly, mark it `known: not-matched` — a
statement about this list today, not a claim that the bug is new. Buckets past the 20-Grep cap were never
compared: leave their `known` blank and name them in the report as uncompared. **Anything not on disk — a
tracker query, a page — or unfilled**: Read, Grep and Glob open files and this skill has no network, so every
bucket is `known: list-not-readable` and matching becomes a handoff — put the signatures in the report and ask
whoever can query the list. Claiming "new" with no list to check against is an invented fact.

Then **Read** the profile's Area to owner map once — it is a table, not a log — and route the whole bucket
table from that one read, on whatever the profile says the map is keyed on. It is not always design hierarchy,
and the key decides the lookup. **Keyed on design hierarchy**: look up the signature's `where`, then its parent
levels until one matches. **Keyed on directory**: resolve `where` to the source directory named in the log
window step 2 already read, and look that up. **Keyed on test name**: the one case where a test name is the
legal key — look it up for the bucket's representative test and record in `notes` that routing was keyed on the
test name, because such a map names whoever owns the *test* while the bug often lives in a block the test
merely exercises. Never route on a test name against a hierarchy-keyed map, and never invent a hierarchy path
for a name-keyed one. If the map yields nothing, leave the owner blank, list the candidates, and ask.

### 7. Draft the report and state the handoffs

```
regression  : <name, date, build tag, all taken from the summary>
totals      : <pass> pass / <fail> fail / <unrun, or "unrun not reported"> of <total>
unaccounted : <count>, derived as total minus pass minus fail — or "none"
verdict     : environmental | mixed | design
coverage    : signed <n> of <fail> failures from logs; <m> unsigned; <b> buckets
unsigned    : by summary status only, never signatures — "<status, verbatim>" <count>, ...
--- then one block like this per bucket, in rank order ---
bucket      : B1
signature   : <phase>|<kind>|<where>|<what>
class       : design | infrastructure | unknown
tests       : <count> across <n> areas — <up to five test names, then "+k more">
vs-baseline : also-failed-in-baseline | test-not-failing-in-baseline | not-checked
known       : known-issue <key> | not-matched | list-not-readable
rank        : <n> because <blocking / gating / baseline / breadth>
owner       : <name from the area map, or blank plus candidates>
run id      : <the representative run, from the summary's test and seed columns>
log         : <that run's log path, and the line range worth reading>
notes       : <neighbour buckets from step 3; the owner map's key if it was the test name; anything else the next person would otherwise rediscover>
```

`vs-baseline` avoids the bare name `baseline`, which `dv-minimal-reproducer` uses for the original run's *cost*.
Leave any field blank rather than filling it plausibly — a blank owner gets fixed in one message, a wrong one
costs a day. Post it where the report-destination slot says, in that slot's shape; if unfilled, ask. Then:

- ask the engineer to rerun bucket B1's representative test with waves on, and give the new log's path
- ask the infra owner to confirm any licence or host event, and the engineer to confirm the build tag
- if the known-issue list is not on disk, ask its owner to match the listed signatures and send the keys

## Gotchas

- **A build failure is one bucket, not two hundred.** Every test downstream of it is unrun. Counting them as
  failures inflates the design queue and hides the single line that matters.
- **Grouping before signing loses bugs.** Two scoreboards printing the same MISCOMPARE text are two bugs;
  they only look alike until `where` is filled in.
- **Timeouts are the most deceptive bucket.** A farm slowdown and a real hang look identical in the summary.
  Distinguish by whether the log shows testbench progress right up to its final line.
- **The same signature in several blocks after a shared-file change is one bug.** Check whether the `where`
  values descend from a common base class, package or VIP before filing several reports.
- **One failing seed is not a flaky test.** It may be the only seed that reached the corner. Flaky needs the
  same test both passing and failing on the same build.
- **Summary status and log verdict disagree when a job is killed.** A wallclock kill often shows as a fail with
  a clean log; trust the log's last lines — which is why unopened failures stay unsigned instead of signed.
- **Known-issue matching is exact string comparison**, and `not-matched` (the list was read, no entry matched)
  is not `list-not-readable` (nobody checked). "Looks like the DMA thing last month" is a memory, not a match.
- **A missing baseline costs exactly one rank key and nothing else.** Every bucket becomes
  `vs-baseline: not-checked`. It does not make the bucket `class: unknown` — `class` is a verdict about what the
  log showed — and it does not collapse the ranking: keys 1, 2 and 4 still rank in that order.

## Human verification — what a wrong answer looks like

Before sending the report, check:

- the bucket count is far below the failure count — if they are nearly equal, grouping did not happen — and
  ranks are justified by breadth or gating, not by descending test count
- no signature carries a seed, a timestamp, an absolute path or a beat index, and none has `?` in both
  `where` and `what` — that test belongs on the unsigned line
- signed plus unsigned equals the failure total, no unsigned failure appears in a ranked bucket, and no
  unsigned group carries an owner
- the header `verdict` matches the classes actually in the table: `mixed` whenever both an infrastructure
  bucket and a non-infrastructure bucket are present, never `design` out of habit on a night that also had a
  farm problem; and any `unaccounted` count is labelled derived, never sitting in the unrun position
- every `known-issue` mark carries the entry key exactly as the list records it, and no bucket reads
  `not-matched` unless a readable list was actually Grepped for that bucket
- every owner name appears in the area map, and the lookup used the key the profile says that map is keyed on
  — an owner inferred from a test name against a hierarchy-keyed map is a wrong answer
- every bucket's `class` is justified by what its log showed, never by an unreachable baseline or an unfindable
  owner; and every bucket carries a `vs-baseline` value, `not-checked` whenever no baseline was readable

A wrong answer usually looks like a tidy table of twenty buckets, ranked by test count with an owner
confidently named for each — produced on a night when one licence server went down and nothing else was
wrong. The second-most common is a table whose last thirty rows share one signature, because they were signed
from the status column instead of from a log.

## Done when

The table can be posted as-is, each named owner has one bucket to look at or one question to answer, and the
failures nobody opened are visible as a stated count rather than hidden inside a bucket.
