---
name: dv-tool-release-behaviour-diff
description: Compare a candidate tool build's output against the reference build's on the same testcase, normalise away path, date, host and seed noise, cluster what survives, and classify each cluster as noise, an intentional change, or a regression. Use when a new tool build changes results against the previous one, when a customer testcase passes on the old build and fails on the new one, when you are asked whether a difference is real before a release goes out, or when the release notes need checking against what the tool actually printed.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Cross-Release Tool Behaviour Diff: Noise, Intentional Change, or Regression"
  semiskill-function: design-verification
  semiskill-role: eda-product-validation-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.2.1
  semiskill-review-by: 2027-09-11
  semiskill-tags: tool-release, regression, validation, diff, normalisation, release-notes
---

# Cross-Release Tool Behaviour Diff

Every tool release changes something, and almost none of what a comparison shows is it. Install roots
move, so every absolute path differs; timestamps, hosts and elapsed figures differ on principle;
collections print in whatever order the run gathered them. Buried in that is the handful of real
differences, and the two expensive mistakes are symmetrical — filing noise as a regression, and
waving a real behaviour change through because the first fifty hunks were noise.

The output is **a small set of classified clusters**, each one noise, an intentional change or a
regression, each with the line that proves it, plus a coverage line saying how much of the difference
was actually opened. Not a re-print of the comparison.

## When to use something else

This skill compares **two builds of a tool on one testcase**. It never explains a failure by itself.

- One untriaged failing simulation log, under one build — `dv-sim-log-first-error`.
- A night of failures to sort and route before any pair is compared — `dv-regression-triage-routing`.
- A build that failed to compile or elaborate on either side — `dv-build-filelist-hygiene`.
- A cluster already classified here as a regression, now needing to be shrunk into something the
  tool's R&D owner will accept — `dv-minimal-reproducer`. That is the normal next step out of here.
- A cluster classified here as `change: regression` that the tool's owner disputes, where the
  argument has become *which behaviour the language or protocol standard requires* rather than
  whether the behaviour changed — `dv-cross-tool-mismatch-adjudication`. It names this skill as its
  own upstream for exactly that handover, so the route runs both ways.
- A whole nightly re-baselined across a tool bump — pass rate, coverage and performance over many
  tests, not one pair of runs on one testcase — `dv-tool-version-migration`. Come back here with the
  single pair it isolates.
- A register mismatch that appeared on a new build — classify it here first, and take it to
  `dv-ral-bringup` only once the cluster is `class: design`.
- You cannot find where either run's output landed — `dv-repo-orientation`.

## Fill this in for our team

Six facts this procedure spends are pack-wide. They live **once**, in `_shared/team-profile.md`,
and are read from there rather than re-asked here.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Run identity** | step 2 — confirming both sides ran the same thing |
| **Pass marker** | step 2 — the side that reached a clean end |
| **Fatal markers** | step 2 — telling a side that ran to a real failure apart from one that was cut short |
| **Infra markers** | step 2 — telling an environment abort apart from either of those |
| **Area to owner map** | step 9 — the owner of a `class: design` cluster only, never a tool change |
| **Rerun convention** | step 10 — the repeat line in the handoff |

Nine facts are specific to a release comparison, so they are asked here and nowhere else.

