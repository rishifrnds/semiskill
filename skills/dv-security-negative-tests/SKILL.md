---
name: dv-security-negative-tests
description: Turn a security threat model into an enumerated matrix of illegal actions that must be refused, then audit the existing tests for the vacuous pass, where a refusal and a no-op look identical. Use when verifying address-region or requester-based access control, key storage and zeroisation, device lifecycle transitions, or debug and test-port locking; when a reviewer asks how you proved an illegal access cannot happen; or when the security suite is entirely green and you do not yet trust it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Threat-Model-Driven Negative Testing for Security Features
  semiskill-function: design-verification
  semiskill-role: security-verification-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-09-14
  semiskill-tags: security, negative-testing, threat-model, access-control, lifecycle, debug-lock
---

# Threat-Model-Driven Negative Testing for Security Features

A positive test fails loudly the moment the feature breaks. A negative test — the one that proves an
illegal access is refused — fails **silently**, because a refusal and a no-op produce the same
waveform, the same log and the same green tick. A security suite that is entirely green almost always
contains at least one test whose stimulus never reached the design, and from the results alone nobody
can say which one.

This procedure does two things: it **enumerates the illegal space** from the threat model, which is
the part no amount of random stimulus will reach, and it **audits the tests that already exist for
vacuity**. The output is a negative-test matrix with a proof status and a file and line per row — not
a statement that security was tested.

## When to use something else

One security test has failed and its log is large — start with `dv-sim-log-first-error`; that is a
failure, not a coverage gap. A whole night of them needs sorting and routing — `dv-regression-triage-routing`.
The failure is a lock, status or control **register** reading back wrong — `dv-ral-bringup`, whose
access-policy table covers the write-once and read-only families a lock register is built from, and
the difference between a field's declared access and the access the map entry actually grants. A
failing security test that takes hours to reproduce — `dv-minimal-reproducer`. A checker file that
will not compile or a bind that is not in the build — `dv-build-filelist-hygiene`. New to the tree —
`dv-repo-orientation`. Proving the feature *works* for a permitted requester is a different job; this
skill enumerates only the illegal space and uses the positive tests as controls in step 5.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Threat model source | [[FILL: where our threat model and asset list live, in what format, and whether it is a file that can be read from disk]] | security architect |
| Security test location | [[FILL: where our security tests, their sequences, and any bind or checker files live in the tree]] | DV lead |
| Access control map | [[FILL: which block enforces region and requester permissions on this part, and where its permission table is written]] | design owner |
| Requester identity | [[FILL: what identifies a requester on our fabric, and which signals carry the privilege and security attributes]] | SoC integrator |
| Denial response | [[FILL: what the design drives on a refused access — the error encoding, and the exact defined read-data value]] | design owner |
| Lifecycle states | [[FILL: our device lifecycle state names in order, which transitions are legal, what authorises each one, and what the state is re-derived from after every reset]] | security architect |
| Debug and test access ports | [[FILL: every debug, trace and test access port on this part, and the signal that locks each one]] | DFT lead |
| Key storage and readers | [[FILL: where key material is held in the RTL, and which paths out of it are declared legitimate readers]] | security architect |
| Expected-error convention | [[FILL: how a negative test marks an error as expected here, and how that expectation is scoped in time and to one source]] | DV lead |

Log location, Build log location, Area to owner map and Sign-off are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than re-asking anyone.

**Denial response is narrower than the profile's Fatal markers, and the two are genuinely different
facts.** Fatal markers are what our *flow prints* when a run fails. Denial response is what the
*design drives* when it refuses an access: an encoding on the response channel and a defined value on
the read-data path. A correctly refused access inside a passing negative test prints no fatal marker
at all, so Grepping for one finds nothing and proves nothing.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented denial encoding or
lifecycle state name turns this whole matrix into a document that looks like evidence and is not.

## Retrieval budget — read this before opening anything

An SoC tree has thousands of files whose names contain the word "secure", and the address-map headers
are machine-written. Enumeration is free; opening things is what costs. Work in this order:

1. **Grep and Read work on files on disk.** A threat model in a slide deck, a spreadsheet or a wiki
   page cannot be opened at all — step 1 says what to do instead, and every row resting on it is
   marked provisional.
2. **Glob** at most three times: the Security test location tree, the Access control map RTL, and the
   bind or checker files. Steps 1 and 3 spend these.
3. **Grep** at most nine times, each anchored on a name taken from a filled slot — an asset name, a
   region name, a lock signal, a state name. Never Grep a bare word like `secure`, `lock`, `valid` or
   `check`; in this tree those return thousands of hits and settle nothing.
