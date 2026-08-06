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
  semiskill-version: 1.4.1
  semiskill-review-by: 2027-07-02
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

A fourth pack-wide fact has no row above because this skill never narrows it: the profile's **Rerun
convention**. Step 8 reads it straight from `_shared/team-profile.md` for the handoff's repeat line.

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
3. Per shrink iteration the budget is one **Grep** for the fatal markers from the slots table, one
   **Grep** for the pass marker, and at most two **Read** windows of about 80 lines each. Step 5
   spends both of those **Grep** calls every time; neither is optional. Four named groups sit outside
   that per-iteration budget, and nothing else does:
   - **Step 2, determinism.** One **Grep** per determinism log, its pattern alternating the fatal
     markers with the pass marker so one call classifies the log. Five logs — three same-seed
     repeats and two different-seed runs — so five **Grep** calls.
   - **Step 3, baseline.** One **Grep** of the original log for the simulated time of failure, and —
     only when the End-of-run summary slot is filled — one **Grep** of that same log for that line.
   - **Step 7, reproducer.** Those same one or two **Grep** calls once more, against the final
     accepted log.
   - **Step 4, non-log lookups.** At most one lookup per proposal, priced in rule 4, and only on the
     two axes that need one.
4. **Non-log lookups, priced.** To locate a configuration knob or a tier directory, **Grep** for the
   name or **Glob** the path rather than reading the file — then **Read** at most 40 lines either
   side of the hit. One lookup is at most one **Glob**, one **Grep** and one 40-line **Read**. Two
   places spend one and no others do: the **Configuration** axis, against the paths in the Config
   surface slot, and the **Hierarchy** axis, against the paths in the Testbench tiers slot. These are
   configuration and filelist text, never logs, and they are not charged against rule 3's log budget.
5. If a **Grep** returns more than about 200 hits, the pattern is too broad. Narrow it before reading
   anything.
6. **Stopping rule.** If two windowed **Read** calls have not confirmed the signature, report that
   iteration as inconclusive. Do not open a third file, and never infer a signature from an earlier run.

## Procedure

### 1. Recover the signature that must be preserved

Derive the baseline signature from the original failing log using
`_shared/failure-signature-schema.md`. **Grep** the log for the fatal markers from the slots table,
take the **lowest** line number, then **Read** a window starting about 60 lines before it. Write the
four fields down explicitly before anything is changed. From that same window, record the **cause
line** verbatim with its line number — the handoff block asks for it, and step 6 checks every later
log against it.

Everything below is measured against this string. If you cannot produce a signature from the original
log, shrinking has nothing to preserve — stop here and say so.

**The `phase` token travels with the signature; do not re-derive it.** It is the signature's own first
field, and the handoff block in step 8 spells it with the same five tokens
`_shared/failure-signature-schema.md` accepts, so a phase column joins against a signature prefix.
Copy it across unchanged. Check only the one pair people get wrong: `finalise` is the simulator still
running — its end-of-run report and final-phase checks, lines that sit in this same log after the last
design activity; `post` is a step that ran after the simulator exited, and its diagnostics live in a
file this log does not contain. A `post` failure can still be shrunk here, but only by shrinking the
simulation that fed it — say that is what you did. A `compile` or `elab` phase means you are in the
wrong skill: there is no stimulus to bisect, and the routing above sends it elsewhere.

### 2. Establish determinism before shrinking anything

If the failure is not reliably reproducible, a shrink step that "fixes" it has told you nothing.

**Say the seed policy out loud when you ask, because the classes below turn on it.** Most regression
harnesses draw a fresh seed per invocation unless one is pinned, so "repeat the test three times"
usually means three different seeds — under which the Deterministic class can never be observed and
seed-dependence can never be isolated. Ask for two things instead, and for the **path of each log**:

- **three repeats with the original failing seed pinned**, taken from the Determinism controls slot
  and held fixed along with everything else that slot names — plusargs, build tag, model revision
- **two further runs on deliberately different seeds, each seed recorded**, not whatever the harness
  happens to generate. Two is the minimum that can distinguish "this seed only" from "any seed"; it
  is not a rate measurement and must not be reported as one.

