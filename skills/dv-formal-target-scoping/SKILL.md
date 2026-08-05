---
name: dv-formal-target-scoping
description: Rank candidate blocks by formal amenability from the RTL and the spec, then give each target a claim type, a depth bound and an effort estimate that carries its own assumptions and its own stopping point. Use when someone asks which blocks to attack with formal this quarter, when a formal plan has to survive a planning review, when you are asked for a day count before a single property exists, or when a proof has been running for three weeks and nobody ever wrote down what would make it stop.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Formal Target Selection, Claim Type and Effort Scoping
  semiskill-function: design-verification
  semiskill-role: formal-verification
  semiskill-level: senior-staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-03-16
  semiskill-tags: formal, model-checking, planning, scoping, abstraction, effort-estimation
---

# Formal Target Selection, Claim Type and Effort Scoping

Formal plans fail in the same two places every time. A block that looked easy turns out to hold a
memory, a timeout counter or a black-boxed macro that nobody counted before the estimate was given;
and the estimate itself was one number with no capacity assumption behind it and no point at which
anyone was permitted to stop. This ranks candidates from what is actually written in the RTL, gives
each one a claim it can plausibly reach, and produces an effort figure carrying its assumptions and
its abandon criterion in the same block.

**What this does not do.** It reads RTL and specification text already on disk. It does not write
properties, constraints or abstractions, cannot start a model checker, cannot open a proof database,
a coverage database or a waveform, and cannot measure a real bound. Every step needing an engine ends
in a handoff to a named person, and says so.

## When to use something else

`dv-formal-apps` is the closest neighbour and the two are easy to confuse: it *runs and reads* the
packaged apps once a target exists, while this decides which targets are worth having. Anything
leaving here as `claim: connectivity`, `claim: unreachability` or `claim: equivalence` is handed
straight to it. If you cannot yet say which file holds which block, do `dv-repo-orientation` first —
its repo map is what step 1 consumes, and without it step 1 spends the whole **Glob** budget guessing.
A filelist that will not expand — including one step 1 could not finish inside its single window — is
`dv-build-filelist-hygiene`; an asynchronous crossing that is itself the thing to be checked is
`dv-cdc-rdc-triage`, not a formal target; one failing simulation log is `dv-sim-log-first-error`; a
night of them is `dv-regression-triage-routing`; a register-access failure is `dv-ral-bringup`;
shrinking a signed failure is `dv-minimal-reproducer`. Writing the properties, constraints and
abstractions themselves is nobody's job here — this stops at the scoping record.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Candidate list | [[FILL: where the list of blocks being considered for formal lives, and whether it is a file that can be read or a plan a person holds in their head]] | verification lead |
| RTL root | [[FILL: which directories hold the RTL for these units, and which hold generated or third-party code we must not rank]] | your mentor |
| Black-box policy | [[FILL: which memory compilers, hard macros and bought-in IP we always black-box, the name prefixes they instantiate under, and where a behavioural model lives when we do not]] | DV infra |
| Assertion IP | [[FILL: which protocol assertion or checker sets we are licensed for, and the exact interface port-name families each one expects to bind to]] | DV infra |
| Reference model | [[FILL: whether an architectural or algorithmic reference model exists for any candidate, and whether that model is a file that can be read]] | architecture owner |
| Coverage-hole source | [[FILL: where our unreachability requests come from, and whether that source can be read from disk]] | coverage owner |
| Model checker and capacity | [[FILL: which model checker we use, which engines the team actually runs, and the machine size, memory and licence count one proof job gets]] | formal lead |
| Bound convention | [[FILL: what proof depth we accept as a useful bounded result for this class of block, and what we require recorded when a proof does not converge]] | formal lead |
| Effort unit | [[FILL: how our plans express effort — engineer-days, points, or a size band — and what one unit assumes about tool turnaround]] | verification lead |
| Effort history | [[FILL: what our last few closed formal efforts actually cost per term, where that is written down, and who holds it if it was never written down]] | verification lead |

