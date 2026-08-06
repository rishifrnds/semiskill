---
name: dv-memory-ordering-litmus
description: Adjudicate one observed multi-hart litmus outcome against the core's memory model by reading the litmus source, the golden allowed-outcome file and the per-hart traces, then name either the ordering rule the design violated or the defect in the test. Use when an MP, SB, LB or IRIW style test reports a surprising final state, when someone says the core reordered two stores, when the golden allowed-outcome file and the hardware disagree, or when you have to decide whether a multicore ordering result is a bug before anyone files it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Litmus-Test Outcome Adjudication Against the Memory Model
  semiskill-function: design-verification
  semiskill-role: processor-ip-dv-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-06-27
  semiskill-tags: memory-model, litmus, ordering, coherence, multicore, fences, dependencies, traces
---

# Litmus-Test Outcome Adjudication Against the Memory Model

A litmus test earns its keep because the verdict is supposed to be binary — the observed final state
either sits inside the set the architecture permits, or the design broke a rule. What happens instead
is that a surprising outcome gets reported as an ordering violation, three people spend a fortnight
inside the store buffer, and it ends at a test that could never have told the two executions apart:
two writes carrying the same value, a register no load ever wrote, a dependency the assembled program
does not contain. This procedure adjudicates **one** outcome and ends in exactly one of three things —
the model rule the design violated, the defect in the test or its golden file, or an honest
`unadjudicable` naming the single artifact that would settle it.

## When to use something else

- A failing simulation log of any kind, ordering or not, starts at `dv-sim-log-first-error`. Come back
  here once the failure is known to be a disagreement about a *set of allowed outcomes*.
- A whole regression night to sort and route is `dv-regression-triage-routing`; shrinking one signed
  failure to the smallest run that still shows it is `dv-minimal-reproducer`.
- A **single-hart** mismatch between the design's architectural state and a reference model — wrong
  register, wrong trap, wrong CSR — is a step-and-compare question. Nothing here applies: with one
  hart there is no second program, so there is no execution to adjudicate.
- An X, a Z or an undriven signal at the failing check is `dv-signal-trace-localisation`. Register
  access failures are `dv-ral-bringup`. A break before simulation started is
  `dv-build-filelist-hygiene`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Memory model of record | [[FILL: the architecture specification and revision our core claims to implement, and the name of the chapter that defines the memory ordering rules]] | core architect |
