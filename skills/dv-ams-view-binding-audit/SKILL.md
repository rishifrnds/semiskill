---
name: dv-ams-view-binding-audit
description: Keep the intended per-test view of every analog block written down in the repo, then audit what elaboration actually bound against it. Use when a regression mixes transistor, fast-SPICE, real-number and digital-stub views of the same block, when an analog test passes suspiciously fast or suspiciously cleanly, when nobody can say which model a given test actually ran, when the same block behaves differently in two tests that should be identical, or when a real-number model was swapped in and the failure went away.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Per-Test Analog Representation Matrix and View-Binding Audit
  semiskill-function: design-verification
  semiskill-role: ams-verification-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-07-09
  semiskill-tags: ams, mixed-signal, real-number-model, view-binding, elaboration, connect-modules, regression
---

# Per-Test Analog Representation Matrix and View-Binding Audit

An AMS regression is several different designs wearing one name. The same PLL is a transistor netlist
in one test, a real-number model in the next, and a tied-off stub in the twenty tests nobody thought
about — and nothing in the source says which. What elaboration binds is decided by a config, a library
search order, a compile-time define, and embarrassingly often by which copy of a cell a filelist
reached first. The result is a green regression that never exercised the block it claims to.

The output is two things: **an intended representation matrix that lives in the repo**, and **a
per-cell diff of that matrix against what one real elaboration actually bound**, every row carrying
the report line it rests on.

**What this cannot do.** The agent cannot elaborate a design, start a simulation, open a waveform, or
ask a library what it holds. It reads text on disk. Every binding fact here comes from a report an
engineer produced and pointed at; everything else in the repo is a hypothesis about what that report
will say.

## When to use something else

- Elaboration **failed** and nothing bound — `dv-build-filelist-hygiene`. It also owns the question of
  why two copies of a cell exist at all; this skill only tells you which copy won.
- One failing simulation log — `dv-sim-log-first-error`.
- A night of failures to sort and route — `dv-regression-triage-routing`.
- Shrinking a signature you already have — `dv-minimal-reproducer`. Record the representation in its
  config diff: a view swap is a configuration change with a wider blast radius than any knob.
- You cannot yet name the build entry point or the filelists — `dv-repo-orientation`.
- A register-access failure — `dv-ral-bringup`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Analog block list | [[FILL: the analog and mixed-signal cells in this testbench that have more than one view, and the cell name each is instantiated by]] | AMS lead |
| View names | [[FILL: the exact view or model name our libraries use for each representation we support, spelled the way the tool spells it]] | AMS lead |
| Selection mechanism | [[FILL: how a view is chosen here — config, library map, compile-time define, wrapper generate, filelist swap, or an AMS control block — which file holds it, and which mechanism wins when two disagree]] | DV infra owner |
| Matrix location | [[FILL: where the intended per-test representation matrix lives in our repo, or that we do not have one yet]] | AMS lead |
| Elaboration report | [[FILL: what our elaborator writes that names the bound view per instance, where that file lands, and the string that opens one binding line in it]] | DV infra owner |
| Connect rules | [[FILL: which connect-rule set or discipline-resolution setting this testbench selects, and the file that declares it]] | AMS lead |
| Snapshot reuse | [[FILL: whether our regression elaborates once and reuses one snapshot across tests or elaborates per test, and what the snapshot is keyed on]] | DV infra owner |
| Cost budget | [[FILL: what one test is allowed to cost at each representation, and who approves an exception]] | verification lead |

Four facts this procedure spends are pack-wide and live in `_shared/team-profile.md` — read them from
there rather than re-interviewing anyone. **Simulator** decides whose elaborator vocabulary steps 2
and 5 search for. **Filelist convention** is what the filelist-swap mechanism turns on. **Build log
location** is where build output lands, and **Run identity** fills the report block's run line.

**Elaboration report is narrower than the profile's Build log location, and they are not the same
fact.** The profile records where build output lands; this slot asks for the one artifact that names a
bound view per instance, plus the string that opens such a line. On many flows that artifact is not
inside the build log at all — it is a separate report the elaborator writes only when asked for it.
Fill both. If they turn out to be one file for your flow, record that as a finding rather than
assuming it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented view name or config
clause produces an audit that is clean about a design nobody ran.