A pasted tail is useful context but is not searchable — see budget rule 2. Then classify with one
**Grep** per log, its pattern alternating the fatal markers with the pass marker. Classify from the
**matched lines themselves** — the marker hit carries the message and usually the time, which is all
four classes need. Do not derive a full signature per repeat: that costs a windowed **Read** per log
and the budget does not carry five of them. Step 1's baseline is the only signature derived here.

- **Deterministic** — the three pinned-seed repeats hit the same fatal marker, with the same message
  and the same simulated time. Ideal.
- **Signature-stable** — same fatal marker, and the same message once the schema's normalisation is
  applied by eye, but the time or the transaction index moves across the three. Usually fine to
  shrink, but time-window shrinking becomes risky, and the movement is itself a finding — read the
  nondeterminism list below before proposing anything.
- **Seed-dependent** — the pinned seed hits the fatal marker every time and both recorded alternative
  seeds hit the pass marker instead. Ask for the failing seed to be pinned and recorded as part of the
  reproducer, not as an aside.
- **Intermittent** — the pinned seed hits the fatal marker only some of the time, with everything
  else held fixed: roughly 1 run in N. Ask the engineer for the observed rate and record N, along
  with how many runs that rate was measured over. Five logs cannot measure N — say it came from the
  engineer. Every later step is judged against that N.

If a repeat hits a *different* fatal marker, or the same one with a message that will not normalise
to the baseline, you are not looking at one failure and there is nothing here to shrink yet. Say so
and send it back to triage rather than picking whichever run you like best.

If a log carries neither the fatal markers nor the pass marker it did not run to completion, and it
classifies nothing. Ask for it to be repeated rather than counting it as a pass or as a miss.

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

### 4. Propose one shrink step, working the axes in order

Work the axes in this order. Axes 1 to 3 are ordered by cost: each is cheaper to try and more likely
to pay than the next. Axes 4 and 5 are not on that scale and are ordered by **how loudly they fail**.
Hierarchy is the most expensive item here — it usually means standing up a different environment, and
its own text below says it often does not pay — but when it is wrong you find out at once and
unmistakably. Test length is cheap and still comes last, because when it is wrong it is silent: the
warm-up you trimmed was the precondition, the failure simply stops happening, and you spend the next
two iterations recording a sensitivity that is an artefact of your own edit.

Every bullet below is a proposal you put to the engineer, not a change you make.

1. **Time window.** Propose cutting the run so it stops shortly after the failure time. If the flow
   supports a saved checkpoint, propose restoring close to the failure instead of starting cold.
   Biggest win, lowest effort, highest risk of changing initialisation — see Gotchas.
2. **Configuration.** Propose switching off what is not implicated — unrelated agents, coverage
   collection, scoreboards for other interfaces, debug verbosity, protocol checkers in untouched
   blocks. The **Config surface** slot names where our test configuration lives and which knobs take
   effect without a rebuild: **Grep** those paths for the knob you mean to change, to confirm it
   exists and is set where you assume, then **Read** at most 40 lines around the hit — budget rule 4.
   Propose runtime knobs over anything that forces a rebuild. If that slot is unfilled, propose the
   change by description and say you could not confirm where the knob lives or whether it rebuilds.
3. **Stimulus.** Propose reducing the number of transactions, then constraining randomisation toward
   the pattern that failed, then replacing the random sequence with a directed replay of the observed
   transactions. Propose these before anything else that would disturb the random stream.
4. **Hierarchy.** Propose moving down a tier — full chip to subsystem to block — only if a lower tier
   can actually drive the same stimulus. Use **Glob** on the paths named in the **Testbench tiers**
   slot and **Grep** for the failing component name to check it even exists at that tier — the slot
   also says what stimulus each tier can reach, which is what decides this. This axis often does not
   pay, and a reproducer that stays at its original tier is still a success if it meets the budget.
5. **Test length.** Propose trimming warm-up, preceding phases, training or calibration sequences.
   Last, because these are the parts most likely to be carrying the real precondition.

Propose exactly one change — name the axis, the change, and the expected outcome. Then ask the
engineer to make that one change, run it, and give you the path of the resulting log.

### 5. Re-check the signature after every single change

