---
name: dv-customer-defect-handoff
description: Turn an isolated customer failure into an internal defect R&D can act on — duplicate-checked against the known-issue list and the release notes, with a pinned version matrix and an expected-versus-actual backed by a documentation clause. Use when a customer escalation has been narrowed to our tool or our VIP, when R&D has bounced a report asking which version or where the manual says that, when the report arrived as an email and has to become a record, or when you suspect we already fixed this in a later release.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Translating a Customer Report into an R&D-Ready Internal Defect
  semiskill-function: design-verification
  semiskill-role: applications-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-05-21
  semiskill-tags: escalation, customer-defect, duplicate-check, release-notes, versioning, documentation, handoff
---

# Translating a Customer Report into an R&D-Ready Internal Defect

A customer report describes an experience; an internal defect describes a reproducible fact about our code.
Reports bounce back from R&D for four reasons: nobody pinned which versions ran, the expected behaviour was
asserted rather than cited, it was already fixed or already documented as a limitation, or the only reproducer was
material we may not keep. The output is **one defect record, a duplicate verdict with the range it was searched
over, and a coverage line** separating artefact facts from the customer's sentence.

## When to use something else

This skill starts **after** the failure has been isolated to something we ship. Before that:

- The case is still a claim — "your VIP is broken" plus whatever was attached: `dv-customer-escalation-isolation`
  settles which of five fault domains broke. Come here when it lands on our VIP or our tool and carry that record
  over — **honestly**. Its `signature` and `known` lines are steps 3 and 4 already done. Its `versions` line is
  **not** all of step 2: it triples *one* quantity (their claim, their log, our manifest), settling the
  product-release row and no other, so the patch-level, simulator, platform and methodology-library rows still
  cost step 2 its Grep and Read window.
- One of our own failing logs with no idea what broke — `dv-sim-log-first-error`.
- Their build fails to compile or elaborate — `dv-build-filelist-hygiene`.
- The failure is a register access — `dv-ral-bringup`.
- A whole regression of our own failures — `dv-regression-triage-routing`.

Afterwards `dv-minimal-reproducer` shrinks the case on the signature; `dv-repo-orientation` maps an unknown tree.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Version banner | [[FILL: what our tool and our VIP print to identify their own version, and where in a log or report that line appears]] | your R&D contact |
| Version matrix rows | [[FILL: which version facts our defect record requires — product release, patch level, simulator, platform, methodology library]] | R&D triage owner |
| Release-note text | [[FILL: where our release notes, fixed-issue lists and change histories are kept as files that can be read, and which releases are kept]] | release manager |
| Documentation set | [[FILL: which documents we are allowed to cite as expected behaviour, where they live on disk, and how a citation is written for us — document name plus clause or section]] | documentation owner |
| Reproducer bar | [[FILL: what R&D require before they will accept a record — a runnable testcase, a saved log, a waveform, or a written sequence — and which of those we are permitted to keep from a customer, for how long]] | R&D triage owner |
| Case key | [[FILL: what identifies one customer case internally, and our rule for referring to the customer inside a defect record without naming them]] | support lead |
| Escalation route | [[FILL: which R&D queue or component owner an isolated defect goes to, and what that route is keyed on — product, component, or release train]] | support lead |

