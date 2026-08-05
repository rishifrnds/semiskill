---
name: dv-ral-bringup
description: Diagnose a UVM register-model bring-up failure with a fixed root-cause tree keyed on the symptom, and route it to one owner with the evidence line behind it. Use when the hardware reset check fails, when a bit-bash or register access test mismatches, when a register reads back the wrong value or lands at the wrong address, when front door and back door disagree, or when an adapter or predictor someone else already wrote is the suspect. Reads source files and saved logs only.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Register-Failure Decision Tree (RAL Bring-Up)
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-06-18
  semiskill-tags: ral, registers, uvm, bring-up, adapter, predictor, debug
---

# Register-Failure Decision Tree (RAL Bring-Up)

Register bring-up fails in about a dozen distinct ways, each with a short list of causes. The
expensive part is never the fix — it is spending a day working out which of the dozen you are in,
because every one presents as the same sentence in the log: a mismatch at some address. This turns
that day into a lookup, ending in a **classification, the evidence line behind it, and one owner** —
the register spec, the RTL, or the testbench integration.

**What this does not do.** It reads source files and saved logs. It does not write an adapter, a
predictor or a map, it cannot start a simulation, and it cannot open a waveform. Every step that
needs one of those ends in a handoff to a named human, and says so.

**When not to use this.** For a single failing simulation log of any kind, start with
`dv-sim-log-first-error`. For a whole night of failures to sort and route, use
`dv-regression-triage-routing`. For shrinking a failure you have already signed, use
`dv-minimal-reproducer`. Come here once the failure is known to be a register access.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Source of truth | [[FILL: the format and repository path our register description lives in — IP-XACT, SystemRDL, or a spreadsheet]] | register owner |
| Generator | [[FILL: the generator and version that emits both the RTL register block and the UVM register model, and whether it flags overlapping addresses — at what severity, or not at all]] | DV infra |
| Model location | [[FILL: where the generated register model files land in our tree]] | your mentor |
| Bus agent and adapter | [[FILL: which bus agent and which adapter class this block uses]] | block DV owner |
| Reset convention | [[FILL: which reset this register block uses, and how long the testbench waits before the reset check]] | RTL designer |
| Back-door paths | [[FILL: whether hdl paths are set for this block, and the root path they hang from]] | DV infra |
| Exclusions | [[FILL: where our waiver list lives and how we record a deliberately excluded register or field]] | DV lead |
| Log location | [[FILL: where the bring-up log is saved so it can be read from disk]] | your mentor |
| Mismatch markers | [[FILL: the strings our register sequences print on a mismatch, beyond UVM_ERROR and UVM_FATAL]] | DV lead |
| Pass marker | [[FILL: the string a clean bring-up run prints at the end]] | DV lead |

Log location and Pass marker are pack-wide facts and live in `_shared/team-profile.md` — read them
from there. **Mismatch markers is narrower than the profile's Fatal markers**: it is whatever the
register sequences print on a comparison mismatch, which may or may not be what the general flow
prints on a failure. If they differ, record both; if you are unsure, ask rather than assuming they
are the same string.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented register path,
generator name or reset convention gives a confidently wrong answer, and unpicking that costs more
than no answer.

## Retrieval budget — read this before opening anything

A generated register model runs to tens of thousands of machine-written lines; reading it end to end
teaches nothing and burns the context. Work in this order, stopping once the classification settles:

1. **Grep and Read work on files on disk.** If the only copy of the log or the register description
   is text in a chat message, save it to a file first and point at that path — there is nothing to
   Grep otherwise.
2. **Glob** first for the generated model and the environment file that builds the map, adapter and
   predictor. Never open a generated file with **Read** as the first move.
3. **Grep** for the exact register or field name to get line numbers — one symptom, one register.
   More than about 100 hits means the name is a substring of something common; anchor it (leading
   `"` or trailing `,`) before reading anything.
