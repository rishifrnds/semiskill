---
name: dv-ral-bringup
description: Bring up a UVM register model and diagnose the failures that follow, using a fixed root-cause tree keyed on the symptom. Use when the hardware reset check fails, when a bit-bash or register access test mismatches, when a register reads back the wrong value or lands at the wrong address, when front door and back door disagree, or when you are wiring an adapter and predictor for the first time.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Register Model Bring-Up and the Register-Failure Decision Tree
  semiskill-function: design-verification
  semiskill-role: soc-dv-engineer
  semiskill-level: junior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-02-05
  semiskill-tags: ral, registers, uvm, bring-up, adapter, predictor, debug
---

# Register Model Bring-Up and the Register-Failure Decision Tree

Register bring-up fails in about a dozen distinct ways, and each one has a short list of causes. The
expensive part is never the fix — it is spending a day rediscovering which of the dozen you are in,
because every one of them presents as the same sentence in the log: a mismatch at some address. This
skill turns that day into a lookup — classify the symptom, then check the two or three things that
can actually produce it.

The output is a **classification, the evidence line that supports it, and which of three owners it
belongs to**: the register spec, the RTL, or the testbench integration. Not a narrative.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Source of truth | [[FILL: the format and repository path our register description lives in — IP-XACT, SystemRDL, or a spreadsheet]] | register owner |
| Generator | [[FILL: the generator and version that emits both the RTL register block and the UVM register model]] | DV infra |
| Model location | [[FILL: where the generated register model files land in our tree]] | your mentor |
| Bus agent and adapter | [[FILL: which bus agent and which adapter class this block uses]] | block DV owner |
| Reset convention | [[FILL: which reset this register block uses, and how long the testbench waits before the reset check]] | RTL designer |
| Back-door paths | [[FILL: whether hdl paths are set for this block, and the root path they hang from]] | DV infra |
| Exclusions | [[FILL: how we record a deliberately excluded register or field, and where that waiver list lives]] | DV lead |
| Log location | [[FILL: where the bring-up log is saved so it can be read from disk]] | your mentor |

**If a slot is unfilled, stop and ask. Do not guess.** An invented register path, generator name or
reset convention produces an answer that is confidently wrong, and unpicking it costs more than
having no answer at all.

## Retrieval budget

A generated register model for a mid-size block is tens of thousands of lines and is machine-written,
so it is uniformly boring — reading it end to end teaches nothing and burns the whole context.
Work in this order and stop when the classification is settled:

1. **Glob** first to find the generated model and the environment file that builds the map, adapter
   and predictor. Never open a generated file with **Read** as the first move.
2. **Grep** for the exact register or field name to get line numbers. One symptom, one register —
   resist widening.
3. **Read** bounded windows only: about 40 lines around the register's declaration, and about 40
   lines around the map entry. Two or three windows total.
4. If a **Grep** returns more than about 100 hits, the name is a substring of something common —
   anchor it (leading `"` or trailing `,`) before reading anything.
5. Stopping rule: after four windowed **Read** calls without a settled classification, stop and
   report what is known plus the one thing you would need next. Continuing past this point is where
   invented explanations come from.

## Procedure

### 1. Name the source of truth before reading the model

The register model is generated, and so, usually, is the RTL register block. If both come from the
same source at the same revision they cannot disagree, so a genuine mismatch means one of three
things: they came from different revisions, one side was hand-edited after generation, or the RTL
that consumes the generated block ignores it. **Grep** the generated model's header for a version,
date or source-file stamp, and do the same for the RTL register block. Record both stamps verbatim.
If they differ, stop — that is the finding, and no amount of debug below will improve on it.

### 2. Locate the register, its map entry, and its fields

Three **Grep** calls, in this order:

- the register class or type name, to find its declaration
- `add_reg` together with the register name, to find its offset and rights in the map
- `configure` inside that register, to find each field's size, lsb, access policy, volatility and
  reset value

Then two bounded **Read** windows: the field declarations, and the map construction (`create_map`,
`add_submap`, `set_base_addr`). Quote the numbers; do not restate them from memory a paragraph later.

### 3. Confirm the bring-up order, and that it was actually followed

The standard order is not arbitrary — each stage assumes the previous one passed:

1. **Hardware reset check.** A front-door read of every register immediately after reset, compared
   against the model's reset values. It goes first because it proves three things at once with no
   prior state: the map addresses decode, the adapter moves data in the right direction, and the
   reset values agree. If this fails, nothing after it is evidence of anything.
2. **Bit-bash.** Walks a one through every bit of every field through the front door and checks the
   read-back against what the field's *declared access policy* predicts. Second, because it assumes
   addressing is already proven — so its failures point at policy, width or lsb, not at the map.
