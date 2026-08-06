---
name: dv-connect-module-discipline-debug
description: Debug a mixed-signal boundary where connect modules are missing, wrongly parameterised, or inserted in the thousands, by reading the elaboration output and the connect rules that produced it. Use when elaboration reports that no connect rule matched or that a discipline is ambiguous, when a digital signal crosses into the analog side and arrives stuck at X or at the wrong level, when an inserted connect module is referenced to the wrong supply, when the connect-module count explodes and a run that used to take minutes takes hours, or when the analog side sees a logic value that was never converted.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Connect-Module Insertion and Discipline-Resolution Debug at the Mixed-Signal Boundary
  semiskill-function: design-verification
  semiskill-role: ams-verification-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-05-27
  semiskill-tags: ams, mixed-signal, connect-modules, discipline-resolution, elaboration, verilog-ams, real-number-modelling
---

# Connect-Module Insertion and Discipline-Resolution Debug at the Mixed-Signal Boundary

At a mixed-signal boundary nobody writes the converter: the elaborator inserts it, from rules somebody else wrote months ago. All four
failures present as something else — a missing converter looks like a dead net, one on the wrong supply like an RTL bug, an ambiguous
discipline like a port-list typo, ten thousand converters like a slow simulator. The output is four things: **the boundary named, the symptom
classified, its one line of evidence, and one owner.**

**What this does not do.** It reads source, connect-rule files and saved elaboration output; it cannot elaborate, simulate or open a waveform,
so those steps end in a handoff to a named person. `discipline`, `connectrules`, `connect` and `connectmodule` are Verilog-AMS reserved words,
spelled the same everywhere; the spelling of a **real-number net is not** — that is a user-defined net type or vendor extension local to your
flow, so the Boundary inventory slot supplies it. Every tool switch, message string and rule-set name is a slot below.

## When to use something else

- Elaboration failed because a module, package or file could not be **found** — a file-set problem owned by `dv-build-filelist-hygiene`. If
  the elaborator could not resolve a *name*, go there; if it resolved every name and then could not resolve a *discipline*, stay here.
