---
name: dv-release-gate
description: Run an IP or VIP release sign-off gate as an evidence-linked checklist — every exit criterion tied to an artifact on disk, every waiver adjudicated with an expiry, and the go or no-go recorded together with its rollback path. Use when a release is due and someone has asked you to sign, when you are handed a status summary and told the criteria are met, when a waiver is requested to get a release out of the door, or when you need to say in advance what would make you withdraw a release after it has shipped.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: IP/VIP Release Sign-Off Gate with Evidence and Rollback
  semiskill-function: design-verification
  semiskill-role: verification-lead
  semiskill-level: manager
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-09-24
  semiskill-tags: release, sign-off, gate, exit-criteria, waivers, rollback, evidence, ip, vip
---

# IP/VIP Release Sign-Off Gate with Evidence and Rollback

A release gate fails in one of two directions and both are expensive. It passes a release on a
checklist ticked from a status summary nobody re-opened, and the escalation arrives a month later
from whoever integrated it. Or it blocks a release for a week over an item waived two releases ago on
terms nobody wrote down. Both are the same defect: the tick and the evidence were never in the same
place.

The output is **a criteria table, a waiver adjudication, and one gate record** carrying the call, its
conditions, its rollback path, and a line saying how much of the checklist was verified from files
rather than reported by a person.

## When to use something else

This skill checks a plan that already exists against artifacts that already exist. It neither writes
the verification plan nor plans coverage closure; if the exit criteria were never written down, a
gate is the wrong place to invent them — say so and stop.

- A night of regression failures needs sorting before any of it reaches a gate — that is
  `dv-regression-triage-routing`. This gate **consumes** its bucket table; it never produces one.
- One blocking failure that has to be understood before it can be waived — `dv-sim-log-first-error`;
  to shrink it for whoever receives the release, `dv-minimal-reproducer`.
- A build that will not compile or elaborate — `dv-build-filelist-hygiene`. And if you cannot yet
  name where summaries, coverage and run areas land, you are not ready to gate anything:
  `dv-repo-orientation` is the map.

## Fill this in for our team

Five facts come from `_shared/team-profile.md` and are read from there rather than re-asked here:
**Regression summary** (step 3), **Coverage output** — where merged coverage lands (step 4),
**Known-issue list** (step 3, where each surviving failure has to land), **Area to owner map** (step
6, an owner for every condition and every blocking item) and **Sign-off** — who signs and on what
evidence (steps 1 and 8). Two copies of the owner map or the summary path drift apart silently, and
nothing in the pack can then say which one is stale.

Nine more facts are specific to a release gate, so they are asked here and nowhere else:

