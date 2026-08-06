---
name: dv-custom-instruction-verification-plan
description: Audit a proposed or modified user-defined instruction encoding against the base opcode map for collisions, priority shadowing and reserved-space violations, then enumerate the semantic corner cases and emit the reference-model delta and the directed-test list. Use when someone adds a custom instruction to our core, when an extension proposal arrives as a spreadsheet row and nobody has checked whether its encoding is free, when a new instruction decodes in RTL but the golden model has never heard of it, or when you have been asked what tests a custom instruction needs before sign-off.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Custom-Instruction Extension Encoding Audit and Verification Plan
  semiskill-function: design-verification
  semiskill-role: processor-ip-dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-09-24
  semiskill-tags: custom-instruction, isa-extension, opcode-map, decoder, encoding, reference-model, verification-plan
---

# Custom-Instruction Extension Encoding Audit and Verification Plan

A custom instruction is cheap to add and expensive to get wrong. The encoding gets picked in a
meeting from a picture of the opcode map, the decoder accepts it because the arm it collides with is
written later in the same priority case statement, and the golden model never learns about it — so
lock-step co-simulation compares two cores that agree on every instruction except the one being
added. By the time silicon exists the encoding is permanent, and every bit the proposal left as a
don't-care has been given away for good.

The output is three artifacts: **an encoding result with the compared set named beside it, a
corner-case list filtered by what this instruction actually does, and a reference-model delta plus a
directed-test list someone else can work from.** Not a restatement of the proposal.

## When to use something else

