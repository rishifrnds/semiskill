---
name: dv-escalation-ownership
description: Take ownership of a customer escalation on a shipped IP or VIP release — establish severity and blast radius from evidence on disk, build a commitment set someone can sign, set the comms cadence, and close the loop back into the verification plan. Use when an escalation lands on your product line and someone asks how bad is it and who else is affected, when a customer says our IP broke their regression or their tape-out, when you have to give a date to a customer, or when a patch has shipped and nobody has written the check that would have caught it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Owning a Customer Escalation to Closure
  semiskill-function: design-verification
  semiskill-role: verification-lead
  semiskill-level: director
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-09-14
  semiskill-tags: escalation, customer, severity, blast-radius, commitments, closure, verification-plan
---

# Owning a Customer Escalation to Closure

An escalation is not a hard debug problem wearing a suit. The debug is the part your team already
knows how to do; what goes wrong is everything around it — a severity set by the volume of the mail
thread rather than by the customer's exposure, a date promised before the debug converged, a blast
radius nobody counted, and a patch that ships without one check that would have caught it.

The output is four things you can be held to: **a severity with the sentence from our own scale that
justifies it, a counted blast radius, a commitment set with a signer on every line, and the named
pre-silicon artifact the escalation closes into.** Not a status summary.

## When to use something else

Use this when you own the escalation, not when you are debugging inside one. A single failing log the
customer sent is `dv-sim-log-first-error` — it goes far deeper into one log than the budget here
allows, and step 2 borrows its first two Greps and stops. A regression gone red after the fix is
`dv-regression-triage-routing`; shrinking the failure into something you can hand back to the customer
is `dv-minimal-reproducer`. A customer whose build will not compile against our release is
`dv-build-filelist-hygiene`, and a register-access failure in their integration is `dv-ral-bringup`.

## Fill this in for our team

Five facts this procedure spends are pack-wide. They live **once**, in `_shared/team-profile.md`, and
are read from there — a second copy of the owner map drifts and nothing can say which is stale.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Fatal markers** | step 2, signing the one customer log that gets opened |
| **Known-issue list** | step 2, deciding whether a shipped bug was already known |
| **Regression summary** | step 4, whether our own regression touches their configuration |
| **Area to owner map** | step 5, the only thing the technical routing may key on |
| **Coverage output** | step 7, the point that should have been hit |

Eight facts are specific to owning an escalation, so they are asked for here and nowhere else.

| Slot | What to fill in | Who knows |
|---|---|---|
| Severity scale | [[FILL: our severity levels, the sentence defining each one, and who is allowed to set or change one]] | verification lead |
| Escalation intake | [[FILL: where a customer escalation is recorded for us, which fields it carries, and whether that record is a file on disk or a tracker a person must query]] | applications lead |
| Release manifest | [[FILL: where the record of what shipped in each release lands, and whether it names the configurations and the customers who took it]] | release owner |
| Customer configuration | [[FILL: where we record the configuration a customer actually integrated, and whether we keep a copy of it on disk]] | applications engineer |
| Commitment vocabulary | [[FILL: the categories of promise our organisation may give a customer — workaround, patch, fix in a named release — and who signs each category]] | program manager |
| Comms cadence | [[FILL: how often an escalated customer is updated, through whom, and what one update must contain]] | program manager |
| Verification plan | [[FILL: where the verification plan for this IP lives, what one row carries, and whether it is a file that can be read]] | block DV owner |
| Waiver record | [[FILL: where we record a deliberately excluded, waived or deferred check, and what an entry must carry]] | DV lead |

**Escalation intake is not the profile's Bug convention.** That convention describes an internal bug
filed against ourselves; the intake record is the customer-facing artifact this escalation is tracked
by. Different owners, fields and lifetimes — fill both, and do not fill one from the other.

**If a slot or a profile fact is unfilled, stop and ask. Do not guess a convention.** An invented
severity level or commitment category is worse than silence: someone who trusted you repeats it to a
customer, and it cannot be taken back.

## Retrieval budget — read this before opening anything

The artifacts are a release manifest with thousands of rows, a plan with hundreds, and whatever the
customer sent, which is usually a very large log. The whole ledger is **one Glob, fifteen Greps and
five windowed Reads**.

