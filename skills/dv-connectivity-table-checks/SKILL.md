---
name: dv-connectivity-table-checks
description: Turn a connectivity spreadsheet or an IP-XACT description into a generated, name-reconciled check list — point-to-point paths, tie-offs, no-connects, conditional paths and address-map regions — instead of hundreds of hand-written tests. Use when you are stitching IP into an SoC and someone hands you a connectivity table, when the names in the table do not match the RTL hierarchy, when you need to say which rows became checks and which could not, or when you have been asked to write one connectivity test per pin.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep, Glob and Write over files on disk (Cursor 2.4+, Claude Code). Writes one generated check file; no shell, no network.
allowed-tools: Read, Grep, Glob, Write
metadata:
  semiskill-title: Table-Driven Connectivity, Tie-Off and Address-Map Check Generation
  semiskill-function: design-verification
  semiskill-role: soc-dv-engineer
  semiskill-level: fresher
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-03-12
  semiskill-tags: integration, connectivity, ip-xact, tie-off, address-map, soc, check-generation
---

# Table-Driven Connectivity, Tie-Off and Address-Map Check Generation

Integration bugs are boring and expensive: a swapped interrupt, an input left dangling, a region
decoded one address bit short. The specification for all of them already exists as a connectivity
table or an IP-XACT description, and the usual mistake is to read it and start typing tests — which
yields a few dozen checks and no record of which rows were skipped.

The work is not writing checks. It is **reconciling the names in the table against the names in the
RTL**, once, as a small set of rules, then expanding every row mechanically. The deliverable is one
generated check file in which every check carries the table row it came from, plus an honest count of
the rows that could not be reconciled and why. The agent cannot elaborate the netlist, start a formal
application, run a simulation or open a waveform; it reads, reconciles, writes, and hands over.

## When to use something else

- The generated checks will not compile, or the wrapper you reconciled against is in no filelist —
  `dv-build-filelist-hygiene`.
- One check failed and you have its log — `dv-sim-log-first-error`; a whole night of them —
  `dv-regression-triage-routing`; shrinking one — `dv-minimal-reproducer`.
- The failure is about a register's *access behaviour*, its fields, its mirror or its adapter —
  `dv-ral-bringup`. The boundary is exact: which base address a slave decodes at is an address-map
  row and belongs here; what happens inside that slave when a field is written belongs there.
- You cannot yet find the netlist, the filelists or the build at all — `dv-repo-orientation` first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Connectivity table | [[FILL: where our connectivity table lives, what format it is exported to, and which columns carry the driver, the receiver, the connection kind and the row key]] | integration owner |
| Integration RTL | [[FILL: which files hold the top-level instantiation for this integration, and whether they are hand-written or emitted by a stitcher]] | integration owner |
| Naming rules | [[FILL: how a name in the table relates to a name in the RTL hierarchy — separator, case, prefixes and suffixes, whether the instance path is included, and how a bus range is written]] | whoever wrote the stitcher |
| Tie-off convention | [[FILL: how our table records an intentional tie-off, an intentional no-connect, and a path that is inverted or resynchronised on the way]] | integration owner |
| Address-map source of truth | [[FILL: which file the address map for this integration is defined in, and whether the RTL decoder is generated from it or maintained by hand]] | SoC architect |
| Check output | [[FILL: where our generated checks land, in what form, and one existing check file that can be read as a template]] | DV lead |
| Check engine | [[FILL: what actually runs connectivity checks here — a formal application, a simulation test, or a netlist checker — and who launches it]] | DV lead |
| Waiver list | [[FILL: where a deliberately unchecked or knowingly broken connection is recorded, and what key each entry uses]] | DV lead |

