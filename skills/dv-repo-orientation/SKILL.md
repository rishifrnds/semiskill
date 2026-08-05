---
name: dv-repo-orientation
description: Map an unfamiliar DV repository on day one — filelists, build entry points, test lists, run areas and coverage output — then trace one named test end to end and write the map down for the next joiner. Use when you have just been handed a verification repo you have never seen, when you cannot tell how a test is chosen or built, when someone tells you to just look at how the other blocks do it, or when you are about to interrupt a senior engineer for the fourth time in a morning.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Orienting Yourself in an Unfamiliar DV Repository
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-06-11
  semiskill-tags: onboarding, repo-map, filelists, build-flow, regression, coverage
---

# Orienting Yourself in an Unfamiliar DV Repository

On day one the map of a verification repo exists only in the heads of the three people who built it,
and every question costs one of them fifteen minutes and their place in a debug session. The usual
mistake is to open a testbench file at random, read a thousand lines of class hierarchy, and still
not know how a test is selected, compiled, run or scored. Structure is cheaper than code: filelists,
build entry points and test lists tell you most of it before you read a single class.

Written for a day-one joiner of any DV role. The judgement it demands is not DV expertise — it is
refusing to write down anything you did not actually see.

The output is **a repo map plus a numbered list of questions for your mentor** — explicitly *not* a
claim to have understood the design, the verification plan, or whether the tests are any good.