Four more facts are pack-wide, in `_shared/team-profile.md`; read them there rather than re-interviewing anyone:
**Known-issue list** (step 4), **Bug convention** (the record's title and required fields, step 8), **Run
identity** (step 2) and **Simulator** (step 2, one matrix row).

Two rows above look like profile rows and are not. **Version banner** is not the profile's Fatal markers: a banner
prints whether or not the run failed, so Greping a fatal marker finds nothing in a report about wrong output that
never errored. **Escalation route** is not the Area to owner map: that map routes a failing design area to its
owner, this routes one of *our shipped components* to its maintaining team.

**If a slot is unfilled, stop and ask.** An invented release name or clause number is worse than a blank one: it
is quoted back to the customer.

## Retrieval budget — read this before opening anything

Case bundles arrive as whole directories, release-note archives span years, and a documentation set is larger than
either. Work in this order and stop as soon as the record is fillable:

1. **Grep and Read work on files on disk.** A report pasted into an email or a chat window cannot be searched —
   step 1 resolves it to a path. Until then every field below is the customer's claim, and the record says so.
2. **Never open a customer log, a release-note archive or a document with Read first.** Glob to find, Grep for a
   line number, Read only a bounded window.
3. The budget is **two Globs, five Greps and four windowed Reads of about 40 lines**: Glob in steps 1 (case
   material) and 5 (the release-note tree, if it is a tree); Grep in steps 2 (version banner), 3 (failing
   message), 4 (known-issue list), 5 (release notes) and 6 (documentation set); one Read after each Grep in steps
   2, 3, 5, 6.
4. A Grep returning more than about 200 hits is too broad — anchor it on the `where` component name first.
5. Stopping rule: when the budget is spent, write `?` in whatever is unknown. If the documentation Grep finds no
   clause, **do not browse the rest of the set** — that silence is a result (step 6), not a reason to read on.
6. Arriving from `dv-customer-escalation-isolation` buys back **two Greps and one Read, not more**: steps 3 and 4
   are done, so verify rather than re-Grep them. Step 2 is only *part* paid — that record settles the
   product-release row, not the patch-level, simulator, platform or methodology-library rows, so step 2 still
   spends its own Grep and Read.
7. State what you covered: the release range the duplicate search spanned, and which matrix rows came from an
   artefact rather than from the customer.

## Procedure

### 1. Get the case onto disk, and separate what we may keep from what we may not

If the report arrived as an email or chat message, ask for the attachments to be saved to a readable directory and
for that path. **Glob** it once — the first of two — to inventory what is really there; customers routinely
describe an attachment they did not send. Record the case under the **Case key** slot's convention (it fills
`escalation`) and apply its naming rule from here on: the record names the case, never the customer, and no
customer host name or site path survives into any field. Check the material against the **Reproducer bar** slot's
second half — what we may keep, and for how long. That is a question for a person; put it to whoever is still on
the thread, because it is unanswerable three weeks later. Then name the deliverable it was isolated to and the
component inside it.

### 2. Pin the version matrix from the artefact, not from the email

The sentence in the email is a claim; the banner in the log is evidence, and when the two disagree *that
discrepancy is often the whole defect*. **Grep** the artefact for the **Version banner** strings (Grep one of
five) and **Read** one 40-line window at the first hit. That window usually carries several rows at once: our
release and patch level, the **Simulator** and its version from the profile, the platform, and often the
methodology library the environment was built against — the rows a record carried in from
`dv-customer-escalation-isolation` does not hold, which is why this Grep is spent even on a pre-isolated case.
Fill every row the **Version matrix rows** slot lists; one you cannot fill from the window is marked
customer-reported and attributed, or left `?`.

While the window is open, compare it against our **Run identity** convention and note which identifiers the
artefact carries. Their run is not one of ours, so unmatched identifiers are things to ask the customer to quote,
not a lookup you can finish here.

### 3. Derive the failure signature

Follow `_shared/failure-signature-schema.md` exactly — same field order, same normalisation rules. **Grep** the
artefact for the message the customer quoted (Grep two) and **Read** one 40-line window around the lowest-numbered
hit. The `phase` token says where in their flow the complaint sits, and all five values are reachable: a
diagnostic before anything ran is `compile` or `elab`; a message timestamped inside the simulation is `run`; an
end-of-test check or end-of-run report is `finalise`; a coverage, log-parsing or checking step that ran after the
simulation exited is `post`.

