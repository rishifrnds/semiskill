---
name: dv-build-filelist-hygiene
description: Decode a build that fails to compile or elaborate, then audit the one filelist behind it for stale, duplicated, missing and shadowed entries. Use when a compile or elaboration error is pasted in or a build log path is given, when a module or package cannot be found, when an include file or a define is missing, when a module is reported as already defined, or when a block-level build passes and the top-level build fails on the same source.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Compile and Elaboration Error Decode with Filelist Hygiene
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-05-23
  semiskill-tags: build, filelist, compile, elaboration, includes, defines, packages, triage
---

# Compile and Elaboration Error Decode with Filelist Hygiene

A build that will not compile is the highest-frequency thing a DV engineer pastes into a chat, and
the error text is the least useful part of it. The compiler reports the *consequence* of a missing
file, a missing include path, a missing define or a wrong file order — twenty times over — while the
elaborator reports a module it cannot resolve without saying which filelist was meant to contain it.
The answer lives in the filelists, which nobody audits because auditing them is tedious, not hard.

The output is three things: **a classified first diagnostic, the filelist evidence for it, and a
bounded audit of the one filelist that produced it.** Not a restatement of the error.

**This skill audits one diagnostic and one filelist per pass.** It never flattens a whole SoC file
set. That set runs to several thousand entries, and no procedure built on Read, Grep and Glob can
assemble it — a previous revision of this skill asked for exactly that and was unusable because of
it. What replaces the flatten is a *bounded ordered slice*: only the branch of the filelist tree
holding the entries whose order or existence is actually in question.

## When to use this, and when not to

- The **build** failed and nothing ran — this skill.
- A simulation started and then failed: that is a simulation log, and `dv-sim-log-first-error` is the
  skill. It classifies build breaks as infrastructure and routes them back here.
- A whole regression is red: sort it with `dv-regression-triage-routing` first, then bring the one
  build failure here.
- You have a signature and want the smallest test that still shows it: `dv-minimal-reproducer`.
- You do not yet know where the filelists live: `dv-repo-orientation` is the map. This skill assumes
  the entry point is already known or filled into the slot table below.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Build log location | [[FILL: where our compile and elaboration logs land, and how long they are kept]] | your mentor |
| Filelist entry point | [[FILL: the filelist the top build actually consumes, and where block filelists live]] | DV infra owner |
| Filelist directives | [[FILL: the directives our filelists use for nested inclusion, include paths, macro defines and library search, and what relative paths resolve against]] | DV infra owner |
| Error markers | [[FILL: the strings our compiler and elaborator print to mark an error and to mark a warning]] | DV infra owner |
| Build-finished marker | [[FILL: the string our flow prints when analysis completes and elaboration begins, and the string printed when the whole build succeeds]] | DV infra owner |
| Diagnostic wording | [[FILL: the actual opening words our tools print for each fault class in the step 4 table — the table holds paraphrases, not strings any tool emits]] | DV infra owner |
| Build parallelism | [[FILL: whether our build analyses files one at a time into one log in filelist order, or in parallel or partitioned batches, or one log per file]] | DV infra owner |
| Compilation-unit grouping | [[FILL: whether our flow analyses a filelist as one compilation unit or each file as its own, and whether the block and top flows differ in this]] | DV infra owner |
| Order evidence | [[FILL: whether our build writes a resolved file list or compile-order manifest we can read instead of reconstructing one, and where it lands]] | DV infra owner |
| Duplicate policy | [[FILL: whether our tool errors on a duplicate module definition or silently keeps one, and which one it keeps]] | DV infra owner |
| Generated sources | [[FILL: which files in our filelists are generated, and by which step]] | DV infra owner |
| Block versus top | [[FILL: which filelist a block build uses versus the top build, and which defines differ between them]] | verification lead |
| External filelists | [[FILL: who owns the IP release filelists we consume but do not control]] | verification lead |

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented filelist path, build
command or directive name sends the engineer to audit a file set that is not the one that failed.

## Retrieval budget — read this before opening anything