4. **Read** bounded windows only — about 40 lines at the declaration, about 40 at the map entry, and
   at most one window of about 80 lines in the log. Four windowed **Read** calls is the whole budget,
   and every later step reuses a window rather than opening a new one.
5. Stopping rule: after four windowed **Read** calls with no settled classification, stop and report
   what is known, the one thing you still need, and how much of the failure list you got through
   (step 9). Past that point answers get invented.

## Procedure

### 1. Name the source of truth before reading the model

The register model is generated, and so, usually, is the RTL register block. From one source at one
revision they cannot disagree, so a real mismatch means different revisions, a hand edit after
generation, or RTL that ignores the generated block. **Grep** both headers for a version, date or
source stamp, record them verbatim, and if they differ stop — that is the finding.

If the source of truth is a format **Read** cannot open — a spreadsheet, a PDF, a wiki page — say so
before going further and treat every spec number as a handoff rather than as evidence: ask the
register owner for the value, record who supplied it, and mark any finding resting on it
*provisional*. A number with no file and no line must never be written up as though it had one.

### 2. Locate the register, its map entry, and its fields

Three **Grep** calls: the register class or type name, for its declaration; `add_reg` with the
register name, for its offset **and its rights** in the map; `configure` inside that register, for
each field's size, lsb, access policy, volatility and reset value. Then two bounded **Read** windows
— the fields, and the map construction (`create_map`, `add_submap`, `set_base_addr`).

Keep the map-entry rights next to the field's declared policy. Step 5 needs both, because the map
entry changes what the field's access actually is on that path.

### 3. Confirm the bring-up order, and that it was followed

The standard order is not arbitrary — each stage assumes the previous one passed.

1. **Hardware reset check.** A front-door read of every register right after reset, compared against
   the model's reset values. First, because with no prior state it can exercise three things at once:
   that the addresses decode, that the adapter moves data the right way, and that the reset values
   agree. It only *proves* all three if at least one register checked has a non-zero reset value —
   see the first row of step 4 for what happens when none does.
2. **Bit-bash.** Inverts each bit of each field in turn, starting from the field's current value, so
   every bit is driven both 1 to 0 and 0 to 1, and compares each read-back against what the field's
   *effective* access predicts. That bidirectionality is the whole point: it is what lets the check
   tell `W1C` from `W0C` from `W1T`. Second, because it assumes addressing is proven — so its
   failures point at policy, width or lsb, not at the map.
3. **Access test.** Writes front door and reads back door, then the reverse. Last, because it needs
   both doors working and every hdl path resolved; earlier it yields addressing bugs in a back-door
   costume. Run the register library's hdl-path check sequence ahead of it —
   `uvm_reg_mem_hdl_paths_seq` in the UVM versions that ship it — so that an unresolved path is
   reported as an unresolved path instead of arriving later as a data mismatch. A path that resolves
   to the *wrong* signal is the case no path checker catches; only a value comparison finds it.

To get this evidence, **ask the engineer to run the bring-up test with the register sequences enabled
and save the log where it can be read from disk**. The agent cannot start a simulation and must not
invent what one would have printed.

Two rows of step 4 need more than a log. A clock-domain question needs a waveform or a timed
back-door dump, and the agent cannot open either — ask a human to read it, and record in the report
that the answer came from a person rather than from a file.

### 4. Classify the symptom

The `Evidence` column says what each row can actually be settled from. `source` is the model and
environment files; `log` is the saved bring-up log; `log + wave` means the agent can narrow it but a
human has to finish it, per the handoff in step 3.

