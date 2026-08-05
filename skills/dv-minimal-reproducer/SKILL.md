---
name: dv-minimal-reproducer
description: Shrink a failing simulation down to the smallest, fastest thing that still shows the same failure signature, one bisection axis at a time. Use when a failure takes hours to reproduce, when a designer or R&D has asked for a smaller test case, when a bug ticket keeps bouncing back for more information, or when you are about to hand over a full-chip regression run as a reproducer. Assumes a failing log already exists on disk and a signature can be derived from it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Shrinking a Failure to a Minimal, Fast Reproducer
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.2.0
  semiskill-review-by: 2027-06-23
  semiskill-tags: reproducer, bisection, determinism, triage, handoff, debug
---

# Shrinking a Failure to a Minimal, Fast Reproducer

A reproducer that needs the full chip, six hours and your personal work area is one nobody will use.
The designer tries it once, it fails elsewhere or not at all, and the ticket bounces back with
"cannot reproduce" — that ping-pong costs the days, not the debug. Shrinking is bisection over a few
axes, and the one invariant that matters is that the **failure signature does not change**.

This skill proposes the next bisection step and reasons over what the engineer reports back — it
cannot start a simulation, build a model, or submit anything. Signature format is defined once in
`_shared/failure-signature-schema.md`; use it as written rather than re-deriving its rules.

What follows is a **discipline checklist for a loop a human drives**, not a procedure the agent runs
end to end. Most steps are "ask the engineer for one thing, then read one bounded window of one log".
The value is in the order of the axes, the revert rules and the handoff — not in automation.

**When not to use this.** Start here only once you already have a signature and want it smaller. For
a single failing log you have not triaged yet, use `dv-sim-log-first-error` — it produces the
signature this skill preserves. For a night of regression failures that need sorting and routing
before anyone shrinks anything, use `dv-regression-triage-routing`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Fatal markers | [[FILL: the strings our flow prints on a real failure, beyond UVM_ERROR and UVM_FATAL]] | DV lead |
| Pass marker | [[FILL: the string a clean run prints at the end]] | DV lead |
| Determinism controls | [[FILL: what makes two of our runs comparable — seed, plusargs, build tag, model revision]] | DV lead |
| Run identity | [[FILL: what identifies one run for us, and where that string is printed]] | your mentor |
| Config surface | [[FILL: where our test configuration lives and which knobs are safe to change without a rebuild]] | DV lead |
| Time-window controls | [[FILL: how our flow limits simulated time, or saves and restores a checkpoint, if it can]] | DV infra owner |
| Testbench tiers | [[FILL: which smaller tiers exist for this block, and what stimulus each can reach]] | block owner |
| Runtime budget | [[FILL: how fast and how small a reproducer must be before the recipient will accept it]] | verification lead |
| End-of-run summary | [[FILL: the line our flow prints at the end of a run carrying simulated time and resource use, if it prints one]] | DV infra owner |
| Handoff template | [[FILL: what our bug ticket or handoff note requires as mandatory fields]] | DV lead |

Three of these are pack-wide facts rather than facts about this procedure: **Fatal markers**,
**Pass marker** and **Run identity**. They live in `_shared/team-profile.md` — fill that in once for
the team and read the answers from there rather than re-interviewing anyone. The same three are the
slots this table shares with `dv-sim-log-first-error`; **Determinism controls** is not one of them —
it has no counterpart in the profile or in that skill, and is answered here and nowhere else. Only
fill in one of the shared three above if this skill needs something narrower than the profile
records — Run identity here also asks where the string is printed, which the profile's entry does not.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented marker string, knob
name or rerun recipe sends the recipient down a path that does not exist, and you will not hear about
it for a day.

## Retrieval budget — read this before opening anything

The artifacts here — logs, filelists, config files, regression summaries — are far too large to read.
Every shrink iteration produces another log. Hold to this:

1. **Never open a log or a filelist with Read first.** Use **Grep** to locate a line number, then
   **Read** a bounded window around it.
2. **Grep and Read work on files, not on chat text.** If the engineer has pasted a log tail rather
   than a path, ask for the path on disk, or ask them to save what they pasted to a file and give you
   that path. Until a path exists you may reason over the pasted lines by eye — but say that is what
   you did. You have not searched the log, only the fragment you were shown.
3. Per iteration the budget is one **Grep** for the fatal markers from the slots table, one **Grep**
   for the pass marker, and at most two **Read** windows of about 80 lines each.
4. To locate a config knob or a tier directory, **Grep** for the knob name or **Glob** the tier path
   rather than reading the file — then **Read** at most 40 lines either side of the hit.
