---
name: dv-regression-tiering-farm
description: Define or repair a regression so its tiers, seed counts and coverage directory names hold up on a real farm. Use when you are adding a test and cannot tell which tier it belongs in, when pre-merge is green and the nightly is red on the same change, when someone asks how many seeds a test should get, or when the coverage merge finds nothing, finds too much, or finds runs from the wrong build.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Regression Tiering, Seed Policy and Farm Job-Script Authoring
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.2.0
  semiskill-review-by: 2027-06-14
  semiskill-tags: regression, tiering, seeds, farm, coverage-merge, job-script, sign-off
---

# Regression Tiering, Seed Policy and Farm Job-Script Authoring

Three decisions define a regression, and all three are usually made once, quietly, by whoever added the second test —
which tier a test belongs to, how many seeds it gets, and what its coverage database is called. Each is cheap on the day
and expensive for years. The costly failure is not a red regression; it is a green one never asked a question worth
answering, and a coverage number merged from runs nobody can enumerate. The output is **a tier table, a per-test seed
policy, and a coverage-directory verdict**, traceable to files this procedure opened. It cannot submit a job, watch a
queue, time a test or merge a database — each is a handoff, named at the step that needs it.

## When to use something else

- **A night of results already in hand** — `dv-regression-triage-routing`: it reads the regression *summary*, this
  reads the *list*. One failing log — `dv-sim-log-first-error`. A smaller signature — `dv-minimal-reproducer`. The
  build broke — `dv-build-filelist-hygiene`. No map of lists, run area and coverage output — `dv-repo-orientation`.
- **The nightly stopped fitting its window** — that is turnaround, so `dv-regression-runtime-tuning`: where one run's
  wall clock actually goes and whether a change made it measurably faster. This skill only changes which tests sit in
  a tier and how many seeds each gets; a job killed for exceeding memory is diagnosed there and fixed here.