Pack-wide facts live in `_shared/team-profile.md` and are read there, not re-asked: **Filelist
convention** tells step 1 how a relative path resolves, **Area to owner map** fills the record's
`owner` line, and **Sign-off** says what evidence a claim must reach — step 8 sizes the review term
against it. One profile fact is deliberately *not* consumed: **Run identity**. Nothing here starts a
run, so there is no seed, test name or build tag to report, and step 9 records the source revision the
counts were read at instead — under its own field name, for the reason given there.

Two slots above are deliberately *not* the profile rows of similar name, and merging them produces a
confidently wrong plan. **Model checker and capacity** is not the profile's **Simulator**: these are
different tools with different capacity limits, and a team commonly has one and not the other.
**Reference model** is not the profile's **Register model source**: a register model is generated from
a register description and says nothing about arithmetic behaviour, which is the only thing an
equivalence claim can use.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented machine size or effort
unit becomes a committed date, and unpicking a committed date costs more than having no estimate.

## Retrieval budget — read this before opening anything

An RTL tree holds thousands of files and one generated block can be a hundred thousand lines. Ranking
is counting, not reading: **Grep** for counts across many files, **Read** only the windows that decide
a claim.

1. **Grep, Read and Glob work on files on disk.** A candidate list that arrived as a chat message
   cannot be searched. Resolve it to paths under the RTL root first, or say plainly that you ranked
   only the names you were handed and mark the whole ranking provisional.
2. **At most 3 Glob calls** — the candidate list, the filelist or RTL root, and one spare for the
   specification directory in step 6. **Glob** returns paths only; getting a name *out of* a file is
   a **Read** and is budgeted as one below.
3. **At most 8 Grep calls**: one in step 2 for module headers, six in step 3 for the six metrics, one
   in step 5 for interface port names. Each runs once across the whole candidate set, never once per
   block — a per-block sweep blows the budget at the fourth block for identical counts. Only the step 2
   call takes trailing context, about 40 lines; that context is what buys the port-count band without
   spending a **Read**, and it is the reason the band is a floor rather than a total.
4. **At most 8 windowed Read calls of about 60 lines**, and no step outside this list opens a file:
   - up to **2 in step 1** — one on the candidate list where that slot resolves to a file, one on a
     filelist that has to be expanded to name the units;
   - **6 in step 6**, two apiece on the top three targets.
   Steps 2, 3 and 5 spend **Grep** only; steps 4, 7, 8 and 9 spend nothing at all.
5. A **Grep** returning more than about 300 hits is matching comments or wildcards rather than logic.
   Narrow it before counting, and never turn a noisy count into a rank.
6. Stopping rule: when the budget is spent and the top three are not separated, stop. Report the
   ranking you have, say which units were ranked from counts alone, and name the one measurement that
   would separate them. Past that the ranks are invented. The same rule binds step 1: a candidate
   list or filelist that does not fit its one window is expanded as far as the window reaches and no
   further.
7. State coverage in the record — `a of b` candidates swept, and which were ranked from the module
   header only. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the candidate set to paths, and drop what must not be ranked

Take the **Candidate list** slot. If it resolves to a file, **Glob** for the path and spend the first
of step 1's two **Read** windows on it — about 60 lines, which is where the unit names come from;
**Glob** cannot return a file's contents. If the list runs past that window, rank the names inside it
and put the shortfall in `coverage`. If it is a plan somebody holds, ask for the names and record that
the list came from a person. Then **Glob** the **RTL root** and discard whatever that slot marks as
generated or third-party — ranking generated code spends the budget on a unit nobody may change.

Where a candidate is named by filelist rather than directory, spend step 1's second **Read** window on
that filelist and expand it under the profile's **Filelist convention**, so you know whether a relative
path resolves against the invocation directory or the filelist's own. Backwards, that silently yields
an empty candidate set, which reads exactly like "no RTL found". One window expands one filelist: a
filelist that nests further filelists, or runs past 60 lines, is not chased here — take the units the
window names, mark the rest unresolved in `coverage`, and send the expansion itself to
`dv-build-filelist-hygiene`.

### 2. Fix each unit's boundary before measuring anything

