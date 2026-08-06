---
name: dv-crypto-kat-coverage-audit
description: Audit whether every algorithm, mode and key-size combination the datasheet claims is backed by a known-answer vector file that a test actually loads and the regression actually schedules, and report the gaps as a ranked table. Use when a crypto block is heading for sign-off or a customer release, when someone asks which datasheet rows have no known-answer test behind them, when the vector directory has grown and nobody can say what is wired in, or when an audit or a customer questionnaire asks for the known-answer coverage evidence.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Known-Answer-Test Coverage Audit Against the Claimed Algorithm Matrix
  semiskill-function: design-verification
  semiskill-role: security-verification-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-02-19
  semiskill-tags: crypto, known-answer-test, vectors, algorithm-matrix, coverage-audit, sign-off, gaps
---

# Known-Answer-Test Coverage Audit Against the Claimed Algorithm Matrix

A crypto block's datasheet is a list of promises — these algorithms, these modes, these key sizes.
Coverage against those promises is not one fact but three independent ones: a vector file exists, a
test loads it, and the regression schedules that test. Each of the three fails on its own, silently,
and from the datasheet's side all three failures look identical — which is why "we have vectors for
that" is so often true and so often worth nothing.

The output is **one row per claimed combination**, each carrying the file, the test, the schedule
entry and the applied count behind it, plus a coverage line saying how much of the matrix that rests
on. Not a list of the vector directory.

**What this does not do.** It counts and cross-references text already on disk. It cannot start a
simulation or a regression, cannot open a datasheet that is a PDF or a spreadsheet, and cannot judge
whether a vector is cryptographically correct — that is the vector publisher's job, not this audit's.
Every step needing one of those ends in a named handoff and says so.

## When to use something else

For one failing known-answer test, start with `dv-sim-log-first-error`. For a whole regression's
worth of failures to sort and route, use `dv-regression-triage-routing`. Once this audit has named a
gap and someone has to *write* the missing directed test and its traceability row, that is
`dv-compliance-test-authoring` — this skill finds the hole, that one fills it. For holes in a merged
functional coverage report rather than in a claim matrix, use `dv-coverage-hole-closure`. For which
of a configurable IP's parameter combinations deserve regression at all, use
`dv-config-space-coverage`. And if you cannot yet say where the test list or the run area live, do
`dv-repo-orientation` first — this audit assumes that map already exists.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Claim matrix | [[FILL: which document holds our claimed algorithm, mode and key-size matrix, its path and revision, and whether it is plain text that can be read from disk or a format that cannot]] | IP product owner |
| Combination key | [[FILL: how we spell one algorithm-mode-size combination in the matrix, in vector file names, and in test names, so the three can be matched to each other]] | crypto DV owner |
| Vector location | [[FILL: where our known-answer vector files live in the tree and what file extension they use]] | crypto DV owner |
| Vector record start | [[FILL: the string that begins one vector record in our vector files, and the string that separates one vector set from another inside a single file]] | crypto DV owner |
| Vector wiring | [[FILL: how a test names the vector file it loads — a plusarg, a config field, a package constant, or a scan of a directory]] | DV infra |
| Test schedule list | [[FILL: which file decides the tests a regression actually schedules, and how a test is named in it]] | DV infra |
| Applied-count marker | [[FILL: the string our known-answer test prints reporting how many vector records it applied]] | crypto DV owner |
| Waiver record | [[FILL: where we record a claimed combination deliberately left without a known-answer test, and what evidence stands in for it]] | DV lead |

Log location is a pack-wide fact and lives in `_shared/team-profile.md` — read it from there rather
than re-asking. Two rows above are deliberately **narrower** than profile rows and are not the same
fact:

- **Test schedule list is narrower than the profile's Regression summary.** The profile records where
  per-test *results* land; this asks which file decides what gets *scheduled*. On most flows they are
  different files, and treating them as one is how an audit "confirms" a test ran by finding it in a
  list that only ever listed it.