1. **Grep, Read and Glob open files on disk.** A mail thread, a ticket, a screenshot and a pasted log
   tail are none of those. Resolve every artifact to a path in step 1, or say plainly which later
   steps did not happen.
2. **Never open a customer log, a manifest or a plan with Read first.** Grep for the line, then Read a
   bounded window around it.
3. The ledger by step: step 1 spends 1 **Glob** and 1 **Read** of about 80 lines; step 2 spends 4
   **Greps** — two on the log, two on the known-issue list — and 1 **Read** of about 80 lines; step 3
   spends up to 6 **Greps**, one directory per call, and 1 **Read** of about 60 lines; step 4 spends 1
   **Grep** and 1 **Read** of about 60 lines; step 7 spends 4 **Greps** and 1 **Read** of about 60
   lines. Steps 5, 6 and 8 open nothing — they spend evidence already gathered.
4. If any **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it to one
   directory, or anchor a longer string, before reading anything around the hits.
5. **Stopping rule.** When the ledger is spent and severity or blast radius is still unsettled, stop:
   the unsettled one becomes a named question with the person who can answer it, never an estimate.
   Then **state what you covered** — which numbers came out of a file you searched, which a person
   reported, and which were never established. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Get the escalation and its evidence onto disk

Use **Glob** once against the **Escalation intake** slot to locate this escalation's record, then
**Read** one bounded window of it: the customer, the release they are on, the date it landed, and the
claim in their own words. If that record is a tracker rather than a file, say so now — everything
below still works, but those four values came from a person and step 8 must attribute them.

Then ask the applications engineer for the **path on disk** of every artifact the customer sent — the
failing log, their configuration, their filelist. A log pasted into a thread cannot be searched; if no
path can be produced, name which parts of steps 2 and 3 did not happen rather than reasoning over the
fragment as though it were the log.

Keep the **claim** and the **evidence** apart from the first pass onward. "Your IP hangs on the third
descriptor" is a claim; a log line with a number is evidence. Escalations regularly turn out to be a
different failure from the one their title names, and a record that never separated the two cannot
show when that happened.

### 2. Set severity from the customer's exposure, on our scale

Severity is the number every later decision hangs off, and the one most often set by how loud the
thread got. Take the levels, their defining sentences, and who may set one from the **Severity scale**
slot. Do not invent a level and do not rank on your own sense of how bad the bug is: quote the one
sentence of the scale the evidence satisfies, and record which sentence it was. Two properties raise
exposure independently of how hard the fix looks — **wrong data that does not announce itself** (a
hang stops the customer, a silently wrong result reaches their silicon, and the quiet one is worse),
and **no workaround**, which is a question about their configuration rather than about our design.

If the customer's log arrived as a path, derive a signature from it following
`_shared/failure-signature-schema.md` — same field order, same normalisation rules — with **two
Greps** (the profile's Fatal markers, then the earliest hit's line number) and **one windowed Read**
starting about 60 lines before that hit. That is all the log work this skill does.

Then spend **two Greps** on the profile's Known-issue list, one for the signature's `where` and one
for the distinctive fragment of `what`, and only when that list is a file on disk. If it is a tracker,
the match is a handoff: ask its owner to compare the signature and record the check as pending. A
signature that matches a known issue changes the escalation entirely — the question becomes why a
known issue shipped, which is a process finding and belongs above the debug in the record.

### 3. Count the blast radius in configurations and releases, not complaints

Spend **up to six Greps**, one directory per call, across the **Release manifest** and **Customer
configuration** slots, plus **one windowed Read** of the manifest section naming the implicated
release. Three questions, in this order:

1. **Which releases carry the code path?** The one the customer is on is the floor, not the answer.
2. **Which shipped configurations reach it?** A parameterised IP has a configuration space no
   regression covers whole, and the escalated setting is frequently one nobody else took.
3. **Who else is on those releases with those settings?** Only from the manifest's own customer
   column; if it has none, this is a handoff to the release owner and the count stays `?`.

Report the radius as fractions with both denominators — "3 of 11 shipped configurations, across 2 of 5
releases still in the field; customers not counted, the manifest carries no customer column". A bare
"limited exposure" is not a finding, and it is the sentence people remember when the second customer
writes in. The customers who have **not** complained are the reason this step exists.

