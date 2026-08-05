---
name: dv-sim-log-first-error
description: Find the true first error in a simulation log, normalise it into a stable failure signature, and produce the exact block needed to reproduce it. Use when a simulation or regression test has failed and the log is too large to read, when you are about to paste a log into a chat, or when you need to hand a failure to someone else.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: First-Error Extraction and Repro Block
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-02-05
  semiskill-tags: logs, triage, debug, regression, reproducer
---

# First-Error Extraction and Repro Block

A failing simulation log is mostly cascade. The first line that looks alarming is usually a
consequence, and the line that explains the failure often scrolled past hundreds of lines earlier
without the word "error" in it. This procedure finds the real first failure, turns it into a
signature that can be matched against other people's failures, and produces a repro block someone
else can act on without asking you three follow-up questions.

The output is three things: **a signature, a cause line, and a repro block.** Not a summary of the
log.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Log location | [[FILL: where our simulation and regression logs land]] | your mentor |
| Fatal markers | [[FILL: the strings our flow prints on a real failure, beyond UVM_ERROR and UVM_FATAL]] | DV lead |
| Pass marker | [[FILL: the string a clean run prints at the end]] | DV lead |
| Run identity | [[FILL: what identifies one run for us — seed, test name, config, build tag]] | your mentor |
| Known issues | [[FILL: where our known-issue list lives]] | DV lead |
| Bug tracker convention | [[FILL: what a bug title looks like here]] | DV lead |

**If a slot is unfilled, stop and ask. Do not guess a convention** — a confidently invented log path
or rerun recipe wastes more time than it saves.

## Retrieval budget — read this before opening anything

Simulation logs routinely run to hundreds of megabytes. Reading one whole is impossible and pointless.
Work in this order and stop as soon as the cause is identified:

1. **Never open the log with Read first.** Use **Grep** to locate lines, then Read only a bounded
   window around a specific line number.
2. Budget roughly: one Grep for markers, one Grep for the earliest marker's line number, then at most
   three windowed Reads of about 80 lines each.
3. If a Grep returns more than about 200 hits, the pattern is too broad — narrow it before reading
   anything.
4. If after three windowed Reads the cause is still unclear, stop and report what is known. Guessing
   past this point produces confident, wrong answers.

## Procedure

### 1. Establish that the run actually failed, and how far it got

Use **Grep** for the pass marker and for the fatal markers. A log with no pass marker and no fatal
marker usually means the run died before the testbench started — a build, licence, or environment
problem, not a design bug. Note which phase the log reaches: compile, elaboration, run, final report.

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

Before going further, classify. These are infrastructure and belong to a different owner:

- compile or elaboration errors, missing files, unresolved modules
- licence, queue, or host errors
- a test that never started, or a log truncated mid-line
- an out-of-disk or timeout with no design activity near the end

If it is infrastructure, stop the analysis here and say so plainly. Do not produce a design bug
report for a build break.

### 4. Normalise into a failure signature

Follow `_shared/failure-signature-schema.md` exactly — same field order, same normalisation rules.
Every field must be traceable to text that was actually in the log; write `?` for anything that is
not, rather than inventing it.

### 5. Check it against known issues

If the known-issues slot above is filled, compare the signature against it. A match means this is
already tracked — say which entry, and stop. Matching from memory rather than from the list is how
duplicate bugs get filed.

### 6. Produce the repro block

The point of the repro block is that the next person needs nothing else from you.

```
signature : <phase>|<kind>|<where>|<what>
cause     : <verbatim cause line, with line number>
first err : <verbatim first fatal line, with line number>
phase     : compile | elab | run | finalise
class     : design | infrastructure | unknown
run id    : <whatever identifies this run for us>
to repeat : <the invocation the human should run, taken from our conventions>
log       : <path, and the line range worth reading>
notes     : <anything the next person would otherwise have to rediscover>
```

Leave `to repeat` empty rather than inventing an invocation. An invented rerun command is the single
most expensive mistake available here.

## Gotchas

- **The first `UVM_ERROR` is rarely the first failure.** A dropped configuration or a missed reset
  usually announces itself as a warning, hundreds of lines earlier.
- **A timeout is a symptom.** The interesting question is what stopped making progress and when —
  look for the last transaction, not the timeout line.
- **`UVM_FATAL` stops the run immediately**, so anything after it is noise from teardown.
- **A miscompare of all zeroes or all Xs** usually means nothing was driven, not that the wrong value
  was computed. Check whether the interface was connected and out of reset.
- **Errors during the final report phase** are counted from the whole run and are not new failures.
- **Two failures with the same message but different `where`** are two bugs. Do not merge them.
- **Interleaved output from parallel runs** in one file will produce nonsense signatures — confirm the
  log belongs to a single run before trusting the ordering.
- **A log that ends mid-line** was truncated: the run was killed. The cause is at the end, not in the
  middle.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the cause line is quoted **verbatim** and its line number really is lower than the first fatal line
- the signature contains no run-specific values — no times, seeds, indices, or data
- `class` is design only if there is actual testbench or design activity near the failure
- `to repeat` is either taken from the team's real convention or left empty

A wrong answer typically names a cascade line as the root cause, or produces a signature that still
carries a seed or a timestamp and therefore matches nothing.

## Done when

You can hand someone the repro block and they need to ask you nothing.
