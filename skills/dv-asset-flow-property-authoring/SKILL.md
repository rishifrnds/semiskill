---
name: dv-asset-flow-property-authoring
description: Turn an asset inventory and threat model into a checkable flow specification — legal sources, forbidden sinks, expected blockers — and the property list that proves each row. Use when the security spec exists but no properties do, when someone asks whether a key, a seed, an entropy source or a debug-unlock token can reach a bus, a debug port or a scan chain, when a reviewer asks which property covers an asset, or when a leak was found in review and you need the property that should have caught it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "Asset Flow Specification: Sources, Sinks, Blockers and the Property List"
  semiskill-function: design-verification
  semiskill-role: security-verification-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-02-17
  semiskill-tags: security, assets, information-flow, formal, properties, threat-model, debug-unlock, scan
---

# Asset Flow Specification: Sources, Sinks, Blockers and the Property List

An asset inventory says *what* is secret. A threat model says *who* wants it. Neither is checkable,
and the gap between them is where security verification quietly becomes a review meeting instead of a
sign-off. What closes the gap is a flow specification — for each asset, in each lifecycle state, the
legal sources, the legal residences, the closed list of forbidden endpoints, and the blocker that is
supposed to stand between them — and then a property list in which every row of that table has a
named obligation, a named discharge route, and a written statement of what it still misses.

The deliverable is three things: **the flow rows, the property list, and an honest coverage line**.
Not a claim that the block is secure. This procedure reads specs and RTL and drafts text; it cannot
prove anything, and every proof is a handoff to a person with a licence.

## When to use something else