At the path the engineer gave you, spend both of budget rule 3's per-iteration calls: **Grep** the new
log for the fatal markers, and **Grep** it for the **pass marker**. Both, every time — the absence of
a fatal marker is not a pass, and this is the only step that can tell those apart. Then **Read** one
bounded window, derive the signature and compare it to the baseline **field by field**. Accept the
step only when all four fields match exactly.

- Fatal marker present, all four fields match → keep the change, update the running config diff,
  propose the next step.
- Fatal marker present, any field differs → revert. Do not carry a changed signature forward.
- No fatal marker, **pass marker present** → a genuine clean run. Revert, and treat the change as a
  sensitivity, not a success.
- No fatal marker and **no pass marker either** → the run did not finish. A hung, truncated,
  out-of-disk or licence-starved run looks exactly like a pass to anyone checking only for errors,
  and counting it as one is the most expensive mistake in this loop. This is not a shrink result:
  say so, ask for the run to be repeated, and if it repeats, record the iteration as
  `infrastructure` per step 8 rather than as a sensitivity.

For an intermittent failure, one passing run is not evidence. Ask for enough repeats to be meaningful
against the recorded N before accepting the step, and record how many repeats you actually got.

### 6. Recognise when shrinking has changed the bug

Shrinking that changes the bug is worse than not shrinking, because it looks like progress. Treat any
of these as a stop-and-revert:

- the signature's `where` moved, even though `what` normalises identically
- the ordering **inside the new run** changed: the cause line you recorded in step 1 no longer
  appears before the failure in the new log, or no longer appears at all. Decide this within the one
  window step 5 already read — the cause still precedes the failure there, or it does not. If that
  window does not settle it, call the iteration inconclusive under budget rule 6 rather than opening
  another file. Never decide it by comparing the two runs' simulated timestamps to each other:
  axis 3 and axis 5 compress simulated time by construction, so a perfectly good shrink routinely
  fails at an earlier absolute time than the original did, and the schema normalises times to `T` so
  the signature cannot move on timing alone. The two runs' clocks are only comparable on axis 1, and
  then only when a checkpoint restore has preserved the original time base — if it has, an earlier
  absolute failure time is worth investigating; otherwise it means nothing. The Gotcha on switching
  off checkers elsewhere is this same rule from the other side.
- an intermittent stopped being intermittent — it now fails every run, or it stopped failing across
  every repeat you could afford. Record the number of repeats; do not claim the rate moved by any
  particular factor. The repeats needed to measure a rate change grow with N, and the Gotchas say
  that is what you cannot afford — so treat the rate as unmeasured and judge the step on the
  signature alone.
- the failure still appears with the block under test stubbed out or held in reset. This is the
  sharpest evidence available here, and it is about **ownership**: whatever is failing is not the
  block you were shrinking. Step 8 says what it does and does not do to `class`.
- the run now ends on a different marker — a timeout where there was a miscompare, or the reverse.
  Decide it from the two **Grep** calls step 5 already spent; do not open anything further. One fatal
  marker swapped for another fatal marker is the bug moving, and belongs in `sensitivity`. *Neither*
  marker firing is not the bug moving at all — the run did not finish, step 5 says what to do with
  it, and step 8 turns a repeat of it into `class : infrastructure`. That second case is the one that
  most often masquerades as a shrink finding, because a log with no errors in it reads like success.

Each of these is information. The change that made the bug move is describing the mechanism; record
it in the sensitivity line of the handoff rather than discarding it.

### 7. Decide to stop

Stop at the first of these, and say which one:

- the reproducer meets the runtime budget slot
- three consecutive proposals in a row were reverted
- every remaining element is load-bearing — each removal you have tried changed the signature
- the time box for shrinking is spent