One **Grep** for every candidate's module header at once — alternate the unit names in a single
pattern anchored on the `module` keyword. That gives a path and line per unit, and it is the boundary
every count in step 3 is scoped to. A unit whose header is not found cannot be ranked; list it as
unresolved rather than scoring it zero.

Run that one **Grep** with trailing context — about 40 lines after each match — so the head of each
port list comes back with the header and no **Read** is spent. What context lines give you is a band,
not a number: a port list that ends inside the context, and one still running when the context does.
Record the second case as "over 40 ports" rather than a count, because it is a floor, not a total. That
floor is the finding — a unit whose port list outruns 40 lines of context is an integration wrapper,
and its properties will be connectivity checks, not behavioural proofs.

### 3. Sweep the six amenability metrics — one Grep each, counts only

Six **Grep** calls, each once across the candidate files, each recording a hit count per file. Do not
read the hits; the counts are the ranking evidence.

| # | What to Grep for | A high count means | Known noise |
|---|---|---|---|
| 1 | an unpacked array declaration — closing bracket, identifier, opening bracket | stored data state: memories, register files, payload arrays | packed multi-dimensional vectors match and are not memories |
| 2 | the `*`, `/` and `%` operators with surrounding spaces, plus `mult`, `div`, `sqrt`, `recip` | wide arithmetic in the datapath | `*` also matches comment openers and wildcard sensitivity lists |
| 3 | `typedef` with `enum`, and the `case` keyword before an opening parenthesis | control-state density: the good kind of state | a `case` over an opcode is a decoder, not a state machine |
| 4 | `parameter` and `localparam` names carrying DEPTH, WIDTH, CNT, TIMEOUT, MAX or LIMIT | the sequential horizon — how deep a trace must go to reach anything | width and depth parameters look identical; only the name separates them |
| 5 | `posedge` and `negedge`, and `always_ff` blocks | how many clock domains, and how much state has no reset term | a generated file repeats the same edge hundreds of times |
| 6 | instantiation lines — identifier, instance name, opening parenthesis | child modules, and therefore black-box candidates | method and task calls share the shape; treat it as an upper bound |

Metric 6 earns its place through a comparison, not its count: any module name instantiated here that
did **not** appear in step 2's headers, or whose prefix appears in the **Black-box policy** slot, is a
black box. Black boxes are the commonest reason an "easy" block is not easy.

### 4. Rank by the worst blocker, never by an average

No new **Grep**, no **Read** — this spends only step 3's counts. Amenability is limited by the worst
attribute in the property's cone, so averaging six metrics is how a block with one fatal multiplier
outranks a clean control block. Give each unit the *worst* blocker it carries, and rank in this order:

1. **none** — control-dominated, small stored state, interfaces you have checkers for. The cheap wins,
   and they belong at the top of every first-quarter plan.
2. **environment** — the design is fine, the setup is missing: unconstrained black boxes, state with
   no reset term, or an asynchronous crossing in the cone. Bounded, one-time work that converts it to
   **none**. For the crossing that word "converts" is narrow and people read it too widely: what
   converts is the *rest* of the cone, once the crossing itself has been routed to a structural
   clock-domain tool via `dv-cdc-rdc-triage` and replaced by a single-clock abstraction plus a few
   targeted properties. The crossing is never proved by the general behavioural run, so a unit whose
   claim is *about* the crossing is not an `environment` fix at all — it leaves this ranking.
3. **data-state** — memories, register files or deep payload storage dominate. Known abstractions
   apply, and the control half is usually provable in full while the data half is not.
4. **horizon** — a counter, timer or FIFO depth puts the interesting event further out than any bound
   reaches. Abstraction recovers it, but the proof is then about a modified design and that is an
   assumption to record.
5. **arithmetic** — a wide multiplier, divider or similar sits in the cone. A specialist effort with
   its own engine strategy, not a normal plan item.
6. **spec-missing** — nothing written down to turn into a property. Checked first as a gate:
   tractability is irrelevant when there is no statement to prove.

Record the worst blocker on the `blocker` line and every other one in `notes`. A unit carrying three
blockers and a unit carrying one are not the same risk even when the worst is identical.

### 5. Check the cheap wins are actually cheap

