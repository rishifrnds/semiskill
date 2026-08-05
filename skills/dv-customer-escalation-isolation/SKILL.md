---
name: dv-customer-escalation-isolation
description: Isolate a customer-reported failure into one of five fault domains — their configuration, their integration, their DUT, our VIP, or our tool — before the case is routed to an R&D queue. Use when a customer says our VIP is broken, when an escalation arrives as a log plus a configuration dump, when a case has bounced twice between support and R&D, when a customer reports that the previous release worked, or when you must decide whether to open an internal bug or send the case back with a finding.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Customer Escalation Reproduction and Fault Isolation
  semiskill-function: design-verification
  semiskill-role: applications-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-09-17
  semiskill-tags: escalation, customer, vip, support, isolation, reproduction, versions
---

# Customer Escalation Reproduction and Fault Isolation

An escalation does not arrive as a failure. It arrives as a **claim** — usually that our VIP is broken —
attached to whatever the customer happened to have open at the time. The expensive mistake is agreeing
or disagreeing with that claim before anyone has established which of five things actually broke: their
configuration, their integration, their DUT, our VIP, or our tool. Get it wrong and the case sits in the
wrong R&D queue for a week, or a real bug goes back marked "works for us".

The output is **one fault domain, the evidence line behind it, and the single next artifact** — either an
internal bug with somewhere to go, or one specific request back to the customer.

## When to use something else

- One of our own failing logs, first error and repro block — `dv-sim-log-first-error`. Come back here once
  you know *what* failed and need to know *whose* it is. A whole night of our own regression is red
  instead — `dv-regression-triage-routing`.
- The domain is already isolated to our VIP and R&D wants something smaller — `dv-minimal-reproducer`,
  preserving the signature this skill records.
- Two simulators give different answers on the same source and the real question is which answer the
  language standard makes correct — `dv-cross-tool-mismatch-adjudication`. Step 4's simulator row hands
  that case over rather than forcing a third-party tool defect into one of the five domains.
- Their build never compiled or elaborated against our release — `dv-build-filelist-hygiene`; step 4 routes
  that row straight out. A register address, access-policy or reset-value mismatch — `dv-ral-bringup`.