## Retrieval budget — read this before opening anything

A transistor netlist for one block runs to hundreds of megabytes, an elaboration report for an SoC top
runs to hundreds of thousands of lines, and the filelists behind them nest. Every step is Grep-first,
and none of it reads a netlist.

1. **Grep, Read and Glob work on files on disk.** A view name someone types into the chat is a claim,
   not evidence. If no elaboration report exists on disk, say so plainly and stop at step 3 with the
   intended matrix alone.
2. **Never open a netlist, an elaboration report or a filelist with Read first.** Grep for a line
   number, then Read a bounded window around it.
3. The ledger for one pass — one elaboration — is **6 Globs, 17 Greps and 6 windowed Reads**, spent
   like this: step 2 takes at most 5 Globs and 6 Greps — one each for the config, the library map, the
   define and the AMS control block, and two for the wrapper, whose second Grep cannot be merged into
   the first because its pattern is whatever the first returned; step 5 takes 2 Greps and 2 Reads of
   about 80 lines; step 7 takes 2 Greps and 1 Read; step 8 takes 2 Greps per divergent cell for at
   most **three** cells, plus 2 Reads of about 40 lines **for the whole of step 8, not per cell**.
   That commits 5 Globs, 16 Greps and 5 Reads, holding one of each back. No other step opens a file.
4. Scope every Glob and Grep to one directory. A pattern run from the repository root over an AMS tree
   returns the whole netlist collection and truncates.
5. If a Grep returns more than about 200 hits the pattern is too broad — narrow it before reading
   anything. A count that hit your runtime's limit is "at least N, truncated", never a count.
6. **Stopping rule.** Stop when every matrix row is either matched to a report line or recorded as
   unchecked, or when the ledger is spent — whichever comes first. A fourth divergent cell is a second
   pass, not more reading.
7. **State the coverage.** Every count carries a denominator, and the report says how many matrix rows
   were actually compared against a report line. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Fix the scope of one pass

One pass covers one elaboration. Settle which one first, because the answer decides how many columns
the matrix is allowed to have.

- Read the **Snapshot reuse** slot. If the regression elaborates once and reuses one snapshot across
  tests, the matrix has one column per *snapshot*, not per test, and any per-test intention written
  next to it is fiction. That finding alone is usually worth the pass.
- A plusarg, a configuration-database entry, or anything else applied at run time **cannot change a
  binding**. Views bind during elaboration; by the time a test name exists the design is fixed. If
  your flow appears to pick a view per test out of one build, what is really being picked is a mode
  inside an already-bound wrapper — say so, and audit the wrapper instead.
- Name the test or test group this pass covers, and get the **Elaboration report** path for it. If
  nobody can produce one, that is the step 4 handoff, not a shortcut.

### 2. Inventory the mechanisms that can decide a view here

Read the **Selection mechanism** slot first, then confirm each mechanism it names actually exists. The
allowance is five **Globs** to locate the files and six **Greps** to search them, spent exactly as the
bullets say. Each bullet also gives the token step 8 records it under: a mechanism described in prose
and one named in a handoff block have to be the same thing. You are building a short list of files
that can move a binding, not a flattened file set.

- **A config** — token `config`. **One Grep**, alternating the config's declaration with its
  `default liblist`, `cell` and `instance` clause keywords. Precedence *inside* a config is fixed by
  the language: an `instance` clause beats a `cell` clause, which beats `default liblist`. A config
  the build never elaborates as its top is a silent no-op — check that the build names it, and record
  whether you saw that or inferred it.
- **A library map** — token `library-map`. **One Grep** of the library-definition file for the cells
  in **Analog block list**. Two libraries holding one cell name means liblist order decides, and that
  order is a property of the build invocation, not of the file.
- **A compile-time define** — token `compile-define`. **One Grep** for the define names around the
  model and the stub. A define is frozen into the snapshot — this is the mechanism that most often
  looks per-test and is not.