| Slot | What to fill in | Who knows |
|---|---|---|
| Exit criteria source | [[FILL: where our written exit criteria for an IP or a VIP release live, which revision applies to this release, and whether it is a file that can be read]] | verification lead |
| Release identity | [[FILL: what identifies one release for us — tag, IP version, VIP version, delivery number — and where that string is recorded]] | release manager |
| Deliverable manifest | [[FILL: what a release actually ships and where the list of it lives — RTL, testbench, VIP package, models, documentation, release notes]] | release manager |
| Previous sign-off record | [[FILL: where the last release's gate record is kept, and how long records are retained]] | verification lead |
| Waiver record | [[FILL: where waivers and coverage exclusions are recorded, what fields one entry carries, and whether an entry carries an expiry]] | DV lead |
| Coverage goals | [[FILL: the coverage numbers this release must meet, per metric, and which metrics are mandatory rather than advisory]] | verification lead |
| Bug bar | [[FILL: what severity of open bug blocks a release here, and the query or list that shows the open ones]] | verification lead |
| Evidence retention | [[FILL: where release evidence is kept once the run areas are cleaned, and how long it survives there]] | DV infra owner |
| Rollback path | [[FILL: how a release is withdrawn once delivered — what the step is called, who is authorised to carry it out, and how long it takes]] | release manager |

Two of these sit close to facts recorded elsewhere and are **not** the same fact. **Coverage goals**
is the set of numbers to meet; the profile's **Coverage output** is only where the merged report
lands — you need both. **Bug bar** is a property of the release, while
`dv-regression-triage-routing`'s *Blocking rule* decides whether one nightly bucket is
release-blocking; if your team has one rule answering both, write it once and point the other entry
at it rather than maintaining two that can drift.

**If a fact or a slot is unfilled, stop and ask. Do not guess a convention.** An invented threshold or
an invented rollback step is worse here than anywhere else in the pack: it gets signed and believed.

## Retrieval budget — read this before opening anything

A release's evidence is a coverage report of tens of thousands of lines, a regression summary of a
few thousand, and a scatter of run areas. The gate reads targeted fragments and nothing whole.

1. **Grep, Read and Glob work on files on disk.** A slide, a wiki page, a spreadsheet or a tracker
   query is not a file and cannot be searched. If a criterion rests on one, ask for the underlying
   artifact's path; if there is none, record that criterion as reported by a named person and mark it
   provisional. Nothing pasted into a message counts as verified.
2. **Never open a coverage report or a regression summary with Read first.** **Grep** for the line
   carrying the claim, then **Read** a bounded window of about 60 lines around it.
3. Per criterion the allowance is **one Glob, one Grep and one windowed Read** — does the artifact
   exist, does it carry this release's identity, and where exactly is the claim made. Cap the
   checklist at **12 criteria in one pass**: 36 calls at full spend. A longer criteria document is a
   second pass, not more reading.
4. Three artifacts sit outside that allowance rather than on top of it. Step 1 spends **two Globs,
   two Greps and two windowed Reads** across the manifest, the criteria document and the previous
   sign-off record; the regression summary and the merged coverage report — the two everyone quotes
   and nobody re-opens — get **two Greps and one windowed Read each**.
5. Waiver adjudication costs **one Grep per waiver id**, and only when the waiver record is a file on
   disk. Cap it at about **20**; past that, adjudicate in criteria order and name the ones left unread.
6. If any single **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it.
7. **Stopping rule.** When the budget is spent — about 65 calls, a full session's attention — stop.
   Every criterion not reached stays `outcome: not-checkable`; none is ever marked met because the
   others were. Then **state the coverage**: how many criteria you verified from files, how many were
   reported to you, and what the budget never reached. An unstated shortcut is worse than a stated one.

## Procedure

### 1. Fix what is being signed, and build the checklist from the written criteria

A gate signs one identified release of one identified deliverable set. Take the tag or version string
from the **Release identity** slot, use **Glob** to locate the **Deliverable manifest**, and spend one
**Grep** of that manifest for the identity string. If either arrived pasted into a message rather than
as a path, resolve that first — budget rule 1. Three things end the pass here rather than three steps
later: the identity string is recorded nowhere readable, so nothing can be tied to this release and
every criterion below is at best `outcome: not-checkable`; the manifest and the release notes disagree
about what ships, which is itself the finding; or the release is still moving, in which case ask the
release manager to freeze the tag, because evidence gathered across a moving target is about no
particular release.

Then open the **Exit criteria source**. If it is a file, **Read** it in bounded windows. If it is a
slide deck, a wiki page or a spreadsheet, **Read** cannot open it: ask the verification lead to state
each criterion, record who supplied it and when, and mark every criterion sourced that way
provisional. Number them one row each and do not merge them — "verification complete" is not a
criterion; split it into the artifacts that would show it, or record it as `outcome: not-checkable`
and name what would make it checkable. Take the signer list from the profile's **Sign-off** fact; a
criterion with no named signer is a question for the gate, not something for you to assign.

Last, spend one **Grep** and one windowed **Read** on the **Previous sign-off record**, for its
conditions and its waivers. Its unfinished conditions are this release's most likely blockers and its
waivers are the ones about to be renewed without discussion. It is the highest-value file in the
procedure and the one nobody opens.

### 2. Check every artifact for existence, identity and freshness — in that order

For each criterion's named artifact, spend the per-criterion allowance in this order, stopping at the
first failure:

- **Glob** the path. A path resolving to nothing is not evidence, however good the number quoted from
  it was. This is routine rather than rare — run areas are cleaned on a schedule, which is what the
  **Evidence retention** slot records.
- **Grep** it for the release identity string from step 1. An artifact carrying a different tag is
  evidence about a different release, and catching that is most of what a gate is for.
- **Read** one bounded window where the claim is actually made, and quote the line.

Evidence lies in four ways, in rising order of how often it is missed: it is about another build; it
no longer exists; it is a summary of a summary, typed by a person from a report they read once; or it
is partial, covering fewer inputs than the run that produced it (step 4). Say which of the four you
ruled out — ruling out the first two is not ruling out the last two.

### 3. Regression evidence — read the summary, not the claim

Use the profile's **Regression summary** fact and read its rows against the format recorded beside it:
**Grep** for the totals, **Grep** for the failing rows, then one windowed **Read**. Check four things
and no more: that the summary carries the same build tag as the release, which is step 2's identity
check applied here; that pass, fail and unrun account for the total, since a test that never started
did not pass; that every surviving failure lands on a known-issue entry key or on a waiver id, quoted
by the signature `dv-regression-triage-routing` produced for it, verbatim, because a freshly derived
one matches neither their table nor the known-issue list; and that nothing is counted twice — one
bucket of forty tests is one item at this gate, not forty.

Two questions the summary cannot answer are handoffs rather than inferences: **ask the regression
owner** whether any test was rerun to obtain a pass, and whether the summary covers the whole test
list or a subset. Record both as reported rather than measured.

### 4. Coverage evidence — the number, its denominator, and its exclusions

The **Coverage goals** slot says which metrics are mandatory and what each must reach. The agent
cannot merge databases or produce a report, so **ask the coverage owner to produce the merged report
for this release and to give you its path, and the path of the merge log**. Then spend the rule 4
allowance: **Grep** the report for the mandatory metric lines, and **Grep** it for the exclusion or
waiver files it applied.

Reported percentages are almost always post-exclusion. The pre-exclusion number plus the exclusion
list says whether the design was exercised; the post-exclusion number says what the team agreed to
stop at. Record which of the two you have, and if only one, say which. The merge log carries the check
nobody does: compare the inputs it merged against the number of runs the regression summary reports —
a merge that silently dropped a third of its databases still emits a clean and plausible report. If
the report cannot be produced or read, this criterion is `outcome: not-checkable`: not met, and not
waived either until step 5 says so.

### 5. Adjudicate the waivers — this is the decision, not the paperwork

The **Waiver record** slot says where waivers live, what one entry carries, and whether it has an
expiry. Spend **one Grep per waiver id** under budget rule 5. Every waiver needs five things stated:
what is waived, specifically; why now; who authorised it; when it expires; and what would make it
unnecessary. Missing any one is a reason to send it back, not to approve it with a note.

| The waiver asks to | Approve only when | Reject when |
|---|---|---|
| skip a check that never ran | the limit is written down and the check is scheduled into a named later release | the check was skipped because it was failing |
| accept a coverage hole | the hole is named as specific bins, structures or features, and the exclusion is in the waiver record rather than only inside a report | the hole is expressed only as a percentage — a percentage names nothing and cannot be reviewed |
| ship with an open bug | it sits below the **Bug bar**, with a named owner and a target release | its severity was lowered in order to clear this gate |
| accept a failing test | the failure carries a signature and a known-issue key, and the affected feature is named | it is called flaky with no measured rate and no entry key |
| defer documentation | the missing part is named and dated, and no recipient decision depends on it | the deferred part is what tells a recipient how to configure what they receive |

Three rules do most of the work. A waiver with **no expiry** is a permanent change to the
specification wearing a temporary hat — give it a date, or route it to whoever owns the specification.
A waiver arriving for its **third renewal** is a requirement the team has decided not to meet; say so
at the gate rather than approving it a fourth time. And a waiver you cannot state in one sentence to
the person receiving this release is not one you can approve on their behalf.

### 6. Make the call

The record's `gate call` line takes one of three values and no others.

- `gate call: go` — every mandatory criterion is met or waived on approved terms, and the coverage
  line says how many you verified from files yourself.
- `gate call: no-go` — one mandatory criterion is not met and no waiver was approved for it. Name the
  criterion and its evidence path, not the general area.
- `gate call: go-with-conditions` — every condition names an artifact, an owner and a date, the owner
  routed through the profile's **Area to owner map** rather than chosen because the name is plausible.
  A condition missing any of the three is not a condition, which makes the call `gate call: go` — say
  which one you mean rather than letting the softer word do the work.

`outcome: not-checkable` is not a pass. Count those separately and list them by name: a gate signed
with four unverifiable criteria is a materially different decision from one signed with none.

### 7. Write the rollback path, before the release ships

The cheapest moment to answer "how would we take this back" is while the answer is still
hypothetical. From the **Rollback path** slot, record four things:

- **Withdrawal** — the named step that removes this release from wherever consumers take it from, who
  is authorised to carry it out, and how long it takes.
- **Notification** — who has to be told, and what they do meanwhile: stop integrating, pin the
  previous version, rebuild against it.
- **The superseding path** — whether a fix ships as a further release or the previous one is restored.
  Those cost the recipients different amounts, and the choice is not yours alone.
- **The tripwire** — the evidence that would trigger any of the above: an escalation of a named class,
  a failure in a named criterion, a coverage claim shown to be wrong.

For anything already delivered outside the team, withdrawal is a notification exercise rather than a
deletion — the copies are elsewhere. Write down who makes that call before you need them.

### 8. Write the gate record

One block per criterion, in the document's own order, then one record for the gate itself:

```
criterion : <id and the criterion statement, quoted from the exit-criteria document>
outcome   : met | not-met | waived | not-checkable
evidence  : <path, and the line or section where the claim is actually made>
identity  : <the release identity string carried by that artifact, or "absent">
waiver    : <waiver id and expiry, when the outcome is waived>
```

```
release    : <the identity string, verbatim from wherever it is recorded>
scope      : <IP or VIP, and the deliverable manifest path>
gate call  : go | no-go | go-with-conditions
criteria   : <a met, b waived, c not-met, d not-checkable of m in the document>
blocking   : <each not-met criterion, with its evidence path and its owner>
waivers    : <a approved, b rejected, c expired of m considered>
conditions : <each condition, with its artifact, its owner and its date>
rollback   : <withdrawal step, who is authorised, how long it takes, who is told>
tripwire   : <the evidence that would trigger that rollback>
signers    : <who signs and for what, from the profile's Sign-off fact>
coverage   : <n of m criteria verified from files by you; k reported by a named person; what the
              budget did not reach>
notes      : <anything the next gate would otherwise rediscover, including every value that came from
              a person rather than from a file>
```

`evidence`, `coverage` and `notes` carry the same meaning here as in `dv-ral-bringup` and
`dv-regression-triage-routing`, so a blocking item pasted from their output keeps its vocabulary.
Leave a field blank rather than filling it plausibly: a blank is a question someone answers in a
message, an invented value is a wrong answer that has been signed.

## Gotchas

- **A green regression may be a green rerun.** Many flows rerun failing tests and report the later
  result. A test that passed on the second attempt is a test with an unexplained failure, which is why
  step 3 asks the regression owner instead of inferring it from the summary.
- **Coverage percentages are quoted after exclusions.** The number reaching the release note is
  post-exclusion; the number saying whether the design was exercised is the pre-exclusion one plus the
  exclusion list. Check the exclusion file's own age — exclusions written for an earlier revision
  quietly keep excluding.
- **A merged report is not proof that everything merged.** Merge steps commonly skip databases that
  are missing or built against a different model and still emit a complete-looking report. A report
  over two-thirds of the runs looks exactly like a report over all of them.
- **Waivers do not expire on their own.** An expiry field nobody reads is a comment. If waivers here
  carry no expiry at all, every waiver ever granted is still in force and the gate is signing an
  accumulated specification change rather than one release.
- **A VIP release is signed on different evidence from an IP release.** A VIP ships into somebody
  else's environment, so what it supports of the protocol, which simulator versions it was built and
  exercised against, whether existing configuration knobs still behave as they did, and whether the
  integration example still matches the API are all exit criteria for it — and none of them are exit
  criteria for a block of RTL. An IP checklist applied to a VIP misses exactly what its recipients hit
  in the first hour.
- **"No open bugs" is a claim about a query at a moment.** Record the query and when it was run.
  Without both, the claim decays from the day it is made and nobody can later tell whether it was ever
  true.
- **Evidence in a run area has an expiry date.** A record whose paths resolve to nothing six weeks
  later cannot be audited when the escalation arrives. Copy the artifact into whatever the **Evidence
  retention** slot names; do not link the scratch area.
- **A condition with no owner and no date is decoration.** Conditions are how a gate says yes without
  lying, and an unowned one is never checked. Two conditions with owners beat eight without.
- **A gate that has never returned no-go is not a gate.** If no release was ever stopped here, the
  criteria describe what the team already does rather than what a release needs — worth saying to
  whoever owns the criteria document, and not a finding about this release.

## Human verification — what a wrong answer looks like

Before circulating the record, check:

- every `outcome: met` names a path plus a line or section, and that artifact carried this release's
  identity string; nothing was marked met from a status summary, a slide, or a sentence in a message
- the coverage figures say whether they are pre- or post-exclusion, and the merge input count was
  compared against the run count
- every approved waiver has an expiry and a named authoriser, and none had its severity adjusted in
  order to clear this gate
- every condition under `gate call: go-with-conditions` carries an artifact, an owner and a date
- the rollback line names a person and a duration, and the tripwire names evidence rather than a
  feeling
- the `coverage` line's denominator is the number of criteria in the document, not the number you
  managed to check

A wrong answer is a fully ticked checklist produced in ten minutes: every criterion met, no path
against any of them, no waiver mentioned, no rollback line, and a coverage figure quoted to two
decimal places with nothing said about what it excludes. The second most common is a no-go raised over
a criterion waived two releases ago, on terms still recorded in the previous sign-off record that
nobody opened.

## Done when

The record can be circulated as it stands — every met criterion has a path a reader can open, every
waiver has an expiry, and if this release has to be withdrawn next week nobody has to work out how.
