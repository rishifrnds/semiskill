---
name: dv-config-space-coverage
description: Choose which of a configurable IP's legal parameter combinations to regress, derive the equivalence classes from where the RTL actually branches on each parameter, and write the coverage argument a release reviewer will accept. Use when the configuration space is far larger than the regression budget, when you have to justify the configurations you picked at a release or sign-off review, when a customer hits a bug in a configuration nobody ever ran, or when someone adds a parameter and asks whether last release's coverage argument still holds.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Configuration-Space Selection and the Coverage Argument for Configurable IP
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: principal
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-04-14
  semiskill-tags: configuration, parameters, coverage, pairwise, release-review, sign-off, ip
---

# Configuration-Space Selection and the Coverage Argument for Configurable IP

A configurable IP has more legal parameter combinations than the release schedule has hours, so the
question was never *how do I regress them all*. It is *which subset did I pick, why that one, and can
I defend it to whoever takes the escalation when a customer's configuration fails*. Most plans lose
that review not because the subset is bad but because nobody wrote down how big the space is, where
the axis values came from, or what was left out and who agreed to leave it.

The output is three things: **an axis table with the size of the legal space, a selected set with a
stated interaction depth, and a signed list of what is not covered**. Not a list of tests.

## When to use something else

This picks configurations and defends the choice; it does not debug one. For a single failing
configuration's log start with `dv-sim-log-first-error`; for a night of failures to sort and route,
`dv-regression-triage-routing`. Once a configuration-dependent failure is signed,
`dv-minimal-reproducer` bisects over exactly the axes step 3 enumerates — hand it the axis table
rather than making it rediscover one. An elaboration axis that breaks the build, or two configurations
colliding over includes and defines, is `dv-build-filelist-hygiene`. Configurability that lives in
registers software programs rather than in elaboration parameters produces register-access failures
and belongs to `dv-ral-bringup`. If you cannot yet say where the parameters, filelists and regression
lists live here, spend an hour in `dv-repo-orientation` first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Parameter source | [[FILL: the file declaring this IP's configurable parameters, and whether the customer-facing legal ranges are written there or only in the integration guide]] | IP owner |
| Legality rules | [[FILL: where the rules that make a combination illegal are recorded — parameter checks in the RTL, a configurator, or a table in the integration guide]] | IP owner |
| Config object | [[FILL: the testbench class or file holding one resolved configuration, and how a run records which configuration it actually used]] | block DV owner |
| Elaboration axes | [[FILL: which of our parameters force a rebuild when they change, and how a build is named so two configurations cannot overwrite each other]] | DV infra |
| Config covergroup | [[FILL: the file holding the covergroup that samples the configuration, if we have one, and that covergroup's name]] | block DV owner |
| Shipped configurations | [[FILL: the configurations customers actually took in the last two releases, and which ones the datasheet names]] | applications engineer |
| Regression tiers | [[FILL: which regression tiers we have, how often each runs, and how many builds each can afford]] | DV lead |
| Waiver record | [[FILL: where we record a configuration deliberately not regressed, and what a reviewer expects to see beside it]] | verification lead |

Three pack-wide facts used below are deliberately **not** re-asked: **Regression summary**, **Coverage
output** and **Sign-off**, all in `_shared/team-profile.md`. Two rows above resemble those and are not
the same fact. **Config covergroup** is the *source* defining how a configuration is sampled, while
**Coverage output** is where merged results land — confusing them means checking a percentage against
a model nobody read. **Regression tiers** is narrower than **Regression summary**: the profile records
where a per-test result summary lands and its format, while this row is a *budget*, how many builds
each tier can pay for, and that budget decides the selected set.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented legal range or list of
shipped configurations is wrong in the one direction that matters, and a reviewer who catches it stops
believing the rest of the document.

## Retrieval budget — read this before opening anything

RTL for a configurable IP runs to thousands of files, and a generated configuration header is
machine-written and enormous. Open a few narrow windows exactly where a parameter changes something.

1. **Grep, Read and Glob work on files on disk.** A configurator GUI, a spreadsheet of legal ranges, a
   PDF integration guide and a coverage viewer are none of them searchable here. Where a number comes
   from one of those, ask a person, record who supplied it, and mark every line resting on it
   *provisional*.
2. Budget for the whole procedure: **two Globs, ten Greps, five windowed Reads of about 60 lines
   each.** Never open the parameter source or a covergroup with Read as the first move.
3. Where it goes: step 1 takes one Glob and one Grep; step 3 one Grep per ranked axis, at most five;
   step 4 re-reads step 3's hits and spends nothing; step 5 is arithmetic over the table you already
   built; step 6 one Grep of the regression lists; step 7 one Glob and two Greps. That is nine,
   leaving **one Grep in reserve** for the single ambiguity that decides the ranking — step 3 says
   when to spend it, and it is the only step allowed to. Reads go one to the parameter declarations,
   at most two to breakpoints in step 3, one to the covergroup in step 7, and one to the Config
   object in step 6. That is five; there is no spare Read, so a step that wants a sixth stops instead.
4. More than about 150 hits for an axis name means it is a substring of something common — anchor it
   with a leading dot or a bracket before reading anything.
5. Stopping rule: when the ten Greps are gone and the axis list is still unsettled, stop. Report the
   axes you opened and the ones you did not, and mark the size of the space a **lower bound** rather
   than a count — a lower bound that says so is useful, a count that was a guess is not. Either way
   step 8's `coverage` line says how many axes you opened and how many claimed pairs you checked.

## Procedure

### 1. Take the axis list from the parameter declarations, not from the datasheet

**Glob** for the Parameter source, then **Grep** it in one call for `parameter` and `localparam`
declarations. Record each axis with its name, default, and any legal range written beside it.
`localparam` is not an axis — it cannot be overridden — but one derived from two parameters is the
best free hint in the file that those two interact, so keep the derivations; step 5 wants them.

Three mismatches surface between what the RTL declares and what the customer-facing document offers.
It may offer *fewer* knobs, because some parameters are internal-only; a *narrower* range, because the
sellable range is a product decision rather than a design limit; and a *recommended* value that is not
the RTL default — meaning the configuration everybody tests is not the configuration anybody ships.

The **Parameter source** slot says whether those customer-facing ranges are written beside the
declarations or only in the integration guide. If they are beside the declarations, the Grep you just
spent already has them and the comparison is free. If they live only in the integration guide, budget
rule 1 applies and there is nothing to Grep: **ask the IP owner for the three values — knob list,
range and recommended default — and record who supplied each.** They land on step 8's `datasheet`
line, marked provisional; an unanswered one is `?` there, never a number you reasoned out from the
RTL, because the whole point of the line is that the two documents disagree.

### 2. Split the axes by what they cost, before choosing anything

Every axis is one of two kinds, and that difference is the whole cost model. **Elaboration axes**
change the netlist, so each distinct value is a separate build; they multiply the build matrix, which
is the expensive number. **Run-time axes** are settled in the Config object after elaboration and
multiply runs inside one build, which is cheap by comparison. Write the size of the space as two
numbers, never one: *builds* × *runs per build*. An argument about "we cannot regress ten million
configurations" is almost always really an argument about eleven builds, and goes far better once that
is on the page.

A compile-time define is a third and worse case: global to the compilation unit, so it forces a
separate build *and* makes two instances of the IP at different settings impossible in one build. If
something in the Elaboration axes slot is a define rather than a parameter, say so — the build-matrix
naming and the collisions that follow belong to `dv-build-filelist-hygiene`. The agent cannot start a
build; where the plan needs a build matrix, **ask the engineer to create the builds and give you the
paths to the build area and its logs**.

### 3. Find the real equivalence classes — where the RTL branches on the parameter

This is what turns "which widths should we test" from taste into something derived. Rank the axes
first — widest legal range and most structural effect at the top — then **Grep** the RTL for each
ranked axis name, one Grep per axis and at most five, alternating the interesting shapes in a single
pattern rather than spending a Grep per shape:

- the name next to a relational operator — `> 1`, `>= 8`, `== 1`, `< `
- a `generate` or `genvar` bounded by it, or a conditional instantiation choosing between submodules
- `$clog2` of it, or a packed dimension declared from it
- the name appearing in a port connection at an instance

The ranking is done from the axis table alone and costs nothing, but it decides which five axes get a
Grep and which do not, so a tie at the cut line is expensive. That tie is what the budget's **one
reserve Grep** is held for, and this is the only step licensed to spend it: where two axes are
indistinguishable on legal range and you cannot tell from the table which is more structural, spend
the reserve on the one whose name you would guess appears next to `generate`, and let the hit count
break the tie. Spend it once. If you spend it, step 8's `coverage` line says the ranking rested on it.

Every comparison against a literal is a **breakpoint**. Values either side of one are structurally
different designs; values between two breakpoints are the same design with different numbers, so
testing three of them tests one thing three times. The derived class list per axis is therefore:
minimum legal, each breakpoint literal, the value immediately either side of each, and maximum legal —
nothing else, unless a person can name what else changes.

Two cautions. A `$clog2` breakpoint sits at a power of two, so depth 8 and depth 9 differ in pointer
width — three bits against four — while depth 9 and depth 15 do not, both needing four. That is a
class boundary no relational operator shows you, and it means the class you want either side of a
power of two is the power itself and the power plus one, not a round number nearby. A parameter used
only inside an assertion or a coverage bin changes what is checked, not what is built.
**Say which level you Grepped**: a breakpoint inside a submodule the parameter is passed down to is
invisible from the top-level declaration, so if you opened only the top level the class list is a lower
bound on the classes that exist, and the report must say so.

### 4. Reduce the cross product to the legal space, and keep the illegal part

Apply the Legality rules to the cross product of step 3's class lists, re-reading step 3's hits rather
than Grepping a second time. Write both numbers down — cross product and legal subset — with the
constraint that removed each difference. A reviewer shown only the legal number cannot tell whether the
constraints are real or convenient.

The illegal part is not waste. A combination the design does not support should be **refused at
elaboration**, so an integrator who tries it gets a build error rather than silicon that misbehaves.
Placement decides that: a check in module or generate scope fails the build, while the same text inside
an initial block does not complain until time zero of a run that already paid for a build. Note which
illegal combinations have such a check and which have nothing — the ones with nothing are a finding,
not a gap in your testing.

### 5. Specify the target set, then check the closure of the set you are handed

Check first whether there is anything to select. Compare step 4's legal count against what the
**Regression tiers** budget can pay for, in builds first since those are the scarce number. If the
whole legal space fits, take it whole and say so — a reduction argument you did not need is a
liability, because it invites a reviewer to argue about a covering array instead of about the design.

The defensible default is **pairwise**: every pair of values drawn from every pair of axes appears
together in at least one selected configuration. It collapses an unbounded space into a set whose size
is governed by the two largest axes rather than by the axis count, which is why it is the one selection
rule that survives a reviewer asking "why not one more". Know its floor: no pairwise set can be smaller
than the product of the two largest axes' class counts, because each configuration contributes exactly
one pair of values from those two axes. Quote that floor beside your set size — a set at the floor is
efficient, a set at four times the floor was built by hand and can probably be halved.

Extend to three-wise only for **named triples**, named from evidence rather than worry: axes whose
step-3 breakpoints landed in the *same* region of RTL are jointly deciding one piece of logic. Axes
that never meet in a source file do not need a triple. Then union in what no argument covers: every
entry in **Shipped configurations** at its exact values — a customer configuration is never covered by
an equivalence-class argument, because they report the bug against their exact numbers and "your width
is in the same class as one we ran" is not an answer; the RTL default, plus step 1's recommended value
if it differs; and each axis's minimum and maximum legal corner, where the arithmetic breaks.

**The agent must not claim to have constructed an optimal covering array.** Ask the engineer to
generate the array with whatever combinatorial tool the team has, or to hand over the proposed set.
What the agent can do — and what step 8 records — is *check closure* of a set it was given: walk the
axis pairs, mark each present or absent, report the absent ones. That check is bounded, so say how much
of it you did. "Checked closure for the four pairs involving the two ranked axes; the other twenty-four
pairs are unchecked" is a real result.

That closure check is also what decides step 8's `depth` token, and the decision belongs here rather
than in the report:

- **`enumerated`** — the legal count from step 4 fits the **Regression tiers** budget and every legal
  configuration is in the set. No interaction-depth argument was made, and claiming one would be
  weaker than the truth. Say the legal count and the budget it fits inside, so a reviewer can see the
  claim is arithmetic rather than a reduction.
- **`pairwise`** — the closure check found every pair present, and no triple is claimed.
- **`pairwise-plus-named-triples`** — as above, and the triples named from step 3 evidence close too.
  Name each triple with the RTL region that justifies it, or the token is `pairwise` with extra runs.
- **`ad-hoc`** — the set you were handed has no derivation you can trace back to steps 3 to 5:
  inherited from last release, assembled by hand, or arriving with axes the axis table does not
  contain. This is the token most sets deserve on a first pass, and writing it is the finding: list
  the absent pairs the closure check found, and let the reviewer decide whether to pay for the
  difference. Do not upgrade it to `pairwise` because the set looks thorough — the check either
  closed or it did not.

If the closure check was too partial to distinguish `pairwise` from `ad-hoc`, the answer is `ad-hoc`
plus the fraction you checked on the `coverage` line, not the better-sounding token.

### 6. State the window the claim holds over

A tier that runs every night and a tier that rotates configurations across nights make very different
claims, and that is where most arguments quietly fail. Take the **Regression tiers** budget, then
**Grep** the regression lists for step 5's configuration names. One Grep, two findings. Any
configuration named in the plan and present in no list is a claim with nothing behind it — delete it or
add it to a list. And the split between the always-on and rotating tiers fixes the window: closure
achieved by rotation is "pairwise complete over the last seven nights", never "pairwise complete", and
that window **resets** the moment an axis gains a value, a default changes, or the RTL adds a
breakpoint.

Cross-check the tiers against the profile's **Regression summary** for what actually ran rather than
what was scheduled. The always-on tier must also be deterministic in its configuration: randomise it
nightly and a configuration-dependent failure looks intermittent, then gets triaged as a seed problem
by someone who will never find it.

That determinism claim is checkable, and the **Config object** slot names where. Spend the last of the
five Reads on a 60-line window of that class or file, at the point the slot says a run records the
configuration it actually used. Three outcomes, and they are not equivalent. It records every axis, so
`run id` can carry the resolved configuration and a failing configuration is reproducible. It records
only the axes someone remembered to add, so the plan claims axes no log will ever name — list those
axes on the `notes` line, because they are the ones a customer escalation will not be able to pin down.
Or it records nothing, and every run-time axis in the argument rests on the constraint solver rather
than on evidence; that is a finding to raise before the review rather than during it.

### 7. Cross-check the coverage model against the claim you are making

**Glob** for the Config covergroup, then **Grep** it in one call for `coverpoint`, `cross`, `bins`,
`illegal_bins` and `ignore_bins`. Read one window where the crosses are declared, and check four things:

- one coverpoint per axis from step 1, with **explicit bins matching the step 3 classes**. A coverpoint
  on an integer with no bins declared falls back to automatic bins up to the tool's limit, spreading
  four legal values across dozens of empty buckets and reporting a meaningless low number.
- a cross for every pair the argument claims is closed. A claim with no cross behind it is untestable.
- `illegal_bins` on the combinations step 4 called illegal, so a bad configuration is an error rather
  than a silent gap.
- **every `ignore_bins` accounted for, by name.** This is the one that matters. `illegal_bins` errors
  when hit; `ignore_bins` removes the bin from the goal entirely, so an untested configuration can be
  taken out of the denominator and the reported percentage goes *up*. That is how a coverage argument
  becomes false while the number improves, and it is the first thing a good reviewer looks for.

The numbers themselves need a merged report the agent cannot produce. **Ask the engineer to merge the
regression's coverage, write a text report, and give you the path** — the profile's **Coverage output**
row says where ours land. Then one **Grep** of that report for the covergroup's name. If no path
arrives, say the model was checked and the numbers were not.

### 8. Write the coverage argument

```
config axes : <n axes, each with its class count and the file and line the class list came from>
datasheet   : <knobs, range and recommended default the customer document gives; who said so, or ?>
space       : <legal> of <cross product> ; <builds> builds x <runs per build> runs
classes     : <per axis, the classes and the breakpoint line each came from, or top level only>
selected    : <n configurations, the pairwise floor for comparison, and the tier each runs in>
depth       : pairwise | pairwise-plus-named-triples | enumerated | ad-hoc
window      : <per-run, per-night or per-week, and the date the window last reset>
shipped     : <each customer and datasheet configuration, marked present or absent from the set>
negative    : <illegal combinations refused at elaboration, and the ones refused by nothing>
model       : <covergroup file; axes with no coverpoint; every ignore_bins named>
uncovered   : <what is not covered, the argument for accepting it, and who signs it off>
run id      : <Run identity per the profile, plus the configuration the run resolved to>
coverage    : <a of b axes opened; c of d claimed pairs checked; which numbers came from a person>
notes       : <anything the next reviewer would otherwise have to rediscover>
```

Anything not fillable from text on disk gets `?`, never a plausible number. The `uncovered` line is
what the Waiver record slot exists for, and the profile's **Sign-off** row says whose name goes on it.
An argument with an empty `uncovered` line is claiming the space was covered, which is almost never
true and is the easiest claim in the document to disprove.

Two lines are decided elsewhere and only recorded here. `run id` is the profile's **Run identity**
fact — whatever identifies one run for this team — and never a convention local to this document;
where step 6 found that a run records the configuration it resolved to, that resolved configuration
goes on this line too, because it is what makes a configuration-dependent failure reproducible.
`depth` is one of the four tokens step 5 assigns, chosen there against the closure check rather than
picked here by how thorough the set looks.

## Gotchas

- **A parameter that is not propagated is an axis that does nothing.** The top level declares it and
  passes it down, and one submodule instantiates its child with a hard-coded literal instead. Every
  configuration below that point is identical, so a twelve-configuration sweep tested one design twelve
  times. The tell is at the instance: a port connection carrying the parameter name versus a number.
- **`ignore_bins` shrinks the denominator; `illegal_bins` raises an error.** Reaching for the first when
  you meant the second turns an untested configuration into a higher percentage. Every `ignore_bins` in
  a configuration covergroup needs a named reason beside it.
- **Adding one value to one axis is not a small change.** It creates a new pair against every class of
  every other axis, so a set that was pairwise-closed last release is not closed any more. "We added the
  ECC-off option" invalidates the whole closure claim, not one row of it.
- **A degeneracy argument has to be checked, not asserted.** "One channel is a subset of four" is false
  exactly when the RTL has a branch removing the arbiter at one channel — in which case the
  single-channel configuration is the *only* one exercising that branch, and the one you nearly dropped.
- **Random configuration without a recorded resolution is unfalsifiable.** If the run does not print the
  configuration it resolved to, the claim rests on the constraint solver rather than on evidence, and
  nobody can reproduce the failing configuration afterwards. The Config object slot asks how a run
  records this precisely because the answer is so often "it does not".
- **Configurations legal in the RTL are not always sellable, and the two lists diverge silently.**
  Regressing an unsellable configuration costs the same and buys nothing; not regressing it strands the
  internal SoC team that instantiated it. Draw that boundary explicitly rather than leaving it implicit
  in a filelist.
- **Seed count and configuration count answer different questions and do not substitute.** Twenty
  configurations at one seed says nothing about stimulus depth; one configuration at twenty seeds says
  nothing about configurability. State both separately or a reviewer will assume the smaller.
- **A configuration-dependent failure needs the configuration in `where`, not in `what`.** Per
  `_shared/failure-signature-schema.md`, `what` has every run-specific literal normalised away, so two
  genuinely different configuration bugs collapse into one signature if the configuration lives there.
  Push it into `where` — the schema's most specific stable location — and repeat it in `run id`.
- **The published claim that most defects come from one- and two-way interactions comes from software
  fault studies, not from RTL parameter studies.** Pairwise is defensible because it is derived, bounded
  and checkable, not because of a percentage. Never quote a number at a reviewer as though it had been
  measured on this IP.

## Human verification — what a wrong answer looks like

Before taking the argument into a review, check:

- the size of the space appears as **two** numbers, builds and runs per build, not one
- every class boundary is traceable to a file and line from step 3, or is marked as coming from a
  person; a class list with no evidence column is taste wearing a table
- the selected set is quoted **against the pairwise floor**, so its efficiency is visible
- every entry in Shipped configurations appears in the set at its exact values, not as a class member
- the `datasheet` line names a person against each of the three values, or carries `?` — a knob list
  or range that appeared with no source is one somebody inferred from the RTL, which is the one thing
  that line cannot be
- `depth` is one of the block's four tokens and matches what step 5's closure check actually found:
  `pairwise-plus-named-triples` only where each triple is named with the RTL region that justifies it,
  `enumerated` only where the legal count itself is quoted and fits the tier budget, and `ad-hoc`
  wherever the derivation could not be traced — a set that closed nothing but reads as `pairwise` is
  the single most common way this block becomes false
- the window names a period **and** the date it last reset — a closure claim with no reset date is
  claiming nothing has changed since it was written
- every `ignore_bins` in the covergroup is named in the `model` line, and `uncovered` is non-empty with
  a name against it
- the `coverage` line says how many axes were opened and how many pairs were actually checked

A wrong answer typically reports one enormous configuration count with no build number behind it; lists
equivalence classes that are round numbers rather than breakpoints; claims pairwise closure over a
rotating tier without naming the window; or reports a coverage percentage that rose because bins were
ignored rather than because configurations were run.

## Done when

A reviewer can see how big the legal space is, which subset runs and at what interaction depth, and
what is deliberately uncovered with a name against it.
