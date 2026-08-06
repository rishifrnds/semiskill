---
name: dv-csr-warl-access-audit
description: Audit a core's machine-readable control-register description against the architecture rules and the RTL — reset values, WARL and WLRL legalisation, privilege and configuration gating, read and write side effects — then emit the negative-access test matrix. Use when a configuration parameter changes and nobody can say which control-register fields changed their legal values, when a test writes an illegal value and you cannot say what should have happened, when a register reads back a value nobody wrote, when a supervisor-mode access traps and you cannot say whether it should have, or when someone asks for the negative control-register tests before sign-off.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Control-Register Field-Behaviour Audit and Negative-Access Test Matrix
  semiskill-function: design-verification
  semiskill-role: processor-ip-dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-04-09
  semiskill-tags: csr, control-registers, warl, wlrl, privilege, negative-testing, reset-values, processor-ip
---

# Control-Register Field-Behaviour Audit and Negative-Access Test Matrix

A core's control registers are described three times — in the architecture rules, in the
machine-readable description the RTL and the documentation are generated from, and in the RTL that
actually legalises writes — and the three drift apart quietly, because the positive tests only ever
write legal values into unlocked registers at the highest privilege and everything passes. The
expensive failures live in the negative half: an illegal write that should have been legalised and
was stored, a locked field that accepted a write, an access from a lower privilege that did not trap.
This procedure cross-checks the three sources for one bounded set of registers and turns the result
into **a negative-access test matrix in which every expected outcome names the authority behind it**.

**Which architecture this is written against, stated once so you can check it.** The shape of the
audit — classify, then compare, then name an authority — is architecture-neutral. Several *default*
expectations below are not: the write-any-read-legal and write-legal-read-legal disciplines, the
privilege and writability bits carried in the register number, the register-wide legalisation of the
address-translation register, the memory-protection lock that also freezes a neighbour, and the
second exception kind under virtualisation are **RISC-V privileged** rules, the last three needing
specific extensions. Each is marked `†` wherever it appears. If the **Architecture baseline** slot
names a different architecture — or the same one without those extensions — every `†` row is
`unspecified` for you until the architect supplies the equivalent rule. The audit still works; you
write those rows instead of inheriting them.

## When to use something else

- A control-register test **failed in simulation** and you have a log — start at
  `dv-sim-log-first-error` to get the true first error and a signature, then come back here with the
  register name to decide whether the behaviour was actually wrong.
- The **UVM register model** cannot reach the register — the adapter, predictor, map or back-door
  path is the suspect — that is `dv-ral-bringup`. It asks whether the model reaches the register
  correctly; this skill asks whether the description describes the right register.