| Symptom | Evidence | Check first | Usual cause |
|---|---|---|---|
| Everything passes on a block never brought up before | log + source | whether any register checked has a **non-zero** reset value | nothing is connected: an undecoded bus returns zero, and every all-zero reset value "matched" |
| Every register mismatches, expected value zero | log + source | whether the model's reset was applied in the reset phase | the mirror was never initialised |
| Every register mismatches, every read the same value | log + source | the adapter's bus-to-register conversion and its status | read data never reaches the model |
| One register's reset value is wrong | log + source | the value in the spec, the value in the model, and the value the log shows was read | spec and RTL built from different revisions |
| Only the first few registers fail the reset check | log | when the check began relative to reset deassertion | the sequence started before reset propagated |
| Write then read returns the old value | source | the field's declared policy **and** the rights on the map entry it was reached through | write-once or RO — declared, or imposed by the map entry |
| Write then read returns zero | source | clear-on-write or clear-on-read semantics | a W1C, WC or RC field behaving correctly |
| The value lands in the wrong bit position | source | the field's size and lsb | width or lsb mismatch |
| The whole value reads back byte-reversed | source | the adapter's byte ordering, then the bus agent's | adapter or agent byte order — **not** map endianness (step 6) |
| The access lands at the wrong address | source | map base, offset, bus width, byte addressing | word offsets where byte addresses are expected |
| A read returns a different register's contents | source | two entries at one offset, or an overlapping submap | a shadowed address |
| Front door and back door disagree | log + wave | whether the hdl path resolves at all — that part is in source — and only then the timing | wrong path, or clock-domain lag |
| A neighbouring field changes when one field is written | source | byte-enable support and partial-write behaviour | the field write wrote back the whole register |
| A status field mismatches only sometimes | log + wave | whether the field is declared volatile | hardware updates it between write and check |

### 5. Access policy — the part that has to be exactly right

Most "the model is wrong" reports are a correct model describing a policy the reader misremembered.

| Policy | Effect of a write | Effect of a read |
|---|---|---|
| RW | stores the written value | returns the stored value, no side effect |
| RO | no effect | returns the hardware value, no side effect |
| WO | stores the written value | undefined; do not compare it against anything |
| RC | no effect | returns the value, then clears all bits |
| RS | no effect | returns the value, then sets all bits |
| WC | any write clears all bits | no effect |
| WS | any write sets all bits | no effect |
| W1C | a 1 clears that bit; a 0 leaves it | no effect |
| W0C | a 0 clears that bit; a 1 leaves it | no effect |
| W1S | a 1 sets that bit; a 0 leaves it | no effect |
| W0S | a 0 sets that bit; a 1 leaves it | no effect |
| W1T | a 1 toggles that bit; a 0 leaves it | no effect |
| W0T | a 0 toggles that bit; a 1 leaves it | no effect |
| W1 | stores on the first write after reset only; later writes ignored | returns the stored value |
| WO1 | stores on the first write after reset only; later writes ignored | undefined; do not compare it |
| NOACCESS | no effect | no effect — the field is present and mapped, it simply neither reads nor writes |

**This table is not the complete list, and must not be read as one.** UVM defines roughly two dozen
policy strings. The rest compose the same two columns — a leading `W`, `W1` or `W0` clause says what
a write does, a trailing `RC` or `RS` clause says what a read does afterwards, so `WRC` stores on
write and clears on read, `WCRS` clears on write and sets on read, `W1CRS` clears the written ones
and sets all bits on read — but the composite family is larger than those examples, and there are
write-only composites too. If the string in the model is not in this table, look it up in the
register-field class the model was generated against; do not reason from the nearest similar name.
`WO1` is the trap: it is not `W1`. Both accept only the first write, and `WO1` also makes the read
undefined, so comparing its read-back is meaningless.

**Declared access is not always effective access.** The field's declared policy is combined with the
rights of the map entry it is reached through: a field declared `RW`, reached through an entry added
with `RO` rights, is read-only on that path, and the sequences check against that effective access,
not against the declared string. So quote two things, never one — the policy string exactly as the
model spells it (`W1C`) and the rights on the `add_reg` line from step 2. A report quoting only the
declared string sends a map-rights bug to the register owner, who looks at the spec, sees `RW`, and
sends it straight back.

The built-in bit-bash sequence derives its expected read-back from that effective access, and it
skips some policies outright rather than bashing them. A policy wrong *in the model* therefore makes
the sequence complain about correct RTL.

