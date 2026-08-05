---
name: dv-sim-log-first-error
description: Find the true first error in a simulation log, normalise it into a stable failure signature, and produce the exact block needed to reproduce it. Use when a simulation or regression test has failed and the log is too large to read, when you are about to paste a log into a chat, or when you need to hand a failure to someone else.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: First-Error Extraction and Repro Block
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: fresher
  semiskill-owner: dv-guild
  semiskill-version: 1.4.0
  semiskill-review-by: 2027-08-05
  semiskill-tags: logs, triage, debug, regression, reproducer
---

# First-Error Extraction and Repro Block

A failing simulation log is mostly cascade. The first line that looks alarming is usually a
consequence, and the line that explains the failure often scrolled past hundreds of lines earlier
without the word "error" in it. This procedure finds the real first failure, turns it into a
signature that can be matched against other people's failures, and produces a repro block someone
else can act on without asking you three follow-up questions.

The output is three things: **a signature, a cause line, and a repro block**, plus one line under
the block saying how much of the log that rests on. Not a summary of the log.

**When not to use this.** A whole night of regression failures needs sorting and routing before any
one log deserves this much attention — that is `dv-regression-triage-routing`. Once you have a
signature from here and want the smallest, fastest run that still shows it, use
`dv-minimal-reproducer`. A failure already known to be a register access belongs to
`dv-ral-bringup`. And a build that failed before any simulation started belongs to
`dv-build-filelist-hygiene` — step 3 finishes the block and routes it there.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Log location | [[FILL: where our simulation and regression logs land]] | your mentor |
| Fatal markers | [[FILL: the strings our flow prints on a real failure, beyond UVM_ERROR and UVM_FATAL]] | DV lead |
| Pass marker | [[FILL: the string a clean run prints at the end]] | DV lead |
| Run identity | [[FILL: what identifies one run for us — seed, test name, config, build tag]] | your mentor |
| Rerun convention | [[FILL: how someone repeats one specific run — describe it; leave blank rather than guessing]] | your mentor |
| Known-issue list | [[FILL: where our known-issue list lives, how each entry is keyed, and whether it is a file that can be read or a tracker that must be searched by a person]] | DV lead |

These are pack-wide facts and live in `_shared/team-profile.md` — fill that in once for the team and
read the answers from there rather than re-interviewing anyone. Every row above is spent by a step:
Log location, Fatal markers and Pass marker in step 1; Known-issue list in step 5; Run identity and
Rerun convention in the repro block in step 6. The profile's **Bug convention** row is
deliberately *not* repeated here — this skill files nothing. Its output is a repro block handed to a
person, and step 3 routes a finding to its owner rather than writing a bug report, so that fact would
be collected and never used.

**If a slot is unfilled, stop and ask. Do not guess a convention** — a confidently invented log path
or rerun recipe wastes more time than it saves.

## Retrieval budget — read this before opening anything

Simulation logs routinely run to hundreds of megabytes. Reading one whole is impossible and pointless.
Work in this order and stop as soon as the cause is identified:

1. **Grep and Read work on files, not on chat text.** If the log arrived pasted into the conversation
   rather than as a path, ask for the path on disk, or ask for the text to be saved to a file and be
   given that path. Until a path exists you may reason over the pasted lines by eye — but say that is
   what you did. You have not searched the log, only the fragment you were shown.
2. **Never open the log with Read first.** Use **Grep** to locate lines, then Read only a bounded
   window around a specific line number.
3. Budget roughly: one Grep for markers, one Grep for the earliest marker's line number, at most
   three windowed Reads of about 80 lines each, and — only when the known-issue list is a file on
   disk — one Grep of that list in step 5.
4. If a Grep returns more than about 200 hits, the pattern is too broad — narrow it before reading
   anything.
5. If after three windowed Reads the cause is still unclear, stop and report what is known. Guessing
   past this point produces confident, wrong answers.
6. State what you actually covered — "signature derived from the log" or "reasoned from a pasted
   fragment only, log not searched". An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Establish that the run actually failed, and how far it got

If the log arrived pasted into the chat rather than as a path on disk, resolve that before anything
else — budget rule 1. The **Log location** slot says where ours land, so ask for the path under it
rather than for the log again.