- **A wrapper generate** — token `wrapper-generate`. The only mechanism that is honest in ordinary
  source, and the only one costing **two Greps**: one for the parameter the wrapper switches on, then
  one for where that parameter is overridden. The second pattern is whatever the first returned, so
  the two cannot be alternated into one call.
- **A filelist swap or a duplicate definition** — token `filelist-order`. Two files defining one cell,
  and the tool keeps one. **No Grep here**: which one it keeps is the Duplicate policy fact
  `dv-build-filelist-hygiene` asks for, so route the question there rather than re-deriving it.
- **An AMS control block** — token `ams-control`. **One Grep** of whatever your simulator reads to map
  instances to analog views and select connect rules. Its name and syntax are house-and-tool facts, so
  they live in the slot.

Record which mechanisms are live, and which the slot named but you could not find. **Which mechanism
wins when two disagree is a tool property**; if the slot does not say, that is a question to ask, not
one to reason out.

### 3. Write the intended matrix down, before opening any report

This is the deliverable that outlives the pass. One row per cell from **Analog block list**, one
column per test group, and a `default` column — which is the column that matters, because it covers
every test nobody thought about.

| cell | default | smoke | lock | droop |
|---|---|---|---|---|
| cell as the tool names it | real-number | real-number | transistor | fast-spice |
| the next one | digital-stub | digital-stub | digital-stub | behavioural |

Each filled square carries two things: the **representation class**, one of the five the report block
below accepts, and the tool's own view name from the **View names** slot, verbatim. The class is what
a human reasons about; the view name is the only string the report will ever contain, so a matrix
holding classes alone cannot be compared against anything.

Every square also needs one line of reason, kept beside the table — why that block is at that
representation for that test, and what that representation is allowed to cost. Take the allowance from
the **Cost budget** slot: a square at or under it needs no more than the reason; a square above it
must name the approver the slot says signs an exception, and a square above it with no approver named
is a finding of this pass, not a detail. That is the square that gets downgraded during the next
runtime panic and never comes back. An **empty** square is not "whatever happens by default"; it is a
question for the AMS lead. Author the matrix as text and hand it to the engineer to commit at the
**Matrix location** slot's path — this skill writes nothing to the repo itself.

### 4. Ask for the elaboration that actually happened

The agent cannot elaborate anything. Ask the engineer to elaborate the test named in step 1 with the
binding report enabled, and to give you the **path** the report was written to — not its contents
pasted back. Ask for two more things in the same message, because a second round trip costs a day:

- the build tag or snapshot identifier that elaboration produced, so the matrix column can be keyed on
  something real
- whether elaboration emitted warnings about unresolved or substituted cells, and where those landed

If the flow produces no per-instance binding report at all, say that plainly. Everything below becomes
unavailable, the result is `binding: unverified`, and the useful deliverable is the step 3 matrix plus
a request that the report be switched on.

### 5. Read what was actually bound

Two **Greps** and two windowed **Reads**, and no more.

- **Grep** the report for the binding-line marker from the **Elaboration report** slot, alternated
  with the cell names from **Analog block list**. One call. Keep the line numbers.
- **Read** about 80 lines around the first cluster of hits. Binding lines usually arrive together, in
  hierarchy order, so one window often carries most of the matrix.
- **Grep** once for the unresolved-or-substituted wording the same slot records. A cell that resolved
  to nothing, or to an empty shell, is the most expensive outcome available here, and it is frequently
  only a warning.
- **Read** one more window if a second cluster sits elsewhere in the file.

Copy each binding **verbatim** — instance path, library, cell and view exactly as the report spells
them. A view name half-remembered from the matrix is how this audit produces a confident answer about
a design that is not the one that ran.

### 6. Diff bound against intended, cell by cell

Arithmetic now; this step opens nothing. For every matrix row exactly one of five things is true, and
the `view match` field spells all five: `matches`; `wrong-view`; `unresolved`; `not-in-matrix`, where
the report bound something the matrix never mentioned, usually a block somebody added; and
`not-in-report`, where the matrix names a cell no binding line mentions.

**`not-in-report` is ambiguous and must not be settled by guessing.** Either the cell is genuinely
absent from the elaborated hierarchy, or the marker string in the slot is wrong and the Grep looked
for text the report never prints. One further **Grep** for the bare cell name decides it — and that
Grep comes out of step 8's per-cell allowance, because a `not-in-report` row *is* a divergent cell.