4. **Read** at most six windows of about 50 lines each, every one entered through a Grep hit. Never
   open a generated address-map header or a bind file with Read as the first move.
5. If a Grep returns more than about 150 hits, the anchor is too broad. Add the module or class name
   and re-Grep before reading anything.
6. Auditing one row costs roughly one Grep and one Read, so this budget settles **four to six rows**,
   not forty. Steps 6 and 7 are entered only for the rows whose asset class they cover.
7. Stopping rule: when the Reads are spent and a row is still unsettled, stop. Write that row as
   `proof : untested`, name the one thing still needed, and state the coverage. Past that point the
   answers are invented, and an invented security proof is the worst artifact in this pack.

## Procedure

### 1. Name the assets, and get the policy onto disk

**Glob** for the Threat model source. Three outcomes, and they are not equivalent:

- **A file that can be read.** Read one window and list the assets verbatim, in the words the model
  uses. Those words become the `asset` field of every row, so that a reviewer holding the threat
  model can line the two up without translating.
- **A format Read cannot open** — a deck, a spreadsheet, a page. Say so before going further. Ask the
  security architect for the asset list and the policy per asset, record who supplied each answer,
  and mark every row resting on it *provisional*. A policy with no file and no line must never be
  written up as though it had one.
- **No threat model at all.** Stop and say that. Enumerating illegal actions from the RTL is
  enumerating what the design happens to refuse, which is a description, not a requirement, and it
  can never find a missing control.

For each asset record four things: what it is, who may reach it, in which lifecycle state, and
through which path. Anything you cannot state in that shape is not yet an asset — it is a worry.

### 2. Enumerate the illegal space

This step costs no tool calls and is the whole value of the skill. A row is only a row when you can
say what "refused" looks like **observably**. "The key must not leak" is not a row. "A read of the
key-storage aperture by a requester outside the declared reader list, in a state after provisioning,
must return the defined denial value with an error response and must not advance the storage read
pointer" is a row.

Generate rows by crossing the axes below. The row people forget is almost never the obvious one.

- **Path** — every port that can reach the asset, from the Access control map: the main fabric, any
  second master, DMA, the debug access port, the test access port. A control that is enforced on one
  port and absent on another is the single most common real finding.
- **Requester** — each identity in the Requester identity slot; then the identities *not* in the
  permission table at all; then the reserved and unused encodings. Also every combination of the
  privilege and security attribute signals your bus carries, not only the ones software uses today.
- **Operation** — read, write, and where the bus distinguishes it, instruction fetch. Then the
  modifiers: unaligned, narrow, wrapping and exclusive or atomic accesses.
- **Address** — inside the region, at the base, at base plus size minus one, at base plus size, one
  below the base, in an unmapped hole between regions, and at an alias formed when upper address bits
  are not decoded.
- **State** — every lifecycle state in which the answer differs, from the Lifecycle states slot.

Then add the state-machine rows from steps 6 and 7: illegal lifecycle transitions, locked debug and
test access ports, and every path out of key storage that is not a declared reader.

Number the rows `NT1`, `NT2`, … now. Steps 3 to 7 fill each row in; step 8 writes them out.

### 3. Find what already claims to cover each row

**Glob** the Security test location for tests, sequences and checker or bind files. Then **one Grep**
across that tree for the asset name from step 1, and **one Grep** of the checker files for the
property names near it. Map each hit to a row number.

Two results are worth writing down, and only one of them is comfortable:

- **A row with no test.** That is the gap the matrix exists to find. Mark it `proof : untested`.
- **A test that maps to no row.** Either the threat model is incomplete, or the test is checking
  something else and its name misled you. Say which, with the file and line — do not quietly invent a
  row to give it a home.

If a Grep turns up a *failing* run rather than a gap, stop this procedure for that row and hand the
log to `dv-sim-log-first-error`. A failure gets a signature from `_shared/failure-signature-schema.md`
and an owner; it does not get a coverage matrix.

### 4. Audit the denial triple — response, data, side effect

**A denial is three requirements, and most checks assert one.** For each row with a candidate test,
spend **one Grep** on the Denial response encoding inside the Access control map RTL and **one Grep**
on the Requester identity signals in the same checker, then **two Read** windows: the permission
decision, and the response path that carries its result back. Record a file and line for each of:

1. **Response** — the exact encoding from the Denial response slot, compared as a value. A check that
   accepts "any status other than OK" also accepts a bus error caused by a bug elsewhere.