- **Applied-count marker is narrower than the profile's Pass marker.** The pass marker says the run
  reached the end. This is whatever the known-answer test prints about how many records it applied. A
  run prints the pass marker perfectly happily having applied zero vectors.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented vector extension or
record layout produces an audit that counts nothing and reports full coverage, which is strictly
worse than reporting that the audit could not be done.

## Retrieval budget — read this before opening anything

Vector sets are tens of megabytes of hex, and a test tree has thousands of files. Nothing here needs
a vector to be read. Work in this order and stop when the row list is settled:

1. **Grep and Read work on files on disk.** The claim matrix is very often a PDF, a spreadsheet or a
   published web page, and none of those can be read. Resolve it to a readable file, or treat every
   claim row as supplied by a person, say so, and mark the whole audit provisional.
2. **Never open a vector file with Read to count its records.** Ask Grep for match counts per file
   instead of for content. If this runtime's Grep has no count mode, ask it for file names only and
   record that you have presence, not counts — then say that in the coverage line.
3. The whole budget: **one Glob** of the vector directory; **at most six Greps** — record counts
   (step 3), wiring (step 4), schedule (step 5), applied counts (step 6), waivers (step 7), and one
   spare for re-anchoring whichever of those came back too wide; and **at most four bounded Reads of
   about 60 lines** — the claim matrix, one representative vector file's head, one wiring site, one
   schedule site.
4. If the Glob returns more than about 200 vector files, do not enumerate them one by one. Group them
   by the **Combination key** convention, audit the groups, and say in the coverage line that files
   were grouped rather than listed.
5. If any Grep returns more than about 200 hits the pattern is too broad — anchor it on the file
   extension, or on the record-start string at the beginning of a line, before reading anything. That
   retry is the spare Grep in rule 3; there is not a second one.
6. Stopping rule: when the budget is spent and rows remain unsettled, stop and report the rows that
   are settled, the rows that are not, and the one thing still needed. Never fill a row from a file
   name alone — a file named for one combination is evidence of a name, not of a vector.
7. State what you actually covered: how many claim rows came from a readable file and how many from a
   person, how many vector files were counted and how many grouped, and whether any applied count
   came from a real log. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the claim matrix, then expand it into rows

Open the **Claim matrix** slot's file with one bounded **Read** if it is readable text. If it is a
format that cannot be read, say that in the first line of the output and **ask the IP product owner
or the technical writer to save the matrix as plain text and give you the path**, or to read the rows
out to you. A row that came from a person is recorded as such, and every finding resting on it is
provisional.

Then expand. A claim row in a datasheet is almost never one combination:

- each algorithm times each mode times each key size is a separate row
- **encrypt and decrypt are two rows**, not one, and so are sign and verify
- an output length, tag length or digest length named as an option is its own row
- a row marked legacy or deprecated is still shipped, so it is still a row

"AES 128/192/256, ECB/CBC/CTR/GCM, both directions" is not one claim. It is twenty-four. Write each
row as one canonical string using the **Combination key** convention, because the next four steps
join on that string, and record which matrix line each row was expanded from.

### 2. Locate candidate vector files — Glob, never Read

One **Glob** under the **Vector location** path with that slot's extension. Match file names to rows
using the **Combination key**, and record three groups: rows with at least one candidate file, rows
with none, and files matching no row at all. That third group is worth reporting on its own — each
one is either an undocumented capability or a dead file, and nobody knows which until asked.

A name match is a candidate. It is never a confirmation.

### 3. Count records without reading vectors — Grep

One **Grep** for the **Vector record start** string across the vector directory, asking for counts
per file rather than content. That gives every candidate file a record count in a single call.

The count that matters most is zero. A placeholder file — a header, a licence banner, and no records
— exists, Globs, Greps, loads, and passes. It clears every other step of this audit and covers
nothing.

