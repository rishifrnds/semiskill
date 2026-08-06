---
name: dv-tool-bug-testcase-extraction
description: Confirm a customer-filed tool bug is a real product defect rather than user error or documented behaviour, then carve a self-contained, IP-clean testcase out of their tree that still shows the same failure signature. Use when a customer sends a tarball and says our tool is broken, when R&D refuses a case because the reproducer needs the customer's whole environment, when you must decide whether any of their material may be kept at all, or when a reduction stopped failing and nobody noticed.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Customer Tool-Bug Reproduction and Self-Contained Testcase Extraction
  semiskill-function: design-verification
  semiskill-role: eda-product-validation-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.2.1
  semiskill-review-by: 2027-06-25
  semiskill-tags: customer, tool-defect, testcase-extraction, reduction, ip-clean, reproduction, handoff
---

# Customer Tool-Bug Reproduction and Self-Contained Testcase Extraction

A customer tool bug arrives as a directory tree, a log, and a sentence. The tree is theirs, the log
came out of a release we may no longer ship, and the sentence is a conclusion rather than an
observation. Two expensive things then happen in sequence: weeks go into reducing something the
release notes already answer, and what finally reaches R&D still contains files we were never
entitled to keep.

The output is **a confirmation with the evidence behind it and, only when that lands on a defect, an
extraction plan, an IP inventory and a packaged testcase our own suite can hold**. Not a forwarded
tarball.

**What this does not do.** It reads files on disk — Read, Grep and Glob, nothing else. It cannot
compile, elaborate, start our tool or compare two runs, so every "does it still fail" question is a
handoff to the engineer who can. **It also cannot write, edit, move or delete a single file**, which
matters most in steps 6 to 8: every option removed, every stub, every substitution and the packaged
tree itself are *proposals* that a named person makes. And it does not decide what we are
contractually permitted to keep — it classifies each file, and a named person rules.

## When to use something else

- Nobody has established whose fault this is yet, or the claim is that our VIP is broken —
  `dv-customer-escalation-isolation` settles the fault domain first. Come here once that lands on
  `domain: our-tool`.
- The defect record itself, with the full version matrix, duplicate search and documentation
  citation — `dv-customer-defect-handoff`. That skill owns the record; this one owns the testcase
  that goes inside it, and step 3 here is deliberately the short form of its steps 4 to 7.
- The shrink loop — establish determinism, cut one axis, re-check, revert — is
  `dv-minimal-reproducer`. Step 6 does not restate it; it supplies only the cuts that exist in a
  customer tree and hands the loop straight back.
- The complaint is that a new build behaves differently from the old one —
  `dv-tool-release-behaviour-diff` classifies that before anything is carved.
- Masking host names, paths and account names out of something you are about to send —
  `dv-artifact-redaction-egress`. A different question: that one decides what must be hidden inside
  an artifact, this one decides which files may exist at all.