One **Grep** across the top three targets only, for the interface port-name families the **Assertion
IP** slot records. A hit means an existing checker set may bind and the property term collapses —
the largest single saving available in this exercise.

Two traps. A port list that *looks* like a standard protocol but deviates in a handful of signals
costs more than authoring from scratch, because the deviations surface one failed bind at a time. And
where the **Assertion IP** slot is unfilled, a generic search for handshake-shaped names tells you a
handshake exists and nothing about conformance — say so, and do not let it reduce the estimate.

### 6. Read only what decides a claim

Up to six windowed **Read** calls of about 60 lines, two apiece on the top three targets: one at the
module header and port list, one at the widest state declaration metric 1 or metric 4 pointed to.

What you want is narrow. At the header: how many clocks and resets arrive, whether the reset is
synchronous, and whether the port list is a protocol or a bag of signals. At the state declaration:
the actual numbers behind a parameter name, because `DEPTH` of 4 and `DEPTH` of 4096 separate a
`claim: full-proof` from a `claim: bounded-proof`. The spare **Glob** from budget rule 2 finds a
specification if one is on disk — but reading one costs a window, and there is no ninth. Where a
target's claim turns on a written statement rather than on a parameter value, spend that target's
*second* window on the specification instead of the state declaration and say in `notes` that the
state declaration was never opened. A spec that is a slide deck, a spreadsheet or a page **Read**
cannot open leaves the target `spec-missing` until a person supplies the statements, and any claim
resting on it is provisional.

### 7. Assign a claim type, and a bound to go with it

The claim is what you will actually be able to say at the end, chosen from the blocker rather than
from ambition.

| Blocker and shape | Claim | What it commits you to |
|---|---|---|
| none, control block with a checkable interface | `full-proof` | every property converges unbounded, or the plan was wrong |
| none, integration wrapper with a large port count | `connectivity` | pin-to-pin and register-decode checks only: cheap, wide, shallow |
| environment, once the setup work is planned | `full-proof` | the setup term in step 8 is not optional and is usually underestimated |
| data-state | `full-proof` on the control half, plus a separate target for data | two records, not one — different claims, different effort |
| horizon | `bounded-proof` | a stated depth, and the reason that depth is enough |
| arithmetic, with a readable reference model | `equivalence` | only where **Reference model** is filled and the model is on disk |
| arithmetic, without one | `bug-hunting` | success is bugs found, not proofs closed; say so in the plan |
| a hole from the **Coverage-hole source** | `unreachability` | needs a database the agent cannot open — always a handoff |
| spec-missing, or a size already past what the **Model checker and capacity** slot allows one job | `not-a-target` | hand it back to simulation with the blocker named |

Three blockers reach a claim at all only by changing what the engine reasons about, and the record has
to name the change. `abstraction: datapath` is the arithmetic one, and it is the value people leave
undefined: the wide operator is replaced by an uninterpreted one of the same width so the control
around it can be proved, and it proves nothing whatever about the arithmetic itself — which is exactly
why `bug-hunting`, not `full-proof`, sits opposite arithmetic with no reference model. `counter` and
`memory` are the same move against the horizon and data-state blockers. `black-box` belongs to
`environment`, where a child was left unmodelled, and `several` says more than one was needed. Every
one of them makes the proof a statement about a modified design, so every one belongs in `assumes`.

Then the bound, where bounded claims usually go wrong. Depth counts from the reset state, so the
design's own initialisation latency is subtracted before any useful cycle: a bound of N against a
k-cycle reset-to-ready sequence gives N minus k useful cycles, and a bound below k proves nothing at
all. A FIFO overflow cannot be witnessed in fewer cycles than it takes to fill the FIFO, so a depth
under its `DEPTH` parameter cannot see the event. A counter W bits wide incrementing once per cycle
wraps at 2^W cycles, which at W of 32 is no bound any engine reaches — that target is `horizon`, and
the honest options are a counter abstraction or a reduced terminal value recorded as a design change,
not a longer run. Write the needed depth against the **Bound convention** slot's accepted depth; where
it is not derivable from the source you read, write `?` rather than a round number.

