---
name: dv-trap-exception-triage
description: Triage an unexpected trap in a processor test from saved logs and an architectural-state dump — decode the cause, the faulting program counter, the trap value and the privilege mode, check delegation and vectoring where the core has them, and classify the failure as RTL, as test or handler, or as environment setup. Use when a core test ends in an unexpected exception, when the run spins forever in the trap handler, when an interrupt is taken in the wrong mode or at the wrong vector entry, or when a trap fires on an instruction the test expected to complete.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Unexpected Trap and Interrupt Triage from Architectural State
  semiskill-function: design-verification
  semiskill-role: processor-ip-dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-03-12
  semiskill-tags: traps, exceptions, interrupts, privilege, csr, processor, triage, debug
---

# Unexpected Trap and Interrupt Triage from Architectural State

A processor test that dies in a trap has already told you almost everything: the cause register, the
exception program counter, the trap value and the mode it was taken to are four numbers that between
them name the failure. The expense is that two of the four mean different things depending on whether
the trap was an interrupt or an exception, and that once a handler has looped three thousand times
the numbers still in the registers describe iteration three thousand rather than the one that
mattered. This procedure recovers the **first** trap's state, checks it against what the architecture
actually requires, and ends in a classification with exactly one owner — the RTL, the test and its
handler, or the environment.

## When to use something else

For any failing simulation log, `dv-sim-log-first-error` comes first: it finds the true first error
and produces the signature this skill's report reuses. Come here once that first error is a trap. A
night of failures to sort belongs to `dv-regression-triage-routing`; shrinking a trap you have
already signed belongs to `dv-minimal-reproducer`; a build that never simulated belongs to
`dv-build-filelist-hygiene`; not knowing where the handler or the disassembly live belongs to
`dv-repo-orientation`.