2. **Data** — the read data equals the defined denial constant. Not "differs from the protected
   value" — see the second gotcha, which is the most expensive one in this file.
3. **Side effect** — the refused access left nothing behind: no pointer advanced, no clear-on-read
   fired, no counter incremented, no interrupt raised, no arbitration grant consumed.

Then set `checked`. A denial observed only at the requester proves what the requester saw, which is
also what it would see if the fabric had routed the transaction somewhere else entirely. The strong
form is a never-happens property bound at the **asset's own port**, saying the transaction never
arrived. For key and lifecycle rows, treat anything less than `both` as unproven.

### 5. Audit for vacuity — the control and the arming witness

Three questions per row, and a row is `proven` only when all three are answered from a file.

- **Positive control.** Is there a test proving the *same* path, *same* address, *same* operation
  succeeds when it is permitted? Without it, the refusal is equally well explained by a disconnected
  interface, a sequence that ended early, or an agent that was never started.
- **Arming witness.** For every never-happens property, is there a cover showing its antecedent
  actually occurred in that test? A property whose precondition never held reports success, and no
  tool volunteers that unless asked. Spend **one Grep** for the cover alongside the property.
- **Scope of expectation.** Read the Expected-error convention. A test-wide switch that marks errors
  as expected also waives the real ones, so a genuine failure inside a negative test disappears. The
  expectation must be scoped to one source and one window. Spend **one Read** on the candidate test
  to see which form it uses.

One more failure mode has no symptom at all: **a checker bound to a module this build never
instantiates is simply not there.** Ask the engineer for the build log path under the profile's Build
log location and confirm the bound instance appears in it. The agent cannot start a build and must
not assume the bind took.

### 6. Lifecycle and debug-lock rows

Enter this step only for rows in those two classes. Spend **one Grep** on a state name from the
Lifecycle states slot or a lock signal from the Debug and test access ports slot, then **one Read**.

For **lifecycle**, four rows that are usually missing:

- Each illegal transition on its own row — backwards, skipping a state, and into a state with no
  legal predecessor. "The state machine has a default case" is not evidence; the default may latch
  the permissive state.
- A transition attempted without the authorising input, and one attempted while a previous transition
  is still in flight.
- The re-derivation row. The state must come back from its non-volatile source after **every** reset.
  A state cached in a register that only the power-on reset clears leaves a warm-reset window sitting
  in whatever the register last held.
- The atomicity row: the window after the state has changed but before the permission table has been
  re-evaluated. That window is often one cycle, and one cycle is enough.

For **debug and test access ports**, three rows per port in the slot: refused while locked, permitted
after a legitimate unlock (this is the positive control, not a separate feature test), and still
refused after a warm reset that follows that unlock. Shifting the scan chain while locked must not
shift out state derived from key material; the classic hole is a pad-level test input that is gated
while an internal test-enable stays reachable from another port. Confirm against the policy **which**
instructions must be refused — identification instructions usually stay answerable by design.

### 7. Key-path rows

Spend **one Grep** on the storage identifier from the Key storage and readers slot and **one Read**
on its fan-out. Enumerate every net driven from the storage and check each against the declared
reader list. A path that is not on the list is a row, whether or not anyone believes it is reachable.

Three specifics that decide whether these rows mean anything:

- **The back door is the ground-truth instrument, never the denied path.** Use a back-door read to
  prove the key material is actually present, so the refusal is not passing because the storage was
  empty. Checking the denial *through* the back door bypasses the very control under test.
- **Zeroisation is three checks, not one.** The storage reads as cleared; no copy survives in a
  pipeline register, shadow or buffer; and the clear completes before the design enters any state
  that would permit a read. Sampling once, late, proves only the first.
- **Observability paths count.** Key state reaching a trace port, a coverage sampling point or a
  dumped signal is a leak if that port is reachable in the field. So is a monitor that prints the
  value into the log — that makes the log itself the exposure, and logs travel further than parts do.

### 8. Write the matrix and the gap block

One block per row. The field names are chosen so a reviewer can read a row without the prose.

```
row       : NT1
asset     : <the protected thing, in the threat model's own words>
state     : <the lifecycle state this row applies to, or "all">
path      : <the port the illegal request arrives on, and the requester identity it carries>
act       : <the exact operation that must not succeed>
denial    : <the response encoding, the defined read-data value, and the side effect that must not occur>
checked   : requester | asset | both | neither
control   : present | absent | not-applicable
arming    : witnessed | unwitnessed | unknown
proof     : proven | vacuous | untested | not-checkable-here
evidence  : <file and line for every claim above, or "none found">
owner     : <the one team that fixes this, from the profile's Area to owner map>
notes     : <what the next person would otherwise have to rediscover>
```