Use **one Grep** whose pattern alternates the pass marker with the fatal markers — one call, and it
is the single marker Grep budget rule 3 allows. A log with no pass marker and no fatal marker usually
means the run died before the testbench started — a build, licence, or environment problem, not a
design bug.

Note how far the log got, using the same five tokens the repro block in step 6 and
`_shared/failure-signature-schema.md` accept — `compile`, `elab`, `run`, `finalise`, `post` — and no
others. Those two lists are compared exactly, so a phase written in any other words matches nothing.

`finalise` and `post` are the pair that get confused, and the test between them is whether the
simulator was still running when the failure happened:

- **`finalise`** — the simulator was still running: its end-of-run report, final-phase checks, and
  the summary counts. These lines are in this same log, after the last design activity.
- **`post`** — the simulator had already exited and a later step failed: coverage merge, log
  post-processing, results checking, artifact copying. If the failing step could not have run until
  the simulation finished, it is `post`, not `finalise`.

If the log simply stops with no end-of-run report at all, the phase is `run` — the run did not reach
`finalise`. If the failing step is one you cannot see in this log, say so rather than assuming
`finalise`; `post` diagnostics usually live in whatever file that step writes, and you have not
searched it.

### 2. Find the earliest failure, not the loudest

Collect the line numbers of every fatal-marker hit with **Grep**. Take the **lowest** line number.
Then Read a window that starts about 60 lines *before* it.

The cause is very often in that preceding window and is not itself marked as an error. Look for:

- the last thing that succeeded, and what it was about to do next
- a warning about a missing, defaulted, or overridden value
- a configuration or plusarg being applied, or conspicuously not applied
- a reset, clock, or power event immediately before the first complaint
- an X or Z appearing in a value that was previously known

Record the **cause line** verbatim, with its line number.

### 3. Separate infrastructure failures from design failures

Before going further, classify — from the marker hits of step 1 and the window you already read in
step 2, not from a new search. This step opens nothing and spends no budget of its own.

These are infrastructure and belong to a different owner:

- compile or elaboration errors, missing files, unresolved modules
- licence, queue, or host errors
- a test that never started, or a log truncated mid-line
- an out-of-disk or timeout with no design activity near the end

**What "stop" means here, precisely.** Stop the *design* analysis: hunt no further for a design root
cause, and never write a design bug report for a build break. Do **not** stop the procedure. Every
finding — infrastructure or design — continues through steps 4, 5 and 6 and ends as exactly one repro
block; `class` changes what goes into that block and who receives it, never whether a block exists.
A sentence with no block is the one output the next person cannot route, compare against anyone
else's, or paste into a triage table.

For an infrastructure finding, fill the block like this:

- `class` is `infrastructure`, and the signature's `kind` is `tool` — the token
  `_shared/failure-signature-schema.md` carries for exactly this case, not `fatal`.
- `where` is the step or tool that printed the diagnostic when the log names it, `?` when it does
  not. Do not reach for a design hierarchy path the run never got near.
- `phase` is still one of the five tokens, chosen in step 1 from how far the log actually got. Write
  `?` if the log supports none of them, rather than defaulting to `run`.
- `cause` and `first err` are filled exactly as for a design failure, from lines you read verbatim.
  `notes` says which of the four bullets above it matched.

Routing then differs by subtype:

- **Compile or elaboration break.** Hand the finished block to `dv-build-filelist-hygiene`, phase
  `compile` or `elab` — the only two its own block accepts. It reuses `signature`, `first err`,
  `cause`, `class`, `run id` and `notes` under these names, so the block *is* the handoff.
- **Licence, queue, host, disk, never-started or truncated.** The block goes to whoever owns the
  compute environment, not a design owner. No sibling skill takes these, so it is all they get.

Write `class: unknown`, never `design` by default, when the evidence settles neither: step 2 ran out
of budget without a cause line, or you are reasoning from a pasted fragment and never searched the
log. `design` requires actual testbench or design activity near the failure.

### 4. Normalise into a failure signature

Follow `_shared/failure-signature-schema.md` exactly — same field order, same normalisation rules.
Every field must be traceable to text that was actually in the log; write `?` for anything that is
not, rather than inventing it.

