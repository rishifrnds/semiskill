---
name: dv-safety-manual-aou
description: Cross-check a safety manual's assumptions of use against what verification actually established, so each assumption is either pinned by the verified configuration or proved by a test that violates it and shows the element itself reporting the violation. Use when a safety manual draft is out for review, when an assessor or integrator asks which assumptions of use are backed by evidence, when a diagnostic-coverage claim rests on a configuration nobody confirmed the regression ran in, or when a release or sign-off package needs an assumptions-of-use compliance matrix.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Safety-Manual Assumptions of Use: Authoring Cross-Check and Integration Compliance Matrix"
  semiskill-function: design-verification
  semiskill-role: safety-verification-engineer
  semiskill-level: principal
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-07-14
  semiskill-tags: functional-safety, safety-manual, assumptions-of-use, seooc, traceability, sign-off
---

# Safety-Manual Assumptions of Use: Authoring Cross-Check and Integration Compliance Matrix

An element developed out of context ships its residual risk to the integrator inside a list of
assumptions of use, and that list is written late, by whoever is holding the pen, largely from
memory of what the design is supposed to do. Verification is the only thing that decides whether
each assumption is true, and the two documents are almost never walked against each other line by
line — so the manual quietly accumulates assumptions nothing pins, assumptions the signed-off
regression contradicts, and assumptions worded so that no run could ever falsify them.

The output is **one matrix row per assumption**, each carrying a verdict, the file and line behind
it, the thing that would make it stronger, and a coverage line saying how many of the manual's
assumptions were actually reached. Not a review of the manual's prose.

**What this does not do.** It reads the manual (if it is in a format **Read** can open), source
files, configuration records, test lists and saved result files. It cannot start a fault campaign,
run a simulation, compute a metric, or open a waveform. Every step that needs one of those ends in a
handoff to a named human and says so.

## When to use something else