- A whole regression is red: `dv-regression-triage-routing` first.
- The generated register files will not compile: `dv-build-filelist-hygiene`.
- You do not yet know where any of these files live: `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| CSR description source | [[FILL: the format and repository path of the machine-readable control-register description our core is generated and documented from, and whether it is a file Read can open]] | core architect |
| Architecture baseline | [[FILL: which instruction-set architecture family and privileged-specification version this core claims, which extensions it claims — in particular whether the hypervisor and physical-memory-protection extensions the `†` rows assume are present — and where the readable copy of that claim lives: a release note, not the specification itself]] | core architect |
| Configuration parameters | [[FILL: the build-time parameters that change which control registers exist or which values are legal, and the file they are set in]] | core integration owner |
| RTL CSR block | [[FILL: which RTL files implement control-register address decode, write legalisation and read multiplexing for this core]] | RTL designer |
| Lock and sticky markers | [[FILL: how our description marks a field that becomes read-only until reset once set, and what the RTL calls that condition]] | RTL designer |
| Gating conditions | [[FILL: the names our description and RTL use for state that gates an access — privilege level, enable bits, extension-present bits, debug mode, virtualisation state]] | core architect |
| Alias and view groups | [[FILL: which control-register addresses in our core are restricted views or subfield windows onto one piece of storage]] | core architect |
| Trap observation | [[FILL: how our tests observe that an access trapped — the handler hook, the value written to the signature, or the line the test prints]] | verification lead |
| Test matrix destination | [[FILL: where the negative-access matrix is recorded, and the columns our test plan requires]] | verification lead |

Every row above is spent: CSR description source in step 1; Configuration parameters in steps 2 and
5; Architecture baseline in steps 3, 4, 5 and again in step 7, where it decides whether the `†` rows
are inherited or written from scratch; RTL CSR block in steps 3 to 6; Lock and sticky markers in
step 4; Gating conditions in step 5; Alias and view groups in step 6; Trap observation and Test
matrix destination in step 7.

**Two pack-wide facts sit next to these and are read from `_shared/team-profile.md`, not re-asked.**
Its **Sign-off** row says who accepts this matrix as evidence — step 8 addresses the handoff to that
person. Its **Register model source** row is *not* the same fact as the CSR description source above
and must not be copied across: that row records what the UVM register model is generated from, which
is a verification artifact, while this slot records the architectural description the core's decode
and its documentation are built from. In many cores one file feeds both. In many others it does not,
and assuming it does sends the whole audit at the wrong file. Ask which, and write down the answer.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented legal-value set or
gating condition produces a matrix of confident, wrong expectations, and every test written from it
then has to be unpicked.

## Retrieval budget — read this before opening anything

A description covering a few hundred registers and an RTL control-register block are both far too
large to read, and the block's write-legalisation logic is usually one enormous case statement. Work
in this order and stop when the budget is spent, not when the questions run out.

1. **Grep and Read work on files on disk.** The architecture specification is almost always a
   document Read cannot open, and the description may be a spreadsheet. Anything that is not a
   readable file becomes a handoff in step 1, and every finding resting on it is marked provisional.
2. **Two Glob calls** to locate the two readable sources — the description and the RTL block. Never
   open either with **Read** first.
3. **An audit set of at most eight registers** (step 2), and **two Grep calls per register in that
   set** — one in the description, one in the RTL block — spent once in step 3 and **reused** by
   steps 4, 5 and 6. That is at most sixteen.
4. **Four further named Greps, and no others**: one in step 2 for the changed configuration
   parameter, one in step 4 for the lock and sticky markers, one in step 5 for the gating conditions,
   one in step 6 for the alias and view groups. Each is a single sweep for the whole audit set, not
   one per register.
5. **Six windowed Reads of about 60 lines** in total: one on the description's header in step 1, and
   at most five across steps 3 to 6, spent only where two sources actually disagree.
6. If a **Grep** returns more than about 200 hits, the register name is a substring of something
   common — anchor it the way the description spells it and search again inside the same allowance.
7. **Stopping rule.** If a register's two Greps and the windows already open do not settle a row,
   write `?` in that cell and move on. Do not open a seventh window, and never infer a legal-value
   set from a similarly named register. If the budget runs out before the audit set is finished,
   stop and say so.
8. **State your own coverage.** The matrix and the block in step 8 both carry `n of m registers
   audited` and which sources were readable. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Put the three sources on disk, and name the one you cannot open

Use **Glob** twice — once for the path in the **CSR description source** slot, once for the files in
the **RTL CSR block** slot. Then spend the first **Read** window on the description's header: the
generator stamp, the source revision, and the configuration it was generated for. Record all three
verbatim. A description generated for a different configuration than the RTL you are about to read is
the finding, and nothing below it is worth doing until that is resolved.

The architecture rules are the third source and are usually a document **Read** cannot open. Do not
paraphrase them from memory. **Ask the core architect for the rule text and for the clause it comes
from, record who supplied it and when**, and mark every row resting on it provisional. The
**Architecture baseline** slot exists so the readable part — which specification version and which
extensions this core claims — comes from a release note rather than from an assumption.

### 2. Choose the audit set — you cannot audit every control register

A core has hundreds and this budget covers eight. There are exactly three honest ways in:

- **A configuration parameter changed.** One **Grep** of the description for the parameter name from
  the **Configuration parameters** slot. The registers whose existence or legal-value set mentions it
  are the audit set. This is the highest-value entry point, because a parameter change silently
  re-legalises fields and no positive test notices.
- **A named register.** A review question, a failing test or a customer question named one. Use it,
  plus anything the **Alias and view groups** slot puts in the same group.
- **An area request.** Sign-off asks for the negative tests on one area. Take the registers the
  request names.

If none of the three names a register, **stop and ask which registers matter**. Sweeping the
description to rank it is not affordable here and produces a ranking nobody asked for.

Within the set, order by blast radius: registers that gate other registers first — extension-present
bits, enables, locks — then those whose legal set moved with the parameter, then the rest.

### 3. Reset values — classify each one before comparing anything

For each register in the set, spend its **two Grep calls**: one in the description for the register
name as the description spells it, one in the **RTL CSR block** for the same name, which lands on the
reset assignment and usually on the write-legalisation arm as well. Keep both hit lists — steps 4, 5
and 6 reuse them and are not allowed to Grep again.

Then classify every field's reset value into one of three, and only then compare:

- **architecture-mandated** — the rules fix the value after reset. All three sources must agree; a
  disagreement is a real finding and the architecture arbitrates.
- **implementation-documented** — the rules leave it open and the release note or the description
  records the choice. Compare description against RTL only. Quoting the architecture here is how a
  correct implementation gets reported as a bug.
- **undefined at reset** — nothing fixes it. There is no correct value, so there is no check. Say so
  explicitly and make sure the test plan does not carry one.

A field with **no** reset value in the description is not a field that resets to zero. It is a field
whose reset value was never stated, and RTL that happens to clear its flops will pass a zero check
for the wrong reason until the day someone re-times the reset.

### 4. Field legalisation — write-any, write-legal, and the register-wide case

Work from the hits already collected. One new **Grep**: the **Lock and sticky markers** slot, one
sweep across the description and the RTL block for the whole set. Classify each writable field:

- **read-only** — writes are ignored, or the address itself is read-only, which step 5 settles.
- **write-any-read-legal (WARL)** `†` — any value may be written and the read-back must be a legal one.
  Extract two things: the legal set, which often depends on a configuration parameter, and what this
  implementation does with an illegal write. **The architecture fixes only the first.** It does not
  promise the field keeps its previous value, and it does not promise the same illegal write yields
  the same legal value on a different configuration. If the description or the release note does not
  document the implementation's choice, that row's authority is `unspecified` and the row is dropped.
- **write-legal-read-legal (WLRL)** `†` — software is required to write legal values, an illegal write
  leaves an unspecified value behind, and a trap is permitted but not required. There is nothing here
  the architecture lets you assert.
- **register-wide legalisation** — some registers legalise as a whole rather than field by field.
  `†` In RISC-V, writing an unsupported translation mode to the supervisor address-translation
  register leaves the *entire* register unmodified, neighbouring fields included. Look for that
  wording in your own description before assuming it; a per-field model gets every one of those rows
  wrong, and a register-wide model applied where the architecture is per-field gets them wrong the
  other way.
- **lock or sticky** — the field becomes read-only until the next reset once set.

Spend a **Read** window on the RTL write-legalisation arm only for the registers where description
and RTL disagree, and at most two of them.

### 5. Access gating — the address, the privilege, and the configuration

Three independent gates. A matrix row that does not say which one it is testing cannot be triaged
when it fails.

- **Address encoding.** `†` In RISC-V the register number itself carries both whether the register
  is writable at all and the lowest privilege that may reach it, in two fixed two-bit sub-fields of
  the twelve-bit address. Ask the architect to confirm your architecture encodes access that way
  before relying on it. Where it does, compare the address in the description against the access
  policy in the description: a writable policy at a read-only address is a description bug you can
  find with no RTL at all, and it is worth checking first because it costs nothing.
  **When that comparison is what disagrees, step 8 records `finding : address-encoding`** — the
  register number and the register's own declared policy contradict each other, and the fix is in the
  description, not in run-time state. Reserve `gating` for the two bullets below, where the
  description and the RTL disagree about *state* — a privilege level or an enable bit — that has to
  hold at the moment of the access.
- **Privilege.** An access from below the encoded level raises an illegal-instruction trap. `†` With
  the RISC-V hypervisor extension and virtualisation active, some denied accesses raise a
  virtual-instruction exception instead — which of the two applies depends on the register, so this
  is a per-register ruling from the architect and not one blanket answer. Either way the expected
  outcome carries a virtualisation-state precondition rather than a single trap kind.
- **Configuration.** An enable bit, an extension-present bit, a counter-enable bit, or debug mode can
  make an otherwise-legal access trap. One **Grep** for the names in the **Gating conditions** slot,
  one sweep for the whole set, then record for each register which gates it sits behind and which
  **Configuration parameters** value decides whether the register exists at all.

Settle one more thing here, in the same windows: an **unimplemented** register may be architecturally
permitted to read as zero, or required to trap. The description says which; the RTL implements one of
them. That cross-check is a common description-versus-RTL disagreement and no positive test finds it.

### 6. Side effects and aliasing — what a per-register model cannot see

One **Grep** for the **Alias and view groups** names, one sweep for the whole set.

- **Aliases and restricted views.** One piece of storage behind several addresses — a subfield window
  onto a larger control register, or a lower-privilege view exposing a subset with narrower write
  permissions. Two independent reset values in the description for one storage is a description bug
  that reads as an RTL bug. Every alias group needs a write through each address and a read back
  through every other one.
- **Read side effects.** A read that clears, or that returns a value the next read will not. `†` In
  RISC-V only the *swap* form skips its read, and only when its destination is the zero register; the
  set and clear forms always read and always raise the read side effect whatever their destination
  is. Get that pairing backwards and a test written to prove there is *no* clear-on-read reports a
  false negative on one that works. The Gotchas spell out both halves — check a row against them
  before you write the instruction form into the matrix.
- **Write side effects.** A write that changes address translation, stops counters, or arms a
  trap-on-access bit that makes the *next* row's access trap. Order the matrix so a side-effecting
  row comes after every row it would perturb, and say in the row that the ordering is load-bearing.

### 7. Draft the negative-access test matrix

One row per (field, attempt). Emit it in the columns the **Test matrix destination** slot records; if
that slot is unfilled, emit these and ask where it goes rather than picking a location.

| id | register.field | attempt | precondition | expected | authority |
|---|---|---|---|---|---|
| N1 | reg.field | write an illegal value | none | read-back is a legal value; which one is not fixed | architecture † |
| N2 | reg.field | write an illegal value | none | read-back keeps the previous legal value | implementation |
| N3 | reg | write via a form that really writes | address is read-only | illegal-instruction trap | architecture † |
| N4 | reg | read | privilege below the encoded level | illegal-instruction trap | architecture † |
| N5 | reg | read | same, virtualisation active, architect confirms this register | virtual-instruction exception | architecture † |
| N6 | reg.field | write | the gating enable is clear | illegal-instruction trap | architecture |
| N7 | reg.field | write | the lock is set — this row goes last | write ignored, read-back unchanged | architecture † |
| N8 | reg | write an unsupported translation mode plus a new field value | none | the whole register is unmodified | architecture † |
| N9 | reg.alias | write here, read the other address | none | both addresses show the written value | architecture |
| N10 | reg | set-form write with the zero register as source | none | no write and no write side effect | architecture † |
| N11 | reg | swap-form access with the zero register as destination | the register has a clear-on-read field | the field is *not* cleared | architecture † |

**`†` means the row is inherited from the RISC-V privileged rules named in the intro and in the
Gotchas, and N5, N7 and N8 additionally need the extension that defines them.** Before drafting,
check the row against what the **Architecture baseline** slot actually says this core claims. Where
it does not match, do not silently keep the row: set its authority to `unspecified`, ask the
architect for the equivalent rule, and drop it if none exists. A `†` row kept because it looked
authoritative is the failure mode this notation exists to stop.

Three rules make this matrix worth writing. **Every row states its authority**, and `unspecified`
rows are dropped rather than guessed — a row asserting behaviour nothing defines will be argued about
for a week and then deleted. **The expected column names an observable**, taken from the **Trap
observation** slot, not "it should trap": a trap nobody records is indistinguishable from a pass.
And **rows that change state carry their ordering constraint in the row**, because a lock set in row
7 silently invalidates rows 8 onward.

Then **ask the engineer to run the resulting tests and give you the path to the log**. The matrix is
a proposal about behaviour, not evidence about this core; nothing here has been observed running. A
failing row comes back through `dv-sim-log-first-error`.

### 8. Record the finding and hand it over

```
register  : <the name exactly as the description spells it, and its address>
sources   : <description path and line; RTL path and line; architecture claim and who supplied it>
class     : design | infrastructure | unknown
finding   : reset-value | legalisation | gating | side-effect | alias | address-encoding | none
disagree  : <which two of the three sources disagree, and what each one says, verbatim>
gating    : <the state that must hold for the access to succeed, named from the gating slot>
matrix    : <n rows drafted, of which k dropped as unspecified>
coverage  : <n of m registers in the audit set; which sources were readable and which came from a
             person; how many windows were spent>
