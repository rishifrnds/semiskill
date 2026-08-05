---
name: dv-formal-overconstraint-credit
description: Audit a formal run before anyone believes it — triage each counterexample as a real bug or an environment artifact, show that the assumption set has not quietly made the proofs vacuous, and decide how much sign-off credit the result has actually earned. Use when a property came back proven and you are about to claim coverage credit for it, when a counterexample looks impossible, when someone added an assumption to make a failure go away, when a proof is only bounded to a depth, or when a formal exclusion is about to reach the coverage database.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Over-Constraint Audit and Formal Sign-Off Credit
  semiskill-function: design-verification
  semiskill-role: formal-verification
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-02-24
  semiskill-tags: formal, assumptions, over-constraint, vacuity, bounded-proof, coverage-credit, sign-off
---

# Over-Constraint Audit and Formal Sign-Off Credit

A formal result is exactly as strong as the assumption set behind it, and nothing in the report says
so. Tighten the environment far enough and every property proves — quickly, cleanly, and about a
design that does not exist. Loosen it and the tool returns counterexamples the surrounding silicon
could never produce, and the reflex fix for those is another assumption, which is how a proof becomes
worthless in the same afternoon it becomes green.

This settles three things in that order: whether a counterexample is a real bug, whether the
properties that passed passed for a reason, and how much of the result may honestly be carried into
the coverage picture. The output is **a per-property verdict, an assumption ledger with an owner
against every unjustified entry, and a drafted credit entry** that a human places. Not a summary of
the report.

## When to use something else

