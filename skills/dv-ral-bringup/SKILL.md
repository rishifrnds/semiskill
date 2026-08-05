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

Register bring-up fails in about a dozen distinct ways, each with a short list of causes. The
expensive part is never the fix — it is spending a day rediscovering which of the dozen you are in,
because every one presents as the same sentence in the log: a mismatch at some address. This skill
turns that day into a lookup. The output is a **classification, the evidence line behind it, and
which of three owners it belongs to**: the register spec, the RTL, or the testbench integration.

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
reset convention gives a confidently wrong answer, and unpicking that costs more than no answer.

## Retrieval budget

A generated register model for a mid-size block runs to tens of thousands of machine-written lines —
reading it end to end teaches nothing and burns the context. Work in this order, and stop once the
classification is settled:

1. **Glob** first for the generated model and the environment file that builds the map, adapter and
   predictor. Never open a generated file with **Read** as the first move.
2. **Grep** for the exact register or field name to get line numbers — one symptom, one register.
   More than about 100 hits means the name is a substring of something common; anchor it (leading
   `"` or trailing `,`) before reading anything.
3. **Read** bounded windows only — about 40 lines around the register declaration and 40 around its
   map entry, two or three windows in total.
4. Stopping rule: after four windowed **Read** calls with no settled classification, stop and report
   what is known plus the one thing you still need. Past that point answers get invented.

## Procedure

### 1. Name the source of truth before reading the model

The register model is generated, and so, usually, is the RTL register block. Built from one source at
one revision they cannot disagree, so a real mismatch means different revisions, a hand edit after
generation, or RTL that ignores the generated block. **Grep** both files' headers for a version, date
or source stamp, record them verbatim, and if they differ stop — that is the finding.

### 2. Locate the register, its map entry, and its fields

Three **Grep** calls: the register class or type name, for its declaration; `add_reg` with the
register name, for its offset and rights in the map; `configure` inside that register, for each
field's size, lsb, access policy, volatility and reset value. Then two bounded **Read** windows — the
fields, and the map construction (`create_map`, `add_submap`, `set_base_addr`).

### 3. Confirm the bring-up order, and that it was followed

The standard order is not arbitrary — each stage assumes the previous one passed.

1. **Hardware reset check.** A front-door read of every register right after reset, compared against
   the model's reset values. First, because with no prior state it proves three things at once: the
   addresses decode, the adapter moves data the right way, and the reset values agree.
2. **Bit-bash.** Walks a one through every bit of every field through the front door, checking the
   read-back against what the field's *declared access policy* predicts. Second, because it assumes
   addressing is proven — so its failures point at policy, width or lsb, not at the map.
3. **Access test.** Writes front door and reads back door, then the reverse. Last, because it needs
   both doors working and every hdl path resolved; earlier it yields addressing bugs in a back-door
   costume. A path that fails to resolve returns X or zero on some simulators with no error at all,
   so put a path-resolution check just ahead of it.

To get this evidence, **ask the engineer to run the bring-up test with the register sequences enabled
and save the log where it can be read from disk**. The agent cannot start a simulation and must not
invent what one would have printed.

### 4. Classify the symptom

| Symptom | Check first | Usual cause |
|---|---|---|
| Every register mismatches, expected value zero | whether the model's reset was applied in the reset phase | the mirror was never initialised |
| Every register mismatches, every read the same value | the adapter's bus-to-register conversion and its status | read data never reaches the model |
| One register's reset value is wrong | the value in the spec, in the model, and what the RTL returned | spec and RTL built from different revisions |
| Only the first few registers fail the reset check | when the check began relative to reset deassertion | the sequence started before reset propagated |
| Write then read returns the old value | the field's declared access policy | RO or write-once one side, RW the other |
| Write then read returns zero | clear-on-write or clear-on-read semantics | a W1C, WC or RC field behaving correctly |
| The value lands in the wrong bit position | the field's size and lsb, then map endianness | width or lsb mismatch |
| The access lands at the wrong address | map base, offset, bus width, byte addressing | word offsets where byte addresses are expected |
| A read returns a different register's contents | two entries at one offset, or an overlapping submap | a shadowed address |
| Front door and back door disagree | the hdl path, then whether the read races a synchroniser | wrong path, or clock-domain lag |
| A neighbouring field changes when one field is written | byte-enable support and partial-write behaviour | the field write wrote back the whole register |
| A status field mismatches only sometimes | whether the field is declared volatile | hardware updates it between write and check |

### 5. Access policy — the part that has to be exactly right

Most "the model is wrong" reports are a correct model describing a policy the reader misremembered.
Read this before concluding anything about a non-RW field.

| Policy | Effect of a write | Effect of a read |
|---|---|---|
| RW | stores the written value | returns the stored value, no side effect |
| RO | no effect | returns the hardware value, no side effect |
| WO | stores the written value | undefined; do not compare it against anything |
| RC | no effect | returns the value, then clears all bits |
| WC | any write clears all bits | no effect |
| W1C | a 1 clears that bit; a 0 leaves it | no effect |
| W0C | a 0 clears that bit; a 1 leaves it | no effect |
| W1S | a 1 sets that bit; a 0 leaves it | no effect |
| W1T | a 1 toggles that bit; a 0 leaves it | no effect |
| W1 | stores on the first write after reset only; later writes ignored | returns the stored value |
| NOACCESS | no effect | no effect; excluded from every test |