Build logs are smaller than simulation logs, but filelists nest, and a top-level file set expands to
several thousand entries. Work in this order and stop as soon as the first diagnostic is explained:

1. **Never open the build log with Read first.** Budget for the log: one **Grep** for error markers,
   one for the build-finished marker, then at most three windowed Reads of about 80 lines.
2. Read a filelist whole only if it is under about 300 lines. Above that, **Grep** for the directive
   of interest and Read bounded windows around the hits.
3. Expand nested filelists to a depth of **four** at most, and to **twelve** filelist files in total.
   Record the ones you did not open instead of opening them.
4. Scope every **Glob** and **Grep** to one directory; a recursive search from the repository root
   returns tens of thousands of paths. Above about 200 hits, narrow before reading.
5. Cap the mechanical audit at about **forty** existence checks and **forty** Greps in one pass. If
   the filelist is longer than that, check the entries named in the diagnostics first, then a
   contiguous window around them — and report the fraction you checked.
6. **Stopping rule.** Stop when the first diagnostic is classified with a cited filelist line and the
   coverage line is filled. A second unexplained diagnostic is a second pass, not more reading.
7. **State the coverage.** Every count in the report carries a denominator. An unstated shortcut is
   far worse than a stated one.

## Procedure

### 1. Get the failing text onto disk, or say plainly that you could not

**Grep and Glob run on files, not on chat text.** If the diagnostic was pasted into the conversation,
nothing in steps 2 and 3 can be done to it.

- **A path was given, or the build-log-location slot leads to one.** Use it. Continue at step 2.
- **Only pasted text.** Ask the engineer for the log's path on disk, or ask them to save the pasted
  text to a file and give you that path. This is not a formality — the whole ranking argument in
  step 3 depends on seeing the whole log.
- **No path can be produced.** You can still classify the pasted diagnostic in step 4 from the text
  in front of you, and you can still audit filelists from step 5 on, because those are files. What
  you cannot do is claim the pasted diagnostic is the *first* one: a pasted excerpt is a sample of
  unknown position. Mark the classification provisional and write `coverage : pasted excerpt only,
  position in log unknown`.

### 2. Separate a compile failure from an elaboration failure

Use **Grep** for the error markers from the slot table, then decide which side broke — the two have
different causes and often different owners. Also **Grep** for the build-finished marker; if the
analysis-complete marker is absent, the build never reached elaboration and every elaboration-shaped
theory is wrong.

- **Compile (analysis)** diagnostics cite a source file and a line number in a file being analysed.
  They are about text — syntax, unknown macros, unknown types, unreadable includes.
- **Elaboration** diagnostics cite a module name, an instance path or a hierarchical name, often with
  no source line at all. They are about binding — which module, which parameter, which port.

### 3. Rank the diagnostics — provisionally, and say so

Print order equals filelist order **only when the flow analyses files one at a time into a single
log**. That is a common and perfectly ordinary configuration, and where it holds, print order is the
best ordering evidence available. Where the flow analyses in parallel or partitions the compile,
output from unrelated files interleaves and print order across files means nothing. Which one applies
is the **Build parallelism** slot. Read it before either trusting or discarding print order.

- **Sequential, one log.** Print order is analysis order, so the first error printed is the first
  error — but confirm the run really was sequential before relying on it. A flow that analyses in
  parallel or partitions the file set interleaves its output even into a single log, and a
  concurrency setting is easy to change without anyone re-reading this. If the file and line numbers
  in the log do not climb monotonically, treat it as the parallel case below.
- **Parallel, partitioned, or one log per file.** Collect the file and line of every error with
  **Grep**, group by file, and take the lowest line number within each file. Carry forward at most
  the **three** earliest candidates. Their order relative to each other is unknown until step 5
  gives them positions — until then the ranking is **provisional** and must be labelled so.
- **Slot unfilled.** Stop and ask. Both branches above are defensible and they disagree.

### 4. Classify the first diagnostic

