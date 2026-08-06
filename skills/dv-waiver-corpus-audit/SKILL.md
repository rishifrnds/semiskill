---
name: dv-waiver-corpus-audit
description: Audit an accumulated lint or domain-crossing waiver corpus as a signoff artifact — count it, then find the entries that match nothing, the wildcards quietly covering violations nobody reviewed, and the duplicated and shadowed entries. Use when a new RTL drop reports zero violations and nobody believes it, when the waiver file has grown across drops and no one has read it end to end, when signoff asks how many waivers there are and why, when a violation you expected never appeared in the report, or when a waiver corpus is being inherited from another block or carried across a tool-version bump.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Waiver Corpus Audit Across RTL Drops
  semiskill-function: design-verification
  semiskill-role: static-signoff-engineer
  semiskill-level: senior-staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-09-17
  semiskill-tags: waivers, lint, cdc, rdc, static-signoff, audit, rtl-drop, exclusions
---

# Waiver Corpus Audit Across RTL Drops

A waiver corpus is the one signoff artifact that only ever grows and is never read. Every entry was
correct on the day it was written; three drops later some of them match nothing at all, some match a
great deal more than their author intended, and both kinds produce exactly the same clean report.
That is the difficulty — nothing in the report distinguishes a corpus doing its job from one that has
quietly stopped.

The output is a **counted audit** — duplicates, shadowed entries, never-matched entries, over-broad
entries and missing bookkeeping, each as a fraction of the entries actually parsed — plus **one named
proposal**. It is explicitly not a claim that the block is clean.

**What this cannot do.** It reads waiver files and saved tool reports. It cannot start the lint or
domain-crossing tool, cannot elaborate the design, and cannot re-run an analysis with a proposed
change. Every claim about what an entry *matched* therefore rests on a report a person produced and
gave you the path to, and step 2 decides what may be claimed without one.

## When to use something else

- **You are triaging today's report, not last year's corpus.** A lint report to disposition is
  `dv-lint-triage`; a clock- or reset-domain-crossing report is `dv-cdc-rdc-triage`. Both of those
  *write* entries. This one audits what they wrote once several drops have gone by, so it starts
  where they stop, and it never drafts a justification.
- The tool produced **no report at all** — a missing file, an unknown macro, an unresolved module.
  That is a build failure wearing a static-analysis costume: `dv-build-filelist-hygiene`.
- A **simulation** failed: `dv-sim-log-first-error`. A whole night of them:
  `dv-regression-triage-routing`.
- **Register-model exclusions** — the entries keeping a register or field out of the built-in
  register sequences — are a different corpus with a different consumer, and they are
  `dv-ral-bringup`'s *Exclusions* slot. Do not audit them here, and do not fill either slot from the
  other; the two are related only by the English word "waiver".
- **Coverage exclusion files** are a third corpus again, and no skill in this pack covers them. The
  four defect shapes below transfer to them unchanged; none of the slots do, because coverage
  exclusions are keyed on coverage objects rather than on rules and design objects.