The rest compose those two columns rather than adding anything new: `RS` and `WS` are `RC` and `WC`
with set for clear, `WRC` stores on write and clears on read, `WCRS` clears on write and sets on
read, `W1CRS` clears the written ones and sets all bits on read. Bit-bash derives its expected
read-back entirely from the declared policy, so a policy wrong *in the model* makes the sequence
complain loudly about correct RTL — confirm the string against the spec before escalating to the
designer, and quote it exactly as the model spells it (`W1C`), never as a paraphrase.

Keep the model's operations straight too: `get`/`set` touch only the desired value and make no bus
traffic; `read`/`write` make front-door traffic and update the mirror; `peek`/`poke` are back-door
and need an hdl path; `mirror` reads and optionally compares; `update` writes only where desired and
mirrored differ; `predict` forces the mirror with no traffic. A report saying a register "was
written", without saying which of these was used, is not yet a report.

### 6. Address, width and lsb

**Read** the map construction and check, in order: base address, bus width in bytes, whether byte
addressing is set, and this register's offset. Offsets are in the map's own addressing units, so a
register list written in word units against a byte-addressed map puts every register at a fraction of
its address — a uniform stride error across the block, not one bad register. For a sub-block, check
the offset its map was added at: a wrong submap offset moves a whole block at once and is
indistinguishable from an interconnect decode bug. For field position, compare size and lsb field by
field — shifted by a constant is an lsb error, truncated is a size error, byte-reversed is the map's
endianness and not a field problem at all.

### 7. Front door versus back door

Some disagreements are correct and must not be filed as bugs. A back-door access has **no read side
effects**, so on an RC field the two doors are supposed to differ after a front-door read. On a WO
field the front-door read is meaningless while the back door returns the stored value. A captured
snapshot in the RTL — a shadow or holding register — legitimately differs from the live counter its
hdl path points at. The real bugs are a path that does not resolve, a path left pointing at the old
hierarchy after an RTL rename, and a back-door check sampling before the value has crossed a
synchroniser into the register's clock domain. The tell for the last is that the mismatch disappears
when the check moves later — say that rather than calling it intermittent.

### 8. Adapter and predictor

These sit between a correct model and a correct design and cause a large share of failures that look
like model bugs. The adapter converts a register operation to a bus item and back; if the reverse
conversion does not set the operation's status, every access looks failed even when the data was
right. If the driver returns read data on a separate response path, the adapter must declare that
responses are provided, or the model reads the request item and returns whatever was in it.
Byte-enable support is also declared there — with it off, a single-field write becomes a
full-register write of the mirrored contents.

The predictor observes the bus monitor and updates the mirror from what actually happened. Use it
*or* automatic prediction inside the map, never both: two updates for one access silently corrupt any
clear-on-access field. Explicit prediction is mandatory if anything besides this sequence writes
these registers — another master, firmware, or a back-door poke elsewhere. On a pipelined bus the
monitor must publish one complete item; a half-formed one makes the predictor write plausible
garbage into the mirror.

### 9. Record the finding

Write the result as a failure signature following `_shared/failure-signature-schema.md` — same field
order, same normalisation rules — then add three lines: the symptom class from step 4, the file and
line number of the evidence, and the owner. If one cannot be filled from text actually on disk, write
`?` rather than an inference.

## Gotchas

- **The design's reset does not reset the model.** The mirror is initialised by an explicit reset
  call in the testbench; skip it and every check compares against zero, which looks exactly like an
  RTL that never resets and sends you to the wrong person.
- **Automatic prediction plus an explicit predictor updates the mirror twice.** Nobody notices on RW.
  On W1C or RC the second update applies the clear again and the mirror drifts a few accesses later.
- **A field-level write is a whole-register write.** Writing one RW field of a register that also
  holds W1C bits writes the mirrored W1C bits back and can clear live status — check byte-enable
  support before reporting that the design clears status spuriously.
- **Volatile is load-bearing, not decoration.** A hardware-updated field not declared volatile makes
  every mirror comparison a race; a field wrongly declared volatile is excluded from the comparison,
  so real bugs pass silently. Both errors are invisible in a passing log.
- **A field declared with no reset value is skipped by the reset check** — an excluded field and a
  correct field produce the identical log line: nothing.
- **Register data and address widths are compile-time settings.** A register wider than the compiled
  data width truncates without complaint, and reads as an RTL bug in the upper bits.
- **Bit-bash on a write-once field fails from the second bit onward** — the register stopped
  accepting writes after the first, exactly as specified. Same shape for a register behind a lock,
  and for anything gated by an enable the sequence cleared two registers earlier.
- **Overlapping addresses are usually a warning, not an error.** A submap added at the wrong offset
  shadows real registers, and the only evidence is one warning line near the start of the log.
- **A register in the block but never added to a map has no address.** It either errors at access
  time or quietly resolves to the block base, reading as a duplicate-address bug elsewhere.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the classification names **one** owner. "Could be either" means step 4 was not finished.
- every number (reset value, offset, size, lsb, policy) is quoted with a file path and line number.
- a reset-value finding shows **three** values from three sources — spec, generated model, design.
- an access-policy finding quotes the policy string exactly as the model spells it.
- nothing the step 5 table calls correct behaviour has been filed as a bug.

A wrong answer typically declares "the register model is wrong" without naming a field; reports a
W1C, RC or WO field working exactly as specified as a mismatch; blames the RTL for a reset mismatch
that was really an uninitialised mirror; or explains a front-door versus back-door gap by
clock-domain lag without first checking that the hdl path resolves at all.

## Done when

You can name the symptom class, the single field or map entry that produces it, and the one person
who fixes it.