Read a window of about 40 lines around the ranked-first error and place it in this table. The left
column describes what the diagnostic is *about*. **No tool prints these words** — they are
paraphrases. Match on meaning, then record your tool's real wording in the Diagnostic wording slot so
the next reader can match on text instead of on judgement.

| What the diagnostic is about | Most likely cause | What proves it |
|---|---|---|
| a module name cannot be resolved to a definition | the source file is absent from the file set | Grep for that module's declaration under the directories the filelist names |
| an include file cannot be opened | include path missing, or ordered behind a stale copy | Glob that header basename under each include path, in order |
| a macro is undefined | the define is never set, or set outside this compilation unit | Grep the macro name across the filelists and the file that failed |
| a name is used as a type but is not one | the package is neither imported nor scope-referenced here, or its file is analysed after this file | compare both positions in the ordered slice from step 5 |
| a port or parameter does not exist on a module | a different copy of that module elaborated | Grep for a second declaration of that module name |
| a module is already defined | the same module reached the build twice | the duplicate check in step 6 |
| an implicit net appears in a file that looks innocent | a preceding file in the same compilation unit changed the default net type and never restored it | inspect the entry immediately before it in the ordered slice |

Record the classification and its one piece of evidence. A classification with no cited line is a
guess, and must be reported as one.

### 5. Resolve the named things — and build an ordered slice only if order is the question

**Resolve first; do not flatten.** Take the file names, module names, header basenames and macro
names from the ranked candidates — a handful of strings, not a tree. Use **Glob** to locate the
entry-point filelist from the slot table, then **Grep** it, and the block filelist, for each of those
strings. Most diagnostics are answered right here: the name is present once, present twice, or
absent. "Absent from the filelists I opened" is the honest claim; "absent from the build" is not one
you can make without having opened them all. Record which you did not open.

**Build the slice only when the fault class is `order`, `shadow` or `duplicate`.** Those three need
the relative position of two entries and nothing else. From the entry point, follow the
nested-inclusion directive down **at most four levels** and open **at most twelve filelist files**,
preferring the branches whose names or paths match the implicated block. Number only the entries you
actually opened, in the order the build would reach them, with four columns: position, originating
filelist and line, the raw entry, and its classification (source file, nested filelist, include path,
define, library search directory, tool switch, comment). Apply the relative-path rule from the slot
table — a nested filelist resolving against its own directory behaves differently from one resolving
against the directory the build started in.

**Label the slice for what it is.** Numbering entries this way is the agent *re-deriving* what the
build tool resolves — nested expansion, relative-path resolution, library search. It is a
reconstruction, not an observation, and it is wrong wherever the reconstruction and the tool
disagree. So:

- If the **Order evidence** slot names a resolved file list or compile-order manifest that the build
  itself writes, read that instead and label the ordering `observed`.
- Otherwise label it `reconstructed`, and state which filelists the slice covers. A position in a
  partial slice orders two entries *relative to each other* and says nothing about entries outside it.

### 6. Audit that one filelist — bounded, and counted

This is the part that never gets done, so give it a budget rather than an ambition. Audit the **one**
filelist step 5 implicated, not the tree. Cap at about forty existence checks per pass; if the
filelist is longer, check the implicated entries plus a contiguous window around them.

- **Stale.** For each source entry you check, **Glob** the path. A miss is a stale entry — unless it
  is a generated source from the slot table, in which case the generation step did not happen.
- **Duplicate path.** The same resolved path twice is harmless noise, but it means a nested filelist
  arrives from two places — which is how the next problem starts.
- **Duplicate module.** **Grep** for a second declaration of each module *named in the diagnostics* —
  those modules only, not every module in the filelist. Two hits in two files is the real hazard;
  report both positions.
- **Shadowed basename.** The same basename under two directories is a shadow candidate. Rank by slice
  position and say which the build would take, using the duplicate policy slot.
- **Stale release root.** Entries under a directory that no longer exists mean an old release path
  survived a version bump; say which release the surviving paths still point at.

**Report every count as `n of m checked`.** A bare `0 stale` is a claim about a file set you did not
traverse, and a reader will hear it as "there are no stale entries".

