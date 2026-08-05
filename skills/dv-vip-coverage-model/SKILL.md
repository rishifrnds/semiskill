---
name: dv-vip-coverage-model
description: Review or draft the functional coverage model a VIP ships to customers — bin counts, cross sizes, what to prune as illegal or unreachable, and what not to cover at all. Use when you are defining the coverage model customers rely on for protocol sign-off, when a cross has been open for three regressions and nobody can say whether it will ever close, when a customer asks which bins their configuration can never hit, or before you burn a regression cycle discovering a cross that can never close.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Shipped Functional Coverage Model: Bins, Crosses and What Not to Cover"
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-09-14
  semiskill-tags: coverage, covergroup, bins, cross, closure, vip, protocol, sign-off
---

# Shipped Functional Coverage Model: Bins, Crosses and What Not to Cover

A VIP's coverage model is not an internal artefact. It is the evidence a customer's protocol sign-off
rests on, and every bin in it is a promise that something is reachable and worth reaching. The
expensive mistakes are all one shape: a cross written in an afternoon multiplies out to tens of
thousands of bins, a few hundred of them forbidden by the protocol and a few thousand that the
customer's configuration can never generate — discovered six weeks later, after nightly regression
has been chasing them the whole time.

The output is **a sized inventory, a disposition for every cross, and a written not-covered list**,
plus a closure-cost floor. This reads source files and saved text reports; it cannot start a
simulation, merge a coverage database, open a waveform, or open a specification that is not a
readable file. Every step needing one of those ends in a handoff to a named person and says so.

## When to use something else

This is the model itself, before the regression that will chase it. Three neighbours start where it
stops. A merged report already full of unhit bins — each hole classified as a stimulus gap, a
constraint blockage, a bin defect or a genuine unreachable — is `dv-coverage-hole-disposition`, and
ranking and owning that plan is `dv-coverage-hole-closure`. Whether the merge is trustworthy at all,
across seeds, configurations and engines, is `dv-coverage-merge-report`. Which of a configurable IP's
legal parameter combinations to regress is `dv-config-space-coverage` — that picks the
configurations, this decides the bins inside one. Step 8 below spends two Greps sanity-checking a
model against a report; it is not a hole review and must not be sold as one.

