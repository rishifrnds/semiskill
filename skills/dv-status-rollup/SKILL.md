---
name: dv-status-rollup
description: Assemble regression, coverage and bug data from several blocks into one weekly status held at a consistent altitude, with the decisions it asks for named. Use when the weekly verification status is due, when every block reports in a different shape and nothing can be compared, when someone asks whether we are on track for the milestone, or when last week's report changed nobody's mind.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Weekly Verification Status Roll-Up Across Blocks
  semiskill-function: design-verification
  semiskill-role: verification-lead
  semiskill-level: lead
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-14
  semiskill-tags: status, reporting, milestone, coverage, regression, cross-block, sign-off
---

# Weekly Verification Status Roll-Up Across Blocks

Every block has its own numbers and its own way of saying them, so the weekly status arrives as five
reports stapled together at five different altitudes: one block described in a paragraph of debug
narrative, four described in a line each, and a reader who concludes the talkative block is the
problem. Nothing is comparable, nobody sees which number moved, and no row asks for anything — so the
meeting ends with the same report scheduled for next week. This holds one altitude across every
block, dates every number to the run behind it, and ends in **a roll-up table plus a decisions
block**. A status that asks the reader for nothing is a newsletter.

## When to use something else

- **One night's failures in one regression**, to be bucketed, signed and routed —
  `dv-regression-triage-routing`. That runs *before* this and feeds it; this skill consumes its
  bucket table rather than rebuilding it, and it is the only place a signature may come from.
- **One failing log** — `dv-sim-log-first-error`. This skill never opens a log at all; budget rule 2
  makes that a hard rule rather than a preference.
- **Shrinking a failure you already have a signature for** — `dv-minimal-reproducer`. **A register
  bring-up failure** — `dv-ral-bringup`.
- **You cannot yet say where a block's summaries and coverage reports live** — `dv-repo-orientation`
  first. A roll-up assembled from guessed paths is worse than none, because it gets believed.

This skill decides nothing itself. It assembles evidence to one altitude and names the decisions that
need a person — step 7, and the part most often skipped.

## Fill this in for our team

Five facts this procedure spends are pack-wide. They live **once**, in `_shared/team-profile.md`, and
are read from there; a second copy below would drift and nothing could say which was stale.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Regression summary** — where it lands, *and its format* | step 2, once per block |
| **Coverage output** — where merged coverage lands | step 3 |
| **Known-issue list** | step 4, to tell an already-tracked failure from a new one |
| **Area to owner map** | step 1, and the `owner` field of every row |
| **Sign-off** — who signs off, and on what evidence | step 7, the gate decisions |

Eight more are specific to this skill, so they are asked for here and nowhere else:

| Slot | What to fill in | Who knows |
|---|---|---|
| Block list | [[FILL: which blocks this roll-up covers, and whether that list is a file on disk or something a person maintains]] | verification lead |
| Status vocabulary | [[FILL: the exact status words our programme uses, what each one means, and who is allowed to set one]] | verification lead |
| Coverage model identity | [[FILL: what our coverage percentage is a percentage of — which merged model, which waiver or exclusion file, and whether the report prints a model revision]] | coverage owner |
| Milestone and gates | [[FILL: the milestone this roll-up counts down to, and the numeric gates attached to it]] | verification lead |
| Previous roll-up | [[FILL: where last week's roll-up is stored, and whether it is a file that can be read]] | verification lead |
| Bug queue | [[FILL: where per-block open-bug counts come from, which field carries severity, and who sets that field]] | DV lead |
| Staleness rule | [[FILL: how old a block's newest regression may be before we report it as stale rather than current]] | verification lead |
| Roll-up destination | [[FILL: where the weekly roll-up is posted, in what format, and who reads it]] | your manager |

Two sit close to facts recorded elsewhere, and not in the same way. **Bug queue is not the profile's
Known-issue list** unless your team keeps one thing: that list answers "is this failure already
tracked", Bug queue answers "how many are open against this block, at what severity". Same tracker,
say so once and read both from it; different, and filling one does not fill the other. **Roll-up
destination is not `dv-regression-triage-routing`'s Report destination**, which is the morning triage
note — a different artifact, audience and cadence. If they are one channel here, record that.

**If a fact or a slot is unfilled, stop and ask. Do not guess a convention.** A guessed status word
is the worst of them: it gets repeated verbatim by someone who believes a human chose it.

## Retrieval budget — read this before opening anything

1. **Grep, Read and Glob work on files on disk.** They cannot search numbers pasted into a chat. If a
   block reported as text in a message, either get the path that text came from, or record the number
   as **reported by a person**, name them in the row, and mark it unverified. Silently promoting a
   message into a table cell is the move that is not available.
2. **This procedure never opens a simulation log.** The inputs are summaries and reports of a few
   thousand lines; the logs behind them are hundreds of megabytes and out of scope by design. A
   number that needs explaining is triage's job, before the roll-up rather than inside it. The
   altitude rule and the budget rule are one rule, which is why this one is worth holding.
3. **Block list:** one **Glob** and one **Read** if it is a file; zero calls if it is a slot fact.
4. **Per block, five calls:** one **Glob** for that block's summary and coverage report; one **Grep**
   for the summary's totals row, using the pattern recorded with the profile's Regression summary
   fact; one **Grep** for the coverage report's total line and model header; two bounded **Read**
   windows of about 40 lines, one at each hit.
5. **Cap the blocks at 8** — 40 calls at full budget. With more, take them in the order the milestone
   makes risky and name the ones you did not open.
6. **Previous roll-up:** one **Glob**, one **Read** of about 80 lines. **Bug queue:** at most one
   **Grep** per block, and only when it resolved to a file on disk — if it is a tracker this line is
   zero, because no Grep can reach it.
7. The ledger is about **52 calls** — 2 for the block list, 40 across eight blocks, 2 for the previous
   roll-up, up to 8 for the bug queue. Already a full session's attention. Any **Grep** returning
   more than about 200 hits is too broad; narrow it before reading anything.
8. **Stopping rule:** when the ledger is spent, stop. Anything missing stays `?` with the name of the
   person to ask beside it, never a plausible number. Then state the basis — how many blocks were
   read from files, how many came from a person, how many are missing.

## Procedure

### 1. Fix the altitude, then give every block a row — including the silent ones

Decide the row contract first, in writing, and hold it: **one row per block, the same fields in the
same order, the same units, every number carrying the file it came from and the date of the run
behind it.** Nothing deeper goes in — no test names, no signatures, no debug narrative. At most one
sentence of prose per block, and it is about the decision, not the bug. Written after the numbers
arrive, the contract bends to fit whichever block reported most fully, which is how the altitude is
lost; a block that needs more gets a linked document, not a taller row.

Then take the blocks from the **Block list** slot — one **Glob** and one **Read** if it is a file —
and name each block's owner from the profile's Area to owner map now, before any number exists, so no
row ends up with nobody answering for it. A block that has sent nothing this week still gets a row:
`recency: missing`, its owner, and a question. Silence reads as "fine" in every status meeting ever
held, and this is the cheapest correction in the procedure.

### 2. Read each block's regression numbers — three of them, and a date

**Glob** against the profile's Regression summary fact, **Grep** for the totals row, one bounded
**Read** at that hit. Take four things: how many tests **passed**; how many **produced a verdict at
all**; how many are **in the list** for that block; and the run identifier with the **date** it ran.

Report all three counts, never one percentage. A percentage hides its denominator, and the
denominator is the part that moves — a block that quietly dropped forty tests from its list raises
its pass rate without fixing anything.

Apply the **Staleness rule** slot to the run date and set `recency` to `current`, `stale` or
`missing`. A block whose newest regression ran on Tuesday is reporting Tuesday, whatever today is. If
the summary separates "failed" from "did not run", carry that through; if it has no not-started
category, write `unrun not reported` rather than deriving it by subtraction.

### 3. Read each block's coverage number, and the model it is a percentage of

**Grep** the coverage report for its total line and the header naming the model, then one bounded
**Read** covering both. Record the number **and** the model identity from the **Coverage model
identity** slot: which merged model, which waiver or exclusion file, and the revision if it is
printed. A coverage number without its model is not a measurement, it is a mood — two blocks quoting
percentages of two differently scoped models cannot be averaged, added or compared.

The agent cannot merge coverage databases or produce a report: **ask the block owner to produce the
merged report and give you the path it was written to**, and record that the merge was theirs. With
no report for a block this week the cell is `not-reported`, which is a fact; last week's number
presented as this week's is not.

### 4. Take the bug counts from the queue, or say plainly that you could not

What is possible depends on what the **Bug queue** slot resolved to:

- **A file on disk.** One **Grep** per block for its open entries. Count by whichever field the slot
  says carries severity, and name that field in the row heading rather than saying "criticals".
- **A tracker or page.** Read, Grep and Glob open files and this skill has no network, so the cell is
  `queue-not-readable` and you ask its owner — recording that the counts came from a person.
- **Unfilled.** `queue-not-readable`, and say so. A count nobody produced is not a zero.

Where triage already produced signatures via `dv-regression-triage-routing`, deduplicate on them
before counting: one shared-component failure across four blocks is one bug and four rows, and
counting it four times hides that one fix clears all four. Compare signatures exactly, per
`_shared/failure-signature-schema.md` — never by resemblance, and never re-derived here, since this
skill has not opened the logs they came from.

### 5. Compare with the previous roll-up, or declare no-baseline

**Glob** and **Read** the **Previous roll-up** slot's file; 80 lines covers a table. Compute each
delta from the two written numbers only. If the file is not on disk, or the slot is unfilled, every
delta is `no-baseline` and the report says so once at the top. Reconstructing last week's numbers
from this week's data is arithmetic, not history, and it always shows progress.

**Refuse a coverage delta across a model change.** If step 3's model identity differs from last
week's — regenerated model, new exclusion file, rescoped merge — the cell is `model-changed` and the
two numbers are not subtractable. Reporting the difference anyway is how a status table tells a
confident lie.

### 6. Set the status word from its owner, not from the pass rate

The numbers are claims about the past; the status word is a claim about the future, and no arithmetic
turns one into the other — a block can sit at 99 percent pass and be off-track because the untouched
work is all ahead of it. Use only the words in the **Status vocabulary** slot, spelled exactly, and
record **who set each one**. If an owner has not given a word, the cell stays empty with their name
beside it. An invented word, or a colour borrowed from another programme, is the one cell nobody
re-checks.

### 7. Name the decisions, with what each needs and by when

This is what makes the roll-up worth writing. Every row that is not clean resolves into one of four
things, and saying which is the job: **a decision someone must make** — accept a gap, drop scope,
move a person, change a date; **an owner and a date**, where the work is understood and simply not
finished; **a question to be answered** before either of those is possible; or **nothing**, genuinely
on track and stated so the reader can skip it.

Name who decides. Gate decisions go to whoever the profile's **Sign-off** fact names, with the
evidence that fact says they sign on — and check the **Milestone and gates** slot's numeric gates
against today's numbers, stating each gap as a number rather than as concern. A decision with no date
is a topic; a decision whose default outcome is unstated will be taken by default anyway, so write
down what happens if nobody answers.

### 8. Draft the roll-up, then hand back what needs a machine or another person

Format it for the **Roll-up destination** slot — where it is posted, in what shape, for whom.

```
rollup     : <programme, week ending date, prepared by>
altitude   : one row per block, same fields, same units — anything deeper is linked, not inlined
blocks     : <n> reported of <m> in the block list
milestone  : <the milestone this counts down to> — <n> weeks out
gates      : <each numeric gate, and the number standing against it today>
sources    : <summary path pattern>, <coverage path pattern>, <bug queue>, <previous roll-up>
basis      : <blocks read from files>, <blocks reported by a person>, <blocks missing>
```

Then one block per row, in the order the milestone makes risky — never alphabetically:

```
block      : <name, spelled as the area-to-owner map spells it>
status     : <one word from our status vocabulary, and who set it>
recency    : current | stale | missing
regression : <pass> / <attempted> of <listed>, run <id>, dated <date>
cov pct    : <number> percent of <model identity>, merged <date> — or not-reported
cov delta  : <change since the previous roll-up, or no-baseline, or model-changed>
bugs       : <open count, by the severity field our queue uses — or queue-not-readable>
blocker    : <the one thing stopping this block, or none>
owner      : <name from the area-to-owner map>
evidence   : <the file each number above came from>
```

Then the decisions, which are the point of the exercise:

```
decision   : D1
asks       : <the question, phrased so it can be answered yes or no>
needs      : <the fact, the number, or the person required to answer it>
decides    : <who decides — from the sign-off fact where it is a gate>
by         : <date, tied to the milestone>
if silent  : <what happens by default if nobody answers>
```

Leave a cell empty rather than filling it plausibly: an empty cell is a question someone answers in a
minute, a plausible one survives for weeks. Then state the handoffs explicitly rather than implying
them — ask each block owner for a status word from the vocabulary and the one blocker behind it; ask
the coverage owner to produce this week's merged report, give you the path, and say whether the model
or the exclusion file changed; ask the bug queue's owner for counts when the queue is not a file; ask
whoever owns a stale block when its regression last ran; ask the sign-off owner to confirm each gate
gap is accepted or not.

## Gotchas

- **A pass rate needs a denominator that does not move.** Ninety-six percent of what — attempted, or
  listed? Dropping tests from a list raises the rate and lowers the confidence, and only the three
  raw numbers show it.
- **Coverage rising is not coverage becoming true.** A new exclusion file, a regenerated model or a
  rescoped merge moves the denominator, so quote the model revision beside every number and refuse
  the subtraction when it changed. Say too whether the merge includes failing runs: coverage from a
  run whose result was thrown away counts stimulus that checked nothing, and both conventions exist.
- **Two blocks measured on two different days are not comparable, and their average is meaningless.**
  Date every row to its run, not to the day you wrote the report.
- **A block with no data is not green.** Give it a row with `recency: missing` and a named owner.
  Absence is the only status that reliably reads as success.
- **One shared-component bug in four blocks is one bug and four rows.** Deduplicate on the signature
  before counting, or the total claims four fixes are needed when one is.
- **Severity is not priority.** A queue's severity field is usually set once by whoever filed the
  entry and never revisited, so counting high-severity entries measures filing habits as much as
  risk. Name the field and who sets it.
- **Deltas need last week's file, not last week's recollection.** With no baseline on disk every
  delta is `no-baseline` — a useful thing to report, where a quietly recomputed one is not.
- **Detail below the altitude belongs in another document, not a footnote.** Five sentences about one
  block beside one line about four others tells the reader that block is the problem, when all it
  shows is which owner writes the most.
- **The report that asks for nothing gets read by nobody twice.** If step 7 produced no decisions,
  either the programme is genuinely clean — say so in one line — or the roll-up stopped one step
  short of being useful.

## Human verification — what a wrong answer looks like

Before posting, check:

- every row carries the same fields, in the same order, in the same units, and no row is taller
- every number names the file it came from and the date of the run behind it
- regression is three numbers, not one percentage
- every coverage number names its model identity, and any delta across a model change reads
  `model-changed` rather than a difference
- every status word is one from the vocabulary slot, attributed to the person who set it
- blocks that reported nothing appear as rows marked `recency: missing`, not as absences
- the basis line accounts for every block — from a file, from a person, or missing — adding up to the
  block list's size
- the decisions block is not empty, and every decision has a decider, a date and a stated default
- nothing in the table came from a simulation log, because no log was opened

A wrong answer is a clean-looking table of five blocks, one percentage each, no dates, no model
identities, a coverage delta computed across a model regeneration, and no decisions — assembled on a
week when one block never reported at all and therefore does not appear.

## Done when

The table can be posted as-is, every number traces to a file and a run date, and every reader either
has a decision with a date on it or can see they are not needed.