If failing output appears *above* that window the quoted message is a cascade line: hand it to
`dv-sim-log-first-error`, take its signature and repro block, and come back. Normalise properly — the schema's six
baseline rules cover times, data literals, indices, seeds, absolute paths and instance paths, but a bare host name
is **not** among them; it belongs to the schema's own team-local row for extra values to normalise. Strip it
whether or not that row is filled, and say so in the notes.

### 4. Search the known-issue list before the release notes

The profile's **Known-issue list** row says what this is and whether it can be read at all. Arriving from
`dv-customer-escalation-isolation`, its `known` line is this step's answer and the Grep is not spent twice.

- **A file on disk.** One **Grep** (three of five) carrying two patterns: the signature's `where`, and the
  distinctive fragment of `what`. Compare exactly; a match ends the work, named with whatever key that list uses.
- **A tracker a person must query.** Read and Grep cannot reach it. Assemble the record anyway and ask whoever can
  query it to compare the signature; `known` stays pending their answer.
- **Unfilled.** Say the check did not happen; never call the failure new. "Not in the list" is a fact about the
  list, never about the world, and the record says which.

### 5. Search the release-note text over an explicit range

Two questions live here. **Already fixed**: a fixed-issue entry matching the signature makes the answer an upgrade
to a *named* release — `defect kind: fixed-in-later-release`, and no R&D work at all; naming no release just
produces a reply asking which one. **Already documented as a limitation**: an entry saying the behaviour is
deliberate makes it `defect kind: documented-limitation`, and the deliverable is an explanation. The
**Release-note text** slot says where these live and which releases are kept. **Glob** that tree once if it is a
tree (the second Glob), then **Grep** once (four of five) across the releases *between the version step 2 pinned
and the newest release kept* — that range is the answer to "which versions did you search", and a record that
cannot state its range has not searched. **Read** one 40-line window on the best candidate. Release notes index
badly — whoever fixed it rewrote the description, so Grep the component name from `where` first and the message
text second.

### 6. Expected versus actual, with a citation

**Actual** is quoted verbatim from the artefact with its path and line number — not paraphrased, not retyped from
memory, not the customer's summary. **Expected** must come from a document; the **Documentation set** slot says
which we may cite and how a citation is written. **Grep** that root for the feature or class name from the
signature's `where` (the fifth and last Grep), **Read** one 40-line window on the clause, and record document and
clause. Cite by name and clause, never by link and never from memory. If no clause states the expected behaviour,
that is a result, and the three ways it lands go to three different people:

- the document states the **opposite** of what happened — a strong defect, the clause its evidence line
- the document is **silent** — `defect kind: enhancement`, routed to the product's scope owner, not a bug fixer
- the document is **ambiguous** — `defect kind: doc-gap`, both readings quoted; the ambiguity is the finding

An expected-versus-actual with no citation is an opinion, and R&D's first question is where it says that.

### 7. Settle the defect kind, and check the record clears the bar

Take the five values in order — the first that fits wins, because each earlier one means less work for everyone:
fixed-in-later-release, documented-limitation, doc-gap, enhancement, defect. Then decide `class`. Our own shipped
code is the thing under test, so a fault in it is `class: design`. A licence, install, platform or environment
failure at the customer's site is `class: infrastructure` and no R&D defect at all — it goes back as an answer
with the matrix row that shows it. Where nothing on disk settles the side, `class` is `unknown`, not a guess.
Last, check the record against the **Reproducer bar** slot's first half. If what we may keep is less than what R&D
require, say so in the notes *now*: a defect closed as unreproducible after the retention window expires costs the
cycle twice. If the bar wants something smaller, `dv-minimal-reproducer` does that on step 3's signature.

### 8. Write the record

The profile's **Bug convention** row gives the title shape and required fields; this block is what they are filled
from. `escalation`, `versions`, `known`, `signature`, `phase`, `class`, `run id`, `log`, `coverage` and `notes`
are spelled the way `dv-customer-escalation-isolation` and `dv-sim-log-first-error` spell them, so a case carried
in from either keeps its vocabulary.