The agent cannot measure a real bound, convergence or capacity. **Ask the formal engineer to start one
short bounded proof on the top target and give you the path to the tool's report**, then read the
reached depth from it. Until that path exists every bound here is a prediction from the RTL and is
labelled as one.

### 8. Build the effort estimate from five terms, not one

One number hides which term is uncertain. Quote all five in the **Effort unit** slot's unit, each as a
range:

- **setup** — harness, black-box handling, clock and reset modelling, first constraints. Roughly fixed
  per block, larger for `blocker: environment`, and paid once whatever the claim.
- **properties** — scales with interfaces and specification size, and collapses toward zero where step
  5 found a checker set that binds.
- **convergence** — the term with unbounded variance. It scales with the blocker class from step 4,
  not with property count, and it is the only term that can consume a quarter alone.
- **constraint validation** — cover properties and an over-constraint check. Never zero, routinely
  omitted, and the term that decides whether the proof means anything.
- **review** — sized against the profile's **Sign-off** row, because a claim nobody will accept as
  evidence is not finished.

The multipliers come from the **Effort history** slot — what the team's last few closed formal efforts
actually cost per term. This step opens nothing (budget rule 4), so however that history is stored,
**ask the person that slot names — the verification lead by default — for the per-term figures, and
quote them as given** alongside the efforts they came from. Where the slot is unfilled, or nobody wrote
the actuals down, say the estimate is uncalibrated rather than borrowing numbers from elsewhere — a
shape with an honest label beats a number with a false one.

Then write the **abandon criterion**, before the work starts: the point at which the claim is
downgraded rather than pursued. "If the control properties have not converged by the end of the setup
and property budget, downgrade to `claim: bounded-proof` at the **Bound convention** depth and
re-plan" is one sentence that saves a quarter. A plan without one produces the three-week proof nobody
can cancel.

### 9. Write the scoping record

One block per target, so two targets produce two blocks. It reuses `owner`, `evidence`, `coverage` and
`notes` from the sibling skills' blocks so a formal plan and a triage table read side by side.

It deliberately carries no `run id`, and that is not an oversight: `_shared/handoff-vocabulary.md`
locks that spelling to the profile's **Run identity** fact — seed, test name, configuration, build tag
— and this skill starts nothing, so it has no such identity to report. What it does have is the source
revision the counts were read at, which is a different question about a different object and therefore
gets its own name, `source revision`. Pasting a scoping block beside a triage block leaves the triage
column empty rather than filling it with a token that would not compare against anything in it.

```
target          : <unit name; the RTL path and line of its module header>
rank            : <n> of <m> ranked
blocker         : none | environment | data-state | horizon | arithmetic | spec-missing
evidence        : <the metric hit counts, and the path and line behind the blocker>
claim           : full-proof | bounded-proof | bug-hunting | equivalence | unreachability | connectivity | not-a-target
bound           : <depth the claim needs, and the reset-to-ready latency it is measured from; ? if not derivable>
abstraction     : none | memory | counter | datapath | black-box | several
effort          : <setup / properties / convergence / constraint-validation / review, each a range in our effort unit>
assumes         : <the capacity and licence count from Model checker and capacity, plus every parameter and reference-model assumption the effort rests on>
abandon         : <the point at which the claim is downgraded rather than pursued>
owner           : <the name from the profile's area-to-owner map, or blank plus candidates>
source revision : <whatever identifies the revision of the RTL and specification these counts were read at>
coverage        : <a of b candidates swept; which were ranked from the module header only; which were named by a partly-expanded list>
notes           : <the other blockers found, the windows not opened, and anything the next person would otherwise rediscover>
```

Anything not derivable from text on disk is `?`, never a guess. `bound`, `abstraction` and `assumes`
are what a reviewer checks first — a claim with no assumptions listed has not been scoped.

## Gotchas

- **Total flop count is the wrong metric and it is the one everybody uses.** What matters is the cone
  of influence of the specific property. A two-hundred-thousand-flop block is trivial for a property
  whose cone is three hundred flops; a two-thousand-flop block is hard the moment a wide counter sits
  in that cone. Rank pairs of unit and property family, never bare units.