Also: bin and covergroup names moving across releases is one line of the larger question
`dv-vip-release-compat` answers properly, and proving a model is genuinely switched on rather than
declared and never constructed is `dv-vip-integration`. A failing test is `dv-sim-log-first-error`; a
night of them is `dv-regression-triage-routing`; a covergroup file that will not compile is
`dv-build-filelist-hygiene`; not yet knowing where coverage lands is `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Protocol and revision | [[FILL: the protocol and exact revision this VIP claims compliance with, and whether our copy of that specification is a file on disk that can be read or a document only a person can open]] | VIP architect |
| Coverage model location | [[FILL: where this VIP's covergroups live in our tree, and which of them are generated rather than hand-written]] | VIP owner |
| Configuration knobs | [[FILL: the configuration parameters that change which bins are legal for one customer instance — data width, channel count, optional feature enables — and where their legal values are declared]] | VIP architect |
| Cross size cap | [[FILL: the largest number of cross bins we allow one cross to declare before it needs written justification]] | verification lead |
| Sample point convention | [[FILL: where our VIP samples coverage — which monitor, which analysis port or callback, and the point in a transaction's life at which its fields are final]] | VIP owner |
| Report format | [[FILL: what our coverage tool writes that is a text file on disk, the string a zero-hit bin prints in it, and the string an excluded bin prints]] | coverage owner |
| Exclusion convention | [[FILL: where our tool-side coverage exclusions live, and whether they ship to the customer with the VIP or stay internal]] | coverage owner |
| Release compatibility rule | [[FILL: what our VIP release promises about covergroup and bin names across versions, and how a rename is deprecated]] | VIP release owner |
| Closure target | [[FILL: the number our customers sign off against, which merged database it is read from, and which covergroups are inside that number]] | verification lead |

Three pack-wide facts come from `_shared/team-profile.md` and are not re-asked here: **Coverage
output** (where merged coverage lands), **Simulator** (whose vocabulary the report is written in) and
**Sign-off** (who signs, on what evidence). Four rows above sit near facts other skills already ask
for, and they relate to them three different ways — read this rather than filling one from another.
**Coverage model location** is genuinely the same fact as `dv-coverage-hole-disposition`'s
coverage-model-source slot: one answer, used twice, and if they disagree one is stale. **Report
format** is only *half* the same — its zero-hit string is that skill's unhit-bin marker, but the
excluded-bin string is asked only here, because step 8 has to tell a bin that was pruned from a bin
that was never reached. **Closure target** is the profile's Sign-off fact narrowed to a number: that
one names the person and the evidence, this names which covergroups are inside the percentage and
which database it is read from. **Release compatibility rule** is narrower than anything
`dv-vip-release-compat` asks — only the promise about *bin and covergroup names*, which its
compatibility tiers may or may not treat as public surface.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented clause, knob name or
naming rule produces a pruning decision that looks authoritative and quietly deletes legal
combinations from the denominator — the one error here that makes the number go *up*.

## Retrieval budget — read this before opening anything

Coverage model source is modest; merged reports are not. A per-bin report for a real VIP runs to
hundreds of thousands of lines, and reading one whole achieves nothing.

1. **Grep, Read and Glob work on files on disk.** If the covergroup arrived pasted into the
   conversation, ask for its path, or ask for it to be saved to a file and be given that path. Until
   a path exists you may reason over the pasted text by eye — but say so, and mark every count
   provisional. You have sized a fragment, not a model.
2. **Glob** first: at most **three** patterns, each scoped to one directory from the Coverage model
   location slot. A repository-wide sweep returns tens of thousands of paths.
3. The **Grep** ledger is **eight calls**: one for covergroup declarations (step 2), one for crosses
   (step 3), one alternating the two pruning keywords (step 4), at most three for configuration knob
   names (steps 4 and 5), and two against the merged report (step 8).
4. The **Read** ledger is **eight windows**: up to five of about 60 lines, one per covergroup under
   review; one spare of about 40 lines at the sample site (step 6); at most two of about 80 lines
   inside the report (step 8). Never open a report or a generated model with Read first — Grep for a
   line number, then window it. Above about 200 hits a pattern is too broad; narrow it first.
5. Bin counts come from **declarations you read**, never from a report's totals and never from
   memory. A report total is a fact about one run's tool settings, not about the model.
6. **Stopping rule, then state your coverage.** When the ledger is spent, stop, and say how many
   covergroups you opened and how many crosses you sized — "sized 3 of 9 covergroups; 6 unopened".
   An unstated shortcut is always worse than a stated one, and in a *coverage* review it reads as a
   claim about coverage.

## Procedure

### 1. Fix the protocol revision, and find out what can actually be read

Everything downstream is pruning, and every pruning cites something. Take the **Protocol and
revision** slot first. If the specification is a readable file on disk, a pruning can cite a clause
and a line. If it is a PDF, a licensed viewer or a printed book, **Read** cannot open it: ask the VIP
architect for the clause and its wording, record who supplied it, and mark every bin pruned on that
basis *provisional — supplied by a person*. Never paraphrase a clause you have not seen. If the model
source was pasted rather than pointed at, resolve that now too — budget rule 1.

### 2. Inventory the covergroups before judging any of them

**Glob** the directories in the **Coverage model location** slot, then **one Grep** for covergroup
declarations to get a line number for each. Record per covergroup: name, file and line, whether it is
generated, and — from the window step 3 opens — its sampling trigger and its `option.per_instance`.

`option.per_instance` is 0 unless someone set it. At 0 the tool keeps one number for the covergroup
*type* and no per-instance breakdown survives, so on a VIP a customer instantiates four times you
cannot say which channel closed which bin. Whether the type number merges instances is a separate
setting again (`type_option.merge_instances`); its default has moved between LRM revisions and tools
differ, so read the value written in our source and ask if it is absent. Which of those two numbers
the **Closure target** slot names is the one that matters.

### 3. Size every coverpoint, then multiply out every cross

Spend the five 60-line **Read** windows here, one per covergroup. Three declaration shapes account
for nearly every sizing error:

- **No explicit bins.** The tool creates automatic bins capped by `option.auto_bin_max` — 64 by
  default in the SystemVerilog LRM, though a house default or a tool switch can change it, so read
  the value rather than assume it. On an 8-bit field that is a defensible 64 buckets; on a 32-bit
  address it is 64 arbitrary sub-ranges of a four-billion-value space, which closes early and means
  nothing. Any wide coverpoint with no explicit bins is a finding on its own.
- **`bins a[] = {[0:7]}` versus `bins a = {[0:7]}`.** The first declares eight bins, one per value.
  The second declares **one** bin that any value in the range fills. Two characters apart, and the
  second reports 100% after a single transaction.
- **Transition bins.** `bins t = (IDLE => BUSY => DONE)` is one bin however many values it names, and
  the repetition forms are declared bins too. A coverpoint's size is the number of *bins declared* —
  not the number of legal values, and not the width of the field.

Then **one Grep** for cross declarations, and multiply the declared bin counts of each cross's
components: a cross's automatic bins are the cartesian product of the component **bins**, not of
their values, which is why sizing had to come first. Rank the crosses by that product, largest first,
and put the **Cross size cap** slot's number beside the list. Anything above it needs a written
justification naming the sign-off question it answers, or step 4's pruning until it falls under. A
cross of 8, 12 and 5 bins is 480 — reviewable. Add one unbinned 32-bit address and it is 30,720, and
no regression on the roadmap closes it.

### 4. Give every cross bin group one of four dispositions

Use **one Grep** alternating the two pruning keywords to see what is already excluded, then work down
the ranked list. Every group of cross bins gets exactly one disposition, and each cites something.

| Disposition | Means | What must be cited |
|---|---|---|
| keep | legal in this revision, and reachable by stimulus this VIP can generate | the sequence or constraint that reaches it |
| `illegal_bins` | the protocol forbids it, so a hit is a design or stimulus bug | the clause, from the **Protocol and revision** slot |
| `ignore_bins` | legal in the protocol, unreachable here or deliberately out of scope | the configuration knob, or the scope decision and its owner |
| drop the cross | the components are not independent, or the cross answers no question | which coverpoint derives from which |

Four shapes decide most of them. **Protocol-forbidden pairings** — a burst type the spec restricts to
fixed lengths, a response the spec never allows on that transaction — are `illegal_bins` *only* when
the clause forbids them in the exact revision the slot names; otherwise `ignore_bins`.
**Configuration-dead combinations** need a width, channel or optional feature the instance does not
have: take the names from the **Configuration knobs** slot and spend at most three **Grep** calls
confirming where each is declared and what values it takes. **Structurally impossible cells** arise
where one coverpoint derives from another — drop that cross, it measures nothing its components did
not. And **cells nobody can name a consequence for**: ask what we would not know if this bin never
closed, and if there is no answer, delete it rather than prune it.

**Prune in the source, not in the report tool.** A pruning that lives in a tool-side exclusion file
travels only as far as the **Exclusion convention** slot says it does — and if that answer is
"internal", the customer inherits a denominator holding bins their configuration cannot reach, and
their number is permanently short. Protocol-impossible belongs in the source; configuration-dead
belongs in configuration-guarded construction; only a local, temporary waiver belongs in the
exclusion file, with an owner and a date.

### 5. State the closure cost before anyone spends a regression

Take the largest surviving cross's legal bin count L — the step 3 product minus everything step 4
pruned. If every legal bin were equally likely, which none of them are, the expected number of
sampled transactions before all L are hit at least once is about **L x (ln L + 0.58)**: roughly 3,200
for L = 480, roughly 450,000 for L = 40,000.

Then say what that figure is not. It is a **floor**. Real stimulus is not uniform, and the true cost
is set by the rarest legal bin — if a constraint makes one combination appear once in 5,000
transactions, that bin alone needs on the order of 5,000, and the uniform figure says nothing about
it. Multiply the floor by `option.at_least` wherever it exceeds 1, and again by the instance count
when the **Closure target** slot names the per-instance number. Present a range with its assumptions
attached, never a date.

### 6. Check the sample point — a model that samples the wrong instant is worse than none

Spend the spare 40-line **Read** window at the site named in the **Sample point convention** slot.

- **Are the fields final?** A transaction sampled when its request is issued carries no response code
  yet, so every response bin records the field's default value — and one default-valued bin reads as
  covered forever once it reaches a merged database.
- **One sample per transaction, or one per clock?** A clock-triggered covergroup over
  transaction-level coverpoints inflates hit counts by the transaction's length, which makes
  `option.at_least` meaningless and a rare bin look well exercised.
- **Is reset excluded?** Sampling during reset records the idle encoding as a genuine hit. Guard the
  coverpoint with `iff`, or start and stop the covergroup instance around reset — and say which our
  VIP uses, because a customer who moves reset will ask.

If the answer turns on timing rather than on the source, no window settles it: ask the VIP owner and
record that the answer came from a person.

### 7. Write down what the model deliberately does not cover

This is the half people skip and the half that ends an argument at sign-off. Four categories belong
on the list, each with a reason. **Proven elsewhere** — anything the protocol checker already
asserts; an assertion that fires is a stronger statement than a bin that fills, and covering both
doubles the closure cost while halving the clarity about which artefact is authoritative. **Not
reachable in any configuration we sell** — reserved encodings, deprecated modes, widths no supported
instance builds at. **The VIP's own internals** — code and toggle coverage of our agent is our
quality evidence, not the customer's protocol evidence, and putting it in the shipped number lets
their protocol coverage rise because our sequencer got exercised. **Deliberately deferred** — name
the release that will claim the feature, or say there is none.

Then check the names, because bin and covergroup names are the merge key when a customer combines our
database with theirs, and the key their exclusions and trend charts are written against. Apply the
**Release compatibility rule** slot: a rename that looks cosmetic splits one bin into two across a
version boundary and resets a customer's trend to zero. Carry every renamed name into the `names`
line of step 9 with its deprecation path.

### 8. Cross-check against a merged report, only if one is on disk

A model review does not need a report, but a report catches what static reading cannot: bins the tool
never created, and bins the model declares that the report has no row for.

Ask the engineer to run one regression with coverage collection enabled, merge the databases, write
the text report and give you the path it landed at — the profile's **Coverage output** fact says
where our merged results live, so ask for the path under it rather than for the report again. The
agent cannot start that regression or merge anything, and must not invent what a report would say.

With a path, spend the last two **Grep** calls and up to two 80-line **Read** windows: one Grep for
the covergroup name, one for the zero-hit string from the **Report format** slot. Then separate three
cases that look alike in a summary — a bin with **zero hits** (stimulus never reached it; step 4's
disposition says whether that is a gap or a missing prune); a bin with **no row at all** (excluded,
renamed, or the covergroup was never constructed, and the excluded-bin string tells the first from
the rest); and a **covergroup absent entirely** (almost always never constructed, or built under a
configuration guard that was false all night). Classifying the holes themselves is
`dv-coverage-hole-disposition`, not this step.

### 9. Write the review block

```
model       : <covergroup name, file and line>
protocol    : <protocol and revision from the slot, and how the specification was read>
points      : <n coverpoints; how many carry explicit bins; how many are on automatic bins>
declared    : <total bins declared, before any pruning>
crosses     : <n crosses, with the product size of the largest three>
pruned      : <bins moved to illegal_bins and to ignore_bins, each with its clause or knob>
dropped     : <crosses removed entirely, and the dependency behind each>
sample      : <where the model samples, and whether the fields are final there>
cost        : <floor estimate for the largest surviving cross, with its assumptions>
not covered : <the four categories from step 7, each with a reason>
names       : <any bin or covergroup renamed since the last release, and its deprecation path>
report      : <path of the merged report read, or "no report read">
coverage    : <a of b covergroups opened; c of d crosses sized; which facts came from a person>
open        : <the questions the owner must answer before this ships>
```

Leave a field empty rather than filling it plausibly, and write `?` for any number not read out of a
declaration. The profile's **Sign-off** fact says who receives this; the `coverage` and `open` lines
are what make it evidence rather than an assertion.

## Gotchas

- **`bins a[] = {[0:7]}` and `bins a = {[0:7]}` differ by two characters and by a factor of eight.**
  The second is one bin any of the eight values fills, so the coverpoint reports 100% after a single
  transaction. It is invisible in every report — the report faithfully shows one bin at 100%.
- **An `ignore_bins` written with one `binsof` clause deletes a whole row of the cross, not one
  cell.** `binsof(cp_a) intersect {WRAP}` removes every combination involving WRAP; the single cell
  needs both clauses joined with `&&`. The number goes up, nothing errors, and the legal combinations
  just deleted are the ones nobody will look at again.
- **`illegal_bins` in a shipped VIP fires an error in the customer's regression, not in yours.** If
  the combination turns out legal in a revision you did not model, or under an erratum, their nightly
  run breaks and they cannot suppress it without editing our source. Reserve it for what the slot's
  exact revision forbids; otherwise use `ignore_bins` and let the protocol checker own the error.
- **Coverage says stimulus was generated. It says nothing about anything being checked.** A model
  closes exactly as fast with the scoreboard disabled. State which regression the number came from,
  and whether checking was on.
- **`option.weight = 0` does not stop collection; it stops contribution.** The coverpoint still
  collects and still reports its own number, it simply drops out of the parent covergroup's
  arithmetic — so the two lines read together look like a broken tool.
- **A covergroup declared and never constructed reports nothing, and nothing is indistinguishable
  from a covergroup with no work to do.** Check the constructor is reached under the configuration
  the regression actually ran, before reading silence as a clean result.
- **Per-instance and merged numbers answer different questions and are quoted interchangeably.** At
  the default `option.per_instance` of 0 there is no per-instance answer at all, so a four-channel
  customer asking which channel is short cannot be answered from that database at any price. Decide
  it before the regression, not after — and note that raising `option.at_least` afterwards
  invalidates the merged database's closure claim the same way, because those hits were counted
  against the old threshold.
- **Automatic bins on a wide field close early and mean nothing.** Sixty-four sub-ranges of a 32-bit
  address fill from ordinary traffic while every interesting boundary — first, last, the ones
  straddling a page — sits inside a bin that was already green.
- **A cross of two coverpoints where one derives from the other is half impossible by construction.**
  Pruning that half is not a concession; leaving it in is how a model acquires a permanent
  unexplainable ceiling that every new engineer re-investigates from scratch.

## Human verification — what a wrong answer looks like

Before this goes to the owner, check:

- every bin count traces to a **declaration you read**, with file and line — not to a report total,
  and not to the width of the field
- every `illegal_bins` cites a clause of the revision the slot names, and anything supplied by a
  person rather than read from a file is marked provisional
- every `ignore_bins` cites a configuration knob or a named scope decision, and no pruning removed
  more of the cross than the sentence explaining it describes
- the closure cost is a floor with its assumptions attached, never a date
- the not-covered list is **not empty**, and each entry has a reason a customer could argue with
- the `coverage` line says how many covergroups were opened out of how many exist, and nothing in the
  shipped denominator is a bin this VIP's own configuration space cannot reach

A wrong answer reads as a confident review that prunes a cross to a comfortable size using a clause
nobody read, or quotes a bin count from a report generated under different tool settings than the
ones sign-off will use. Its quieter cousin declares the model complete with no not-covered list at
all — the claim that every combination in this protocol is worth reaching, which no VIP has defended.

## Done when

Every cross has a disposition with something cited behind it, the not-covered list is written in
words a customer can challenge, and the closure cost is a stated floor rather than a hope.