5. If a **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it before reading
   anything.
6. **Stopping rule.** If two windowed **Read** calls have not confirmed the signature, report that
   iteration as inconclusive. Do not open a third file, and never infer a signature from an earlier run.

## Procedure

### 1. Recover the signature that must be preserved

Derive the baseline signature from the original failing log using
`_shared/failure-signature-schema.md`. **Grep** the log for the fatal markers from the slots table,
take the **lowest** line number, then **Read** a window starting about 60 lines before it. Write the
four fields down explicitly before anything is changed.

Everything below is measured against this string. If you cannot produce a signature from the original
log, shrinking has nothing to preserve — stop here and say so.

### 2. Establish determinism before shrinking anything

If the failure is not reliably reproducible, a shrink step that "fixes" it has told you nothing.

Ask the engineer to repeat the unmodified test three times and to give you the **path of each log**.
A pasted tail is useful context but is not searchable — see budget rule 2. Then classify with one
marker **Grep** per log:

- **Deterministic** — same seed, same signature, same simulated time of failure. Ideal.
- **Signature-stable** — same signature, but the failure time or the transaction index moves between
  runs. Usually fine to shrink, but time-window shrinking becomes risky.
- **Seed-dependent** — fails on one seed only. Ask for the failing seed to be pinned and recorded as
  part of the reproducer, not as an aside.
- **Intermittent** — fails roughly 1 run in N. Ask the engineer for the observed rate and record N,
  along with how many runs that rate was measured over. Every later step is judged against that N.

These four class names are local to this skill. `_shared/failure-signature-schema.md` covers the
signature only; if a second skill ever needs to filter on determinism class, move this list there
rather than restating it in a second vocabulary.

**Where run-to-run nondeterminism actually comes from.** For a fixed executable and a fixed seed, the
event schedule and X resolution are expected to be identical run to run — that expectation is exactly
what seed-based reproduction rests on. So when repeats of an *unmodified* test genuinely differ, look
at what sits outside that guarantee:

- multi-core, multi-threaded or partitioned simulation, where the partitioning or the merge order is
  not fixed run to run
- calls out to C through DPI or PLI, and uninitialised memory or pointer-dependent behaviour in C,
  C++ or SystemC models
- co-simulation with an emulator, a host process, or anything else carrying its own clock
- anything derived from wall-clock time or host load — timeouts scaled to real time, timestamps
  printed into the log, licence or queue wait

Two things that are commonly blamed and usually innocent. **X differences between two runs are almost
always a build difference, not a schedule difference** — a different executable, a different compile
define, a different model revision. Confirm the build tag from the determinism-controls slot before
anyone goes hunting X initialisation in a design that is behaving perfectly deterministically. And
**stimulus re-ordering is not a determinism failure at all** — it is a comparability failure across a
change, which step 5 and the Gotchas handle. It cannot make two runs of the unmodified test differ.

### 3. Record the baseline cost

Use **Grep** on the original log for the simulated time of failure, and for the end-of-run summary
line from the slot table if that slot is filled. If it is unfilled, say so and record the baseline
without it — do not guess what the line looks like.
Ask the engineer for wall-clock duration, tier, and whether a build was needed — none of those are
readable from here, so if the engineer does not report one, leave that part of the baseline empty
rather than estimating it. A shrink with no baseline is a claim, not a measurement.

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
   for the failing component name to check it even exists at that tier. This axis often does not pay,
   and a reproducer that stays at its original tier is still a success if it meets the runtime budget.
5. **Test length.** Trim warm-up, preceding phases, training or calibration sequences. Last, because
   these are the parts most likely to be carrying the real precondition.

Propose exactly one change — name the axis, the change, and the expected outcome. Then ask the
engineer to make that one change, run it, and give you the path of the resulting log.

### 5. Re-check the signature after every single change

**Grep** the new log at the path the engineer gave you, **Read** one bounded window, derive the
signature and compare it to the baseline **field by field**. Accept the step only when all four
fields match exactly.

- All four match → keep the change, update the running config diff, propose the next step.
- Any field differs → revert. Do not carry a changed signature forward.
- No failure at all → revert, and treat the change as a sensitivity, not a success.

For an intermittent failure, one passing run is not evidence. Ask for enough repeats to be meaningful
against the recorded N before accepting the step, and record how many repeats you actually got.

### 6. Recognise when shrinking has changed the bug

Shrinking that changes the bug is worse than not shrinking, because it looks like progress. Treat any
of these as a stop-and-revert:

- the signature's `where` moved, even though `what` normalises identically
- the failure now occurs earlier than the **simulated time** of the cause line in the original log
- an intermittent stopped being intermittent — it now fails every run, or it stopped failing across
  every repeat you could afford. Record the number of repeats; do not claim the rate moved by any
  particular factor. At 1 in N you would need several hundred runs to measure that, which the Gotchas
  say you cannot afford, so treat the rate as unmeasured and judge the step on the signature alone.
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

Author both blocks. Leave a field empty rather than filling it from assumption.

The first block uses the field names `dv-sim-log-first-error` emits, so a ticket produced here can be
matched mechanically against one produced there:

```
signature   : <phase>|<kind>|<where>|<what>
cause       : <verbatim cause line, with line number>
first err   : <verbatim first fatal line, with line number>
phase       : compile | elab | run | finalise | post
class       : design | infrastructure | unknown
run id      : <whatever identifies this run for us, from the run-identity slot>
to repeat   : <invocation taken from our conventions, or empty>
log         : <path, and the line range worth reading>
notes       : <anything the recipient would otherwise have to rediscover>
```

The second block is this skill's local extension:

```
determinism : deterministic | signature-stable | seed-dependent | intermittent 1 in N
baseline    : <tier; wall clock; simulated time to failure — empty if not reported>
reproducer  : <tier; wall clock; simulated time to failure — empty if not reported>
config diff : <every change from the standard test, including the cosmetic ones>
sensitivity : <changes that made it vanish or moved the signature>
not tried   : <axes deliberately left alone, and why>
coverage    : <which numbers you read out of a log yourself and which the engineer reported; how
               many axes were tried; how many repeats each accept or revert rests on>
```

`not tried` matters more than it looks. It stops the recipient repeating work you already did and
stops them assuming an axis was clean when it was simply never touched.

**State the coverage — an unstated shortcut is far worse than a stated one.** Wall clock, tier and
build status can only ever be reported to you, never measured here, and a reproducer accepted on two
repeats of a 1-in-40 intermittent is a guess wearing a measurement's clothes. Say which it was.

## Gotchas

- **Starting later from a checkpoint is not the same run.** A restored state already holds values a
  cold start reaches through a specific sequence. A bug that depends on initialisation, on X
  resolution, or on a one-time calibration quietly disappears when you restore past it.
- **Turning the waveform dump off can change the failure**, and turning it on can too. Dumping
  perturbs scheduling in some flows and suppresses optimisations in others. If the bug only appears
  with dumping enabled, that is a finding to write down, not an inconvenience to work around.
- **Changing the stimulus re-orders the random stream — but not in the way people usually assume.**
  Adding or removing a `randomize` call, or changing the constraints on a sequence, changes every
  value that sequence draws afterwards, so "same seed" no longer means same stimulus for it. UVM,
  though, seeds each object's generator from its full hierarchical name, so adding or removing an
  unrelated component does not by itself perturb an existing component's stream — do not abandon a
  configuration shrink on that assumption alone. Either way, decide it by comparing signatures from
  two actual logs, not by reasoning about seeds.
- **The unrelated agent you switched off is often not unrelated.** Shared bus arbitration, credit
  return, and backpressure mean background traffic can be the precondition. If the failure needs it,
  you have just found the mechanism.
- **Dropping down a tier removes real reset, clock and power sequencing.** Block benches typically
  drive an idealised reset and one clean clock. A reset-domain or clock-crossing bug will not follow
  you down, and its absence at block level proves nothing.
- **Twenty clean runs mean nothing if the original rate was 1 in 50.** For intermittents, the number
  of repeats needed to call a step good grows with N, and most people stop far too early. If you
  cannot afford the repeats, say the rate is unmeasured rather than implying it held.
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

- the shrunk reproducer was **confirmed by an actual log at a path you searched**, not predicted from
  the shrink reasoning and not read only from a pasted fragment
- all four signature fields match the baseline character for character
- the config diff lists every change, including the ones that felt too small to mention
- the determinism class of the reproducer is the same as the baseline's, or the change is called out
- `to repeat` is taken from the team's real convention, or left empty
- `coverage` names every number that was reported rather than measured, and the repeat counts behind
  each verdict

A wrong answer looks like "reduced from four hours to three minutes", where the three-minute version
fails on a different component, or fails deterministically when the original failed one run in forty,
or needs a file that exists only in the author's area. It reads as a triumph and bounces in a day.

## Done when

The recipient reproduces your signature once, using your two handoff blocks and nothing else, inside
the runtime budget — at whatever tier the shrink actually landed on.
