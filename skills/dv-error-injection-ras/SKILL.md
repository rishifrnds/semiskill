---
name: dv-error-injection-ras
description: Build the standard error-injection matrix for an interface IP — every protected structure crossed with every error pattern, timing and persistence — and state the five checks each cell demands before it counts as verified. Use when you are verifying ECC, parity, CRC, link-level retry, poison propagation or error reporting, when someone asks whether the RAS story is covered, when an injected error produced no report and you cannot tell whether that is correct, or when a fault campaign needs a scenario list rather than more random seeds.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Error-Injection, ECC and RAS Scenario Matrix for Interface IP
  semiskill-function: design-verification
  semiskill-role: ip-dv-engineer
  semiskill-level: senior-staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-09-22
  semiskill-tags: ecc, ras, error-injection, poison, crc, parity, retry, fault-campaign
---

# Error-Injection, ECC and RAS Scenario Matrix for Interface IP

Error protection is the part of an interface IP that the datasheet claims and almost nothing
exercises. Every test in the regression proves the clean path; the corrected-error path is proved by
whichever cells somebody remembered on a Friday, and the uncorrectable-fatal path by none of them
until a customer's machine check names your block. The failure is never a missing test — it is a
matrix nobody wrote down, so nobody can say what is missing.

The output is **a matrix, one expected response per row quoted from a named clause, a covered / gap /
waived status per row, and a coverage line** — not a list of tests to write. It reads source files,
register descriptions, test lists and saved logs; it cannot inject an error, start a campaign, drive
a force or open a waveform, and every step needing one of those hands off to a named human.

## When to use something else

One injection run failed in a way you did not predict — take the true first error and a signature from
`dv-sim-log-first-error` first. The error-status register itself reads back wrong, or the model and
the design disagree about a field's access policy — `dv-ral-bringup`, and settle it before any
reporting check here means anything. A whole campaign's results to sort and route is
`dv-regression-triage-routing`; warn it that this matrix deliberately contains tests that end in a
fatal, so their logs look like failures and are not. A slow failing cell belongs in
`dv-minimal-reproducer`; a hook that will not compile in `dv-build-filelist-hygiene`; a testbench you
cannot find at all in `dv-repo-orientation`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Protection inventory | [[FILL: which structures in this block are protected, by which mechanism (parity, SECDED, symbol code, CRC, duplication), at what granularity, the detect/correct claim made for each — and the name of the source file that inventory lives in]] | IP architect |
| Severity taxonomy | [[FILL: what our specification calls each severity class, and which document and clause define the classification]] | RAS architect |
| Reporting registers | [[FILL: which registers latch error status, first-error, counters, thresholds, masks and captured address or syndrome — and the path to the register description on disk]] | register owner |
| Injection hooks | [[FILL: how an error is injected in our environment — the knob, sequence, VIP capability or force interface — and its exact spelling]] | VIP or testbench owner |
| Injection marker | [[FILL: the string the environment prints when an injection was actually applied, as distinct from any failure marker]] | testbench owner |
| Poison convention | [[FILL: whether this interface carries a data-error or poison marker, its granularity in bytes, and how far it is required to propagate]] | IP architect |
| Retry limits | [[FILL: the replay or retry count this interface allows, and the specified behaviour when it is exhausted — or that this interface does not retry]] | protocol owner |
| Error test list | [[FILL: where our existing error-injection tests are listed, and how a test name maps to a scenario]] | DV lead |
| Waiver record | [[FILL: where a deliberately un-injected scenario is recorded, and who signs that decision]] | verification lead |

This skill also spends three pack-wide facts from `_shared/team-profile.md` — **Log location**,
**Fatal markers** and **Pass marker**, all in step 7. Read them there; do not re-interview anyone.
Three rows above are deliberately narrower than a profile row and are **not** the same fact.
**Reporting registers** narrows *Register model source*: that says what our model is generated from,
this says which registers inside it carry error state. **Waiver record** narrows *Sign-off*: that says
who signs the block off, this says where one skipped scenario is written down. **Injection marker** is
not a failure marker and must never be filled from *Fatal markers* — it is the line proving the
injection happened, and a run can print it and still pass.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented protection claim or
severity class produces a matrix that looks authoritative and verifies nothing.

## Retrieval budget — read this before opening anything

A register description runs to tens of thousands of generated lines and an injection log to hundreds
of megabytes. The matrix's *rows* are authored from the axes in step 3 and cost no retrieval at all;
only the expected response and the covered / gap status cost anything.

1. **Grep and Read work on files on disk.** If the specification is a PDF, a spreadsheet or a wiki
   page, say so before going further and treat every number from it as a handoff — ask the architect,
   record who supplied it, mark that row *provisional*. If a log arrived pasted into the chat, ask for
   the path under **Log location** before step 7.