Whether the mechanism an assumption leans on actually detects each error pattern is a different
matrix — `dv-error-injection-ras`. Which parameter combinations the regression genuinely exercised is
`dv-config-space-coverage`, and this skill consumes its answer one value at a time rather than
re-deriving it. The verification plan's own feature-to-test-to-coverage-to-checker chain is
`dv-testplan-traceability-review`; that audits what we promised ourselves, this audits what we
promised the integrator. Assembling the whole sign-off package is `dv-release-gate`, and this matrix
is one exhibit in it. When two readings of an assumption both look legal, the question belongs in
`dv-spec-interpretation-ledger` before anyone disposition it. And a violation test that failed in a
way you did not predict goes to `dv-sim-log-first-error` first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Manual source | [[FILL: where the safety manual draft lives, its format, and whether that format can be opened as text]] | functional safety manager |
| Assumption keys | [[FILL: how each assumption of use is keyed in our manual, and whether those keys stay stable across revisions]] | functional safety manager |
| Configuration record | [[FILL: the file recording the parameter, define and tie-off values the signed-off regression actually ran with, and whether it is generated or hand-maintained]] | DV lead |
| Mechanism inventory | [[FILL: where the element's claimed safety mechanisms are listed, and the identifier each is cited by]] | safety architect |
| Violation-test convention | [[FILL: how a test that deliberately violates an assumption is named or tagged here, and where those tests are listed]] | DV lead |
| Detection observable | [[FILL: what our environment observes to say the element itself reported — an output port, an error register bit, a named message — as distinct from a testbench check firing]] | testbench owner |
| Campaign results | [[FILL: where fault-injection and safety-mechanism campaign results land, in what format, and whether they are readable files]] | safety verification lead |
| Metric source | [[FILL: where the diagnostic-coverage and metric numbers the manual quotes are produced, and whether that source can be read]] | safety architect |
| Element boundary | [[FILL: what sits inside this element and where the integrator's responsibility starts, as written down today]] | safety architect |
| Matrix destination | [[FILL: where the compliance matrix is recorded and who reviews it]] | functional safety manager |

Three pack-wide facts come from `_shared/team-profile.md` and are deliberately not re-asked here:
**Regression summary** (step 5, to name the regression the manual's claims rest on), **Known-issue
list** (step 8, so an assumption already recorded as unsupported is not filed a second time), and
**Sign-off** (step 9, because this matrix is sign-off evidence and has to arrive in the shape that
gate expects).

Two rows above sit close to a profile fact without being it, and the difference is load-bearing.
**Configuration record** is *not* the profile's Regression summary: a summary says which tests
passed, never what parameter values they ran with, and the whole of step 5 turns on the second
question. **Campaign results** is *not* the profile's Coverage output: a fault campaign and a merged
functional or code coverage database are different measurements from different runs, and a campaign
that was never run leaves the coverage database looking perfectly healthy.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented parameter name or an
invented assumption key produces a matrix that looks complete and cites nothing — worse here than
anywhere else in this pack, because the reader is an assessor who will ask for the file.

## Retrieval budget — read this before opening anything

A safety manual runs to a hundred assumptions scattered through a document that is mostly not
assumptions, and a configuration record for a configurable IP is thousands of lines. Work in this
order and stop at the cap:

1. **Grep, Read and Glob work on files on disk.** If the Manual source slot resolves to a format
   that cannot be opened as text — a document, a slide deck, a wiki page — say so before anything
   else and ask the functional safety manager for a text or markdown export and its path. Until one
   exists the only assumptions available are the ones somebody typed into the conversation; you may
   reason over those by eye, but every row is provisional and you do not know the denominator.
2. **Glob** first for three things: the manual export, the Configuration record, and the list the
   Violation-test convention names. Never open the manual with **Read** as the first move.
3. One **Grep** of the manual for the assumption-key pattern, to enumerate the list with line
   numbers, then at most **three Read windows of about 80 lines** across the assumptions section.
4. Three standing **Grep** calls, each spent once for the whole session, not once per row: the
   Element boundary statement (plus one 40-line **Read** window on it), the Metric source when any
   row quotes a number, and the profile's Known-issue list when it is a file on disk.
5. Per assumption, at most **two Greps** — one against the Configuration record for the knob the
   claim names, one against whichever evidence file the verdict needs — and at most **one 40-line
   Read** window.
6. Cap at **12 assumptions per session**. The whole ledger is then 3 Globs; 1 + 3 + 24 = 28 Greps;
   3 manual windows + 1 boundary window + 12 evidence windows = 16 Reads. Around 47 calls, which is
   already a full session's attention — spend it on the rows most likely to be wrong, per the tail
   rule in the Gotchas.
7. If a **Grep** returns more than about 200 hits the pattern is too broad — a parameter name is
   usually a substring of something common. Anchor it before reading anything.
8. **Stopping rule.** Stop at 12 assumptions, or when three consecutive rows end unresolved waiting
   on the same missing input. Name that input and report what was reached. Past that point verdicts
   get invented, and an invented verdict here is signed by somebody.
9. State the coverage — "dispositioned 12 of 41 assumptions; the other 29 were not opened, and they
   are the tail of the list". An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the manual to a path before reading a word of it

**Glob** for the Manual source. If it resolves to something **Read** cannot open, stop and make the
handoff in budget rule 1 — ask the functional safety manager for a text export and the path it was
written to. Do not work from a screenshot, a quotation, or a recollection of the manual.

If only a handful of assumptions were pasted into the conversation, say plainly what that costs: you
cannot know how many assumptions the manual holds, so no percentage and no completeness claim is
available, and every row below is provisional.

### 2. Enumerate the assumptions and pin each one to a key

Use **one Grep** for the pattern in the Assumption keys slot. Count the hits — that count is the
denominator of every later claim, and it is the number people most often replace with the number of
rows they happened to write.

If the manual keys nothing, stop and say so. An unkeyed assumption cannot be cited in a matrix,
matched against the next revision, or answered by the integrator. Proposing keys is a legitimate
deliverable, but say the numbering is yours rather than the manual's.

Watch for one assumption stated twice — once in an overview, once in a per-mechanism section, worded
differently both times. One key, one row.

### 3. Rewrite each assumption as one checkable claim — the authoring half

Before checking anything, turn the sentence into a claim naming an observable. "The integrator shall
ensure the memory interface is appropriately protected" names nothing. "Parameter *ecc_en* shall be 1
in any configuration to which the safety claim applies" names a parameter, a value and a scope.

The test is one question: can you name the file that would have to change, or the run that would have
to exist, for this claim to be false? If you cannot, the verdict is `aou-verdict: not-checkable`, the
owner is the manual's author, and your proposed rewrite goes in the claim field. Do not go on to
check an unfalsifiable claim — you will find evidence for it, because everything is evidence for a
claim nothing can contradict.

Keep the manual's wording verbatim beside your rewrite. The assessor reads the manual, not your
paraphrase, and a rewrite that quietly narrows the claim is the failure mode of this step.

### 4. Decide which side of the element boundary the claim lands on

Spend the standing **Grep** and 40-line **Read** window on the Element boundary statement, once, and
classify every claim against it:

- `aou-scope: element` — the claim is about something inside what we built and verified.
- `aou-scope: integrator` — it is about the system around us: a supply, an external monitor, a
  software sequence, an operating condition, a periodic action at a stated interval.
- `aou-scope: shared` — it names something at the boundary itself, which we drive and they consume.

A claim about a signal that does not exist at the boundary is not an assumption of use at all — it is
an internal requirement that was copied into the wrong document. Send it back rather than
dispositioning it, and say which document it belongs in.

### 5. Look for enforcement in the verified configuration

**Grep** the Configuration record for the parameter, define or tie-off the claim names. Three
outcomes, and they are not the same answer:

- **Pinned.** The value is set explicitly in the configuration the signed-off regression ran, so no
  verified run could have violated the claim → `aou-verdict: enforced-by-config`. Record the file and
  line, and name the regression from the profile's **Regression summary** fact. A matrix that does
  not say which regression it was built against is unreviewable a month later.
- **Default only.** Nothing sets it; the regression inherited the RTL default and an integrator
  override is perfectly legal → `aou-verdict: default-only`. This is the row people mark compliant
  and should not. Nothing was chosen, and nothing at all was verified in the other setting.
- **Contradicted.** The mechanism the manual says must be enabled is disabled in the configuration
  that ran, very often for speed → `aou-verdict: gap`, and it is the most expensive row in the
  matrix, because every number quoted for that mechanism rests on runs that did not have it.

Static and dynamic enforcement are different things. A parameter or tie-off is fixed at elaboration
and an integrator cannot undo it at run time. A register bit written by boot software can be written
back the other way at any point afterwards, so it is never `aou-verdict: enforced-by-config` however
carefully the boot sequence sets it — the honest question for it is step 6's.

### 6. Look for a test that violates the claim and shows the element reporting it

Use the Violation-test convention to **Grep** the test list for a test that drives this claim false.
Then judge the result against the **Detection observable** slot: the evidence must be the element's
own reporting path — the output port, the error register bit or the message named there — and not a
testbench checker firing. A scoreboard noticing proves our testbench is watching; the integrator has
no scoreboard.

- Such a test exists and the result shows the observable → `aou-verdict: violated-and-detected`.
  Where the Campaign results file carries the row, cite that file and row rather than a simulation
  log; a campaign result is the artifact an assessor expects.
- A check exists in source — an assertion, an elaboration-time error — but no run is known to have
  driven it false → `aou-verdict: asserted-only`. An assertion nobody has made fire is a claim about
  the assertion, not about the design.
- No such test exists. The handoff is explicit: **ask the block DV owner to add a test that drives
  this assumption false and to give you the path of the log or result file it writes.** The agent
  cannot start a run and must not describe what one would have printed.

Be precise about what `aou-verdict: violated-and-detected` buys. It does not discharge the
assumption — the integrator still has to satisfy it. It proves the failure mode is detected rather
than assumed away, which upgrades the manual's sentence from "the integrator shall" to "the
integrator shall, and the element reports if they do not". That is a much stronger sentence and the
manual's author has earned it; tell them.

### 7. Assign one verdict per row, and record what would move it

Where neither step 5 nor step 6 produced evidence, the verdict is `aou-verdict: gap` — the manual
claims something no file on disk supports. Where the row is `aou-scope: integrator`, the verdict is
`aou-verdict: handed-over`, and it needs both the named interface and the document the handover is
made in; "the integrator's problem" with neither is a gap wearing a better coat.

Every row also carries the one thing whose absence keeps it where it is: the run that does not exist,
the pin nobody set, the observable nobody checks. The verdicts are a score; that column is the work
list, and it is what the next session spends its budget on.

### 8. Push the findings back into the manual, not only into a bug list

Three shapes of manual change come out of this, and they are different work:

- **Over-claim.** A number taken from the Metric source sits above a mechanism whose row is
  `aou-verdict: default-only` or `aou-verdict: gap`. The number is not necessarily wrong; its
  precondition is unstated. That fix is in the manual, not in the RTL.
- **Under-claim.** A `aou-verdict: violated-and-detected` row the manual still words as a bare
  obligation. The cheapest improvement available here, and the one nobody makes.
- **Missing.** Something verification relied on that the manual never states. You will meet these
  sideways, as pins you noticed while spending step 5's Greps with no assumption key against them.
  Report them as found-in-passing rather than as a complete list — a complete list needs a pass over
  the Configuration record that this budget does not buy.

Before filing any of it, spend the standing **Grep** of the profile's **Known-issue list**, when that
list is a file on disk. An assumption already recorded there as unsupported gets that entry's key,
not a second entry. If the list is a tracker no tool here can reach, say the check is pending and ask
its owner to compare the keys.

### 9. Draft the compliance matrix

One header block:

```
element     : <the element the manual describes, and the manual revision this was checked against>
manual      : <path, if it was readable — otherwise the format and who holds it>
regression  : <the regression the claims rest on, from the profile's Regression summary>
assumptions : <n> keyed in the manual, <k> dispositioned here
coverage    : <k of n dispositioned; which of the rest were not opened, and why>
```

Then one block per assumption, worst verdict first:

```
aou id      : <the manual's own key, verbatim>
claim       : <the checkable rewrite, with the manual's own wording kept beside it>
aou-scope   : element | integrator | shared
aou-verdict : enforced-by-config | violated-and-detected | handed-over | default-only | asserted-only | gap | not-checkable
mechanism   : <the safety mechanism this assumption holds up, by its Mechanism inventory identifier, or none>
evidence    : <file path and line, or test name plus result file and the observable seen in it>
blocker     : <the run, pin or observable whose absence is why this row is not stronger>
owner       : <manual author | block DV owner | the interface this is handed over at>
notes       : <anything the next reader would otherwise rediscover>
```

Under the header block, add one line saying what the whole matrix rests on — "the manual was Grepped
at that path" or "the manual could not be opened; rows derived from assumptions pasted into the
conversation, denominator unknown". Leave any field empty rather than filling it plausibly.

Post it where the **Matrix destination** slot says, in the shape that slot records, and check it
carries what the profile's **Sign-off** fact says that gate needs. If either is unfilled, hand the
matrix back and ask rather than choosing a destination yourself.

## Gotchas

- **A default is not an enforcement.** `aou-verdict: enforced-by-config` means a verified run could
  not have violated the claim. A value nobody set means the regression inherited it, the integrator
  may legally override it, and no run anywhere covers the other setting.
- **A pin says nothing about whether the mechanism was ever provoked.** A configuration that enables
  ECC and a regression that never injects a bit flip both pass this step. That second question is
  `dv-error-injection-ras`'s matrix, and a row citing only a pin is quietly answering the easier one.
- **The testbench noticing is not the element reporting.** A scoreboard message, a `UVM_ERROR` from a
  monitor, a checker in the environment — none of them exist in the integrator's system. Only the
  observable named in the Detection observable slot counts as detection.
- **A register bit set by boot software can be cleared by software later.** Dynamic enablement is
  revocable, so it is never enforcement; the useful question is whether the element complains when it
  is turned back off, which is a violation test, not a configuration check.
- **A time-interval assumption cannot be closed by simulation.** "The self test shall complete within
  the diagnostic test interval" — a run can show the test completes and reports; the interval is the
  integrator's timing budget against a number from the Metric source. The honest verdict is
  `aou-verdict: handed-over` with that number quoted and attributed to where it came from.
- **Violation tests look exactly like regressions.** They end in a deliberate error or fatal, so a
  triage pass counts them as failures and somebody eventually "fixes" the test. Tag them by the
  Violation-test convention and warn `dv-regression-triage-routing` that this class exists.
- **The tail of the assumption list is the least verified part of it.** Assumptions added after the
  verification plan was frozen carry no evidence by construction, and they are usually the
  highest-keyed. When the budget is short, walk the tail first rather than the top.
- **A metric quoted in the manual is not evidence for the assumption beneath it.** The Metric source
  computed that number *assuming* the mechanism was enabled and effective. Quoting it back as proof
  of the assumption that enables the mechanism is circular, and it survives review because the number
  looks like data.
- **Assumption keys drift between revisions unless someone makes them stable.** If the Assumption
  keys slot says they are not, this matrix cannot be diffed against the last revision's — say that
  rather than reporting a delta that is really a renumbering.
- **An assumption about an internal signal is a misplaced requirement, not a weak assumption.**
  Dispositioning it wastes the budget and leaves the real defect — a requirement that escaped into
  the integrator's document — in place.

## Human verification — what a wrong answer looks like

Before the matrix goes anywhere, check:

- every row cites a file and a line, or a test name and its result file, or says plainly that it
  cites nothing
- no row is `aou-verdict: enforced-by-config` on the strength of a default, and none is on the
  strength of a register write that software can undo
- every `aou-verdict: violated-and-detected` row names the element's own observable, not a testbench
  check
- the denominator is the manual's assumption count from step 2, not the number of rows produced
- every `aou-verdict: not-checkable` row carries a proposed rewrite and is owned by the manual's
  author
- no `aou-verdict: handed-over` row is missing either its interface or the document it is handed over
  in
- the header names the manual revision and the regression the matrix was built against
- the coverage line is present, and if the manual could not be opened, nothing above it is being
  treated as verified

A wrong answer is a matrix reporting ninety-four per cent compliance where most rows say
`aou-verdict: enforced-by-config` and cite a parameter's default value. The second most common is a
matrix where every `aou-verdict: violated-and-detected` row's evidence is a scoreboard message — so
what was actually proved is that our testbench watches, not that the element reports.

## Done when

Every assumption in the manual has a row, every row has a verdict a file backs or an honest admission
that none does, and the assessor's next question is about one named row rather than about the
document.