For turning a spec chapter or databook into a feature table before any of this exists, use
`dv-spec-feature-extract`. For one normative protocol sentence that needs a numbered passive checker
and a negative test, use `dv-protocol-checker-rule`; for one that needs a directed compliance test,
`dv-compliance-test-authoring`. Asset flow is not a single clause, which is why neither of those
fits it. For deciding what may leave your hands in a log or a customer package — artifact egress
rather than flow inside the design — use `dv-artifact-redaction-egress`. For the fault-injection
analogue on protected structures, use `dv-error-injection-ras`. Once a property has actually failed
and you need to know which signal went wrong first, go to `dv-signal-trace-localisation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Asset inventory | [[FILL: where our asset inventory and threat model for this block live, and whether each is a file that can be read or a page a person must read out to you]] | security architect |
| Security boundary | [[FILL: which module instance counts as the inside of the boundary for this block, and which ports are the boundary]] | block owner |
| Lifecycle states | [[FILL: our lifecycle state names, which of them permit debug, and which permit test or scan]] | security architect |
| Observation points | [[FILL: the endpoints our policy counts as observable at that boundary — which read-data path, which debug or trace port, which scan interface, which pins]] | security architect |
| Scan handling | [[FILL: how flops holding an asset are handled in scan for us — separate chain, blanked, cleared on scan enable, or nothing yet — and who owns that decision]] | DFT owner |
| Erasure requirement | [[FILL: which event must clear an asset out of its holding register for us, within how many cycles, and of which clock]] | security architect |
| Property files | [[FILL: which property language our security properties are written in, where those files live, and how a property is numbered]] | DV infra |
| Path-proof tooling | [[FILL: which tool class we have for path or taint proofs, and whether we have a licensed secure-path mode or must build the two-copy model by hand]] | DV infra |

Two facts this skill needs are pack-wide and live in `_shared/team-profile.md` — read them from there
rather than asking again: **Area to owner map**, which turns a failing row into a person in step 8,
and **Sign-off**, which says who may accept a row that no property covers. The profile's log-related
rows are deliberately *not* repeated here, because this skill never opens a simulation log; it reads
the inventory, the RTL and the existing property files.

**Observation points is narrower than the security boundary**, and the two are not interchangeable.
The boundary says which module is the inside; observation points says which specific endpoints on and
beyond it your policy treats as visible to an attacker. A boundary with no enumerated endpoints
produces properties that cannot be written down.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented lifecycle state name
or an invented erasure latency produces a property that passes, gets signed off, and covers nothing.

## Retrieval budget — read this before opening anything

A security spec is long, an RTL tree is longer, and an asset name fans out across both. Work in this
order and stop when the budget is spent, not when the inventory runs out:

1. **Grep and Read work on files on disk.** If the inventory or the threat model arrived pasted into
   the conversation, ask for the path, or ask for the text to be saved and be given that path. Until
   a path exists you may reason over what you were shown by eye — but say that is what you did, and
   mark every row provisional. If it is a slide deck, a spreadsheet or a wiki page that **Read**
   cannot open, treat every fact in it as supplied by a person and attribute it.
2. Two **Glob** calls, and no more: one for the inventory and security spec named in the slot, one
   for the existing property files. Never open a spec with **Read** as the first move.
3. At most two windowed **Read** calls of about 80 lines in the inventory — the asset table, and the
   attacker or threat section. Anything else you want from it is a question for its author.
4. The forbidden-endpoint list in step 3 may spend **at most three Grep calls**, one per endpoint you
   cannot name from the Observation points slot alone.
5. Per asset, steps 4 and 5 spend **one Grep** for the asset name's fanout, **one Grep** for the
   blocker signal, and **at most two windowed Read calls** of about 40 lines — the declaration, and
   the blocker's driver.
6. **Four assets per pass.** That is the ceiling for the whole run: two Globs, eleven Greps, ten
   windowed Reads. A fifth asset is a second pass. Steps 2, 6, 7 and 8 are authoring and spend
   nothing.
7. If a **Grep** on an asset name returns more than about 150 hits, the name is a substring of
   something common — anchor it on a declaration keyword or a port suffix before opening anything.
8. Stopping rule: when the budget is spent, write the rows you have and the coverage line, and stop.
   A row invented past the budget is worse than a missing one, because a missing row is visible at
   review and an invented one gets signed.

## Procedure

### 1. Resolve the inventory, the boundary and the states to files on disk

Two **Glob** calls and at most two windowed **Read** calls, per budget rules 2 and 3. Come out of
this step with three written-down things: the path of the inventory, the module instance named in the
**Security boundary** slot, and the state names from the **Lifecycle states** slot with debug and
scan permission marked against each.

If any of the three came from a person rather than a file, say so now rather than in the last line of
the report. Everything downstream inherits that provenance.

### 2. One row per asset and per lifecycle state, not one row per asset

Reuse the windows step 1 already opened; this step spends no budget. For each asset in the inventory,
split it into one row per lifecycle state whose legality differs. A device key is unreadable in a
provisioned state and may be legitimately loadable in a manufacturing state, and a specification
keyed on the asset alone silently permits the only case anyone cares about.

Name each asset the way the **RTL** spells it, not the way the inventory spells it. The two disagree
more often than not, and every later **Grep** is against the RTL spelling.

### 3. Close the forbidden-endpoint list before writing any property

An open-ended "must not leak" is not checkable. Start from the **Observation points** slot and turn
it into a numbered, closed list against the named boundary. The endpoints that get missed are always
the same four:

- the read-data path back to whichever bus reaches this block, including any lower-privilege window
- the debug or trace port, and any mirror register a debugger samples
- the scan interface — every flop holding an asset is observable there, which is why the **Scan
  handling** slot exists and why its answer is an obligation on the DFT owner, not an assumption
- primary outputs and any pin that is muxed onto a shared pad in a test mode

Spend **at most three Grep calls** here, one per endpoint whose driver you cannot name from the slot.
Then write the boundary next to the list. A list closed against a block boundary says nothing about
an integration that hangs this block's key bus off a chip-level debug mux; mark those endpoints as
owned by whoever verifies the level above, rather than silently including or excluding them.

### 4. Derivation closure — find what actually carries the asset

**One Grep** per asset on its declared name. Classify every hit as one of four things: a custodian
(it is stored there), a legal sink (it is consumed there), a forwarding assignment (a new name now
carries it), or a comparison (it is only tested there). Every forwarding assignment adds a name.

Follow that closure **two levels deep** on this one Grep and no further. Record the names you stopped
at rather than implying the closure is complete — a round-key expansion, a fuse shadow, a retention
copy and a debug mirror are all the asset, and a property list keyed on the original flop alone
covers one flop.

### 5. Name the blocker, its armed condition, its scope and its latency

**One Grep** for the blocker signal and **at most two windowed Read calls** per asset — the asset's
declaration, and the blocker's driver.

A blocker is only usable in a property if you can state four things about it: the signal, the
condition under which it is armed, what it covers (one endpoint, one register, or the whole path),
and its latency — how many cycles of which named clock pass between the arming event and the endpoint
being safe. The **Erasure requirement** slot supplies the latency the policy demands; the RTL
supplies the latency it actually has, and the gap between them is a finding.

Two things that look like blockers and are not. An address-decode hole is a property of the decoder,
not of the asset — change the decode and the leak reappears with nothing failing. A register declared
write-only in the register spec is a model policy, not a gate — the RTL read path may still return
the value. Record either as `no blocker found` rather than as a blocker.

### 6. Write the property list — six obligations per row

Authoring only; no budget. Each forbidden endpoint on each row generates properties from this fixed
set. The `flow rule` column is the vocabulary the handoff block in step 8 uses.

| Flow rule | What the property must state | Route |
|---|---|---|
| `never-reach` | with the asset held symbolic, the value at the endpoint does not vary with it, in every cycle the row's states are active | path-proof |
| `blocker-armed` | whenever the row's permitting condition is false, the blocker signal is asserted | trace-proof |
| `blocker-effective` | while the blocker is asserted, the endpoint holds a fixed value that does not vary with the asset | path-proof |
| `no-bypass` | no path other than the enumerated legal sinks carries the asset across the boundary | path-proof |
| `erasure` | after the terminating event, every custodian holds a non-asset value within the slot's latency and holds it thereafter | trace-proof |
| `source-legality` | a custodian's value changes only when driven by one of the enumerated legal sources | trace-proof |

The distinction that decides whether the list is worth anything: **`never-reach` and `no-bypass` are
not single-trace properties and cannot be written as ordinary assertions.** An assertion compares
values on one execution; non-interference is a statement about *two* executions that differ only in
the asset. Discharge it with the tool's path or taint mode if the **Path-proof tooling** slot says we
have one, and otherwise with a two-copy model — two instances of the block, identical stimulus,
different asset value, endpoints asserted equal. Say which of the two you are asking for, because
they cost very different amounts and the second doubles the state space.

Number each property in whatever scheme the **Property files** slot records, and draft it in that
language rather than a generic one. Do not invent a numbering scheme; if the slot is unfilled, leave
the number blank and say so.

### 7. Write down what each property rests on, and what it still misses

Every constraint added to make a check converge is a hole, and the constraint that makes a security
property converge is very often the attack itself. Assuming debug is disabled to close a proof
deletes exactly the case the property was written for.

So each property carries two fields nobody enjoys writing. `assumes` lists every constraint, each
with the named person who owns it — an assumption with no owner is not an assumption, it is a guess.
`misses` says what a pass still would not rule out: a timing side channel, an endpoint outside the
boundary, a state the constraints excluded, or a path the derivation closure did not reach.

### 8. Hand it over

Three blocks. One flow row per asset and state:

```
asset      : <the name as the RTL spells it, its width, and the file and line it is declared at>
states     : <the lifecycle states this row applies to>
sources    : <every legal origin, each with file and line>
custodians : <every register or memory it legally rests in, each with file and line>
allowed    : <the endpoints it may legally reach, each with file and line>
forbidden  : <the numbered endpoints from step 3 it must never reach>
blockers   : <per forbidden endpoint - the signal, armed when, scope, latency and clock>
derived    : <downstream names that carry the asset, and the names closure stopped at>
boundary   : <the module instance this row is written against>
```

One property row per obligation:

```
property   : <number in our scheme, or blank, and a short name>
row        : <the asset and states row above>
flow rule  : never-reach | blocker-armed | blocker-effective | no-bypass | erasure | source-legality
endpoint   : <the numbered forbidden endpoint, or none for erasure and source-legality>
blocker    : <the gating signal and the condition that arms it>
statement  : <what must hold, from when, for how long, in which clock's cycles>
discharge  : path-proof | trace-proof | directed-test | inspection | undischargeable-here
assumes    : <every constraint the check rests on, each with the person who owns it>
misses     : <what a pass of this property still would not rule out>
owner      : <who fixes a failure, from the profile's area-to-owner map>
```

And one summary, which is the part a reviewer reads first:

```
spec coverage : <n of m inventory assets have a full row; which were not opened and why>
endpoint list : <k endpoints, closed against the named boundary; what was left to the level above>
properties    : <p drafted; q of them undischargeable-here, and what each needs>
from a person : <every fact that came from someone rather than from a file, and who>
open questions: <numbered, each addressed to a named person>
```

To get any of it discharged, **ask the engineer to run the proof or the directed test and give you
the path to the tool's report**. The agent cannot start a formal engine or a simulation, and must
never write down what one would have said.

## Gotchas

- **A value comparison is not a flow property.** An assertion that the endpoint differs from the
  asset passes on an all-zero key, passes when the leak is one bit per cycle, and passes when the
  leak is transformed — bit-reversed, byte-swapped, or a truncated digest. The checkable form is
  independence, and independence is a two-execution statement, so no ordinary assertion states it.
- **The derived value is the asset.** A list keyed on the key register and not on the round-key
  expansion, the fuse shadow, the retention copy or the debug mirror covers one flop. Do the closure
  in step 4 before writing a single property, and record where you stopped.
- **Scan is the sink whose evidence is not in your file set.** The chain is stitched after RTL
  sign-off, so the RTL you are reading shows no leak at all and never will. That has to leave your
  hands as a written obligation on the DFT owner with a named blocker, not as a sentence in the
  assumptions.
- **A blocker with no latency is not a blocker.** "Cleared on lifecycle exit" needs the event, the
  cycle count, the clock that counts them, and what the value is meanwhile. A pipeline stage holding
  the last key for three cycles after the clear is a real leak that an eventually-property passes.
- **Reset does not erase.** Retention flops, always-on domains and fuse shadows survive a functional
  reset by design. Check which reset and which power domain before writing the `erasure` property, or
  it proves the wrong thing about the wrong flop.
- **X is a false negative in simulation and a false positive in formal.** A key register cleared to X
  compares unequal, so a dynamic negative test passes on a design that leaks. Formal runs the other
  way: an unconstrained input is symbolic, so counterexamples arrive in states the design can never
  actually enter, and the fix is a constraint — which is exactly the thing step 7 makes you write
  down and get owned.
- **Directed negative tests prove the blocker works on the path you thought of.** They are still
  worth writing, because they catch a blocker tied off at the wrong constant, which a proof under the
  wrong constraint will not. They cannot close a forbidden-endpoint row on their own — mark those
  rows `directed-test` in the block and let the reviewer see it.
- **The same asset changes legality between lifecycle states, and the transition is its own case.**
  Most specifications cover the states and skip the edge. The interesting window is the one where the
  new state's rules apply but the old state's data has not been cleared yet.
- **An asset that is only ever compared is still an asset.** A debug-unlock value that is never
  stored but is compared against a fuse still leaks through the comparison's timing and through the
  granularity of the response — a per-byte early-out turns a search of the whole space into a search
  of one byte at a time. Record it as an endpoint with `misses` naming the side channel, rather than
  leaving it off the list because no wire carries the value.
- **A closed endpoint list is only closed against one boundary.** Rows written at block level say
  nothing about the integration above. Naming the boundary next to the list is what stops a
  block-level pass being quoted as a chip-level result six months later.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every `never-reach` and `no-bypass` row is routed to a path-proof or a two-copy model, and none of
  them is written as a plain value comparison
- the forbidden-endpoint list is numbered, closed, and has the boundary written next to it — and scan
  and debug are both on it or both explicitly assigned to another owner
- every blocker carries all four parts: signal, armed condition, scope, and latency with its clock
- the derivation closure names where it stopped, and no row implies a closure that was not done
- every `assumes` entry has a person's name against it, and no property is discharged under an
  assumption that nobody owns
- the coverage line's denominator is the number of assets in the inventory, not the number you got to
- every fact that came from a person rather than a file is attributed as such

A wrong answer typically asserts that the endpoint is not equal to the asset and calls that a flow
property; writes rows for the key register while the round keys, the shadow and the debug mirror go
unmentioned; states an erasure requirement with no cycle count; or reports a clean proof that was
closed by constraining away the debug enable the whole property existed to test.

## Done when

Every asset in the inventory has either a flow row with a numbered property behind each forbidden
endpoint, or a line in the coverage block saying why it does not — and the sign-off owner can see
which is which without asking you.