This skill audits an encoding and writes a plan; it starts no simulation and opens no waveform. A
decoder that will not compile or elaborate is `dv-build-filelist-hygiene`. One failing log from a
test using the new instruction starts at `dv-sim-log-first-error`; a night of them is
`dv-regression-triage-routing`, and shrinking one is `dv-minimal-reproducer`. If the extension also
adds a control or status **register** and that register mismatches on bring-up, that is
`dv-ral-bringup` — registers and instructions fail in different ways and have different owners. If
you cannot yet say where the decoder or the golden model lives, spend an hour in
`dv-repo-orientation` first; this procedure assumes those paths are known or filled in below.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Encoding source | [[FILL: where the proposed instruction's encoding is written down, in what format, and whether it is a file that can be read]] | extension owner |
| Base opcode map | [[FILL: the file holding our base decoder's opcode table, and what one entry of it looks like]] | processor architect |
| Custom encoding space | [[FILL: which encodings our ISA revision leaves to non-standard extensions, which it reserves for future standard use, and the document and clause that say so]] | processor architect |
| Decoder style | [[FILL: whether our decoder is a priority case statement, a flat table, or generated — and if generated, from what source]] | CPU RTL owner |
| Reference model | [[FILL: which golden model the core is compared against, where its decode table lives, and whether that source is a file that can be read]] | model owner |
| Co-simulation compare points | [[FILL: what architectural state our lock-step compare covers, and at which point it samples]] | DV infra owner |
| Extension enable | [[FILL: the control bit or build option that turns this extension on, and what the core is specified to do when it is off]] | processor architect |
| Existing custom instructions | [[FILL: where the list of custom instructions we have already allocated lives, and how each entry records its encoding]] | DV lead |
| Directed test home | [[FILL: where our directed processor tests live and what one test is made of]] | block DV owner |

Two pack-wide facts live in `_shared/team-profile.md` and are read from there rather than re-asked:
its **Area to owner map** routes the findings in step 9, and its **Sign-off** entry says who accepts
this plan. The profile's **Register model source** is **not** this table's **Reference model** — one
is the register description our register model is generated from, the other is the instruction-set
golden model the core is compared against instruction by instruction. Different artifacts, different
owners, usually different repositories; filling either from the other puts a wrong path in both.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented opcode-space
assignment is the worst answer available here, because it looks like a clearance and is acted on
as one.

## Retrieval budget — read this before opening anything

A generated opcode header runs to thousands of machine-written lines and a decoder is one case
statement hundreds of lines long. Neither is readable end to end, and neither needs to be.

1. **Grep, Read and Glob work on files on disk.** If the encoding arrived as a slide, a spreadsheet
   cell or a chat message, resolve it to a path first — step 1. Until one exists you may reason over
   what you were shown, but say so: the opcode map was not searched, and every result is provisional.
2. **Never open the opcode map or the model's decode table with Read first.** **Glob** to locate,
   **Grep** for line numbers, then **Read** a bounded window.
3. The whole ledger is **3 Globs, 8 Greps and 5 windowed Reads of about 80 lines**: step 1 one Grep;
   step 2 one Glob, one Grep, one Read; step 3 one Grep and one Read; step 4 one Grep; step 5 one
   Grep; step 7 one Glob, one Grep, one Read; step 8 one Glob and one Read. Six Greps and four Reads
   spent, leaving two Greps and one Read for whichever step needs a second pass. Step 6 costs
   nothing — it is a checklist over facts already in hand.
4. A **Grep** returning more than about 200 hits is too broad. A mnemonic is often a substring of
   something common; anchor it before reading around the hits.
5. Stopping rule: if the opcode table is generated from a source **Read** cannot open, or the budget
   is spent before the sibling set settles, stop. Say which of the three artifacts you did produce
   and name the one fact you still need. Past that point encodings get invented, and an invented
   neighbour is worse than an unchecked one.
6. **State your coverage.** "Compared against all 14 entries in that opcode group" and "compared
   against the 9 the window reached; the group continues past it" are different claims, and only one
   of them supports a clearance.

## Procedure

### 1. Pin the proposed encoding to something on disk

Start from the **Encoding source** slot. If it resolves to a spreadsheet, a slide or a PDF, **Read**
cannot open it: ask the extension owner for a text copy, say every result rests on that
transcription, and do not transcribe from a picture of the opcode map yourself. If it resolves to a
file, one **Grep** for the mnemonic gives you the line.

Then restate it in one normalised form, because a per-field table is easy to read and impossible to
compare, while masks compare mechanically:

```
mnemonic : <as it will be spelled in the assembler>
mask     : <the bits this encoding constrains>
match    : <the value those constrained bits must take>
free     : <the bits it leaves unconstrained, listed by position>
against  : <the base ISA document and clause this proposal is written to>
```

`against` is not decoration. An encoding is free only relative to one revision of one document, and
"the architect said it was free" is a memory of a revision nobody wrote down.

### 2. Locate the base opcode map and pull the neighbourhood

**Glob** for the file the **Base opcode map** slot names, **Grep** it for the primary opcode field's
token or value, then **Read** one window of about 80 lines around the hits. Collect every entry in
that group with its mnemonic, mask and match.

That group is the neighbourhood, and bounding the comparison to it is an **approximation, not a
proof** — say so in the coverage line. An entry outside the group still collides if its own mask
leaves the primary opcode field unconstrained, which is exactly the shape of a catch-all or
illegal-instruction arm. Check the masks you collected for that shape rather than assuming none.

### 3. Test for overlap, then test for reachability

The overlap test is bitwise and costs no tool call. Take the bits both entries constrain — the
bitwise-and of the two masks — and ask whether the two match values agree on all of them. As one
expression that is the bitwise-exclusive-or of the two match values, and-ed with both masks: a zero
result means at least one bit pattern satisfies both entries and they collide. A non-zero result
means the surviving bit positions are what tell the entries apart; quote one, because that position
is the evidence and the clearance is only as good as it.

Do that arithmetic one named field at a time — primary opcode, then each sub-field, then the rest —
and write the two masks and the two match values out per field before you conclude anything. Nothing
here checks your work: a single digit misread out of a wide hex constant produces a clearance that
looks exactly like a correct one, and it is the only step in this procedure whose output no file can
contradict. If the encodings are wide enough that the per-field working does not fit in the block,
put it in `notes` rather than dropping it.

Overlap is half the question. Use the **Decoder style** slot, **Grep** the tree for the new mnemonic
— a name already used by an assembler table or another team's private header collides too — and
**Read** one window over the decoder's arm order. A priority case statement resolves an overlap
silently in favour of whichever arm is written first, so an overlap has three very different
outcomes — and "it collides" is none of them. Write the token step 9's block uses:

- **the new instruction is shadowed**, its colliding arm written first — it never decodes, every
  directed test for it fails at once, and somebody finds it in an afternoon. Record
  `collision: shadowed-by-sibling`;
- **the new instruction shadows an existing one**, its own arm written first — the older instruction
  quietly stops decoding, and the symptom is an unrelated, long-passing test failing days later for
  no visible reason. Record `collision: shadows-sibling` and name the entry it displaces;
- **the overlap is proven and the winner is not** — a flat or generated table with no arm order to
  read, or an order that ran past your window. Record `collision: overlaps-sibling`; guessing a
  shadow token here sends someone to debug the wrong instruction.

No overlap at all carries `collision: none-found` into step 5, which may still overturn it.

If the decoder is generated, the table is ground truth and the RTL is a build product. Say which of
the two you read; a finding against a generated file is a finding against its generator.

### 4. Check the space it lands in, and the bits it leaves free

**Grep** the map for the reserved and custom markers named in the **Custom encoding space** slot.
Three outcomes matter, they are not interchangeable, and each has one token — write it, rather than a
sentence that means it, or the same finding reaches the architect under three different names:

- the encoding falls under the marker your ISA revision designates for non-standard extensions →
  record `space status: custom`, quoting the clause that designates it;
- it falls under the marker reserved for future standard use → record
  `space status: reserved-for-standard`. Legal today, forward-incompatible forever: route it to the
  architect with the clause attached and do not clear it here;
- a marker or an existing entry already claims that encoding → record
  `space status: already-allocated`, then skip to step 9 and route the block as it stands. Nothing
  later in this procedure recovers an encoding that is taken, and a corner-case list for a proposal
  that has to change its encoding is work done twice.

If the slot is unfilled, or the markers are not in the file you read, record `space status: unknown`.
That is a question someone answers in a message; a guessed `custom` is a clearance nobody re-opens.

Then take the `free` bits from step 1 seriously. A bit the decoder ignores can never be given meaning
later, because software built today is free to set it to anything. If the base ISA says a field must
be zero, check whether the decoder enforces that or merely tolerates it. On a variable-length ISA the
instruction-length bits are part of the encoding and are never free.

### 5. Check it against the instructions we have already added

Use **one Grep** over the list the **Existing custom instructions** slot names, whose pattern
alternates the mnemonic with the match value — one call, and it is the single Grep the ledger gives
this step. Two teams allocating independently out of the same custom space is the most common source
of a real collision, and it never appears in step 2, because neither entry is in the base map.

A hit is a collision even though nothing in step 2 saw it. If that sibling is already an arm of the
decoder you read in step 3, apply that step's arm-order test to it and record the shadow token it
yields. If it is an allocation on paper with no decoder arm yet, record
`collision: overlaps-sibling` — the overlap is proven and no arm order exists to settle which side
wins, which is a weaker and more honest claim than either shadow token.

If the list reads clean and step 3 found no overlap either, record `collision: none-found`, and name
in the coverage line which list, and which revision of it, that clearance rests on.

If that list is not a file on disk, this is a handoff: ask its owner to compare the normalised
encoding from step 1, and record `collision: not-checked` until they answer. Matching from memory is
how two products ship one opcode meaning two things.

### 6. Enumerate the corner cases this instruction actually creates

Filter by the properties the instruction has. A pasted list of thirty cases for an instruction that
touches no memory is the tell that this step was skipped.

| If the instruction … | Settle this before the plan is written |
|---|---|
| writes a general-purpose register | destination equal to each source in turn; destination equal to the architecturally-fixed zero register; a result narrower than the register, and whether the upper bits are sign- or zero-extended |
| reads more sources than the widest base instruction | register-file read ports, and whether the hazard and bypass logic was told about the extra operand at all |
| takes more than one cycle | write-after-write against a shorter instruction issued behind it, in-order retirement, and whether an interrupt can be taken mid-instruction |
| can be interrupted or restarted | restart-from-scratch versus resume, idempotence, and what a partially executed instruction leaves architecturally visible |
| can fault | precise state, the reported cause, the recorded faulting-instruction value, and whether any register write happens before the fault is taken |
| accesses memory | alignment and misaligned handling, address translation and page faults, protection checks, byte ordering, ordering against fences, atomicity, and fault-before-write |
| is gated by an enable | that it raises the base ISA's illegal-instruction trap when the extension is off — not a silent no-op — and that software can tell the two apart |
| is restricted by privilege | behaviour at every privilege level, and whether the check happens before or after the operands are read |
| adds architectural state | reset value, context-switch save and restore, the enable or dirty bookkeeping, and debug visibility — agreed with whoever owns the software port |
| writes a status or flag register | sticky bits, read-modify-write races with other writers of that register, and what a read in the next instruction slot returns |
| rounds or saturates | where the rounding mode comes from, tie-breaking, the saturation boundary at each width, and overflow of the flag itself |
| has a compressed or longer-than-base form | length decode, and whether the trace and debug units parse the new length |

One row settles a field of step 9's block and not only a test. Read `faulting` as a statement about
the instruction **with its extension enabled** — the disabled-extension illegal-instruction trap
belongs to the enable row and to step 8's negative case, not to this field. Then: if any operand
value, address, alignment or privilege check in the instruction's own definition can raise an
exception, record `faulting: can-fault` and keep the `can fault` row above. If the definition names
no exception condition and the instruction touches neither memory nor privileged state, record
`faulting: cannot-fault`, and treat that as a claim step 7's exception list has to agree with — a
model that raises an exception the plan calls impossible fails co-simulation in the direction nobody
debugs first. If the definition is merely silent, record `faulting: unknown` and put the question to
the architect; silence in a proposal is not a specification of no faults.

Rows whose answer is in the RTL you can settle from source. Rows about timing, interruptibility or
retirement order you cannot: **ask the engineer to run that case with waves enabled and give you the
paths to the log and the waveform**, and record in the plan that the answer came from a person.

### 7. Write the reference-model delta

**Glob** and **Grep** for the decode table the **Reference model** slot names, **Read** about 60
lines of it to match its shape exactly, then write the delta as items a model owner can implement
without asking you anything:

- the decode entry — mask, match, mnemonic — added to the same table the disassembler reads, so a
  trace of the new instruction is a mnemonic rather than a word of hex;
- operand extraction: which bits become which operand, and the extension rule for each immediate;
- the semantics, written as the state it reads and then the state it writes, in that order;
- the exception conditions, and their priority against each other and against the base ISA's;
- the side-effect list — every piece of state that changes and is not the named destination;
- what the lock-step compare must now cover, per **Co-simulation compare points**, and honestly what
  it cannot. Any result depending on timing, on a free-running counter, or on state the model does
  not carry must be named and excluded explicitly, or the compare fails for a reason nobody can
  debug.

### 8. Write the directed-test list

**Glob** the **Directed test home**, **Read** one sibling test, and list cases in that shape, each
with its pass criterion. The minimum list is:

- one case per corner-case row kept in step 6;
- one encoding case per free bit — set it, and check the instruction still decodes the same way, or
  traps, whichever the base ISA clause from step 1 requires;
- one negative case per nearest neighbour from step 2 — the encodings one constrained bit away must
  still decode to exactly what they decoded before this change;
- one negative case with the extension disabled, per **Extension enable**;
- if step 3 found a shadowed entry, one case proving that entry still decodes.

Then say what stays random and what random cannot reach. Adding the instruction to the generator's
opcode pool, with crosses on destination-equals-source, the zero register as each operand, and the
enable bit, is worth more than ten further directed cases. But a generator draws *legal* encodings,
so it never produces the reserved-field and illegal-encoding cases — those are directed by necessity
rather than by preference.

**Ask the engineer to run this list once it exists and give you the paths to the logs.** Anything
failing then belongs to `dv-sim-log-first-error`, not back here.

### 9. Record the audit block

```
instruction  : <mnemonic, plus the artifact and line its encoding was read from>
encoding     : <one mask and one match, exactly as the source writes them>
space        : <the named encoding space it lands in, and the clause that assigns it>
space status : custom | reserved-for-standard | already-allocated | unknown
collision    : none-found | overlaps-sibling | shadowed-by-sibling | shadows-sibling | not-checked
free bits    : <the bits the encoding leaves unconstrained, and what each one forecloses>
state added  : <none, or every piece of new architectural state and its reset value>
faulting     : cannot-fault | can-fault | unknown
model delta  : <the entries the golden model needs, one line each>
tests        : <n positive, n negative, what is left to random, and where they will live>
owner        : <name from the profile's area-to-owner map, or blank plus candidates>
coverage     : <how many sibling entries were compared, out of how many that group holds>
notes        : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

Leave a field blank rather than filling it plausibly, and route the block to the owner the profile's
**Area to owner map** yields and to whoever its **Sign-off** entry names. A blank owner is a question
someone answers in a message; an invented encoding clearance is a tape-out.

## Gotchas

- **A collision need not produce an error anywhere.** A priority-encoded decoder resolves it silently
  in favour of whichever arm is written first. Nothing warns, nothing fails to build, and the symptom
  is an old instruction that quietly stopped decoding.
- **The primary-opcode neighbourhood is a bounded approximation.** Any entry whose mask leaves the
  primary opcode field unconstrained can collide across groups, and catch-all or illegal-instruction
  arms are exactly that shape. Say the comparison was bounded rather than that it was complete.
- **A reserved field the decoder ignores is a field given away permanently.** Software built while
  the decoder tolerated a non-zero value may have set it to anything, so the field can never carry
  meaning afterwards. Enforce it, or record that the space has been surrendered.
- **The architecturally-fixed zero register is not an operand like the others.** Reads yield zero and
  writes are discarded, so an instruction whose only architectural effect is its destination write
  becomes a no-op with that destination — while a design treating it as a real write still performs
  every side effect. Both behaviours are defensible; only one is specified.
- **Adding architectural state is the expensive decision, not adding an instruction.** New state must
  be reset, saved and restored across a context switch, given its enable or dirty bookkeeping, and
  made visible to debug, with the software port's owner agreeing to all of it. It is discovered last
  and costs most, which is why step 6 asks before the plan is written.
- **Lock-step co-simulation only compares what it samples.** State the golden model does not carry
  cannot disagree with anything, so a brand-new instruction can pass co-simulation on the day it is
  added without having been compared at all.
- **Illegal must mean illegal.** With the extension disabled the encoding has to raise the base ISA's
  illegal-instruction trap. A decoder treating it as a no-op makes the extension undetectable at run
  time, and every software feature check built on it is then a lie.
- **A variable-length ISA decodes length before opcode.** A custom instruction wider than the base
  width whose length bits are wrong does not merely mis-decode itself — it mis-parses the whole fetch
  stream behind it until the next re-sync, and the trace reads as memory corruption.
- **Multi-cycle instructions break the retirement order the rest of the pipeline assumes.** A long
  custom instruction followed by a short base instruction writing the same destination is the
  write-after-write case, and random stimulus does not reach it at a useful rate.
- **The mnemonic collides too.** An assembler, disassembler or trace decoder already using that name
  is a build-time surprise rather than a silicon one, but it is found the same way — by Grepping for
  the string before the meeting instead of after it.

## Human verification — what a wrong answer looks like

Before anyone acts on the plan, check:

- every encoding value is quoted with the file and line it came from, or attributed to the person who
  supplied it and marked provisional — a value with neither is an invention
- the coverage line names how many sibling entries were actually compared, and that number is what
  the window reached rather than the size of the group
- a clearance rests on the opcode map on disk, not on the picture inside the proposal
- `space status` is `unknown` rather than `custom` on any pass where the **Custom encoding space**
  slot was unfilled, and `collision` is `not-checked` rather than `none-found` wherever the existing
  custom-instruction list could not be read
- a proven overlap whose winner was never established reads `overlaps-sibling`, not one of the two
  shadow tokens — a shadow token asserts an arm order somebody actually read, and the two send the
  reader to different instructions
- the corner-case list was filtered — memory-ordering rows for an instruction that touches no memory
  mean the table was pasted rather than applied
- every row needing a run or a waveform is written as a handoff to a named person, not as a claim
- the model delta says what the compare **cannot** cover, not only what it can
- the test list contains negative cases; one with no illegal-encoding case and no extension-disabled
  case is a plan for a feature, not for an encoding

A wrong answer typically clears an encoding after comparing it against the four instructions visible
in one screenshot, or reproduces last quarter's thirty-row corner list unchanged because it was never
filtered by what this instruction does.

## Done when

The encoding has a result with its compared set named beside it, the model owner has a delta they can
implement without asking you anything, and every corner case is either a listed test or a written
handoff.
