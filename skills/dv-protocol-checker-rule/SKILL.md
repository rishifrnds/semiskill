---
name: dv-protocol-checker-rule
description: Turn one normative sentence from a protocol specification into a numbered passive checker rule with a stable ID, a spec back-reference, a message, and a negative test that proves the rule actually fires. Use when you are adding a check to a VIP someone else wrote, when a reviewer asks which clause a checker enforces, when a rule needs a number and you do not know which numbers are already taken, when a checker has never fired in a year of regressions, or when a designer says the protocol allows what your checker just flagged.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Passive Protocol Checker Rules with Stable Rule IDs
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-14
  semiskill-tags: vip, protocol, checker, assertions, sva, rule-id, negative-test
---

# Passive Protocol Checker Rules with Stable Rule IDs

A checker rule with no number cannot be waived, a rule with no spec back-reference cannot be defended
the first time a designer says the protocol allows it, and a rule with no negative test cannot be told
apart from a rule that never fires. That last one is the expensive failure: a check that has sat in the
VIP for a year without firing looks exactly like a clean protocol, and is usually an antecedent that
was never reachable. This produces four things for **one** normative sentence — a rule ID, a rule
record, a message, and a negative test the engineer can run — plus one line on what was confirmed.

## When to use something else

This skill authors and reviews a rule. It reads source files and saved logs; it cannot start a
simulation, open a waveform, or read a licensed specification that exists only as a PDF on someone's
desk. Every step needing one of those ends in a named handoff and says so.

- A checker has already fired and you are working out what broke — `dv-sim-log-first-error`.
- A whole night of failures needs sorting and routing first — `dv-regression-triage-routing`.
- The failure is a register read-back mismatch, not a protocol violation — `dv-ral-bringup`.
- You are building the agent and its end-to-end scoreboard rather than one rule inside a VIP that
  already exists — `dv-uvm-agent-checker`. That compares data across two points; rules here constrain
  one interface against its own specification.
- The injection is a fault in a protected structure — ECC, parity, CRC, retry — rather than an illegal
  transfer, and you need the whole matrix — `dv-error-injection-ras`.
- Your new checker file does not compile — `dv-build-filelist-hygiene`. You cannot yet find where this
  VIP lives in the tree — `dv-repo-orientation` first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Rule ID scheme | [[FILL: the shape of our checker rule identifiers, which prefix this VIP owns, and whether numbers are allocated per interface or per protocol layer]] | VIP owner |