Keep the model's operations straight too: `get`/`set` touch only the desired value and make no bus
traffic; `read`/`write` make front-door traffic and update the mirror; `peek`/`poke` are back-door
and need an hdl path; `mirror` reads and optionally compares; `update` writes only where desired and
mirrored differ; `predict` forces the mirror with no traffic. A report saying a register "was
written" without saying which of these was used is not yet a report.

**Two mechanisms silently exclude a register or field from a check, and neither prints anything.**
The first: a field declared with no reset value is skipped by the reset check. The second: the
built-in register sequences look up a resource keyed on the register's or block's full name before
touching it — the `REG::` namespace, with `NO_REG_TESTS` and per-sequence variants of it — and skip
anything marked. Confirm the exact resource names against the register-sequence source in the UVM
version we compile against, and confirm our own bookkeeping in the Exclusions slot. "The check
passed" and "the check never ran" produce the identical log line: nothing.

### 6. Address, width and lsb

Use the map-construction window **already opened in step 2** — do not reopen it, the budget does not
stretch — and check, in order: base address, bus width in bytes, whether byte addressing is set, and
this register's offset. Offsets are in the map's own addressing units, so a register list written in
word units against a byte-addressed map puts every register at a fraction of its address — a uniform
stride error across the block, not one bad register. For a sub-block, check the offset its map was
added at: a wrong submap offset moves a whole block and is indistinguishable from an interconnect
decode bug. Then compare each field's size and lsb — shifted by a constant is an lsb error, truncated
is a size error.

**A byte-reversed value is not a map-endianness setting.** Map endianness orders the *bus words* of a
register wider than one bus word. A 32-bit register on a 32-bit bus occupies a single bus word, so
map endianness has nothing to order and cannot reverse its bytes; that is the adapter or the bus
agent laying the bytes down the other way round. Filing a byte reversal against `create_map` costs an
afternoon and ends with the map being correct.

### 7. Front door versus back door

Some disagreements are correct and must not be filed as bugs. A back-door access has **no read side
effects**, so on an RC field the two doors are supposed to differ after a front-door read. On a WO
field the front-door read is meaningless while the back door returns the stored value. A captured
snapshot in the RTL — a shadow or holding register — legitimately differs from the live counter its
hdl path points at. The real bugs are a path that does not resolve, a path left on the old hierarchy
after an RTL rename, and a back-door check sampling before the value has crossed a synchroniser into
the register's clock domain. Take those in that order: the first two are visible in source, the third
is not, and needs the waveform handoff from step 3. The tell for the third is that the mismatch moves
with the check — say that rather than calling it intermittent.

### 8. Adapter and predictor

These sit between a correct model and a correct design and cause a large share of failures that look
like model bugs. The adapter converts a register operation to a bus item and back; if the reverse
conversion does not set the operation's status, every access looks failed even when the data was
right. If the driver returns read data on a separate response path, the adapter must declare that
responses are provided, or the model reads the request item and returns what was in it. Byte-enable
support is declared there too — with it off, a single-field write becomes a full-register write.

The predictor observes the bus monitor and updates the mirror from what actually happened. Use it
*or* automatic prediction inside the map, never both: two updates for one access silently corrupt any
clear-on-access field. Explicit prediction is mandatory if anything besides this sequence writes
these registers — another master, firmware, a back-door poke elsewhere. On a pipelined bus the
monitor must publish one complete item; a half-formed one makes the predictor write garbage.

### 9. Record the finding

Write the result as a failure signature following `_shared/failure-signature-schema.md` — same field
order (`phase|kind|where|what`), same normalisation rules — then fill in this block. It reuses the
field names from `dv-sim-log-first-error`'s repro block so the two read side by side; `symptom`,
`evidence`, `owner` and `coverage` are the additions this skill needs.

