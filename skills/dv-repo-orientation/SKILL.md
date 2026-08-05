---
name: dv-repo-orientation
description: Map an unfamiliar DV repository on day one — filelists, build entry points, test lists, run areas and coverage output — then trace one named test end to end and write the map down for the next joiner. Use when you have just been handed a verification repo you have never seen, when you cannot tell how a test is chosen or built, when someone tells you to just look at how the other blocks do it, or when you are about to interrupt a senior engineer for the fourth time in a morning.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Orienting Yourself in an Unfamiliar DV Repository
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: fresher
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-02-05
  semiskill-tags: onboarding, repo-map, filelists, build-flow, regression, coverage
---

# Orienting Yourself in an Unfamiliar DV Repository

On day one the map of a verification repo exists only in the heads of the three people who built it,
and every question you ask costs one of them fifteen minutes and their place in a debug session. The
usual mistake is to open a testbench file at random, read a thousand lines of class hierarchy, and
still not know how a test is selected, compiled, run, or scored. Structure is cheaper than code:
filelists, build entry points and test lists tell you most of it before you read a single class.

The output of this procedure is **a repo map plus a numbered list of questions for your mentor**. It
is explicitly *not* a claim to have understood the design, the verification plan, or whether the
tests are any good.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Repo and branch | [[FILL: the repo we clone for this block, and the branch a new joiner starts on]] | your mentor |
| Build entry point | [[FILL: the makefile, wrapper script or flow command we actually invoke to build]] | DV infra owner |
| Test list | [[FILL: where the list of tests lives, and what one row of it means]] | DV lead |
| Run area | [[FILL: where one run's output directory lands, how it is named, how long it survives]] | your mentor |
| Coverage output | [[FILL: where coverage databases and reports land, and what combines them]] | coverage owner |
| House conventions | [[FILL: our naming rules for tests, sequences, files and directories]] | DV lead |
| Escalation path | [[FILL: the person or channel that takes the questions this procedure cannot answer]] | your manager |

**If a slot is unfilled, stop and ask. Do not guess.** A repo map that names an invented build target
or an invented log path is worse than no map at all, because the next joiner will inherit it and
spend a day proving it wrong.

## Retrieval budget — read this before opening anything

A block-level DV repo commonly holds tens of thousands of files; a top-level one holds hundreds of
thousands, with filelists thousands of lines long. Reading broadly is not an option.

1. **Glob is nearly free; Read is the budget.** Survey the whole tree with **Glob** patterns first
   and record *paths and counts only*. Do not open a file during the survey.
2. **Never Read a filelist, a test list or a log whole.** **Grep** for the entry you want, note the
   line number, then Read a window of about 60 lines around it.
3. Cap the orientation at roughly **12 Glob patterns, 15 Greps, and 10 windowed Reads of about 80
   lines** — enough for a first map, and already a full session's attention.
4. If a Glob returns more than about 300 paths, the pattern is too broad — narrow it to one directory
   before looking at the result.
5. **Stopping rule.** Stop when you can name, each with a path, the build entry point, the test list,
   one test's own files, and where results and coverage land — or when the budget above is spent.
   Everything still unknown at that point becomes a numbered question, never an inference.

## Procedure

### 1. Survey the tree breadth-first, before reading anything

Use **Glob**, one pattern at a time, and write down directory names and hit counts:

- `**/Makefile`, `**/makefile`, `**/*.mk` — build entry points
- `**/*.f`, `**/*.flist`, `**/*.filelist` — compile filelists
- `**/*.sv`, `**/*.svh`, `**/*.v` — where RTL and testbench actually live
- `**/*test*.sv`, `**/*seq*.sv` — test and sequence classes
- `**/*.yaml`, `**/*.yml`, `**/*.json`, `**/*.cfg` — regression and tool configuration
- `**/*.py`, `**/*.pl`, `**/*.csh`, `**/*.sh` — flow wrappers
- `**/README*`, `**/*.md`, `**/doc/**` — whatever documentation exists

A directory with 400 `.sv` files and one with 6 are different kinds of thing; the shape of the counts
already suggests which tree is design, which is testbench, and which is abandoned.

### 2. Read the documentation that does exist, however stale

Use **Read** on any README at the repo root and one level below it, plus the most promising file
under a `doc/` directory. Mark every claim as unverified. Stale documentation is still the cheapest
source of *vocabulary* — block names, the team's word for a regression, the shape of a test name —
and you need that vocabulary to make the next Greps specific rather than broad.

### 3. Identify the build entry points

Use **Grep** on the makefiles and wrappers for target-shaped lines (`^[A-Za-z0-9_.-]+:`) and for
simulator vocabulary — `vcs`, `simv`, `xrun`, `-sverilog`, `-full64`, `-ntb_opts`, `+incdir`,
`-timescale`. The real entry point is usually the shallowest file that mentions **both** a filelist
and a simulator binary name.

Record the path and the target names. Do **not** reconstruct a full command line from fragments
scattered across three files — that is the single most tempting invention in this whole procedure.

Handoff: ask the engineer to build one test in a scratch area and paste back the first 40 lines of
console output plus the compile line the flow echoes. That echoed line is ground truth; everything
inferred from the makefile is a hypothesis until it matches.

### 4. Find the test list, and work out what a test *is* here

Use **Grep** for `UVM_TESTNAME`, `+testname`, `testlist`, `TESTS`, `tests:`, `regression`. Then
classify, because the rest of the procedure depends on the answer — a test in this repo is one of:

- a SystemVerilog class that a plusarg selects,
- a row in a YAML or CSV regression list that names options and a seed count,
- a directory of stimulus plus a configuration file, or
- a target in the build system itself.

Keep apart two things new joiners routinely conflate: the **list of tests** a regression walks, and
the **definition of one test**. Different files, often different owners.

### 5. Trace one named test end to end

Pick the shortest-named smoke or sanity test in the list — it has the fewest layers.

Use **Grep** for that exact string across the tree. Expect three to six hits: the list entry, the
class declaration, perhaps a sequence, perhaps a coverage exclusion. Use **Read** on about 60 lines
around the class declaration and record what it extends, which sequence it starts, and which
configuration it sets. Then **Grep** the parent class name once to find the base test and read its
build and run phases. One level of parent is enough; walking the whole hierarchy loses the budget.

Write the chain out explicitly:

```
list entry -> test class -> base class -> env -> filelist -> build target -> run area
```

Any link you cannot back with a file and a line number is a question, not a conclusion.

### 6. Locate where results and coverage land

Use **Grep** on the build scripts and configuration for `-cm`, `coverage`, `covdb`, `urg`, `vdb`,
`ucdb`, `logdir`, `report`. Use **Glob** for `**/cov*/**` and `**/*.vdb` to see whether output lands
inside the repo or somewhere else entirely.

Two distinct places matter and are constantly conflated: the **per-run scratch directory**, usually
deleted on a schedule, and the **kept, combined coverage area** that sign-off reads. Record both,
plus how long each survives.

Handoff: ask the engineer to run one passing test and paste the output-directory path the flow
printed. A path derived from a script is a guess until one real run confirms it.

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
repo map v1 — author, date
build       : path to entry point       targets: names
filelists   : paths                     compiled by: target
test list   : path                      one row means: class | yaml row | directory
one test    : name -> class file:line -> base class file:line -> sequence
run area    : path pattern              retention: ?
coverage    : db path -> report path    combined by: ?
conventions : 3-5 observed rules, each with the two sibling files that show it
unknowns    : numbered questions for the mentor
```

Every `?` is a question, and the question list is the deliverable that makes this worth doing twice.
A map with no `?` after one day is a map containing inventions.

## Gotchas

- **The makefile at the repo root is usually not the entry point.** Most teams keep a thin wrapper
  that sets environment variables and hands off to a deeper flow holding the options that matter.
  Follow the call, and record both paths.
- **Filelists include other filelists.** A `-f` line inside a `.f` file means what you are reading is
  a fraction of the compile unit. Follow one level of `-f`, then record the rest as unexplored rather
  than assuming the list is flat.
- **`+incdir` is not a filelist.** Include directories resolve `` `include `` at compile time, so a
  class can be compiled into the design without its file ever appearing in any filelist. If a class
  you can Grep for is in no filelist, it is almost certainly pulled in by an `` `include `` inside a
  package file that *is* listed.
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
- each link in the traced test chain carries a file **and a line number**, not a plausible name
- the build entry point has been confirmed by a real build the engineer ran, not derived from a
  makefile alone
- the unknowns list is **not empty**

A wrong map reads fluently and names a build target that does not exist, or a `results/` directory
the flow would sensibly use but never writes to. Its second signature is confidence about what the
design *does* — this procedure only maps the machinery around the design, and claiming more than
that is exactly the failure it exists to prevent.

## Done when

A new joiner can reach the build entry point, the test list, and one test's files from your map
alone, and every remaining unknown is written down as a question instead of a guess.