2. **Glob twice at most**, and only where no slot hands you a location: the source named in
   **Protection inventory**, spent in step 1, and one spare in step 2 if **Reporting registers**
   arrived without the path it asks for. No other step spends one — steps 3, 4 and 5 open nothing,
   step 6 reaches the hook by the exact spelling **Injection hooks** gives it and the test list by its
   own slot, and step 7's log path comes from the engineer. Never open a generated file with **Read**
   first.
3. **Five Grep calls, no more**, one per lookup: the protection mechanism names (step 1); the
   reporting register names (step 2); the injection hook's exact spelling (step 6); the **Error test
   list** (step 6); and one alternating pattern over one log for the **Injection marker**, the
   profile's **Fatal markers** and its **Pass marker** (step 7).
4. **Five bounded Reads of about 60 lines** on our own files — protection inventory, error-register
   declarations, hook declaration, one existing error test, one spare for wherever the matrix is
   thinnest — plus, only in step 7 and only when a log is being confirmed, one 80-line window in it.
   More than about 150 Grep hits means the pattern is too broad: a hook spelled like `inject` is a
   substring of half the testbench, so anchor it before reading anything.
5. **Stopping rule.** When the budget is spent, emit the matrix as it stands with its coverage line —
   how many rows carry a clause read from a file, how many carry a person's answer, which axes were
   never enumerated. A matrix with honest gaps is useful; one with invented expected responses is
   worse than none, because it will be signed.

## Procedure

### 1. Establish what is actually protected, before designing any cell

A cell aimed at an unprotected structure is not a hole and not a bug — it is a cell whose correct
outcome is silence, and that has to be written down as such. Spend the budget's first **Glob** on the
source named in **Protection inventory** — the one lookup in this skill no slot hands you a path for —
then **one Grep** for the mechanism names it lists and one 60-line **Read** at the densest hit. Record
per structure: the mechanism, the granularity in bits or bytes, and the claim — how many bit errors it
detects and how many it corrects. That claim is every row's yardstick. A code
that corrects one bit and detects two cannot be failed for mis-correcting three; that is its limit.

### 2. Enumerate the reporting surface before designing any check

**One Grep** of the register description, at the path **Reporting registers** gives you, for the names
it lists — that slot promises a path, so this step costs no **Glob**; if it arrived without one, the
budget's spare **Glob** goes here. Then one 60-line **Read** at the declarations. Five things, each of
which becomes a column of the report check in step 5.

- a status bit per error class, and whether it is sticky
- a first-error latch, and the overflow bit saying a second error arrived while it was full
- counters per class, whether they saturate or wrap, and the threshold that crossing them trips
- mask or enable bits — and, from **Severity taxonomy**, whether a masked error still latches status
  or is dropped entirely, which is IP-specific and must not be assumed
- captured address, syndrome or transaction identifier, and its validity bit

Record the clear mechanism for each sticky bit too. If it is read-to-clear, a scoreboard that reads
the status register twice has cleared it between the two reads and the second read proves nothing;
`dv-ral-bringup` has the policy table, and the string is quoted exactly as the model spells it.

### 3. Build the axes — and resist the cross product

**Axis A — injection site.** Where the corruption enters.

| Site | Why it is its own row |
|---|---|
| the wire, ahead of the receiver's checker | the only site the protocol's own CRC ever sees |
| the receive datapath, after the checker and before storage | exercises internal protection, not link protection |
| a storage array — buffer, replay copy, tag or descriptor RAM | exercises the array's code and its scrubber, if it has one |
| the check bits themselves | half of every codeword, and the half routinely skipped |
| the address, index or tag rather than the data | data protection passes and the wrong location's clean data comes back |
| control, metadata and configuration — length, byte enables, sideband, credits, mode bits | often unprotected by design, so the expected result is silence, and a flipped mode bit changes behaviour with no data error anywhere |

**Axis B — error pattern.** One bit; two bits inside one protection domain; three or more; adjacent
bits inside one symbol; a whole symbol or lane; a burst spanning consecutive beats.
**Axis C — timing.** Idle; steady traffic; first, middle and last beat of a packet; during link
training or reset; across low-power entry and exit; at a credit-exhausted or buffer-full boundary;
inside a replay that is itself replaying; a second error before the first was cleared.
**Axis D — persistence.** Single-shot; repeated below the threshold; repeated across it; persistent.

**The selection rule.** The full cross product is thousands of cells and is not the matrix. A
candidate earns a row only when some named clause predicts a **different specified response** for it
than for a row already there. Everything else is another seed of a row you have and belongs in the
random campaign. Applied honestly this leaves a few dozen rows, each of which someone can defend.