### 7. Audit the include paths and defines named in the diagnostic

- **Include shadowing.** For each header named in the diagnostics — those headers only — **Glob** its
  basename under each include-path entry, in order. Search is first-match-wins, so the earliest
  directory holding that basename is used, intended or not.
- **Missing defines.** **Grep** for the one macro named in the diagnostic, across the filelists in the
  slice and across the file that failed. Do not sweep the sources for every conditional-compilation
  directive: on an SoC tree that returns far more hits than rule 4 of this skill's own budget allows,
  and it answers a question nobody asked. A macro tested in the failing file and set nowhere in the
  slice is a strong candidate cause — say "nowhere in the slice", not "nowhere".
- **Conflicting defines.** The same macro set twice with different values inside the slice is a real
  finding; report both positions rather than deciding which is right.

### 8. Check package and interface ordering, for the packages in the diagnostic

- Record the slice position of the file declaring each package named in the diagnostic. Then find its
  dependants **two** ways, because one of them is routinely missed: **Grep** for import statements
  naming the package, and **Grep** for the package name immediately followed by the scope-resolution
  operator. A file that writes `my_pkg::some_type` without importing anything is exactly as
  order-dependent as one that imports, and an import-only search reports zero ordering hazards on a
  file set that has them. This is common enough in DV code to be the default assumption, not an edge
  case.
- Any dependant positioned **before** its package in the slice is an ordering hazard — report it even
  if it is not the cause of today's failure.
- **Interfaces and packages depend on each other in both directions, and the direction decides the
  fix.** A package that names an interface type — most often as a virtual interface — needs that
  interface analysed first. An interface that names a type declared in the package needs the package
  first. When both are true the dependency is circular and no ordering works: the fix is not a
  reorder but moving the shared type into a third package both analyse after, or breaking the
  dependency with a parameter or a forward-declared type. Say which of the three cases you observed
  and cite the line in each file that creates the dependency. Do not answer "put the interface first"
  without checking the other direction — that advice breaks the second case.

### 9. Explain a block-versus-top disagreement

When the same source builds at block level and fails at top, the source is rarely the difference.
Compare the two filelists named in the Block-versus-top slot and check these six, in order. Comparing
them is two bounded slices, not two flattens — expand each only far enough to contain the implicated
entry.

1. Different macro definitions — a block filelist setting a stub or simulation-only macro that top
   does not.
2. Different include-path order, so a different copy of the same header wins.
3. Different compilation-unit grouping. Grouping is a property of the flow and its switches, **not**
   of block versus top — a block flow and a top flow can group identically, or differ, independently
   of scope. Read the Compilation-unit grouping slot. If the two flows do group differently, a macro
   or default-net-type setting that reached its consumer at block level may not reach it at top.
4. A second copy of a module arriving at top through a neighbouring IP filelist.
5. A block-level stub replaced by real logic at top, exposing a never-checked port or parameter
   mismatch.
6. A relative-path filelist invoked from a different directory.

### 10. Report

```
signature : <phase>|<kind>|<where>|<what>
first err : <verbatim diagnostic, with file and line>
cause     : <the filelist line or Grep result that explains it, verbatim>
phase     : compile | elab
kind      : tool
class     : design | infrastructure | unknown
fault     : missing-file | missing-incdir | missing-define | order | duplicate | shadow | port-mismatch | syntax
filelist  : <which filelist, which line>
ordering  : observed | reconstructed | not-needed
owner     : <block owner | infra | external IP release>
audit     : <n stale of m entries checked, n duplicate paths, n duplicate modules, n shadowed, n order hazards>
coverage  : <a of b entries audited in that filelist; c of d nested filelists expanded; ranking provisional or confirmed>
run id    : <whatever identifies this build for us>
notes     : <which nested filelists were not expanded and why, plus anything the next person would otherwise rediscover>
next      : <the single named change, and a request to rebuild and send back the first 40 lines>
```

