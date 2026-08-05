---
name: dv-tb-architecture-record
description: Fix the shape of a new verification environment before any code exists — agent topology, the VIP versus native boundary, the configuration hierarchy, and what must stay true for the block environment to survive integration — and write it down as a reviewable record. Use when you are starting a testbench for a new block or IP, when someone says just copy the last environment, when you have to decide whether to buy VIP or write an agent, when a block environment is about to be instantiated inside a bigger one, or when nobody can say which parts of the current structure were deliberate.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Testbench Architecture Decision Record and Reuse Boundary
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: principal
  semiskill-owner: dv-guild
  semiskill-version: 1.2.0
  semiskill-review-by: 2027-04-27
  semiskill-tags: architecture, testbench, uvm, vip, reuse, configuration, decision-record
---

# Testbench Architecture Decision Record and Reuse Boundary

A verification environment's shape is chosen in its first week and paid for over its next three
years, and almost none of it is written down. The topology is inherited from whichever sibling
environment got copied, the VIP boundary is settled by whoever held an entitlement that month, and
the reuse contract is discovered eighteen months later at integration, as a list of things that
turned out not to be true. This procedure fixes four decisions — **agent topology, the
VIP-versus-native boundary, the configuration hierarchy, and the block-to-integration reuse
contract** — into one record, each carrying its alternative and the cost of reversing it. The
deliverable is that record plus numbered open questions with a named owner each. It is not a
verification plan: it fixes the structure of the environment, never what to test with it.

## When to use something else