- A simulation failed and you do not know why: `dv-sim-log-first-error`, then return once the failure is known to sit at the boundary. A red
  regression: `dv-regression-triage-routing`. The smallest run still showing a signature: `dv-minimal-reproducer`. A register read-back
  mismatch: `dv-ral-bringup`. Where the AMS rules live: `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Connect-rule selection | [[FILL: which connect-rule set our AMS flow selects, the file it lives in, and where the selection is made — control file, elaborator switch, or config]] | AMS lead |
| Connect-module library | [[FILL: which connect-module library we use, whether it is vendor-supplied or in-house, and whether its source can be read from disk]] | AMS lead |
| Supply parameter convention | [[FILL: how a connect module learns the supply of the domain it sits in for us — fixed parameters per rule, a supply map file, or supply-sensing modules — and where that mapping is written]] | AMS lead |
| Insertion report | [[FILL: how our elaborator is asked to list the connect modules it inserted, and where that listing lands]] | DV infra owner |
| Discipline defaults | [[FILL: which default-discipline setting our flow relies on, the files it is set in, and which discipline-resolution method our elaborator is configured for]] | AMS lead |
| Boundary inventory | [[FILL: which blocks in this testbench are true analog, which are real-number models and which are digital, how a real-number net is declared for us, and where that list is written down]] | block owner |
| Power net exclusions | [[FILL: how our rules keep supply and ground nets out of connect-module insertion, and the names those nets carry]] | AMS lead |
| Insertion budget | [[FILL: how many connect modules a healthy elaboration of this testbench inserts, taken from the last known-good run]] | AMS lead |
| AMS diagnostic markers | [[FILL: the strings our elaborator prints for a discipline-resolution failure and for a boundary it left unconverted]] | DV infra owner |

Two pack-wide facts come from `_shared/team-profile.md` instead: **Build log location**, where our elaboration output lands, and
**Simulator**, whose vocabulary the markers use. **AMS diagnostic markers is narrower than the profile's Fatal markers** — those are what a
*simulation* prints on a failing run, these what the *elaborator* prints before one started. **If a slot is unfilled, stop and ask**: an
invented rule-set name or supply figure describes a boundary that does not exist.

## Retrieval budget — read this before opening anything

An elaboration log with insertion reporting on prints one line per inserted connect module, so on an SoC it is larger than the source it
describes. Reading it is not an option.

1. **Grep and Read work on files on disk.** A pasted diagnostic cannot be searched: resolve it to a path first — step 1 — or say so, and mark
   everything downstream provisional.
2. **Never open the elaboration output or the insertion report with Read first.** They get **two Greps** — step 1 for the AMS diagnostic
   markers, step 7 to locate the report — and at most **three windowed Reads of ~80 lines**.
3. **Our own files** get **six Greps** and **four Reads of ~40 lines**: two Greps and one Read in step 2; two Greps and two Reads in step 3;
   and two more in the branch step 4 picks — step 5's `no-rule-matched` leg spends one on the default-discipline setting and its
   `ambiguous-discipline` leg none, while step 6 spends one on the supply mapping and one plus the last Read on the module's own default.
4. **Counting uses Grep hit counts, never Read.** Step 7 gets **five counting Greps** on top: one total, three hierarchy prefixes, one
   supply-net pattern; everything else it reports is arithmetic on those five. A count above about 200 hits *is* the finding — record it and
   stop.
5. Steps 5 to 7 are **alternatives**, so thirteen Greps and seven windowed Reads is what all of them would cost together and no single run
   spends more than eleven.
6. **Stopping rule.** Once that is spent with no settled symptom, report what is known and the one thing still needed, and **state what you
   covered** — which symptoms were ruled out from files, which were never opened.

## Procedure

### 1. Get the elaboration output onto disk and say which side broke

If the diagnostic arrived pasted into the chat, ask for the path under the profile's **Build log location**, or for the text to be saved to a
file and be given that path. Until a path exists you may reason over the pasted lines by eye, but say so: a pasted excerpt is a sample of
unknown position. Then use **one Grep** whose pattern alternates the **AMS diagnostic markers** — the single marker Grep budget rule 2 allows
— and **Read** one 80-line window at the earliest hit.

Now split the problem, because the owner differs. **Elaboration-time**: the elaborator complained and stopped, the symptom is
`no-rule-matched` or `ambiguous-discipline`, and everything you need is in source. **Run-time**: elaboration was clean and the failure
appeared once the run started, so the symptom is `wrong-supply` or `insertion-explosion` — and the elaboration output is still where you look,
because the insertion report was written there. If the **Insertion report** slot says our flow produces none by default, that is the first
handoff: **ask the engineer to elaborate again with connect-module reporting enabled and give you the path to the listing.**

### 2. Find out which connect rules were actually selected

The most common single cause of a missing converter. A rule set that is written, compiled and syntactically perfect does **nothing** unless
the flow selects it, and selection happens somewhere else entirely — a control file, an elaborator switch, a config. Two **Greps**: one for
the selection, at the location named in the **Connect-rule selection** slot; one for the `connectrules` keyword across the directory that slot
names. Then one 40-line **Read** of the block that was selected.

Record two facts verbatim, with file and line: **which rule set the flow selects**, and **whether the rules you have been reading are in it**
— several rule sets with one selected is normal for an AMS repository. While that window is open, note where the **Connect-module library**
slot says the module sources live; step 6 needs them, but do not open them yet.

### 3. Name the boundary — one net, two disciplines, both quoted

A converter is inserted where two different disciplines meet on one connected net set. Two **Greps**, one per side: the net or port name in
the analog block, and the same name in the digital block, looking for the `discipline` declaration that applies. Then one 40-line **Read** at
each hit. Use the **Boundary inventory** slot to know which side is which — whether the "analog" side is true analog or a real-number model,
since those take different converters, and how a real-number net is spelled here. A side with no declaration takes its discipline from
resolution, fed by the **Discipline defaults** slot; note which side is declared and which inferred, because where *both* are inferred it
usually is not a boundary.

### 4. Classify the symptom

| What you observe | Symptom | Settle it from | Usual cause |
|---|---|---|---|
| The elaborator names a net or port and says no connection rule applies | `no-rule-matched` | source | the rule set was never selected, or no rule covers this discipline pair or this direction |
| No converter exists and no diagnostic was printed — the analog side simply sees a logic value | `no-rule-matched` | source + report | both sides resolved to the same discipline, so there is no boundary for a rule to match |
| The elaborator refuses to resolve a net's discipline, or names two disciplines on one net | `ambiguous-discipline` | source | two incompatible declarations on one connected set, with no tie-break |
| The digital side sits at X from time zero while the analog side moves, or the converted value is defined but consistently wrong — a level, not a logic error | `wrong-supply` | source + waveform | thresholds, drive strength or output levels belong to a different supply domain, so nothing ever crosses them |
| Elaboration is clean but far slower or larger than it was, or the report lists many times the known-good count | `insertion-explosion` | the report | one converter per receiver or per bit where one per net was meant, or a discipline that leaked into a digital block |

Carry exactly one symptom forward. "Could be either" means step 3 is not finished — quote the second discipline first.

### 5. The elaboration-time pair — `no-rule-matched` and `ambiguous-discipline`

For `no-rule-matched`, check these in order and stop at the first that explains it; the first two usually do.

1. **Was the rule set selected at all?** Step 2 answered this. If not, that is the finding; stop rather than reading rules that never ran.
2. **Is there a boundary at all?** Two sides on the same discipline need no converter, so no rule can match — the quiet case with no
   diagnostic. Spend this leg's one branch **Grep** from budget rule 3 on the setting named in the **Discipline defaults** slot: a default
   making undeclared analog nets digital removes every boundary at once.
3. **Does a rule cover this pair, in this direction?** A set covering a continuous discipline against a logic discipline covers a
   **real-number** net against neither, those having their own converter family; and rules are per direction, so a genuinely bidirectional net
   — an `inout`, drivers on both sides, a pad, a bus with a keeper — needs its own rule.
4. **Is the net excluded?** A name matching the **Power net exclusions** slot is skipped silently, and "excluded" and "no rule matched" print
   the same nothing.

For `ambiguous-discipline` the elaborator is not confused — it was given two answers. Using step 3's open windows, quote **both declarations
verbatim with file and line**, usually a port declared in the instantiating module as well as the instantiated one; name **which side is
wrong** from the **Boundary inventory** slot rather than the seniority of the file, since that decides between the analog and digital block
owner in step 8; and check **whether the selected rule set carries a resolution statement**, because if it does the ambiguity is about that
statement and belongs to the connect-rule owner. Never propose deleting a declaration to silence the message; the Gotchas say why.

### 6. `wrong-supply` — three numbers from three sources

Thresholds and output levels come from the converter's parameters, which come from whichever of three places our flow uses, per the **Supply
parameter convention** slot. Put three numbers side by side, each with a file and a line:

- **The domain's real supply.** One **Grep** for the domain name in the supply mapping that slot names, if the mapping is a readable file; the
  hit line is the answer, so no Read is needed. If it is not a file, the number comes from the block owner — record who supplied it and mark
  the finding provisional.
- **The value the rule overrides.** From the `connect` statement in the selected rule set, in step 2's window. If there is no override there,
  say so explicitly, because then the next number is what ran.
- **The default in the connect module itself.** One **Grep** for the parameter name in the module source named by the **Connect-module
  library** slot, then the last 40-line **Read** at the declaration. If that library cannot be read — a compiled or encrypted release — treat
  the default as unknown and say so.

A converter carrying a 1.8 V threshold on a 1.2 V domain never sees a logic high, so its output holds its initial value forever — the
X-from-time-zero row in step 4, and a parameterisation bug, not the RTL bug it will otherwise be filed as. The agent cannot confirm the actual
voltage, so finish with a handoff: **ask the engineer to open the waveform at the boundary net and read out the analog level and the converted
digital value at the same time**, and record that the answer came from a person.

### 7. `insertion-explosion` — count, do not read

Counting the report with **Read** is impossible and with **Grep** trivial. Spend the second log **Grep** from budget rule 2 to locate it, then
the five counting **Greps** from rule 4 — one total, three prefixes, one supply-net:

1. **Total inserted** (Grep 1), against the **Insertion budget** slot. With no known-good figure there is no explosion, only a large number —
   say that rather than calling it one.
2. **The ratio.** Divide the total by the boundary-net count the **Boundary inventory** slot leads you to expect. A small integer multiple
   points at multiplication — one converter per receiver where one per net was meant, or one per bit of a vector — while orders of magnitude
   point at a whole block on the wrong discipline.
3. **Where they are** (Greps 2 to 4). Count hits under the **three** most likely hierarchy prefixes, cheapest first — three, not "as many as
   it takes", because the fifth Grep is committed below. The prefix holding most insertions names the block whose discipline leaked; dividing
   its count by that block's instance count separates a scope error from a rule error.
4. **Supply nets in the report** (Grep 5). One pattern alternating the names in the **Power net exclusions** slot. Any hit is a finding on its
   own, and on a net with that fanout a large fraction of the total. Give every count a denominator.

### 8. Report

Write the failure as a signature following `_shared/failure-signature-schema.md` — same field order, same normalisation rules — then fill in
this block, whose `signature`, `cause`, `phase`, `class`, `run id`, `log` and `notes` are fields `dv-sim-log-first-error` and
`dv-build-filelist-hygiene` already use, so a failure routed from either keeps its vocabulary.

```
signature : <phase>|<kind>|<where>|<what>
symptom   : <no-rule-matched | ambiguous-discipline | wrong-supply | insertion-explosion>
boundary  : <the net, and the discipline on each side, each with a file and a line>
phase     : compile | elab | run | finalise | post
class     : design | infrastructure | unknown
rules     : <the rule set actually selected, and the line that selects it>
inserted  : <n reported by the elaborator against the known-good figure, or "not reported">
cause     : <the verbatim line that explains it — diagnostic, rule, or declaration>
evidence  : <file and line, or log line number, for every claim above>
owner     : <analog block owner | digital block owner | connect-rule owner | AMS flow owner>
run id    : <whatever identifies this elaboration for us>
log       : <path, and the line range worth reading>
coverage  : <which of the four symptoms were ruled out from files, and which were never opened>
notes     : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

