---
name: dv-lrm-conformance-matrix
description: Build a clause-by-clause conformance matrix over the language standard a product claims to implement, by reconciling a machine-readable clause inventory against the test suite's own clause tags, then rank what is left untested. Use when someone asks what percentage of the standard we actually cover, when a customer or an audit asks which clauses are untested, when you inherit a conformance suite whose tags were written against an older revision of the standard, or when a release claim needs defending with something better than a number nobody can reproduce.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Conformance Matrix over a Language Standard
  semiskill-function: design-verification
  semiskill-role: eda-product-validation-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-04-21
  semiskill-tags: conformance, standards, coverage, traceability, gap-analysis, test-suite, release-claim
---

# Conformance Matrix over a Language Standard

"How much of the standard do we support?" is normally answered with a percentage nobody can
reproduce: the denominator was never written down and the numerator counts header comments. A suite
accumulates tags claiming clauses no longer numbered that way, tests disabled for a tool bug two
releases ago, and normative error cases nobody tagged. This reconciles the two lists that do exist on
disk — the clause inventory and the suite's own tags — demotes every claim it cannot support, and
produces **a conformance statement carrying its denominator, a per-clause matrix, and a ranked gap
list**, plus one line saying how much was reconciled by hand rather than counted from tags.

## When to use something else

- One conformance test failed and you need the true first error — `dv-sim-log-first-error`.
- A suite run came back with dozens of failures to sort and route — `dv-regression-triage-routing`.
- The suite will not compile or elaborate — `dv-build-filelist-hygiene`; or you cannot yet find where
  it, its lists and its results live — `dv-repo-orientation`.
- A failing conformance test has to be shrunk before it goes to R&D — `dv-minimal-reproducer`.
- Coverage of a *design* is a different measurement; this one covers a *document*, and a matrix at
  100% says nothing about how much product source the suite reaches (the reverse holds too).

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Standard and revision | [[FILL: which standard and which revision of it this release claims conformance to, and which parts are in scope — for example a SystemVerilog, VHDL, UPF or assertion standard, named with its revision year]] | product owner |
| Clause inventory | [[FILL: where a machine-readable clause list for that revision lives, its format, what one row looks like, and whether it is a text file that can be read or a licensed document that cannot]] | standards lead |
| Requirement granularity rule | [[FILL: what one row of our denominator is — a clause, a subclause, or an extracted testable requirement — and who decided]] | standards lead |
| Test suite root | [[FILL: where our conformance suite lives and how it is partitioned into directories]] | validation lead |
| Clause tag convention | [[FILL: the exact syntax a test uses to name the clause it claims, and where in the file that sits]] | suite owner |
| Run-list convention | [[FILL: which file decides that a test is selected to run in the release regression, and how a test is named in it]] | validation lead |
| Deviation and waiver list | [[FILL: where deliberately unsupported, deferred or non-normative clauses are recorded, and what an entry is keyed on]] | validation lead |
| Customer-priority signal | [[FILL: how we know which clauses customers actually exercise — an escalation history keyed on clause, a supported-feature list, or a person to ask]] | applications engineering |

Pack-wide facts live in `_shared/team-profile.md`. Two are spent here: **Regression summary** supplies
the per-test results file in step 6, **Sign-off** the recipient of the statement in step 8.
**Run-list convention is narrower than the profile's Regression summary** and is not the same fact —
the profile records where a run's *results* land, this slot asks which file decides a test is
*selected to run at all*. Those are usually different files, and treating them as one is how a
disabled test gets counted as coverage. Every row above is spent: Standard and revision, Clause
inventory and Test suite root in step 1; Requirement granularity rule in step 2; Clause tag
convention in step 3; Run-list convention and Deviation and waiver list in step 5; Customer-priority
signal in step 7. **If a slot is unfilled, stop and ask. Do not guess a convention** — and never
reconstruct clause numbers or wording from memory; an invented identifier looks like a real one.

## Retrieval budget — read this before opening anything