| Litmus source location | [[FILL: where the litmus test sources live, and where the assembled program each hart actually ran is kept]] | processor DV lead |
| Golden outcome file | [[FILL: where the allowed-outcome list for a test lands, which model checker and which model revision produced it, and whether it enumerates every allowed state or only the states the test asks about]] | processor DV lead |
| Trace location and format | [[FILL: where each hart's retired-access trace lands, one file per hart or one interleaved file, and which columns carry the instruction address, the data address, the data value and the ordering timestamp]] | DV infra |
| Observed outcome record | [[FILL: where the harness records the final register and memory state for one run, and whether it also records which write each read returned]] | DV infra |
| Location naming | [[FILL: how a location name in the litmus source maps to the address that appears in the trace — a symbol table, a map file, or a fixed base plus stride]] | processor DV lead |
| Ordering primitives | [[FILL: the fence and ordered-access mnemonics our tests are allowed to use, and which access pairs each one is documented to order]] | core architect |
| Quiescence marker | [[FILL: the string our harness prints once every hart has retired its last litmus access and the final state has been sampled]] | DV infra |

**Quiescence marker is narrower than the profile's Pass marker.** The profile's Pass marker says the
whole run finished cleanly; this one says the *sampling point* was legitimate, and a run can print the
first without ever having printed the second. If they are genuinely the same string here, say so; do
not assume it. Two facts this skill also needs — **Run identity** and the **Known-issue list** — are
pack-wide and live in `_shared/team-profile.md`. Read them from there; they are not re-asked above.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented location-to-address
map or an invented fence semantics produces a confident verdict about silicon, and unpicking that
costs far more than no verdict.

## Retrieval budget — read this before opening anything

A litmus binary is tiny and its trace is not: one test run ten thousand times across four harts is a
multi-gigabyte artifact, and the interesting window is about forty accesses wide. Work in this order,
and stop the moment the adjudication settles.

1. **Grep and Read work on files on disk.** If the outcome arrived pasted into the chat, resolve it to
   a path under the **Observed outcome record** slot first. Until a path exists you may reason over
   the pasted lines by eye, but every field below is provisional and must say so.
2. One **Glob** — the litmus source, the golden outcome file and the trace files, in a single call.
3. Two whole-file **Read** calls, both expected to be small: the litmus source and this run's observed
   outcome record. If the litmus source runs past about 120 lines it is not a litmus test; stop and
   say so rather than paging through it.
4. One **Grep** for the **Quiescence marker**.
5. At most two **Grep** calls against the golden outcome file — one for the test name, one for the
   observed state.
6. At most six **Grep** calls against the traces — one per location-and-hart pair you actually need.
   The final condition names at most two or three shared locations; take those, and record which pairs
   you did not check.
7. At most four windowed **Read** calls of about 60 lines each in the traces, every one entered at a
   line number a Grep in step 6 returned. Never browse a trace.
8. One further **Grep** of the known-issue list, and only if that list is a file on disk.
9. **Stopping rule.** The budget is one Glob, six Reads and ten Greps. If the adjudication has not
   settled when it is spent, stop, write `adjudication: unadjudicable`, and name the one artifact that
   would settle it. Past this point the edges get invented, and an invented edge reads exactly like a
   real one.
10. State what you actually covered — how many harts' traces you opened, and whether coherence order
    was fully or only partially recovered. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the outcome to files, and prove the sampling point was legitimate

Spend budget lines 2, 3 and 4 here. **Glob** for the three artifacts. **Read** the observed outcome
record whole and copy the final state verbatim — this string is compared character by character later,
so paraphrasing it destroys the comparison.

Then **Grep** for the **Quiescence marker**. A final state sampled while a hart was still retiring
litmus accesses is not an outcome; it is a snapshot of a run in progress, and it will show states no
model permits. If the marker is absent, record `defect: trace-incomplete` and stop — this is the
cheapest wrong answer available and it is worth ruling out before anything else.

If any of the three artifacts does not exist, **ask the engineer to re-run the test with tracing
enabled and give you the paths**. The agent cannot start a simulation, cannot assemble the test and
must not describe what a run would have printed.

### 2. Read the test, then check the two things that make it adjudicable at all

**Read** the litmus source (budget line 3). Record, in this order: the initial state — every location
and register the test assumes, with its initial value; each hart's program in program order; the final
condition exactly as written, including whether it is an existence claim or a negated one; and the
value each write puts into each shared location.

Now two checks that cost nothing and settle a large share of these cases before any trace is opened.

- **Every write to a shared location must carry a distinct value, distinct also from the initial
  value.** If two writes to one location write the same thing, no final state can say which write a
  read returned — the reads-from edge is unrecoverable, and every edge derived from it is a guess.
  Record `defect: value-collision`, write `adjudication: unadjudicable`, and stop.
- **Every register named in the final condition must be written by a load on the hart it belongs to.**
  A register no load ever wrote holds whatever the harness left there, usually zero, and matches the
  interesting outcome for free. Record `defect: dead-register` and stop.

Also confirm each location the test uses appears in the initial state (`defect: init-incomplete`) and
that the final condition is not asserting the opposite of what the test intends
(`defect: condition-inverted`). Both are one-line reads and both have wasted weeks.

### 3. Take the model's answer from the golden file, never from memory

Spend budget line 5: **Grep** the golden outcome file for the test name, then for the observed state.
Three results, and they route differently.

- **The state is listed as allowed.** Then `adjudication: allowed` and there is no bug, however
  surprising the outcome looks. Quote the line of the golden file that says so and stop.
- **The state is listed as forbidden, or the file enumerates every allowed state and this is not among
  them.** It is a *candidate* violation. Continue to step 4; do not file anything yet.
- **The file does not mention this test, or carries a different model revision than the Memory model
  of record slot names.** Record `defect: golden-stale`, write `adjudication: unadjudicable`, and say
  which revision each artifact carries.

One distinction decides how much this file is worth. A golden file **produced by a model checker from
the model definition** can say *forbidden*. A golden file **accumulated from states people observed**
can only say *not yet seen* — an unlisted state is news, not a violation, and a listed state is not
thereby architecturally permitted. The Golden outcome file slot asks which one this is precisely
because the two are indistinguishable once they are both sorted lists of states.

### 4. Recover the actual execution from the traces, as edges

Only now open a trace. Use the **Location naming** slot to turn each location name into the address
that appears in the trace, then spend budget line 6: one **Grep** per location-and-hart pair, at most
six. Then at most four windowed **Read** calls (budget line 7) around the first access of interest on
each hart.

Write the execution down as edges, not as prose. Four edge kinds, and where each comes from:

| Edge | Means | Recovered from |
|---|---|---|
| `po` | program order inside one hart | that hart's trace, directly — the one edge a trace always gives you |
| `rf` | the write a read returned | the read's value, and only because step 2 proved the values distinct |
| `co` | the order writes to one location took | a global order or timestamp in the trace; often only partial |
| `fr` | a read, to every write ordered after the write it read | derived from `rf` and `co`; never printed anywhere |

`fr` is the one people leave out. If read *r* read from write *w1*, and *w2* is coherence-after *w1*,
then *r* has an `fr` edge to *w2*. Nothing prints it, and it closes most of the cycles that matter.

If the trace carries no global timestamp or ordering channel, `co` is only partially recoverable. Say
so in the coverage line and mark the finding provisional rather than filling the gaps by eye.

### 5. Look for a cycle, using only the edges the model preserves

An outcome is forbidden when the edges the model preserves form a cycle: no single global order of
memory accesses can be consistent with all of them at once, so the execution cannot happen. Build that
graph from step 4, keeping every `rf`, `co` and `fr` edge, but keeping only those `po` edges the model
actually preserves.

Which `po` edges survive is exactly what the memory model defines, and what the **Ordering primitives**
slot records for our stream. The general shape below holds across the models these tests are written
against — confirm each row against the Memory model of record rather than against this table.

| Pair in program order | Usually preserved by |
|---|---|
| store → store | a store-store fence, or a release annotation on the second |
| load → load | a load-load fence, an address dependency, or an acquire annotation on the first |
| load → store | an address dependency, a data dependency, a control dependency, or a fence |
| store → load | a full fence only — no dependency orders this pair |
| both accesses to the same location | always preserved; per-location coherence needs no fence at all |

Two traps live in that table. A **control dependency from a load to a later load orders nothing** —
the branch is predicted, the second load issues early, and if the prediction held nothing replays;
only a control dependency to a later *store* is preserved, because a store cannot be made visible
speculatively. And **address and data dependencies are defined syntactically** in the models that
define them at all, so whether a chain that computes a constant still counts is a property of the
model text, not of the microarchitecture — read it in the Memory model of record and do not assume
either answer.

Two rules sit outside the cycle test and must be checked separately:

- **Store-to-load forwarding inside one hart is not a cycle.** A read may return its own hart's earlier
  write before that write is visible anywhere else; the models permit this with a separate load-value
  rule. Feeding an internal `rf` edge into the graph invents violations in tests that are correct.
- **A read-modify-write pair is atomic.** The models add a rule saying no other write may be
  coherence-ordered between the paired load and store. An outcome that puts another hart's write
  between them is forbidden by that rule even when the edge graph is acyclic.

### 6. Name the rule, or name the defect

If a cycle exists and every edge in it is preserved by the model, the outcome is forbidden and the
design violated the model. Name the rule of the Memory model of record that preserves the **weakest
edge** — the one edge whose removal makes the cycle disappear — because that is the edge the
microarchitecture failed to enforce, and it is the only sentence the designer needs.

If a cycle exists but one edge is preserved only by something the test does not actually contain — a
fence absent from the source, a dependency broken in the assembled program, a register the calling
convention clobbered — then the outcome is `adjudication: allowed` and the expectation was
over-strong. Record `defect: broken-dependency` and quote the two lines of the assembled program that
show the chain is not there.

If no cycle exists under the preserved edges, the outcome is allowed. Say which `po` edge is not
preserved, so the next reader does not redo the work.

Three shapes are outside the answer you are holding, whatever the graph says. Overlapping accesses of
different widths (`defect: mixed-size`), an access to a device or non-cacheable region
(`defect: wrong-region`), and two location names resolving to overlapping bytes
(`defect: aliased-location`) are all governed by rules a single-size, ordinary-memory model answer does
not carry.

### 7. Cross-check against the known-issue list, then classify

Spend budget line 8. If the profile's **Known-issue list** is a file on disk, **Grep** it once for the
signature. If it is a tracker no tool here can reach, say the check is pending and name who can run it.
Do not match from memory — that is how the same ordering bug gets filed twice under two names.

Then set `class`. A confirmed forbidden outcome with every edge traced is `class: design`. A defect in
the test, the golden file, the harness or the trace is `class: infrastructure`. Anything that stopped
on the budget is `class: unknown`, and saying so is the correct answer.

### 8. Write the finding

Compose the signature per `_shared/failure-signature-schema.md` — same field order, same normalisation
rules — then fill this block. It reuses `signature`, `class`, `run id` and `notes` from
`dv-sim-log-first-error`'s repro block so the two read side by side.

```
signature    : <phase>|<kind>|<where>|<what>, per the shared schema
test         : <litmus test name, its family, and the source path>
observed     : <the final state, verbatim from the outcome record>
adjudication : allowed | forbidden | unadjudicable
rule         : <the named rule of the model of record the cycle violates, or empty>
cycle        : <the edges in order, each labelled po, rf, co or fr, or empty>
weakest edge : <the one edge whose removal breaks the cycle, or empty>
defect       : none | value-collision | dead-register | init-incomplete | broken-dependency | aliased-location | mixed-size | wrong-region | condition-inverted | golden-stale | trace-incomplete
class        : design | infrastructure | unknown
candidates   : <microarchitectural candidates for the weakest edge, as candidates and never findings>
run id       : <whatever identifies this run for us>
traces       : <path per hart, and the line range worth reading>
coverage     : <n of m harts opened; co fully or partially recovered; which budget lines were spent>
notes        : <anything the next person would otherwise have to rediscover>
next test    : <the one litmus family that would confirm or kill this, and why>
```

Take `kind` for the signature from the shared schema's list, not from a new word: `scoreboard` when
the harness's own final-state comparison flagged the outcome, `assert` when a checker in the testbench
fired first. For `candidates`, keyed on the weakest edge: a store-store failure suggests a store buffer
draining out of order or writes merging across a fence; a load-load failure suggests load-load
speculation with no replay on a snoop; a store-load failure suggests store buffer forwarding to a load
that should have waited; a same-location failure suggests two paths to one line. Hand those over as
candidates. They are where the designer looks first, not what you found.

## Gotchas

- **`fr` closes most cycles and is printed nowhere.** In the store-buffering shape there is no `rf`
  edge between the harts at all — every read returns the initial value — so the cycle is
  `po`, `fr`, `po`, `fr`. An analysis that draws only `po` and `rf` finds nothing and clears a real
  violation.
- **A control dependency between two loads orders nothing.** It is the most common over-strong
  expectation in a litmus suite, and it presents as "the core reordered my loads" from someone who
  wrote a branch between them and no fence.
- **Two writes with the same value make the test unadjudicable, not lenient.** If both harts store 1 to
  x, the final value 1 names no write, and every `fr` edge downstream of it is a guess dressed as
  evidence.
- **Store-to-load forwarding inside one hart is legal and is not a cycle.** The models handle it with a
  separate load-value rule. Feed that internal edge into the graph and you will manufacture violations
  out of correct tests.
- **A cycle confined to one location is almost never a test defect.** Per-location coherence holds with
  no fence and no dependency, so there is nothing the test could have got wrong. Stop hunting for the
  missing fence and look for two paths to the same line — a bypass around the coherence point, or a
  write-through path racing a cached one.
- **Multi-copy atomicity decides the IRIW and WRC families, and it is a property of the specification.**
  With no ordering between the two reads on each observer, IRIW is permitted everywhere. Put an address
  dependency between them and the answer splits: a multi-copy-atomic model forbids the outcome, a model
  that is not multi-copy atomic permits it. Take that property from the Memory model of record. It
  cannot be inferred from the design, and "there is a shared last-level cache so it must be
  multi-copy atomic" has been wrong.
- **A read-modify-write pair carries an atomicity rule the cycle test does not express.** Check it
  explicitly; an acyclic graph does not clear an outcome that slipped another hart's write between the
  paired load and store.
- **A golden file grown by appending observed states can say "not yet seen", never "forbidden".** Ask
  which kind you are holding before treating an unlisted state as a bug.
- **The trace's own order is program order, not visibility order.** A retirement trace gives `po` for
  free and `co` almost never. Without a global timestamp, `co` is partially recovered at best — say so
  instead of filling it in.
- **An outcome the model permits but hardware has never shown is not a failure.** A test whose final
  condition is an existence claim, run a million times with no hit, has demonstrated nothing about the
  design; it is a stimulus problem, and it belongs in the coverage conversation rather than this one.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the `observed` line is copied **verbatim** from the outcome record, not paraphrased or reformatted
- every write to each shared location carries a distinct value — if not, the only honest answer is
  `adjudication: unadjudicable`
- the `cycle` field lists edges, each labelled `po`, `rf`, `co` or `fr`, and at least one `fr` edge is
  present in any store-buffering shape
- no internal store-to-load forwarding edge appears in the cycle
- every `po` edge in the cycle is one the Memory model of record actually preserves, quoted by rule
  name, and no `po` edge rests on a control dependency between two loads
- `rule` names a clause of the model of record, not a general principle someone remembers
- the golden file's model revision matches the Memory model of record slot
- the `coverage` line says how many harts were opened and whether `co` was fully recovered

A wrong answer typically declares an ordering violation from a graph missing its `fr` edges; treats a
predicted-branch load pair as ordered; adjudicates against a golden file that only ever accumulated
observed states; or names a store-buffer culprit before checking that the two writes in the test even
carried different values.

## Done when

You can say `allowed`, `forbidden` or `unadjudicable` for this one outcome, name the model rule or the
test defect behind it, and state how much of the execution you actually recovered.
