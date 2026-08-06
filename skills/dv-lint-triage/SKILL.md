---
name: dv-lint-triage
description: Turn a lint report holding hundreds or thousands of violations into a ranked, dispositioned rule-group table — fix, waive or escalate by rule class — and write waiver justifications that survive sign-off review. Use when a lint goal comes back with a violation count nobody can read, when you are told to clean up lint before a sign-off gate, when a waiver was bounced back for more detail, when you cannot tell which violations are real bugs and which are noise from generated code, or when one rule fires four hundred times and you need to know whether that is one problem or four hundred.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Lint Violation Triage and Waiver Justification
  semiskill-function: design-verification
  semiskill-role: static-signoff-engineer
  semiskill-level: fresher
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-02-18
  semiskill-tags: lint, static-signoff, waivers, rule-classes, triage, rtl
---

# Lint Violation Triage and Waiver Justification

A lint goal that returns two thousand violations has not told you about two thousand problems, and
the pull is always to make the number go down rather than to find out what it is made of. The count
is dominated by a few rules firing across generated files and parameterised modules, while the three
violations that will cost a respin sit somewhere in the middle of it. This procedure sorts the report
into rule groups, dispositions each group, and writes the waivers so they survive the review that
rejects most of them.

The output is **a dispositioned rule-group table, plus the waiver text for every group you propose to
waive** — not a violation count, and not a spreadsheet with every row marked reviewed.

**What this cannot do.** It reads a text report and the source files that report names. It cannot
start a lint run, open the tool's own database, regenerate a generated file, or edit RTL. Every step
needing one of those ends in a handoff to a named person and says so.

## When to use something else

- A **clock- or reset-domain-crossing report** is a different goal with a different failure mode —
  most of its violations describe your setup rather than your design. It is `dv-cdc-rdc-triage`, and
  the rule-class table below does not cover crossings. This skill borrows that one's `action`
  vocabulary deliberately, so a static sign-off engineer working both reports keeps one set of words.
- The question is **whether the accumulated waiver file is still doing its job** — entries matching
  nothing, wildcards covering violations nobody reviewed — that is a corpus audit across drops, and
  it is `dv-waiver-corpus-audit`. This skill writes one new waiver at a time and hands the corpus
  question there.
- The lint goal itself **failed to elaborate** — a module it could not find, a file missing from the
  file set: that is a build problem in a static tool's clothing, and `dv-build-filelist-hygiene` owns
  it. A report produced over a design that did not fully elaborate is evidence about nothing.
- A **simulation** failed: `dv-sim-log-first-error`. A night of them:
  `dv-regression-triage-routing`. If X values are appearing in a *running* simulation rather than in
  a static rule, that is `dv-xprop-triage` — the two meet at the `casex` row below and nowhere else.