A conformance suite is tens of thousands of small files and the inventory has hundreds of rows.
Reading either end to end is neither possible nor useful; most of this is set arithmetic.

1. **Grep and Read work on files on disk.** The standard is a licensed document, is not an input, and
   its text is never quoted or paraphrased into the matrix. If the Clause inventory slot resolves to
   a spreadsheet, a rendered document or a page rather than a text file, say so and stop at step 2 —
   you can still list what the suite claims, but with no denominator, so no percentage.
2. **Never open a test file with Read as the first move.** Locate with **Glob**, join with **Grep**,
   read only bounded windows around a match.
3. The whole budget: **two Glob** calls (step 1 for the inventory, suite root and waiver list; step 3
   for the test tree); **four Grep** calls (step 3 the clause tags, step 5 the run list, step 5 the
   waiver list, step 6 the results file — that last only if such a file already exists); **one
   bounded read of the inventory** in step 2, at most three windows of about 200 lines or the whole
   file if smaller; **at most four windowed Reads of about 60 lines inside tests** in step 5. A
   **fifth Grep** is allowed in step 7 and only there, if the Customer-priority signal is a file; if
   it is a person or a tracker it is a handoff. Steps 4 and 8 open nothing.
4. If the tag Grep returns more than about two thousand matches, do not enumerate: aggregate by the
   leading clause number, work at clause-group granularity, and say so in the statement.
5. If any Grep returns zero hits the convention is wrong, not the suite untagged — stop and re-ask. A
   zero-hit tag Grep silently produces a 0% matrix, the most expensive wrong answer available here.
6. Stopping rule: when the budget is spent, report the matrix as it stands; step 8's `coverage` line
   says how many rows were reconciled by hand and how many were counted from tags alone.

## Procedure

### 1. Pin the revision and the scope before counting anything

**One Glob** locates the three things the slots name: the Clause inventory file, the Test suite root,
and the Deviation and waiver list. Record their paths. Then write down what the Standard and revision
slot says — the standard, the revision, the parts in scope. Clause identifiers are revision-scoped:
material moves, a subclause splits, a clause is renumbered, an annex is promoted into the normative
body. A matrix without a stated revision cannot be compared with anything, its own last edition
included. If inventory and suite were built against different revisions that is already the
finding — say so rather than reconciling across the gap and reporting a number.

### 2. Build the denominator from the inventory, not from memory

**Read** the inventory within the budget's window allowance. Extract, per row: the clause identifier
exactly as the inventory spells it, its own short title, and any marking it carries for informative
or non-normative material. The denominator is then the count of **in-scope, normative** rows at the
granularity the Requirement granularity rule names — write that rule into the statement. A
denominator of clauses and one of extracted testable requirements differ by an order of magnitude
over the same document, so a percentage without its granularity is not a measurement. If the
inventory is not a readable file, say so and stop: what follows still yields a claim list and a
tag-rot count, but no percentage and no gap list, there being nothing to subtract the claims from.

### 3. Size the suite, then harvest the clause tags — this is the join

**Glob** the Test suite root for test files; record the count and the directory partitioning. This is
sizing, not reading: it tells you whether the next call returns hundreds of matches or tens of
thousands, which decides the granularity you work at under budget rule 4. Then **one Grep** across
that root for the Clause tag convention's pattern, returning matching lines rather than file bodies,
so the result is the tag list and the files carrying it. This single call is the entire join between
standard and suite; everything after it is arithmetic and demotion. Zero hits means the convention is
wrong (budget rule 5); a hit count far above the file count means the pattern also matches prose, a
change log or a copied header — narrow it before going on.

### 4. Reconcile the two lists into four piles

No tool call; set arithmetic over steps 2 and 3:

- **matched** — a tag resolves to an in-scope row. This is a *claim*, not coverage.
- **tag rot** — a tag resolves to no row in this revision. Count these: usually the first
  quantitative evidence anyone has that the suite drifted from the standard it cites.
- **gap** — an in-scope normative row with no tag pointing at it.
- **excluded** — a row the inventory marks informative or non-normative, or one the scope line in
  step 1 puts outside this release's claim.

