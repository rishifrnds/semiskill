---
name: dv-minimal-reproducer
description: Shrink a failing simulation down to the smallest, fastest thing that still shows the same failure signature, one bisection axis at a time. Use when a failure takes hours to reproduce, when a designer or R&D has asked for a smaller test case, when a bug ticket keeps bouncing back for more information, or when you are about to hand over a full-chip regression run as a reproducer.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Shrinking a Failure to a Minimal, Fast Reproducer
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-02-05
  semiskill-tags: reproducer, bisection, determinism, triage, handoff, debug
---

# Shrinking a Failure to a Minimal, Fast Reproducer

A reproducer that needs the full chip, six hours and your personal work area is one nobody will use.
The designer tries it once, it fails elsewhere or not at all, and the ticket bounces back with
"cannot reproduce" — that ping-pong costs the days, not the debug. Shrinking is bisection over a few
axes, and the one invariant that matters is that the **failure signature does not change**.

This skill proposes the next bisection step and reasons over what the engineer pastes back — it
cannot start a simulation, build a model, or submit anything. Signature format is defined once in
`_shared/failure-signature-schema.md`; use it as written rather than re-deriving its rules.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Determinism controls | [[FILL: what makes two of our runs comparable — seed, plusargs, build tag, model revision]] | DV lead |
| Run identity | [[FILL: what identifies one run for us, and where that string is printed]] | your mentor |
| Config surface | [[FILL: where our test configuration lives and which knobs are safe to change without a rebuild]] | DV lead |
| Time-window controls | [[FILL: how our flow limits simulated time, or saves and restores a checkpoint, if it can]] | DV infra owner |
| Testbench tiers | [[FILL: which smaller tiers exist for this block, and what stimulus each can reach]] | block owner |
| Runtime budget | [[FILL: how fast and how small a reproducer must be before the recipient will accept it]] | verification lead |
| Handoff template | [[FILL: what our bug ticket or handoff note requires as mandatory fields]] | DV lead |

**If a slot is unfilled, stop and ask. Do not guess.** An invented knob name or an invented rerun
recipe sends the recipient down a path that does not exist, and you will not hear about it for a day.

## Retrieval budget

The artifacts here — logs, filelists, config files, regression summaries — are far too large to read.
Every shrink iteration produces another log. Hold to this:

1. **Never open a log or a filelist with Read first.** Use **Grep** to locate a line number, then
   **Read** a bounded window around it.
2. Per iteration the budget is one **Grep** for the failure marker, one **Grep** for the pass marker,
   and at most two **Read** windows of about 80 lines each.
3. To locate a config knob or a tier directory, **Grep** for the knob name or **Glob** the tier path
   rather than reading the file — then **Read** at most 40 lines either side of the hit.
4. If a **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it before reading
   anything.
5. **Stopping rule.** If two windowed **Read** calls have not confirmed the signature, report that
   iteration as inconclusive. Do not open a third file, and never infer a signature from an earlier run.

## Procedure

### 1. Recover the signature that must be preserved

Derive the baseline signature from the original failing log using
`_shared/failure-signature-schema.md`. Use **Grep** to find the first fatal marker, then **Read** a
window around it. Write the four fields down explicitly before anything is changed.

Everything below is measured against this string. If you cannot produce a signature from the original
log, shrinking has nothing to preserve — stop here and say so.

### 2. Establish determinism before shrinking anything

If the failure is not reliably reproducible, a shrink step that "fixes" it has told you nothing.
Ask the engineer to repeat the unmodified test three times and paste the tail of each log, then
classify with **Grep** over those logs:

- **Deterministic** — same seed, same signature, same simulated time of failure. Ideal.
- **Signature-stable** — same signature, but the failure time or the transaction index moves between
  runs. Usually fine to shrink, but time-window shrinking becomes risky.
- **Seed-dependent** — fails on one seed only. Ask for the failing seed to be pinned and recorded as
  part of the reproducer, not as an aside.
- **Intermittent** — fails roughly 1 run in N. Ask the engineer for the observed rate and record N.
  Every later step is judged against that same N.

Three things commonly break determinism — uninitialised state that starts as X and resolves
differently under a different schedule, anything derived from wall-clock time or host load including
timeouts, and randomisation whose seed-stream order depends on how many agents are active.

### 3. Record the baseline cost

Use **Grep** on the original log for the simulated time of failure and any end-of-run resource line.
Ask the engineer for wall-clock duration, tier, and whether a build was needed. A shrink with no
baseline is a claim, not a measurement.

### 4. Propose one shrink step, on the cheapest axis first

Work the axes in this order. Each is cheaper to try and more likely to pay than the one after it.

1. **Time window.** Cut the run so it stops shortly after the failure time. If the flow supports a
   saved checkpoint, propose restoring close to the failure instead of starting cold. Biggest win,
   lowest effort, highest risk of changing initialisation — see Gotchas.
2. **Configuration.** Switch off what is not implicated — unrelated agents, coverage collection,
   scoreboards for other interfaces, debug verbosity, protocol checkers in untouched blocks. Prefer
   knobs that take effect at runtime over anything that forces a rebuild.
3. **Stimulus.** Reduce the number of transactions, then constrain randomisation toward the pattern
   that failed, then replace the random sequence with a directed replay of the observed transactions.
   Do this before touching anything else that would disturb the random stream.