Three pack-wide facts in `_shared/team-profile.md` are used here and **not** re-asked above: its
**Filelist convention** (step 1, to tell a compiled wrapper from one that merely exists in the tree),
its **Area to owner map** (step 8, for the report's `owner` line), and its **Register model source**
— which is a *different fact* from this table's **Address-map source of truth**. The register model
source says what register fields are generated from, usually per IP; the address map says where each
IP lands in the SoC. One file sometimes carries both; do not assume ours does, and if it does, say
so rather than leaving one blank. The profile's **Fatal markers** and **Pass marker** are
deliberately not repeated: this skill Greps no log, and the log a check run leaves behind belongs to
`dv-sim-log-first-error`.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented naming rule
reconciles every row to a plausible name that does not exist — one wrong rule is several hundred
wrong rows at once.

## Retrieval budget — read this before opening anything

A connectivity table carries thousands of rows; a stitched netlist is tens of thousands of lines of
machine-written instantiation. Neither can be read.

1. **Grep and Read work on files on disk.** A spreadsheet saved as `.xlsx` is a compressed binary
   container: Read cannot open it and Grep cannot search it. Ask for a comma- or tab-separated
   export and the path it was written to. Rows pasted into the chat are not a file either — reason
   over what you were shown if you must, say so, and mark every count from it provisional.
2. **Never open the table or the netlist with Read first.** Read the header row and one bounded
   window; find everything else with **Grep**.
3. The procedure fits in **3 Globs, 14 Greps and 6 windowed Reads of about 80 lines**: step 1 spends
   the 3 Globs; step 2 one Read and one Grep; step 3 one Read; step 4 at most 8 Greps and 2 Reads;
   step 5 one Grep; step 6 two Greps and one Read. That is 12 Greps and 5 Reads, leaving two Greps
   and one Read spare for wherever a name refuses to resolve. Steps 7 to 9 open nothing new.
4. **The rule that makes this fit: one Grep per naming rule, never one Grep per row.** Eight hundred
   rows cost one Grep per distinct *shape* of name; the rule is then applied mechanically.
5. A Grep returning more than about 200 hits is too broad — anchor it to one instance or one module
   first. A hit count that hit your runtime's limit is "at least N, truncated", not a count, and
   must never be reported as a row total.
6. **Stopping rule.** When the Greps are spent, stop reconciling. Every group still unresolved is
   reported as a group, with the reason and one example row — never expanded into a guessed name.
7. **State your coverage**: rows read of rows in the file, groups reconciled of groups found, checks
   generated. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the table to a path, and find the RTL it describes

Use **Glob** three times, recording paths only: the **Connectivity table** under the location its
slot names, the **Integration RTL** files, and any IP-XACT the slot mentions. Open nothing yet. If
the table exists only as a spreadsheet or as pasted text, stop and ask for the export — budget rule
1, and the most common reason this procedure produces nothing useful.

Then apply the profile's **Filelist convention**: a wrapper that sits in the tree but appears in no
filelist is not in the design, and reconciling against it generates checks on a module nobody
compiles. If two similarly named wrappers are indistinguishable, that is a question for step 8's
report, not a coin toss.

If IP-XACT is the source, its element names differ across the 2009, 2014 and 2022 revisions of the
IEEE 1685 standard and across vendor extensions. Take them from the file's own root element and
namespace declaration — step 2's Read window shows both — not from memory, and confirm the ones
carrying address regions, ad-hoc connections and port maps before relying on any of them.

### 2. Read the header, not the rows

One **Read** of the table's first 80 lines, for the *schema*: which column is the driver, which the
receiver, which the connection kind, which the row key, and whether a condition column exists.
Columns the **Connectivity table** slot never mentioned mean the slot is stale, and that difference
is worth reporting before either is used.

Then **one Grep** whose pattern matches every data row — the row-key column is usually the cleanest
anchor — and take the hit count. That number is the denominator for everything reported afterwards.
A table with no stable row key is itself a finding: without one a generated check cannot be traced
back to the row that justified it, which is the whole point of generating rather than hand-writing.
Ask for a key column before generating anything.

### 3. Classify every row before reconciling any name

Five kinds, generating genuinely different checks. Classify from the kind column if there is one,
from the shape of the row if there is not.

| Kind | What the row says | What the check has to prove |
|---|---|---|
| point-to-point | one driver reaches one receiver | the two are the same net, or their values agree |
| tie-off | an input is held at a constant | the observed value is that constant, at all times |
| no-connect | an output is deliberately unused | nothing — but the row must exist, so a later dangling input is not mistaken for it |
| conditional | the path exists only in some mode | the values agree **while the named condition holds**, and nothing is claimed otherwise |
| address-map | an IP occupies a region of the map | the decoder covers exactly that region, and nothing overlaps it |

Then one **Read** of an 80-line window further down the table. Row shapes are not uniform: tables
grow by accretion, and the rows added last — usually the conditional and test-mode ones — sit at the
bottom and look nothing like those at the top, so a classification taken from the first 80 rows alone
silently mis-files them. Record the count of each kind; those five counts go into the report and are
the first thing a reviewer checks.

### 4. Reconcile names by rule, not row by row

This is the step the skill exists for, and the one that consumes the budget. Group endpoint names by
*shape*, not by row: everything differing from an RTL name in the same way is one group. Start from
the **Naming rules** slot, then confirm each group with a single **Grep** of the **Integration RTL**
for one representative name — at most 8 Greps, plus at most 2 windowed **Reads** around the
instantiation the first hits land in.

```
Table row R0087 driver   dma_top.irq_out        receiver   intc.irq_in[7]
RTL                      u_soc/u_dma/o_irq                 u_soc/u_intc/i_irq[7]
Rule for this group      drop the _top suffix, add the u_ prefix and the u_soc path,
                         rename out to o_ and in to i_
```

The differences that actually occur, roughly in the order they bite:

- **Hierarchy separator and depth.** The table names a leaf, the RTL wants a path; the separator may
  be a dot where the RTL uses a slash, and the table usually omits the top level.
- **Bus range notation.** A full-width range, a range written the other way round, and a bare name
  all mean the same port. A *partial* range does not — that row is a field-level connection with a
  different check, and normalising notation must never normalise away a partial range.
- **Case, separators, prefixes and suffixes** — direction prefixes, instance prefixes, wrapper
  suffixes, a hyphen against an underscore.
- **Arrayed and generated instances.** One row can stand for N instances, and the loop bound lives
  in an RTL parameter, not the table. If you cannot read the bound, record the row as expanding to
  an unknown count rather than assuming one.
- **A rename at a hierarchy boundary.** The same wire has one name inside the IP and another on the
  wrapper port; both are correct, but only one appears in the RTL you are checking against.

Once a rule is confirmed by one Grep, apply it to its whole group without further searching. A group
whose representative Grep returns nothing is **not** reconciled — say so and move on; it is a
group-sized finding, and guessing a second candidate name burns the spare Greps for nothing.

### 5. Tie-offs and no-connects are value rows, not path rows

At most **one Grep** for the constants in the **Integration RTL**, guided by the **Tie-off
convention** slot. A tie-off cannot be proven by tracing a net, because there is no net to trace —
the check compares an observed value against a constant.

Three states are routinely conflated and are three different findings: an input tied to a constant
in the RTL, an input left off the port list entirely, and an input driven by a signal that merely
happens to be constant today. The second is the dangerous one — depending on the language and the
tool it resolves to X, to Z, or to a default, and none of those is the zero the table asked for. A
no-connect row generates no value check but must still appear in the output; its purpose is negative,
stopping the next person filing a bug when they find that output unused.

### 6. Address-map rows — overlaps and gaps, against the decoder

Two **Greps** and one **Read**: Grep the **Address-map source of truth** for each region's base and
size, Grep the **Integration RTL** for the decoder's parameters or constants, Read one 80-line window
at the decode logic. Sort the regions by base address, walk them once, and look for three things:

1. **Overlaps** — two regions covering one address. Found quickly, usually a table edit.
2. **Gaps** — an address in no region. The expensive ones: nothing complains until somebody accesses
   that address a year later and gets a decode error nobody can place.
3. **Size against decoded width** — a region declared one size but decoded on too few address bits,
   which aliases it across the map. A region of 64 kilobytes needs 16 bits below the compare.

If the decoder is generated from the same file as the map, an inconsistency means one of the two was
edited after generation — say which, and stop rather than reporting a design bug. If the register
model comes from a *different* source (the profile's **Register model source**), there are now three
descriptions of one map and any two of them can drift.

### 7. Conditions, inversions and waivers

**Conditions.** A conditional row without its enabling condition generates a check that is false in
the other mode. That check fails, gets waived, and the waiver then hides a real break in the mode
nobody looked at. If the condition column is empty for a row you know is mux'd, leave it
unreconciled rather than generating an unconditional check.

**Inversions and resynchronisation.** A path through an inverter is one row whose expected value
inverts; a path through a synchroniser is one row whose values agree only after a delay, and the
**Tie-off convention** slot records how ours are marked. A checker comparing raw values across either
reports a correct connection as broken — which is how a check set loses its reader's trust on run one.

**Waivers.** Read the **Waiver list** and carry each matching row's key into the output rather than
dropping the row. A dropped row and a waived row look identical in the counts, and only one of them
had a decision behind it.

### 8. Write the check list

Use **Write** once, to the location the **Check output** slot names; producing this file is the
deliverable. If that slot names an existing check file as a template, read it first and follow its
shape rather than the tool-neutral one below. One row per check, each traceable to its source row:

```
CHK_ID, ROW, KIND, DRIVER, RECEIVER, EXPECT, WHEN, STATUS
CONN0142, R0087, p2p, u_soc/u_dma/o_irq, u_soc/u_intc/i_irq[7], match, always, reconciled
CONN0143, R0088, tieoff, u_soc/u_dma/i_test_mode, -, constant 0, always, reconciled
CONN0144, R0089, amap, u_soc/u_dma slave port, -, base 0x4000_0000 size 0x0001_0000, always, reconciled
CONN0145, R0090, cond, u_soc/u_pad12/o_data, u_soc/u_spi/i_miso, match, mode_sel is 2, unreconciled-receiver
CONN0146, R0091, nc, u_soc/u_dma/o_spare, -, none, always, no-connect-recorded
```

Then the report block that travels with it. Its `owner` line comes from the profile's **Area to
owner map**; its `coverage` line is not optional; and anything not fillable from text on disk gets
`?` rather than a plausible number.

```
check set    : <name, plus the connectivity table path and the table revision it came from>
rtl revision : <the integration RTL revision the reconciliation was done against>
rows         : <total, then the five step-3 kind counts>
checks       : <how many were generated, and the expansion rule that produced them>
reconciled   : <n of the total, both endpoints resolved to a real RTL name>
unreconciled : <n, grouped by reason, one line per group and never one line per row>
waivers      : <rows carried through from the waiver list, with their keys>
owner        : <who owns each unreconciled group, from the area-to-owner map>
coverage     : <rows read of rows in the file; groups reconciled of groups found; what was not reached>
notes        : <anything the next person would otherwise rediscover, including any value from a person>
```

### 9. Hand it to whatever can actually run it

The agent cannot start a formal application, a simulation or a netlist checker. Ask the engineer
named in the **Check engine** slot to run the generated list and to give you the path to the output
it writes, then read that path; until then the check list is a proposal. Ask in the same message for
the RTL revision the run used, to compare against the `rtl revision` line, and for how many checks
the engine actually loaded — a count below the generated count means rows were dropped at load time,
and a check that never loaded reports exactly what a passing check reports: nothing.

## Gotchas

- **A row is not a check, and both counts must be reported.** One 32-bit bus row becomes 32
  bit-level checks in a formal connectivity application and one vector comparison in a simulation
  test. Report rows consumed and checks generated separately, or a reviewer counting rows concludes
  you dropped most of the work.
- **The driver and receiver columns are not always the driver and the receiver.** Tables are often
  written from one IP's point of view, so a wrapper port is a receiver on the row that reaches it and
  a driver on the row that leaves it. Take direction from the RTL port declaration, never from which
  column a name sits in — a check written the wrong way round passes happily on a floating net.
- **An input left off the port list is not a tie-off.** It resolves to X, to Z, or to a default
  depending on the language and the tool, and behaves differently again in gate-level or power-aware
  runs. "Tied to 0" and "not connected" are two rows, two checks and two bugs.
- **A partial bus range is a different row from a full one.** Normalising `[31:0]` against a bare
  name is safe; normalising `[15:8]` the same way widens a field-level connection into a whole-bus
  one and makes the check pass on the wrong 24 bits.
- **Address-map gaps cost more than overlaps.** An overlap shows up on the first access; a gap shows
  up months later as an unexplained decode error from software, by which time the map has been copied
  into three other documents. Worse still is a region declared as 64 kilobytes but decoded on 15
  address bits: it aliases into its neighbour, and every access inside its first half works
  perfectly, which is exactly why that one survives bring-up.
- **Test, DFT and power connections are usually a different table with a different owner.** Scan
  enable, clock-gate enable, isolation and retention control rarely appear in the functional
  connectivity table. If yours has no rows of that kind, that is a scope statement to write down,
  not a clean result.
- **A reconciliation is valid against exactly one RTL revision.** Insert a wrapper, rename an
  instance, or re-run the stitcher and every hierarchical path moves. Record the revision in the
  output; without it the next integration merge produces a page of fake breaks and the reader stops
  trusting all of it.
- **Two endpoints that resolve to the same net make a check that cannot fail.** That is usually the
  table naming one wire twice through a passthrough wrapper, not a connection proven correct — count
  those rows separately, because a check set full of them looks far greener than it is.
- **The table is a specification, not evidence.** It is maintained by hand and it drifts. A
  disagreement between table and RTL is a finding to route, not automatically an RTL bug: say which
  of the two you believe and why, and let the owner decide.

## Human verification — what a wrong answer looks like

Before anyone runs the generated list, check:

- every check row carries a real table row key, and three picked at random are all found in the table
- reconciled plus unreconciled equals the row count step 2's Grep produced, and that count did not
  come from a truncated result
- every hierarchical path in the output appeared in an actual Grep hit against the integration RTL —
  none was assembled from a rule alone and never confirmed
- unreconciled rows are grouped by reason with an example each, not listed one by one or dropped
- the five step-3 kind counts are present, and no conditional row became an unconditional check
- the `rtl revision` line is filled, the `coverage` line says what the budget did not reach, no
  tie-off row became a path check, and no no-connect row was deleted

A wrong answer reads as a complete, tidy check list in which every name is plausible and perhaps a
third of the paths do not exist — the signature of a naming rule applied everywhere and confirmed
nowhere. Its second form is a check set that passes completely on the first run, which almost always
means the engine loaded fewer checks than were generated, or the rows resolved to nets that were
already identical.

## Done when

The engineer who runs the check list can trace every check back to a table row, and every row that
did not become a check is named, grouped and owned.