Before claiming the first of those, measure the reproducer the same way step 3 measured the baseline,
against the last accepted log: **Grep** it for the simulated time of failure, and — only if the
End-of-run summary slot is filled — **Grep** it for that line. Wall clock, tier and build status can
only come from the engineer; leave empty whatever they do not report. A measured baseline against an
unmeasured reproducer is not the comparison the handoff block promises.

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
to repeat   : <invocation from the profile's Rerun convention, or empty>
log         : <path, and the line range worth reading>
notes       : <anything the recipient would otherwise have to rediscover>
```

Take the repeat line from the team profile's **Rerun convention**, exactly as `dv-sim-log-first-error`
does; if that entry is unfilled, leave the field empty rather than inventing an invocation. This skill
has no rerun slot of its own, so there is nowhere else that answer can come from.

**`class` is carried, not re-derived — and say which.** Shrinking does not re-triage the failure, so
the default is to copy the value from the triage that produced your baseline signature
(`dv-sim-log-first-error` assigns it in its own step 3) and to write "class carried from triage" in
`notes`. Depart from that only on evidence this skill actually produced:

- **`infrastructure`** — a step-5 iteration came back with neither the fatal markers nor the pass
  marker, and did so again on repeat; or the engineer reports the run died on licence, queue, host or
  disk, which you cannot see from here and must attribute to them. The shrink result is void until a
  complete run replaces it; say the class describes the run you have, not the bug you were shrinking.
- **`design`** — carried from triage, and nothing in steps 5 or 6 contradicted it. Stubbing the block
  out and still seeing the failure (step 6) does *not* flip this on its own: it says the failure is
  not where you thought, which changes the owner, not the design/infrastructure line. Put that in
  `sensitivity` and say the class is unchanged.
- **`unknown`** — the triage never assigned one, or step 6 moved the signature and you reverted to a
  state nobody has re-triaged. Blank is not a substitute; `unknown` is the honest token.

If two engineers could read your evidence and fill this field differently, you have not said enough.
A wrongly carried `class` routes the ticket to the wrong owner, and that costs a day before anyone
looks at the shrink at all.

The second block is this skill's local extension:

```
determinism : deterministic | signature-stable | seed-dependent | intermittent 1 in N
baseline    : <tier; wall clock; simulated time to failure; and the resource figures from the
               end-of-run summary line if that slot is filled — each part empty if not reported>
reproducer  : <the same four parts for the final accepted run, measured the same way in step 7>
config diff : <every change from the standard test, including the cosmetic ones>
sensitivity : <changes that made it vanish or moved the signature>
not tried   : <axes deliberately left alone, and why>
coverage    : <which numbers you read out of a log yourself and which the engineer reported; how
               many axes were tried; how many repeats each accept or revert rests on>
```

`not tried` matters more than it looks. It stops the recipient repeating work you already did and
stops them assuming an axis was clean when it was simply never touched.

**Then satisfy the ticket, without disturbing either block.** The two blocks above are fixed: the
first is a join key with `dv-sim-log-first-error` and the second is compared across shrinks. Whatever
our own ticket demands on top of them is listed in the **Handoff template** slot — append those as
further lines *below* the second block. Never rename a field, drop one, or fold a ticket field into
one of the blocks: a ticket field that asks the same question under a different name gets its own
line, because a renamed field silently breaks the mechanical match this ordering exists to give you.
If that slot is unfilled, say plainly that the ticket may require fields you have not supplied, and
name whoever fills the ticket in as the person to ask.

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
- the final accepted log was checked for the **pass marker** as well as the fatal markers, so a run
  that merely stopped early is not being handed over as a clean one
- the determinism classification rests on **three repeats of one pinned seed** plus at least two other
  recorded seeds, and the block says which seed is the reproducer's
- all four signature fields match the baseline character for character
- the config diff lists every change, including the ones that felt too small to mention
- the determinism class of the reproducer is the same as the baseline's, or the change is called out
- `class` says in `notes` whether it was carried from the triage or revised here, and on what
- `to repeat` is taken from the profile's **Rerun convention**, or left empty
- anything the ticket needs beyond the two blocks is appended below them, with no field in either
  block renamed or removed to make room
- `coverage` names every number that was reported rather than measured, and the repeat counts behind
  each verdict

A wrong answer looks like "reduced from four hours to three minutes", where the three-minute version
fails on a different component, or fails deterministically when the original failed one run in forty,
or needs a file that exists only in the author's area. The quieter wrong answer is a three-minute run
that no longer fails *and no longer passes* — it dies early on something the shrink broke, nobody
Grepped for the pass marker, and it is handed over as a success. Both read as a triumph and bounce in
a day.

## Done when

The recipient reproduces your signature once, using your two handoff blocks and nothing else, inside
the runtime budget — at whatever tier the shrink actually landed on.