- You cannot find our own VIP source, filelists or benches — `dv-repo-orientation` is the map.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Escalation intake | [[FILL: where a customer's attached artifacts are unpacked on our side, and what our case record calls each attachment]] | support lead |
| Release manifest | [[FILL: the file recording which VIP, model and tool versions shipped in a given release, and where it lands on disk]] | release owner |
| Supported configurations | [[FILL: the file recording which configurations of this VIP we test and ship, and where unsupported combinations are recorded]] | VIP owner |
| VIP identity markers | [[FILL: the strings our VIP prints to identify itself as the author of a message]] | VIP owner |
| VIP knob surface | [[FILL: where our VIP's configuration object and its knobs are declared in our tree, and which knobs a customer is expected to set]] | VIP owner |
| Protocol reference | [[FILL: which protocol specification revision this VIP claims compliance with, how we cite a clause, and whether that document is a file Read can open]] | VIP owner |
| Reproduction bench | [[FILL: which of our own testbenches can drive a customer configuration, and what we cannot reproduce internally at all]] | VIP owner |
| Escalation boundary | [[FILL: what we are allowed to ask a customer for, and what must not leave their site]] | support lead |

Five pack-wide facts live once in `_shared/team-profile.md` and are read from there; there is deliberately
no second copy of them above. **Known-issue list** is spent in step 7, **Fatal markers** in step 8 signing
the log from *our own* reproduction attempt, **Simulator** in the step 4 row that turns on whose simulator
produced the log, and **Area to owner map** and **Run identity** in step 9's `owner` and `run id` lines.

Two profile facts are deliberately **not** used, for the same reason: they describe our flow on our disks.
**Log location** is replaced by the Escalation intake slot, because a customer's log lands wherever support
unpacked it. **Pass marker** has no customer-side counterpart at all — their flow prints its own end-of-run
line and this pack cannot know it, so never Grep a customer log for ours and read the absence as a failure.
**VIP identity markers is not Fatal markers renamed**, either: Fatal markers say a run failed, identity
markers say *who printed a line*, and a line can carry one and be routine information. Step 3 needs the
second question, so record both separately.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented manifest path or knob name
produces a confident domain, and a confident wrong domain is the thing the customer remembers.

## Retrieval budget — read this before opening anything

A customer bundle is the worst input in this pack: a huge log, a configuration dump, files we did not write,
and usually several artifacts nobody can open at all.

1. **Grep, Read and Glob work on files on disk.** An escalation arrives as ticket text and mail attachments;
   get the unpacked path under the Escalation intake slot before anything is Grepped. If the only copy is
   text in the ticket you may reason over it by eye — but say so, and mark every field resting on it
   provisional.
2. Some attachments cannot be opened at any budget: waveform databases, spreadsheets, screenshots, encrypted
   archives. Record them as **received but unreadable** rather than skipping them silently — a waveform
   screenshot is a handoff to a person, not evidence.
3. **Two Glob calls**: the intake directory (step 1) and our own tree for the VIP configuration class
   (step 5). Never open a customer log with **Read** first.
4. **Their log is the primary artifact — three Greps and one windowed Read of about 80 lines**: the version
   banner (step 2), the VIP identity markers and the earliest marked line's number (step 3), then the window
   before it.
5. **Three further customer artifacts at most, each one Grep and one windowed Read of about 40 lines**:
   their configuration dump and their integration file (step 5), plus one spare — normally the log from our
   own reproduction attempt (step 8).
6. **Our own files**: one **Grep** each of the release manifest (step 2), the Supported configurations record
   (step 4) and our tree for the knob names (step 5); one **Grep** *and* one 40-line **Read** of the
   protocol reference, *only if it is a file Read can open* (step 6) — a clause is quoted to a customer,
   so it is read in its own window and never lifted from a single Grep hit line; two Greps of the
   Known-issue list *only if it resolved to a file on disk* (step 7).
   The whole ledger is 2 Globs, 12 Greps and 5 Reads — about 19 calls, four of them conditional, and
   nothing outside it. Narrow any **Grep** returning more than about 200 hits before reading anything.
7. **Stopping rule and coverage.** If their log and two further artifacts have not settled the domain, stop,
   write `domain: unknown`, and name the one artifact still needed and who has it — past that the procedure
   invents a domain, and a case in the wrong queue is not corrected for days. Then state what was actually
   covered: artifacts opened, artifacts unreadable, how much of the log one window reached. An unstated
   shortcut is far worse than a stated one.

## Procedure

### 1. Inventory what actually arrived, before reading any of it

One **Glob** of the Escalation intake path, then two lists side by side: what the ticket says was attached,
and what is actually on disk. They differ more often than not, and the difference is your first message back
to the customer — sent now, not after two days of analysis.

Three artifacts decide this procedure: **their log, the configuration they actually ran, and anything naming
a version**. If one is missing, ask for that one by name — but read the **Escalation boundary** slot first.
Their RTL, their test source and sometimes the log itself may be blocked by contract, and an unaskable
request costs the same two days as no request at all. From here on keep ticket text and artifacts apart: the
ticket is a claim, the files are evidence.

### 2. Pin three versions before analysing anything

Version skew is the largest single category of escalation and the cheapest to settle. There are three answers
to "which version", and they disagree: what the customer **says** they run, taken from the ticket and
therefore a claim; what their **log** printed, one **Grep** of it for our VIP's banner or version string; and
what our **release manifest** records for that release, one **Grep** of that slot's file.

Record all three verbatim with their sources. If the log carries no banner the version is unknown — write
`?`. Do not assume the latest release, and do not assume the manifest describes what is in their tree: a
locally patched or hand-copied VIP is common, and this comparison is exactly what finds it.

### 3. Attribute every message to its author before reading it as evidence

A customer's log holds three populations: messages our VIP printed, messages their testbench printed, and
messages their simulator printed. The escalation usually quotes one line, and which population it came from
decides ownership before any analysis happens. One **Grep** for the **VIP identity markers** slot's strings,
a second to fix the line number of the earliest hit that is a complaint rather than an information message,
then the log's single **Read** window of about 80 lines starting roughly 60 lines before it.

Two rules get reversed constantly. A message *our VIP* printed is not automatically our bug — it is very
often our checker correctly reporting their violation. A message *their testbench* printed is never evidence
about our VIP; it is evidence about their expectation.

### 4. Classify into exactly one of the five domains

`Evidence` says what each row can be settled from: `log` is their log, `config` their configuration dump,
`source` our own tree, `manifest` the release manifest from step 2. `+ person` means this procedure can
narrow the row but someone else must finish it.

| Symptom | Evidence | Check first | Usual domain |
|---|---|---|---|
| Our VIP reports a protocol violation on a signal their DUT drives | log + spec | the clause our message cites, against what their log shows on that signal | customer-dut, until the clause says otherwise |
| Our VIP reports a violation on a signal our own VIP drives | log + source | which knob selects that behaviour, and what they set it to | customer-config if the knob explains it, our-vip if it does not |
| Our VIP never issues a transaction and prints nothing | log + config | whether the agent is active or passive, and whether a sequence was ever started on it | customer-integration |
| Checkers never fire, coverage is empty, and the test passes | config + source | whether the monitor's virtual interface was ever assigned | customer-integration |
| Works at their block level, fails at their subsystem level | config | clock, reset and interface connection at the level that fails | customer-integration |
| The previous release worked and this one does not | manifest | whether the two runs differ *only* in our release — see the Gotchas | our-vip until the difference says otherwise |
| Fails on their simulator, passes on the one the profile names as ours | log + manifest | simulator and version on both sides, then the compile switches and the timescale | our-tool only if the failing simulator is ours; otherwise see below the table |
| Their build fails against our release before anything runs | log | the first diagnostic, and whether the file named is one we ship | route to `dv-build-filelist-hygiene` |
| Their scoreboard mismatches and our VIP reports nothing | log + config | whether our checks were enabled at all in that configuration | customer-config, until proven otherwise |
| The configuration is a combination we do not list as supported | source | the Supported configurations record, one **Grep** | customer-config, and our own documentation debt |
| Intermittent — one seed in many | log | whether the seed and the version are pinned in what they sent | unknown until reproduced |
| They cannot share the failing testbench at all | + person | what the escalation boundary permits them to send | isolate from the log alone, domain provisional |

One row cannot be closed inside the five domains. When the simulator that fails is *not* the one the
profile names as ours, a defect in it is not `our-tool` — we do not ship that tool — and it is none of the
other four either. Rule out the three portable causes first, because each is commoner than a simulator bug:
our own source depending on behaviour only one simulator provides (`our-vip`), a race or an X-propagation
difference in their DUT (`customer-dut`), and two runs whose compile switches or timescale differ
(`customer-integration`). Only if all three are ruled out on evidence, write `domain: unknown`, say in
`notes` that no domain in this scheme owns a third-party tool defect, and route the comparison to
`dv-cross-tool-mismatch-adjudication`, which rules on the language standard rather than on ownership.
Never write `our-tool` for a tool we do not ship: that queue is ours, and the case will sit in it.

Name one row. "Could be configuration or integration" means this step is unfinished — go to step 5 first.

### 5. Read the configuration they ran, not the one they describe

**Glob** our tree for the VIP configuration class named in the **VIP knob surface** slot, then one **Grep**
there for the knobs the step 4 row turns on — declared names, defaults and legal values. Then spend two
customer artifacts: one **Grep** and one 40-line **Read** of their configuration dump for those same names,
and the same again on their integration file, where our VIP is instantiated, configured and connected.

The commonest escalation of all is a default nobody set; the second commonest is a knob set at the wrong
moment (see the Gotchas). Quote each knob with a file and a line on both sides — ours for what it means,
theirs for what it was.

### 6. Separate "our VIP is wrong" from "our VIP is right and says so"

This step decides whether an internal bug is opened, so be slowest here. Take the clause our message cites
and check it against the **Protocol reference** slot — the exact revision this VIP claims compliance with,
cited the way that slot says we cite. One **Grep** of that document for the clause number to fix its line,
then one 40-line **Read** window starting a little above it — quote the clause from that window and never
from the Grep hit line, which shows one line of what is usually a multi-sentence obligation whose conditions
and exceptions sit in the sentences around it. Both calls only if the document is a file **Read** can open.
If it is a licensed PDF or a paper copy, say so: every clause statement then becomes a handoff to the VIP
owner, is attributed to whoever supplied it, and the finding is marked provisional. Never paraphrase a
clause from memory — a misquoted clause in a customer-facing report is the most expensive error available in
this whole procedure.

Three ways our checker fires without our VIP being wrong: their DUT genuinely violates the clause; the clause
is conditional on something their configuration disables; the clause changed between the revision we coded
against and the one they read. Three ways it is wrong: we coded against a different revision, the check is
stricter than the clause, or the check is right but names the wrong signal.

When the evidence needs another run, hand it off rather than assuming one: **ask the customer to repeat the
run with our VIP's own reporting raised on that checker, and ask our support engineer to unpack the resulting
log under the intake location and give you the path.** The agent cannot start a simulation and must not
invent what one would have printed.

### 7. Match against the known-issue list, not memory

What is possible depends on what the profile's Known-issue list resolved to. **A file on disk**: two
**Greps**, one for the signature's `where` and one for the distinctive fragment of `what`; compare exactly,
and a match attaches this case to that entry, named with the key that list itself uses. **A tracker or page
that is not a file on disk**: Read and Grep cannot reach it, so put the signature in the record and ask
whoever can query the list; until then the case is `list-not-readable`. **Unfilled**: say the check did not
happen, and never tell a customer their issue is new.

The same VIP bug arrives from three customers inside a month under three different descriptions, which is why
this step is worth more here than anywhere else in the pack.

### 8. Reproduce on our own bench, or say plainly that you did not

The **Reproduction bench** slot records two things, and the second matters more: which bench can drive their
configuration, and what we cannot reproduce internally at all — their DUT, their simulator version, their
scale. The agent cannot build or run anything: **ask the engineer to bring the customer's configuration up on
the bench that slot names and to give you the path of the resulting log.** Then, *if a path comes back*,
spend the spare artifact — one **Grep** of that log for the profile's **Fatal markers**, one 40-line
**Read**. Our flow printed it, so the profile's markers apply here, which is exactly why they did not apply
in step 3.

Record one of the four `bench` outcomes and nothing vaguer, and put the log you actually read on the
`bench log` line beside it:

- The handoff came back with a path and our bench showed the failure — `reproduced`, with that path and the
  line range of the window on `bench log`. A `reproduced` with no line to point at is an opinion.
- The handoff came back with a path and the log carries none of the Fatal markers — `not-reproduced`, again
  with the path. That is a fact about our bench, never a verdict about their report.
- The engineer answers that this bench structurally cannot drive their case — their DUT, their simulator
  version, their scale — `not-reproducible-here`, and `bench log` stays blank. It is not a softer
  `not-reproduced`: it is a finding about our own test surface and belongs in the record.
- The request is still outstanding when the record has to go out — the bench queue, a licence, or the person
  who owns it is away — `not-attempted`, `bench log` blank, and `ask` naming the run and whose it is.
  Records leave on day one and benches free up on day five, so this is the ordinary state of a first record
  rather than a failure of it. Never write `not-reproduced` for a run nobody has made yet: once written, no
  later reader can tell the two apart, and that is the line that closes a real bug.

### 9. Write the escalation record

Where their log was readable, derive a failure signature following `_shared/failure-signature-schema.md` —
same field order, same normalisation rules — so this case matches our own triage tables. `signature`,
`cause`, `first err`, `phase`, `class`, `run id`, `log` and `notes` are the field names
`dv-sim-log-first-error` emits, so a case escalated inward keeps its vocabulary; the rest are local.

```
escalation : <our case identifier, and the customer-facing one if they differ>
domain     : customer-config | customer-integration | customer-dut | our-vip | our-tool | unknown
class      : design | infrastructure | unknown
signature  : <phase>|<kind>|<where>|<what>, per the shared schema, or ? if no log was readable
first err  : <verbatim first complaint carrying one of our VIP identity markers, with line number>
cause      : <verbatim line that explains it, with line number>
phase      : compile | elab | run | finalise | post
versions   : <what they say; what their log printed; what our manifest records — each with its source>
config     : <the knobs that decided the classification, with the file and line each was read from>
clause     : <revision and clause from the protocol reference, or the person who supplied it>
bench      : reproduced | not-reproduced | not-attempted | not-reproducible-here
bench log  : <path of the log from our own reproduction attempt and the line range read, or blank
              where there is no such log — see the step 8 outcomes>
known      : known-issue <key> | not-matched | list-not-readable
owner      : <queue or person from the profile's area-to-owner map, or blank plus candidates>
run id     : <theirs for their log, ours for the reproduction attempt>
log        : <path under the intake location, and the line range worth reading — their artifacts only>
ask        : <the one artifact or answer still needed, and from whom>
coverage   : <artifacts opened; artifacts received but unreadable; windows spent of the budget>
notes      : <anything the next person would otherwise rediscover, including anything supplied by a
              person rather than read from a file>
```

Two names are chosen rather than borrowed. The reproduction outcome is `bench`, not `repro`, because
`dv-escape-analysis` asks a different question about a different object under that name — whether a
post-silicon escape reproduces in simulation at all, not whether one customer's configuration comes up on
one of our benches — and two blocks read side by side must not wear one name for two questions. The four
values are deliberately its four: identical values under two names is the safe direction, one name over two
questions is not. `log` is theirs and `bench log` is ours, never one field carrying both. The
citation line is `clause`, the same name and content `dv-spec-feature-extract` and
`dv-spec-interpretation-ledger` use, so a clause argued with a customer matches one already logged
internally; that skill's `spec` field is a *judgement* about the specification, not a citation, so the two
must not be merged.

Leave a field empty rather than filling it plausibly. A blank `owner` is one message; a wrong one is a week.
`class` is `infrastructure` when the case turns out to be their farm, licence or disk rather than
verification content, and `unknown` is allowed when nothing on disk settles it. `phase` is a phase of
*their* run, read from where in their log the first complaint sits: an end-of-test check that only fires
after the last transaction — a scoreboard drain, an unmatched-transaction count, an objection nobody dropped
— is `finalise`, not `run`, and filing it as `run` routes the case to whoever owns stimulus instead of
whoever owns the end-of-test check.

## Gotchas

- **The version they name and the version their log printed disagree constantly.** They read the release page
  rather than their own tree, or they run a locally patched copy someone made during a previous escalation.
  That is why step 2 collects three answers instead of one.
- **"The previous release worked" is a claim about two runs, not about a diff.** Customers upgrade the VIP,
  the simulator and their own testbench inside one window. Confirm the two runs differ only in our release
  before anyone opens a release note, or you will find a change that explains nothing.
- **A passive agent drives nothing and fails nothing, exactly as designed.** "Your VIP does not transmit" is
  most often an agent left passive, or an active agent whose sequencer never had a sequence started on it.
  Both produce a clean, quiet, entirely uninformative log.
- **Configuration written after the phase that reads it is ignored in silence.** A component reads its
  configuration during its own build phase, so a value placed in the configuration database after that
  component is built — a parent doing it in connect, a test doing it in the run phase — arrives too late,
  prints nothing, and the component simply uses its default.
- **An unassigned virtual interface fails at first use, not at connect.** The null handle surfaces deep in
  the run, far from the integration mistake that caused it, which is why it reads as a VIP bug and gets
  escalated as one.
- **Our checker firing is a claim about a clause, not about a bug.** Route it by clause number and revision,
  never by message text, and check whether their configuration disables the condition the clause is written
  under before deciding whose side is wrong.
- **A waveform screenshot is not evidence you can search**, and neither is a spreadsheet of transactions nor
  an encrypted archive. Record them as received but unreadable and turn them into one question for a person;
  pretending to have read them is how a fabricated detail enters a customer report.
- **Our bench differs from theirs in at least three ways** — a configuration we support, a simulator we
  chose, and a reference DUT rather than their design — so a clean run here narrows nothing on its own.
- **Asking for something they cannot legally send costs the same as asking for nothing.** Check the
  escalation boundary and ask for the permitted artifact that answers the same question: a configuration dump
  instead of a testbench, a log tail instead of a log.

## Human verification — what a wrong answer looks like

Before the record leaves your hands, check:

- the domain names **one** of the five, or `domain: unknown` with either the missing artifact named or, in
  step 4's third-party-simulator case, the reason none of the five owns the finding. A hedge between two
  domains means step 4 was never finished, and `our-tool` on a tool we do not ship is not a domain at all.
- all three entries in `versions` are present and separately sourced — the claim, the log line, the manifest
  entry — and none was assumed.
- every knob in `config` carries a file and a line on both sides: what it means in our tree, what it was set
  to in theirs.
- any protocol statement cites a revision and a clause from the **Protocol reference** slot, or is attributed
  to whoever supplied it and marked provisional.
- `bench` says what actually happened on our own bench, and `bench log` carries the path and line range that
  shows it — blank only on `not-attempted` and `not-reproducible-here`, where there is no such log. A
  request still sitting in the bench queue is written `not-attempted`, never `not-reproduced`, and a
  `not-reproduced` has not been written up as a customer-side domain.
- `known` reflects a real comparison against the list, or says the list could not be reached, and `coverage`
  names the artifacts that arrived unreadable — they are part of the case, not an omission.
- nothing in the record came from the ticket text alone without being marked as such.

A wrong answer routes a case to the VIP R&D queue on the strength of the customer's own sentence, with no
version triple and no clause number behind it. The second-most common wrong answer closes the case as
`domain: customer-config` because our bench did not reproduce it — which is a fact about our bench.

## Done when

One domain is named, every line behind it points at a file and a line or at a person, and the case carries
either an owner or a single question with somebody's name on it.