### 4. Give every row an expected response, quoted from a clause

Use **Severity taxonomy** for the words our specification uses; the ladder below is the shape, not our
vocabulary. Assign every row exactly one token from the left column and copy it into `severity`
**with the spelling shown here** — `uncorrectable-recoverable` and `none-expected` carry a hyphen, and
a row spelled `uncorrectable, recoverable` or `none expected` will not sort with anybody else's.

| Token | Assign it to a row when | The check that is easy to forget |
|---|---|---|
| `corrected` | the mechanism fixes it, delivers correct data and counts it | that it was *counted* — a correction nobody counts is a reliability hole that stays silent until it becomes uncorrectable |
| `deferred` | the data must not be consumed: it is marked and the mark propagates | that the mark survives every hop, per **Poison convention** |
| `uncorrectable-recoverable` | the transaction fails and is reported, and the interface stays up — take this token for every row whose specified response is an error the software is expected to act on and continue from | that software can restart, and that the interface is at *full* service, not degraded |
| `uncorrectable-fatal` | containment is impossible and the block goes down by design | that it went down for this reason and not another |
| `none-expected` | step 1 found no mechanism covering this structure, so the specified response is silence — take this token whenever the row's correct outcome is that nothing at all happens | that the silence was predicted in writing before the run |

Both directions matter. Under-response is the obvious bug; **over-response is a bug too** — a link
that retrains on a single corrected error, or a fatal raised where the specification says recoverable,
costs a customer more availability than the error did. Retry rows take their limit and exhaustion
behaviour from **Retry limits**; a retry row with no stated limit has no expected response.

### 5. The five checks every cell demands

A cell is verified when all five hold. Four out of five is an unverified cell with a green tick.

1. **Detect** — the intended detector fired and no other one did. Two mechanisms both reporting is an
   unspecified interaction, which is a finding in itself.
2. **Respond** — exactly the response step 4 predicted. Not stronger, not weaker.
3. **Report** — every column from step 2: the right status bit and only that one; first-error latched
   on the first and not the last; the counter moved by exactly one; the severity classified correctly;
   the notification raised once rather than once per beat; the overflow bit set when a second error
   arrived into a full log.
4. **Contain** — no incorrect data delivered without its marker, at the specified granularity; no
   other in-flight transaction disturbed; nothing corrupted upstream of the injection site.
5. **Recover** — the sticky state clears only by the specified means, the counter only by its own, the
   next transaction is clean, and the interface is back at full service.

### 6. Find which cells already exist

**One Grep** for the exact **Injection hooks** spelling across the testbench and **one Grep** of the
**Error test list**. Then two 60-line **Read** windows — the hook declaration, to learn which axes it
can reach, and one existing error test, for the house pattern. Mark each row `covered`, `gap` or
`waived`. A row is `covered` only when a test exists **and** its checks match step 5; a test that
injects and then only asserts that traffic completed leaves the row a gap, because it would pass with
the detector deleted. A row is `waived` only when the decision is recorded in **Waiver record** with a
name against it — never because nobody got to it. A hook that cannot reach an axis is itself a finding
and outranks any single row: one that corrupts only data leaves three whole bands unreachable.

### 7. Confirm one cell against a real run

The agent cannot inject anything. **Ask the engineer to run one injection test with the hook applied
and to save the log where it can be read from disk**, then give you the path. Spend the budget's last
**Grep** there — one alternating pattern over the **Injection marker**, the profile's **Fatal
markers** and its **Pass marker** — and one 80-line **Read** window at the first hit.

What you are looking for is not the pass. **A log with a pass marker and no injection marker is a
vacuous cell**, and it is by a wide margin the most common broken result in a fault campaign: the knob
was misspelled, nothing was injected, the test ran clean and somebody ticked the row. Report
injection-confirmed and check-result as two separate outcomes. For a fatal-class row the fatal marker
*is* the pass condition — say so in the notes, or triage will bucket it as a failure.

### 8. Record the matrix, the gaps, and how far you got

Deliver the matrix table, then one block per row that failed or is a gap. Where a row failed, write the
failure as a signature following `_shared/failure-signature-schema.md` — same field order, same
normalisation rules. The block reuses field names from `dv-sim-log-first-error` so the two read side by
side; `cell`, `mechanism`, `severity`, `response`, `checks` and `status` are this skill's own.

`class` is the pack-wide routing field, and this skill's mapping is narrower than it first looks. A
misspelled **Injection hooks** knob, a force path that does not exist, a hook that structurally cannot
reach the row's axis, or a VIP that accepted the knob and applied nothing is `infrastructure` — the
run proved nothing about the RTL either way, and step 7's vacuous cell is by far the commonest member
of that class, however much a silent detector feels like a design bug. A row where the injection
marker was seen and the design then detected, responded, reported, contained or recovered differently
from the clause step 4 quoted is `design`. A row where injection is confirmed and you still cannot say
which side owns the miss stays `unknown` until someone re-runs it.