Two fields fall straight out of that classification, and both are written here rather than left to
whoever reads the block:

- **`bound`.** The class the report's view string belongs to. Where no report line gives the cell a
  view — a `not-in-report` row settled as a genuine absence, or an `unresolved` cell whose line names
  the instance and prints no view — write `bound: not-reported` and leave `view name` empty. Never
  carry `intended` across into `bound`: that turns a missing fact into a match.
- **`binding`**, the pass's one summary line. `matrix-honoured` only when every matrix row was compared
  against a report line and every one of them is `matches`, which makes it available only when
  `coverage` reads n of n. `divergent` when any compared row is anything else, however few rows were
  compared. `unverified` when nothing diverged and nothing was established either — no per-instance
  report came back from step 4, or the ledger ran out with rows still uncompared. **Partial and clean
  is `unverified`, not honoured**: a pass that compared four of eleven rows has not seen the matrix.

### 7. Audit the boundary the swap moved

A representation change moves the analog-to-digital boundary, and what sits on that boundary appears
in nobody's source. Where a continuous-discipline port meets a discrete-logic one, the elaborator
inserts a connect module chosen by the **Connect rules** set. Those instances exist only in the
elaborated hierarchy and in the report.

Spend **two Greps and one Read**: one Grep of the report for the connect-module insertion lines, one
Grep of the **Connect rules** file for the threshold, supply and direction parameters it sets, then
one window around whichever of the two is shorter. Check three things, in this order:

1. **Did the count change with the view?** Swap a transistor block for a real-number one and the
   electrical nets at its edge stop existing, so the connect modules there disappear — or move outward
   to the next block that is still electrical. A boundary that did not move when the view changed is
   strong evidence the view did not change.
2. **Real-number nets are discrete-event, not continuous.** They are not electrical, so the automatic
   connect-module machinery does not apply to them. Conversion between a real-valued net and a logic
   net is an explicit converter somebody wrote, and conversion between two *different* real-net
   flavours — a Verilog-AMS `wreal` and a SystemVerilog user-defined nettype — usually needs one too.
   If nobody wrote it the elaborator complains; if somebody did, its thresholds are a second copy of
   the connect rules, maintained by nobody.
3. **Which supply do the rules assume?** A connect module converts against a threshold derived from a
   supply value the *rules* set, not from the supply the design drives. On a multi-supply or
   power-gated block, one connect-rule set for the whole testbench converts the low-voltage domain
   against the wrong threshold, and the failure surfaces as a design bug in the receiving block.

### 8. Attribute each divergence — mechanism, cost, and where the fault sits

For each divergent cell — **three at most in one pass** — two **Greps**. The two 40-line **Reads** are
for the whole of this step, not for each cell: spend them on the two hits you cannot classify from the
Grep line alone, and classify the rest from the hit.

- **Grep** the step 2 mechanism files for that cell name. One hit in one mechanism is the answer.
- **Grep** a second way, using the library-qualified form the report used rather than the bare cell
  name. A config clause and a report line frequently spell one cell differently, and the bare-name
  search misses the clause.

Then write the finding down in the tokens the block accepts, not in the words the file used:

- a config `instance`, `cell` or `default liblist` clause naming the cell → `mechanism: config`
- a library-definition entry, or a liblist order deciding which library answers → `library-map`
- a define around the model or the stub → `compile-define`
- the parameter a wrapper switches on, or the override that sets it → `wrapper-generate`
- two definitions of one cell, where the tool kept whichever a filelist reached first → `filelist-order`
- an AMS control-block entry mapping this instance to a view → `ams-control`
- no mechanism naming the cell, or two of them naming it → `unknown`

If two mechanisms both name the cell, do not decide the winner from precedence you remember. Record
both positions, mark the mechanism `unknown`, and ask. Precedence *between* mechanisms is the one
thing in this procedure that cannot be read off the files.

