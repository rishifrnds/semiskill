---
name: dv-cdc-rdc-triage
description: Triage a clock- or reset-domain-crossing report by verifying the setup before the violations, separating constraint noise from real crossings, clustering by domain pair, and drafting object-based waivers a sign-off reviewer will accept. Use when a CDC or RDC report comes back with thousands of violations, when someone says the report is all noise, when a block that was clean on its own turns dirty at the top level, when a waiver keeps getting bounced, or when you are asked to sign off crossings you did not write.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: CDC and RDC Triage, Setup-Noise Separation and Object-Based Waivers
  semiskill-function: design-verification
  semiskill-role: static-signoff-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-09
  semiskill-tags: cdc, rdc, static-signoff, clock-domain, reset-domain, waivers, constraints, triage
---

# CDC and RDC Triage, Setup-Noise Separation and Object-Based Waivers

A first crossing report on a real block comes back with thousands of violations, and most of them are
the tool describing your setup rather than your design. The engineer who starts at violation one and
works down spends a week and signs off nothing; the engineer who settles the setup first watches the
same report collapse to a few dozen crossings that are worth an argument.

The output is three things: **a setup verdict, a ranked set of domain-pair clusters, and waivers
written against named objects** — plus one line saying how much of the report that rests on.

## When to use something else

If the tool's own design read failed — missing files, unresolved modules, a package it could not find
— that is a build break wearing a static-analysis costume, and it belongs to
`dv-build-filelist-hygiene`; step 1 routes it there. A failing *simulation* log starts at
`dv-sim-log-first-error`, a whole night of them at `dv-regression-triage-routing`. If you cannot yet
find the setup files or the report in an unfamiliar tree, spend an hour on `dv-repo-orientation`.

