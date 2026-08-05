---
name: dv-uvm-agent-checker
description: Add a new interface agent and its end-to-end checker to an existing UVM environment so the result matches this team's own conventions rather than generic UVM. Use when you are writing the driver, monitor, sequencer, item and scoreboard for an interface nobody has verified here yet, when a reviewer keeps sending your new agent back over style, when you cannot tell which base classes and configuration keys this environment expects, or when you need to decide where a scoreboard samples each side and what it does with items that never match.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Building a UVM Agent and Its End-to-End Checker to House Conventions
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-03-05
  semiskill-tags: uvm, agent, monitor, driver, scoreboard, checker, house-conventions
---

# Building a UVM Agent and Its End-to-End Checker to House Conventions

An agent written from the cookbook compiles, elaborates, drives traffic — and comes back from review
three times, because about twenty of the decisions in it are house decisions and none of them are in
the standard: which base classes, which configuration keys, who builds the monitor, what the ports
are called, where the scoreboard lives. The quieter failure is worse: a checker structurally unable
to catch the bug it was written for, because both sides of its comparison come from the same monitor,
or because nothing ever reports the items still sitting in its queue when the test ends.

The output is three things: **a conventions contract with two-file evidence behind every rule, a
file-by-file plan with drafted skeletons, and a checker design note** — plus one line saying how much
of the reference pair was actually opened.

**What this cannot do.** It reads source files. It cannot compile, elaborate, simulate or open a
waveform, and it does not write into your tree — it drafts bodies into the reply for you to place.

## When to use something else

- You cannot yet name the environment file, the filelists or the test list: `dv-repo-orientation`
  maps the machinery first, and this skill assumes that map exists.
- You are adding one normative rule to a passive checker someone else wrote, rather than standing up
  a whole agent: `dv-protocol-checker-rule`.
- The interface is a register bus and the symptom is a register access: `dv-ral-bringup` owns the
  adapter, the predictor and the register model. Do not re-derive them here.
- The new files exist and the build breaks on them: `dv-build-filelist-hygiene`. The new checker
  fires and you need the first real error out of a log: `dv-sim-log-first-error`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Reference agents | [[FILL: the two agents already in our tree closest in shape to the one being added, by path, and confirmation that both are current rather than legacy]] | block DV owner |