Where `view match` is `unresolved`, check one thing before attributing anything: whether the cell
resolved to an empty shell rather than to nothing at all. An empty shell elaborates cleanly, drives
nothing, and turns every downstream check into a pass.

Then set the last two lines of the cell's block, both from what is already in front of you:

- **`cost`.** Compare the representation actually bound against the **Cost budget** slot's allowance
  for this test, and say which side of it the binding sits. A cell bound *cheaper* than the matrix
  intends, inside no approved exception, is the silent downgrade this skill exists to catch — someone
  bought runtime with a check. *Dearer* than the allowance is a cost finding rather than a correctness
  one and still belongs in the block: it is the pressure that produces the next downgrade. Where the
  slot sets no allowance for this representation, write that.
- **`owner`.** One of three, and the two rows above it decide which. **The matrix** — the flow bound
  what it was configured to bind, and the square is wrong, empty, or was never agreed. **The
  mechanism** — the square is right and a mechanism file contradicts it, and `evidence` carries that
  file and line. **The model itself** — only where the bound view *is* the intended one and the block
  still behaved wrongly, the one case here that is a design problem rather than a flow one. Where the
  mechanism reads `unknown`, leave this line empty until the precedence question comes back answered;
  a plausible owner is how a binding fault gets filed against a designer.

### 9. Report

```
matrix      : <path in the repo, or "drafted here, not yet committed">
test        : <the test or test group this pass covers>
snapshot    : shared | per-test | unknown
build tag   : <the identifier the elaboration produced, as the engineer reported it>
report      : <elaboration report path, and the line range worth reading>
binding     : matrix-honoured | divergent | unverified
phase       : compile | elab | run | finalise | post
class       : design | infrastructure | unknown
run id      : <whatever identifies this run for us>
coverage    : <n of m matrix rows matched to a report line; k of j divergences attributed>
notes       : <mechanisms the slot named but you could not find, and anything the next person would
               otherwise rediscover>
```

Then one block per divergent cell, and none at all when `binding: unverified`:

```
cell        : <library and cell as the report spells them>
instance    : <instance path from the report>
intended    : transistor | fast-spice | real-number | behavioural | digital-stub
bound       : transistor | fast-spice | real-number | behavioural | digital-stub | not-reported
view name   : <the tool's own view string, verbatim from the report>
view match  : matches | wrong-view | unresolved | not-in-matrix | not-in-report
mechanism   : config | library-map | compile-define | wrapper-generate | filelist-order | ams-control | unknown
boundary    : <connect modules the report names at this instance's edge, or "none reported">
cost        : <the bound representation against the Cost budget allowance, and the approver if it is
               an exception; cheaper-than-intended is the finding, not the reassurance>
evidence    : <report path and line number, plus the mechanism file and line>
owner       : <the matrix, the mechanism, or the model itself>
```

`phase`, `class`, `run id`, `notes` and `coverage` are the field names `dv-sim-log-first-error` and
`dv-ral-bringup` use, so a finding routed between them keeps one vocabulary. Here `phase` is `elab`
for anything the binding decided and `run` for a model that was bound as intended and then behaved
wrongly. The line keeps the pack's full five tokens so the column still joins, but only those two are
reachable here: `compile` belongs to the build skill this one routes to, and `finalise` and `post` are
later than anything an audit of elaboration can see. `class` is `infrastructure` for a binding fault — a wrong view is a flow-configuration problem — and
`design` only when the bound view is the intended one and the block itself is at fault, the same case
that makes `owner` the model.

This skill produces **no failure signature**. If the pass explains a failure someone is already
carrying, hand back the signature that failure already has, per
`_shared/failure-signature-schema.md`, rather than deriving a second one that will not match theirs.

Leave any field empty rather than filling it plausibly, and keep the `coverage` denominators honest:
one 80-line window over a report holding sixty bindings covers a fraction of the matrix, and saying so
is the difference between an audit and a reassurance.

## Gotchas

- **A stub with tied-off outputs passes every test downstream of it.** Nothing errors and nothing
  warns; the block's coverage simply goes to zero and nobody reads that number. This is the analog
  cousin of an all-zero register block reading clean on a bus that decodes nowhere. Keep one check
  that can only pass when the block is real, and confirm it fails when the stub is bound.