notes     : <anything the next person would otherwise rediscover>
```

`class` carries the same three values `dv-sim-log-first-error` and `dv-ral-bringup` use, so a row
routed either way keeps its vocabulary: `design` when the disagreement is inside the core —
description or RTL — `infrastructure` when it is in the flow that generates or delivers them, and
`unknown` while a third source is still unread. Leave a field empty rather than filling it
plausibly, and take the person the block goes to from the profile's **Sign-off** row.

## Gotchas

- **A read-only register can be read-only by address, not by policy.** `†` RISC-V puts both
  writability and the lowest privilege that may reach a register into the register number itself, so
  the address is the authority and the description's access-policy column is a restatement of it. A
  description that never checks the two against each other will happily describe a writable register
  at a read-only address; the RTL, which decodes the address, will disagree — and the positive tests,
  which never write it from a lower privilege, will not notice. Where access is not encoded in the
  address this check evaporates, which is why **Architecture baseline** is answered before step 5.
- **"Writes zero" and "does not write" are different instructions.** `†` In RISC-V, a set or clear
  form whose *source* is the zero register performs no write and raises no write side effect, while
  the same instruction with an ordinary register that happens to hold zero does write. The decision
  is in the encoding, not in the value. A row meant to prove a register rejects writes must use a
  form that really writes, or it passes for the wrong reason forever.
- **The read-side mirror of that rule belongs to a different instruction — get this the right way
  round.** `†` It is the *swap* form, with the zero register as its **destination**, that performs no
  read and raises no read side effect; that is how the plain write pseudo-instruction leaves a
  clear-on-read field alone. The set and clear forms always read and always raise the read side
  effect, whatever their destination — for those two it is the *source* being the zero register that
  suppresses the write, never the destination that suppresses the read. Reading it the other way
  round fails silently: a test that clears with the zero register as destination, expecting no read,
  still fires the clear-on-read and reports a false negative on a side effect that is working.
- **Write-any-read-legal does not promise which legal value comes back.** The guarantee is that the
  read-back is legal — not that it is the previous value, and not that the same illegal write behaves
  identically on the next configuration. A row asserting "the field keeps its old value" is asserting
  an implementation property; label it as one or it becomes wrong the day another configuration ships.
- **Write-legal-read-legal is not testable from the architecture alone.** Nothing defines what an
  illegal write leaves behind and nothing requires a trap. The honest matrix cell is no row, not a
  guessed expectation, and certainly not the write-any-read-legal expectation copied across.
- **Some legalisation is register-wide.** `†` In RISC-V, writing an unsupported translation mode to
  the supervisor address-translation register leaves the whole register unmodified, neighbouring
  fields included. The test that catches a per-field model is the one that writes an unsupported mode
  *together with* a new value in another field and then reads both back. Confirm the same wording
  exists in your own description before writing that row — the register-wide rule is stated per
  register, not as a general property of control registers.
- **Aliased registers are one piece of state behind several addresses.** Rounding-mode and
  exception-flag windows onto a floating-point control register, and lower-privilege restricted views
  of machine-level registers, are the same storage. Two independent reset values in the description
  for one storage is a description bug that reads for days as an RTL bug.
- **A lock bit makes test order load-bearing, and it can reach past the register it lives in.** `†`
  RISC-V physical-memory-protection configuration is the case to know: setting the lock bit makes
  that entry's configuration and address read-only until reset, and where the entry uses the
  top-of-range addressing mode the lock also freezes the address register of the entry below it —
  the half people miss. Any row that sets a lock belongs last in its sequence, or every later row
  fails for a reason unrelated to the row. Whether *your* core has that extension is an
  **Architecture baseline** question; the ordering discipline applies to any sticky bit regardless.
- **The same denied access can raise two different exception kinds.** `†` With the RISC-V hypervisor
  extension and virtualisation active, some accesses that would raise illegal-instruction outside
  raise a virtual-instruction exception instead. It is not a blanket substitution — it depends on the
  register — so the architect rules per register. Either way, a matrix with one expected column and
  no virtualisation-state precondition looks wrong on every one of those rows the day the extension
  is enabled.
- **An unimplemented register is not required to trap the way you expect.** Some are permitted to
  read as zero; some must trap. The description usually states one and the RTL usually implements
  one, and they are not always the same one.

## Human verification — what a wrong answer looks like

Before writing a single test from this matrix, check:

- every **expected** cell traces to an **authority**, and no cell says `unspecified` — those rows
  should have been dropped, not softened into a guess.
- every `†` row was checked against what the **Architecture baseline** slot says this core claims,
  and any `†` row whose architecture or extension this core does not claim was re-sourced from the
  architect or dropped. A matrix that still carries `†` rows for an extension the core does not
  implement is asserting rules from somebody else's specification.
- every architecture claim is either quoted from a readable file with a path and line, or attributed
  to the person who supplied it and marked provisional. A rule quoted from memory is the most
  expensive thing on this page.
- reset-value rows were **classified before they were compared** — nothing undefined at reset is
  being checked against zero, and nothing implementation-documented is being arbitrated by the
  architecture.
- every alias group was tested through **every** address in the group, not just the one that failed.
- rows that set a lock, change translation, or clear on read carry their ordering constraint, and no
  row that must be last sits in the middle.
- the coverage line gives `n of m` for the audit set and says which of the three sources were
  actually readable.

A wrong answer typically asserts that an illegal write leaves the previous value — an implementation
property presented as an architectural one; files a correctly legalised field as an RTL bug; writes a
negative row for a write-legal-read-legal field that nothing defines; proves a register is read-only
using an instruction form that never wrote to it; or clears a register with the zero register as
destination and concludes from the surviving value that there is no clear-on-read, when the read
fired and the field really did clear.

## Done when

The matrix names one authority per row, the coverage line says how much of the audit set it rests on,
and the person in the profile's Sign-off row can accept or reject each row without asking you what a
cell meant.