- You do not yet know where the lint output lands or what the ruleset is called: `dv-repo-orientation`
  maps the machinery first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Lint report location | [[FILL: where our lint goal writes its report, and whether we get a readable text file or only the tool's own database]] | DV infra owner |
| Rule identifier format | [[FILL: how one violation line is printed here — the rule identifier, the severity, the file, the line and the message, in the order our report prints them]] | static sign-off owner |
| Severity labels | [[FILL: the severity labels our report prints, and which of them our team treats as must-fix whatever the tool's default says]] | static sign-off owner |
| Goal and ruleset owner | [[FILL: which lint goal and ruleset this report came from, and who owns that ruleset]] | static sign-off owner |
| Elaboration settings | [[FILL: the top module, parameter values and macro defines this lint goal elaborates with, and whether they differ from the simulation build]] | DV infra owner |
| Generated and third-party paths | [[FILL: which path fragments in our tree hold generated or vendor-supplied source, and who owns each]] | DV infra owner |
| Waiver record | [[FILL: where our lint waivers live, what one entry looks like, and whether an entry is keyed on rule plus file, rule plus module, or rule plus instance]] | static sign-off owner |
| Waiver expiry | [[FILL: how long a waiver stays valid here and what event forces a re-review]] | DV lead |
| Baseline report | [[FILL: which lint report is our signed-off baseline for counting new violations, and whether it is still on disk]] | verification lead |

Two facts this procedure spends are pack-wide and live in `_shared/team-profile.md`; they are not
re-asked here, because two copies drift apart silently. **Sign-off** — who signs off and on what
evidence — is the approver every waiver in step 8 needs. **Area to owner map** is the only thing
step 6 is allowed to route on. Nothing else in the profile is used: this skill never opens a
simulation log, so the profile's markers, run identity and rerun convention have no step to spend
them in.

**Waiver record is not automatically the same file as `dv-cdc-rdc-triage`'s Waiver store or
`dv-waiver-corpus-audit`'s Waiver corpus location.** Some teams keep one waiver file per static goal
and some keep one for all of them. Fill this row with the file the *lint* goal reads, and if it is
the same file those skills name, write that down here as an observation rather than assuming it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented rule identifier makes
step 2 sweep the report for a string it never contains and report no violations, which is the worst
wrong answer available here.

## Retrieval budget — read this before opening anything

A lint report for a mid-size block runs to tens of thousands of lines and repeats the same handful of
messages. Reading it is neither possible nor useful; the counts carry more than the rows.

1. **Grep, Read and Glob work on files on disk.** If the only copy of the report is inside the tool's
   database or on somebody's screen, none of the steps below can touch it — ask the engineer to export
   a text report and to give you the path it was written to. Until that path exists there is nothing
   to triage, and triaging summary numbers read out to you is not triage.
2. **Never open the report with Read first.** Locate with **Grep**, then Read bounded windows — and
   read them in the *source file* the violation names, not in more of the report.
3. The whole allowance is **two Glob calls, thirteen Greps and eight windowed Reads of about sixty
   lines**. Spent as: one Glob for the report and one for the waiver record; two Greps in step 2 (the
   rule-identifier sweep and the severity sweep); one Grep in step 3 for the generated-path fragments;
   one Grep and at most one Read per rule group in step 5, for at most **eight** groups; two Greps in
   step 7 against the waiver record. Steps 4, 6, 8 and 9 open nothing.
4. **A hit count that reached your runtime's display limit is not a count.** Record it as "at least N,
   truncated" and never write a truncated number into the table as a measurement.
5. Here, unlike in a log, a Grep returning thousands of hits is not a broken pattern — it is the
   answer for that rule group. Take the count, apply rule 4, and do not then read the hits.
6. **Stopping rule.** Stop at eight dispositioned rule groups or when the allowance is spent,
   whichever comes first. The rest of the report is undispositioned, which is not the same as clean.
7. **State your own coverage.** Every number carries a denominator: rule groups dispositioned out of
   rule groups seen, violations opened out of violations counted. An unstated shortcut is far worse
   than a stated one.

## Procedure

### 1. Get the report onto disk, and record what produced it

Use **Glob** against the **Lint report location** slot. If that slot resolves only to the tool's own
database, stop and say plainly that nothing below can run until a text export exists, then ask for it.

Then record, beside the report path and before any triage, the **Elaboration settings**: the top
module, the parameter values and the macro defines this goal ran with. This is not bookkeeping. A
lint report is a statement about one elaboration of the design, so a violation that is absent may only
have been parameterised away, and step 4's baseline comparison is arithmetic on unlike things without
it. If the slot is unfilled, write `elaboration settings unknown` and mark every count provisional.

### 2. Build the rule inventory before opening any RTL

Two **Grep** calls against the report, and no Reads:

- One for the pattern in the **Rule identifier format** slot, to get the set of rule identifiers that
  fired and how many times each fired. That set — usually a few dozen entries — is the real size of
  the problem, and it barely moves when the violation total collapses.
- One for the **Severity labels** slot's labels, to attach a severity to each identifier.

Group by rule identifier, exactly as the report spells it. Never group by message text: the same rule
prints a different message per signal, so grouping on the message splits one rule into two hundred
groups you will then triage two hundred times.

**A lint violation does not get a failure signature.** `_shared/failure-signature-schema.md` describes
failures a *run* produced, and its fields assume a simulation happened; a violation found statically
reached none of those moments, so forcing one means inventing values nothing observed. The grouping
key here is the rule identifier plus the scope from step 3. What does carry over is the schema's
discipline — quote verbatim, strip nothing that identifies the construct, compare exactly.

### 3. Split the population by who owns the file

Use **one Grep** for the path fragments in the **Generated and third-party paths** slot against the
report, and split each rule group's violations three ways:

- **ours** — source under active edit by this team;
- **generated** — emitted by a tool from a spec, where the fix is in the generator or the spec and
  never in the file itself;
- **third-party** — vendor or IP-release source we consume and do not control.

Do this before ranking, because it changes the answer for the identical violation. A width truncation
in our RTL is a design question; the same one in a generated register block is a question for whoever
owns the generator, and editing the generated file to silence it is undone by the next build.

Report the three counts. If they total less than the group, the difference is source you could not
attribute — say so rather than folding it into "ours".

### 4. Rank the rule groups — the count is the weakest signal

Order the groups on these keys, highest first:

1. Groups whose class in step 5 is *simulation and synthesis will disagree*, or *driven from more than
   one place or from nowhere*. Those change the netlist relative to what was simulated.
2. Groups the **Severity labels** slot records as must-fix for our team, whatever the tool's own
   column says.
3. Groups absent from the **Baseline report**. If that slot is unfilled or the baseline is no longer
   on disk, drop this key, keep the other three, and mark every group `not compared to baseline`
   rather than ranking as though it had been.
4. Blast radius — the number of distinct **source files** the group touches, not the violation count.

Violation count comes last and means least. One missing `default` in a module instantiated forty
times is forty violations and one edit; forty violations of forty rules in forty files is forty
conversations.

### 5. Classify each ranked group against the rule-class table

For each group, in rank order, for at most eight groups: **one Grep** of the report for that rule
identifier to get its file-and-line list, then at most **one Read** of about sixty lines in the source
file at the *first* instance. The source is what tells you whether the construct is a defect or a
deliberate design; the message never will.

The left column says what the violation is *about*. **No tool prints these words** — they are
paraphrases. Match on meaning, then write your tool's real rule identifier beside the row.

| What the violation is about | Usual action | What decides it |
|---|---|---|
| a net driven from more than one place, or from nowhere at all | fix-rtl | whether the second driver is another procedural block, another instance, or a tie-off someone meant to delete |
| a block meant to be combinational infers a latch — an `if` with no `else`, a `case` with no `default`, a variable not assigned on every path | fix-rtl, unless the latch is intended | whether this block is *supposed* to hold its value; the rule cannot know, and where the code does not say, this is a handoff |
| simulation and synthesis will read the code differently — an incomplete sensitivity list, `full_case` or `parallel_case`, a delay in RTL, state set from an `initial` block | fix-rtl | almost nothing; the rule exists because the two tools disagree, so "it simulates correctly" is not evidence about the netlist |
| a value truncated, extended, or compared across widths or signedness | fix-rtl by making the intent explicit; waivable with a stated bound | whether you can name the invariant keeping the discarded bits constant, and the line that enforces it |
| X-optimism or X-pessimism — `casex` or `casez` matching don't-cares, a comparison against an unknown | fix-rtl | these hide bugs at exactly the moments — reset, power-up — when you need them visible |
| reset or clock structure — a state register with no reset, mixed edge polarity in one block, a reset used as data | needs-a-human | whether it is deliberate architecture; an unreset pipeline register is a normal area choice, and the deliberate ones are precisely the ones needing a written argument |
| dead, unreachable or unused logic — an unread signal, an unreachable state, a condition that is constant | depends on parameterisation | which parameter set this elaboration used; unused here can be load-bearing at another configuration |
| naming, formatting and coding-standard rules | fix-rtl as one mechanical change, or fix-setup | never per-instance; two hundred waivers for a style rule is the wrong shape of answer |
| anything at all inside generated or third-party source | fix-setup, or waive by path | never by editing the file — the next build undoes it |

A group whose source window did not settle the question is `needs-a-human`, and it stays that way in
the table. Guessing here is how a real defect acquires a waiver.

### 6. Choose the action, preferring a setup fix to a waiver

Use the same four words `dv-cdc-rdc-triage` uses, in the same order of preference:

- **`action: fix-setup`** — the tool was told something wrong or not told something true: a rule that
  does not belong in this goal, a wrong parameterisation, generated output that should never have
  been in the run. One change, every violation the mistake produced, and it survives RTL edits. Route
  a ruleset change to the **Goal and ruleset owner**, with the group's count behind it — not to a
  designer, who cannot act on it.
- **`action: fix-rtl`** — the construct is wrong in source this team owns. Name the file and the first
  line; do not propose exact replacement text unless the window showed you the whole construct.
- **`action: waive`** — the construct is correct and there is an argument that makes it correct. Go to
  step 7.
- **`action: needs-a-human`** — the answer is not in the source. Route on the profile's **Area to
  owner map**, keyed on the file or module the violation names, never on the rule identifier.

If a group splits — some instances a deliberate truncation, some a wrong parameter — it is two groups
with two actions. Same rule, two root causes, and the message is identical for both.

### 7. Check the waiver record before writing anything

Use **Glob** for the **Waiver record**, then two **Grep** calls against it: one for the rule
identifier, one for the module or file name from step 5. Then read what the slot says about keying.

- **An entry already covers this scope.** Say which entry, using that record's own key, and stop. Two
  justifications for one thing have to be kept in step with each other, and they will not be.
- **An entry covers the rule more broadly than this violation.** Report it and stop there: judging how
  much a corpus of entries is quietly covering is `dv-waiver-corpus-audit`'s whole procedure, and two
  Greps is not a corpus audit.
- **Nothing matches.** Write the new waiver at the *narrowest* key the record supports — instance if
  it supports instances, module if not, file only as a last resort.

If the waiver record is not a file that can be read, this check did not happen. Say so, and ask its
owner to compare before anything is submitted.

### 8. Draft the waiver against named objects, never against line numbers

A waiver is a claim about the design, not a verdict about the violation. These are the field names
`dv-cdc-rdc-triage` uses, so waivers from the two static goals read side by side.

```
waives    : the rule identifier, verbatim as the report spells it
objects   : the module, instance or signal names this covers, by full name
scope     : the narrowest key the Waiver record slot supports, and which level was analysed
because   : the argument, in sentences a reviewer can disagree with
backed by : the parameter, constraint, assertion or specification clause keeping it true
holds if  : the conditions under which it stops being true
expires   : the date or event from the Waiver expiry slot, and what must be rechecked then
signed    : who accepted it, per the profile's Sign-off row
```

Illustration only — these names are placeholders, not any real block:

```
waives    : the width-truncation rule, as our report identifies it
objects   : fifo_ctrl, signal wr_ptr and the port it drives
because   : wr_ptr is 12 bits and the port is 8, and wr_ptr is bounded by MAX_BURST, so the
            discarded bits are always zero
backed by : rtl/fifo_ctrl.sv line 84 declares the bound; line 141 makes the assignment
holds if  : MAX_BURST stays at or below 255 and the bound at line 84 survives
```

Four justifications that get bounced, and why:

- *"Reviewed, not an issue"* — a signature rather than an argument. Nothing in it can be re-checked.
- *"False positive"* — a claim about the tool, not the design. If the rule really is wrong for this
  construct, that is `action: fix-setup` routed in step 6, not a waiver.
- *"Waived per the designer"* — an authority, not a reason. Record who agreed **and** what they said.
- *"Same as the entry above"* — the thing above moves when the file is edited.

### 9. Record the result, with coverage

One block per dispositioned group, in rank order. Leave a field empty rather than filling it
plausibly.

```
rule      : the rule identifier, verbatim as the report spells it
scope     : the file, module or instance this record applies to
count     : violations in this group, split ours / generated / third-party
sample    : the one violation actually opened, with its file and line
action    : fix-setup | fix-rtl | waive | needs-a-human
because   : the rule-class row from step 5, named
evidence  : file and line for every claim above; the word person for anything that came from one
owner     : who fixes it, or who approves the waiver
expires   : the date or event from the Waiver expiry slot, on a waive only
notes     : anything the next person would otherwise have to rediscover
```

Then one line for the whole pass, and it is not optional:

```
coverage  : dispositioned n of m rule groups; opened v of V violations; elaboration settings
            recorded or unknown; compared to baseline or not compared
```

A table covering six rule groups of forty-one that says so is useful. The same table without that
line reads as a finished sign-off and is not one.

## Gotchas

- **The violation count is not the problem count.** One incomplete `case` in a module instantiated
  forty times is forty violations and one edit. Report both numbers, in that order, or somebody will
  plan a week around the larger one.
- **`full_case` and `parallel_case` silence the rule by creating the bug it warned about.** They
  assert to synthesis that a case is complete or its branches mutually exclusive; simulation ignores
  the claim entirely. Where the claim is wrong, the netlist and the RTL diverge at exactly the branch
  that falls through — and the report is now clean. A rule silenced by a pragma is not a fixed rule.
- **A latch is not always a defect, and the rule cannot tell.** The enable latch inside a clock-gating
  cell, and a deliberate level-sensitive hold, are correct code carrying a violation; the same
  violation in a block meant to be combinational is a missing `else`. The difference is intent, intent
  lives in a person, and where the code does not say, it is a handoff and not a judgement call.
- **A width waiver written against a literal rots the moment a parameter moves.** "The top four bits
  are always zero because the counter only reaches two hundred" is true until someone raises the
  maximum, and nothing re-checks it. Waive on the invariant, cite the line enforcing it, and say what
  breaks it.
- **Lint elaborates with its own top module, parameters and defines.** Two reports from two
  parameterisations describe two different designs, so a violation that disappeared may only have been
  parameterised away. Without the elaboration settings recorded beside it, a baseline delta is a
  number with no meaning.
- **Unused and unreachable are parameterisation-dependent.** A signal read only inside a `generate`
  branch this configuration does not take is genuinely unused here and load-bearing at the next
  customer's settings. The waiver has to name the settings it was true at.
- **Severity is a vendor default, not your team's policy.** The rule your methodology cares most about
  routinely ships at the tool's lowest severity, and one you will never act on ships as an error. Rank
  on what the team promoted, which is what the Severity labels slot exists for.
- **A rule-wide waiver is invisible forever.** Waiving on the rule identifier alone also removes every
  instance added next month, in files nobody has opened yet. That is not a clean goal, it is a
  disabled one, and the count will not tell you which you have.
- **Keep generated files in the run and out of the ranked table.** Excluding them from the report is
  reasonable housekeeping; excluding them from the run means the day the generator starts emitting a
  new construct is the day nobody finds out.
- **Two violations of one rule can have two root causes.** A deliberate truncation and a wrong
  parameter print an identical message. That is the whole reason step 5 opens the source instead of
  reading the message a second time.

## Human verification — what a wrong answer looks like

Before anything is submitted, check:

- every record names a rule identifier **and** a scope. "All width warnings" is not a scope.
- nothing in the *simulation and synthesis disagree* class, and no multiply-driven or undriven net,
  carries a waiver. Those rows are fixes, and a waiver on one of them is the expensive mistake here.
- every waiver has a `holds if` and a `backed by` citing a file and line. A waiver whose argument
  rests on a number nobody can point at is a memory.
- no violation was silenced by editing source — a pragma added, a signal artificially read, a
  generated file hand-edited. The count moved and the design did not.
- every count carries a denominator, and no number came from a truncated Grep result.
- the elaboration settings are recorded, and the baseline is either genuinely compared or marked not
  compared — never left to read as a comparison that happened.
- every `action: needs-a-human` was routed on the file or module through the area-to-owner map, and
  every `action: fix-setup` that is a ruleset change went to the ruleset owner rather than a designer.
- the coverage line is present, and the groups nobody reached appear as a count rather than absent.

A wrong answer is a spreadsheet of fourteen hundred rows each marked "reviewed — OK", produced without
a single source file being opened. Its close relative is a report that proudly takes the count to
zero, where the zero was bought with three rule-wide waivers and a pragma.

## Done when

Every rule group you reached has an action, an owner and evidence; every waiver says what would make
it false; and the groups you did not reach are counted in the open rather than missing.