- You do not yet know where any of these files live: `dv-repo-orientation` maps the tree.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Waiver corpus location | [[FILL: every waiver file our static goals read, their extensions, and which are per-block versus chip-wide]] | static signoff owner |
| Waiver entry syntax | [[FILL: what one entry looks like — the directive it opens with, which argument is the rule identifier and which is the design object, and how a comment is written]] | static signoff owner |
| Wildcard syntax | [[FILL: which characters our waiver files treat as wildcards, and whether one of them crosses a hierarchy separator or stops at it]] | static signoff owner |
| Bookkeeping fields | [[FILL: which of justification, owner, date, expiry and tracking key our convention requires, whether each is a field the tool reads or free text in a comment, and which the tool enforces]] | verification lead |
| Waiver-application record | [[FILL: whether our tool writes a per-entry hit count or a readable list of waived violations, where it lands, and whether a violation covered by two entries counts against both or only the first]] | static signoff owner |
| Unwaived report | [[FILL: where a report generated with the waiver corpus disabled lands, and whether one exists for the current drop]] | static signoff owner |
| Rule catalogue | [[FILL: where the list of rule identifiers our current tool version emits lives, and whether it is a file we can read]] | static signoff owner |
| Hierarchy evidence | [[FILL: whether our flow writes an elaborated design-hierarchy or instance list we can read, and where it lands]] | DV infra owner |
| Drop identity | [[FILL: what identifies one RTL drop for us, and where the previous drop's waiver files and reports are kept]] | verification lead |
| Waiver sign-off rule | [[FILL: what sign-off requires of the corpus itself — who approves a new entry, whether entries expire, and whether there is a ceiling on how broad one may be]] | verification lead |

Four relationships are worth stating rather than assuming. **Waiver corpus location is deliberately
broader** than `dv-lint-triage`'s *Waiver record* and `dv-cdc-rdc-triage`'s *Waiver store*: each of
those names the one store its own goal writes into, and this skill exists because a team usually has
several and audits none of them — so this row is the union, and if it turns out to name one file,
record that as a finding. **Waiver entry syntax overlaps** the format half of both those rows; fill
it once and reuse the answer. **Bookkeeping fields is wider than** `dv-lint-triage`'s *Waiver
expiry*, which asks only about expiry, and it adds the question that row does not — whether the tool
reads the field or ignores it. And **Waiver sign-off rule is narrower than** the profile's
**Sign-off** row in `_shared/team-profile.md`, which covers the block as a whole; here it is only
about the corpus. Step 9 routes on the profile's **Area to owner map**, read from there, so there is
no second copy of it above.

**If a slot is unfilled, stop and ask. Do not guess a convention.** This skill shows no example
waiver entry anywhere — an invented directive sends you Grepping for a keyword your tool never emits,
and every count after that is zero for the wrong reason.

## Retrieval budget — read this before opening anything

A chip-level corpus runs to thousands of entries across a dozen files, and the reports it applies to
are far larger again. Work in this order and stop at the cap, not at an answer.

1. **Grep, Read and Glob work on files on disk.** A waiver file or report pasted into the
   conversation cannot be searched — ask for the path, or ask for the text to be saved to a file and
   be given that path. You may read a pasted entry by eye; say that is what you did, and record the
   corpus count as unknown rather than as what you were shown.
2. **Glob for the corpus first, one directory per call** — at most **4 Glob calls**. Record paths
   only; open nothing during the survey.
3. **Count before reading.** One **Grep** per waiver file for the opening directive gives that file's
   entry count, and that is the denominator every later number is quoted against. Open at most **6
   waiver files**; name the ones you did not.
4. Read a waiver file whole only under about **300 lines**. Above that, Grep for the directive and
   **Read** bounded windows of about 80 lines around the hits. Cap the corpus at **10 windowed
   Reads**.
5. **Never open a report with Read first.** Per report at most **2 Greps and 2 windowed Reads of
   about 80 lines**, and at most **3 reports** — the current waived one, the current unwaived one,
   and the previous drop's.
6. The existence cross-checks in step 6 cost **one Grep per entry checked, capped at 30 in a pass**,
   each scoped to the single directory the entry names. Checking j entries across k directories is j
   times k Greps and exhausts the cap immediately; that is the mistake to avoid, not a target.
7. A **Grep** returning more than about 200 hits is too broad — narrow it before reading anything. A
   count that reached your runtime's limit is "at least N, truncated", never a count.
8. The ledger is roughly 4 Globs, 42 Greps and 16 windowed Reads. **Stopping rule:** stop when the
   corpus is counted, steps 4 and 5 are complete, and the 30 cross-checks are spent. A partial audit
   reported as a fraction is useful; one completed by extrapolating from the entries you did read is
   not.
9. **State the coverage.** Every count carries a denominator, and the `basis` line says which class of
   evidence the whole audit rests on.

## Procedure

### 1. Locate the corpus and count it before opening a single entry

If any of it arrived pasted rather than as a path, resolve that first — budget rule 1.

Use **Glob** against the Waiver corpus location slot, one directory per call. Then one **Grep** per
file for the opening directive from the Waiver entry syntax slot, giving the entry count per file.
Record which drop this corpus belongs to, from the Drop identity slot.

Two numbers get conflated here and must not be. The **entry count** is a property of the corpus; the
**waived-violation count** is a property of a report. One entry can cover hundreds of violations and
one violation can be covered by several entries, so the two have no reason to agree, and a report
showing them agreeing is a coincidence rather than a check.

### 2. Decide what evidence you have, because it decides what you may claim

This step comes before any analysis. Use **Glob** and the Waiver-application record and Unwaived
report slots to establish which of these you hold:

- **A per-entry hit record.** The strongest evidence, and the only one supporting entry-level claims.
  Record `basis: hit-record`.
- **A waived and an unwaived report for the same drop.** Their difference is the set of violations the
  corpus removed — a corpus-level fact with **no attribution to individual entries**. You may say how
  much the corpus is hiding, not which entry hid what. Record `basis: unwaived-diff`.
- **Only the previous drop's material.** Useful for step 7 and nothing else: `basis: previous-drop`.
- **None of the above.** Steps 4, 5 and 8 still run in full, because duplicates, shadowing, breadth
  and bookkeeping are properties of the corpus text alone. Steps 6 and 7 do not. Record
  `basis: structural-only` and **call no entry stale** — there is no evidence for it.

Where evidence is missing, ask rather than working around it: **ask the engineer to produce a report
for this drop with the waiver corpus disabled, and to give you the path it was written to**, plus the
per-entry hit record if the tool can emit one. Both are an option change on a run they already do,
and neither can be produced from here.

### 3. Normalise each entry you open into one record

Parse against the Waiver entry syntax slot, never against a guess at it.

```
rule        : <the rule identifier, verbatim as the entry spells it>
object      : <the design object the entry names, normalised>
match key   : object | signature | file-line
breadth     : exact | subtree | rule-wide | blanket
bookkeeping : <which required fields are present, and which are missing>
state       : matched | shadowed | never-matched | not-checkable
entry       : <waiver file and line>
```

Normalise `object` with the rules in `_shared/failure-signature-schema.md` — indices to `i`, absolute
paths to the base name, instance paths to the last two hierarchy levels — so entries written years
apart in different styles compare as text. Keep the raw string beside it; a proposal must quote the
raw string.

**This record is not a failure signature and must not be filed as one.** The schema describes one
observed failure in one run; a waiver is a standing exception to a rule. Reusing its normalisation
rules is deliberate, so the two artifacts sort alike; reusing its four-field shape would claim a run
this corpus never had.

### 4. Classify breadth, and rank on it

`breadth` is the risk axis and is decidable from the entry text alone. Read the Wildcard syntax slot
first — it changes every answer here.

- **exact** — one rule, one fully specified object. Can only ever cover what it was written for.
  Safest, and first to go stale.
- **subtree** — a wildcard covering a named branch. Whether it stops at the hierarchy separator or
  crosses it is the difference between "this instance's ports" and "everything beneath here,
  including what was added last month".
- **rule-wide** — no object constraint, or a pattern too general to exclude anything. The rule is off
  for the design.
- **blanket** — no rule constraint, or a whole file, block or library switched off in one line.

Rank widest first and spend the rest of the audit in that order. An entry covering one net is worth
minutes; a `breadth: rule-wide` entry is worth the afternoon, because everything it hides was hidden
without anyone reading it. Getting the wildcard rule wrong is expensive both ways: assume it crosses
the separator when it does not and you flag the whole corpus; assume it does not when it does and you
miss the only entry that mattered.

### 5. Find duplicates and shadowed entries — corpus text only, no new reading

Both run over the records from step 3 and cost nothing further.

- **Duplicate.** Two entries whose normalised `rule` and `object` are identical. Mostly harmless
  noise, and always a sign the corpus is appended to from two places — which is how the next defect
  starts.
- **Shadowed.** A narrow entry whose match set is wholly inside a broader one's. Order the containment
  test on breadth: an exact entry can be shadowed by a subtree entry naming an ancestor of its object,
  and anything can be shadowed by a rule-wide entry for the same rule.

**Settle shadowing before staleness, never after.** A shadowed entry is consulted by nothing and shows
zero hits, so it is indistinguishable from a stale one in the hit record — and the Waiver-application
record slot asks whether your tool credits a covered violation to every matching entry or only the
first, because if only the first, every shadowed entry reads as never-matched. Mark these
`state: shadowed`. Deleting one is harmless; concluding from it that the underlying violation is gone
is wrong, and that is what this ordering prevents.

### 6. Find stale entries — three kinds, three different proofs

Reachable only under `basis: hit-record`; otherwise this step is a handoff. Spend the 30 cross-check
Greps here, widest entries first.

- **Never matched.** The hit record says zero and step 5 has ruled out shadowing. The only kind
  statable without further evidence: `state: never-matched`.
- **Dead object.** The instance, module or net no longer exists. One **Grep** of the Hierarchy
  evidence slot's elaborated hierarchy or instance list settles it. With no such file, one Grep of the
  single source directory the entry names is the fallback — and much weaker than it looks, because
  paths under generate blocks and instance arrays are constructed at elaboration and never appear
  literally in source. For those, "no hit in the RTL" means nothing. Say which of the two you used.
- **Dead rule.** The identifier is not one the current tool version emits; one **Grep** of the Rule
  catalogue slot settles it where that catalogue is a readable file. Upgrades rename and split rules
  routinely, and an entry naming a retired identifier waives nothing while looking exactly like one
  that works.

Where the evidence is not on disk this is a handoff, not a verdict: **ask the static signoff owner for
the hit record, the hierarchy list or the current rule catalogue, and for the path each was written
to.** Mark those entries `state: not-checkable` and count them separately — they are neither clean nor
stale but unexamined, and the report says so in those words.

### 7. Compare against the previous drop

Use the Drop identity slot to locate the previous drop's waiver file and report — one of the three
reports budget rule 5 allows. Two comparisons repay the cost:

- **Entries added since that drop.** Read each justification. An entry added in the same drop as the
  RTL it covers is not a reviewed exception but a deferral, written to get past the gate. It is
  invisible in a single-drop audit and obvious in a two-drop diff, which is why this step exists.
- **Entries that matched then and match nothing now.** Something moved. Either a real fix, in which
  case the entry should go, or a rename that silently switched the waiver off while leaving the
  violation in place under a new name. Those look identical in the waiver file; only the unwaived
  report separates them, so name the entry and ask rather than choosing.

If the previous drop's material is not on disk, say the cross-drop comparison did not happen. Do not
substitute the age of a date field for it — a date says when someone typed, not when the entry last
did anything.

### 8. Check bookkeeping against what the tool actually enforces

Against the Bookkeeping fields slot, count entries missing each required field. Then the part that
matters more than the count: whether the tool *reads* each field or it is free text in a comment. **An
expiry the tool does not enforce is a comment**, and a corpus full of them is one where everybody
believes entries are ageing out and none of them are. Same for an owner field and a tracking key —
unenforced, they are a convention, and conventions decay silently across exactly the drops this skill
looks across.

Then check the corpus against the Waiver sign-off rule slot — approver, expiry policy, breadth ceiling
— and report breaches of it as a count separate from staleness. The two go to different people.

### 9. Draft the audit

```
drop id   : <what identifies this RTL drop for us>
corpus    : <each waiver file audited, and the entries counted in it>
basis     : hit-record | unwaived-diff | previous-drop | structural-only
counted   : <n duplicate, n shadowed, n never-matched, n dead-object, n dead-rule, n over-broad, n missing-bookkeeping>
widest    : <the single broadest entry, verbatim, with its file and line>
proposal  : <the one entry to remove or narrow, what replaces it, and the check that would confirm it>
owner     : <the entry's own owner field, or the profile's area map, or blank>
coverage  : <a of b entries parsed; c of d files opened; which checks could not run, and why>
notes     : <anything the next person would otherwise rediscover>
```

`drop id`, `owner`, `coverage` and `notes` are the field names the sibling skills use, so an audit
sits beside their reports without translation; `basis`, `counted`, `widest` and `proposal` are local.
Route `owner` on the profile's **Area to owner map**, keyed on the entry's design object — never on
which file the entry lives in, since chip-wide waiver files hold entries belonging to a dozen owners.
Leave it blank with candidates listed rather than guessing.

Propose **one** change, not a cleanup. Name the entry, say whether it is removed or narrowed and to
what, then state the confirming handoff: **ask the engineer to re-run the analysis with that one entry
changed and give you the path to the new report**, so the difference in violation count is read rather
than predicted. Forty deletions at once are unreviewable and get rejected whole; one deletion with a
report behind it sets the precedent for the other thirty-nine.

## Gotchas

- **A zero-violation report is the expected output of a healthy corpus and a broken one alike.** What
  separates them is not in the report — it is the count of entries that matched nothing, which lives
  in the hit record. A team quoting only the report has no measurement.
- **How an entry matches decides which way it fails, and the two cost very different amounts.**
  Object-pattern entries fail *closed*: they keep matching and quietly cover new violations appearing
  under the pattern. Signature- or hash-based entries fail *open*: any change to the violation text
  invalidates them and the violation returns, which is noisy and costs a morning. File-and-line
  entries do the worst thing of the three — they stay valid and slide onto whatever violation now
  occupies that line after an edit above it. Audit the failing-closed families first.
- **A wildcard crossing the hierarchy separator covers instances that did not exist when it was
  written.** That is the exact mechanism by which a new subsystem arrives pre-waived, with no entry
  ever added for it and nothing in any report to show it happened.
- **Waiving a bought-in IP subtree is defensible; waiving the glue around it is not.** A pattern
  anchored one level too high also covers the integration logic the team wrote — which is precisely
  where the domain crossings are, because the IP was signed off by its supplier and the glue by nobody.
- **Half a bus is a red flag.** A multi-bit crossing waived bit by bit, some bits covered and others
  not, means the bundle was never treated as a bundle. A grey-code or handshake justification is a
  claim about the whole group: if it holds, the whole group is covered, and if only part is, either
  the justification is wrong or somebody waived the bits that were shouting.
- **"Quasi-static" and "synchronised elsewhere" are claims about usage, not structure.** They stop
  being true when firmware starts writing that register during traffic, or when the synchroniser they
  point at moves. Neither event changes the entry and neither shows up in any report, so those entries
  need a re-review date rather than an expiry.
- **Reset-domain crossings are not clock-domain crossings, and a corpus inherited from one does not
  cover the other.** A crossing whose two ends share a clock and differ in reset is clean to one
  analysis and dirty to the other. Where a single file feeds both, count the entries separately before
  quoting a number for either.
- **A justification naming a person rather than a mechanism is not a justification.** "Agreed with the
  designer" survives the designer leaving, and by the third drop nobody can say what was agreed. That
  is a finding at signoff even where the entry is technically correct.
- **The corpus changes at drop boundaries and nowhere else, so audit at drop boundaries.** Between
  drops nothing moves, which makes the audit cheap to repeat and easy to postpone — postponed far
  enough, the diff is against a corpus nobody remembers and every entry looks load-bearing.

## Human verification — what a wrong answer looks like

Before taking the audit to signoff, check:

- the `basis` line is present, and no entry-level staleness claim appears under
  `basis: structural-only` or `basis: unwaived-diff` — neither can attribute anything to an entry
- every count is `n of m`, and `m` is the number of entries actually parsed — not lines in a file, and
  not violations in a report
- nothing marked `state: never-matched` skipped the shadowing check first. This is the most common
  wrong finding available here, and acting on it deletes an entry that was doing its job
- the widest entry is quoted **verbatim** with a file and a line, not paraphrased
- any dead-object claim says whether it came from the elaborated hierarchy or from a source Grep, and
  none rests on a source Grep for a path built by a generate block or an instance array
- entries the evidence could not reach are counted as `state: not-checkable`, visibly outside the
  clean pile
- the proposal is one entry with a confirming check named, not a list of deletions

A wrong answer reads as a tidy list of thirty stale entries proposed for deletion, produced with no
hit record on the desk — half of them shadowed by an entry three lines further down, and removing the
rest changing no report at all, because the corpus was never what was hiding those violations.

## Done when

The corpus has a counted state, the widest entry in it has a name and an owner, and one proposed
change is on someone's desk with the check that would confirm it.