Then one summary block for the audit as a whole:

```
threat model : <name and revision, and whether it was read from disk or reported by a person>
assets       : <how many were named, and how many had a policy that could be read from a file>
rows         : <how many illegal actions step 2 enumerated>
tally        : <n> proven / <n> vacuous / <n> untested / <n> not-checkable-here
worst gap    : <the one row a reviewer should look at first, and why>
run id       : <whatever identifies the run whose log was read, or "no log read">
log          : <path, and the line range worth reading>
coverage     : <n of m rows audited against files; which rest on a person's answer; which asset classes were never opened>
```

Write `?` for anything not traceable to text on disk. **The denominator in `coverage` is the number
of rows step 2 enumerated, never the number you got to.** "Audited 5 of 34 rows; the other 29 are
enumerated and unopened" is a useful artifact that a reviewer can plan against. "All audited rows
pass" is the sentence that gets a part taped out with a hole in it.

## Gotchas

- **A refusal and a no-op are the same waveform.** Every negative row needs a positive control on the
  same path; without one, a test that never drove anything is indistinguishable from a design that
  refused everything, and it is the cheaper of the two to write by accident.
- **X is not a denial, and it hides a real leak.** In SystemVerilog an equality comparison against a
  value containing X evaluates to X, and a conditional treats X as false — so a check phrased "fail
  if the read data equals the protected value" never fires on an all-X read. Simulation shows X on
  the locked-out path and silicon settles it to the real value. Use the case operators, and require
  the data to **equal the defined denial constant** rather than merely to differ from the asset.
- **Default-deny must be proven where the table says nothing.** A permission table that refuses
  everything it knows about and passes through everything it does not looks perfect against every row
  of itself. The rows that find it are the unmapped hole between regions and the alias formed by
  undecoded upper address bits.
- **A burst that straddles the boundary is where the off-by-one lives.** Base plus size and base plus
  size minus one are one row each. A burst that starts inside the region and ends outside must be
  refused whole; one that returns the in-region beats alongside an error response is a leak with a
  clean-looking status.
- **The error response and the absence of data movement are separate requirements.** Some fabrics
  return read data on the same beat as the error, and a checker watching only the status will call
  that a pass forever.
- **A debug unlock that survives a warm reset is the same bug as a lifecycle state cached in a
  register.** Both re-enter a permissive condition without any transition being requested, and both
  are invisible to any test that resets only once, at the start.
- **The identification instruction answering while the port is locked is usually correct behaviour.**
  Filing it costs a day and ends with the policy being right. Check which instructions the policy
  actually requires to be refused before writing any of them up.
- **A test-wide expected-error switch waives real errors too.** Scope the expectation to one source
  and one window, or a genuine failure inside the negative test will never be seen by anyone.
- **A bound checker in a module this build never instantiates passes, and so does an unwitnessed
  never-happens property.** Neither reports anything: no bind, no antecedent, no complaint. Require a
  cover for every property and the bound instance in the build log.
- **Constrained-random stimulus does not reach the illegal space** — the constraints are precisely
  what excludes it, so more seeds buy nothing here. Negative rows are directed, or a constraint is
  deliberately relaxed for that row and the relaxation is recorded next to it.

## Human verification — what a wrong answer looks like

Before treating the matrix as evidence, check:

- every row's `denial` names **three** things — response encoding, defined data value, and the side
  effect that must not occur — and not merely "an error".
- every row marked `proof : proven` cites a file and line for the check **and** a file and line for
  its positive control. One without the other is `vacuous`.
- no row is proven from a back-door read of the very path under test.
- `checked` is `asset` or `both` on the key and lifecycle rows; `requester` alone is the requester's
  opinion, not the asset's.
- the enumeration in step 2 includes the addresses, requesters and attribute combinations the
  permission table does **not** mention. A matrix built backwards from the tests that exist can never
  find a missing control, and reads exactly like a thorough one.
- `coverage` has the enumerated row count as its denominator, and every provisional row traceable to
  the person who supplied the policy.
- nothing the policy calls legal has been written up as a gap.

A wrong answer typically reports "all negative tests pass" with no arming witness anywhere in the
evidence column; marks a row proven on a log line saying an error was seen without saying which
error; or enumerates thirty rows for the one asset with a readable policy and none for the three
whose policy lives in a deck nobody opened.

## Done when

Every enumerated row carries a proof status, the file and line behind it, and — for each row not
proven — the single thing still needed, with a coverage line naming how many rows you actually opened.
