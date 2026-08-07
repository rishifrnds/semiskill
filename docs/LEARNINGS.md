# Learnings

Hard-won, project-specific lessons. Each one cost real time or shipped a real defect. Kept separate
from `docs/AUTHORING_CONTRACT.md` (which is *what to do*) because this is *why*, and the why is what
stops someone "simplifying" a rule back out.

---

## On verification tooling

### `lint 1.000` is a SECURITY score, not a quality score
It says the text contains no url, no shell verb, no credential-shaped string, no prompt-injection
phrasing. It says **nothing** about whether the DV content is correct. Two full adversarial review
rounds were spent learning this: six skills at a perfect 1.000 were still judged "not ready to
publish as a set", twice.

### A rule with zero precision is worse than no rule
`C002` matched `\b[A-Z][A-Za-z-]+(?: [a-z-]+){0,3} slot\b`, so any sentence starting with a capital
and containing "slot" was reported as a reference to an undeclared slot. On the real pack:
**105 findings, 105 false** — "If a slot is unfilled" read as a slot named "If a". The one genuine
finding was invisible inside the noise. Fixed by requiring a *label* (strip leading function words;
what remains must still begin with a capital). Result: 105 → 1, and the survivor was real.

**Rule:** before shipping a check, run it on the whole corpus and read the findings. A rule that
fires on everything trains people to ignore it, which is worse than silence.

### A linter can cause the drift it exists to catch
`specs/skill_registry.json` planned five cells each for `memory-ip-dv-engineer`,
`processor-ip-dv-engineer` and `eda-product-validation-engineer`, but
`semiskill/authoring/facets.py` never learned those roles. Consequence: 10 skills failed lint with
"unreachable facet" — and **5 more had been quietly remapped by their authors to `ip-dv-engineer`
to get past the linter**. The facet-drift check was catching drift the linter had caused.

**Rule:** when a check and a plan-of-record disagree, find out which is wrong before making the
content conform to the check. Authors route around linters, silently.

### Field-name identity is not field identity
`C003` assumed any two skills using the same handoff field name must carry the same enum. That
produced 10 wave-blocking errors, of which **9 were unrelated skills reusing a common English word**
(`culprit`, `mechanism`, `ruling`, `divergence` …) for entirely different things — disjoint value
sets, no relationship. It was reporting a *name collision* as *drift*, and the prescribed fix
(reconcile the enums) would have been actively wrong.

Resolved by ADR-011: a signed registry (`skills/_shared/handoff-vocabulary.md`) answers "is this
name pack-wide?", and the two failures split — disagreeing with a *registered* enum is C003, sharing
an *unregistered* name is C006. Measured afterwards: the only 7 enum names appearing in more than
one skill are exactly the 7 registered ones.

### A governed value set must be exempt from local-reachability rules
`C005` ("this block offers a value no step assigns") is sound for a field a skill owns. Applied to a
*registered* field it is a contradiction: `class` may not drop `unknown`, so a skill whose procedure
only reaches two of the three values gets a warning it cannot fix — the only "fix" C005 offers
raises a wave-blocking error instead. 76 of 205 C005 warns were structurally unfixable this way.

**Rule:** when two rules can both be satisfied only by violating the other, one of them is scoped
wrong. Find the boundary (here: governance vs. local procedure) rather than adding an exception list.

### Snapshot tests that pin current defects go stale when you fix them
Tests asserting "C011 finds exactly these three defects" go red every time the gate does its job —
which trains you to bump the number without reading it. Two better shapes:
- assert the **rule** on a synthetic tree (so `0` on the real pack means "clean", never "rule broken");
- assert a **ceiling** on the real pack (`found <= KNOWN`), which still fails on a *new* defect.

Likewise, registry snapshots (`len(reg.narrowings) == 5`) fail on correct work. Assert **shape**
instead: every narrowing is a proper subset of the enum it narrows; no name is in two categories.

---

## On running a multi-agent gate

### One fix pass then a strict recheck converges on zero
44 skills completed author → review → fix → independent recheck. **Zero passed.** Two causes, and
only one of them was the content:
1. The findings were genuine (see below), and one fix round does not close them all.
2. **The verdict was uncalibrated.** Reviewers listed `semiskill-review-by` collisions and phrasing
   preferences beside genuine blockers, then set `ready: false`. Under "would you hand this to an
   engineer today? 'Nearly' is a no", `ready: true` was unreachable by construction.

Fixed by forcing every finding into **BLOCKING** vs **NON-BLOCKING** and gating only on the former,
with explicit instruction not to inflate a nit to look rigorous nor demote a real defect to look
generous. Expect the gate to need **rounds**, and budget for them.

### A wave that dies halfway must leave NO gate record rather than a false one
~40 agents died mid-flight on a session token limit. `collect_wave.py` keyed off the journal and
would have written `ready: false` with an empty findings list for every one — recording *"an
independent reviewer rejected this"* when in fact **nobody looked**, and the scoreboard could not
tell the two apart. It now skips a skill with no recheck record entirely, so those skills read as
`never-reviewed`, which is the truth, and the gate picks them up again.

**Rule:** the failure mode of a batch driver is reporting phantom work as real work. Silently
reporting an empty wave as a success is the worst outcome available; a half-finished wave that
*claims* completion is the second worst.