`class` and `owner` are read off the **cause**, not off the symptom — the same symptom lands on either side of the design/infrastructure line
depending on what produced it — so take both from this table:

| What the evidence says | class | owner |
|---|---|---|
| The rule set was never selected, the flow selects a different one, a default-discipline setting removed the boundary, or the connect-module library is the wrong release or unreadable | infrastructure | AMS flow owner |
| No rule covers this discipline pair or direction; a rule's supply override is wrong; the tie-break statement is wrong | design | connect-rule owner |
| A discipline declaration is wrong, or two of them disagree | design | the owner of the side step 5 named as wrong — analog block owner or digital block owner |
| One block's discipline leaked and multiplied the insertions | design | the block owner of the prefix step 7 counted |
| Nothing settled inside the budget | unknown | leave blank and list the candidates |

`phase` is the phase of the step that *failed*, as `dv-sim-log-first-error` defines it, not always the phase in which the converter was wrong:
`elab` for the two elaboration-time symptoms; `run` while the simulator was running; `finalise` when the only thing that noticed was an
end-of-test check in the end-of-run report, where a value that never left its initial state surfaces; `post` when the failing step ran after
the simulator exited — the runtime or count comparison that normally catches an insertion explosion. A `compile` break is a file-set problem,
routed away at the top. The four `symptom` values are **local to this skill**, so name the skill whenever one is quoted elsewhere; `kind` is
usually `tool` at elaboration and `xprop` at run time. Anything not fillable from disk gets `?`.