| Slot | What to fill in | Who knows |
|---|---|---|
| Builds under comparison | [[FILL: which build is the reference and which is the candidate, and the banner line each one prints to identify itself inside its own output]] | release owner |
| Comparison run areas | [[FILL: where the reference run's output and the candidate run's output are kept for this comparison, and how long each survives]] | validation lead |
| Diff artifact | [[FILL: whether our flow writes a textual comparison file for a pair of runs, what produces it, where it lands, the marker string that opens one changed hunk inside it, and whether a hunk carries each side's own line numbers or only the comparison file's]] | validation lead |
| Volatile fields | [[FILL: the fields our output carries that differ between two runs of the same testcase regardless of build — timestamps, host, run directory, process id, elapsed and memory figures, licence lines]] | validation lead |
| Result vocabulary | [[FILL: the strings our tool prints for a per-check outcome that a comparison may treat as a result, and the strings that are progress chatter rather than a result]] | tool owner |
| Release notes | [[FILL: where the candidate build's release notes or change list live, whether they are a file that can be read, and how one change is keyed]] | release owner |
| Accepted differences | [[FILL: where we record a behaviour difference already accepted between these two releases, and how each entry is keyed]] | validation lead |
| Tool component owner map | [[FILL: how we map a changed behaviour to the tool component owner who takes it, what that map is keyed on, and whether it is a file that can be read or a page a person must be asked]] | validation lead |
| Build selection | [[FILL: how someone selects one specific tool build for a run — describe it; leave blank rather than guessing]] | validation lead |

Five of those rows sit next to a pack-wide fact and are **not** it. **Comparison run areas** is
narrower than the profile's *Log location*: that row says where logs land in general, this one names
the two areas kept for this one pair and how long each survives, which is what decides whether the
comparison is repeatable next week. **Accepted differences** is not the *Known-issue list*: that
records bugs, this records behaviour changes already signed off between these two releases, and
filling one from the other turns a signed-off change into an open bug. **Tool component owner map**
is not the *Area to owner map*, which is keyed on design hierarchy or test name and routes design
bugs; step 9 spends both, on different clusters, and says which one each `owner` came from.
**Result vocabulary** is not the profile's *Fatal markers*: those are what the flow prints when a run
fails, and step 2 spends them to decide how each side ended; this row is the per-check outcome
vocabulary step 3 compares between the two sides, and it includes the outcomes of checks that
passed. **Volatile fields** overlaps `_shared/failure-signature-schema.md`'s *Extra values to
normalise* without being it: the schema's list makes one failure message stable across runs, this one
makes two whole outputs comparable across builds. Check both; copy neither.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented banner string, hunk
marker or run area sends the comparison down the wrong file and still produces a confident table.

## Retrieval budget — read this before opening anything

Two outputs of hundreds of megabytes, and a comparison file that can be larger than either. Reading
any of them whole is impossible.

1. **Grep, Read and Glob work on files on disk.** They cannot search a comparison pasted into the
   conversation. Ask for the path that text came from, or ask for it to be saved and be given the
   path. Until one exists you may read the pasted lines by eye — say so, and mark every cluster
   provisional.
2. **The agent cannot produce the comparison.** Read, Grep and Glob open files; they do not diff two
   of them. Either the flow already wrote the file the **Diff artifact** slot names, or the comparison
   is the coarser marker-by-marker one in rule 4. Say which you did.
3. **Locating costs two Globs**, one per side, against the **Comparison run areas** slot. Never Glob
   from the repository root.
4. The whole ledger, and nothing outside it: **two Globs** in step 1, one per side; **two Greps** in
   step 2, one per side, each alternating five strings — the banner, the run-identity string, the
   pass marker, the fatal markers and the infra markers; **one Grep** of the comparison file in
   step 3 for the hunk marker — or **two**, one per side for the **Result vocabulary** strings, when
   there is no comparison file; **six windowed Reads** of about 60 lines in step 5; **three Greps**
   of the release notes in step 7; **two Greps** of the accepted-differences list in step 8; **two
   Greps** of whichever owner map step 9 selects. Steps 4, 6 and 10 open nothing new.
   That is **ten Greps** where a comparison file exists and **eleven** where there is none, six Reads
   and two Globs either way. Both are ceilings, not targets — step 7 spends nothing if the release
   notes are not a file on disk, step 8 nothing if no cluster came out `change: regression`, step 9
   nothing if the owner map is a page a person must be asked. Say which you did not spend, and why.
5. If the step 3 Grep returns more than about 200 hunks — or, on the marker-only path, more than
   about 200 result lines on a side — one pass cannot classify this. Cluster six, report the number
   you did not open, call the rest unclassified — do not widen the budget to meet the artifact. The
   same 200-hit ceiling narrows any other Grep before it is read around.
6. **Stopping rule.** When the six windowed Reads are spent, stop. A seventh window is how a
   comparison session becomes a debug session on the wrong build.
7. **State the coverage** — "6 of 214 hunks opened; the other 208 share the two path prefixes
   normalised in step 4 and are unexamined". On the marker-only path there are no hunks, so count
   differing result lines instead — "4 of 37 differing result lines opened" — and name the unit you
   counted in. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Establish what you are actually comparing, and get it onto disk

If the comparison arrived pasted rather than as a path, resolve that first — budget rule 1.

Use **Glob** against the **Comparison run areas** slot, once per side. You are looking for one of two
things, and which you find changes everything after it:

- **The comparison file** the **Diff artifact** slot names. Best case: something outside this
  procedure already aligned the two outputs, and step 3 can count hunks.
- **Two run outputs and no comparison file.** Ask the engineer to produce the comparison with
  whatever our flow uses and to give you the path it was written to. If that is not available today,
  the comparison degrades to marker-by-marker: you can compare the **Result vocabulary** lines on
  each side and nothing else, which finds changed results and misses changed detail. Record that as
  the diff source and say so in the coverage line.

Never read a missing comparison file as "no differences". Absence of an artifact is not evidence.

### 2. Prove the two runs are comparable before reading a single difference

The step that gets skipped, and the one that invalidates everything after it. Spend **one Grep per
side** — two in total — each pattern alternating five strings: the banner from the **Builds under
comparison** slot, the profile's Run identity string, the profile's Pass marker, the profile's Fatal
markers and the profile's Infra markers. Then ask three questions in order:

- **Are the two banners the two builds you meant?** A comparison against whatever build the
  environment happened to select is the most common wasted afternoon here. Quote both verbatim.
- **Is everything except the tool the same** — design revision, testcase, seed, options? If anything
  else moved, this is not a tool comparison: record `input parity: differ`, name what else changed,
  and stop. Two variables, no conclusion.
- **How did each side end?** A missing pass marker means only that the side did not reach a clean
  end. It does **not** mean the output was cut short, and the three ways of not finishing are not
  interchangeable. Read them off the markers the same Grep already returned, per side:
  - **Pass marker present** — the side ran clean.
  - **No pass marker, a fatal marker present** — the side ran to a real failure. This is the case
    the skill exists for: old build passes, new build fails. The lines after that fatal marker are
    the behaviour change and are usually the highest-ranked cluster in step 6. Keep every one of
    them. Writing them off as a kill artefact discards the finding the comparison was run to get.
  - **No pass marker, an infra marker present** — licence, queue, host or disk. The run stopped
    before it finished exercising the build, so the tail is an artefact of the environment and no
    cluster drawn from it is trustworthy until the side is rerun.
  - **No pass marker, and neither a fatal nor an infra marker** — the side stopped with nothing
    saying why: killed, timed out, or still being written. Only here is every "removed" line past
    the last line the two sides share an artefact of the kill rather than a behaviour change.

  Record the answer for each side in `completion` in those words, and if the two sides ended
  differently, say both. Where the profile's Fatal markers or Infra markers slot is unfilled, you
  cannot separate the last three cases: say "did not finish, cause not distinguishable" for that
  side rather than picking one, and treat its tail clusters as provisional.

If the run-identity strings cannot be matched to each other, record `input parity: unknown` and treat
every cluster as provisional. That is an honest report; a cluster table over unmatched runs is not.

### 3. Measure the size and shape of the difference before opening it

One **Grep** of the comparison file for the hunk marker from the **Diff artifact** slot. What you want
is the count and the line numbers, not the content.

Where there is no comparison file, this is instead one **Grep** per side for the **Result vocabulary**
strings — outcome strings only, never the progress chatter, whose wording changes between releases
for reasons nobody will care about. Compare the two result lists by eye.

Let the count set expectations. A handful of hunks is a normal release; several hundred almost always
means one systematic difference — an install root, a date format, a reordered collection — repeated
per line, and step 4 collapses most of it.

### 4. Normalise, on paper, before clustering anything

Take the **Volatile fields** slot and strike every one of those fields out of both sides of each hunk
*before* deciding it is interesting. In practice:

1. Absolute paths → keep the base name. The install root moved; that is not a behaviour change.
2. Dates, wall-clock and elapsed times, memory figures, process ids, hosts, licence lines → drop.
3. Run directory names, and any identifier carrying a run number or a seed → drop.
4. Source line numbers inside a message → drop the number, keep the message, **unless** the message
   is about that line's content.
5. Ordering: a block holding the same lines in a different order is one cluster, not one per line.

What survives is the comparable part. This costs no tool calls — it applies to the step 5 windows.

### 5. Cluster what survives

Spend the six windowed **Reads** on hunks that look **unlike each other**, taking line numbers from
step 3 — never on six consecutive hunks, which usually belong to one cluster and buy one fact for six
windows. Step 3 deliberately did not read hunk content, so choose the spread from what it *did*
return: the first hunk, the last, and four spread evenly across the line numbers in between — or,
where the hunk marker line itself carries a file or phase name, four marker lines that name
different ones.

**On the marker-only path there are no hunks**, so the six Reads open something else: a window
around each **Result vocabulary** line whose outcome differs between the two lists compared by eye in
step 3, on whichever side carries it, up to six. Everything below reads the same with "differing
result line" in place of "hunk", including the coverage count — report "4 of 37 differing result
lines opened", never a hunk figure you do not have.

Group by the normalised pair: identical normalised before-and-after text is one cluster. Give each
cluster the smallest `where` that still separates it from its neighbours — the tool phase or the
check that printed it, not the file it landed in.

A cluster whose normalised before and after are **identical** is noise the normalisation caught. Say
so and move on; it is the cheapest classification available, and it is most of the count.

### 6. Rank the clusters, before anything else spends a Grep

This step opens nothing. It sits here, ahead of every step that says "in rank order", because the
remaining Greps are rationed and something has to decide which clusters get them.
**Rank on blast radius, not on hunk count.** In order:

1. A **changed result** — a check outcome, a count, a compared value that differs.
2. A **check that stopped firing** on the candidate build. This outranks one that started, because a
   new message gets read and a missing one silently removes coverage nobody notices for two releases.
3. A **message whose meaning changed** — same check, different claim about the design.
4. A **message whose wording changed** with its meaning intact.
5. Everything the step 4 normalisation already collapsed. These rank last by construction.

A cluster of 400 hunks that is one moved install root ranks below a single-hunk changed result. Write
the rank order down before step 7; every "in rank order" and "highest-ranked" after this reads off
this list, and if two clusters genuinely tie, rank the one with the smaller `where` first — it is the
one that can be handed to an owner.

### 7. Classify each cluster

Every cluster gets exactly one `change` value, plus the `change basis` that carries it. Every bullet
below states its own basis, so two engineers classifying the same cluster write the same field:

- **`change: noise`** — the normalised pair is identical, the difference sits entirely inside a
  **Volatile fields** entry, or the block was merely reordered.
  *Basis:* which step 4 rule collapsed it, by its number — "step 4 rule 1, install root".
- **`change: intentional`** — a release note for the candidate build describes it. Use **Grep** on the
  **Release notes** file for the cluster's distinctive token, in the step 6 rank order, three
  clusters at most.
  *Basis:* the note's key, exactly as the notes key it. If the notes are not a file on disk this Grep
  cannot happen — hand the cluster list to whoever can read them, and mark every cluster
  `change: unclassified` until the answer comes back.
- **`change: regression`** — behaviour changed, no note describes it, and it matters: a result that
  flipped, a check that stopped firing, a message that changed meaning.
  *Basis:* the before-and-after line pair that shows the change, each with its file and line, **plus
  the named lists that were searched and did not hold it** — the release notes, and after step 8 the
  accepted-differences list. Name any of those that was not searched, and why. A basis that says only
  "changed" is the field being filled in by two people two ways.
- **`change: unclassified`** — anything else. A real answer, and the right one far more often than
  people expect. A cluster is never a regression by elimination.
  *Basis:* the named reason the classification could not be reached — "release notes are not a file
  on disk", "no token distinctive enough to Grep on", "hunk not opened, the six Reads were spent",
  "run identity unmatched, every cluster provisional". Never leave it empty; empty reads as untried.

Set `class` separately, because it answers a different question — who the change belongs to, not
whether it was intended. `class: design` when the candidate build is correctly exposing a defect in
**our own source**; a new warning about an uninitialised variable is the classic case and belongs to
the source owner, not the tool. `class: infrastructure` when the difference is environment or flow —
a different install, licence path or working directory. `class: unknown` when it settles neither way,
which is where most regressions sit until R&D looks at them.

### 8. Check the regressions against what is already accepted

Only clusters marked `change: regression` earn this step. Use **Grep** on the **Accepted differences**
list for each one's distinctive token — two Greps, so the two highest-ranked by step 6. A hit means it
is already signed off between these two releases: move it to `change: intentional` and make the
accepted-difference key its `change basis`, exactly as that list keys it.

If that list is not a file on disk, or the slot is unfilled, say the check did not happen — in the
`change basis` of every regression, not only in prose. Do not call a difference new because you did
not find it in a list you never opened.

### 9. Name an owner for each cluster, or a named question instead

The **Tool component owner map** slot says what the map is keyed on and whether it is a file that can
be read. Take each cluster's key from its `where` — the tool phase or check the difference appeared
in — and, if the map is a file on disk, use **Grep** on it for that key. Two Greps, so the two
highest-ranked by step 6; everything below that gets a blank `owner` and says so.

- A single hit fills `owner`.
- Several hits, or a key that only partly matches, fills `owner` with the candidates and a question:
  "candidates A or B — which of you owns <where>?" Two named candidates beat one confident guess.
- No hit, or a map that is a page a person must be asked rather than a file, leaves `owner` blank and
  puts the same question in the handoff at step 10.

`class` decides **which** map, and the two are not interchangeable. `class: infrastructure` or
`class: unknown` means a tool behaviour change, which takes the **Tool component owner map** whatever
its `change` value. `class: design` means our own source exposed by the new build, so that owner comes
from the profile's Area-to-owner map — keyed on design hierarchy or test name — and the cluster leaves
by the design route in "When to use something else". Record which map each `owner` came from: a tool
change sent down the design map lands on someone who cannot act on it, in a report that looks complete.

### 10. Write the report and hand back what needs a run

One header block, then one block per cluster in rank order.

```
comparison  : <reference banner> versus <candidate banner>, both quoted from their own output
testcase    : <what was run, identically, on both sides>
run id      : <the run identity of each side, per the profile>
input parity: same | differ | unknown
completion  : <which side carried the pass marker, and which did not>
diff source : <comparison file path, or "result markers only, no comparison file">
clusters    : <count>
coverage    : <n of m hunks opened; what the remainder is and why it was not opened>
```

```
cluster     : C1
where       : <the tool phase or check the difference appears in>
before      : <verbatim reference line, with file and line>
after       : <verbatim candidate line, with file and line>
normalised  : <the same pair after step 4 — identical means noise>
change      : noise | intentional | regression | unclassified
class       : design | infrastructure | unknown
change basis: <per the bullet in step 7 for whichever change value this cluster got>
owner       : <name, plus which of the two maps it came from; or blank plus candidates and a question>
signature   : <phase>|<kind>|<where>|<what>, per the shared schema — regressions only
to repeat   : <the profile's rerun convention plus the build selection slot, or empty>
notes       : <anything the next person would otherwise have to rediscover>
```

`signature`, `class`, `owner`, `run id`, `to repeat` and `notes` are the field names
`dv-sim-log-first-error` and `dv-minimal-reproducer` already use, so a cluster handed on for shrinking
keeps its vocabulary; the rest are local to this skill. Fill `signature` from
`_shared/failure-signature-schema.md` — same field order, same normalisation rules — and only for a
regression; a noise cluster has nothing to sign.

`change basis` is deliberately not the pack-wide name for a citation: `_shared/handoff-vocabulary.md`
locks that name to mean a file path and line behind every claim in the block, which `before` and
`after` already supply here. This field answers a different question — *why was it classified that
way* — so it takes a name of its own, qualified with the axis it explains.

Take `to repeat` from the profile's **Rerun convention** together with the **Build selection** slot,
which is the half the profile does not record. If either is unfilled, leave the field empty; an
invented way of selecting a build will be repeated by everyone who reads the report.

Then state the handoffs plainly rather than implying them: ask the engineer to repeat the top-ranked
regression on both builds and give you both log paths; ask the tool component owner step 9 named
whether the top `change: unclassified` cluster was intended; where step 9 left `owner` blank, put the
"who owns <where>?" question in the handoff with the candidates it found; and, where the release notes
are not a file on disk, ask their owner to compare the cluster list against them.

## Gotchas

- **A new build usually arrives with a new install root**, so every absolute path differs and the raw
  hunk count is meaningless until step 4 has run. "1,400 differences" is nearly always one moved
  path prefix.
- **Same seed does not mean same stimulus across builds.** Constraint-solver behaviour is generally
  not guaranteed stable between tool releases, so identical source and identical seed can legitimately
  produce different randomised values. Check what the vendor actually claims before calling re-ordered
  stimulus a regression — and before calling it noise.
- **Elapsed time and memory always differ** and must never form a cluster. A performance regression is
  a separate measurement with repeats on a quiet host; one pair of numbers measures the host.
- **A message that disappeared is more dangerous than one that appeared.** A new warning gets read; a
  check that quietly stopped firing looks like an improvement and removes coverage nobody notices for
  two releases. Rank removals above additions.
- **Reordering is not a change.** Tools print unordered collections — analysed files, coverage bins,
  warnings gathered in parallel — in whatever order the run produced them, and a reordered block
  yields one hunk per line. Compare those as sets before treating any of it as content.
- **Same message at a different line number is usually noise; the same message from a different
  instance path is not.** Source line numbers move with any edit; hierarchical paths do not, so a
  message that moved instance is a real change in where the tool thinks the problem is.
- **A pass on both sides is not "unchanged".** Verdicts are the coarsest thing either run prints. A
  testcase can pass twice while half of it stopped being exercised — compare counts, values and which
  checks ran.
- **Optimisation and X-propagation changes arrive as data, not as errors.** A new optimisation default
  can change what an uninitialised variable reads as, surfacing as a value mismatch far from anything
  the notes mention. That is `class: design` — the build exposed a real defect in our source, and
  filing it against the tool costs a release cycle.
- **Zero differences on a testcase that exercises nothing proves nothing.** If the reference run never
  reached the area the release notes changed, a clean comparison is a statement about the testcase.
  Say which areas the pair actually touched.
- **Release notes are a claim, not a record.** Intentional changes get left out of them routinely, so
  "no note describes it" is one piece of evidence, not a verdict. That is what `change: unclassified`
  is for.

## Human verification — what a wrong answer looks like

Before sending the report, check:

- both banners are quoted **verbatim from the outputs themselves**, not from what someone said they
  ran, and `input parity: same` only because each side's run identity was actually matched
- no cluster survives whose normalised before and after are identical, and none is built on elapsed
  time, memory, a host name, a run directory or a path prefix
- every cluster has a non-empty `change basis`, and it is the one step 7 specifies for that `change`
  value — a release-note or accepted-difference key for `intentional`, a numbered step 4 rule for
  `noise`, a line pair plus the named lists searched for `regression`, a named unavailable lookup for
  `unclassified`. A basis that just restates the classification is the field not being filled in.
- nothing is `change: regression` purely because no note was found — that is `change: unclassified`
- `class: design` appears only where the difference is our own source being exposed, never as a
  synonym for "the tool changed something"
- every `owner` says which of the two maps it came from, and no `class: design` cluster was routed
  through the tool component owner map or vice versa; a blank `owner` carries the question instead
- the cluster blocks are in the step 6 rank order, and a 400-hunk normalised cluster is not above a
  single changed result
- `to repeat` is either built from the profile's rerun convention plus the build-selection slot, or
  left empty
- the coverage line is present, gives both numbers, and says whether a real comparison file or only
  the result markers were compared

A wrong answer is a long table of clusters that are all one moved install root, with the single
changed result sitting at row 40 unremarked. The second-most common one names a regression on a pair
of runs whose design revision also moved, which no amount of clustering can rescue.

## Done when

Every cluster carries one classification, the `change basis` step 7 specifies for it, and one owner or
one named question, and the coverage line says how much of the comparison was opened and how much was not.
