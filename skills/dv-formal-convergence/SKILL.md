---
name: dv-formal-convergence
description: Choose a convergence technique for a formal property that came back inconclusive or bounded, and write the plan down with the soundness caveat it creates, instead of launching another overnight run. Use when properties come back undetermined or proven only to a depth, when a proof ran all night and got three cycles deeper, when someone proposes black-boxing a block or shrinking a parameter and nobody can say what that does to the result, or when you need to state which properties are still not signed off and why.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Convergence Playbook for Inconclusive Proofs
  semiskill-function: design-verification
  semiskill-role: formal-verification
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-04-23
  semiskill-tags: formal, fpv, convergence, abstraction, assumptions, proof-depth, sva
---

# Convergence Playbook for Inconclusive Proofs

An inconclusive property is neither a pass nor a failure — it is a bill for compute that has not been
paid, and paying it again overnight almost never works. The engine did not stop because it was nearly
there; it stopped because the space it was asked to search grows faster than the clock does. The way
out is to change what the engine is asked to reason about, and **every one of those changes weakens
the result in a specific, nameable direction**. Getting that direction backwards is how a real
counterexample gets dismissed and an unsound proof gets signed.

The output is a per-property plan: one technique, the direction it moves soundness in, the caveat it
leaves behind, and an honest count of how many properties you actually planned.

**What this does not do.** It reads the formal report, the property source and the RTL as text on
disk. It cannot start the formal tool, cannot open a counterexample viewer, and cannot measure a
runtime. Every step needing one of those ends in a named handoff and says so.

## When to use something else

A property that came back with a **counterexample is not inconclusive** — that is a result, and
convergence work on it is wasted; debug the trace. A failing simulation log belongs to
`dv-sim-log-first-error`; a night of regression failures to `dv-regression-triage-routing`; shrinking
a failing simulation run to `dv-minimal-reproducer`. If the formal tool never got as far as a result
because the RTL or the bind file would not compile or elaborate, that is
`dv-build-filelist-hygiene` — the break is in the file set, not in the proof. A register-model
failure is `dv-ral-bringup`, and a repository you have never seen is `dv-repo-orientation`. Writing
the properties in the first place, and formal coverage sign-off, are both outside this skill.

Two formal siblings sit either side of this one and share its result vocabulary. A packaged app —
connectivity, register, unreachability, post-ECO equivalence — is `dv-formal-apps`; a proof that
converged suspiciously fast because the constraint set was too tight is
`dv-formal-overconstraint-credit`. All three write the registered `proof status` field with the same
spellings, so a convergence plan, an app report and an overconstraint audit sort into one column
rather than three vocabularies. Route to them by name and paste the block across unchanged.

## Fill this in for our team

Two facts this procedure spends are pack-wide and live **once** in `_shared/team-profile.md`. They
are read from there and deliberately not re-asked below.

| Fact in `_shared/team-profile.md` | What this skill spends it on |
|---|---|
| **Filelist convention** | step 4 — the RTL under the property's cone is reached through the entry-point filelist the formal build reads, and that row says how ours nest and what a relative path resolves against. There is no RTL-location question here beyond it |
| **Sign-off** | steps 3 and 9 — who decides whether a bounded proof at depth k is enough, and on what evidence |

Nine facts are specific to a convergence decision, so they are asked here and nowhere else:

| Slot | What to fill in | Who knows |
|---|---|---|
| Formal report location | [[FILL: where our formal run's per-property result report lands, and whether it is a text file that can be read from disk]] | formal owner |
| Result vocabulary | [[FILL: the exact strings our tool prints for a full proof, a bounded proof, a counterexample, an undetermined result, a vacuous result and an unreachable cover]] | formal owner |
| Bound reporting | [[FILL: how our tool reports the depth a bounded proof reached, and whether that count starts at reset release or at time zero]] | formal owner |
| Property source | [[FILL: where our properties, assumptions and covers live in the tree, and whether they are bound in from a separate file or written inline]] | block formal owner |
| Complexity report | [[FILL: whether our tool writes a per-property cone or state-bit count we can read, and where]] | formal infra |
| Engine record | [[FILL: which proof engines or modes our tool exposes, how one is selected, and whether per-property engine progress is written where we can read it]] | formal infra |
| Abstraction record | [[FILL: which file a black box, a cut point, a parameter override or a symbolic constant is written into for us, and how it is reviewed]] | formal infra |
| Assumption register | [[FILL: where we record an assumption that is not yet discharged elsewhere, and who reviews that list]] | verification lead |
| Formal run identity | [[FILL: what identifies one formal run for us — property set, RTL build stamp, tool version, assumption set]] | formal owner |

Two of these look like pack-wide facts and are not. The profile's **Log location** covers simulation
and regression logs; a formal run writes its own per-property report, usually somewhere else, so
**Formal report location** is a different artifact and gets its own row — if your flow does put them
in one tree, record that in the profile and point this row at it. The profile's **Run identity** is
seed-and-test shaped, and a formal run has no seed; **Formal run identity** is therefore a different
fact, not a copy of it. **Result vocabulary is not the profile's Fatal markers** either: an
undetermined property prints nothing a failure marker would catch, which is exactly why these runs
get reported as clean.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented status string sends
every Grep in this procedure to the wrong lines and produces a plan for properties that do not exist.

## Retrieval budget — read this before opening anything

A formal report embeds full counterexample traces and can be enormous; a generated property file can
run to thousands of lines. Work in this order and stop when the budget is spent:

1. **Grep and Read work on files on disk.** If the result arrived pasted into the chat, ask for the
   report path under the Formal report location slot. Until a path exists you may reason over the
   pasted lines by eye, but say that is what you did — you have not searched the report.
2. **Never open the report with Read first.** Glob to find it, Grep to locate the status lines, then
   Read a bounded window.
3. The whole budget is **3 Globs** — the report (step 1), the property source (step 2, reused by
   step 5) and the formal build's entry-point filelist (step 4); **4 Greps** — the Result vocabulary
   strings in the report (step 1), the assertion and cover labels in the property source (step 2),
   the hard-structure names across the RTL directories the filelist named (step 4), and that one
   property's label and its assumption set (step 5); and **6 windowed Reads** — about 80 lines at the
   report's status table (step 3), about 40 in the complexity or engine record and about 30 at the
   filelist entry point (step 4), about 40 at the property text and about 40 at its assumptions
   (step 5), and one spare 40-line window wherever the technique choice lands (step 6). Steps 7 to 9
   reuse those windows and open nothing.
   **Every Glob is scoped to one directory.** A recursive pattern from the repository root returns
   tens of thousands of paths and spends the budget before step 1 has a report.
4. If the step 1 Grep returns more than about 200 status lines, do not plan them one at a time. Rank
   first (step 4), plan the top three, give the rest `proof status: not-read`, and say in `coverage`
   how many that was.
5. Stopping rule: once the budget is spent with properties still unplanned, stop and report what is
   known, the one thing you still need, and the count from step 9. Past that, techniques get chosen
   from the shape of the name rather than from the design.
6. State what you actually covered. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the result to a file, and split "inconclusive" into what it actually is

**Glob** under the Formal report location for the report, then one **Grep** alternating the Result
vocabulary strings. Five distinct outcomes get lumped together as inconclusive and only one of them
is actually nothing:

- **Bounded proof to depth k** (`bounded`) — real evidence. No counterexample exists within k cycles.
  Coverage you already own, and step 3 decides whether it is enough.
- **Undetermined** (`inconclusive`) — the engine made no usable claim. There is no k to quote.
- **Vacuous or trivially proven** (`vacuous`) — it converged and proved nothing.
- **Unreachable cover, or a dead property** (`proven`, of unreachability) — the thing you asked about
  cannot happen. That is a finding about the environment, not a convergence problem.
- **Error** (no token, because there is no row) — the property did not elaborate and never ran, so
  step 2 is the only place it can be noticed.

Build a table of property, status string verbatim, and depth, and carry both the verbatim string and
the token it normalises to. Do not paraphrase the status; these strings are compared exactly by
everyone downstream, and step 9 asks for the string and the token side by side.

### 2. Count what ran against what was written

**Glob** the **Property source** first — this is the step that locates it, and steps 5 and 6 reuse
what it finds rather than spending a second one. Then one **Grep** across it for the assertion and
cover labels, compared against the count of status lines from step 1. If the slot says the properties
are bound in from a separate file, that Glob's pattern has to cover the bind file as well — a bind
file the run never read produces a report with no rows and no complaint about it.

**A property that did not elaborate has no line in the report at all** — no
status, no warning, nothing — so a report is only complete relative to a count taken from the source.
While that Grep result is in front of you, check for an `assume` written where an `assert` was meant:
it constrains the environment instead of checking anything, and it never appears as a failing check.

### 3. Read the bound before buying more compute

Spend the 80-line **Read** at the status table and take each bounded property's depth. The **Bound
reporting** slot decides how to read it: if the count starts at time zero and reset takes thirty
cycles, a bounded proof at depth 42 covers twelve cycles of operating behaviour, not 42.

Then compare k against the deepest sequential distance that can affect this property — reset length,
plus pipeline latency, plus the deepest queue that can hold the transaction the property is about. If
k already exceeds it, you may have enough. Be exact about what that is: it is a **written argument
that the interesting behaviour fits inside k**, not a proof, because nothing here bounds the design's
reachability diameter. It belongs in the plan as `discharge`, and whether it is acceptable is the
question the profile's **Sign-off** row names an owner for.

### 4. Rank by what is expensive, not by what ran longest

If the **Complexity report** or the **Engine record** slot says a per-property cone, state-bit count
or engine-progress file exists, spend the 40-line **Read** there. Two numbers matter: state bits in
the cone, and depth gained per hour. A run that reached depth 40 in the first hour and 43 in the
eighth will reach about 45 overnight — that property does not need more clock, it needs a smaller
model.

Then find the RTL before searching it — guessing a directory is how a Grep comes back empty and gets
read as "no hard structures here". **Glob** the entry-point filelist the formal build reads (the
profile's **Filelist convention** row says how ours nest and what a relative path resolves against)
and spend the 30-line **Read** on it to turn it into a short list of source directories. If that row
is unfilled, or the filelist is generated where this procedure cannot see it, ask the engineer for the
source directories the run compiled rather than substituting a repository-wide search.

Then one **Grep**, scoped to those directories, for the structures that reliably do not converge: a
multiply or divide on a wide vector, and the names `crc`, `lfsr`, `scramble`, `ecc`, `syndrome`,
`galois`. Anchor the pattern to those words rather than to the operator alone; a bare
arithmetic-operator search returns thousands of hits and tells you nothing. Hits outside the
property's own signal paths are noise — the tool already pruned that logic out of the cone.

If neither file exists, say the ranking is by property shape only, and ask the engineer to send the
cone or state-count report the tool can produce — that is a handoff, and the ranking stays provisional
until it comes back.

### 5. Read the property before abstracting anything

Work inside the **Property source** step 2 already located — no fourth Glob. **Grep** the one
property's label to get line numbers, then two 40-line **Read** windows: the property text, and the
assumption set that applies to it. Look for:

- an unbounded range (`##[1:$]`), `s_eventually`, or a strong operator — a liveness obligation
- a `disable iff` condition that is true most of the time, which makes a proof nearly empty
- an antecedent that needs a sequence the environment forbids — the vacuity shape
- `$past` with a large offset, which adds that many registers of state to the cone
- a wide equality over data, which drags the entire data path into the cone

### 6. Choose one technique per property

Every cell in the right-hand column is one of the `technique` tokens step 9's block accepts, spelled
the way the block spells it, and every one of them is named by a soundness row in step 7. Nothing
else may be written into that field — if the property matches no row, write `none` and say what you
could not classify. The two tables and the block's enum are a matched set: if you find a technique on
one and not the others, the skill is broken and the plan is not safe to sign.

| What the report and the property say | `complexity` | First `technique` |
|---|---|---|
| Depth climbs steadily but slowly, memory flat | sequential-depth | bound-the-property (counter-abstraction next iteration) |
| Depth stalls low within minutes, memory climbing | state-space | blackbox (data-abstraction next iteration) |
| A wide equality over data appears in the property | state-space | symbolic-constant |
| A multiplier, CRC, LFSR, scrambler or ECC block is in the cone | state-space | blackbox — only if the property does not check its value |
| A large array or deep queue is in the cone | state-space | symbolic-constant on one entry, **not** a blackbox |
| The claim is about control — a handshake, an ordering, an arbiter — and the wide data path is only carried through it, never inspected | state-space | data-abstraction |
| A structural parameter — queue depth, channel count, number of ports — sets the state size, and the claim is the same shape at every legal value of it | state-space | parameter-shrink |
| A wide free-running counter or timer gates the interesting event | sequential-depth | counter-abstraction |
| Liveness, or an unbounded range in the property | property-shape | bound-the-property |
| One opcode, port or burst type dominates the space | state-space | case-split |
| One big claim that only holds because of a smaller invariant | state-space | helper-lemma |
| Reset takes tens of cycles and the bound counts from time zero, so most of k is spent getting out of reset | sequential-depth | start-state |
| The engine is spending the space on input traffic the real environment can never send | environment | constrain-environment |
| Everything converged the moment an assumption was added | environment | none — go back to step 5 and check vacuity |
| One engine ran the whole time, or never got past setup | unknown | engine-change |

Two of those tokens need saying rather than assuming. **start-state** begins the proof from a
supplied post-reset state instead of from time zero, so the whole of k buys operating behaviour; ask
the engineer whether your tool takes one and how it is produced, because that is tool-specific.
**constrain-environment** adds an input assumption that rules the illegal traffic out — the cheapest
technique here and the easiest to get silently wrong, which is why step 8 sends every assumption it
creates to the **Assumption register**.

The spare 40-line **Read** goes wherever the chosen row points — the counter declaration, the array,
or the parameter. One technique per property per iteration: two changes at once and you cannot say
which one moved the result.

### 7. The soundness ledger — the part that has to be exactly right

Every `technique` token step 6 can produce has a row here, and every row names one — the twelve
tokens against thirteen rows, because `helper-lemma` is the one technique whose soundness depends on
something you control. Its qualifier, like the qualifiers on the other rows, is in the first cell,
and the plan has to say which of the two the property is on.

| `technique` | `soundness` | Survives the change | What it can make wrong |
|---|---|---|---|
| blackbox | over-approximation | a proof | counterexamples may be spurious |
| counter-abstraction, terminal count left free | over-approximation | a proof | the event fires at impossible times, so counterexamples may be spurious |
| constrain-environment | under-approximation | a counterexample | the proof holds only if the constraint is true, and may be vacuous |
| start-state, from a state the reset sequence provably reaches | under-approximation | a counterexample | any reachable post-reset state you left out is now unverified, silently |
| helper-lemma, assumed and separately proven | equivalence-preserving | both | nothing, if the lemma is proven unbounded and without circularity |
| helper-lemma, assumed and not yet proven | under-approximation | a counterexample | the parent proof is worth exactly what the lemma is worth |
| case-split with a proven-exhaustive guard set | equivalence-preserving | both | nothing; an unproven guard set leaves a silent hole |
| symbolic-constant over a value the property quantifies | equivalence-preserving | both | wrong if behaviour for that value depends on traffic you also constrained away |
| bound-the-property | stronger-property | a proof implies the original | a counterexample need not be one for the original claim |
| data-abstraction, narrower data | different-design | nothing automatically | the result is about the narrow design until a data-independence argument is written |
| parameter-shrink | different-design | nothing automatically | the result is about the shrunken design, and the carry-over argument is human |
| engine-change | equivalence-preserving | both | nothing — the only free move that still changes the run |
| none | equivalence-preserving | both, unchanged | nothing was changed, so nothing moved — the row exists so a property step 6 sends backwards is still a fillable block rather than a gap |

Two lines carry most of the value. **Removing logic keeps proofs and endangers counterexamples**;
**adding constraints keeps counterexamples and endangers proofs.** So `soundness: over-approximation`
means chase every counterexample before believing it, and `soundness: under-approximation` means
chase the proof, not the trace. `soundness: different-design` means neither result transfers on its
own, and a plan that leaves that row's argument unwritten has produced a number about a design nobody
is shipping.

### 8. Case splits and helper lemmas without leaving a hole

A case split is only a split if the guards cover everything. Write the disjunction of the guards as an
**assertion that is proven, never assumed**, on the same model — half the splits filed as complete
skip this, and the uncovered case is invisible because no property mentions it. Split on a guard that
is stable across the property's whole window; one that changes mid-check splits nothing.

Layer helper lemmas strictly. While proving lemma L, never assume anything whose own proof assumes L;
some tools detect that circularity and some do not, so confirm which yours does with the formal owner
rather than relying on it. And carry the weakest link forward: a helper proven only to depth k makes
every property that assumes it bounded by k, whatever the parent's own line in the report says.

Every assumption you add goes in the **Assumption register** with an owner and one of three
discharges — proven here, asserted on the neighbouring block by its owner, or accepted as debt with
sign-off's agreement. An assumption with no discharge is a proof with a hole in it.

### 9. Write the plan and hand back what needs the tool

One block per property, written into the file the **Abstraction record** slot names:

```
property      : <the assertion label, exactly as the report spells it>
proof status  : proven | falsified | bounded | inconclusive | vacuous | not-read
status string : <the report's own words for this property, verbatim, plus the depth if it carries one>
bound         : <depth reached, and whether that count starts at reset release or at time zero>
complexity    : state-space | sequential-depth | property-shape | environment | unknown
technique     : blackbox | data-abstraction | symbolic-constant | counter-abstraction | parameter-shrink | case-split | helper-lemma | bound-the-property | constrain-environment | start-state | engine-change | none
soundness     : over-approximation | under-approximation | equivalence-preserving | stronger-property | different-design
caveat        : <the step 7 ledger's last column for this technique, in its own words>
edit          : <the exact change and the file it belongs in>
discharge     : <what must be proven elsewhere before this counts, and where that debt is recorded>
run id        : <whatever identifies this formal run for us>
report        : <path, and the line range worth reading>
coverage      : <n of m inconclusive properties given a technique; what the rest are and why not opened>
notes         : <anything the next person would otherwise rediscover>
```

`proof status` is the pack's registered formal-result field — name, spellings and all six tokens
taken from `_shared/handoff-vocabulary.md` unchanged, so a row written here counts beside one from a
sibling formal skill instead of needing a translation table. The full set is emitted rather than a
subset, and every token is reachable: `bounded`, `inconclusive`, `vacuous` and the unreachable
cover's `proven` are four of step 1's outcomes; `not-read` is the honest token for a property the
budget's rule 4 ranked and never opened; and `proven` and `falsified` are what the *re-read* produces
after the engineer has applied an `edit` and rerun — which is the moment `caveat` earns its keep,
because a `falsified` result under `soundness: over-approximation` may be spurious. Step 1's fifth
outcome has no token on purpose: a property that never elaborated has no report row, so it gets no
block here — it is step 2's count gap and it belongs to `dv-build-filelist-hygiene`.

`status string` is not optional beside the token, because normalising is lossy: the depth, the engine
name and whatever qualifier the tool attaches survive only there. The token is read off the string;
never write the string from the token.

`run id`, `report`, `coverage` and `notes` are the field names the rest of the pack uses, so a formal
result reads beside a simulation one. There is deliberately **no `signature` field**: the shared
schema in `_shared/failure-signature-schema.md` normalises a message, and an undetermined property has
no message to normalise. Do not manufacture one.

Then state the handoffs rather than implying them: ask the engineer to apply one `edit`, rerun that
property, and give you the path to the new report; ask for the cone or state-count file if step 4 went
without it; ask the neighbouring block's owner to assert what you assumed; and ask whoever the
profile's **Sign-off** row names whether a bounded proof at depth k with the step 3 argument is
acceptable.

## Gotchas

- **A bounded proof is evidence; undetermined is not.** They look equally grey in a summary table, and
  conflating them either throws away coverage you own or claims coverage you do not.
- **The bound may include reset.** Thirty cycles of reset out of a depth of 42 leaves twelve cycles of
  operating behaviour. Fill the Bound reporting slot before quoting a depth to anyone.
- **More wall clock buys almost nothing.** The search grows roughly exponentially with the state bits
  in the cone, so depth-per-hour, not hours elapsed, is the number that says whether waiting helps.
- **Black-boxing outside the cone changes nothing.** The tool already pruned it. Every real win is
  inside the cone, on logic that feeds data the property never checks.
- **Never black-box what the property is about.** Cutting the array out of a data-integrity property
  makes the read data free, so the property becomes unprovable rather than easier. That case wants one
  symbolic entry, not a cut.
- **Converging the moment an assumption is added is a suspect, not a success.** Check that the
  antecedent is still reachable with a cover, and that the assumption set is consistent — an
  inconsistent set proves every property in the file instantly and prints nothing unusual.
- **`assume` where `assert` was meant is silent.** Two characters, and a whole block of logic is
  unverified while the report stays clean.
- **A `disable iff` that is true most of the time is a proof of almost nothing**, and so is a property
  whose antecedent needs a sequence the environment forbids. Both report as proven.
- **Liveness without fairness produces trace-shaped nonsense.** The counterexample is a loop in which
  something is starved forever by an environment that would never do it. Bound the property instead of
  arguing with the trace.
- **A cached proof can outlive the RTL it was about.** If the flow reuses previous results, compare
  the design stamp in the report header against the build the RTL is at now. A stale proven is the
  most expensive green available here.

## Human verification — what a wrong answer looks like

Before acting on the plan, check:

- `status string` carries the report's own words **verbatim**, with its depth, not a paraphrase, and
  `proof status` was read off that string rather than the other way round
- every `technique` value is one of the tokens step 6's right-hand column produces. A technique that
  is not on that table, or is on it but has no row in step 7's ledger, is the failure this step
  exists to catch — the two tables are a matched pair and drift between them is invisible in review
- every technique carries a `soundness` value, and it matches the step 7 ledger — a `blackbox` written
  as `soundness: under-approximation` is backwards, and backwards here is what gets a real
  counterexample dismissed. `constrain-environment` and `start-state` both restrict the model and are
  therefore `soundness: under-approximation`; writing either as over-approximation inverts which of
  the two results you are allowed to trust
- no proof rests on an assumption absent from the Assumption register, with an owner and a discharge
- any bounded result quoted as sufficient names the depth argument from step 3 as an argument
- a `case-split` names the guard set and says whether its exhaustiveness was proven or only asserted
- the `coverage` line says how many of the inconclusive properties actually got a plan
- nothing in the plan is written as though the agent had run the tool

A wrong answer typically says "raise the effort and rerun" with no technique behind it; black-boxes
the block the property is about; splits cases whose guards were never shown exhaustive; or quotes a
proven property that was disabled, vacuous, or never elaborated at all.

## Done when

Each inconclusive property has one technique, one soundness direction, one written caveat and one
named discharge — and the count of the ones that do not is stated.