- **The weekly coverage number itself** — `dv-coverage-merge-report`: what the merged number measures and what moved it.
  Come here only when that merge consumes the wrong runs *because of how tiers and run directories are named*.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Regression lists | [[FILL: which file each tier's test list lives in, what one row means, and the row pattern worth grepping for]] | DV infra owner |
| Tier definitions | [[FILL: what our tiers are called, what each one gates, and the wall-clock budget each must finish inside]] | verification lead |
| Seed convention | [[FILL: how a seed is chosen for one run, where the chosen seed is recorded, and whether any value is a sentinel meaning choose one for me]] | DV infra owner |
| Closure plan | [[FILL: where our coverage goal and its per-feature test and seed allocation are written down, and whether that is a file which can be read]] | coverage owner |
| Job script | [[FILL: where the script that turns one test into one farm job lives, and whether we submit one job per test or one array job per tier]] | DV infra owner |
| Job resource and retry | [[FILL: the memory, wall clock and queue one job asks for by default, what the scheduler does when a job exceeds one of them, and whether a failed or killed job is resubmitted automatically and where its output lands]] | DV infra owner |
| Coverage directory expression | [[FILL: the expression our flow builds each run's coverage database directory name from, and which of its components vary per run]] | coverage owner |
| Merge scope | [[FILL: what our merge step reads or globs to find the databases it combines, and what it does when one is unreadable or came from a different elaboration]] | coverage owner |

Four pack-wide facts come from `_shared/team-profile.md`, each spent by a named step: **Regression summary** (steps 1
and 4 — where a drawn seed is recorded), **Pass marker** (step 6 — what a `pass rule` of `log-marker` matches),
**Coverage output** (step 6 — the kept storage a job's log and database must reach before exiting) and **Sign-off**
(step 7). Two rows above are deliberately *narrower* and must never be filled from them: **Coverage directory
expression** is the per-run directory built *before* any merge, where *Coverage output* is where the kept combined
coverage lands; **Regression lists** names which tests run at which tier, where *Regression summary* says what each
did — `dv-repo-orientation`'s *Test list* gathers that same input, and if they disagree one is stale. **If a slot is
unfilled, stop and ask**: an invented tier name or seed default looks authoritative and is fiction at sign-off.

## Retrieval budget — read this before opening anything

Lists reach thousands of rows and a farm writes tens of thousands of run directories. Grepping is cheap, reading is
the budget, and every call the steps below spend is priced here.

1. **Grep, Read and Glob work on files on disk.** A list or job script pasted into the conversation cannot be searched —
   ask for the path, or for the text saved to a file. If neither is possible, say plainly nothing below was verified.
2. **Glob** first, at most **four** patterns, for the tier lists, the job script and the flow wrapper. Paths only.
3. Per tier: one **Grep** for the row pattern from the Regression lists slot — its hits *are* the membership — plus
   one windowed **Read** of about 60 lines at the head of the list, where the defaults sit. Cap at **four tiers**:
   four Greps, four Reads. Name any tier you skipped. Step 4's seed-sentinel search is **one further Grep** on those
   same files — an alternation spent once across all of them, never folded into the row-pattern Grep above.
4. The job script and the flow wrapper are two files. Read either whole only under about 300 lines; otherwise **Grep**
   for the strings steps 5 and 6 name — at most **six** across both — and **Read** at most **four** windows of about
   40 lines. Step 4's closure plan gets one further **Grep** and one 60-line **Read**, and only when readable.
5. A Grep returning more than about 200 hits is too broad — narrow it first. **A hit count that reached your runtime's
   limit is not a count**: record "at least N, truncated" and call that membership check incomplete.
6. **Stopping rule.** Four Globs; twelve Greps (four membership, one sentinel, six flow-file, one closure plan); nine
   windowed Reads (four list heads, four flow-file windows, one closure plan). When that is spent, stop and report
   **what you covered** — tiers read from their lists, tiers taken from the slot table alone, files never opened.
   Past this line, invented seed counts and directory components look exactly like measured ones.

## Procedure

### 1. Locate the lists, the job script and the flow wrapper

Resolve the pasted-versus-path question first — budget rule 1. Then **Glob** the paths the Regression lists and Job
script slots name. If either slot is unfilled, stop: every Grep below searches for strings only those slots supply, and
a search for a convention we do not use returns zero hits on the step meant to find the regression. Keep the *list* and
the profile's **Regression summary** apart: last night's summary reports what ran — the list minus what the farm dropped.

### 2. Build the tier table from what the lists actually hold

Per tier, one **Grep** for the row pattern gives the membership as hit lines; one windowed **Read** at the head of the
file gives the defaults — seed count, coverage on or off, resource overrides, timeouts. Record row count, whether jobs
share one build or each elaborates its own, and the wall-clock budget from **Tier definitions**.

**Write `cov mode` here**, from the rows rather than the flow's intent: `on` or `off` when the head-of-list default
governs every row, `mixed` when individual rows override it — name those rows beside the value, or the next reader
assumes the whole tier collected. A shared build is the usual hazard: if anything rebuilds into that directory while
jobs are still starting, some take the old executable and some the new. The list cannot say if it was frozen — ask.

### 3. Classify each tier against the four properties, then check containment

Work from the windows step 2 opened. A tier is a tier only with all four:

1. **One question it settles** — is it safe to merge this change; did anything that worked yesterday stop; is the
   release note's pass-and-coverage claim true. A tier whose question needs a paragraph is a habit that acquired a name.
2. **A budget it fits inside**, from **Tier definitions**. A pre-merge tier people wait ninety minutes for gets
   bypassed, and a bypassed tier is worse than none because the table still shows it.
3. **A named action on red** — who is told, what is blocked, within what time.
4. **A stated failure tolerance** — zero, or a waiver list where every entry has an owner and a date. Unexamined known
   failures are how a gate dies: not by argument, but by everyone learning that the red is normal.

Then containment, from the step 2 hit lines — never from a tier column nobody has verified. **Pre-merge should be a
subset of nightly, and nightly of sign-off**, on test identity rather than seed count. **Same name means same test**: a
shortened variant used to fit a pre-merge budget needs a different name, or every pre-merge pass is a claim about
something that never ran at the tier it represents. **A test in no tier is dead** — name them, but do not recommend
deleting anything seen only in a filelist. If the membership Grep truncated, say containment is unchecked for that tier.

### 4. Set the seed policy per test, not per tier

Take the allocation from **Closure plan** — one **Grep** and one windowed **Read**, only if it is a readable file. With
no plan, say the counts are unallocated: "everything gets ten" is at once far too few for the two tests that need
hundreds and waste on the thirty that need one, because seeds buy new state only where randomisation reaches it, and a
directed test at forty seeds is forty identical runs at forty times the cost.

- **Pre-merge runs a fixed seed per test, written in the list** — a gate must return the same verdict for the same
  code, or people learn to resubmit until green and the gate is decoration that still costs farm time. A fixed seed
  ages, pinning one path while the stimulus moves, so rotate it on a schedule and *visibly*.
- **Nightly and sign-off draw fresh seeds, and every seed is recorded** in the profile's **Regression summary** — an
  unrecorded seed makes its failure unreproducible, the same as never having run it.
- **Check the sentinel.** Some flows accept a value meaning "choose one for me" and record *that value* rather than the
  one chosen. Spend budget rule 3's single sentinel **Grep** across the lists for the value named in **Seed
  convention**; every row carrying it is a run nobody can repeat.

**Write `seeds` from the rows, not from the policy above:** `fixed` when every row names a literal seed;
`random-recorded` when rows leave it to the flow *and* **Regression summary** confirms the drawn seed is recorded per
run; `unrecorded` when nothing records it, including every row carrying the sentinel; `mixed` when rows in one tier
disagree — name those rows beside the value.

**Cost, and what to ask the engineer for.** Sum across tests rather than multiplying one runtime by the whole tier: each
test's seed count times *its own* runtime, added up — a tier mixes directed tests finishing in minutes with soak tests
that do not. The agent cannot time anything, so ask for the wall clock of the longest test per tier and of a typical
one, then write a labelled range: typical the floor, longest the ceiling. One figure, say which end; neither, **unmeasured**.

### 5. Judge the coverage directory name against what the merge step actually reads

Spend two of budget rule 4's six flow-file Greps on the job script and wrapper, for the components of the **Coverage
directory expression**, and read **Merge scope** for what the merge is aimed at. A name is mergeable when the pattern
finding it matches every database you want and nothing you do not. Three things go wrong, only the first of them loud:

- **Collision** — two runs writing one directory. Last writer wins, and if both were live you get a database that is
  neither. Test name alone collides across seeds; seed alone across tests; test plus seed with its own retry.
- **Miss** — the pattern matches nothing, usually because a component it never knew about, such as a timestamp, sits above its fixed part.
- **Over-match** — it picks up another tier, another build, or somebody's waveform-debug rerun in the same tree. The
  quiet one: a sign-off number including runs nobody would defend if asked to list them.

Classify every component of the expression as exactly one of three kinds, and say which:

```
<scope: tier and build tag>/<run: test name, seed, attempt>/
```

**Scope** is fixed for the whole regression and is what the merge anchors on. **Run** is every component that changes
between runs, and they must *jointly* make one run distinct — test name, seed *and* attempt, or an automatic retry
overwrites the partial database the killed job left. All else is **noise**: host name, scheduler job id, user name, a
timestamp to the second, varying for reasons unrelated to the run and defeating both a search for one run and a re-merge.

**Put the build tag in scope.** Databases from different elaborations do not describe the same model: different RTL,
compile defines or parameters mean different coverage bins, and tools variously error, warn or quietly union over bins
that no longer exist — **Merge scope** says which ours does. With the tag in scope a cross-build merge cannot be built;
without it, it has to be *noticed*, and it is not noticeable. Likewise **a killed job leaves a partial database**: write
under a name the pattern misses until the run ends cleanly, else record killed runs so they can be excluded.

### 6. Read the job script for the four settings that manufacture fake failures

**Read** the job script whole if it is short, otherwise **Grep** it for the strings the **Job resource and retry** slot
names. That slot's retry half is none of the four settings below: copy the policy it states straight into `retry`, and
take the directory a retry writes into from the attempt component step 5 classified.

- **Resources.** Under-requested wall clock has the job killed after its last line was flushed, so the summary says
  fail and the log looks perfect — the exact case `dv-regression-triage-routing` warns about. Under-requested memory
  kills it mid-line instead, which reads as a design hang; the two are told apart by whether the last line is complete.
- **Where the verdict comes from.** **Write `pass rule` from what the script does**, not what it ought to do:
  `log-marker` when the summary matches the profile's **Pass marker** in the log, `exit-status` when it uses the
  wrapper's exit code, `unknown` when neither is legible. `exit-status` is itself a finding — a wrapper ending in a file
  copy exits cleanly after a failed simulation.
- **Copy-back.** If the job works in node-local scratch, the log and the database must reach the kept storage the
  profile's **Coverage output** fact names before the job exits, and a failed copy must be loud.
- **Environment.** A farm job inherits none of an interactive profile. Anything set only in one person's shell is
  absent — which is why a regression can work for its author and nobody else, and keep working until they leave.

**Handoff.** Ask the engineer to submit one job from each tier and to give you the path of the log and the path of the
coverage directory it actually wrote, then compare those against the expression classified in step 5. That comparison
is the only thing that turns the hypothesis into a finding.

### 7. Write the tiering block, one per tier

Every field comes from a **Read** window or a Grep hit already produced; leave a field empty rather than filling it.

```
tier      : <the tier's name, exactly as our lists spell it>
answers   : <the one question a red result here settles, and what it blocks>
tests     : <n rows read of m the list holds, or "at least n, truncated">
contains  : <the tier it should be a superset of, and any test missing from it>
seeds     : fixed | random-recorded | unrecorded | mixed
budget    : <the tier's wall-clock budget> against <summed per-test seeds x runtime, as a labelled range, or unmeasured>
cov mode  : on | off | mixed
cov dir   : <the expression, each component marked scope, run or noise>
cov merge : <what the merge reads, and what it does with an unreadable or mismatched database>
retry     : <the policy, and the directory a retry writes into>
resources : <memory, wall clock and queue requested> and <what the scheduler does on exceed>
pass rule : log-marker | exit-status | unknown
findings  : <the defects, most expensive first, each with a file and a line>
coverage  : <n of m tiers read from their lists; which files were never opened>
```

`seeds`, `cov mode` and `pass rule` are local to this skill, so they are compared only against this table. Sign-off
evidence is the profile's **Sign-off** fact — quote it beside the sign-off tier's block, and if the tier whose coverage
sign-off reads is not the one that fact names, that mismatch is the page's top finding.

## Gotchas

- **A pre-merge tier with three known failures is not a gate.** The cost is not the three; it is that nobody reads the
  result any more, so the fourth arrives unnoticed and merges. Waive by name with an owner and a date, or remove.
- **Coverage merges as a union, not a sum.** A database merged twice adds no new bin, but hits per bin accumulate: a
  bin needing more than one hit can cross on the duplicate alone, and a doubled pass count hides a retry. Look in the
  counts, not the number.
- **Automatic retry hides flakiness by design.** One test in twenty failing and passing on the second attempt reports
  as all green. Retries are reasonable; unrecorded retries are how an intermittent survives to sign-off.
- **A node-local scratch directory disappears when the job ends**, and the copy back is the step nobody instruments.
  The tell of a silent copy failure is a complete summary beside an empty coverage area.
- **Tens of thousands of sibling run directories is a filesystem problem, not a naming preference**: listing turns
  slow, some globs truncate, and a truncated glob hands the merge a subset with no error at all. Shard one level.
- **The tier a test lands in is chosen at the end of a long day**, which is why containment is read from the rows.

## Human verification — what a wrong answer looks like

Before committing any of this, check:

- every tier row cites the file its membership was read from, truncated Greps are labelled "at least n, truncated", and
  containment was checked by comparing test names rather than by trusting a tier column
- no seed count is a round number with no source, and `seeds` is `random-recorded` only where the summary really does
  record the drawn seed — any `mixed` on `seeds` or `cov mode` names the rows that disagree
- `pass rule` describes what the job script does today, not what it ought to do, and an `exit-status` or `unknown`
  reading also appears in the findings line, since either is a defect and not a neutral reading
- every component of the coverage directory expression is labelled scope, run or noise; the build tag is in scope; and
  every component that varies per run is labelled `run` — test name, seed and attempt at minimum, so a *missing* run
  component is the defect, never an extra one. A retry able to overwrite its own original is a defect while all green
- the budget line is a summed, labelled range built from runtimes the engineer supplied, or says unmeasured — never one
  runtime multiplied across the tier; the `coverage` line says how many tiers were read and what was never opened

A wrong answer is a tidy three-tier table with confident seed counts, produced without opening a single list. The next
most common declares the naming healthy because last week's merge succeeded: a merge matching nothing succeeds too.

## Done when

Each tier has one question, one budget, one action on red, a seed policy sourced per test, and a directory expression
whose scope, run and noise components are named — and what you did not read is written down beside it.