Those are working names and the matrix spells them differently, so pin the mapping now rather than
letting two vocabularies drift. **matched** enters the matrix as `clause status: claimed`, and only
steps 5 and 6 move it to `deviation` or `covered`. **gap** is written `untested`, the word both the
matrix and the statement use for that pile. **excluded** is written `non-normative`. **tag rot** gets
no matrix row at all; step 8 says where it goes. Excluded rows leave the denominator and are reported
separately, never folded into the numerator and never dropped silently — a percentage that moves
because the denominator shrank is the commonest way this measurement is gamed.

### 5. Demote every claim you cannot support

A matched tag starts at `clause status: claimed` and only earns better here. Three demotions, in this
order, because each is cheaper than the next:

1. **Not selected to run.** **Grep** the file named by the Run-list convention for the test names
   behind the matched tags. Anything selected by no list stays `clause status: claimed` with
   `run list: selected by none`. This usually moves more rows than the tag reconciliation does, and
   it is invisible to any summary that counts test files.
2. **Deliberately waived.** **Grep** the Deviation and waiver list for the identifiers in the gap
   pile and for any matched clause it mentions. A clause the product has declared it does not
   implement is `clause status: deviation` — a decision, not a gap — and belongs in its own column so
   closing it stays a product decision rather than a test-writing task.
3. **No check inside the test.** Spend the budget's **four windowed Reads** here, about 60 lines
   around the tag. Choose the four by a rule stated at this step — step 7's ranking is not it, since
   that ranks the untested pile rather than matched claims. Take the matched clauses still standing
   after demotions 1 and 2 that carry the **fewest tests** (one test is the thinnest claim in the
   matrix), breaking ties by path order so a second pass picks the same four. Look for what the test
   compares: an expected value, an expected diagnostic, a golden file reference. Record it in `check`
   verbatim, or `no check found`. Name the four; the rest stay where demotions 1 and 2 left them.

### 6. Pass or fail is a handoff, not an inference

The agent cannot build the product, cannot run the suite, and must not infer a result from a test's
existence. **Ask the engineer to run the conformance suite against this release's build and give you
the path to the per-test results file** — the profile's Regression summary row says where that lands.
If such a file already exists on disk, spend the fourth **Grep** on it for the sampled test names and
promote only those rows to `clause status: covered`. Everything unconfirmed stays
`clause status: claimed` and keeps whatever `basis` step 5 earned it, `tag-only` or
`run-list-checked`. The statement's own `basis` line then carries the weakest value any counted row
carries — the one-word summary of what the whole number rests on. A failing test is not coverage,
and neither is a test whose result nobody looked up.

### 7. Rank the gaps by consequence, not by clause number

An untested pile sorted by identifier is a list nobody reads. Rank it by:

1. **Customer-priority signal** — clauses with escalation history or on the supported-feature list.
   If it is a file this is the fifth Grep; if a person, ask, and record that the ranking rests on one.
2. **Negative and diagnostic clauses** — rows the inventory titles as an illegal case or a required
   diagnostic. Systematically untagged, and systematically probed by anyone evaluating the product.
3. **Interaction rows** — anything the inventory places where two features meet.
4. **Breadth** — a whole untagged subtree beats a scattered handful of rows.

### 8. Write the matrix and the statement

One row per clause, keyed on an identifier the inventory actually carries — this block repeated, or a
table with the same column names, whichever the team keeps under revision control (the *diff* between
two releases is the part that gets read).

```
clause        : <identifier exactly as the inventory spells it>
title         : <the inventory's own short title — never retyped from the standard itself>
clause status : covered | claimed | untested | deviation | non-normative
tests         : <count> — <up to three test paths, then "+k more">
run list      : <which list selects them, or "selected by none">
check         : <what the test compares, quoted from the test, or "no check found">
basis         : <tag-only, run-list-checked or results-confirmed — the weakest that applies>
rank          : <n> because <customer signal / negative case / interaction / breadth>
notes         : <anything the next person would otherwise have to rediscover>
```