```
signature : phase|kind|where|what, per the shared schema
symptom   : the step 4 row, quoted
evidence  : file path and line, or log line number, for every number quoted above
class     : design | infrastructure | unknown
owner     : register spec | RTL | testbench integration
run id    : whatever identifies this run for us
log       : path, and the line range worth reading
coverage  : classified n of m reported mismatches; what the rest are and why they were not opened
notes     : anything the next person would otherwise rediscover, including any value that came from a person rather than a file
```

If a line cannot be filled from text on disk, write `?` rather than inventing it. **State the
coverage honestly.** Four windowed Reads will not classify forty mismatches: "classified 3 of 41; the
other 38 share the first one's address stride and are unexamined" is a useful report, and an unstated
shortcut is far worse than a stated one.

## Gotchas

- **The design's reset does not reset the model.** The mirror is initialised by an explicit reset
  call in the testbench; skip it and every check compares against zero, which looks exactly like an
  RTL that never resets and sends you to the wrong person.
- **An all-zero block passes the reset check with nothing connected.** If every reset value is zero
  and the bus returns zero for addresses that decode nowhere, a total decode failure is a clean pass.
  Find one register with a non-zero reset value before believing the check.
- **Automatic prediction plus an explicit predictor updates the mirror twice.** Nobody notices on RW.
  On W1C or RC the second update applies the clear again and the mirror drifts a few accesses later.
- **A field-level write is a whole-register write.** Writing one RW field of a register that also
  holds W1C bits writes those mirrored bits back and can clear live status — check byte-enable
  support before reporting that the design clears status spuriously.
- **Volatile is load-bearing, not decoration.** A hardware-updated field not declared volatile makes
  every mirror comparison a race; a field wrongly declared volatile is skipped, so real bugs pass.
- **A field with no declared reset value is skipped by the reset check**, and a resource-marked
  register is skipped by the built-in sequences entirely (step 5). An excluded item and a correct one
  produce the identical log line: nothing.
- **Register data and address widths are compile-time settings.** A register wider than the compiled
  data width truncates without complaint, and reads as an RTL bug in the upper bits.
- **A write-once, locked or enable-gated field cannot behave like RW under a bit-level test.** The
  register stopped accepting writes after the first, exactly as specified — same shape for a register
  behind a lock, and for anything gated by an enable the sequence cleared two registers earlier. What
  the sequence *does* about that varies: the built-in one carries per-policy expected values and
  skips some policies rather than bashing them, so read its handling of this policy in the version we
  compile against before filing anything against the design.
- **Whether overlapping addresses are reported at all is a property of the generator, not of UVM.**
  Fill the Generator slot before reading a quiet log as evidence of no overlap. A submap added at the
  wrong offset shadows real registers, and the trace may be one line near the start of the log, or
  nothing. A register never added to any map is a different failure: it has no map through which to
  reach it, so a front-door access errors when it is attempted. It does not silently alias to the
  block base — that mechanism is folklore, and chasing it wastes the afternoon.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- the classification names **one** owner. "Could be either" means step 4 was not finished.
- every number (reset value, offset, size, lsb, policy) is quoted with a file path and line number —
  or, where it came from something **Read** cannot open (a spreadsheet, a waveform, a person), is
  attributed to whoever supplied it and the finding is marked provisional.
- a reset-value finding shows **three** values from three sources — spec, generated model, design.
- an access-policy finding quotes the policy string exactly as the model spells it **and** the rights
  on the map entry it was reached through.
- the `coverage` line is present, and its denominator is the number of mismatches actually reported.
- nothing the step 5 table calls correct behaviour has been filed as a bug.

A wrong answer typically declares "the register model is wrong" without naming a field; reports a
W1C, RC or WO field working exactly as specified as a mismatch; blames the RTL for a reset mismatch
that was really an uninitialised mirror; calls a byte-reversed value a map-endianness bug; or
explains a front-door versus back-door gap by clock-domain lag without first checking that the hdl
path resolves at all.

## Done when

You can name the symptom class, the one field or map entry producing it, the person who fixes it,
and how much of the failure list you actually got through.