3. **Access test.** Writes front door and reads back door, then the reverse. Last, because it needs
   both doors working and every hdl path resolved. Ahead of the others it produces addressing bugs
   wearing a back-door costume.

If back doors are used at all, a path-resolution check belongs between stages 2 and 3 — an hdl path
that silently fails to resolve returns X or zero on some simulators without an error.

To get this evidence, **ask the engineer to run the bring-up test with the register sequences enabled
and save the log where it can be read from disk**, then work from that file. The agent cannot start a
simulation.

### 4. Classify the symptom

| Symptom | Check first | Usual cause |
|---|---|---|
| Every register mismatches, expected value is zero | whether the model's reset was applied in the reset phase | the mirror was never initialised, so it holds zero |
| Every register mismatches, every read returns the same value | the adapter's `bus2reg` direction and status | read data never reaches the model |
| One register's reset value is wrong | the value in the spec, in the model, and what the RTL returned | spec and RTL built from different revisions |
| Only the first few registers fail the reset check | when the check began relative to reset deassertion | the sequence started before reset propagated |
| Write then read returns the old value | the field's declared access policy | RO or write-once in one side, RW in the other |
| Write then read returns zero | clear-on-write or clear-on-read semantics | a W1C, WC or RC field behaving correctly |
| The value lands in the wrong bit position | the field's size and lsb, then map endianness | width or lsb mismatch |
| The access lands at the wrong address | map base, offset, bus width, byte addressing | word offsets used where byte addresses are expected |
| A read returns a different register's contents | two entries at one offset, or an overlapping submap | a shadowed address |
| Front door and back door disagree | the hdl path, then whether the read races a synchroniser | wrong path, or clock-domain lag |
| A neighbouring field changes when one field is written | byte-enable support and partial-write behaviour | the field write wrote back the whole register |
| A status field mismatches only sometimes | whether the field is declared volatile | hardware updates it between write and check |

### 5. Access policy — the section that has to be exactly right

Most "the model is wrong" reports are a correct model describing a policy the reader misremembered.
Read this table before writing a conclusion about any non-RW field.

| Policy | Effect of a write | Effect of a read |
|---|---|---|
| RW | stores the written value | returns the stored value, no side effect |
| RO | no effect | returns the hardware value, no side effect |
| WO | stores the written value | undefined; do not compare it against anything |
| RC | no effect | returns the value, then clears all bits |
| RS | no effect | returns the value, then sets all bits |
| WC | any write clears all bits | no effect |
| WS | any write sets all bits | no effect |
| WRC | stores the written value | returns the value, then clears all bits |
| WCRS | any write clears all bits | returns the value, then sets all bits |
| W1C | a 1 clears that bit; a 0 leaves it | no effect |
| W0C | a 0 clears that bit; a 1 leaves it | no effect |
| W1S | a 1 sets that bit; a 0 leaves it | no effect |
| W1T | a 1 toggles that bit; a 0 leaves it | no effect |
| W1 | stores the value on the first write after reset only; later writes ignored | returns the stored value |
| NOACCESS | no effect | no effect; excluded from every test |

Two consequences worth internalising. First, the bit-bash stage derives its expected read-back
entirely from the declared policy, so a policy that is wrong *in the model* makes the sequence
complain loudly about correct RTL — always confirm the policy string against the spec before
escalating to the designer. Second, quote the policy exactly as the model spells it (`W1C`), never
as a paraphrase ("write-one-to-clear-ish"), because the whole point is that these are distinguishable.

Keep the model's own operations straight too: `get`/`set` touch only the desired value and generate
no bus traffic; `read`/`write` generate front-door traffic and update the mirror; `peek`/`poke` are
back-door and need an hdl path; `mirror` reads and optionally compares; `update` writes only where
desired and mirrored differ; `predict` forces the mirror without any traffic. A report that says a
register "was written" without saying which of these was used is not yet a report.

### 6. Address, width and lsb

**Read** the map construction and check, in order: the map's base address, the bus width in bytes,
whether byte addressing is set, and the offset given for this register. Offsets are in the map's own
addressing units — a register list written in word units against a byte-addressed map puts every
register at a fraction of its intended address, which shows up as a uniform stride error across the
whole block rather than one bad register.

For a sub-block, also check the offset at which its map was added to the parent. A wrong submap
offset moves an entire block at once, and looks identical to a decode bug in the interconnect.

For field position, compare the model's size and lsb against the spec field by field. A field that
reads back shifted by a constant is an lsb error; a field that reads back truncated is a size error;
a field that reads back byte-reversed is a map endianness setting, not a field problem.

### 7. Front door versus back door

Some disagreements are correct and must not be filed as bugs:

- A back-door access has **no read side effects**, so on an RC or RS field the two doors are supposed
  to differ after a front-door read.
- On a WO field the front-door read is meaningless while the back door returns the stored value.
- A register that is a captured snapshot in the RTL — a shadow or holding register — legitimately
  differs from the live counter the hdl path points at.

The real bugs are: an hdl path that does not resolve; a path pointing at the wrong hierarchy after an
RTL rename; and a back-door check sampling before a value has crossed a synchroniser into the
register's clock domain. For the last one the tell is that the mismatch disappears when the check is
moved later — say that explicitly rather than calling it intermittent.

### 8. Adapter and predictor

These two sit between a correct model and a correct design, and they cause a large share of
bring-up failures that look like model bugs.

- The adapter converts a register operation to a bus item and back. If its reverse conversion does
  not set the operation's status, every access looks like it failed even when the data was right.
- If the bus driver returns read data on a separate response path, the adapter must be told that
  responses are provided; otherwise the model reads the request item and returns whatever was in it.
- Byte-enable support is declared on the adapter. With it off, a single-field write becomes a
  full-register write of the mirrored contents.
- The predictor observes the bus monitor and updates the mirror from what actually happened on the
  bus. Use it *or* automatic prediction inside the map — never both, because two updates for one
  access silently corrupt any clear-on-access field.
- Explicit prediction through the monitor is mandatory if anything other than this sequence can
  write these registers — another master, firmware, or a back-door poke elsewhere in the environment.
- On a pipelined bus where address and data arrive on separate channels, the monitor must publish one
  complete item; a half-formed item makes the predictor write plausible garbage into the mirror.

### 9. Record the finding

Write the result as a failure signature following `_shared/failure-signature-schema.md` — same field
order, same normalisation rules — and add three lines beneath it: the symptom class from step 4, the
file and line number of the evidence, and the owner (spec, RTL, or integration). If any of the three
cannot be filled from text actually on disk, write `?` rather than an inference.

## Gotchas

- **The RTL's reset does not reset the model.** The model's mirror is initialised by an explicit
  reset call in the testbench. Skip it and every reset check compares against zero — which looks
  exactly like an RTL that never resets, and sends you to the wrong person.
- **Automatic prediction plus an explicit predictor updates the mirror twice.** On RW fields nobody
  notices. On W1C or RC fields the second update applies the clear again and the mirror drifts from
  the design a few accesses later, far from the cause.
- **A field-level write is a whole-register write.** Writing one RW field of a register that also
  holds W1C bits writes the mirrored W1C bits back too, and can clear live status. Check byte-enable
  support before reporting that the design clears status spuriously.
- **Volatile is load-bearing, not decoration.** A hardware-updated field that is not declared
  volatile makes every mirror comparison a race; a field wrongly declared volatile is excluded from
  the comparison, so real bugs pass silently. Both errors are invisible in a passing log.
- **A field declared with no reset value is skipped by the reset check.** An excluded field and a
  correct field produce the identical log line: nothing.
- **The register data and address widths are compile-time settings.** A model containing a register
  wider than the compiled data width truncates without complaint, and the truncation looks like an
  RTL bug in the upper bits.
- **Bit-bash on a write-once field fails from the second bit onward** — the register stopped
  accepting writes after the first, exactly as specified. The same shape appears for any register
  behind a lock or unlock-code register, and for anything gated by a clock-enable that the sequence
  turned off two registers earlier.
- **Overlapping addresses are usually a warning, not an error.** A submap added at the wrong offset
  shadows real registers, and the only evidence is one warning line near the very start of the log,
  hundreds of lines before the first mismatch.
- **A register that exists in the block but was never added to a map has no address.** Depending on
  the flow it either errors at access time or quietly resolves to the block base, which reads as a
  duplicate-address bug in a completely different register.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the classification names **one** owner — spec, RTL, or integration. "Could be either" means step 4
  was not finished.
- every numeric claim (reset value, offset, size, lsb, policy) is quoted with a file path and line
  number, not recalled.
- a reset-value finding shows **three** values from three sources: the spec, the generated model, and
  what the design actually returned.
- an access-policy finding quotes the policy string exactly as the model spells it.
- nothing that the policy table in step 5 says is correct behaviour has been filed as a bug.

A wrong answer typically declares "the register model is wrong" without naming a field; or reports a
W1C, RC or WO field working exactly as specified as a mismatch; or blames the RTL for a reset
mismatch that was really an uninitialised mirror; or explains a front-door versus back-door gap with
clock-domain lag without checking that the hdl path resolves at all.

## Done when

You can name the symptom class, the single field or map entry that produces it, and the one person
who fixes it.