## Gotchas

- **Silence proves nothing — not that a rule ran, nor that a converter exists.** A rule set that is never selected compiles, is valid and
  inserts nothing, with no warning; insertion is itself silent unless the report is asked for. Check selection before reading a rule.
- **The quiet failure is worse than the loud one.** Two sides on the same discipline need no converter, so nothing is printed and the analog
  block gets a bare logic value a solver will integrate into nonsense. That is why deleting a declaration to silence an ambiguity is a
  downgrade, not a fix: it turns the loud error into the quiet one.
- **Real-number nets are not analog nets, and multiply-driven ones need a declared resolution.** A real-valued net is discrete in time with
  its own converter family, so rules covering a continuous discipline against logic cover neither leg — mixing a real-number model and a true
  analog model on one net reliably ends in no rule matched. Two drivers with no combining rule is a separate bug, visible at the declaration.
- **Inserted converters carry tool-generated instance names.** Any waveform script, force, probe or assertion written against a hierarchical
  path through the boundary breaks the moment the rules change — and looks like a design change, because the path no longer exists.
- **X does not survive the boundary, and time zero is not a bug.** A digital X into a converter usually produces defined analog behaviour —
  mid-supply, a hold, high impedance — so an X bug vanishes at the boundary and reappears downstream as a wrong level. The other way, the
  converted value is commonly X before the first analog solution, so a strap sampled early reads X in a correct testbench.
- **A converter on a supply or ground net is always wrong, and a bidirectional boundary is often simply not driven.** Exclusions fail quietly
  when a net is renamed, so look for supply names before believing a large count; and what a bidirectional converter does when the digital
  side releases is a property of that converter, not the design.

## Human verification — what a wrong answer looks like

- The boundary names **one** net with **two** disciplines, each quoted with a file and a line, and the `rules` line names the rule set the
  flow actually selects rather than the one that was read. If those differ, that difference is the finding.
- The symptom is exactly one of the four, its step 4 row is quoted, and `class` and `owner` came from the step 8 table rather than the symptom
  alone: a rule set that was never selected is an infrastructure finding for the AMS flow owner, not a design bug against whoever wrote the
  rules.
- A `wrong-supply` finding shows **three** numbers from three sources, and any number that came from a person rather than a file says so and
  is provisional. An `insertion-explosion` finding carries a denominator and names its three prefix counts.
- Nothing the Gotchas call correct behaviour — a time-zero X, a converter holding when the digital side releases, an excluded net — is filed
  as a bug, and the coverage line says which symptoms were ruled out from files and which were never opened.

A wrong answer blames the digital block for a converter parameterised to another supply domain; declares "the connect rules are wrong" without
establishing which rule set ran; proposes deleting a declaration to clear an ambiguity; or calls a count an explosion with no known-good
figure beside it.

## Done when

You can name the boundary net, one of the four symptoms, its single line of evidence, and the one person who fixes it — and you have said
which of the other three you never opened.