Note the direction that does **not** work: RTL simulation propagates a value cleanly across a
crossing instead of resolving it either way, so a real crossing rarely shows up as a test failure. A
clean regression is not evidence about crossings, and this report is not evidence about function.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Report location | [[FILL: where our crossing reports and the tool's setup log land, and which of those two files carries the setup messages]] | static sign-off owner |
| Setup files | [[FILL: which constraint and setup files this block's analysis reads, and which one wins when two of them disagree]] | static sign-off owner |
| Clock groups | [[FILL: where the record of which clocks are genuinely synchronous lives, and what makes a pair synchronous here — common source, integer ratio, or a declared assumption]] | clocking or integration owner |
| Reset architecture | [[FILL: which resets are asynchronous to which clocks, which ones have their deassertion synchronised, and where that is written down]] | RTL designer |
| Mode tie-offs | [[FILL: the mode, test and bypass signals that must be constrained for a functional analysis, and the value each is held at]] | DFT engineer |
| Synchroniser cells | [[FILL: the module or cell names our recognised synchronisers use, and how the tool is told about them]] | static sign-off owner |
| Report vocabulary | [[FILL: the check names our tool prints for each violation category, and the messages it prints when it infers a clock, leaves a port unconstrained, or black-boxes a module]] | static sign-off owner |
| Waiver store | [[FILL: where waivers live, their format, and the fields ours are required to carry]] | static sign-off owner |

Two pack-wide facts come from `_shared/team-profile.md` rather than being asked again: **Area to
owner map** fills the `owner` line in step 8, and **Sign-off** fills the `signed` line in step 7.

**Report location is not the profile's Log location.** That row records where *simulation* logs land;
a static tool writes elsewhere. If the two are the same directory here, say so in this slot rather
than assuming it. For the same reason the profile's Fatal markers and Pass marker are deliberately
not reused — a crossing report has neither, and Greping one for a simulation marker returns nothing,
which reads exactly like a clean result.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented clock group is the
worst mistake available here: it deletes real crossings and leaves the report looking better.

## Retrieval budget — read this before opening anything

A crossing report is a database dump, not a log. Tens of thousands of rows is normal, and the counts
matter far more than the rows.

1. **Grep and Read work on files on disk.** If the report arrived pasted into the conversation, ask
   for the path, or for the text to be saved and be given that path. Until a path exists you may
   reason over the pasted rows by eye — but say so, and the setup verdict in step 2 is `unverified`.
2. **Never open the report with Read first.** One **Glob** to find the files, **Grep** for counts and
   line numbers, then bounded **Read** windows.
3. The allowance for one report is **one Glob, eight Greps, and six windowed Reads of about 60
   lines**: step 1 one Grep; step 2 three Greps and two Reads; step 3 one Grep; step 4 two Greps and
   one Read; step 5 one Grep and two Reads. That leaves one spare Read, and steps 6 to 8 open nothing
   — they reuse windows already read.
4. A **second or third** cluster taken to structural depth costs one more Grep and two more Reads
   each on top of that. A fourth is out of budget: stop, and record the rest as ranked but unopened.
5. If a Grep of the report returns more than about 300 hits, do not read them. That count **is** the
   finding — three hundred violations sharing one domain pair are one constraint, not three hundred
   bugs. Narrow to the distinct pairs and carry on.
6. Stopping rule: if the allowance is spent and the setup is still unverified, stop there. Classify
   nothing against an unverified setup; nobody downstream will remember that it was provisional.
7. State what you actually covered, in the `coverage` line of step 8.

## Procedure

### 1. Get the report, the setup log and the run identity onto paths

**Glob** under **Report location** for both files. The setup log matters first: the report says what
the tool found, the setup log says what the tool believed, and a report read without it is a list of
answers to an unknown question.

Then **one Grep** of the setup log's header for the tool version, the design top, the analysis date,
and — the part people skip — the constraint and setup files it actually read. Compare that against
**Setup files**. A file everyone assumes is applied but which is absent from the header was not
applied, and that alone can account for the whole report.

If the same header shows the tool failed to read the design — unresolved modules, a missing include,
a package it could not find — stop. That is a build problem and goes to `dv-build-filelist-hygiene`
with the first diagnostic verbatim and the phase its block accepts, `compile` or `elab`. A report
over a design that did not fully elaborate is evidence of nothing.

### 2. Verify the setup before you look at a single violation

Six checks, each cheap, each able to invalidate the whole report alone. Spend **three Greps** — the
tool's setup diagnostics, the clock and reset definitions actually applied, and the unresolved or
black-boxed instances, with strings from **Report vocabulary** — and **two Reads**: the clock-group
section of the authoritative file from **Setup files**, and the warning block in the setup log.

1. **Every clock defined.** A clock the tool inferred rather than being told about becomes a domain
   of its own, and everything reaching it becomes a crossing. Count the inferred ones.
2. **Clocks grouped correctly.** Clocks sharing a source and a phase relationship are one domain and
   their crossings are not crossings. Take the grouping from **Clock groups** and check it against
   where the clocks are generated — never against how quiet the report is.
3. **Mode and test signals constrained**, per **Mode tie-offs**. An unconstrained scan enable ties
   every domain together through the scan chain and makes the report largely fictional.
4. **Resets defined**, with their assertion style, per **Reset architecture**. Undefined resets make
   the RDC half of the report either empty or total, and both look plausible.
5. **Black boxes named and understood.** An unresolved module is not neutral — see the gotchas.
6. **Abstract or hierarchical block models current.** A top-level analysis over a model generated
   from an older revision answers last month's question; compare the stamps.

Write the verdict before going further:

```
setup       : verified | partial | unverified
report      : <path to the report, path to the setup log, tool version, analysis date>
inputs      : <setup files the header says were read, and any expected file missing from that list>
clocks      : <n defined; n the tool inferred; n primary inputs left unconstrained>
groups      : <the synchronous groups claimed, and what each claim rests on>
resets      : <n defined; which are asynchronous to which clock; which have synchronised deassertion>
modes       : <the mode and test signals constrained, and the value each is held at>
blackboxes  : <n unresolved instances, named, and what each one hides>
models      : <which abstract block models were used, and the stamp on each>
```

`verified` means every row came from a file; `partial` means one rests on somebody's word;
`unverified` means the report cannot yet be triaged. In that last case hand the setup gaps back and
**ask the static sign-off owner to re-analyse once they are closed, and to give you the path to the
new report**. The agent cannot start the tool and must not describe what it would have printed.

### 3. Separate the reset-domain question from the clock-domain one

RDC is not CDC with different nouns, and treating it as one is why reset crossings survive review. A
reset crossing exists when a source flop's asynchronous reset is not the destination flop's, **even
when both share a clock**: the source clears at a moment unrelated to the destination's capture edge,
so the destination samples a signal changing inside its own aperture. Deassertion is the tamer half —
that is what a reset synchroniser fixes, asserting asynchronously and releasing with the clock.

**One Grep** of the record named by **Reset architecture** gives, per reset in the report, which clock
it is asynchronous to and whether its deassertion is synchronised. Three structures fall out:

- A destination flop with **no reset at all**, fed by an asynchronously reset source, is a crossing —
  easy to miss, because nothing about the destination looks reset-related.
- A destination on a **different** asynchronous reset is a crossing, and the question that decides it
  is whether the two resets can ever assert independently.
- A destination on the **same** reset, or one provably asserted with it and released later, is the
  case that becomes a waiver. The argument is about ordering, so it belongs in `because` in step 7.

### 4. Cluster by domain pair, not by violation

**Two Greps** of the report: one for the check-name field, one for the domain-pair field, using the
names from **Report vocabulary**. Take the *counts*, not the rows. A cluster is one triple — source
domain, destination domain, check name — and the number of distinct triples sits two orders of
magnitude below the violation count and barely moves when the setup is fixed. Then **one Read** at the
head of the largest cluster, to see one real row.

Rank the clusters cheapest-and-largest first, not most-alarming first:

1. A cluster whose whole population shares one pair and one check — a single missing or wrong
   constraint. Fixing it removes the cluster and uncovers whatever it was hiding.
2. A cluster on a synchroniser the tool did not recognise: also a setup fix, per **Synchroniser
   cells**, and dangerous to leave, because the tool has stopped watching a real structure.
3. Unsynchronised **control** — a load enable, a request, a state-machine input. One bad capture
   changes state that never comes back.
4. Multi-bit **data** with no coherency mechanism.
5. Convergence and reconvergence around otherwise correct synchronisers.
6. Combinational logic feeding the first synchroniser stage.

`_shared/failure-signature-schema.md` is deliberately **not** used here: its `phase` field is a
simulation vocabulary, a static crossing happened at none of those moments, and forcing one produces
a string that matches nothing. The cluster triple is the stable key instead. What does transfer is
the schema's discipline — strip run-specific values, quote the rest verbatim, compare exactly.

### 5. Take one cluster down to the RTL and say what it actually is

**One Grep** for the destination object's name in the RTL, then **two Reads** of about 40 lines, one
at the source flop and one at the destination flop. Five facts are in play, and each changes the
answer.

| What you find | What it actually is | What it needs |
|---|---|---|
| One-bit control, no synchroniser | a real crossing | two flops in the destination domain, or the recognised cell from **Synchroniser cells** |
| One-bit control, hand-written chain the tool did not match | a recognition gap | name the cell in the setup; waiving it also waives the day it stops being one |
| Multi-bit bus, every bit through its own synchroniser | still a real crossing | gray coding, a synchronised qualifier holding the bus, or an asynchronous FIFO |
| Multi-bit bus changing one bit per transition | gray-coded, safe if that is enforced | a waiver whose `because` is the encoding, and something that fails if it breaks |
| Combinational logic between source flop and synchroniser | a glitch that can be captured | register in the source domain first, then cross |
| One source flop fanning into several synchronisers, recombining later | reconvergence | one synchronised qualifier gating the rest |
| Source inside a black box | unanalysed, not clean | resolve the module, or say plainly that this pair was never checked |

The fifth fact — whether the destination tolerates the crossing being wrong for one cycle — is
functional, is in neither window, and is the one a waiver has to answer. If the design owner is the
only person who can, **ask them and record that the answer came from a person, not from a file**.

### 6. Choose a setup fix, an RTL fix, or a waiver — in that order

Most rejected waivers are missing constraints wearing a waiver's clothes, and a reviewer who has been
caught by that once looks for it every time. Prefer, in order:

- **A setup fix**, when the tool was told something wrong or not told something true. One statement,
  applied to every violation the mistake produced, and it survives RTL edits.
- **A constraint stating the assumption**, when a signal really is quasi-static or gray-coded. The
  tool stops asking everywhere, and the assumption lands where reviewers read. Still an assumption
  and not a proof — see the gotchas.
- **An RTL fix**, when the structure is wrong. Much cheaper than a waiver that turns out false.
- **A waiver**, only for a crossing that is structurally real and functionally safe, where the
  argument is about behaviour no constraint can express.

### 7. Draft the waiver against objects, never against indices

A waiver keyed on a violation number, a report row or a source line stops matching the moment the RTL
moves, and it fails silently in both directions. Name objects.

```
waives       : <the check name, verbatim from the report>
objects      : <source and destination signals by full hierarchical name, and the module holding them>
domains      : <source clock or reset, destination clock or reset, named as the report names them>
waiver scope : block | top | both
because      : <the functional argument, in sentences a reviewer can disagree with>
backed by    : <the assertion, constraint, specification clause or review note that keeps it true>
holds if     : <the conditions under which it stops being true>
expires      : <a date, and what must be rechecked then>
signed       : <who accepted it, per the profile's Sign-off row>
```

Write it into the format named by **Waiver store**, carrying whatever extra fields that store
requires. Four things get a waiver bounced, and all four are avoidable:

- a wildcard over a whole module, which also waives everything added to it next quarter
- a `because` that says "reviewed and found safe" — a signature, not an argument
- a `waiver scope` of `block` used to sign the top level, where the neighbours' real clocks apply
- no `expires`, which turns a temporary exception into a permanent hole nobody remembers making

### 8. Write the cluster records and state the coverage

One block per cluster taken to depth, then one coverage line under the set.

```
cluster   : C1
pair      : <source domain to destination domain, exactly as the report names them>
rule      : <the check name, verbatim>
count     : <violations in this cluster, and the report total they came out of>
class     : design | infrastructure | unknown
root      : one-missing-constraint | one-structural-fix | many-independent | not-yet-known
sample    : <one violation row, verbatim, with both object names and its line in the report>
structure : <what the RTL does between the two flops, from the windows read in step 5>
owner     : <name from the profile's area map, or blank plus candidates>
action    : fix-setup | fix-rtl | waive | needs-a-human
evidence  : <file and line for every claim above; the word "person" for anything that came from one>
```

`class` is `infrastructure` when the cause is the setup or the tool, `design` when the RTL structure
is wrong, `unknown` until one of those is shown. The coverage line is not optional: "setup verified
from files; 3 of 41 clusters opened to RTL; 38 ranked and unopened; 2 pairs pass through an
unresolved black box and were never analysed" is a useful report. Silence about the 38 is not.

## Gotchas

- **The violation count is not a quality metric.** One ungrouped clock pair or one untied test signal
  produces thousands of them. The number that carries information is the count of distinct domain
  pairs, and it barely moves when the violation total collapses from four thousand to forty.
- **Missing grouping is loud; wrong grouping is silent.** Declaring two genuinely asynchronous clocks
  synchronous deletes their crossings from the report — it gets *cleaner*, which is what everyone
  wanted, and nothing prints. Check a grouping claim against where the clocks are generated.
- **Two-flop synchronisers on every bit of a bus do not make a synchronised bus.** Each bit is
  individually safe and the group is not: bits resolve on different destination edges, so the
  destination can latch a combination the source never held. Gray coding, a separately synchronised
  qualifier holding the bus stable, or an asynchronous FIFO — and the setup has to say which.
- **Separately synchronised signals that recombine are a new bug, not two solved ones.** Two control
  bits from one source domain, each correctly synchronised, can arrive a destination cycle apart, and
  logic combining them sees a state that never existed. Synchronise one qualifier and gate the rest.
- **Combinational logic in front of the first synchroniser flop turns a settling window into a
  glitch**, and a glitch too narrow to notice in simulation is wide enough to capture. Register in
  the source domain, then cross.
- **A black box is not neutral.** Crossings inside it are unanalysed and the report is quiet about
  them, which reads exactly like clean. Paths through it arrive at the boundary carrying whatever
  domain the tool assumed, and a black-boxed clock generator poisons everything downstream of it.
- **RDC survives a single clock.** Two flops on one clock with different asynchronous resets still
  cross, because the source clears asynchronously relative to the capture edge. A reviewer who says
  "the clocks are the same" has not answered the question.
- **Block-level clean does not carry to the top.** At block level the ports usually take a virtual or
  default clock, quietly asserting something about neighbours that do not exist yet; in the subsystem
  they get real clocks and the crossings appear. That is what `waiver scope` records.
- **Quasi-static is an assumption, not a proof.** Declaring a configuration bus static tells the tool
  to stop asking; it does not stop firmware writing it while traffic is moving. Back it with
  something that fails when it stops being true.
- **A waiver keyed on an index or a line number is worse than no waiver.** After the next edit it
  either stops matching and the noise returns, or it matches a different crossing nobody has ever
  reviewed — and that one is now signed off in your name.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the setup verdict is `verified` only if every row of the step 2 block came from a file, and any
  grouping claim is traced to where the clocks are generated rather than to a quiet report
- no cluster whose entire population shares one pair and one check is called `design` — that shape is
  a constraint, not hundreds of bugs
- no multi-bit crossing is called safe because each bit has a synchroniser
- an RDC finding is not dismissed on the grounds that both flops share a clock
- every waiver names objects by hierarchical name, has a `because` a reviewer could argue with, a
  `waiver scope` matching the level being signed, and an `expires`
- the coverage line is present, and its denominator is the number of clusters, not of violations

A wrong answer typically signs off a report whose setup was never verified, quotes a violation count
as progress, or produces a waiver that would have been a two-line constraint fix and now has to be
re-earned by hand every release.

## Done when

You can name the setup verdict, the ranked clusters behind whatever count remains, and for each
waiver the objects it names and the one sentence that makes it true — and a reviewer can check that
sentence without asking you anything.