| Base classes | [[FILL: which base classes our components extend — ours or UVM's directly — and where those files live]] | DV infra owner |
| Interface contract | [[FILL: the signal list, clocking and reset for this interface, and the document and clause that define the protocol]] | design owner |
| Connection convention | [[FILL: how a testbench hands a virtual interface and a configuration object to an agent here, which keys and scopes are used, and who sets them]] | DV infra owner |
| Checker placement | [[FILL: where end-to-end checking lives here — one scoreboard per agent, one environment-level scoreboard, checks inside the monitor, or a reference model — and which of those this environment uses today]] | block DV owner |
| Prediction source | [[FILL: what predicts the expected transaction for this path — an existing model in the tree, a model behind a DPI boundary, an algorithmic description, or nothing yet]] | block DV owner |
| Coverage ownership | [[FILL: whether functional coverage for an interface lives in the agent, in a separate subscriber, or in the test, and where the coverage plan for this interface is written]] | coverage owner |
| Acceptance gate | [[FILL: what a new agent must show before the nightly regression will take it, and who reviews it]] | verification lead |

Three pack-wide facts are read from `_shared/team-profile.md` rather than re-asked: **Filelist
convention** (step 8 uses it to locate where the new files belong), **Area to owner map** and
**Sign-off** (step 9). That file is one Read, taken in step 8 and reused by step 9.
**Acceptance gate is narrower than the profile's Sign-off** — sign-off is what closes verification of
a block on stated evidence; this asks only what one new agent must show before the nightly will take
it. If they are the same answer for your team, record that rather than assuming it.

**If a slot is unfilled, stop and ask. Do not guess a convention** — an invented base class,
configuration key or scoreboard location produces code that reads cleanly to you and is rejected by
whoever owns the environment, which is the outcome this skill exists to prevent.

## Retrieval budget — read this before opening anything

Testbench source is smaller than a log and far more tangled; the failure here is reading four
thousand lines of class hierarchy and still not knowing what the house does.

1. **Grep, Read and Glob work on files on disk.** A class body pasted into the conversation cannot be
   searched. Ask for its path, or say plainly that the conventions were read from a fragment and mark
   every rule resting on it provisional.
2. **Never open a testbench file with Read first.** **Glob** to locate, **Grep** for a line number,
   then **Read** a bounded window around it.
3. The whole exercise is capped at **4 Globs, 14 Greps and 10 windowed Reads of about 80 lines**,
   allocated: step 1, 2 Globs and 2 Greps; step 2, 2 Greps and 4 Reads; step 3, 1 Glob and 1 Grep;
   step 4, 2 Greps and 2 Reads; step 5, 2 Greps and 1 Read; step 6, 2 Greps and 2 Reads; step 7, 1
   Grep; step 8, 1 Glob, 2 Greps and 1 Read. Step 8's Read is `_shared/team-profile.md`, which step 9
   reuses rather than reopening; step 9 opens nothing of its own.
4. **The paired Greps assume a shared parent, and step 1 settles it.** Five of those fourteen — two
   in step 4, two in step 6, one in step 8 — are written as "**Grep** both reference agent
   directories". Each is genuinely one call only where the two paths in the **Reference agents** slot
   sit under a common parent holding those two agents and nothing else the pattern would also match.
   Where they do not, each of the five becomes one call per directory and the Grep cap rises to
   **19**; no other line of the budget moves. Widening a pattern to reach both from one call instead
   only trades a budget overrun for a Grep too broad to trust, which is item 6.
5. **Two files per convention, never one.** A rule seen in one file is a coincidence; seen in both
   reference agents it is the house style. That pairing is what the Read budget buys.
6. A **Grep** returning more than about 150 hits is too broad — anchor it, or scope it to one
   directory, before reading anything around the hits.
7. **Stopping rule.** Stop when every rule the new files need is in the contract with two citations
   and the checker note names both sampling points and its end-of-test rule, or when the budget above
   is spent. Whatever is still open then is a numbered question in step 9, never an inference.
8. **State what you covered** — which files were opened, and which rules rest on a single sibling. An
   unstated shortcut is far worse than a stated one.

## Procedure

### 1. Confirm the two reference agents are current and actually in the build

**Glob** each path in the **Reference agents** slot — one call each — and record the file inventory
without opening anything. A tree that still compiles but appears in no filelist is a dead agent, and
copying its style propagates an abandoned convention into a file nobody will accept.

While both paths are in front of you, settle the question budget item 4 depends on and write the
answer down: do these two directories sit under a common parent that holds them and nothing else a
class-name or macro-name pattern would also match? That answer, not a hope, is what lets the five
paired Greps in steps 4, 6 and 8 cost one call each instead of two. It costs no tool call — the Glob
results already carry it.

**Grep** the filelist entry point for each agent's package or directory name, one Grep per agent.
"Absent from the filelists I opened" is the honest claim; "absent from the build" is not one you can
make yet. If neither reference agent is in the build, stop and ask the block DV owner for a pair that
is — there is nothing here to derive from.

### 2. Derive the conventions contract from the pair, not from the cookbook

**Grep** each agent directory once for class declarations to get every class name and its file
without opening a line — two Greps. Then spend **four windowed Reads**: the agent class in each
sibling, and the transaction item in each.

What is identical across both is the convention; what differs is content. Record one rule per line:
file and class naming, directory layout, which base class each component extends, the registration and
field-automation idiom, the file header or include guard, the analysis port and export names, and
where the active-versus-passive decision is consulted. Cross-check the extends against the **Base
classes** slot — siblings that disagree with the slot are themselves the finding, and it belongs to
whoever owns those base files.

```
rule       : <the convention, stated so a reader can obey it without asking>
seen in    : <sibling A file and line> and <sibling B file and line>
applies to : <which of the new files it constrains>
```

Where the two siblings disagree, prefer the one the current test list points at and record the
disagreement as a question, not as a decision you made.

### 3. Pin the transaction item to the interface contract before drafting anything else

Every other file depends on the item, so getting it wrong costs a rewrite of all of them. Take the
signal list, clocking and reset from the **Interface contract** slot, **Glob** for the interface file
to see whether one already exists, and **Grep** its name once to find who else uses it.

Then decide, per field and in writing: driven or observed; randomised or set; compared or ignored.
The third is the column people skip, and a field carried in the item but excluded from the comparison
differs silently for the life of the agent — so it goes into the contract explicitly.

The protocol document named in that slot is very likely something **Read** cannot open. If so, ask
the design owner for the field widths and the legal ordering, record who supplied each, and mark any
rule resting on them provisional. A width with no file and no line must never be written up as though
it had one.

### 4. Draft the driver, monitor and sequencer against the sibling's idiom

**Read** one bounded window of sibling A's driver and one of its monitor. Then **Grep** both
directories for the driver handshake idiom and for the analysis port declaration — two Greps where
step 1 found a shared parent, four where it did not — instead of reading sibling B's copies, which
the budget will not stretch to.

Four decisions get made explicitly and written into the contract, because each fails silently:

- which handshake pairing the siblings use, and whether the completion call sits at the start or the
  end of the transfer
- whether the driver drives through a clocking block or the raw signals, and which of those the
  monitor samples
- what the monitor does with a part-assembled item when reset asserts
- that the monitor is built unconditionally, and the sequencer and driver only when active

Handoff: ask the engineer to elaborate the environment with the new agent instantiated in both the
active and the passive configuration and to give you the path to each build log. Elaboration is the
cheapest place to find a connection that was never made, and the agent cannot start one.

### 5. Draft the connection the way this environment already connects agents

**Read** the environment file that builds a reference agent, then **Grep** it twice against the
**Connection convention** slot: once for the key strings, once for the calls that consume them.

Copy the scope and key shape exactly, wildcards included. A set and a get whose scopes do not agree
is the most common wiring failure in a new agent, and the mismatch is symmetric — either side can be
the mis-scoped one, and neither reports anything: the get returns zero, the handle keeps its default,
and the first access is a fatal naming the component rather than the key. Draft every get with its
return value checked and the key printed on failure, and say in the contract that you did.

### 6. Design the checker end to end before drafting a line of it

The **Checker placement** slot says where this belongs; do not introduce a second scoreboard style
beside an existing one. Answer these six in writing before any code:

1. **What is compared against what.** Name both endpoints and the file each is observed from. If both
   come from one monitor, the checker compares that monitor with itself and can never fail.
2. **Where each side is sampled** — clocking block or raw signal, and which edge. Name the two
   separately; they may differ only if you say why.
3. **How items are matched** — in order, by an id into an associative array, or inside a time window.
   Name the field the id comes from.
4. **What happens to an item that never matches.** Every checker needs an end-of-test drain check
   reporting the depth of both queues, in a named phase, even when the depth is zero.
5. **What reset does to the checker** — which queues are flushed, and whether items in flight across
   reset are expected to be dropped or completed.
6. **What the checker deliberately does not check.** This is the list the next person needs and the
   one nobody writes down.

Only then **Read** one sibling scoreboard, **Grep** both directories for the subscriber idiom and for
the reporting method — two Greps under step 1's shared parent, four without it — and **Read** the
second scoreboard if the reporting idiom is still ambiguous.

### 7. Choose what predicts the expected value, and say what it cannot predict

**Grep** once for whatever the **Prediction source** slot names, then take the matching case:

- **An existing model in the tree.** Reuse it and cite the file. Do not write a second one.
- **A model behind a DPI boundary.** The agent cannot usefully read that source inside this budget —
  record a handoff and ask the block DV owner for its argument list and ordering guarantees.
- **An algorithmic description.** Draft the prediction in SystemVerilog and mark it unverified until
  one real run agrees with it.
- **Nothing yet.** Then this is not an end-to-end checker. Say so plainly and scope the deliverable to
  a protocol checker plus a transaction-count check rather than letting it be called end-to-end.

Whatever the source, list the transformations it does **not** model — reordering, latency,
arbitration, error injection, clock-domain crossing. Those are the checker's blind spots and they
belong in the contract, not in someone's memory.

### 8. Work out where the coverage and the new files belong

The **Coverage ownership** slot decides where the covergroups go; **Grep** the reference agent
directories once for the covergroup idiom — one Grep under step 1's shared parent, two without it —
and write the drafted covergroups to match it. Sampling a covergroup in the monitor and again in a
subscriber double-counts every bin, and the number looks better for it.

Then locate the position the new files take in the build. Nothing here edits the build: this step
produces a filelist line and the place it goes, and the engineer applies it. **Read**
`_shared/team-profile.md` for the **Filelist convention** — which directive nests one list inside
another, and what a relative path resolves against — then **Glob** the filelist entry point and
**Grep** it once for a reference agent's package to find the position your new package must take
relative to it. Package order is load-bearing: a package analysed before one it imports fails on a
type that is perfectly well declared.

Handoff: ask the engineer to add the new package at exactly that position, compile it on its own, and
give you the paths to the filelist diff and the build log — the diff because a position you named and
a position they applied are two different facts, and the agent can read neither into the tree itself.
Take any compile or elaboration break to `dv-build-filelist-hygiene`.

### 9. Write the plan, the handoff block and the coverage line

```
agent       : <the new agent's name and the interface it drives>
refs        : <the two Reference agents by path, and what was actually opened in each>
contract    : <n rules, each citing two sibling files with line numbers>
item        : <the transaction class, its fields, and which of them the checker compares>
active      : <what the active configuration creates, and what the passive one creates>
connection  : <the key and scope the environment sets, and the file and line it was copied from>
checker     : <where it lives, and what is compared against what>
sampled     : <the sampling point for each side, named separately>
matching    : <in order, by id, or windowed — and the field the id comes from>
unmatched   : <what the end-of-test check reports, and in which phase>
model       : <what predicts the expected value, and the transformations it does not model>
not checked : <what this checker deliberately does not check>
gate        : <what the Acceptance gate slot requires, and which of those items are still open>
owner       : <who this checker's failures route to, from the profile's Area to owner map, and who accepts the agent per its Sign-off row>
coverage    : <which files were opened, which rules rest on one sibling only, what the budget did not reach>
open        : <numbered questions, each naming the person who answers it>
```

The `gate` line has a method rather than a judgement, because no earlier step retrieves against it:
take the **Acceptance gate** slot item by item and, for each item, name the line of this plan that
already satisfies it. An item with no such line is open, and it goes into `open` against whoever
closes it. That is the whole of the slot's use — it is the one slot answered from the finished plan
rather than from the tree.

Leave a field empty rather than filling it plausibly. An empty `open` list after a first agent means
the questions were answered by invention — there are always some, and they are far cheaper asked now
than found in review.

## Gotchas

- **The monitor is built in both configurations; the sequencer and driver only in the active one.**
  The active-versus-passive flag gates stimulus, not observation. A monitor built inside the active
  branch makes every passive instance blind, and the scoreboard downstream then reports zero compared
  and zero mismatches — on the console, indistinguishable from a clean pass.
- **Where the completion call sits decides whether the driver can ever overlap transfers.** The
  blocking request-and-complete pairing will not release the next item until completion is signalled,
  so signalling only at the end of a whole transfer serialises a bus the protocol allows to pipeline.
  Fetch-and-respond is the other legal shape; mixing the two, or completing one item twice, produces
  a hang or an error that names neither.
- **A monitor that reads the driver's variables is not a monitor.** It agrees with the driver by
  construction and stays green while the pins carry something else. Its only inputs are the signals.
- **A driver on the clocking block with a monitor on the raw signals disagrees by one cycle.** A
  clocking block output is not driven *at* the edge — it lands an output skew after it, in the
  non-blocking region by default — while a monitor sampling the raw signal at that same edge reads the
  value that was there before it, and books the transfer a cycle late. Reverse the pair and the offset
  reverses with it: a clocking block *input* is sampled an input skew ahead of the edge, so a value a
  raw-signal driver placed on that edge is not visible to the monitor until the next one. Both sides
  are self-consistent alone, and the off-by-one surfaces as data corruption in the first transaction
  after any pipeline change. Pick one sampling discipline for both sides and write down which.
- **A scoreboard with no end-of-test drain check cannot fail.** Items left in the expected queue when
  the test ends are dropped transactions. If nothing counts that queue in the final check, a design
  that swallows everything after the first packet passes cleanly. Print the depth even when it is
  zero: a printed zero is evidence, a silent zero is nothing.
- **Both sides of a comparison must not come from the same monitor.** Expected comes from the
  input-side monitor plus a model, or from the sequence's own recorded intent — never from the stream
  that also produces actual.
- **Out-of-order traffic turns a queue-based scoreboard into one bug reported many times.** As soon as
  the protocol allows multiple outstanding transfers, match on the id into an associative array. A
  first-in-first-out compare mismatches on the first reordered pair and on every pair after it, so the
  report reads as a catastrophe rather than as a matching-policy mistake.
- **Reset is a transaction, not an interruption.** A monitor that does not abandon the item it is
  assembling when reset asserts stitches a pre-reset half onto a post-reset half and publishes
  something that never appeared on the pins. The scoreboard then spends a day chasing a phantom.
- **An analysis write is a SystemVerilog function and cannot consume time.** Work that needs to block
  belongs in a task started from the run phase, fed by a queue or an analysis FIFO the write pushes
  into. Trying to wait inside the write is why scoreboards get rewritten in their second month.
- **Field-automation macros compare every field you registered**, including the ones that are supposed
  to differ — timestamps, ids, delays. A team that hand-writes its comparison method usually did it
  for exactly that reason. Whichever the two reference agents do, do that.

## Human verification — what a wrong answer looks like

Before handing the plan to a reviewer, check:

- every rule in the conventions contract cites **two** sibling files with line numbers; a rule with
  one citation is a coincidence written down as a convention
- the checker's two sides trace to two different observation points, and neither is the driver
- the monitor is created in the passive configuration, and you can name the line that makes it so
- the end-of-test check names a phase and prints a count even when that count is zero
- no base class, configuration key, macro or port name in the plan is anything other than a string
  that appeared in a real Grep or Read result — resemblance to another team's convention is not
  evidence
- the `not checked` line is not empty; a checker with no stated blind spots has unexamined ones
- the coverage line says which rules rest on a single sibling, and what the budget did not reach
- nothing in the plan reads as though a file was placed, a filelist edited or a package added — the
  plan names a position and the engineer applies it; if you have no filelist diff back, say so rather
  than writing the position up as though it had landed

A wrong answer is a complete, tidy, textbook-correct agent — right UVM, wrong house — that the
environment owner rewrites. The second shape is a scoreboard comparing one monitor's output against
that same monitor's output, which has passed every run since the day it was written and always will.

## Done when

A reviewer can check your plan against the two reference agents line by line, the checker's blind
spots are written down rather than discovered, and every remaining unknown is a numbered question
with a name against it.