### 4. Decide honestly whether it reproduces here

The agent cannot start a simulation, build a model or hold a licence. Ask the engineer to attempt the
reproduction **in the customer's configuration rather than our default**, and to give you the path of
the log it wrote. Then spend **one Grep** of the profile's Regression summary and **one windowed
Read** to establish whether any test of ours exercises that configuration at all — a different question
from whether the bug reproduces, and the more useful one for step 7. Record exactly one of these four:

- `reproduced-here` — it failed in their configuration, and you have the log path.
- `not-reproduced` — attempted in their configuration and it did not fail. That is a finding about the
  gap between our environment and theirs, not a verdict on their claim.
- `not-attempted` — nobody has tried. Say so; an untried escalation reported as unreproducible is the
  most damaging single line available in this record.
- `customer-only-config` — their configuration cannot be built here at all. Name the missing piece.

Reproducing on our default configuration, not seeing it, and calling the escalation unreproducible is
the most common wrong answer in this whole procedure.

### 5. Build the commitment set, one line per promise, each with a signer

Take the categories our organisation may promise from the **Commitment vocabulary** slot. Do not
invent a category, and do not launder a hope into a promise by writing it in the same list as one.
Every commitment line carries four things: **what**, **to whom**, **by when**, and **who signed it**.
A line with no signer is a draft, and a draft read aloud on a customer call becomes a commitment
nobody agreed to. Where the debug has not converged, the honest commitment is a date for the *next
update* — which you can always keep — rather than a date for the fix, which you cannot.

A workaround is a commitment too: telling a customer to disable a feature commits us to a
configuration that may be in no regression at all. Check it against step 4 first, and if it is
unverified, say so in the same sentence that offers it.

Route the technical work on the signature's `where` through the profile's **Area to owner map**, never
on the customer's description of the symptom. A blank owner with two named candidates is a question
someone answers in one message; a confidently wrong owner burns a week of the escalation's clock. The
profile's **Sign-off** fact is a different thing from a commitment signer — sign-off accepts
verification evidence for a release, a signer promises a category to a customer. If your organisation
makes them the same person, record that as an observation rather than assuming it.

### 6. Set the comms cadence and draft the update

From the **Comms cadence** slot: how often, through whom, and what one update must contain. The agent
drafts the text; a person sends it, and the record names that person. Where the slot does not say what
an update contains, these six are the minimum, in this order — what we know today in the customer's
own terms; the agreed severity and whether it moved; which of their configurations are affected and
which we checked and cleared; the workaround available today, or "none yet" and never "coming soon";
the one thing being done now and who is doing it; and the date and channel of the next update.

Three cadence rules survive contact. **A cadence kept with nothing new beats a cadence broken with
news** — silence reads as no progress, and the customer's next mail goes above you rather than to you.
**The channel is part of the promise**, so an update posted somewhere other than the last one reads as
no update at all. And **never move the severity in an update without saying you moved it**, quoting
the scale sentence that now applies and naming who agreed to it.

### 7. Close the loop into the pre-silicon artifacts

A patch closes the customer's problem, not the escalation. The escalation is closed when a check
exists that fails on the old design and passes on the new one, and that check lives somewhere that
runs without anyone remembering this week. Name the artifact with **two Greps** of the **Verification
plan** slot's file — one for the feature, one for the customer's configuration setting — and **one
windowed Read** around the hits. Exactly one of three findings follows, and the record says which:

- **A row exists, a test exists, and it passed.** The check is wrong, not missing — wrong stimulus,
  wrong checker, or a configuration the test never sets. The most valuable outcome available here, and
  the one people are most reluctant to write down.
- **A row exists with no test**, or with a test that never entered the nightly list. The plan
  described the intent and nothing enforced it.
- **No row at all.** The feature or the configuration was never planned for, which makes this a
  planning finding and puts the plan's owner on the closure list.

Then two single **Greps** more: the profile's Coverage output for the point that should have been hit
— and if ours is not a readable file, say that rather than implying it was checked — and the **Waiver
record** slot for an entry covering this check. A waiver that excluded exactly this case is the finding
of the whole escalation and belongs at the top of the record, not in a footnote. Every closure action
is a handoff and is phrased as one: ask the block owner to add the named plan row, ask the DV owner to
add the test to the nightly list, ask the coverage owner to withdraw the exclusion.