Tag rot has no row here: a rotted tag resolves to no inventory identifier, so it has nothing to put
in `clause`. Keep it as a flat list of its own — per stale tag, the tag text exactly as the suite
writes it, then the file and line carrying it — under the statement's `tag rot` count. That list, not
the matrix, is what someone repairing the tags works from. Then one statement for the whole matrix,
the part that gets quoted; hand it to whoever the profile's Sign-off row names.

```
standard      : <name and revision, exactly as the inventory spells it>
scope         : <which parts of the standard this release claims>
granularity   : <clause, subclause or extracted requirement — whichever our rule names>
denominator   : <n> in-scope normative rows, of <m> in the inventory
excluded      : <m minus n> rows, informative or out of scope, listed separately
covered       : <n> confirmed against a results file
claimed       : <n> tagged but not confirmed
untested      : <n> — step 4's gap pile, under the name the matrix uses
deviation     : <n> declared on the waiver list
tag rot       : <n> tags resolving to no row in this revision, listed separately
basis         : <the weakest value any counted row carries on its own basis line>
coverage      : <n> of <m> rows reconciled by hand; the rest counted from tags alone
top gaps      : <the five highest-ranked untested rows, by identifier>
```

Anything not fillable from text on disk is `?`, never a guess. If the inventory was unreadable,
`denominator` is `?` and no percentage appears anywhere — say that rather than approximate one.

## Gotchas

- **A tag is a claim, not a test.** The comment asserts a clause is covered; nothing checks that it
  is. Tag harvesting gives the *claimed* matrix, and that word must survive into the statement.
- **Clause identifiers are revision-scoped, so tag rot is silent.** A tag from the previous revision
  resolves to unrelated material or to nothing and never errors: the suite still builds and passes.
- **A clause is not one requirement.** One subclause routinely carries a dozen testable statements: a
  shall, a shall-not, an error case, a diagnostic, an interaction with another clause. One test per
  clause counted as covered is how a suite reaches 90% and still fails a customer's first design.
- **The negative half of the standard is the half nobody tags.** Most suites demonstrate that legal
  constructs elaborate and simulate; clauses stating a construct is illegal, or that a diagnostic
  shall be issued, surface as gaps only if the inventory carries them as rows. A gap list with no
  error cases in it indicts the inventory.
- **A test that exists but is in no run list is not coverage.** Suites accumulate tests disabled for a
  tool bug several releases ago; nothing in the file says so, and the only evidence is its absence
  from the run list.
- **A passing test can pass for the wrong reason.** With no compare, no expected-diagnostic match and
  no golden reference, it passes until the product crashes on it — including after the feature it
  covers is removed. Look for the check, not the exit status.
- **Interaction behaviour has no home clause.** Where two features meet the tag belongs to one or the
  other, so the interaction reads as covered by both and tested by neither. Say so: it is residue
  outside what this measurement sees.
- **An externally supplied suite's mapping is its supplier's claim, not yours.** You cannot inspect
  its checks; give it its own column and basis, or nobody can say which half they may rely on.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every percentage carries its denominator, revision, scope, granularity and basis — and if the
  inventory was unreadable, there is no percentage at all
- nothing is `clause status: covered` on the strength of a tag alone; that state needs a results file
- deviations and non-normative rows are in their own columns, not folded into the numerator or into
  the excluded pile without being listed
- the tag-rot count is present even when zero, and the stale tags behind it are listed with their
  files rather than hidden inside matrix rows
- the gap list is ranked by something other than clause number, each row naming which of step 7's
  four criteria put it there
- every identifier is quoted exactly as the inventory spells it, and no clause text is reproduced
  from the standard itself

A wrong answer typically reports one percentage with no denominator; counts header comments as
coverage; shows a suspiciously round figure because the tag Grep matched almost nothing and nobody
questioned it; or drops the clauses the product does not implement, so the number improves each
release without a test being written.

## Done when

You can state one number, say exactly what it is a fraction of, and hand over a ranked list of
untested clauses someone could start writing tests against tomorrow.
