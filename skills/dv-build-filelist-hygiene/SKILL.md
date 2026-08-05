---
name: dv-build-filelist-hygiene
description: Decode a build that fails to compile or elaborate, and audit the filelists behind it for stale, duplicated, missing and shadowed entries. Use when a compile or elaboration error is pasted in, when a module or package cannot be found, when an include file or a define is missing, when a module is reported as already defined, or when a block-level build passes and the top-level build fails on the same source.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Compile and Elaboration Error Decode with Filelist Hygiene
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-02-05
  semiskill-tags: build, filelist, compile, elaboration, includes, defines, packages, triage
---

# Compile and Elaboration Error Decode with Filelist Hygiene

A build that will not compile is the highest-frequency thing a DV engineer pastes into a chat, and
the error text is the least useful part of it. The compiler reports the *consequence* of a missing
file, a missing include path, a missing define or a wrong file order — twenty times over — while the
elaborator reports a module it cannot find without saying which filelist was meant to contain it. The
answer lives in the filelists, which nobody audits because auditing them is tedious, not hard.

The output is three things: **a classified first diagnostic, the filelist evidence for it, and an
audit of what else is wrong in the same filelist.** Not a restatement of the error.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Build log location | [[FILL: where our compile and elaboration logs land, and how long they are kept]] | your mentor |
| Filelist entry point | [[FILL: the filelist the top build actually consumes, and where block filelists live]] | DV infra owner |
| Filelist directives | [[FILL: the directives our filelists use for nested inclusion, include paths, macro defines and library search, and what relative paths resolve against]] | DV infra owner |
| Error markers | [[FILL: the strings our compiler and elaborator print to mark an error, a warning, and a build that finished]] | DV infra owner |
| Duplicate policy | [[FILL: whether our tool errors on a duplicate module definition or silently keeps one, and which one it keeps]] | DV infra owner |
| Generated sources | [[FILL: which files in our filelists are generated, and by which step]] | DV infra owner |
| Block versus top | [[FILL: which filelist a block build uses versus the top build, and which defines differ between them]] | verification lead |
| External filelists | [[FILL: who owns the IP release filelists we consume but do not control]] | verification lead |

**If a slot is unfilled, stop and ask. Do not guess.** An invented filelist path, build command or
directive name sends the engineer to audit a file set that is not the one that failed.

## Retrieval budget — read this before opening anything

Build logs are smaller than simulation logs, but filelists nest, and a top-level file set expands to
several thousand entries. Work in this order and stop as soon as the first diagnostic is explained:

1. **Never open the build log with Read first.** Budget for the log: one **Grep** for error markers,
   one for the marker that ends compilation, then at most three windowed Reads of about 80 lines.
2. Read a filelist whole only if it is under about 300 lines. Above that, **Grep** for the directive
   of interest and Read bounded windows around the hits.
3. Expand nested filelists to a depth of **four** at most, and to **twelve** filelist files in total.
   Record the ones you did not open instead of opening them.
4. Scope every **Glob** and **Grep** to one directory from the flat list; a recursive search from the
   repository root returns tens of thousands of paths. Above about 200 hits, narrow before reading.
5. **Stopping rule.** Stop when the first diagnostic is classified with a cited filelist line and the
   audit table is filled. A second unexplained diagnostic is a second pass, not more reading.

## Procedure

### 1. Separate a compile failure from an elaboration failure

Use **Grep** for the error markers from the slot table, then decide which side broke — the two have
different causes and often different owners. Also **Grep** for the marker that ends compilation; if
it is absent the build never reached elaboration and every elaboration-shaped theory is wrong.

- **Compile (analysis)** diagnostics cite a source file and a line number in a file being analysed.
  They are about text — syntax, unknown macros, unknown types, unreadable includes.
- **Elaboration** diagnostics cite a module name, an instance path or a hierarchical name, often with
  no source line at all. They are about binding — which module, which parameter, which port.

### 2. Order the diagnostics by dependency, not by print order

Most flows compile files in parallel, so **print order is not source order and is not filelist
order**. Collect the file and line of each error with **Grep**, then rank: group by file, take the
lowest line number within each file, and across files take the one appearing **earliest in the
flattened filelist** from step 4. That file, at that line, is the one to explain.

### 3. Classify the first diagnostic

Read a window of about 40 lines around the ranked-first error and place it in this table.

| What the diagnostic says | Most likely cause | What proves it |
|---|---|---|
| cannot find module, unresolved instance | the source file is absent from the flat list | Grep the module declaration across the flat list directories |
| cannot open include file | include path missing, or ordered behind a stale copy | Glob that header basename under each include path in order |
| undefined macro | the define is never set, or set in a file that is not in this compilation unit | Grep the macro name across the sources and the filelists |
| unknown type, or a name is not a type | the package is not imported here, or its file sits **after** this file | compare both positions in the flat list |
| port or parameter not found on a module | a different copy of that module elaborated | Grep for duplicate module declarations |
| module already defined | the same module reached the build twice | the duplicate check in step 5 |
| implicit net declaration in a file that looks innocent | a preceding file changed the default net type and never restored it | inspect the entry immediately before it in the flat list |

Record the classification and its one piece of evidence. A classification with no cited line is a
guess, and must be reported as one.

### 4. Flatten the filelist