- Their build never compiled or elaborated — `dv-build-filelist-hygiene`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Case tree | [[FILL: where a customer's submitted tree is unpacked on our side, and how that area is kept separate from anything we author]] | support lead |
| Release stamp | [[FILL: how our tool writes its own release and patch level into its output, and which line of a log carries it]] | release owner |
| Diagnostic identity | [[FILL: how our tool spells a diagnostic identifier in its output, and whether that identifier can be looked up in a file or only by a person]] | R and D contact |
| Documented behaviour | [[FILL: which of our user guide, release notes and known-limitations list exist as files that can be read, and where they live]] | documentation owner |
| Retention rule | [[FILL: what the customer agreement lets us keep, substitute or must destroy; how long we may hold any of it; which header or marker words decide a file's ownership for us; and who rules on a disputed one]] | contracts owner |
| Substitution library | [[FILL: where our own stand-in models, bus stubs and memory models live, so restricted content can be replaced rather than deleted]] | DV infra owner |
| Suite conventions | [[FILL: the directory shape, entry filelist and naming a testcase must have to enter our own regression suite]] | validation lead |
| Case record | [[FILL: what a customer-originated defect record requires on top of an internal bug, and our rule for referring to the case without naming the customer]] | support lead |

Two pack-wide facts are spent here and are read from `_shared/team-profile.md` rather than re-asked:
**Known-issue list**, in step 3, and **Filelist convention**, in steps 5 and 8. Four more sit close
to rows above and are **different facts** — do not fill one from the other.

- **Diagnostic identity is not the profile's Fatal markers.** Fatal markers are what our own
  regression flow prints when a run failed. A diagnostic identifier is the code our *product*
  attaches to a message, and a message carrying one is very often informational.
- **Case record is the profile's Bug convention plus the customer-facing additions**, not a
  replacement for it. Fill the profile row first and record only what is extra here.
- The profile's **Log location** is where *our* runs land. A customer log lands wherever support
  unpacked it, which is the Case tree slot.
- The profile's **Pass marker** has no counterpart on their side at all. Their flow prints its own
  end-of-run line and this pack cannot know it, so never read the absence of ours as a failure.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented release name, header
word or retention limit is worse than a blank one: the first two get quoted back to the customer and
the third gets a file kept that should have been destroyed.

## Retrieval budget — read this before opening anything

A submitted case is a whole tree plus a log larger than everything else you will read this month.

1. **Grep, Read and Glob work on files on disk.** A tarball described in a mail thread cannot be
   searched. Get the unpacked path under **Case tree** first. Until one exists you may reason over
   the pasted lines by eye, but what you have is *reported*, never *observed*, and every field
   resting on it is provisional.
2. **Their design source is the one thing to open least.** It is what we are least entitled to read
   and what an agent is most tempted to browse. Exactly **one** 60-line **Read** window is available
   into it, entered at the file and line the step 3 diagnostic names, and opening it goes on the
   coverage line. Anything more is a question for a person, not a larger budget.
3. The fixed pool, covering steps 1 to 5, is **three Globs, six Greps and four windowed Reads**:
   - **Glob** — the case tree's top two levels (step 1); its filelists and invocation scripts
     (step 5); its source files by extension, for the inventory (step 5).
   - **Grep** — the release stamp in their log (step 2); the diagnostic identifier in their log
     (step 3); that identifier and its message text across the **Documented behaviour** set
     (step 3); the ownership header words from **Retention rule** across the tree (step 5); the
     profile's **Known-issue list**, only when it is a file on disk (step 3), so five when it is
     not; and **one spare**, held for the single re-narrowing rule 6 allows.
   - **Read** — about 60 lines of their invocation script (step 2); about 80 lines of their log at
     the first diagnostic (step 3); about 60 lines of the entry filelist (step 5); and rule 2's
     single 60-line window into their source (step 4).
4. **Steps 6, 7 and 8 sit outside that pool, and only they do — a per-rebuild allowance.** Every cut
   a person makes produces a *new* log, and a fixed pool cannot cover a loop whose length nobody
   knows in advance. Per rebuilt tree the allowance is **one Grep** of the new log for the step 3
   diagnostic identifier, and **at most one 80-line Read** window at its first hit: enough to derive
   the four signature fields and nothing more. Step 8's clean-area build gets that same one Grep and
   one window once more. Their design source is not reopened by any of it — rule 2's single window
   is spent in step 4 and does not renew per cut.
5. **Per-cut stopping rule.** If that one Grep and that one window do not settle whether all four
   signature fields survived, record the cut as unverified, say what is missing, and stop there. Do
   not open a third file, and never carry an unverified cut forward as accepted.
6. **Two hundred hits is a ceiling on a *search*, not on the inventory.** A Grep looking for one
   thing — the release stamp, the diagnostic identifier, that identifier across the documentation
   set — is too broad above about 200 hits: anchor it on the identifier or on one directory and run
   it once more. That second run is what the pool's spare Grep is for, and there is no second spare.
   Step 5's ownership sweep is the exception and is judged the other way round. It is an inventory,
   not a search: one hit per file that carries a header is the intended result, so its count scales
   with the tree and a large count is the sweep working, not a pattern to narrow. What matters there
   is what it does **not** return — every path it misses stays unclassified, and that number goes on
   the coverage line. If it comes back carrying the same header on their files and ours alike, so
   that it separates no class from another, it has classified nothing: say so, leave
   `ip status: not-yet-cleared`, and take the tree to the **Retention rule** slot's ruling owner as
   one directory-level question rather than spending the spare hunting a sharper word.
7. **Stopping rule for the gate.** If step 3 is unsettled once its Greps and its window are spent,
   stop with the disposition empty, name the one artifact still missing, and do **not** start
   carving. Reduction is the expensive half of this procedure and must never begin on an unconfirmed
   defect — that is what protects the per-rebuild allowance from being spent on nothing.
8. State what you covered — how many of the tree's files the inventory actually classified, which of
   their files were opened, and which figures in the record were reported to you rather than read by
   you. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Inventory what actually arrived, before opening any of it

One **Glob** of the **Case tree** path, top two levels only. Then write two lists side by side: what
the case says was sent, and what is on disk. They differ more often than not, and that difference is
your first message back — cheap now, expensive after two days of analysis.

Three things decide whether extraction is possible at all: their log, the exact invocation, and the
source that invocation names. A tree with no invocation is a tree nobody can rebuild; ask for the
script by path rather than asking how they ran it.

Keep the mail thread and the tree apart from here on. The thread is a claim; the files are evidence.
Apply the **Case record** slot's naming rule from your first note onward — the case is referred to by
our own key, never by the customer, and no site path or host name is copied into any note.

### 2. Pin the release that produced the log, and the invocation behind it

Version skew closes more of these than analysis does, and it is cheap to settle first. **Grep** their
log for the **Release stamp** slot's line and quote it verbatim. If there is no stamp the release is
`?`. Do not infer it from an install path, a directory name or the mail thread — a site wrapper
loading a build nobody meant to load is a common finding, and inference is exactly what hides it.

Then **Read** about 60 lines of their invocation script. What you want is the option set actually
used, not the one described in the thread: options that change semantics are usually set two or three
levels down in a wrapper the customer has forgotten they have.

The profile's **Simulator** row names the tool *our own* runs use. It is not the release under test
here, and treating it as one gets the case reproduced against the wrong build.

Handoff: when the stamp is missing, **ask the support lead — the role the Case tree and Case record
slots both name as the one to ask — to confirm with the customer which release produced the attached
log**. The agent cannot start our tool and must not invent what it would have printed.

### 3. Confirm the defect before carving anything

This is the gate, and it exists because reduction is expensive. `dv-customer-defect-handoff` owns the
full version matrix, duplicate search and citation; what follows is the short form that decides only
whether carving starts. Where a row below is not clear-cut, hand the case to that skill rather than
arguing it here.

Three searches, in this order: one **Grep** of their log for the **Diagnostic identity** shape, to
get the identifier and the line number of its first occurrence, then the log's single 80-line
**Read** window starting about 60 lines earlier; one **Grep** of the **Documented behaviour** set for
that identifier and for the distinctive fragment of the message; and one **Grep** of the profile's
**Known-issue list** when it is a file on disk. When that list is a tracker, ask whoever can query it
to compare and record the answer as pending — never call the failure new because you could not reach
the list.

| What the evidence shows | Where it lands | What happens next |
|---|---|---|
| The message is a known limitation of this release | `disposition: documented-limitation` | no carving; the deliverable is an explanation |
| A later release's fixed-issue entry matches | `disposition: fixed-in-later-release` | no carving; name the release |
| An option in the step 2 invocation selects exactly this behaviour | leave the disposition empty; this skill opens no record | back to `dv-customer-escalation-isolation`, carrying step 2's quoted option line |
| Our documentation is silent on the behaviour | `disposition: enhancement` | to whoever owns product scope |
| Two clauses of our documentation disagree | `disposition: doc-gap` | quote both readings; the ambiguity is the finding |
| The known-issue list already carries this identifier and this `where` | attach to that entry | no new record, no carving |
| Our tool raised an internal error, an assertion in its own source, or exited with no diagnostic | `disposition: defect` | carve — see the Gotchas |
| Our tool produced a result contradicting a clause we can cite | `disposition: defect` | carve |
| Nothing on disk settles it | leave the disposition empty | name the one artifact needed, and stop |

Carving starts only on `disposition: defect`. The five rows that name a disposition still produce a
record, handed to `dv-customer-defect-handoff`, but nothing is reduced and nothing of theirs is kept.

Two rows leave the disposition empty and they are **not** the same state. The option row is settled
and not ours — the fault domain moves, and this skill closes. The last row is unsettled — nothing has
moved yet and the case is waiting on one artifact. The third column is the only thing that tells them
apart, so never record an empty disposition without it. Where the evidence cannot even say which side
of the line the fault sits on, that is `class: unknown` in step 9, not a guess at `design`.

### 4. Fix the signature the extraction has to preserve

Derive a failure signature from their log following `_shared/failure-signature-schema.md` — same
field order, same normalisation rules. For these cases `kind` is usually `tool`, and the phase is
whichever of the five the failing step actually reached. Two of the five are routinely mis-assigned
on a tool bug, and they route to different R and D components:

- **`phase: finalise`** — our tool was still up and failed on the way down: end-of-run reporting,
  closing and writing the coverage database, flushing or closing the waveform file.
- **`phase: post`** — our tool had already exited and a *separate* one of ours failed on its outputs:
  merging coverage, generating a report, opening the database in the debug environment. That step
  usually diagnoses itself into a file of its own rather than the log step 3 read, so ask for that
  path instead of inferring the phase from where their log happens to stop.

Where the diagnostic names a file and a line in their source, spend rule 2's single 60-line **Read**
window there so that `where` is specific rather than a file name, and record on the coverage line
that you opened it.

This signature is the acceptance test for every cut that follows, and it is stricter than it sounds.
**"It still fails" is not the test.** A cut that leaves the same message firing on a different
construct has changed `where`, and `where` is what routes the case to an R&D component; a reduced
testcase failing for a second reason costs the wrong team a week. Normalise properly, too — a
signature still carrying their absolute paths, host name or seed matches nothing anywhere.

### 5. Classify every file before touching one

Two **Globs** — their filelists and invocation scripts, then their source by extension — and one
**Grep** across the tree for the ownership header words the **Retention rule** slot names. Then
**Read** about 60 lines of the entry filelist. Classify every path into exactly one class:

| Class | What it is | What may survive into what we keep |
|---|---|---|
| theirs | their RTL, testbench, configuration, stimulus | nothing |
| third-party | a vendor's VIP, IP core or memory model | nothing, and substituting it changes the case — step 7 |
| ours | our own product content they licensed | keep, at the version we shipped |
| public | the language standard's own packages, freely redistributable models | keep |
| generated | produced by a tool from one of the above | regenerate, never copy |

The **Retention rule** slot also says who rules on a disputed file and how long we may hold anything
at all. Classification is the agent's work; the ruling is not. Any path you cannot classify from a
header, a directory or a filelist entry is unclassified — and an unclassified file is not a clean one.

While the filelist window is open, record how each entry's relative path resolves. The profile's
**Filelist convention** describes how *ours* resolve; theirs follows their own convention, and step 8
moves files, which changes what every relative path means.

### 6. Propose the cuts, one axis at a time — a person makes them

The loop belongs to `dv-minimal-reproducer` — determinism first, one change at a time, re-check after
every change, revert on any signature move. Use it as written, **including its shape**: propose
exactly one change, then ask the engineer to make that one change and give you the path of the
resulting log. What follows is only the order that is specific to a customer tree, cheapest and least
disturbing first.

1. **Time and stimulus.** Propose stopping the run just after the failure point. A compile or
   elaboration defect has nothing on this axis at all — the run never started — so for those, start
   at 2. Do **not** skip 2 as well: optimisation, incremental-compile and debug settings are
   compile-time options, and the Gotchas below say that is exactly where this defect class hides.
2. **Options.** Propose removing one option at a time from the step 2 set. Every option that can go
   is one fewer thing R and D has to consider, and an option whose removal makes the failure vanish
   is itself the finding; record it rather than dropping it quietly.
3. **Hierarchy.** Propose replacing blocks the failure never reaches with stubs carrying the same
   port list — see step 7 for what "same" has to mean, and for who writes the stub.
4. **Restricted content**, taking the classes from step 5 in the order theirs, then third-party.
   Prefer a substitution to a deletion wherever the shape carries the bug — step 7 again.
5. **Source text.** Propose deleting unreferenced declarations first, then shrinking what survives.

**The agent proposes; a person cuts.** This skill holds Read, Grep and Glob, so it cannot delete an
option from a script, write a stub, replace a file or shrink a line of source. Each item above is
therefore a proposal naming four things: the axis, the file by path, exactly what comes out, and the
signature you expect to survive it. Then, for that single change:

Handoff: **ask the engineer to make that one cut, rebuild the reduced tree, and give you the path of
the resulting log.** Spend the per-rebuild allowance from budget rule 4 on that log — one **Grep**
for the diagnostic identifier, one 80-line **Read** window — and compare the four signature fields
against step 4's yourself. A cut nobody made is not a cut; a cut nobody rebuilt is a cut nobody
verified. Both go into the record as unverified, never as accepted.

The last cut before the failure disappears is very often the trigger rather than noise. Write it
down; reverting it and moving on discards the most informative thing the whole reduction produced.

### 7. Substitute rather than delete wherever the shape carries the bug

When step 5 says a file cannot be kept but the failure needs something in its place, name the
stand-in from the **Substitution library** slot — by path, in the proposal — and state what it has to
match: the *shape*, not the contents. Tool defects are shape-dependent far more often than
content-dependent:

- port widths and parameter values — an elaboration defect that fires at exactly one width vanishes
  the moment a stub rounds it to something tidy
- generate structure and array dimensions, including the degenerate ones nobody writes on purpose
- hierarchy depth and identifier length, both of which have been triggers and both of which helpful
  renaming destroys
- the same language constructs — swapping an interface for a module, or a parameterised class for a
  concrete one, produces a different testcase wearing the same name

If a parameter *value* is itself restricted, say so and ask which is restricted, the file or the
number. Those are different answers and people conflate them, and a stub that quietly rounds the
number changes the case in a way nobody can detect afterwards.

Putting the stand-in into the tree is step 6's handoff again, not something the agent does:
**ask the engineer to swap in the named stand-in, rebuild, and give you the path of the resulting
log**, then spend one per-rebuild allowance on it. A substitution is a cut like any other and is
verified like one — it is the cut most likely to make the failure quietly disappear.

Record every substitution in the record's `substituted` field. A testcase silently carrying our own
model where the customer had a vendor's tells R and D their design does something it does not.

### 8. Package it so our own suite can hold it

The **Suite conventions** slot gives the directory shape, the entry filelist and the naming. A
testcase our suite cannot pick up is not a testcase; it is a directory somebody deletes next quarter.

Moving files breaks relative paths. The profile's **Filelist convention** says how ours resolve and
step 5 recorded how theirs did — re-anchor every entry, and treat any path still pointing outside the
carved tree as a failure of the extraction rather than a detail to fix later.

Ship four things with it or it comes back: the invocation, the release from step 2 that it fails on,
the expected-versus-observed statement, and the signature it must produce. Take the expected side
from the clause step 3 found; if there was none, leave it empty and say so, because an expectation
with no source behind it is an opinion.

The packaging itself — creating the directory, writing the entry filelist, moving the surviving files
— is a person's work for the same reason every cut was. Describe the target shape; never narrate it
as done. Handoff: **ask the engineer to assemble and build the packaged testcase in a clean area that
has never held the customer's tree, and to give you the log path.** Then spend the last per-rebuild
allowance from budget rule 4 on that log and confirm step 4's signature came back, field by field. A
testcase that works only in the directory it was carved in is the commonest way a case comes back
marked not-reproducible.

### 9. Write the record

`signature`, `phase`, `class`, `run id`, `log` and `notes` are the field names
`dv-customer-defect-handoff` and `dv-sim-log-first-error` already use, so the three records read side
by side and a case moves between them without translation. `disposition` carries exactly the token
set `dv-customer-defect-handoff` spells `defect kind` — same five values, so a row crosses by
relabelling and nothing else; do not add a sixth value on one side only. The rest are local here.

```
case key    : <our internal case identifier, never the customer's name>
disposition : defect | documented-limitation | fixed-in-later-release | doc-gap | enhancement
signature   : <phase>|<kind>|<where>|<what>, per the shared schema
phase       : compile | elab | run | finalise | post
class       : design | infrastructure | unknown
release     : <the release and patch stamp their log carries, verbatim, or ?>
testcase    : <path of the carved tree, its entry filelist, and the invocation>
reduction   : <cuts accepted in order, each with the signature that survived it; then any cut
               proposed but not yet made or not yet rebuilt, marked unverified>
ip status   : cleared | not-yet-cleared
substituted : <every file replaced, and what replaced it>
residual    : <anything of theirs still in the tree, and who holds the ruling>
owner       : <the R and D component this routes to, or blank plus candidates>
run id      : <what identifies their failing run, in their own terms>
log         : <path, and the line range worth reading>
coverage    : <files classified of files found; cuts a person actually rebuilt; which figures were
               reported to you rather than read>
notes       : <what we may keep and until when, plus anything R and D would otherwise rediscover>
```

`class` answers the same question here as everywhere else in the pack — whether the fault sits in the
thing under test or in the environment around it. Our own product is the thing under test, so a fault
in it is `class: design`, while a licence, install or platform failure at their site is
`class: infrastructure` and never reaches R and D as a defect at all. Assign `class: unknown` in
exactly two situations, and assign it rather than guessing: while step 3's disposition is still empty
under the gate's stopping rule, and whenever the same evidence fits both sides — a feature that fails
to start where our release notes say we ship it is our packaging or their install, and their log
alone does not separate the two. A case arriving labelled "your tool is broken" is not evidence for
`class: design`; that label is the claim under test.

`ip status` is `cleared` only when every file in the step 5 inventory has both a class and a ruling;
one unclassified path makes the whole tree `ip status: not-yet-cleared`. There is deliberately no
third value — it answers whether clearance is *complete*, not how the tree got clean. A tree cleaned
by step 7 stand-ins is `cleared` once each stand-in has a class and a ruling of its own, and that it
was substituted rather than deleted lives in `substituted` and `residual`, which is where a reader
looks for it. Leave a field empty rather than filling it plausibly.

## Gotchas

- **An internal error is a defect whatever the input looked like.** A product must diagnose malformed
  input with a message and a location; an assertion inside our own source, a crash, or a silent exit
  is a defect on its own terms. Do not spend two days proving the input was legal first — that is a
  separate question and a later one.
- **"It works in the other simulator" is a disagreement, not evidence.** The language standard leaves
  real latitude — evaluation order inside a time step, parts of elaboration-time resolution, the
  values a random stream yields — and two conforming tools legitimately differ there. Find the clause
  first, and cite it from the copy the **Documented behaviour** slot points at rather than from
  memory of what the manual says somewhere.
- **A stub with an empty body is not a stub with the same port list.** Elaboration and binding
  defects are width-, parameter- and structure-dependent; replacing a block with an empty file
  changes elaboration wholesale, and the failure then disappears for a reason unrelated to the bug.
- **Third-party content is ordinary text with a header, and reduction strips comments.** Once the
  header is gone nobody can tell whose file it was, and the only safe assumption then costs you the
  file. Classify in step 5, never after the first cut.
- **Protected or encrypted source can be neither reduced nor usually read.** If the failing construct
  sits inside a protected region the testcase cannot be made self-contained without its owner's
  plaintext. Say so at step 5: this is the commonest reason an extraction stalls at nine tenths done,
  and it is a conversation with a third party, not a harder cut.
- **The options are part of the testcase.** A defect that fires only under a particular optimisation,
  incremental-compile or debug setting is not reproducible from source alone, and that setting is
  usually in a wrapper script the customer did not send. Read the script, not the mail.
- **Incremental and cached builds both mask and manufacture defects.** A failure appearing only in
  their incremental flow is still a defect — in the incremental path — but the packaged testcase has
  to say which, or R and D builds it clean and closes it as not-reproducible.
- **A wrong-result claim needs three things, not two**: what the tool produced, what they expected,
  and where that expectation comes from. With two of the three it is an opinion, and R and D will
  say so after a week.
- **Never retype the customer's output into the record.** Mail threads re-wrap and people re-type; a
  diagnostic identifier with one character changed matches nothing when R and D searches for it.
  Quote from the file, with its path and line number.
- **A carved tree that only builds where it was carved is not self-contained.** Environment variables
  set by their site wrapper, include paths still pointing back at their tree, and a filelist entry
  that resolves against the invocation directory all survive reduction invisibly. The clean-area
  build in step 8 exists to catch exactly that.

## Human verification — what a wrong answer looks like

Before the testcase leaves your hands, check:

- the record lands on **one** row of the step 3 table — either a named disposition, or an empty one
  with that row's route written down beside it — and carving happened only under `disposition: defect`
- the signature in the record is step 4's, and it is what the final reduced tree actually produced —
  not merely a failure of the same kind
- every cut in the `reduction` line was made **and** rebuilt by a person and carries the signature
  that survived it; anything the agent only proposed is marked unverified, not accepted
- every path the step 5 inventory found carries a class, and `ip status` is not `cleared` while one
  does not
- every substitution is listed with what replaced what, and no substitution silently changed a width,
  a parameter value or a hierarchy depth
- `release` came from the stamp in their log and is `?` if there was no stamp
- no customer name, host name or site path survives in the carved tree, in its file names, or in the
  record
- the coverage line says how many cuts a person actually rebuilt, and which figures were reported to
  you rather than read

A wrong answer typically reduces until the failure changes and then reports the new one; ships a tree
that still needs three files from the customer's environment; declares a defect because another tool
disagrees; or marks a tree clean because nothing in it happened to look proprietary. The subtlest one
reads as a finished extraction that nobody performed: cuts written up in the past tense, a `reduction`
line with no rebuilt log behind any entry, and a signature copied down from step 4 rather than found
again in a log a person produced.

## Done when

R and D can build the carved tree in a clean area, on the release named in the record, get step 4's
signature back, and nothing in it belongs to the customer.