4. **Hierarchy.** Move down a tier — full chip to subsystem to block — only if a lower tier can
   actually drive the same stimulus. Use **Glob** on the tier paths from the slots table and **Grep**
   for the failing component name to check it even exists at that tier.
5. **Test length.** Trim warm-up, preceding phases, training or calibration sequences. Last, because
   these are the parts most likely to be carrying the real precondition.

Propose exactly one change — name the axis, the change, and the expected outcome. Then ask the
engineer to make that one change, run it, and paste the log path plus the last 100 lines.

### 5. Re-check the signature after every single change

With **Grep** and one bounded **Read**, derive the signature from the new log and compare it to the
baseline **field by field**. Accept the step only when all four fields match exactly.

- All four match → keep the change, update the running config diff, propose the next step.
- Any field differs → revert. Do not carry a changed signature forward.
- No failure at all → revert, and treat the change as a sensitivity, not a success.

For an intermittent failure, one passing run is not evidence. Ask for enough repeats to be meaningful
against the recorded N before accepting the step.

### 6. Recognise when shrinking has changed the bug

Shrinking that changes the bug is worse than not shrinking, because it looks like progress. Treat any
of these as a stop-and-revert:

- the signature's `where` moved, even though `what` normalises identically
- the failure now occurs earlier than the cause line identified in the original log
- an intermittent's rate moved by more than roughly a factor of two in either direction
- the failure still appears with the block under test stubbed out or held in reset
- the run now ends on a different marker — a timeout where there was a miscompare, or the reverse

Each of these is information. The change that made the bug move is describing the mechanism; record
it in the sensitivity line of the handoff rather than discarding it.

### 7. Decide to stop

Stop at the first of these, and say which one:

- the reproducer meets the runtime budget slot
- three consecutive proposals in a row were reverted
- every remaining element is load-bearing — each removal you have tried changed the signature
- the time box for shrinking is spent

A good-enough reproducer handed over today beats a minimal one handed over on Thursday.

### 8. Draft the handoff so the recipient needs nothing else

Author this block. Leave a field empty rather than filling it from assumption.

```
signature   : <phase>|<kind>|<where>|<what>
determinism : deterministic | signature-stable | seed-dependent | intermittent 1 in N
baseline    : <tier, wall clock, simulated time to failure>
reproducer  : <tier, wall clock, simulated time to failure>
to repeat   : <invocation taken from our conventions, or empty>
config diff : <every change from the standard test, including the cosmetic ones>
sensitivity : <changes that made it vanish or moved the signature>
first fail  : <verbatim first fatal line, with line number>
cause line  : <verbatim cause line, with line number>
log         : <path, and the line range worth reading>
not tried   : <axes deliberately left alone, and why>
```

`not tried` matters more than it looks. It stops the recipient repeating work you already did and
stops them assuming an axis was clean when it was simply never touched.

## Gotchas

- **Starting later from a checkpoint is not the same run.** A restored state already holds values a
  cold start reaches through a specific sequence. A bug that depends on initialisation, on X
  resolution, or on a one-time calibration quietly disappears when you restore past it.
- **Turning the waveform dump off can change the failure**, and turning it on can too. Dumping
  perturbs scheduling in some flows and suppresses optimisations in others. If the bug only appears
  with dumping enabled, that is a finding to write down, not an inconvenience to work around.
- **Any change to constraints, sequence counts, or active agent count re-orders the random stream.**
  After that, "same seed" no longer means same stimulus and seed-based comparison against earlier runs
  is meaningless. Freeze the stimulus with a directed replay first, or accept the loss.
- **The unrelated agent you switched off is often not unrelated.** Shared bus arbitration, credit
  return, and backpressure mean background traffic can be the precondition. If the failure needs it,
  you have just found the mechanism.
- **Dropping down a tier removes real reset, clock and power sequencing.** Block benches typically
  drive an idealised reset and one clean clock. A reset-domain or clock-crossing bug will not follow
  you down, and its absence at block level proves nothing.
- **Twenty clean runs mean nothing if the original rate was 1 in 50.** For intermittents, the number
  of repeats needed to call a step good grows with N, and most people stop far too early.
- **Prefer runtime knobs to rebuilds.** Removing files or flipping a compile-time define changes
  elaboration order, optimisation and sometimes X behaviour at once — you will have shrunk three axes
  while believing you shrank one.
- **Switching off checkers elsewhere lets the run continue past where it used to stop.** The failure
  appears "later" and looks new — compare signatures, not timestamps, before concluding anything.
- **A reproducer that only works in your work area is not shrunk, it is trapped.** Anything the
  recipient cannot reach — a local model build, an uncommitted edit, a scratch file — belongs in the
  config diff or must go before handover.

## Human verification — what a wrong answer looks like

Before sending the handoff, check:

- the shrunk reproducer was **confirmed by an actual pasted log**, not predicted from the shrink
  reasoning
- all four signature fields match the baseline character for character
- the config diff lists every change, including the ones that felt too small to mention
- the determinism class of the reproducer is the same as the baseline's, or the change is called out
- `to repeat` is taken from the team's real convention, or left empty

A wrong answer looks like "reduced from four hours to three minutes", where the three-minute version
fails on a different component, or fails deterministically when the original failed one run in forty,
or needs a file that exists only in the author's area. It reads as a triumph and bounces in a day.

## Done when

The recipient reproduces your signature once, from your block alone, inside the runtime budget.