- **A `real` value has no X, and it starts at 0.0.** Swap a logic stub for a real-number model and
  every X-propagation bug in the receiving logic quietly vanishes, because an undriven real supply
  reads as a legal 0 V rather than as unknown. The reverse is worse: a design that only ever ran
  against real-number models has never had its reset-time X behaviour verified at all.
- **A plusarg cannot change a view.** Binding is settled at elaboration. If one snapshot serves the
  whole regression, the matrix has exactly one column and every per-test intention beside it is a
  record of a wish.
- **The connect modules are inserted, not written, and they are not in the matrix.** Which ones appear
  is derived from the view set. Two tests with the same matrix but different connect-rule selections
  are two different designs, and only the report will tell you.
- **A config nobody elaborated is a no-op that reads like a decision.** Every clause present, spelled
  correctly, reviewed by two people — and the build never named that config as its top. Nothing warns.
- **Port order is the entire interface where a Verilog instance binds to a SPICE subcircuit.** The
  subcircuit's terminal list is positional, so two same-typed terminals swapped there give a design
  that elaborates, simulates and is wrong. SPICE identifiers are also commonly case-folded while
  Verilog ones are not, so `vdd` and `VDD` may be one net or two depending which side you ask.
- **`bind` does not swap a view.** It adds an instance alongside the existing one. People reach for it
  when a config fights them, and then wonder why two models are running at once.
- **Multiple drivers on a real-valued net do not resolve the way a logic net does.** A SystemVerilog
  user-defined nettype needs a declared resolution routine, or a second driver is an elaboration
  error; a Verilog-AMS `wreal` net's behaviour with two drivers depends on its declaration and on the
  tool. Confirm what your flow does before wiring the second driver — a silently dropped driver looks
  exactly like a model bug.
- **A checker that lives inside one view disappears with it.** Assertions and coverage written into
  the stub are not carried by the real-number model, and vice versa. Swapping a view therefore changes
  what is being *checked* as well as what is being modelled — track checks as their own matrix row.
- **One transistor view can cost more than three fast-SPICE ones.** The analog partition's timestep is
  set by its fastest dynamics, so adding one block with a tight time constant slows every other analog
  block in the same partition. Steps 3 and 8 spend the **Cost budget** slot in opposite directions for
  that reason: the obvious mitigation — moving a block down one representation — is also the move that
  quietly removes the check that mattered, so a binding cheaper than the matrix intends is a finding
  even when nothing failed.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every `bound` value was copied from a report line with a path and a line number, and any cell the
  report gave no view for reads `not-reported` rather than repeating `intended`. A view named from the
  matrix, from a filelist, or from memory is not evidence.
- `binding` reads `matrix-honoured` only where `coverage` reads n of n. A pass that compared some rows,
  found them all matching and called the matrix honoured is the failure mode of this whole procedure.
- the `snapshot` value was read from the flow rather than assumed. A per-test matrix over a shared
  snapshot is the most expensive wrong answer available here.
- every `not-in-report` row was settled by the second Grep, not left as an assumption about the marker
  string.
- the connect-module count is stated for the boundaries that moved, and any cell whose view changed
  shows its boundary changing too.
- the `coverage` denominator is the number of matrix rows, not the number of binding lines that
  happened to fall inside the window you read.
- nothing the report only warned about — an unresolved cell, an empty shell — is recorded as a clean
  binding.
- the mechanism reads `unknown` wherever two mechanisms both name the cell, rather than being resolved
  from remembered precedence — and `owner` is empty wherever it does.
- `owner` reads the model only where `bound` and `intended` agree. A divergent binding blamed on the
  model sends a flow-configuration problem to a designer, who will not find it.

A wrong answer is typically a tidy matrix in which every row says `matches`, built from one 80-line
window that held a third of the bindings. Its two variants are a report naming the view a config
*intends* rather than the one the report *recorded*, and a green analog regression in which two of the
four blocks were stubs the whole time.

## Done when

You can hand over the matrix text and the path it belongs at, a report block whose `binding` line is
consistent with its `coverage` line, and one block per divergence naming a mechanism token and where
the fault sits.