```
cell      : <site> / <pattern> / <timing> / <persistence>, from the step 3 axes
mechanism : <the protection this row exercises, named as our specification names it>
severity  : corrected | deferred | uncorrectable-recoverable | uncorrectable-fatal | none-expected
response  : <the specified response, with the document and clause it was quoted from>
checks    : detect, respond, report, contain, recover — pass, fail or unchecked for each
status    : covered | gap | waived
signature : <phase>|<kind>|<where>|<what>, per the shared schema, only where the row failed
class     : design | infrastructure | unknown
run id    : <whatever identifies this run for us>
log       : <path, and the line range worth reading>
coverage  : <n of m rows carry a clause read from a file; which axes were never enumerated>
notes     : <injection-confirmed or not; whether a fatal here is expected; anything a person told you>
```

Write `?` for anything not traceable to a file or a named person. A row whose `response` has no clause
behind it is an opinion, and marking it `status: covered` launders an opinion into sign-off.

## Gotchas

- **Never write a row that asks a code to beat its own distance.** Parity detects an odd number of
  flips and nothing else, so two bits in one parity domain are invisible by construction; a code that
  corrects one and detects two may silently mis-correct three into a different valid codeword. Both
  are specified limits. What is verifiable is that the design's *claim* matches the code's real
  distance — filing the limit as a bug costs a week and ends with the code being correct.
- **Injecting into the check bits is the band everyone skips.** They are part of the codeword, so a
  single flip there must be reported as a corrected error like any other. Corrupt only the data field
  and half of every codeword goes untested, silently.
- **Address or tag corruption defeats data protection completely.** A flipped index returns a clean,
  correctly-coded value from the wrong location and every data check passes. Only address protection
  or a stored-tag comparison catches it; a matrix with no address band has not verified the claim.
- **A background scrubber can pass your cell for the wrong reason.** An error injected into an idle
  array may be corrected by the scrubber before your read arrives, so the read path's own correction
  was never exercised. Inject with traffic, or say in the notes which one you actually proved.
- **The replay copy is its own structure.** An error on the wire and an error in the buffered copy
  held for retransmission are different rows with different owners, and only the second asks whether
  the replay path is protected at all.
- **A sticky log latches the first error, not the last.** Inject three, read the status at the end,
  and you have tested error one and the overflow bit. If no row ever overflows the log, the overflow
  bit has never been checked. A threshold, likewise, fires once at the crossing and not on every count
  past it — and whether the counter saturates or wraps changes what "past it" even means.
- **Poison granularity mismatches go both ways.** A marker wider than the error condemns clean data
  and costs an avoidable outage; narrower, and bad bytes escape unmarked, which is silent corruption.
  Check the merge points and the write-back path — a poisoned value that is read, modified and written
  back must not come back clean.
- **"The link is up" is not recovery.** After a lane is dropped and the link retrains narrower the
  interface is up and permanently degraded, and a recovery check that only asks whether traffic flows
  will sign off a halved link. Equally, an error the design correctly ignores still needs a row:
  silence predicted in writing is evidence, silence nobody predicted is indistinguishable from a hook
  that never fired.

## Human verification — what a wrong answer looks like

Before signing anything, check:

- every row's `response` carries a document and clause; rows resting on a person's word are provisional
- no row expects parity to catch an even number of flips, and none files a mis-correction beyond the
  code's stated distance as a design bug
- the matrix has at least one check-bit row, one address or tag row, and one row expecting silence
- every `covered` row asserts on the reporting surface from step 2, not merely that traffic completed
- injection-confirmed is quoted separately from the check outcome; a pass marker with no injection
  marker is `status: gap`
- fatal-class rows are flagged as expected-fatal so triage does not bucket them as failures
- every row carries one of step 4's five `severity` tokens spelled exactly as that table spells them,
  and every failing row carries a `class` — a row whose injection was never confirmed is
  `infrastructure`, not a design finding, however plainly the detector looks asleep
- the coverage line's denominator is the number of rows in the matrix, not the number of tests found

A wrong answer typically presents a full-looking matrix in which every expected response was inferred
rather than quoted; marks rows covered on the strength of a test that would pass with the detector
removed; reports a code behaving exactly at its stated limit as a bug; or has no row at all for the
check bits, the address path, or the cells where silence is correct.

## Done when

You can name every row in the matrix, the clause behind its expected response, its covered / gap /
waived status, and how many of those you resolved from files rather than from a conversation.