Use this **before** code exists, or immediately before a block environment is instantiated inside a
larger one. If you cannot yet find the repository's build entry point, test list or existing
environments, start with `dv-repo-orientation`. Downstream of an approved record: writing one named
agent and its checker is `dv-uvm-agent-checker`, and proving a chosen VIP's checkers and coverage are
genuinely switched on is `dv-vip-integration` — this record only decides *which* interfaces get VIP.
`dv-ral-bringup` debugs a register model that misbehaves; step 5's `Register model` contract row and
the record's `ral` line only decide where that model comes from. A build that does not compile is `dv-build-filelist-hygiene`, one failing log is
`dv-sim-log-first-error`, a night of failures is `dv-regression-triage-routing`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Target environments | [[FILL: the block this environment verifies, and every place it must later run — block, subsystem, SoC, emulation, customer delivery — with a date for each]] | verification lead |
| Reference environment | [[FILL: the two environments in our tree whose structure we consider current, their paths, and which of the two is the one to copy]] | DV lead |
| VIP inventory | [[FILL: which protocol VIP we are entitled to use, at which exact version, how many simulation entitlements we hold, and where the installed tree and its release notes sit on disk]] | DV infra owner |
| Native agent library | [[FILL: which interfaces already have an in-house agent, that library's repository path, and who maintains it]] | DV lead |
| Config convention | [[FILL: how a component gets its configuration here — from its parent's configuration object, from the configuration database keyed on its own instance path, or a split by field kind, in which case say which kinds go which way — and our key naming rule]] | DV infra owner |
| Reset and clock ownership | [[FILL: which component drives reset and clock in our block environments, and what drives them at the next target up]] | block DV owner |
| Delivery form | [[FILL: what a customer or another team receives with this IP — the whole environment, a compliance suite, a subset, or nothing — and which files are externally visible]] | IP product owner |
| Record location and approval | [[FILL: where an architecture record lives in our tree, its file naming rule, and who must approve it before environment code starts]] | DV lead |

Pack-wide facts are **not** re-asked here. `_shared/team-profile.md` supplies exactly one fact this
skill spends: **Register model source**, used as written by step 5's `Register model` contract row and
recorded on step 6's `ral` line. Three other profile rows are deliberately *not* named as inputs,
because nothing here would consume them: **Simulator** and **Filelist convention** are spent by
`dv-build-filelist-hygiene` when the skeleton first compiles, after this record is approved, and
**Area to owner map** keys a *failing area* to its owner, whereas this record has no failures — its
owners come from the **Record location and approval** slot and from the people named in steps 3 and 5.
**Record location and approval** is narrower than the profile's
**Sign-off**, which is who accepts *finished verification* and on what evidence; this asks who
approves a structural record before any code exists — usually a different person, always a different
moment. **Reference environment** is a judgement the profile does not record at all.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented VIP version, agent
library path or approval route produces a record that reads as agreed and was agreed by nobody.

## Retrieval budget — read this before opening anything

An RTL top file can carry two thousand port declarations and an installed VIP tree hundreds of
thousands of files. This is a decision, not a survey.

1. **Grep and Read work on files on disk.** If the interface list, the integration plan or the VIP
   release notes exist only as a document Read cannot open — a spreadsheet, a slide deck, a wiki page
   — say so first, take those facts as handoffs, name whoever supplied each, and mark every record row
   resting on one *provisional*.
2. **Glob for paths, never to read.** Record paths during a survey; open nothing.
3. The whole procedure is capped at **4 Glob patterns, 12 Greps and 8 windowed Reads of about 80
   lines**, spent as: step 1 two Globs, two Greps, two Reads; step 2 two Greps, two Reads; step 3 one
   Glob, two Greps, one Read; step 4 two Greps, one Read; step 5 one Glob, three Greps, one Read; and
   one Grep plus one Read held back for whichever step needs a second look. Steps 6 and 7 open nothing.
4. **One call per step, never one call per name.** Every allocation above is flat: it does not grow
   with the number of interfaces, VIP products or existing environments in play. Where a step needs
   several names, alternate them into a **single** pattern — `nameA|nameB|nameC` — and spend one call.
   Where the list is longer than one readable pattern, take the two names whose answer is least
   certain, spend the call on those, and make the rest numbered open questions. A step that fans out
   one call per name is the way this budget gets quietly exceeded on the second interface. The same
   holds for **paths**: where two directories have to be compared, root a *single* Grep at their
   nearest common parent and separate the hits by the file path each one carries, rather than one call
   per directory. If that parent is broad enough to trip rule 5, do not widen the budget — narrow the
   question to one directory and make the other a numbered open question.
5. **A Grep returning more than about 200 hits is too broad** — anchor it before reading around any
   hit. **A result that hit your runtime's limit is not a count**: record "at least N, truncated".
6. **Stopping rule.** Stop when every interface found in step 1 has a topology row and every row of
   the step 5 contract is answered, or when the budget is spent — whichever comes first. Whatever the
   budget did not reach becomes a numbered open question with an owner, never an inference.
7. **State your coverage.** The record's `coverage` row says which rows were read out of files, which
   came from a person, and what was never reached.

## Procedure

### 1. Fix the design boundary from the RTL, not from the block diagram

Two **Glob** patterns: one for the block's top-level RTL file, one for the directory holding it — a
top and its wrapper both match the obvious pattern, and picking the wrapper silently hides a whole
interface. Then one **Grep** for the module header to get its line number, and one bounded **Read** of
about 80 lines from there.

Group the signal names into interfaces by prefix family: a protocol interface almost always announces
itself as a shared prefix across a handful of signals. Record three numbers — ports seen, interfaces
named, signals you could not group — and carry the third into the record honestly.

Two things break this sweep. **SystemVerilog interface ports carry no direction keyword**, so a top
using them under-counts badly — and a long port list runs past the window either way. Both are
answered by the **same second Grep**, spent once: alternate the direction keywords and every
interface type name the window showed into one pattern — `input|output|inout|type_a|type_b` — and
read the line numbers it returns. That single call tells you both how far the port list actually runs
and how many interface-typed ports it carries, and the second **Read** then lands on the tail. Do not
Grep once per interface type: a block with more than one external protocol is the normal case, so
per-type calls exceed this step's two-Grep allocation before you have finished the boundary. If the
alternation is too long to read, follow budget rule 4 — the two least certain names, and the rest as
open questions. And **a parameterised or generated top has conditional ports**, so what you read is
one configuration of the boundary — say which, and make the others open questions.

### 2. Fix the agent topology

One agent per **protocol interface**, never per signal group and never per internal design block. The
DUT's internal partitioning is not visible at its pins, and an environment shaped like the design's
block diagram cannot be reused when that partitioning changes.

For each interface from step 1 write down its **role** (master, slave, responder or monitor-only),
whether the environment drives it or only observes it, and whether it is **passive-capable** — able to
build with its sequencer and driver absent. Passive capability is a configuration field, not a second
agent and not a second topology; every agent is built both ways from the first day or it will never be
built passive at all. Then say where sequences live: a virtual sequencer holding handles to the real
sequencers is what lets one test express intent across interfaces, and it must survive integration
with only a *subset* of those sequencers present. Layer an agent only where the protocol has layers.

Use the **Reference environment** slot, not a Glob, to see how this was done last time. That slot
names two environments and says which of the two is **the copy target**; wherever a later step says
*copy target* it means that one path, so every count this record quotes belongs to a single named
environment.

Two **Greps**, one for the agent instantiation lines and one for the active-passive configuration
field. Root both at the **nearest parent directory the two reference paths share**, so one call
returns hits from both environments and the file path on each hit says which one it came from; ignore
hits under any other path. What appears the same way in both is house convention; what differs is
content — a convention seen in one file is a coincidence. If the two paths share no parent narrow
enough to stay under rule 5's hit ceiling, spend both Greps on the copy target alone, mark the
convention claim *provisional*, and make the second environment a numbered open question for the DV
lead. Both bounded **Reads** land in the copy target — its build phase and its connect phase — since
that is the file you will mirror; the identical-or-different test needs the other environment's Grep
lines, not its body.

### 3. Fix the VIP-versus-native boundary, one interface at a time

Now that the agent list exists, decide who supplies each one, from the **VIP inventory** and **Native
agent library** slots. One **Glob** confirms the installed trees are on disk at the claimed versions —
one pattern with every claimed VIP directory alternated into it, however many products are in play,
never one Glob per product.

Reuse VIP when the protocol is standard, when compliance against the specification is itself part of
the deliverable, and when a customer will expect the recognised checker. Write a native agent when the
interface is proprietary, when it is narrow enough that the VIP's abstraction costs more than it
saves, or when the check you need lives below the level the VIP models. Four facts belong in the
record beside each VIP choice — all four come from the one Glob above and the one conversation below,
not from a fresh search per product:

- the **exact version string**, from release notes on disk or from the DV infra owner — a VIP upgrade
  changes the environment's contract and earns its own regression
- the **entitlement count**, which caps how many simulations run in parallel; a throughput decision,
  not a cost line
- the **extension mechanism** — factory override, callback or configuration, never a source fork
- whether its files are externally visible under the **Delivery form** slot

Much VIP ships protected or pre-compiled, so **Read** returns nothing useful from it. Spend this
step's two **Greps** and one **Read** on the *copy target's* instantiation of that VIP
instead — that shows the configuration object it expects and the connections it needs. Both Greps are
flat across products: one alternates every VIP product name to find the instantiation lines, one
alternates them again for the configuration handles set on them, and the single **Read** lands on the
instantiation site of whichever product is least certain. Two products cost the same two Greps as
one; a third and a fourth do not get their own calls — check the two least certain and make the rest
numbered open questions. To confirm the entitlement count and version, **ask the DV infra owner and
record who answered**; the agent cannot query a licence manager.

### 4. Fix the configuration hierarchy

The rule that prevents most later drift: **each configuration field has exactly one source** — either
an object handed down by the parent, or the configuration database keyed on the component's own
instance path. Never the same field from both. Two sources for one field are invisible while the
values agree and undebuggable the week they stop.

The rule is per field, not per component, and that distinction is the whole of it. If the **Config
convention** slot came back as a split — structural knobs through the parent object, selection knobs
from the database, say — that is a legitimate house convention and is compatible with this rule;
write the split into the record kind by kind, so the boundary is a stated rule rather than a habit.
What is fatal is one *field* reachable by both routes, never a component that reads different fields
different ways.

Build the object tree top-down: one environment configuration object holding a handle to each agent's
configuration object, constructed by the environment. A single set at the top then reaches everything
without a wildcard scope, and the whole tree can be constructed by a *parent* environment later, which
is what makes step 5 possible. Sort every knob into one of three kinds — they have different
deadlines, and both of the first two mistakes below produce a run that passes and proves less than it
claims:

| Kind | Examples | When it is read | The trap |
|---|---|---|---|
| Structural | agent count, active or passive, which checkers exist | build phase, before children exist | set after the build phase it is read by nobody, and the run silently uses defaults |
| Behavioural | timing pressure, error-injection rate, delay ranges | run phase | frozen in the build phase it stops varying, and every seed becomes the same seed |
| Selection | which test, which sequence, which preset | before the build phase | read deep inside a component as a plusarg it is invisible in this record, and unreachable from a parent environment |

Confirm the house rule from the **Config convention** slot and the copy target: two **Greps**, one for
configuration-database set calls and one for get calls, and one bounded **Read** at that
environment's configuration class declaration. A set with a wildcard scope is the finding to look
for; step 5 says why it is fatal.

### 5. Fix the block-to-integration reuse contract

This section pays for the whole record. Answer every row with **met, not met, or deliberately waived**
— a waived row with a reason is a decision, a blank row is a surprise at integration.

| Contract row | What must be true | How to check it now |
|---|---|---|
| Instance uniqueness | Nothing is a singleton — no static class member, no wildcard configuration scope, no fixed interface name | Grep the copy target for wildcard scopes and static members |
| Interface handoff | Virtual interfaces arrive through the configuration object, not a database key baked at block level | the set calls found in step 4 |
| Config construction | The environment uses a configuration object given to it if one exists, and creates its own only when none does | the build-phase window from step 2 |
| Reset and clock | The environment knows whether it owns reset, and every reset-driving sequence is gated on that | **Reset and clock ownership** slot, both levels |
| End of test | The block environment does not decide when the test ends; the objection belongs to the top-level sequence | Grep the copy target for objection calls |
| Register model | The environment accepts a pre-built model and a non-zero base address instead of always building its own at zero | profile's **Register model source** row, plus the model construction site |
| Scoreboard | Stated as reusable or block-only — one level up, its stimulus may be another block's output | a decision, not a Grep |
| Coverage credit | Whether coverage collected here counts toward sign-off after integration, and under whose merge policy | handoff to the verification lead |

Three of the rows above are checked against the **copy target** and nowhere else, and that is where
this step's three **Greps** go: wildcard configuration scopes, static class members, objection calls.
Those are the habits this environment stands to inherit, and they exist on disk today whether or not a
higher level does. Do not re-point these Greps at a higher-level environment part-way through — one
target per row, or the counts the record quotes belong to a file the record never names.

Then take the levels from the **Target environments** slot. If one of them already exists in the tree,
spend this step's **Glob** finding it and its one bounded **Read** where it instantiates a block
environment; a real precedent beats every opinion in the room, and it is the only evidence here for
how integration actually consumes an environment. If none exists yet, say so, mark the contract
*provisional*, and leave that Glob and Read unspent — a cap is not a quota. Then **ask
the integration owner one question in writing and record the answer: will this environment ever be
instantiated more than once in the same simulation.** At an IP company the answer is usually yes, and
it invalidates every singleton in the table above.

### 6. Draft the record

Each decision gets its alternative and its reversal cost. That pairing is what makes this a record of
a decision rather than a description of a testbench.

```
tb architecture record v1 — block, author, date
status       : proposal, not approved — no environment code has started against it
approver     : <who must approve this before code starts, from the Record location and approval slot>
scope        : <the block, and every target from the Target environments slot with its date>
dut boundary : <path and line of the module header> <ports seen, interfaces named, ungrouped>
topology     : <one row per interface — name, role, passive-capable, owner>
vip          : <per interface — product, exact version, entitlement count, extension mechanism>
config       : <the object tree, the one source each field has, and the split by kind if we have one>
reset owner  : <what drives reset here, and what drives it at the next target up>
ral          : <where the register model comes from, and whether this environment builds or accepts it>
reuse        : <one line per step 5 row — met, not met, or waived with a reason>
delivery     : <what leaves the company with this IP, and which files above are externally visible>
reversal     : <per decision — cost of changing it once written, tagged from-file, from-person or judgement>
open         : <numbered questions, each with the person who answers it and a date>
coverage     : <which rows came from files, which from a person, what the budget did not reach>
```

**The reversal cost is derived, not felt.** Nothing new is opened for it — every source is already in
hand from steps 1 to 5, and each entry carries the tag that says which one it came from:

- **from-file** — a count the Greps already spent returned, quoted with its path. Step 5's
  wildcard-scope and static-member Greps are the reversal cost of the instance-uniqueness decision:
  each hit is a file a later fix has to touch. Step 2's agent-instantiation Grep is the reversal cost
  of changing the topology — that many sites moved the last time somebody did it. Step 4's set and get
  Greps are the reversal cost of changing where a field is sourced from. All three counts come from the
  copy target, which is on disk today, so they stand even for a green-field block — quote each with
  that path, never with the path of the environment you are about to write.
- **from-person** — a cost stated by the person who answered the handoff. The VIP version and
  entitlement answers came from the DV infra owner in step 3; the "instantiated more than once"
  answer came from the integration owner in step 5. Name who said it.
- **judgement** — everything neither of those reached, which for a green-field block is usually the
  delivery-form and scoreboard-reuse decisions. Write the word. Tagged that way the reader knows it
  is the author's estimate, and the record stops presenting it as evidence.

Where step 5's Glob found **no** higher-level environment, its Read was never spent and nothing on
disk prices what a future parent would have to change: the reversal cost of the interface-handoff,
config-construction and coverage-credit rows is `judgement` there, or `from-person` if the integration
owner gave you a number. That is a missing parent, not a missing Grep — the three counts above came
from the copy target and still stand.

An untagged reversal entry is the one thing this record must not carry: it reads exactly like the two
evidenced kinds and was checked by nobody.

The record is text you produce, not a file this procedure creates — the agent has no Write tool. **Ask
the engineer to save it** at the path the **Record location and approval** slot names, under that
slot's file naming rule, with the approver named inside it. Nothing here starts the environment: this
is a proposal until that person accepts it, and the record's first line says so.

### 7. Audit the record against the tree before handing it over

No new files — check against what you already opened:

- every interface from step 1 has exactly one topology row, and the ungrouped-signal count is stated
  rather than quietly dropped
- no agent row claims passive-capable without the step 2 evidence behind it
- every VIP version, entitlement count and path is either a path and line you read, or attributed to
  the person who supplied it
- every step 5 row says met, not met, or waived — none is blank
- every reversal entry carries its tag — a count and a path you already read, a named person, or the
  word *judgement*; an untagged one is not finished
- every unfilled slot appears as a numbered open question with an owner, never as an assumption

Then hand it to the approver. Once the topology is agreed, **ask the engineer to compile the empty
environment skeleton once and give you the path to the build log**; if that build breaks it is
`dv-build-filelist-hygiene`'s problem, not this record's.

## Gotchas

- **A monitor that samples the driver cannot go passive.** Rebuilding the transaction from an internal
  queue instead of from the pins works perfectly at block level, where the agent is always active, and
  removes the entire reuse case the moment the agent is built passive. Invisible until integration,
  which makes it the most expensive shortcut in this list.
- **Two instances of the same IP break every global.** Static class members, a configuration set with a
  wildcard scope, a fixed interface name, and coverage keyed on nothing are all correct with one
  instance and wrong with two. At an EDA-and-IP company the second instance is the normal case, and
  retrofitting instance-uniqueness later touches every file.
- **A forked VIP can never take a vendor fix.** Once its source is edited in your tree, every future
  release is a merge you own forever. Extend by factory override, callback or configuration, and record
  which one you used next to the version.
- **The entitlement count sets regression width, not just cost.** A VIP checking out one entitlement
  per simulation caps parallel jobs, so a four-hundred-job nightly against a small pool quietly becomes
  a queue and stops finishing overnight. Decide it before the topology.
- **Protocol coverage is not functional coverage.** A VIP's compliance coverage says the interface was
  exercised legally. It says nothing about your design's modes, and counting it toward the plan gives a
  green number and a gap that surfaces at sign-off.
- **Reset ownership moves at integration and nobody notices** until a block sequence asserts reset in
  the subsystem and kills three neighbours. Gate every reset-driving sequence on an ownership field
  from day one; it costs one line now.
- **A block environment that raises and drops the end-of-test objection cannot be a sub-environment.**
  Something else decides when the test ends up there, and a block that ends it truncates everyone
  else's stimulus.
- **Copying the reference environment forks it.** Copy it for conventions, not for infrastructure: a
  copied base class drifts and a fix in the original never reaches you. Say in the record which parts
  are copied and which are imported.
- **Bound assertions and hierarchical references are absolute.** An assertion bound with a block-level
  path, or an interface fetched by a fixed string, moves under integration and fails in a way that
  looks like a design bug for a day and a half.

## Human verification — what a wrong answer looks like

Before the record is approved, check:

- every interface named in the topology traces to a port group in the design's own header with a line
  number, and the count of signals that could not be grouped is written down
- every agent row states passive-capability explicitly, and a "yes" was checked against a real
  environment rather than assumed
- every VIP version is an exact string from a file or a named person, never a plausible number
- the reset row names **two** owners — this level, and the next level up
- every decision carries an alternative and a reversal cost, and every reversal cost is tagged
  from-file, from-person or judgement; an untagged cost is a number nobody sourced
- the `coverage` row is present and the open-question list is **not empty**

A wrong record reads fluently and mirrors the design's internal block diagram instead of its pins; or
names one agent per signal group; or lists a topology with no owner per interface; or claims a reuse
contract never checked against an environment that exists. Its clearest tell is a reversal column
that is either absent or entirely untagged — a description of a testbench somebody already intended
to write, not a set of decisions anyone can disagree with on evidence.

## Done when

The approver named in the record can accept or reject each decision on its own, and every unfilled
slot has become a numbered question with an owner instead of a silent assumption.