This audits a formal run that already exists; it does not set one up and does not write properties.
For turning a normative spec sentence into a checker rule with a negative test, use
`dv-protocol-checker-rule`. For classifying unhit bins in a merged functional-coverage report, use
`dv-coverage-hole-disposition` — that skill's `proof` field wants a path to a formal output, and this
one decides whether that output deserves to be quoted there. For a ranked closure plan across a whole
merged report use `dv-coverage-hole-closure`, and for the merged number itself
`dv-coverage-merge-report`. For assembling the release evidence once credit is settled, use
`dv-release-gate`. A formal setup that will not elaborate at all is a build problem —
`dv-build-filelist-hygiene`. A simulation log is `dv-sim-log-first-error`, not this.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Formal setup location | [[FILL: three paths — our formal setup or constraint script, the property files it loads, and where a run's saved text report lands — and whether the script and the properties sit under one root a single pattern can reach]] | formal owner |
| Proof status vocabulary | [[FILL: the exact strings our report prints for a full proof, for a bounded proof and the depth it reached, for a counterexample, and for an inconclusive result]] | formal owner |
| Reachability and vacuity checks | [[FILL: which checks our tool runs for cover reachability, for a contradictory or dead-end assumption set, and for vacuity, and the string each prints when it passes and when it does not]] | formal owner |
| Abstraction directives | [[FILL: the commands or pragmas our setup uses for cutpoints, blackboxes and abstractions, so they can be located in the script]] | formal owner |
| Reset and initial-state modelling | [[FILL: how our setup models reset, and whether a proof starts from a modelled reset sequence or from an arbitrary state]] | formal owner |
| Interface contract source | [[FILL: where the protocol rules our assumptions are meant to encode are written down, and whether it is a file that can be read]] | block owner |
| Assumption ownership record | [[FILL: where we record who owns each assumption and how it is discharged — proved on the neighbouring block, covered in simulation, or accepted as environmental]] | verification lead |
| Formal credit convention | [[FILL: what our coverage flow accepts as formal credit, and the file and format that credit is recorded in]] | verification lead |

Three pack-wide facts are read from `_shared/team-profile.md` and are deliberately not repeated
above: **Coverage output** (step 8, where credit has to land), **Area to owner map** (step 9, the only
thing routing may key on) and **Sign-off** (step 9, who takes the report). The profile's **Log
location** row is *not* the same fact as Formal setup location and must not be substituted for it: it
records where simulation and regression logs land, whereas a formal run writes a report from a
different flow, and this skill needs three separate paths — script, properties, report — where that
row carries one. If your flow genuinely writes both to one place, say so once here rather than
assuming it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented status string makes
every Grep in step 2 return nothing, which reads identically to a run in which nothing failed.

## Retrieval budget — read this before opening anything

Property files are readable; formal reports and RTL are not. A report over a few hundred properties
runs to tens of thousands of lines, and a trace export is longer than the design.

1. **Grep, Read and Glob work on files on disk.** A counterexample pasted into the chat is not
   searchable, and **a waveform cannot be opened at all** — no Read, Grep or Glob reaches one. If the
   only form of the trace is a waveform, say so plainly: the counterexample triage in step 3 becomes
   a handoff to a person, and everything resting on it is provisional. Ask for a text export of the
   trace and its path before treating step 3 as done.
2. **Glob before Read, Grep before Read.** Never open the report or a generated property list with
   Read as the first move.
3. The whole ledger is **2 Globs, at most 9 Greps, and at most 6 windowed Reads — five of about 60
   lines and one of about 40 — plus one conditional spare 40-line window**. The Greps are spent: one
   in step 2 on the report for the status strings; two in step 3, one for the counterexample section
   and one for the failing property's name in source; two in step 4, one for the assumption keyword
   across the property files and the setup script and one for the abstraction directives; one in
   step 5 for the reachability and vacuity check strings; one in step 6 counting declared properties
   in source; one in step 7 for the bounded-proof string. The ninth is step 8's Grep of the credit
   file, and it is spent only when that file is on disk. The five 60-line Reads are the status
   table, the trace window, the two assumption windows and the reachability results; the 40-line one
   is the failing property's declaration in step 3. The spare belongs to **step 4 alone** and only
   under the condition named there — the script's abstraction section, when a directive's hit line
   does not name what it abstracts. If that condition does not arise the spare stays unspent; it is
   not a general reserve, and no other step may claim it. Steps 6 to 9 open nothing new and read
   their answers out of Grep output already in hand.
4. If a Grep returns more than about 200 hits, the pattern is too broad — narrow it before reading
   anything. An assumption keyword across a large environment will do exactly this.
5. **Stopping rule.** If the two assumption windows have not classified the set, stop classifying.
   Report the count found, the count classified, and which ones were left — never extend into a
   third window, and never classify an assumption you have not read.
6. State what you actually covered: how many assumptions of how many were classified, how many
   properties had their status read, and whether the trace was read from a file or described by a
   person. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Find the three artifacts, and name what cannot be reached

Two **Glob** calls against the **Formal setup location** slot: one spanning the setup or constraint
script and the property files, one for the saved report. Three artifacts must exist before anything
else is worth doing — the script that builds the environment, the properties, and a report from a run
of that script against those properties.

That first call assumes the script and the properties sit under one root a single pattern can reach,
which is exactly what the slot is asked to state. Where the slot says they do not, spend the two
Globs on the script and the properties separately and take the report path verbatim from the slot
instead — a path the slot spells out in full needs no search — and say in the report which of the
three was found by pattern and which was handed to you.

Then say out loud what is missing. A report with no script is unauditable: the assumptions that
produced it are not visible, and no verdict below can be reached. A script whose report is from an
older revision is worse than no report, because every status in it is about a different environment;
check any revision or date stamp the two carry against each other and stop if they disagree.

### 2. Take the status inventory before opening a single trace

One **Grep** of the report for the strings in the **Proof status vocabulary** slot — full proof,
bounded proof, counterexample, inconclusive — in one call, then one windowed **Read** where the hits
cluster. Write down the four counts, and record each property in the canonical `proof status`
spelling: a full proof is `proven`, a counterexample is `falsified`, and `bounded` and `inconclusive`
keep their own words. `not-read` is for a property whose status was never read at all — a reading
status rather than an engine outcome, so keep it out of proof-outcome denominators.

The inventory is the only number in the whole procedure that is cheap, and it frames everything: a
run that is 90 percent inconclusive is a capacity problem, not a sign-off candidate, and a run where
every property is `proven` on the first attempt is the single strongest indicator of over-constraint
there is.

Do not start with the counterexample. A counterexample in an over-constrained environment is still
information, but which kind it is cannot be decided until step 5 has looked at the constraint set.

### 3. Triage the counterexample before touching an assumption

One **Grep** for the counterexample section, one windowed **Read** of the trace, one **Grep** for the
failing property's name in source and one 40-line **Read** at its declaration.

If the trace never resolves to text on disk — a waveform only, or an account someone gave you in a
message — stop the triage here rather than reasoning from the summary line. Write `cex: not-analysed`
and `class: unknown`, mark the finding provisional, and ask for a text export and its path per budget
point 1. `cex: not-analysed` is also the honest entry for a falsified property whose trace you simply
have not reached inside the budget, which is what lets a partial audit say which traces were opened
and which were not.

With the trace in hand, classify it as exactly one of four artifacts, in this order — the order
matters, because each later class costs more to establish than the one before. Each bullet ends in
the token that goes on the `cex` line of step 9; write that token, not a paraphrase of it:

- **A property bug.** The property does not say what its author meant: an overlapping implication
  where a non-overlapping one was meant, a missing disable condition so the property is checked
  through reset, a sampled value taken a cycle from where it was intended, a clocking event that is
  not the clock the signals live on. Read the declaration before the design. This is the most common
  outcome and the cheapest to confirm, because it is settled entirely in the source you have already
  opened. Write `cex: property-bug`.
- **An abstraction artifact.** The trace turns on a signal the setup made free — a cutpoint, a
  blackbox output, an abstracted counter or memory. Those signals have no driver in the model, so
  they can do anything, and the trace is describing the abstraction rather than the design. Find
  them with the **Abstraction directives** Grep in step 4 and compare against the signals the trace
  actually moves. Where one of them is what the trace moves, write `cex: abstraction-artifact`.
- **An initial-state artifact.** The trace begins in a state the design cannot reach after reset.
  Check the **Reset and initial-state modelling** slot first: a proof that starts from an arbitrary
  state will happily produce these, and they are not bugs. A trace whose violation is at cycle 0 or 1
  is this case until proven otherwise. Write `cex: initial-state-artifact` — it has its own token
  precisely because it is neither an environment sequence nor an abstraction, and filing it as either
  one loses the fact that the fix is in how reset is modelled.
- **A spurious input sequence.** The environment drove something the real neighbours never drive.
  This is the class that justifies a new assumption — and **only** if you can name the rule that
  makes the sequence illegal and say where that rule is written, from the **Interface contract
  source** slot. "The neighbour would not do that" is a belief. A clause reference is evidence. If
  the contract source is not a file that can be read, the justification is a handoff: ask the block
  owner for the rule and record that the answer came from a person. With the rule named, write
  `cex: spurious-environment`; without one, the class is not established and the entry stays
  `cex: not-analysed` until it is.

What is left once all four are excluded is a **real bug**: write `cex: real-bug`, and it is the only
case that gets a failure signature — derive it per `_shared/failure-signature-schema.md`, same field
order (`phase|kind|where|what`), same normalisation rules, pipe-delimited and compared exactly. Use
`run` as the phase: the violation is a runtime behaviour of the design, and that keeps the string
comparable in shape with one from a simulation failure. Do not promise more than that. The two tools
word their messages differently, so `what` will rarely match character-for-character across them;
`where` is the field that carries, and it is what routing in step 9 uses.

The `class` line follows from the token and never from a feeling about severity. `cex: real-bug` is
`class: design` — the design does the wrong thing. All four artifacts are `class: infrastructure`:
the counterexample is a fact about the property, the abstraction, the reset model or the environment,
all of which are verification code however senior the person who wrote them. `class: unknown` belongs
with `cex: not-analysed` and nowhere else — an unread trace is the one case where the side of the
line is genuinely not known yet.

### 4. Inventory the assumptions and classify every one

One **Grep** for the assumption keyword across the property files and the setup script, and one for
the **Abstraction directives** strings. Take the counts first, then spend the two windowed **Read**
calls on the densest regions. Classify each assumption you read into exactly one of these, and record
the file and line for every single one:

1. **Contract-backed** — it encodes a rule from the **Interface contract source**, with a clause
   reference. The strongest class, and the only one that needs no further argument.
2. **Assume-guarantee** — it will be discharged as an assertion on the block that drives the signal,
   at the level above. Legitimate, but it is a debt: it is only true once that assertion is proven,
   and until then the proof here is conditional. Record it in the **Assumption ownership record**.
3. **Mode-restricting** — it pins a configuration, a mode or a parameter. Legitimate, and it narrows
   what the proof means: credit applies to that mode and to no other. Name the mode in the report.
4. **Convenience** — it was added to make a counterexample go away and has no external justification.
   This is the class that destroys proofs. Every one needs an owner and a route to class 1, 2 or 3,
   and until it has one, no property in its cone earns credit.

Two shapes deserve their own line in the report wherever they appear. An assumption written on an
**internal** design signal rather than on a boundary input constrains the design itself and can
assume the bug away — quote its hierarchy path in full. And an assumption over the same expression an
assertion checks is a tautology dressed as an environment rule; so is the subtler form, where the
assumed signal is downstream of the asserted one.

The abstraction Grep usually settles itself, because a cutpoint or blackbox line names its target on
the hit line and step 3 can compare that name against the trace directly. Where it does not — a
directive that takes a list, a wildcard, or a variable the hit line does not expand — this is the one
place the budget's spare 40-line **Read** may be spent, on the script's abstraction section, once,
and for nothing else. If the hit lines name their targets, leave the spare unspent and say so in the
`coverage` line rather than opening the section to be thorough.

### 5. Test the assumption set itself — contradiction, dead end, vacuity

One **Grep** of the report for the strings in the **Reachability and vacuity checks** slot, then one
windowed **Read** of the results. Three distinct failures hide here and none of them looks like a
failure in the status inventory:

- **Contradiction.** If the assumptions cannot all hold at once, every assertion is proven and every
  cover property is unreachable. The tell is on the cover side, never the assert side: a run with a
  wall of proofs and no reachable cover is not a good run, it is an empty one.
- **A dead end.** The set is satisfiable up to some depth and has no legal successor beyond it.
  Everything past that depth proves for free while the summary still reads as proven. This is the
  partial form of the case above and it is far harder to see, which is why the check exists as its
  own item in the slot rather than being folded into the reachability one.
- **Vacuity.** An implication whose antecedent is never satisfiable under the constraints passes
  without checking anything. If our tool reports antecedent or trigger reachability, read it; if it
  does not, the line is `not-checked` rather than clean.

Those three checks decide the `vacuity` line of step 9, and it carries three values because there
are three outcomes rather than two. Write `vacuity: clean` only where all three ran against this
report's own run and every one passed against the pass strings the **Reachability and vacuity
checks** slot records. Write `vacuity: suspect` where a check ran and the answer was not a pass — an
unreachable cover, a contradiction or dead-end report, an antecedent the tool could not show
reachable — and equally where it ran but the result cannot be read as a pass: a string the slot does
not cover, a result printed for a different property set, or a check whose output belongs to the
older revision step 1 told you not to trust. Write `vacuity: not-checked` only where the check was
never run, or where our tool has no antecedent-reachability report to run. Never fold `suspect` into
`not-checked`: one says the tool looked and the answer was wrong or unreadable, the other says
nobody looked, and only the first is evidence about this run.

A `suspect` or a `not-checked` vacuity line is a finding on its own, and it is the finding that most
often turns a green run amber. To settle a class 4 convenience assumption from step 4, do not reason
about it — **ask the formal owner to re-prove the property with that one assumption removed and to
give you the path of the new report**, then repeat step 2 against it. A property that still proves
without the assumption never needed it; one that produces a counterexample sends you back to step 3
with a real question.

### 6. Check that the properties you think were proven were actually there

One **Grep** counting the assertion declarations in the property files, compared against the property
count from step 2. A property that was never elaborated — sitting inside a disabled generate, in a
file the formal filelist does not include, or under a name the setup never selected — reports
absolutely nothing, and nothing is what a passing property also reports.

Treat a discrepancy as a question rather than a verdict: one macro can expand into several
properties and one file can be compiled into more than one instance, so the two counts are not
required to match exactly. What is required is that the properties in the sign-off claim appear by
name in the report. Check those by name. If the shortfall is a file the build never picked up, that
is `dv-build-filelist-hygiene`'s problem, not this one.

### 7. Read the bound before calling anything proven

One **Grep** for the bounded-proof string from the **Proof status vocabulary** slot. A bounded proof
says only that no violation exists within some depth of the initial state. It is a per-property fact,
not a per-run one, so a summary line claiming the run is proven is not evidence about any particular
property in it.

Record the bound with its units exactly as the report states them, and then ask the one question that
matters: what behaviour in this block needs more cycles to set up than the bound allows? Arbitration
under contention, a buffer reaching full, a retry after an error, a credit loop wrapping — these
routinely need more depth than a default bound provides. The agent cannot know the block's latencies;
ask the block owner and record who answered.

### 8. Decide the credit, and draft the entry someone else places

Credit is `full` only when four things hold together: the status is `proof status: proven`, step 5's
line reads `vacuity: clean`, the assumption ledger has no unclassified and no convenience entries
left in that property's cone, and the property appears by name in the report.
Miss any one and it is not full credit — it is `bounded` where step 7 supplied a depth, `withheld`
where an audit finding is open including a `vacuity: suspect` line, and `none` where the check never
ran or the status came back inconclusive.

Two claims are commonly made here and only one of them is defensible. The cone of influence of a
property is an **upper bound** on what that property could ever have checked — it is not evidence
that anything was checked, and quoting it as coverage overstates the result by a wide margin. What
the proof actually depended on is the defensible measure; if our tool reports it, quote that, and if
it does not, say so rather than substituting the cone.

Unreachability found by formal is legitimate exclusion evidence, with one condition that is
absolutely load-bearing: **the constraints must have been audited first**. Over-constraint makes live
code look dead, and an exclusion written on that basis hides working logic from coverage for the rest
of the project, long after the run that produced it is forgotten. Any exclusion drafted here carries
the audit date and the constraint set revision it rests on, so the next person can tell whether it is
still true.

Then draft — do not place — the credit entry, in the shape the **Formal credit convention** slot
records, and one **Grep** of that file (only if it is a file on disk) to check the property is not
already recorded there under another name. The agent has no write access to the coverage flow by
design: hand the drafted text to the owner of the profile's **Coverage output** and ask them to place
it. If the credit convention slot is unfilled, hand the audit back and ask what shape credit takes
here rather than inventing a format.

### 9. Record the finding

One block per property claim. It reuses `signature`, `class`, `evidence`, `owner`, `run id`,
`coverage` and `notes` from the pack's other handoff blocks so a formal finding and a simulation
finding read side by side; the rest are this skill's own.

```
property   : the property name, exactly as the source spells it
proof status: proven | bounded | falsified | inconclusive | not-read
bound      : the depth the report states, with its units, or empty when proof status is proven
cex        : real-bug | spurious-environment | property-bug | abstraction-artifact | initial-state-artifact | not-analysed
signature  : phase|kind|where|what, per the shared schema, for a real-bug cex only
class      : design | infrastructure | unknown
vacuity    : clean | suspect | not-checked
assumptions: n in force in this cone; k unjustified, listed by file and line
credit     : full | bounded | none | withheld
evidence   : file path and line for every assumption, directive and status quoted above
owner      : the name the profile's area-to-owner map gives for the signature's where
run id     : whatever identifies this formal run for us
coverage   : classified n of m assumptions; status read for p of q properties; trace from file or person
notes      : anything the next person would otherwise rediscover
```

The `cex` line takes exactly one of the six tokens step 3 assigns, and is left empty where the
property was never falsified — a `proven` or `bounded` property has no counterexample to classify,
and `not-analysed` there would read as an unread trace that does not exist. The `signature` line is
pipe-delimited because the whole pack joins on it: `_shared/failure-signature-schema.md` compares
signatures exactly, so a signature written with any other separator matches nothing anyone else has
recorded, however correct its four fields are.

There is deliberately no `phase` field. The pack's five phase tokens describe a simulation's
lifetime, and a proof has no equivalent; the phase that belongs in the signature is stated in step 3
instead. Leave any line empty rather than filling it plausibly, and route on the signature's `where`
through the profile's area-to-owner map, never on the property name. The report goes to whoever the
profile's **Sign-off** entry names, and if that entry is unfilled, ask rather than picking someone.

## Gotchas

- **Contradictory assumptions prove everything and announce nothing.** There is no error message for
  it. The evidence is always on the cover side: if the covers that should obviously hit are
  unreachable, no proof in that run means anything, however many of them there are.
- **A dead-end constraint set is worse than a contradiction, because it is partial.** Legal to depth
  k, no legal successor at k+1, everything beyond k proven for free — and the summary still says
  proven. It is invisible in the status counts by construction.
- **A cutpoint under-constrains, and the obvious repair over-constrains.** Cutting a net makes it a
  free input and spurious counterexamples follow; the reflex is to constrain the cut net, and a
  constraint tighter than its real driver silently deletes legal behaviour. Constrain it only with
  the driver's own guarantee, and log it as an assumption to discharge.
- **A blackbox turns its outputs into free inputs.** That is under-constraint, which is safe for
  proofs and noisy for counterexamples. Assuming those outputs are well behaved swings it the other
  way in one line, and now it is over-constraint wearing an abstraction's clothes.
- **Over-approximating abstractions keep proofs sound; under-approximating ones do not.** A counter
  or memory abstraction that adds behaviours can only produce spurious counterexamples. One that
  removes behaviours — including a plain range assumption on a counter — removes them from the proof
  as well, and that is over-constraint by another name.
- **A bounded proof is a per-property fact.** Mixing bounded and full statuses under one run-level
  headline is the most common way an unproven corner reaches a sign-off slide, and it survives review
  because the headline is technically true.
- **Cone-of-influence coverage is not proof coverage.** The cone says what the property could have
  touched; what the proof depended on says what it did. Reporting the first as credit is the single
  largest overstatement available in formal sign-off.
- **A property that was never elaborated is silent, and so is a passing one.** A file left out of the
  formal filelist, a generate condition that is false, a name the setup never selected — all three
  produce a clean report and no check. Confirm by name, not by count.
- **A proof is conditional until its assumptions are discharged.** An assume-guarantee obligation
  that never becomes an assertion at the level above is an assumption nobody will ever test, and the
  block it protects is the one that ships.
- **An exclusion outlives the constraint set that justified it.** Re-audit any formal exclusion when
  the setup script changes; a stale unreachability claim quietly hides live code from coverage and
  nothing in the flow will ever flag it.

## Human verification — what a wrong answer looks like

Before anyone signs anything, check:

- every assumption named in the report is quoted with a file path and line number, and every one
  landed in exactly one of step 4's four classes
- no counterexample is dismissed as spurious without naming the rule that makes the sequence illegal
  and where that rule is written — or, if the contract source is not readable, without attributing
  the answer to the person who gave it and marking the finding provisional
- the `vacuity` line is present, and reads `clean` only where all three step 5 checks ran against
  this run and passed — `suspect` where one came back negative or unreadable, `not-checked` where it
  never ran at all. A `clean` standing in for either of the other two is the failure this whole audit
  exists to prevent
- every falsified property carries one of step 3's six `cex` tokens, `not-analysed` appears only
  where the trace was never read from a file, and a proven or bounded property leaves `cex` empty
- the `signature` line is pipe-delimited, `phase|kind|where|what`, so it can be matched against a
  signature someone else recorded
- `credit: full` appears only where all four conditions in step 8 hold, and a stated bound never
  appears next to it
- the bound is quoted with its units exactly as the report states them
- no exclusion is proposed from a run whose reachability check failed or was not run
- the drafted credit entry is still text — the agent placed nothing, and the coverage owner is named
- the coverage line gives both denominators, and says whether the trace was read from a file or
  described by a person

A wrong answer is a clean table reading "all 43 properties proven, full credit" produced from a run
in which every cover was unreachable — it is the most confident-looking output this task can produce
and it is worth nothing. The next most common is a counterexample closed as illegal stimulus with a
new assumption and no clause behind it, which is how a real bug is assumed away in one line.

## Done when

Every property in the claim carries a credit value, every assumption behind it carries a class and an
owner, and the coverage owner has a drafted entry they can place without asking you anything.