Use **Glob** to locate the entry-point filelist named in the slot table. **Read** it, then **Grep**
it for the nested-inclusion directive recorded in the slots. If that slot is unfilled, stop and ask —
expanding the wrong directive audits the wrong file set entirely.

Produce a numbered **flat list** in the order the build would see it, with four columns: position,
originating filelist and line, the raw entry, and its classification (source file, nested filelist,
include path, define, library search directory, tool switch, comment). Apply the relative-path rule
from the slot table — a nested filelist resolving against its own directory behaves differently from
one resolving against the directory the build started in.

### 5. Audit the flat list for stale, duplicated and shadowed entries

This is the part that never gets done. Work through the flat list mechanically.

- **Stale.** For each source entry, **Glob** the path. A miss is a stale entry — unless it is a
  generated source from the slot table, in which case the generation step did not happen.
- **Duplicate path.** The same resolved path twice is usually harmless noise, but it means a nested
  filelist is being pulled in from two places, which is how the next problem arises.
- **Duplicate module.** For each module named in the failing diagnostics, **Grep** for its
  declaration across the flat-list directories. Two hits in two files is the real hazard; report both
  paths and both flat-list positions.
- **Shadowed basename.** The same basename under two directories is a shadow candidate. Rank by
  flat-list position and say which the build would take, using the duplicate policy slot.
- **Stale release root.** Entries under a directory that no longer exists mean an old release path
  survived a version bump; say which release the surviving paths still point at.

### 6. Audit include paths and defines

- **Include shadowing.** For every include-path entry, in order, **Glob** the basename of each header
  named in the diagnostics. Include-path search is first-match-wins, so the earliest directory
  holding that basename is used, whether or not it is the one intended.
- **Missing defines.** **Grep** the sources for conditional-compilation directives and collect the
  macro names they test. Compare against the macros set in the filelists. A macro tested but never
  set anywhere is a strong candidate cause.
- **Conflicting defines.** The same macro set twice with different values is a real finding; report
  both flat-list positions rather than deciding which is right.

### 7. Check package and interface ordering

Ordering matters even in flows where module instantiation is order-independent.

- **Grep** for package declarations and record each package file's flat-list position, then **Grep**
  for import statements and record the position of every file importing each package.
- Any importer positioned **before** its package is an ordering hazard — report it even if it is not
  the cause of today's failure.
- An interface whose type is referenced inside a package must be analysed **before** that package.
  People have this backwards more often than not, and its symptom is an unknown type inside a package
  rather than anything that mentions the interface.

### 8. Explain a block-versus-top disagreement

When the same source builds at block level and fails at top, the source is rarely the difference.
Compare the two flat lists and check these six, in order:

1. Different macro definitions — a block filelist setting a stub or simulation-only macro that top does not.
2. Different include-path order, so a different copy of the same header wins.
3. Different grouping into compilation units, so a macro or net-type setting that leaked usefully at block level no longer reaches its consumer.
4. A second copy of a module arriving at top through a neighbouring IP filelist.
5. A block-level stub replaced by real logic at top, exposing a never-checked port or parameter mismatch.
6. A relative-path filelist invoked from a different directory.

### 9. Report

```
verdict    : compile | elaborate | filelist
first diag : <verbatim diagnostic, with file and line>
class      : missing-file | missing-incdir | missing-define | order | duplicate | shadow | port-mismatch | syntax
evidence   : <the flat-list position or Grep result that proves it>
filelist   : <which filelist, which line>
owner      : <block owner | infra | external IP release>
audit      : <n stale, n duplicate paths, n duplicate modules, n shadowed, n order hazards>
unopened   : <nested filelists not expanded, and why>
next       : <ask the engineer to rebuild after the single named change and paste the first 40 lines back>
```

If this failure must be handed on or matched against an existing one, derive the signature using
`_shared/failure-signature-schema.md` — `phase` is `compile` or `elab`, `kind` is usually `tool`.

## Gotchas

- **The first printed error is not the first error.** Parallel compile interleaves output from
  unrelated files. Rank by file, then line, then flat-list position before believing anything.
- **One unknown type produces twenty diagnostics.** A single missing package import makes every
  declaration using its types fail. The error count says nothing about the problem count.
- **Macros do not cross file boundaries reliably.** A macro is visible only within its compilation
  unit and only from its definition onward. A block build analysing everything as one unit hides
  this; a top build analysing per-file exposes it as an undefined macro in a file unchanged for a
  year. Guarded headers that each consumer includes are the durable answer.
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

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every claim cites a **flat-list position or a Grep result**. "File X is missing from the filelist"
  with nothing behind it is a guess wearing a fact's clothing.
- the named first diagnostic is the earliest by dependency, not the last printed nor the most
  alarmingly worded.
- any proposed filelist addition was checked for the file being **already present at a different
  position** — adding it again creates a duplicate-definition hazard that surfaces weeks later.
- nothing generated is reported as stale, and the compile-versus-elaboration verdict matches the
  shape of the diagnostic — a module-not-found with no source line is not a syntax problem.

A wrong answer typically explains a cascade diagnostic in fluent detail, or reports an audit with
zero findings on a filelist that is demonstrably failing to build. Zero findings usually means the
nested filelists were never expanded — check the unopened list before trusting it.

## Done when

The first diagnostic is classified with cited evidence, and the engineer has one named change to make
and one rebuild to ask for.