### Fix agents introduce defects — re-run the pack check after every batch
Two caught this session: an undeclared `phase` narrowing (C007) and a value-wearing-a-sentence
(C009, wave-blocking) that a fixer wrote while closing an unrelated finding. Neither was in any
review; both were found by re-running `check_pack` after the batch.

### Never run `pytest` while an agent is running it
The test fixture `TRUNCATE`s the shared dev Postgres `artifacts` table before each test. Two
concurrent runs destroy each other's rows and fail in ways that look exactly like real regressions —
30 failures across `test_site` / `test_pack` / `test_scoreboard` / `wave`, every one passing in
isolation. **An hour was lost misdiagnosing this as a rule bug.** Serialise test runs.

---

## On the content itself

The defects the independent recheck finds are the ones no linter can reach. Representative:

- **A retrieval window pointing away from the value it records.** `dv-signal-trace-localisation`
  step 1 read "one window of about 80 lines *before*" the marker — but the pack's own schema puts
  `expected N got N` on the line *after* the marker. The single most important value was outside
  the only window the step opened.
- **A budget that makes a branch unreachable.** `dv-coverage-hole-disposition` granted 2 Greps to a
  step needing 3. The procedure did not fail; it **silently degraded** to a weaker ranking rule, and
  the reader was never told.
- **A flat claim that is actually policy.** "A failing test contributes no coverage" — coverage is
  sampled during simulation regardless of the final verdict; whether that database is merged is a
  flow decision. The same skill handled this correctly in three other places, which is exactly what
  made the flat assertion dangerous.
- **A shared word with inverted polarity.** One skill used `falsified: yes` to mean *the check is
  trustworthy*, while the registered `proof status` uses `falsified` to mean *the property was
  refuted*. Same word, opposite sense, one pack.

**Rule:** these are all *cross-reference* failures — text disagreeing with other text. That class is
decidable, which is why so much of it moved into `consistency.py`. What remains needs a reviewer who
knows the domain, and the reviewer must be independent of the fixer.

---

## On honesty in records

A recurring theme, worth stating once plainly. Every mechanism in this project that records a
verdict has a failure mode where it records **something that did not happen**:

| Mechanism | The lie it can tell |
|---|---|
| `REVIEW.json` written from a dead agent | "an independent reviewer rejected this" |
| `ready: true` written by the fixer | "someone else checked my work" |
| An empty wave reported as success | "83 skills published" |
| A snapshot test bumped without reading | "this still guards something" |
| A catalog page with invented metrics | "1.3k installs, 4.8 stars" |
| MEMORY.md claiming a step is done | "77 skills went through the full gate" |

The last one is real: this session began by measuring the previous session's claim and finding
83 authored, 6 with a gate record, **0 published**. Measure before you trust a record — including
your own.

---

## 2026-08-07 — Source-bound gates and launch truth

### A green platform suite is not a green catalog

The immutable full suite proved 1,078 repository tests on one exact clean commit and isolated test
database. It proved **zero** skill reviews, approvals or publications. Keep platform proof and catalog
credit as separate funnels; otherwise a large passing test number can visually overpower the more
important `0/84` release result.

### There are two hashes, and only the full payload hash governs approval

Strict lint reports a hash of `SKILL.md`. Every current DV skill also imports three canonical
`_shared` files that affect its instructions. Review, approval, badge, export and publication must use
the full captured payload hash that includes those vendored bytes. Displaying the lint hash beside an
approval action without naming its narrower scope is a high-risk operator-interface bug.

### A migration approval expires when source changes

A read-only plan can be perfectly formed and still become unusable one documentation commit later if
the migration contract binds the repository commit/tree. Preserve the old plan as provenance, mark it
superseded, and generate a new plan after the final clean checkpoint. Never interpret “continue” or
“push everything” as approval of an older digest.

### A scanner that misses the behavior file cannot be Stage 2

The audited claude-flow path primarily scans JS/TS/JSON/YAML/env files, can write inside the target,
depends on networked `npm audit`, and swallows some errors. Parsing its output more carefully cannot
repair those authority failures. The replacement must reconcile the scanner's exact file inventory
against every captured payload file, run read-only and without network, and fail closed on any error
or extra output. File coverage alone is insufficient: payload-owned `.semgrepignore` and inline
`nosem` can suppress findings while a file still appears scanned. Trusted staging must isolate
scanner controls, disable suppressions and fail on every ignored, skipped, partial or parse-error file.

### “Local model” is not the same as “local-only model”

Ollama was installed locally but listening on wildcard IPv6. An adapter that calls `127.0.0.1` does
not by itself prevent another interface from reaching the daemon. Activation must verify the daemon's
actual listener, disable proxies/redirects/tools, bind the exact model/prompt/calibration hashes and
refuse credit until independent held-out labels establish the error signal.

### One command centre needs one observation contract

API, dashboard and export should not independently reimplement freshness, database identity,
scoreboard validation or fallback rules. A shared strict observation module prevents one surface from
showing stale green while another correctly says unavailable. Business planning data remains useful,
but its hypotheses must never share the visual or schema authority of observed launch evidence.

### A commit cannot contain its own Git SHA

The original state rules asked MEMORY to name the latest commit SHA inside that same commit. Git
hashes the tree containing MEMORY, so the requirement is self-referential and cannot be satisfied.
The durable convention is an exact `this <STEP-ID> checkpoint` marker whose containing commit subject
must name the same STEP-ID; real SHAs remain mandatory when recording an already-existing commit.
Making this explicit prevents every fresh operator from correctly stopping on an impossible gate.