`signature`, `phase` and `kind` follow `_shared/failure-signature-schema.md` — use that file's field
names and normalisation rules rather than restating them here; `phase` is `compile` or `elab` and
`kind` is usually `tool`. `first err`, `cause`, `class`, `run id` and `notes` are the same fields
`dv-sim-log-first-error` uses, so a build break routed from there keeps its vocabulary: `class` is
`infrastructure` for a filelist, include-path or release-path fault, and `design` when the diagnostic
is a genuine error in source under active edit. `fault`, `filelist`, `ordering`, `audit` and
`coverage` are local to this skill.

## Gotchas

- **The first printed error is not the first error — unless the flow prints in analysis order.**
  Check the Build parallelism slot. Under parallel or partitioned compile, output from unrelated
  files interleaves and print order across files proves nothing. Under sequential single-log analysis
  it is exactly the evidence you need, and discarding it throws away your best signal.
- **One unknown type produces twenty diagnostics.** A single missing package import makes every
  declaration using its types fail. The error count says nothing about the problem count.
- **Macros do not cross compilation-unit boundaries.** A macro is visible only inside its compilation
  unit and only from its definition onward. Whether a filelist is one unit or one unit per file is a
  tool-and-switch property, not a block-versus-top property — check the Compilation-unit grouping
  slot. Two flows over the same source can disagree about it, and that is how a file unchanged for a
  year starts reporting an undefined macro.
- **A changed default net type leaks forward.** A file that turns implicit nets off and never
  restores them hands that setting to the next file in the same compilation unit, so the diagnostic
  lands on an innocent file. That is why it survives so long.
- **A missing timescale directive is an ordering bug, not a missing line.** A module without one
  inherits from whatever was analysed before it, so reordering the filelist changes time resolution
  with no source edit at all.
- **Include-path search is first-match-wins.** Two directories holding the same header basename means
  the earlier one silently wins. A stale copy in an older release or a personal work area is the
  classic explanation for "it built yesterday".
- **Library search directories make a missing file look present.** If the flow searches directories
  by module name, a module absent from the filelist can be picked up from an old release with no
  diagnostic at all. Absence of an error is not evidence the intended file was used.
- **A duplicate module definition is not always an error.** Some flows keep the first, some the last,
  some only warn. The symptom is not a build failure — it is a stub elaborating in place of real
  logic, with outputs stuck at constants, or a port that "should exist" reported as missing.
- **A filelist entry missing from disk may be generated.** Check the generated-sources slot before
  calling it stale; removing a generated entry breaks a working flow for everyone.
- **A clean filelist audit does not mean a clean file set.** A class or a block of code pulled in by
  an include directive never appears in any filelist — it arrives inside the file that includes it.
  A filelist audit therefore under-reports by exactly the size of the include graph. If the failing
  name is nowhere in the filelists, Grep for it as an include target inside the files that *are*
  there, before calling it absent.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every claim cites a **slice position or a Grep result**; a bare "file X is missing from the
  filelist" is a guess wearing a fact's clothing.
- every audit count is a fraction of something stated, and the coverage line has denominators.
  `0 stale` with no `of m checked` is not a finding.
- the ranking is labelled `provisional` unless a slice position, or a sequential-print-order slot,
  confirms it.
- `ordering` says `observed` only if a manifest the build itself wrote was read. A reconstruction
  reported as an observation is the most expensive error available here.
- any proposed filelist addition was checked for the file being **already present at a different
  position** — adding it again creates a duplicate-definition hazard that surfaces weeks later.
- nothing generated is reported as stale, and the compile-versus-elaboration verdict matches the
  shape of the diagnostic — an unresolved module reported with no source line is not a syntax problem.

A wrong answer typically explains a cascade diagnostic in fluent detail, or reports an audit with
zero findings on a filelist that is demonstrably failing to build. Zero findings usually means the
nested filelists were never expanded — check the `notes` and `coverage` lines before trusting it.

## Done when

The first diagnostic is classified with cited evidence, the coverage line states what was actually
traversed and what was not, and the engineer has one named change to make and one rebuild to ask for.