An infrastructure finding is normalised the same way — step 3 already fixed its `kind` and `class`,
and nothing else here changes. Job numbers and host-specific text in a licence or disk diagnostic
normalise away exactly as seeds and times do, or the signature matches nothing next week.

### 5. Check it against the known-issue list, not memory

What you can do depends on what the known-issue slot resolved to:

- **A file on disk.** One **Grep** of it for the signature's `where` and for the distinctive
  fragment of `what`. Compare exactly. A match means this is already tracked: name that entry in
  the block's `notes`, by whatever key the list uses, and stop debugging — still produce the block.
- **A tracker or page that is not a file on disk.** Read and Grep cannot reach it. Produce the repro
  block anyway and ask the person who can query the list to compare the signature; say the
  known-issue check is pending their answer.
- **Unfilled.** Say the check did not happen. Do not call the failure new.

This applies to an infrastructure finding too — a recurring licence or host break is exactly the kind
of entry such a list already carries, and the check costs the one Grep already budgeted. Matching
from memory rather than from the list is how duplicate bugs get filed.

### 6. Produce the repro block

The point of the repro block is that the next person needs nothing else from you. One failure, one
block — including the infrastructure ones step 3 routed elsewhere. `class`, `phase` and the
signature's `kind` are whatever step 3 settled; every other field is filled the same way either way.

```
signature : <phase>|<kind>|<where>|<what>
cause     : <verbatim cause line, with line number>
first err : <verbatim first fatal line, with line number>
phase     : compile | elab | run | finalise | post
class     : design | infrastructure | unknown
run id    : <whatever identifies this run for us>
to repeat : <the invocation the human should run, taken from our conventions>
log       : <path, and the line range worth reading>
notes     : <anything the next person would otherwise have to rediscover>
```

Take `to repeat` from the team profile's **Rerun convention**; if that is unfilled, leave the field
empty rather than inventing an invocation. An invented rerun command is the single most expensive
mistake available here.

Under the block, add one line stating the coverage — "signature derived from the log" (give the
path) or "reasoned from a pasted fragment only, log not searched", in which case every field above
it is provisional. The line goes under the block rather than inside it: the block's field set is
fixed, because `dv-minimal-reproducer` and `dv-ral-bringup` reuse these field names in their own
handoff blocks.

## Gotchas

- **The first `UVM_ERROR` is rarely the first failure.** A dropped configuration or a missed reset
  usually announces itself as a warning, hundreds of lines earlier.
- **A timeout is a symptom.** The interesting question is what stopped making progress and when —
  look for the last transaction, not the timeout line.
- **`UVM_FATAL` stops the run immediately**, so anything after it is noise from teardown.
- **A miscompare of all zeroes or all Xs** usually means nothing was driven, not that the wrong value
  was computed. Check whether the interface was connected and out of reset.
- **Error *counts* in the end-of-run report (`finalise`)** are totals for the whole run, not new
  failures — they repeat errors already printed earlier. A check that genuinely fires in the report
  phase, such as an end-of-test emptiness check, is a real failure and its phase is `finalise`.
- **Two failures with the same message but different `where`** are two bugs. Do not merge them.
- **Interleaved output from parallel runs** in one file will produce nonsense signatures — confirm the
  log belongs to a single run before trusting the ordering.
- **A log that ends mid-line** was truncated: the run was killed. The cause is at the end, not in the
  middle.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the cause line is quoted **verbatim** and its line number really is lower than the first fatal line
- the signature contains no run-specific values — no times, seeds, indices, or data
- the phase is one of the block's five tokens spelled exactly, and is `post` only if the failing step
  ran after the simulator exited — the end-of-run report is `finalise`, not `post`
- there is a block at all — an infrastructure finding gets one too, and is `class: infrastructure`
  with the signature's `kind` as `tool`, not a sentence saying the build broke
- `class` is `design` only if there is actual testbench or design activity near the failure, and is
  `unknown` rather than `design` whenever the log settled neither
- `to repeat` is either taken from the team's real rerun convention or left empty
- the coverage line is present under the block, and if it says the log was never searched, nothing
  above it is being treated as verified

A wrong answer typically names a cascade line as the root cause, or produces a signature that still
carries a seed or a timestamp and therefore matches nothing.

## Done when

You can hand someone the repro block, with its coverage line, and they need to ask you nothing.