**Not this skill.** A build that fails to compile or elaborate belongs to `dv-build-filelist-hygiene`.
One failing simulation log belongs to `dv-sim-log-first-error`. A night of regression failures
belongs to `dv-regression-triage-routing`. Orientation stops at the machinery: it maps how a test is
chosen, built, run and scored, and never explains why one failed.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Repo and branch | [[FILL: the repo we clone for this block, and the branch a new joiner starts on]] | your mentor |
| Build entry point | [[FILL: the makefile, wrapper script or flow command we actually invoke to build, and the simulator and elaborator command names that appear inside it]] | DV infra owner |
| Filelist directives | [[FILL: the extensions our filelists use, the directive that nests one filelist inside another, the directive that adds an include path, and what relative paths resolve against]] | DV infra owner |
| Test list | [[FILL: where the list of tests lives, what one row of it means, and the file names, keys or variable names worth grepping to find it]] | DV lead |
| Run area | [[FILL: where one run's output directory lands, how it is named, how long it survives]] | your mentor |
| Coverage output | [[FILL: where coverage databases and reports land, what combines them, and the option strings and output names our flow uses for coverage]] | coverage owner |
| House conventions | [[FILL: our naming rules for tests, sequences, files and directories]] | DV lead |
| Escalation path | [[FILL: the person or channel that takes the questions this procedure cannot answer]] | your manager |

**If a slot is unfilled, stop and ask. Do not guess a convention** — a map naming an invented build
target, tool option or log path is worse than no map, because the next joiner inherits it and spends
a day proving it wrong.

Two of these are the same facts `dv-build-filelist-hygiene` asks for under *Filelist entry point* and
*Filelist directives*. Fill them once for the team and reuse the same answer in both skills; if they
ever disagree, one of the two maps is stale.

## Retrieval budget — read this before opening anything

A block-level DV repo commonly holds tens of thousands of files; a top-level one holds hundreds of
thousands, with filelists thousands of lines long. Reading broadly is not an option.

1. **Glob is nearly free; Read is the budget.** Survey the tree with **Glob** patterns first and
   record *paths only*. Do not open a file during the survey.
2. **Never Read a filelist, a test list or a log whole.** **Grep** for the entry you want, note the
   line number, then Read a window of about 60 lines around it.
3. Cap the orientation at roughly **12 Glob patterns, 15 Greps, and 10 windowed Reads of about 80
   lines** — enough for the step 1 survey (at most 8 patterns), the documentation in step 2 and the
   single trace in step 5, and already a full session's attention.
4. A Glob returning more than about 300 paths is too broad — narrow it to one directory first. **A
   result that hit your runtime's limit is not a count.** Record it as "at least N, truncated" and
   never put a truncated number into the map as if it were a measurement.
5. **Pasted text is not a file.** You can read a short excerpt someone pastes back, but you cannot
   Grep it. If you need to search build or run output, ask for its path on disk first.
6. **Stopping rule.** Stop when you can name, each with a path, the build entry point, the test list,
   one test's own files, and where results and coverage land — or when the budget above is spent.
   Everything still unknown at that point becomes a numbered question, never an inference.

## Procedure

### 1. Survey the tree breadth-first, before reading anything

Use **Glob**, one pattern at a time, and write down the paths. Start with the five patterns that find
*structure*, because every hit also names a directory — the skeleton comes free, without a broad
source-file sweep:

- `**/{Makefile*,makefile*,*.mk}` — build entry points and included fragments
- `**/*.{f,flist,filelist}` — filelists, using whichever extensions the slot table records
- `**/{README*,*.md}` — whatever documentation exists
- `**/*.{py,pl,csh,sh}` — flow wrappers
- `**/*.{yaml,yml,json,cfg}` — regression and tool configuration

If your runtime does not expand brace groups the pattern returns nothing; run the alternatives one at
a time and count each against the budget. On a case-insensitive filesystem `Makefile` and `makefile`
match the same file, so de-duplicate paths before counting anything.

Only now go after source, and **one directory at a time**: from the directories those hits named,
pick at most three candidate trees and Glob `<dir>/**/*.{sv,svh,v}` in each. A repo-wide `**/*.sv`
breaks budget rule 4 — it returns tens of thousands of paths, gets truncated, and the truncation
limit then gets written into the map as a file count.

A directory holding hundreds of source files and one holding six are different kinds of thing, and
the shape already suggests which tree is design, which is testbench and which is abandoned — but only
compare counts that were **not** truncated. Test and sequence file naming is a house convention: if
`<dir>/**/*test*.sv` misses, that tells you the convention differs, not that there are no tests.

### 2. Read the documentation that does exist, however stale

Use **Read** on any README at the repo root and one level below it, plus the most promising file
under a `doc/` directory. Mark every claim as unverified. Stale documentation is still the cheapest
source of *vocabulary* — block names, the team's word for a regression, the shape of a test name —
and you need that vocabulary to make the next Greps specific rather than broad.

### 3. Identify the build entry points — the invocation and the definition

Start from the **Build entry point** slot, not from a Glob hit. If that slot is unfilled, stop and
ask; the rest of this step searches for strings only the slot can supply.

Use **Grep** on the makefiles and wrappers for target-shaped lines (`^[A-Za-z0-9_.-]+:`), then for
the simulator and elaborator command names recorded in that slot. Tool vocabulary differs by vendor
and by flow — searching for the commands of a simulator your team does not run returns zero hits on
the one step that is supposed to find the build, which is the worst possible outcome on day one.

**The file you invoke and the file holding the options are usually not the same file**, and this is
the single distinction the step exists to make:

- the **invocation** is the shallowest file in the call chain, often at the repo root, usually a thin
  wrapper that sets environment variables and calls something deeper
- the **build definition** is the deepest file in that same chain that names both a filelist and a
  simulator command

Record both paths and label which is which. Do **not** reconstruct a full command line from fragments
scattered across three files — that is the single most tempting invention in this whole procedure.

Handoff: ask the engineer to build one test in a scratch area and send back the first 40 lines of
console output plus the compile line the flow echoes, and to say where that output was written. That
echoed line is ground truth; everything inferred from the makefile is a hypothesis until it matches.

### 4. Find the test list, and work out what a test *is* here

Use **Grep** for `+UVM_TESTNAME` — the standard UVM plusarg, if this is a UVM testbench — and for the
file names, keys and variable names recorded in the **Test list** slot. Names like a test-list file
or a tests key are house conventions, not universals: take them from the slot, not from memory.

Then classify, because the rest of the procedure depends on the answer — a test in this repo is one
of:

- a SystemVerilog class that a plusarg selects,
- a row in a structured regression list that names options and a seed count,
- a directory of stimulus plus a configuration file, or
- a target in the build system itself.

Keep apart two things new joiners routinely conflate: the **list of tests** a regression walks, and
the **definition of one test**. Different files, often different owners.

### 5. Trace one named test end to end

Pick a test the team itself calls a smoke or sanity test — the **Test list** slot or your mentor
names it. Do not pick by name length or by position in the list; neither predicts how many layers a
test has.

Use **Grep** for that exact string across the tree, then interpret whatever count comes back. Any of
these is normal in some repo; the count tells you what to do next, not that something is wrong:

- **hits only in the list** — the label is mapped to a class by a table, a prefix rule or a factory
  override (see the Gotchas). Find the mapping before going further.
- **a handful of hits** — typically the list entry, the class declaration, perhaps a sequence or an
  exclusion. That is enough to trace.
- **dozens of hits** — the name is a substring of something common. Narrow to one directory, or Grep
  a longer anchored form of the name.

Use **Read** on about 60 lines around the class declaration and record what it extends, which
sequence it starts, and which configuration it sets. Then **Grep** the parent class name once to find
the base test and read its build and run phases. One level of parent is enough; walking the whole
hierarchy loses the budget.

Write the chain out explicitly:

```
list entry -> test class -> base class -> env -> filelist -> build target -> run area
```

Any link you cannot back with a file and a line number is a question, not a conclusion.

### 6. Locate where results and coverage land

Use **Grep** on the build scripts and configuration for the coverage option strings and output names
recorded in the **Coverage output** slot, plus the words the team uses for its log and report
directories.

Do **not** Glob for coverage databases. Coverage output is produced by a run, into a run area that is
usually outside the source tree and often on a different filesystem; on a fresh clone the Glob
returns nothing and the map records "coverage: none found", which is false and gets inherited. What
the scripts *name* is a hypothesis; only a real run confirms it.

Two distinct places matter and are constantly conflated: the **per-run scratch directory**, usually
deleted on a schedule, and the **kept, combined coverage area** that sign-off reads. Record both,
plus how long each survives.

Handoff: ask the engineer to run one test the team says passes today, and to send back the
output-directory path the flow printed. A path derived from a script is a guess until one real run
confirms it.

### 7. Derive house conventions from sibling code, not from questions

Use **Read** on two files that do the same job for different blocks — two test classes, two
filelists, two env files. **What is identical across both is the convention; what differs is the
content.** Ten minutes of this yields naming rules, file layout, header format, macro usage and the
standard registration idiom, at zero cost to anyone's afternoon.

Where two siblings disagree, prefer the one the current test list points at, and record the
disagreement as a question. A rule seen in one file is a coincidence; seen in two, it is a convention.

### 8. Write the map, and the question list beside it

Keep it short and evidence-linked — every line names a path that appeared in a real Glob or Grep
result:

```
repo map v1  — author, date
invocation   : path we are told to invoke      targets: names
build defn   : path holding the real options   filelist it names: path
filelists    : paths                           nesting followed: 1 level
test list    : path                            one row means: class | config row | directory | build target
one test     : name -> class file:line -> base class file:line -> sequence
run area     : path pattern                    retention: ?
cov output   : db path -> report path          combined by: ?
conventions  : 3-5 observed rules, each with the two sibling files that show it
map coverage : <n of the 8 rows above backed by a real Glob or Grep hit>; <what the budget did not reach>
unknowns     : numbered questions for the mentor
```

`map coverage` is not optional. A map that surveyed three of eight rows and says so is useful; the
same map without that line reads as a complete answer and is not one — an unstated shortcut is far
worse than a stated one.

Every `?` is a question, and the question list is the deliverable that makes this worth doing twice.
A map with no `?` after one day is a map containing inventions.

## Gotchas

- **The makefile at the repo root is usually not the build definition.** Most teams keep a thin
  wrapper there that sets environment variables and hands off to a deeper flow holding the options
  that matter. Follow the call, and record both paths — this is why step 3 asks for two of them.
- **Filelists include other filelists.** A filelist can name another filelist instead of a source
  file, using whichever directive our tool spells it with (**Filelist directives** slot). When it
  does, what you are reading is a fraction of the compile unit. Follow one level of nesting, then
  record the rest as unexplored rather than assuming the list is flat. How relative paths inside a
  nested filelist resolve is in that same slot and changes which files you are actually looking at.
  A full audit is `dv-build-filelist-hygiene`'s job; here you only need to know the list is not flat.
- **An include path is not a filelist.** Filelists carry include-path directives as well as source
  files. Include directories resolve `` `include `` at compile time, so a class can be compiled into
  the design without its own file ever appearing in any filelist. If a class you can Grep for is in
  no filelist, it is very likely pulled in by an `` `include `` inside a package file that *is*
  listed.
- **The name in the test list is often not the class name.** Many flows map a short label to a longer
  class through a table, a prefix rule, or a factory override. Prove the mapping with a Grep hit;
  resemblance is not evidence.
- **Two directories named `tb` are normal.** Large repos carry a block-level and a subsystem
  testbench with identical directory names at different depths. Record full paths always — a relative
  path in your map will send the next joiner to the wrong tree.
- **Generated files look exactly like source.** Register models, configuration classes and coverage
  models are frequently produced from a spec during the build. A "do not edit" header means the real
  source is elsewhere — ask which spec generates it before reading a line of it.
- **The newest-looking directory is often dead.** An abandoned migration leaves a parallel tree that
  still compiles but appears in no test list. If nothing in the test list reaches it, treat it as
  inactive and put it on the question list rather than studying it.
- **Coverage exclusions are a separate axis from the test list.** Waivers and exclusion files change
  the reported number without changing any test, and they live in directories nobody mentions during
  onboarding. Find them now, or be surprised at sign-off.
- **History is unavailable to the agent.** Blame, log and diff need a shell, so "who changed this and
  why" is always a handoff to a person, never an inference from how the code looks.

## Human verification — what a wrong answer looks like

Before you hand the map to anyone, check:

- every path in the map appeared in an actual Glob or Grep result, and you can say which
- no number in the map came from a Glob result that was truncated
- every tool option or command name in the map came from a filled slot or from output a real run
  printed, never from what a simulator elsewhere is called
- each link in the traced test chain carries a file **and a line number**, not a plausible name
- the build entry point was confirmed by a real build the engineer ran, not read off a makefile
- the `map coverage` line is present, and the unknowns list is **not empty**

A wrong map reads fluently and names a build target that does not exist, or a `results/` directory
the flow would sensibly use but never writes to. Its second signature is confidence about what the
design *does* — this procedure only maps the machinery around the design, and claiming more than
that is exactly the failure it exists to prevent.

## Done when

The next new joiner reaches the build entry point, the test list and one test's files from your map
alone, every number in it survives being checked, and every remaining unknown is written down as a
question instead of a guess.