```
escalation  : <our case identifier, and the customer-facing one if they differ>
product     : <the shipped component the failure was isolated to>
signature   : <phase>|<kind>|<where>|<what>
phase       : compile | elab | run | finalise | post
class       : design | infrastructure | unknown
defect kind : defect | documented-limitation | fixed-in-later-release | doc-gap | enhancement
versions    : <one line per row the matrix asks for, each marked artefact or customer-reported>
expected    : <the behaviour the document states, quoted>
citation    : <document name and clause, or ? if the search found none>
actual      : <the artefact's own words, with path and line number>
known       : known-issue <key> | not-matched | list-not-readable
release note: <the entry and the release it names, or none found>
searched    : <the release range the release-note search actually covered>
run id      : <what identifies the failing run, in our run-identity terms>
log         : <path, and the line range worth reading>
route owner : <the R&D queue or component owner this routes to, per the Escalation route slot>
coverage    : <which rows came from an artefact, which from the customer's word, what the budget missed>
notes       : <what we may keep of their material and until when, plus what R&D would otherwise ask for>
```

The routing line is `route owner`, not the bare noun: the pack's field registry locks that spelling to the
profile's area-to-owner map, and this line deliberately answers a different question — which R&D queue maintains a
shipped component, per the **Escalation route** slot. Two records pasted into one table must never put two
questions under one label. `coverage` sits above `notes` because the registry keeps `notes` last in every block. A
line that cannot be filled from text on disk gets `?`: a `?` is triaged, a confident wrong version is quoted back.

## Gotchas

- **The version in the email is a claim; the version in the banner is evidence.** Environment modules, a site
  wrapper or a half-applied patch each make the customer wrong about what ran, and that gap is often the defect.
- **The methodology library belongs in the matrix even when nobody asked for it.** A component built against one
  library version and elaborated against another fails *inside* our code without being our fault, and the record
  is unfalsifiable until that row exists.
- **Confirm the attachment is from the failing run.** Customers attach the log from the run that passed, or from
  before they changed the setting, far more often than expected — hence step 2's run-identity comparison.
- **A documented limitation filed as a defect costs the customer more than an answer would.** But an *ambiguous*
  clause is a real finding — a defect against the document, and why the next customer files the same case.
- **The customer's testcase is usually their intellectual property.** Record the retention limit in the notes; one
  deleted before R&D reaches the record becomes a close-as-unreproducible and a second escalation.
- **Same message with a different `where` is two defects.** Merging two customers into one record loses the second
  version matrix, which is very often what tells them apart.
- **A failure only reproducible at the customer is usually a row in the matrix, not a line in our code.** Work
  down the matrix — simulator, platform, library, patch level — before concluding otherwise.
- **Normalise the signature before you search with it.** Seeds, times and absolute paths come out under the
  schema's baseline rules; the customer's host name does not — that is a team-local addition the schema leaves as
  a row to fill. Strip it either way, or both searches return a silence that reads as novelty.

## Human verification — what a wrong answer looks like

Before the record leaves your hands, check:

- every matrix row is traceable to an artefact line or marked customer-reported, and a pre-isolated case has not
  had its patch-level, simulator, platform or library rows copied from a record that never held them
- the expected behaviour names a document and a clause; if `citation` is `?`, this is not `defect kind: defect`
- `known` and `release note` say what was actually searched, and `searched` names the release range, rather than
  the bare claim that nothing matched
- the signature is clean under the schema's baseline rules — no seed, time, absolute path or customer identifier —
  and the host name too, a team-local normalisation the schema defers, so the notes say you applied it
- no customer name appears anywhere in the record, per the case-key rule
- the notes say what we may keep and until when, and the coverage line names its own shortfalls

A wrong answer quotes the email's version as though it came out of the log, files a documented limitation as a
defect, or declares "not a duplicate" after searching one release's notes.

## Done when

R&D can open the record, reproduce from what is in it, and reach the same expected-versus-actual without
contacting you or the customer.