- **Wide multipliers defeat the general engines.** Bit-level reasoning has no cheap structural
  shortcut through a large multiply, so a full behavioural proof of one is a specialist project with
  its own engine strategy. Equivalence between two multipliers of the *same* structure is routine;
  between different structures it is research-shaped. Never plan it as a normal item.
- **A deep counter sets the horizon, not the state count.** A watchdog with a 2^24 timeout puts the
  interesting event sixteen million cycles out. Abstracting the counter and reducing its terminal
  value both work, and both mean the proof is about a different design — record it in `assumes`, or
  sign-off is claiming something that was never proved.
- **A FIFO's control is provable and its data is not, and that is fine.** Pointers, flags and the
  overflow and underflow properties converge at the real depth. Data integrity is proved by tracking
  one symbolic item through, not by holding every entry. Proving a small depth and asserting it
  generalises is an assumption, not a proof.
- **Black-boxing is over-approximation and constraints are under-approximation; they fail in opposite
  directions.** A black box frees its outputs, so counterexamples may be impossible in the real design
  and each must be triaged against it. A constraint removes behaviour, so an over-constrained
  environment can prove anything. Pair every constraint with a cover property and plan the time, since
  an unchecked constraint set is the most expensive silent failure in formal.
- **A bounded proof that never reaches the interesting behaviour is worse than none**, because it gets
  reported as green. Subtract the reset-to-ready latency before believing a bound, and require a cover
  property that actually reaches the scenario the claim is about.
- **Uninitialised state is free state.** A flop with no reset term starts arbitrary, and the engine
  will produce a counterexample from a state the silicon cannot occupy. Metric 5's `always_ff` count
  exists for this — decide per block whether those flops get an initial-state constraint and put the
  decision in `assumes`.
- **More than one asynchronous clock changes the question.** A property proved under a single-clock
  abstraction says nothing about the crossing itself; crossings belong to a structural clock-domain
  tool plus a few targeted properties, and folding them into a general behavioural proof produces a
  setup nobody can debug. Read step 4 with that in mind: a crossing is `blocker: environment` for the
  *rest* of the cone only, and the crossing itself leaves this ranking rather than becoming a setup
  item somebody schedules.
- **Amenability and specifiability are separate axes and only one is in the RTL.** The most tractable
  block in the tree is worth nothing if no statement exists about what it should do — which is why
  `blocker: spec-missing` is a gate before the ranking rather than a rank within it.
- **Latches and combinational loops break assumptions several engines are built on**, and they hide
  inside small blocks scoring `blocker: none` on every metric above. If step 6's window shows a
  combinational always block with an incomplete assignment, the target is `blocker: environment` until
  somebody confirms the tool handles it.

## Human verification — what a wrong answer looks like

Before acting on the plan, check:

- every rank names **one** worst blocker with a path and line behind it, not a score
- nothing ranked `blocker: none` instantiates anything metric 6 could not resolve to a module header —
  an unnoticed black box is the classic false cheap win
- no `claim: full-proof` sits on a target whose cone holds a wide multiplier or an unabstracted counter
- every `claim: bounded-proof` states a depth **and** the reset-to-ready latency it was measured from,
  and the depth exceeds that latency
- `claim: equivalence` appears only where **Reference model** is filled and the model can be read
- the effort line has five terms and ranges, and `assumes` names the machine size and licence count
  from the **Model checker and capacity** slot plus every parameter reduction the figure depends on
- `abandon` is present and is a condition somebody could actually observe
- the `coverage` denominator is the number of candidates you were given, not the number you swept, and
  a candidate list or filelist that outran its one window is named there rather than passed off as a
  complete sweep
- the block carries a `source revision` and never a `run id` — a scoping record has no run in it, and
  filling a triage table's run column with a revision joins two different questions

A wrong answer typically averages six metrics into one amenability score, promises a full proof on a
block whose memory nobody counted, quotes one effort number with no capacity assumption, or gives a
bounded claim with no depth — which is a bug-hunting effort wearing a proof's label.

## Done when

Every candidate carries one blocker, one claim, a bound or a `?`, a five-term effort range with its
assumptions, and a written point at which the claim gets downgraded instead of pursued.