`dv-ral-bringup` is the near neighbour and the boundary is worth stating. A control-register access
that **traps** is here — the trap is the failure. A register accessed successfully that reads back
the wrong value through a UVM register model is there. A test writing a control register the current
privilege mode does not permit gets an illegal-instruction trap, and that is this skill.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Architecture and revision | [[FILL: which architecture and revision this core implements, which privilege modes are actually built, whether its trap mechanism has the shape step 3 describes, and where our copy of the specification lives — and whether that copy is plain text on disk or a document only a person can read]] | core architect |
| Cause decode table | [[FILL: where the cause-code to name mapping for this core lives, including custom or reserved codes we define, and whether it is a file that can be read]] | core architect |
| Trap markers | [[FILL: the strings our testbench or tracer prints when a trap is taken, and the labels it puts on the cause, exception PC, trap value and mode fields]] | DV lead |
| State dump | [[FILL: whether we dump the control registers at a trap or at end of run, where that file lands, and its format]] | DV infra |
| Disassembly | [[FILL: where the built test's disassembly listing and symbol map land, and whether their addresses are link addresses or load addresses]] | build owner |
| Handler source | [[FILL: which file holds the trap handler and startup code our tests link against, and whether one test may replace it]] | test owner |
| Memory map | [[FILL: where the address map for this configuration is written down — which regions exist, and which are readable, writable or executable]] | environment owner |
| Expected-trap convention | [[FILL: how one of our tests declares that a trap is deliberate, and where that declaration lives]] | test owner |
| Reference model | [[FILL: whether we run a reference model in lockstep, where its log lands, and how it reports an architectural-state mismatch]] | DV infra |

Log location, Run identity and the known-issue list are pack-wide facts and live in
`_shared/team-profile.md` — read them there rather than asking again. **Trap markers is narrower than
the profile's Fatal markers**: it is whatever the tracer prints when a trap is *taken*, which on many
flows is an informational line no failure marker matches, on a run that also ends with an ordinary
error. If the two really are the same string here, say so; do not assume it.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented cause name or vector
layout produces a confidently wrong owner, and a designer sent a bug against correct RTL spends a day
disproving it and reads the next report more slowly.

## Retrieval budget — read this before opening anything

1. **Grep and Read work on files on disk.** If the trap state arrived pasted into the conversation,
   ask for the path under the profile's Log location. Until a path exists you may reason over the
   pasted lines by eye — but say that is what you did, and treat every conclusion as provisional.
2. **Glob before Read** — at most three **Glob** calls, all three spent in step 1: one for the
   disassembly listing and symbol map, one for the handler and startup source, one for the failing
   test's own source file. Never open any of them with **Read** as the first move.
3. **Six Grep calls, each named by the step that spends it**: trap markers in the log (step 1), the
   cause code in the decode table (step 3), the exception PC in the disassembly (step 4), the
   vector-base and delegation register names alternated in one pattern across the handler and the
   test source (step 5), the faulting address's region in the **Memory map** (step 7, and only when
   the finding is the access-or-permission row of its table), and the exception PC in the
   reference-model log (step 8, and only when a model runs). No step spends a seventh, and the last
   two go unspent rather than being reallocated when they do not apply.
4. **Five bounded Read windows**: about 60 lines at the first trap report — or at the **State dump**
   instead, when the log prints no trap state (step 2); about 40 at the faulting instruction
   (step 4); about 40 spent across the configuration writes and, where the dump is a separate file
   not yet opened, its vector and delegation entries (step 5); about 40 at the second trap report or
   the handler entry (step 6); and about 30 at the memory-map entry the step-7 Grep found.
5. **The specification is outside this budget.** Nothing here funds reading it, and on most teams it
   is a document no Grep can open. So wherever a step below asks for a document and clause, get it
   one of exactly two ways: the **Architecture and revision** slot names a plain-text copy on disk,
   in which case you may spend the step-8 Grep on that copy *instead of* the reference-model log —
   never both — or you ask the core architect for the clause covering this cause and record that it
   came from a person, exactly as step 3 does for the decode table. Never write a clause number you
   did not read and nobody gave you; leaving it outstanding is the cheaper error by far.
6. A trap-marker Grep returning thousands of hits is not a broken pattern — it is the answer to
   step 6. Take the count and the first two line numbers and open nothing else.
7. **An instruction trace is the one artifact this budget will not survive.** A trace of a boot runs
   to gigabytes; enter it only through a Grep on a specific address, and if none is on disk, say so
   rather than describing cycle-by-cycle behaviour you never saw.
8. **Stopping rule.** Five windows spent with no settled classification: stop, report what is known,
   name the single artifact still needed, and state the coverage. Past that point answers get
   invented, and an invented architectural claim is the expensive kind.

## Procedure

### 1. Resolve the artifacts, and rule out a trap the test wanted

Resolve the log to a path first (budget rule 1), and spend the three **Glob** calls on the
**Disassembly**, the **Handler source** and the failing test's own source file now, so later steps
have paths rather than guesses. The test source is not optional bookkeeping: the check two paragraphs
below reads it, and step 5 Greps it alongside the handler.

Then one **Grep** of the log alternating the **Trap markers** with the profile's fatal and pass
markers. Record the hit count and the first two line numbers — steps 2 and 6 both need them.

Before decoding anything, check the **Expected-trap convention** in the test source you just
located — the slot says where that declaration lives. A test that deliberately takes a
system call, a breakpoint or an illegal instruction to prove the handler works *will* trap, and the
failure is then that the handler did not return cleanly, not that the trap happened. Triaging a
deliberate trap as a bug is the cheapest afternoon to lose in this area.

### 2. Recover the state of the first trap, not the last

Take the **lowest** line number from step 1 and **Read** about 60 lines starting roughly 20 lines
before it. Record, verbatim and with line numbers: the raw cause value before any decoding; the
exception program counter; the trap value; the mode the trap was taken **from** and the mode it was
taken **to**; and the saved previous-mode and interrupt-enable bits, if the flow prints them.

If the log prints none of these, the **State dump** slot says whether a control-register dump exists.
If neither exists, stop and ask for one — everything below is arithmetic on those numbers.

**Hardware overwrites cause, exception PC and trap value on every trap.** Unless the handler saves
them before it can itself trap, whatever is in the registers at the end of the run belongs to the
*last* trap. Where a printed tracer line and an end-of-run dump disagree, the printed line is the
first trap and the dump is not — use it, and say in the report which of the two you used.

### 3. Split the cause before you decode it

**Check first that this core has the shape the next three steps assume.** Steps 3, 5 and 6, and the
vectoring and delegation Gotchas below, describe one specific trap mechanism: a cause register whose
top bit says whether the trap was an asynchronous interrupt or a synchronous exception and whose
remaining bits number a code within that class; a vector register holding a base address and a
direct-or-vectored mode together in one value; and delegation registers that can only move a trap to
a *less* privileged mode. Cores in the RISC-V privileged family are built this way. **Plenty of
architectures are not** — one that dispatches through a table of vector entries indexed by an
interrupt number, or that funnels every trap into one of a few fixed entry points and reports the
reason in a separate syndrome register, splits and decodes its trap state differently, and
"delegation" and "vector base" may name nothing in it at all.

The **Architecture and revision** slot settles this, and here it is a gate rather than a detail. If
the answer is not an architecture of that shape, steps 1, 2, 4, 7 and 9 still hold — they need only
that a trap was reported, its state recorded, the exception PC mapped to an instruction and the
result owned — but steps 3, 5 and 6 must be adapted to this core's own mechanism, and the core
architect is who tells you what that mechanism is. Say in the report which of the two you did: an
adapted step is honest work, while a step used as written against a machine it does not describe
produces a fluent wrong answer, which is the expensive kind.

On a core that does have the shape, split the raw value into flag and code *first*: the two code
spaces are unrelated, so code 5 as an interrupt and code 5 as an exception are different failures
with different names.

Decode the code with one **Grep** of the **Cause decode table**. Do not decode from memory — every
core that adds a custom cause extends the standard list, and a code reserved in the base architecture
may be defined in ours. If the table cannot be read as a file, ask the core architect and record that
the decode came from a person. Two properties matter more than the name:

- **Required, or merely permitted?** Where the specification lets an implementation either complete
  an operation or trap on it — unaligned accesses are the usual case — trapping is a legal choice and
  the test is what has to change.
- **Does this cause define a trap value?** The specification fixes this cause by cause rather than
  once: a faulting address on the address, access and page-fault causes, and on several others a
  value the implementation is free to leave as zero. A zero there is evidence of nothing. Which
  causes are which is a clause, and budget rule 5 says where a clause comes from.

### 4. Turn the exception PC into an instruction

**Grep** the **Disassembly** for the exception PC, then **Read** about 40 lines around the hit — the
instruction, its enclosing symbol, and the handful before it. The exception PC does not mean the same
thing in both classes, and this is the most common wasted hour in trap debugging:

- **A synchronous exception** reports the address of the instruction that caused it. That instruction
  did not complete.
- **An interrupt** reports the address of the instruction that would have run next. Nothing is wrong
  with that instruction; it is only where control resumes.

Three outcomes are worth naming on sight: the address is **not in the disassembly at all**, so
control left the loaded image and the question is what jumped there; the address is inside the
handler or the vector table, so this is already a nested trap and step 6 owns it; or the symbol is
startup or library code nobody wrote for this test, which usually lands in environment.

Watch the arithmetic. With a compressed instruction set present, instructions are 2 bytes as well as
4, so an exception PC that is not 4-byte aligned is ordinary. And if the **Disassembly** slot says
the listing carries link addresses while the core reports load addresses, every comparison here is
off by the load offset — subtract it once, out loud, and say that you did.

### 5. Check vectoring and delegation against what the machine held

This step is written for the step-3 shape and is only usable on it. On a core without that shape, ask
the core architect which registers play the base, mode and delegation parts here — or whether nothing
does — before Grepping for names that may not exist.

One **Grep** across the **Handler source** and the test source Globbed in step 1, alternating the
vector-base register name with the delegation register names for this architecture, then **Read**
about 40 lines at the writes.

**Vectoring.** The vector-base register carries a base address and a mode in one value. In direct
mode every trap enters at the base. In vectored mode interrupts enter at the base plus the cause code
times the entry size, while synchronous exceptions still enter at the base. A handler written for one
mode and configured in the other lands part-way through an instruction stream, and what follows looks
like an RTL bug and is not one. The base field also ignores the low bits of what is written, with a
stricter alignment requirement in vectored mode than in direct mode, so a misaligned base silently
loses them. A base that reads back zero was never written: the trap enters at address zero, address
zero is not a handler, and the next trap is a fetch-side access fault. That is the loop in step 6,
and it is never RTL.

**Delegation**, in the two rules that settle most arguments. Delegation only ever moves a trap to a
**less** privileged mode, so a trap taken in the most privileged mode is not delegated whatever the
register holds. And a delegation register for a privilege mode that was not built is read-only zero,
so a test that writes it and then expects the trap elsewhere gets it in the most privileged mode and
reports an RTL bug; the **Architecture and revision** slot says which modes exist, and it settles
that in one line.

Both rules are properties of that shape rather than of every machine, so if what you find here is
going to be written up as an RTL bug, budget rule 5 is where the supporting clause comes from — a
plain-text copy, or the core architect, and the report says which.

Compare against the value the machine *held*, from the **State dump**, not the value the test wrote.
With no dump, say the check rests on the test's intent rather than on machine state, and mark that
part of the finding provisional.

### 6. Tell a single trap from a handler loop, and name which loop

Step 1's hit count decides: one or two hits is a single trap, thousands is a loop and the log is one
line repeated. **Read** about 40 lines at the *second* trap report and compare it field by field with
the first. Do not open the third.

| What repeats | What it means | Usual owner |
|---|---|---|
| Same exception PC, same cause | the handler returned without removing the cause | test or handler |
| Exception PC at the vector base or inside the handler | a second trap was taken inside the handler | test or handler, unless its cause is one the handler could not have provoked |
| Exception PC zero, or a fetch-side access fault at the base | the vector base was never written, or points where there is no memory | environment |

The first row has a short list of causes worth knowing by heart: a system-call or breakpoint trap
whose handler returned without advancing the saved address past the trapping instruction; an
interrupt whose source was never cleared at the device, so it reasserts the instant interrupts are
re-enabled; a fault whose mapping or permission the handler never changed. Each is a correct trap and
a wrong handler, and each reaches us reported as a timeout.

### 7. Classify — RTL, test or handler, or environment

`state` is the printed trap line or the control-register dump; `source` is the test, handler and
configuration files already open. `map` is the **Memory map**, and it is the one artifact in this
table you have not opened yet: when — and only when — the finding is the first row, spend the step-7
**Grep** on the map for the faulting address's region and **Read** about 30 lines around the hit.
If that slot is unfilled, or the map is not a file that can be read, say so and mark that row's
classification provisional rather than assuming which regions exist here.

| Symptom | Evidence | Check first | Usual class |
|---|---|---|---|
| Access fault on an address the test meant to use | state + map | whether the region exists here, with the permission the access needed | environment |
| Illegal instruction on an instruction the test meant to run | state + source | whether that extension or feature is built and enabled in this configuration | test, or environment |
| Illegal instruction on a control-register access | state + source | whether that register exists at this privilege and is writable | test |
| Trap taken in an unexpected mode | state + source | delegation, per step 5 | test, unless delegation was configured correctly and honoured wrongly |
| Interrupt taken while disabled, or not taken while enabled and pending | state | the enable, pending and mode bits at that instant | RTL |
| Trap value contradicts the cause | state | what the architecture requires that cause to write | RTL |
| Trap on the first instruction after reset | state + source | the reset vector, and whether the image is loaded there | environment |
| Every trap at one address with a fetch-side access fault | state | whether the vector base was ever written | test or environment |
| Two exceptions apply and the lower-priority one is reported | state | the architecture's exception priority order | RTL |
| A trap that appears on one seed only | state + source | what moved — usually interrupt arrival relative to the instruction | RTL, and a real one |

**An RTL classification requires the rule it violates, named by document and clause — and this skill
does not fund reading the specification.** Get the clause the way budget rule 5 says: from a
plain-text copy if the **Architecture and revision** slot names one, otherwise by asking the core
architect for it and recording in the report that a person supplied it. Until one of those has
happened, leave `rule` empty and say in `notes` that the clause is outstanding. "This looks wrong" is
not a classification; the designer will ask for the clause before reading further, and a clause
number that turns out not to exist ends the conversation for good.

### 8. Cross-check against the reference model, when there is one

If the **Reference model** slot says a lockstep model runs, spend the last **Grep** on its log at the
same exception PC. It is the cleanest discriminator available: the model taking the same trap with
the same cause means the test caused it, so go and read the test; the model taking **no** trap means
either the design trapped where the architecture does not require it or the model is behind on a
feature we implement — both worth reporting, only the first an RTL bug, and the specification clause
is what separates them; the model taking a *different* cause is decode or priority, and that is
exactly the clause to quote.

Every one of those endings needs a clause, and none of them may invent one. If no model runs, budget
rule 5 lets this last Grep go to a plain-text specification copy instead, when the **Architecture and
revision** slot names one — that is the only funded read of the specification in the skill. With
neither a model nor a readable copy, say so: the classification then rests on a clause the core
architect gave you, and the report names who gave it.

### 9. Write the finding

Write the failure signature per `_shared/failure-signature-schema.md` — same field order, same
normalisation rules — then fill in this block. It reuses field names from `dv-sim-log-first-error`'s
repro block so the two read side by side.

```
signature : <phase>|<kind>|<where>|<what>, per the shared schema
cause     : <raw cause value, split into class and code, then the decoded name>
trap pc   : <exception PC, its symbol, and whether it is the faulting or the resumption address>
tval      : <raw trap value, and what the architecture requires for this cause>
mode      : <taken from, taken to, and what delegation says it should have been>
vector    : <base and mode as the machine held them, and the entry the trap actually reached>
shape     : <single trap, or which row of step 6>
phase     : run
class     : design | infrastructure | unknown
blame     : <rtl | test-or-handler | environment>
rule      : <document and clause an RTL blame rests on, plus whether you read it or a person gave
             it to you; empty, with a note, while it is still outstanding>
model     : <what the reference model did at this PC, or that no model runs>
run id    : <whatever identifies this run for us>
log       : <path, and the line range worth reading>
coverage  : <how many trap reports you opened, of how many hits; which values came from a tracer
             line and which from an end-of-run dump; whether the step-3 shape check passed, and
             which steps you adapted if it did not>
notes     : <anything the next person would otherwise rediscover, including any value that came
             from a person rather than a file>
```

`phase` is narrowed to the single value `run` here — a trap is by construction a run-phase failure,
so the field never varies in this skill. It is kept in the block rather than dropped so a report from
here still joins against a signature prefix, and the narrowing is declared in
`_shared/handoff-vocabulary.md` so an aggregator knows this skill contributes to no other phase's
denominator.

`blame` is the finer classification this skill exists to produce; `class` is the coarse one the rest
of the pack compares on, so map it deliberately — RTL and test-or-handler are both `class: design`,
environment is `class: infrastructure`, and anything still resting on a missing state dump is
`class: unknown`. Matching the signature against the known-issue list is `dv-sim-log-first-error`
step 5, and is deliberately not a sixth Grep here.

## Gotchas

- **The registers readable at the end of the run belong to the last trap.** Cause, exception PC and
  trap value are overwritten every time, so on a loop the end-of-run dump describes iteration three
  thousand. Only the tracer line printed at the time carries the first one.
- **An interrupt's exception PC is not a faulting instruction.** It is where control resumes. Reading
  it as an exception's is how afternoons get spent staring at innocent code.
- **A handler that returns without advancing the saved address past a system-call or breakpoint
  instruction re-enters it forever.** Every one of those traps is correct; the run is reported as a
  hang, and the timeout is what reaches the bug tracker.
- **An interrupt whose source is never cleared at the device refires the instant it is re-enabled.**
  The handler can be right in every other respect. Look at the device model, not at the core.
- **A trap value of zero is legal on many causes.** The architecture names the causes that must write
  a meaningful value; elsewhere zero is permitted. Read the clause before filing a bug on a zero.
- **On a core with the step-3 shape, vectored mode moves interrupts only.** Synchronous exceptions
  enter at the base in both modes. A handler that works for exceptions and falls apart on interrupts
  is nearly always this — on an architecture that vectors by a different rule, this bullet is not
  about your machine and the core architect owns the equivalent.
- **On that same shape, a delegation register for a mode that was not built reads back zero**, so the
  write that "configured" it did nothing. Check what the machine held, never what the test wrote.
- **Compressed instructions make odd addresses ordinary.** An exception PC that is not 4-byte aligned
  is a misalignment only on a core without compressed instruction support — and even then the
  misaligned-address cause must come from the core, not from your own arithmetic.
- **Two exceptions on one instruction have a defined priority.** When the reported cause is the
  lower-priority of two that both apply, the finding is real but unactionable until you name both
  causes and the clause that orders them.
- **Enabling interrupts with a source already pending traps immediately.** That is the architecture
  working, not a race, and not an RTL bug.
- **Nobody in this loop has read the specification.** The clause in an RTL report either came off a
  plain-text copy on disk or out of the core architect's mouth. A clause number that reads plausibly
  and does not exist is the fastest way to have every later report from this pack ignored.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the trap mechanism was checked against the **Architecture and revision** slot before steps 3, 5 and
  6 were used, and any step adapted for a differently shaped core says which and how
- the cause is quoted **raw** and decoded, and the decode came from the team's table, not from memory
- interrupt-or-exception was settled **before** the exception PC was interpreted
- every value belongs to the **first** trap, and the report says whether it came from a tracer line
  or from an end-of-run dump
- an RTL blame names the document and clause it rests on, **and** says whether that clause was read
  in a file or supplied by the core architect — a clause written from memory is a fabrication
- an access-fault classification was checked against the **Memory map** rather than against an
  assumption about which regions exist
- delegation and vectoring claims are compared against a register the machine actually held, or are
  explicitly marked provisional
- the coverage line says how many trap reports were opened, of how many hits
- nothing the specification permits — a legal zero trap value, a permitted-but-not-required trap, an
  immediate trap on re-enabling a pending interrupt — has been written up as a bug

A wrong answer typically reports the last trap of a loop as the failure; blames the instruction at an
interrupt's exception PC; calls a handler bug an RTL bug because the trap itself was correct; asserts
that the core traps spuriously without naming the clause that says it should not; or decodes a cause
register that this core does not have, because step 3's shape check was skipped.

## Done when

You can name the first trap's cause, the instruction it belongs to, the one rule or line that caused
it, and the single owner who fixes it — with the coverage stated underneath.