Spend one bounded **Read** of about 60 lines at the head of one representative file to confirm the
record-start string really is what the slot says, and to see whether a single file carries several
vector sets separated by that slot's set separator. If it does, the per-file count is a total across
sets and cannot be split by counting alone — say so rather than attributing the whole count to one
combination.

### 4. Find what actually loads each file — Grep

One **Grep** across the testbench for whatever the **Vector wiring** slot names — the plusarg, the
config field, or the constant. A file no test names is present-and-unwired, which is
`kat state: not-wired`.

If the wiring is a directory scan rather than a named file, every file in that directory is loaded
and none is named. Record that the wiring is implicit, and note that this makes the check *weaker*,
not stronger: a vector file dropped into the wrong directory is then ignored in complete silence.

Spend one bounded **Read** at the wiring site to see whether the load is conditional — sitting inside
a branch on a configuration field, a parameter, or a plusarg. **A conditional load is not coverage
until that condition is known to hold in a build somebody schedules.** Record the condition verbatim
in the row's `conditional` field.

### 5. Confirm the test is scheduled — Grep

One **Grep** of the **Test schedule list** for the test names found in step 4, written as a single
alternation so it costs one call. A test that exists in the repository and appears nowhere in the
schedule list has never run — `kat state: not-scheduled`. This is the most common gap this audit
finds and the cheapest one to fix.

Being listed is not the same as having run recently. A test scheduled only into a tier or a nightly
set that has not been launched in months is listed and idle; step 6 is what tells the two apart.

### 6. Ask for a run, then reconcile the counts

The agent cannot start a simulation, a regression, or a farm job, and must not invent what one would
have printed. **Ask the engineer to launch the known-answer tests and give you the path to the logs,
or to point you at the most recent regression's log directory**, then spend one **Grep** of those
logs for the **Applied-count marker**.

Compare the applied count against step 3's record count, per row:

- equal — the row is `kat state: covered`
- fewer — records were filtered or skipped; the row is not covered, and the difference is the finding
- zero, or no marker at all — the test loaded nothing, or the marker is not the string the slot says

If no log can be produced, every row that got this far is `kat state: not-confirmed`. Do not promote
it. Wired and scheduled means nobody has yet seen a vector applied.

### 7. Check the waivers before calling anything a gap

Spend one **Grep** of the **Waiver record** if it is a file on disk. If it is a tracker or a page,
Read and Grep cannot reach it — **ask the DV lead to query it** and mark those rows pending rather
than calling them gaps.

A waived row is `kat state: waived`. That is not the same as covered: it carries the waiver key and
the evidence the waiver names, and it stays visible in the table so that a sign-off reviewer sees it.

### 8. Write the audit table and rank the gaps

One block per claimed combination. The field names deliberately echo the handoff blocks in
`dv-sim-log-first-error` and `dv-ral-bringup` so the three read side by side.

```
combination : <one algorithm-mode-size-direction row, in the Combination key spelling>
claimed in  : <claim-matrix file and line, or the name of the person who read the row out>
vectors     : <vector file path and the record count from step 3, or none-found>
wired by    : <test or sequence file and line that loads it, or none-found>
conditional : <the config field, parameter or plusarg the load sits behind, or unconditional>
scheduled   : <schedule-list file and line, or not-listed>
applied     : <count from the applied-count marker, with log path and line, or no-log>
kat state   : covered | no-vectors | not-wired | not-scheduled | not-confirmed | waived | unknown
waiver      : <waiver key and the evidence it names, or blank>
rank        : <1 unqualified claim, 2 selectable configuration, 3 legacy row — and why>
```

Rank the gaps rather than listing them flat: a combination the datasheet claims without qualification
outranks one only reachable behind a configuration option, which outranks a row the matrix itself
marks legacy. A reviewer with an afternoon fixes the top of that list.

Then one summary block for the whole audit:

```
matrix     : <claim-matrix path and revision, or the name of whoever read it out>
rows       : <n claimed combinations, expanded from m matrix lines>
audit      : <c covered; g gaps; w waived; u unknown>
unmatched  : <vector files matching no claim row, and whether each is capability or dead file>
coverage   : <how many rows came from a readable file and how many from a person; how many vector
              files were counted and how many grouped; whether any applied count came from a log>
run id     : <the run the applied counts came from, or none>
notes      : <anything the next person would otherwise have to rediscover>
```

If a field cannot be filled from text on disk, write `?` rather than inventing it.

## Gotchas

- **A vector file in the tree is not coverage.** Existence, wiring and scheduling fail independently,
  and the datasheet cannot tell them apart. An audit that stops at the Glob reports the directory,
  not the coverage.
- **A round-trip test is not a known-answer test.** Encrypting then decrypting and comparing against
  the original passes perfectly on a design that is self-consistently wrong. The comparison has to be
  against the published ciphertext, and the decrypt direction needs its own vectors — most published
  sets ship the two directions separately for exactly this reason.
- **Key size is not the only axis with a size on it.** For an authenticated mode the initialisation
  vector length, tag length and additional-data length are separate claims. A 96-bit IV is used
  directly by GCM while any other length is first compressed through the mode's own hashing step —
  two different paths through the design, one matrix row, and a vector set that only carries 96-bit
  IVs leaves half of it untouched.
- **The interesting lengths are the ones that are not whole blocks.** For any mode that pads or steals
  ciphertext, a vector set built entirely from block-multiple lengths covers the mode's name and none
  of its edge. Check the length column before believing a row.
- **Truncated-output algorithms are separate algorithms.** SHA-512/224 and SHA-512/256 use their own
  initial hash values; they are not SHA-512 output cut short, and SHA-512 vectors do not check them.
  A matrix row per output length needs a vector set per output length.
- **One file wired into two tests is one covered row, not two.** Count distinct combinations, never
  references. Double counting is how an audit reports coverage that does not exist.
- **A skipped vector prints nothing.** A plusarg left unset, a config field at its default, an early
  return on "not supported in this configuration" — all produce a log identical to a vector that
  passed. Only the applied count separates them, which is why step 6 exists.
- **Published sets often ship more than one file class per algorithm** — a short known-answer set and
  a much longer chained or Monte-Carlo set. If only the short one is scheduled, auditing against the
  whole directory over-counts every row it touches.
- **A hard-coded expected record count goes stale silently.** When the source vector set is upgraded
  the record count changes; a test asserting the old number keeps passing while applying fewer
  vectors than the file now holds. Compare against the count you measured in step 3, not against the
  number the test believes.
- **A design's built-in self-test vectors are not this evidence.** Vectors baked into the block to
  prove it powered up correctly answer a different question from the datasheet's claim matrix, and
  quoting them in a customer questionnaire is the mistake that gets noticed in the audit and not
  before.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the row count is the **expanded** count — algorithm times mode times size times direction — not the
  number of lines in the datasheet table
- every `kat state: covered` row names a vector file, a test, a schedule entry **and** an applied
  count with a log path; three of the four is `kat state: not-confirmed`
- no row was settled from a file name alone
- a file with zero records is not sitting in a covered row
- rows whose load is conditional carry the condition verbatim, and are not covered unless that
  condition holds in a scheduled build
- the coverage line says how many rows came from a person rather than from a file, and if the claim
  matrix was never readable, nothing above it is being treated as verified
- waived rows appear in the table with their waiver key rather than being quietly dropped

A wrong answer typically reports the vector directory as the coverage, counts one file twice because
two tests load it, calls a row covered on the strength of its file name, or collapses encrypt and
decrypt into a single row and halves the real gap list.

## Done when

Every claimed combination has a row, every row has a state backed by a file and a line, and the gaps
are ranked with an owner to hand them to.