| Checker source | [[FILL: where this VIP's passive checker files live, what they are named, and whether checks are written as concurrent assertions or as procedural code]] | VIP owner |
| Rule registry | [[FILL: where allocated rule IDs, their text and their retirement status are recorded, and whether that is a file which can be read or a page a person must open]] | VIP owner |
| Spec reference | [[FILL: the exact document name and revision this VIP checks against, and the citation form our reviews expect for a clause]] | protocol owner |
| Message convention | [[FILL: the field order our checker messages print in, and which of those fields our triage tooling parses]] | DV lead |
| Severity levels | [[FILL: which severities our checkers may emit, and what each one does to a regression result]] | DV lead |
| Per-rule control | [[FILL: how one rule is enabled, disabled or waived on its own ID, and where a waived instance is recorded]] | VIP owner |
| Negative-test location | [[FILL: where this VIP's error-injection tests live, and how each one is tied back to the rule it violates]] | VIP owner |
| Sampling and reset | [[FILL: which clock our checkers sample on for this interface, and which reset they are disabled under]] | block owner |

Two pack-wide facts are read from `_shared/team-profile.md` rather than repeated above, and both are
spent in step 7: **Log location**, for where the negative-test log lands, and **Pass marker**, for
telling a run that finished from one that died on the way. **Message convention is not the profile's
Fatal markers** and must not be filled in from it: Fatal markers is what our flow prints when a run
fails, a property of the flow, while the message convention here is the field order inside this VIP's
own messages — and a rule reporting at a non-failing severity prints one without printing a fatal
marker at all. If the two genuinely coincide for our house macros, write that down explicitly.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented ID prefix or message
shape produces a rule that looks house-standard, passes review, and is invisible to the triage tooling.

## Retrieval budget — read this before opening anything

A VIP's checker source and its error-injection suite are large, and the specification usually is not
readable at all. Work in this order and stop as soon as the rule record is filled:

1. **Grep and Read work on files on disk.** A clause quoted in a chat message, a screenshot or a PDF is
   not searchable. You may transcribe one sentence a person gives you, but record who gave it to you
   and mark anything resting on it provisional. Never reconstruct spec wording from memory.
2. **Never open a checker file with Read first.** **Glob** to find it, **Grep** for a line number, then
   **Read** a bounded window.
3. The whole budget is three **Glob** calls — the spec in our tree (step 1), the checker source
   (step 3), the negative-test area (step 6); six **Grep** calls — the interface clock and reset by
   name (step 2), the ID prefix across the checker source, the same prefix across the rule registry
   when that registry is a readable file, one distinctive noun from the statement to hunt duplicates
   (those three in step 3), an existing rule ID in the negative-test area (step 6), and the new rule ID
   alternated with the pass marker in the negative-test log (step 7); and three **Read** windows —
   about 40 lines at the clock and reset declaration (step 2), about 60 at the nearest sibling rule
   (step 4), about 60 at the first log hit (step 7). Nothing else is opened.
4. If a **Grep** for the ID prefix returns more than about 200 hits, you are matching message text as
   well as declarations — anchor it to the declaration form the sibling rule in step 4 uses.
5. **Stopping rule.** If those three windows have not settled the shape of a house rule, stop and ask
   the VIP owner. A checker idiom invented to fill the gap compiles, reviews well, and checks nothing.
6. State what you covered — which files were searched, which facts came from a person, and whether the
   fire in step 7 was seen in a log or is still pending a run.

## Procedure

### 1. Get the normative sentence verbatim, with its clause and its strength

**Glob** the path the Spec reference slot names, in case the document is readable text in our tree.
Usually it is not: ask the protocol owner, transcribe the sentence **verbatim** into the rule record,
and put document, revision and clause beside it. A paraphrase is how a rule ends up stronger than the
specification it claims to enforce, and notes, figures and examples are informative unless the document
says otherwise — a rule sourced from a waveform picture cites nothing.

Classify the strength from the sentence's own verb, not from how important it feels. **Shall / shall
not** is a requirement and becomes a firing rule. **Should / should not** is a recommendation — a rule
only at an advisory severity, because at a failing severity it turns a legal design into a regression
failure. **May / optional / is permitted** is permission, never a rule: if it matters it is a coverage
point, and belongs to whoever owns the coverage plan. **Reserved / undefined / implementation defined**
is no rule at all — the specification is declining to constrain it, so a checker here reports our
assumptions rather than the protocol.

**One sentence is often two rules.** Split on every "and", "or" and "until" carrying its own
obligation. A merged rule cannot say which half broke, and a waiver for one half silently waives both.

### 2. Reduce the statement to antecedent, obligation, window and qualifiers

Write four things down in plain words before touching code. The **antecedent** is the observable
condition that makes the obligation apply, built only from signals on this interface. The
**obligation** is what must then hold, stated so you can say what would be seen if it did not. The
**window** is same cycle, next cycle, within a bounded number of cycles, or until a named condition —
and where the sentence says "eventually" with no bound, see the Gotchas: an unbounded obligation does
not fail in simulation, and the bound you pick is a testbench policy, not a spec fact. The
**qualifiers** are when the rule does not apply — during reset, before the interface is enabled, in a
mode this instance is not configured for.

Fill the qualifiers from the **Sampling and reset** slot. **Grep** for the clock and reset names it
gives, then **Read** about 40 lines at the interface declaration to confirm polarity and active edge.
Guessing an active-low reset is active-high yields a rule disabled for the whole test, which passes
perfectly.

### 3. Allocate the rule ID and prove it is free

**Glob** the Checker source path, then spend two **Grep** calls on the prefix from the **Rule ID
scheme** slot — one across the checker source, one across the **Rule registry** when that registry is a
file that can be read. If the registry is a page only a person can open, say so and ask the VIP owner
to allocate the number. Do not take the highest number in the source as the next free one: retired and
reserved IDs do not appear there. Then one **Grep** for the most distinctive noun in the sentence, to
find a rule that already says this — a duplicate rule is worse than a missing one, because it doubles
every failure count, splits the waiver list across two IDs, and the second is the one nobody maintains.

Three allocation rules, and they are the whole reason IDs exist. **Never renumber**: IDs outlive the
code in waiver files, triage tables and customer bug reports. **Never reuse a retired ID**, because an
old waiver then silently reapplies to a different rule and nothing reports it. **Allocate in the
registry first, then write the code** — two people editing one file both pick the next free number and
both are right.

### 4. Draft the check as an observer, not a participant

**Read** about 60 lines at the nearest sibling rule found in step 3 and copy its shape — that file, not
this skill, is the authority on our house form. Whatever the form, four parts must be present, and the
standard-language shape shows them clearly:

```
   property p_<id>;
     @(<sampling event>) disable iff (<reset or enable qualifier>)
       <antecedent> |-> <obligation, inside the window>;
   endproperty
   a_<id> : assert property (p_<id>) else <the message drafted in step 5>;
   c_<id> : cover  property (<the antecedent on its own>);
```

Passive constrains more than it sounds like. The check reads interface signals only: a rule reaching
into design hierarchy stops working the moment the design is a gate-level netlist, an encrypted
deliverable or an emulation model — exactly when protocol checking is most needed. It drives nothing,
consumes nothing and holds no handshake; if removing it changes the simulation, it is not a checker.
And it samples on the interface clock through the sampling event, never on a raw signal edge inside
procedural code — a concurrent assertion samples values as they were before that time step's updates,
which is what the receiving flip-flop saw, while procedural code at the same edge races with the design.

The `cover` line is neither optional nor decoration. It separates "this rule holds" from "this rule was
never tried", and step 6 turns it into a pass criterion.

### 5. Draft the message

Use the field order from the **Message convention** slot and pick the level from the **Severity
levels** slot — a should-rule from step 1 does not get a failing severity. The message carries at
minimum the rule ID, what was observed, what was required, the identity of the transaction or beat it
happened on, and the clause back-reference.

Say what was observed, not who is at fault: the rule fires on the interface it watches, the offender
may be the other side or the interconnect, and a message naming a culprit routes half its failures to
the wrong person. Do not print the whole transaction either — the line has to survive being pasted into
a bug report and matched against a signature by `_shared/failure-signature-schema.md`, where every
run-specific value becomes `N`, `T` or `i` anyway and a fifty-line dump normalises to nothing.

### 6. Specify the negative test and the reachability witness

A rule is unproven until something has made it fire on purpose. **Glob** the **Negative-test location**
path and **Grep** it for any existing rule ID to see how tests are tied back to rules here; copy that
convention rather than inventing a naming scheme. Then specify, in the record, the violation to inject
— the smallest deviation from legal behaviour that trips this antecedent, breaks this obligation, and
nothing else. Three separate things the test must show:

1. The rule fires at all, at the expected severity.
2. **Only** this rule fires, or the record names the rules cascading behind it and why. After the first
   protocol violation the interface state is undefined and downstream rules report on garbage.
3. The clean, unmodified test still passes and its `cover` from step 4 was hit. A cover that never hits
   means the rule has been passing vacuously and would have gone on doing so for a year.

The agent cannot start a simulation. **Ask the engineer to run both the negative test and the clean
test, and to give you the path of each log**, saved where the profile's Log location says ours land.
Until those paths exist the record says the fire is not yet run — do not write it up as working.

### 7. Confirm the fire from the log, not from the reasoning

Once the negative-test log is on disk, spend one **Grep** whose pattern alternates the new rule ID with
the profile's **Pass marker** — one call. Neither one present usually means the run died before
reaching the injection, not that the rule is broken.

**Read** about 60 lines around the first rule-ID hit and check four things: the severity is the one step
5 chose, the message fields are in the convention's order, the observed and required values are both
present and actually differ, and the hit count matches what the injection should have produced. A rule
firing eleven times for one injected violation is re-triggering every cycle the antecedent stays true —
a window or qualifier error, not a design bug. Then confirm the **Per-rule control** works: the record
must name how this one ID is disabled on its own. A rule that can only be switched off with its whole
category takes the neighbouring rules with it the first time an integrator hits a false fire.

### 8. Record the rule

Fill this block. Leave a field empty, or write `?`, rather than filling it from assumption.

```
rule id    : <the allocated ID, and where it was allocated>
strength   : shall | shall-not | should | may | reserved
statement  : <the normative sentence, verbatim, and who supplied it>
spec ref   : <document name, revision, clause, in our citation form>
antecedent : <the trigger, and the sampling event it is checked on>
obligation : <what must hold once the antecedent holds>
window     : same-cycle | next-cycle | within-n | bounded-eventually
qualifiers : <reset, enable and mode conditions this rule is disabled under>
severity   : <the level from our severity list, and why a should-rule is not failing>
message    : <the message text, in our field order>
control    : <how this one ID is disabled or waived, and where a waiver is recorded>
neg test   : <path of the test that violates this rule, and the injected deviation>
witness    : <the cover proving the antecedent is reachable, and whether it was hit>
fired      : confirmed | not-confirmed | not-run
coverage   : <files searched, facts that came from a person, and whether the fire and the witness
              were seen in a log or are still pending a run>
notes      : <rules that cascade behind this one, and anything the next person would rediscover>
```

`strength: may` and `strength: reserved` mean there is no rule to write; record the finding and stop
rather than checking something the specification declined to constrain. **State the coverage
honestly** — `fired: not-run` with everything else filled is a useful record, because a reviewer knows
what is outstanding. The same record with `fired: confirmed` and no log path is a claim, and it will be
believed.

## Gotchas

- **An unknown value on the antecedent silently disables the rule.** An assertion expression evaluating
  to X or Z counts as false, so an X on the qualifying signal means the antecedent never triggers and
  the rule passes. The asymmetry is the trap: an X on the *checked* value also evaluates false and so
  reports a failure. X on the trigger hides bugs; X on the obligation reports them.
- **A rule with no cover has never been proven to run.** Vacuous passes are the default outcome of a
  wrong antecedent, and in the log they are indistinguishable from a clean protocol — both print
  nothing at all.
- **An unbounded obligation does not fail in simulation.** A weak property still waiting at the end of
  the run is treated as passing, so "eventually" checks nothing unless the strong form is used or the
  window is bounded. Bound it, and record the bound as a testbench policy with its own owner — the
  specification did not give you that number.
- **The reset qualifier is asynchronous and discards in-flight attempts.** Anything mid-obligation when
  reset asserts is dropped, not failed. That is correct, and it also means this rule can never report a
  violation straddling a reset; if the protocol constrains behaviour across reset, that is a different
  rule with a different qualifier.
- **Retiring a rule is not deleting it.** Leave the ID in the registry with its retirement note — the
  waiver files, triage tables and bug reports naming it outlive the file it lived in.
- **A should-rule at a failing severity gets the whole category switched off.** The first integrator
  hitting a legal-but-unusual design disables it, and takes the neighbouring shall-rules with it when
  the control is per-category. That is why step 7 checks the per-rule control.
- **A checker that reads design hierarchy is not a VIP checker.** It works beautifully at block level
  and disappears at the exact moment the design becomes a netlist or an encrypted deliverable.
- **Eleven fires for one violation is a window bug.** Level-sensitive antecedents re-trigger every cycle
  they stay true. Edge-qualify the trigger, or make the obligation span the whole window, then re-check
  against the same negative test.

## Human verification — what a wrong answer looks like

Before the rule goes near a review, check:

- the normative sentence is quoted **verbatim** with document, revision and clause — and where it came
  from a person rather than a readable file, that person is named and the record says so
- the strength matches the verb: a rule at a failing severity traces back to a shall or a shall not,
  never to a figure, a note or an example
- the ID was checked against the registry as well as the source, and is not a retired one back in use
- the antecedent and the obligation are built from interface signals only
- the negative test made **this** rule fire, seen in a log at a path you searched, any other rule firing
  alongside it is named in the notes, and the clean test still passes with its cover hit
- the per-rule control disables this ID and only this ID
- `fired: not-run` is written plainly when no log was searched, and nothing above it is read as verified

A wrong answer is usually an assertion that passes on every test because its antecedent is unreachable
or permanently X; a rule numbered from the highest ID visible in one file; a "shall" invented out of a
timing diagram; or a message naming the master as the offender when the rule only ever watched the
slave side of the interface.

## Done when

You can hand over a rule ID, the clause behind it, the message it prints, and a log line showing it
fired on a test written to break it — and nothing in that set rests on a number or a sentence you chose
without checking.