### 8. Write the escalation record

```
escalation : <the intake record's own key, and the date it landed>
severity   : <the level, and the scale sentence that justifies it, quoted>
signature  : <phase>|<kind>|<where>|<what>, per the shared schema, or "not derived — no log on disk"
class      : design | infrastructure | unknown
reproduced : reproduced-here | not-reproduced | not-attempted | customer-only-config
blast      : <n of m shipped configurations, across p of q releases in the field, r customers>
owner      : <name from the area map, or blank plus the candidates it makes plausible>
run id     : <whatever identifies the run behind our reproduction, if there is one>
log        : <path, and the line range worth reading>
commitments: <one line per promise — what, to whom, by when, signed by whom>
gap        : <the plan row, test or coverage point that should have caught this, named>
closure    : <the handoffs from step 7, each with the person asked>
coverage   : <what was searched, what a person reported, what was not established>
notes      : <anything the next owner would otherwise rediscover>
```

`signature` follows `_shared/failure-signature-schema.md`; `class`, `run id`, `log` and `notes` are
the fields `dv-sim-log-first-error` emits, so an escalation and the log triage behind it read side by
side. Leave a field blank rather than filling it plausibly — a blank `blast` is a question, an invented
one is a wrong answer wearing a measurement's clothes.

## Gotchas

- **Severity is about the customer's exposure, not about our embarrassment.** A crash they can see and
  configure around outranks nothing; a quietly wrong result that reaches their silicon outranks almost
  everything. Neither has to do with how hard the fix looks from here.
- **Their configuration is the fact you are least likely to have and the one that decides the case.**
  Our regression exercised the configurations we chose; a parameterised IP or a VIP knob set has a
  space nobody sweeps whole, and escalations cluster exactly where it was not swept.
- **Escalated bugs skew toward the integration surface, not the core datapath.** Clock and reset
  sequencing, parameter combinations we never legalised, back-pressure applied harder than any test
  applies it, and the boundary between our IP and their fabric — open those before the block's core,
  which a thousand nightly seeds have already hammered.
- **Two customers with the same symptom on different releases may be two bugs.** Compare derived
  signatures, not symptoms; "same as the descriptor thing" is a memory, and merging on a memory loses
  the smaller bug for a month.
- **A date is a commitment; a fix is work.** A date given before the debug converged will be missed,
  and a missed date costs more credibility than the original bug did. Commit to the next update
  instead, every time, until the debug has converged.
- **A workaround creates a configuration we now support.** If nothing in the regression covers the
  customer running with that feature disabled, we have promised a mode we do not verify — that belongs
  on the step 7 closure list, not in the next escalation.
- **"Fixed in the next release" is not closure.** Closure is a check that fails on the old design.
  Without it the same bug returns after the next refactor, on a different customer, and this record
  helps nobody because it ends at a patch.
- **A silent waiver beats a loud bug every time.** An excluded check and a passing check produce the
  same output — nothing. When step 7 finds a waiver covering the failing case, the escalation is about
  how that waiver was granted, and the design fix is the smaller half of the work.

## Human verification — what a wrong answer looks like

Before the record goes anywhere, check:

- the severity quotes a **sentence from our scale** and names who set it; a severity with no quoted
  sentence was set by the thread, not by the scale
- the blast radius carries **both denominators**, and says which numbers came from a file that was
  searched and which a person reported
- `reproduced` is one of the four values, and `not-reproduced` appears only where the attempt was made
  **in the customer's configuration**
- every commitment line names a signer, and no line gives a fix date resting on a debug still running
- the owner appears in the area map and was routed from the signature's `where`, not from the
  customer's wording of the symptom
- `gap` names a real plan row, test or coverage point, every closure action has a person against it —
  the agent can add none of them — and the coverage line says what was never established at all

A wrong answer reads as a calm, complete record: one severity, one owner, one fix date, "limited
exposure", and closure recorded as a shipped patch. Nothing in it was searched, the radius was guessed
from the fact that only one customer had written in, and no check exists anywhere that would fail on
the original design.

## Done when

The record can be handed to whoever owns the next escalation, every number in it survives being
checked, and the closure list has a named person against every artifact that must change.
