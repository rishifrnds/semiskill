---
name: dv-tool-version-migration
description: Re-baseline pass rate, coverage and performance across a simulator, UVM or VIP version change, and separate a real regression from seed noise, a stricter new diagnostic and coverage-model churn. Use when IT is retiring the simulator release you are on, when a VIP drop lands mid-project, when moving from UVM 1.2 to the 1800.2 line, when the nightly fell from 96 percent to 88 percent the morning after a tool bump, or when someone asks whether coverage really dropped or the model just changed.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Simulator, UVM and VIP Version Migration with Re-Baselining
  semiskill-function: design-verification
  semiskill-role: dv-infra-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.1.1
  semiskill-review-by: 2027-08-27
  semiskill-tags: migration, tool-version, uvm, vip, re-baseline, coverage, performance, regression
---

# Simulator, UVM and VIP Version Migration with Re-Baselining

A tool bump rarely breaks an environment outright. What it does is make every number you had stop
meaning what it meant — pass rate, coverage and runtime all move, and none of those movements is
evidence of anything until you know how far they move when nothing has changed at all. The expensive
mistake is to read the first red nightly on the new release as a list of bugs, spend a week on it,
and find that most of it was a different point in the random space plus a coverage model that quietly
gained three hundred bins.

The output is **three re-baselined numbers that each carry a denominator, a classified list of the
failures that are genuinely new, and a debt list** — not a claim that the new version is good. This
procedure reads summaries, coverage reports, release notes and saved logs. It cannot start a
simulation, merge a coverage database, time anything, or open a vendor portal; every step needing one
of those ends in a named handoff.

## When to use something else

- The new release will not **compile or elaborate** our source — `dv-build-filelist-hygiene`, and it
  is the most common first day of a migration.
- **One** failing log on the new version, needing its first error and a signature —
  `dv-sim-log-first-error`.
- A whole night of new-version failures to bucket and route — `dv-regression-triage-routing`; step 5
  hands it the tail of the candidate list.
- Shrinking one migration failure into something a vendor will accept — `dv-minimal-reproducer`.
- The register model was regenerated against a new generator in the drop — `dv-ral-bringup`.
- You cannot yet say where the summaries or coverage output land — `dv-repo-orientation` first.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Axis inventory | [[FILL: which of simulator, UVM and VIP is moving, the from-version and to-version of each, and whether our UVM is the simulator's built-in package or compiled from our own source]] | DV infra owner |
| Version banners | [[FILL: the exact lines our simulator, the UVM package and each VIP print at start-up to name their own version]] | DV infra owner |
| Migration baseline | [[FILL: which regression and which seed set is frozen as this migration's reference, and whether its summary, coverage report and logs from the OLD version are still on disk]] | DV lead |
| Release notes | [[FILL: where the incoming version's release notes and deprecation list land, and whether they are files we can read or a vendor portal only a person can open]] | DV infra owner |
| Deprecation switch | [[FILL: which compile-time legacy-API or deprecation define our build sets today, and who decides when it comes off]] | DV infra owner |
| Coverage report format | [[FILL: what one covergroup row of our coverage report carries — bins covered, bins total, weight, exclusions applied — and whether our tool can report exclusions that matched nothing]] | coverage owner |
| Performance figures | [[FILL: which figures our end-of-run summary prints — simulated time, wall clock, peak memory — and where compile and elaboration times are recorded]] | DV infra owner |
| Farm limits | [[FILL: the memory and wall-clock limits our compute farm enforces, and what a job killed for exceeding one looks like in the regression summary]] | DV infra owner |
| Vendor case route | [[FILL: how we open a case with a tool or VIP vendor, and what a reduced test case must contain before they will accept it]] | DV infra owner |

Nothing above is a pack-wide fact, deliberately — this runs on top of `_shared/team-profile.md`
rather than duplicating it. Seven profile rows are read straight from there and must not be
re-asked: **Regression summary** and **Coverage output** for where each side's artifacts land,
**Build log location** for the compile and elaboration output step 6's first row quotes from,
**Fatal markers** and **Pass marker** for step 2's marker check, **Infra markers** for the
killed-job row in step 6, and **Sign-off** for who accepts the result in step 10.

Four rows above sit next to facts recorded elsewhere and are **not** the same fact. **Version
banners** is not the profile's **Simulator** row — that says which simulator we run and how a build
is launched, while this asks what the tools print *about themselves at run time*, the only evidence
of what actually elaborated. **Migration baseline** is not `dv-regression-triage-routing`'s *Baseline
regression*, which picks last night's comparison for novelty ranking; this pins a frozen old-version
reference that has to survive the switch. **Release notes** is the vendor's account of the incoming
version; the profile's **Known-issue list** is ours, about our design. **Performance figures**
contains what `dv-minimal-reproducer` asks under *End-of-run summary* and is wider than it: the
end-of-run figures are the same question and that answer transfers unchanged, but this row adds one
clause that skill never asks — where compile and elaboration times are recorded. Copy the first
half; answer the second half here, or step 9 has one number where it needs three.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented banner string makes
step 2 conclude the wrong version elaborated, and every number below it then measures something
nobody asked about.

## Retrieval budget — read this before opening anything

A migration produces two of everything and both sides are large. These caps are for a **single pass
over a single axis**; a compound migration is several passes, not a bigger budget.

1. **Grep, Read and Glob work on files on disk.** Pasted release notes, a coverage percentage read
   out in a meeting and a screenshot of a summary are all unsearchable. Ask for the path, or for the
   text to be saved to a file and be given that path. What stays unsearchable is reported as *told to
   you*, never as measured.
2. **Glob first, at most six patterns, one directory each** — two summaries, two coverage reports,
   the release notes, and the new side's build log under the profile's Build log location. A
   repository-wide pattern truncates, and a truncated count is not a count.
3. **Summaries: at most three** — old side, new side, and step 4's old-side control — each one
   **Grep** for the fail-row pattern plus at most **two windowed Reads of about 100 lines**.
4. **Version and marker proof: one Grep per side** (step 2), against one representative log, its
   pattern alternating the banner strings with the profile's fatal and pass markers. Two calls, and
   they are the only ones that check gets.
5. **Coverage reports: one Grep and one windowed Read of about 60 lines per side** (step 8). Never
   Read one whole — a block-level report runs to thousands of covergroup rows.
6. **Failure logs: at most five opened** (step 5), each **two Greps** — markers, then the earliest
   fatal line — and **one windowed Read of about 80 lines**.
7. **Release notes and deprecated-symbol sweep** (step 7): at most **two Greps and two windowed Reads
   of about 60 lines** in the notes, plus at most **five Greps of our own source**, one named symbol
   per call and one directory per call.
8. **Performance figures** (step 9): at most **one Grep and one windowed Read of about 40 lines per
   side**, over the end-of-run summary and build-log paths you were handed, for whichever figures
   the **Performance figures** slot names. Repeats are the reason this cap is small: if the three
   repeats per side sit in six separate files, ask for the collated figures and record them as *told
   to you* rather than spending a Read per repeat.
9. **Build logs: at most two Greps, one per side.** The two logs are in different places by
   construction — the new side's found by one of rule 2's Glob patterns under the profile's **Build
   log location**, the old side's at whatever path the engineer hands you — so no single call spans
   both and each side needs its own. Alternate each pattern the way rule 4 does, so one call answers
   everything that side owes: the new side's carries step 6's first-row build diagnostic, the
   X-handling and optimisation switch lines step 6's tool-semantics row compares, and the
   **Deprecation switch** define step 7 records; the old side's carries the same switch lines and
   define, there being no new-release diagnostic on that side to quote. Compile and elaboration
   output does not always land in the per-test log this skill already opens — the profile keeps
   **Build log location** as its own row for exactly that reason. These two calls are the only
   budgeted way to quote a build diagnostic, a switch line or the define's state; past them all
   three are asks, not quotes.
10. If any **Grep** returns more than about 200 hits the pattern is too broad — narrow it first.
11. That is roughly 28 Greps, 17 Reads and 6 Globs: a full session's attention, spent once.
    **Stopping rule** — stop when the three baselines each carry a denominator and the opened logs
    are classified, or when these caps are spent. Past that it is a second pass, not more reading.
12. **State what you covered**: which numbers you read from a file yourself, which the engineer
    reported, and how many failures were never opened.

## Procedure

### 1. Name exactly what moved, and freeze everything else

Read the **Axis inventory** slot and write the axes down with from-version and to-version. One axis
per pass — two moving together cannot be attributed, and if the schedule forces both, that is a
compound baseline and must be labelled as one rather than reported as a simulator result. The trap is
in that slot's second half: where UVM is the simulator's built-in package rather than our own
compile, **bumping the simulator bumps UVM underneath**, so a migration everyone calls one axis is
two. Settle that before any numbers are collected.

Then freeze RTL revision, testbench revision, filelists, seed set, coverage exclusion files and farm
queue. **Ask the engineer to pin both sides to one revision on a branch** and confirm which revision
that is. A branch that also takes a week of RTL commits produces a diff nobody can read.

### 2. Prove which versions elaborated, and that the markers still match

**One Grep per side**, against one representative log each, alternating the **Version banners**
strings with the profile's Fatal markers and Pass marker. Two calls, two questions.

Which versions ran: the module someone loaded is not evidence — a stale wrapper, an environment
default, a hard-coded path inside a filelist or a cached compiled library can each serve a version
other than the one requested. Quote the banner lines verbatim with path and line number and check
them against step 1's axis list, including the built-in UVM question.

Whether our instrumentation survived: if the fatal or pass marker text changed on the new side, every
pass rate below measures the wrong string and a broken regression reads as green. Not finding the
markers here is a finding, not a null result.

### 3. Locate the artifacts, and confirm the old side still exists

**Glob** under the profile's Regression summary, Coverage output and Build log locations, and under
whatever directory the **Release notes** slot names — six patterns at most, one directory each,
which is rule 2's list exactly. The build log is the one people forget to Glob for, and step 6's
first row cannot quote a compile diagnostic without it; if the profile's **Build log location** row
is blank because compile output lands in the same place as everything else, say so here and spend
that pattern elsewhere. Glob for the release notes here even though step 7 is where they are read:
if that slot points at a vendor portal rather than a directory the pattern returns nothing, and you
have learned now — while there is still time to ask — that step 7 starts from a handoff instead of
a path. Then check the **Migration baseline** slot's second half: are the old
version's summary, coverage report and representative logs still on disk? If not, say so and stop
claiming a comparison — everything below becomes a description of the new version alone. Once the
old release is uninstalled or delicensed the comparison cannot be rebuilt at any price.

### 4. Re-baseline the pass rate, with a denominator and a noise floor

**Read** the two summaries under budget rule 3 and record, per side, passed, failed, and whatever the
summary reports as unrun, skipped or killed, against the total. Never write a bare percentage.

Then the control — the step that gets skipped and the one that makes the rest honest. **Ask the
engineer to repeat the old version once more over a different seed set of the same size** and give
you that summary's path. The spread between the two old-side runs is this regression's noise floor,
and **a new-versus-old difference smaller than that spread is not a finding**. Treating one as a
finding is exactly how a migration acquires a week of imaginary work. If the control cannot be
afforded, say the noise floor is unmeasured and demote every rate difference to a candidate; do not
substitute a remembered figure from an earlier month, since the seed set, test list and farm have all
moved since.

### 5. Diff the failure sets — not the seeds

**The same seed is not the same stimulus across versions.** Reproducibility is a property of a fixed
executable: same build, same seed, same plusargs redraws the same values. Across a simulator or UVM
change it does not hold, because the constraint solver's internal ordering is an implementation
detail, and because any change to the number or order of randomization calls the library itself makes
shifts every value drawn afterwards. A paired-seed diff across the boundary compares two samples from
one distribution, not the same test twice.

From the two summaries already open, form three groups and treat them differently:

- **Fails on both** — pre-existing. Not the migration's problem, and not evidence it is clean.
- **Fails on new only** — the candidate list, and the input to step 6.
- **Fails on old only** — the group nobody looks at. Something that stopped failing was either fixed
  by the new version or hidden by it, and only one of those is good news.

Sign what you can afford: at most five logs (budget rule 6), each yielding one signature per
`_shared/failure-signature-schema.md` — same field order, same normalisation rules, `?` for any field
not traceable to text in the log. Spend the five on candidates whose summary rows look unlike each
other, not on the first five in the table. Everything unopened is **unsigned**; report it as a count
grouped by summary status string and hand it to `dv-regression-triage-routing`.

### 6. Classify each new-only failure

Eight classes going to eight different places. The `Proves it` column says what settles each row;
where that is a person or a machine, the row ends in a handoff.

| What you are looking at | Check first | Class | Proves it |
|---|---|---|---|
| the build fails on the new release, source unchanged | whether the diagnostic names a construct or a removed symbol | new diagnostic | budget rule 9's new-side Grep, quoting the first diagnostic, then route to `dv-build-filelist-hygiene` |
| one test, new-only, signature is a scoreboard miscompare | whether this seed even produced the same stimulus | seed noise until shown otherwise | rates over a seed population per side, per step 4 — never a single paired seed |
| a whole block's tests fail with one shared signature | whether a VIP default or knob changed in the drop | drop behaviour change | the release-notes entry quoted, or the VIP owner's answer |
| a protocol or assertion check fires that never fired before | whether that check is new in this drop | newly exposed, either way | ask the VIP owner; if the check is not new, the stimulus reached it for the first time and it is a real bug |
| X where the old release had a known value | each side's X-handling and optimisation switches | tool semantics change | budget rule 9's one Grep per build log, the two sides compared after both calls — or the switch settings from the DV infra owner where only one build log survives |
| failures with no testbench activity, or killed jobs | resource use against **Farm limits**, and the profile's Infra markers | infrastructure | the resource line in the summary, or the end-of-run figures |
| the new tool contradicts the standard, or itself | reduce it before anything else | tool or VIP regression | a reduced case via `dv-minimal-reproducer`, then the **Vendor case route** |
| everything passes and coverage jumped | whether the markers still match (step 2) | measurement broken | budget rule 6's marker Grep, spent on a known-failing new-version log rather than a sixth log |

The last row is the one that ends quietly: a migration that looks better than the baseline on every
axis is far more likely to be mismeasured than good.

Those eight classes are local to this skill. Two further columns are pack-wide, and each opened
failure carries both, assigned **here, per failure**, inside step 10's per-failure block — never
rolled up, because eleven new failures do not share one phase or one side of the design line.

**`phase`** is read off the first field of that failure's signature, not decided. The build row is
`compile` or `elab`, whichever the diagnostic came from; an ordinary new-only test failure is `run`.
Write `finalise` where the failure lands in the end-of-run report or the objection drain rather than
in the body of the test — the phasing, objection-ownership and report-server moves step 7 sweeps for
surface here first, and a residual objection or a changed severity count fails a run whose last
transaction passed. Write `post` where the failure exists only in something generated after the run
ended, such as step 8's zero-bin covergroup, whose evidence is in a report and in no log at all.

**`class`** is the coarse routing decision, and this skill's eight classes map onto it as follows.
`infrastructure` takes the infrastructure and measurement-broken rows, the tool-semantics row, the
tool-or-VIP-regression row, a job killed for exceeding **Farm limits**, and a confirmed drop
behaviour change — the environment moved, however much a memory blow-up or a changed VIP default
feels like a design bug. `design` takes the newly-exposed row once the VIP owner confirms the check
is *not* new, and the new-diagnostic row once the diagnostic is confirmed to name a construct of
ours: a stricter release reading the standard correctly puts the fix in our source. Everything still
waiting on its `Proves it` evidence is `unknown` — seed noise until step 4's rates settle it, a drop
or newly-exposed row until the VIP owner answers. Guessing beats nothing only in the wrong
direction: a premature `design` sends a tool bug to a block owner who cannot fix it.

### 7. Sweep the deprecated and removed APIs, and price the switch

For the UVM axis, and for a VIP drop that removes knobs. Start from **Release notes**. If the notes
and deprecation list are files on disk, **Grep** them for removal and deprecation wording and
**Read** at most two 60-line windows around the hits. If they live only behind a vendor portal, that
is a handoff: ask the engineer to extract the removed-symbol list into a file and give you the path.

Then at most five **Grep** calls over our own source, one named symbol per call, one directory per
call. The areas a UVM line move reliably disturbs — say which ours are in — are configuration and
resource access, the report server with its severity counts and message formatting, phasing and
objection ownership, sequence and sequencer entry points, and the factory registration macros. The
report server couples straight back to step 2: a reworked end-of-run summary changes the very strings
the triage flow greps for.

Finally the **Deprecation switch**: record its state on each side. Building green with legacy APIs
enabled is a loan, not a fix — the work moved rather than happened, and the release after this one
usually withdraws the switch along with the APIs. It belongs in step 10's debt line with an owner
from the profile's Sign-off row and a date, never in the pass column.

### 8. Re-baseline coverage — numerator, denominator, per covergroup

**Do not merge across the boundary.** A merge spanning two tool versions either refuses outright or
drops one side, and the silent case reads as a clean pass. Ask the engineer to generate each side's
report under its own version and give you both paths.

**Grep** each report once and **Read** one 60-line window per side (budget rule 5), guided by the
**Coverage report format** slot. Record, per covergroup, bins covered and bins total on both sides.
The top-level percentage is the last number to look at: adding one coverpoint raises the denominator
and lowers the percentage with no verification change whatever. Classify every mover as one of two
kinds, because only the second is a regression — **the model changed** (a new coverpoint or cross, a
split or renamed bin, a different automatic bin default, an ignore or illegal bin added or removed, a
restructured VIP coverage model), or **the verification changed** (same model, same bins, fewer hit).

Two mechanisms move the number invisibly. Exclusions and waivers are keyed on names, so a covergroup
rename or a hierarchy change leaves them matching nothing and coverage appears to fall — or matching
more than intended, which inflates it. Where the tool writes unmatched exclusions into the coverage
report itself, rule 5's Grep per side is the one call that finds them, so put the exclusion wording
in that pattern rather than spending a second call; where it writes a separate report, ask for it
and record the answer as *told to you*; where it writes nothing, record the exclusion set as
unverified rather than assuming it applied.
Separately, a covergroup reporting **zero bins** was never instantiated or never sampled: a build or
configuration finding, not a coverage finding, and the one that gets waived by mistake.

Then roll the per-covergroup work up into the block's one `cov model` verdict, which answers a
narrower question than the movers do — *did the thing we are measuring against change shape?* Write
`identical` only when every covergroup you compared carries the same name and the same **bins
total** on both sides and no covergroup exists on one side alone; that is the ordinary result of a
simulator-only bump with no VIP drop and no regenerated model underneath, and it is what licenses
you to read a coverage difference as verification rather than arithmetic. Write `changed` the moment
one covergroup's bins total moves, or one is renamed, added or dropped — even where the top-level
percentage held still, because a rise and a fall of equal size cancel in the percentage and not in
the model. Write `unknown` where you could not compare shapes at all: only one side's report exists
(step 3), or budget rule 5's one windowed Read per side covered too few covergroups to stand behind
the word `identical`. That last case is the common one and the one people round up rather than
admit.

### 9. Re-baseline performance — three numbers, medians, and the one that actually breaks

Compile time, elaboration time and run time are three separate numbers with three different
consumers. A release that elaborates far slower and runs slightly faster is a win for an overnight
regression and a loss for interactive debug; one blended figure hides that completely.

For run time prefer a rate — simulated time per wall-clock second, or whatever the **Performance
figures** slot says our end-of-run summary prints — over raw wall clock, which on a shared farm
largely measures who else is on the host. One repeat per side is not a measurement: **ask the
engineer for at least three repeats per side on the same class of host, and for the median they
report**, then state how many repeats that was. Where they hand you the individual figures in a file
instead, the median is arithmetic over numbers you Read under budget rule 8 — say which of the two
happened, because the agent times nothing either way. Peak memory is the figure that actually
breaks migrations: a larger footprint pushes the biggest tests past the **Farm limits**, and the kill
lands in the summary as a failure with a clean log, the same shape as a design bug and as a licence
outage. Label every figure here with where it came from — a file whose path you were given, or a
person who reported it — because those two are not the same evidence and the block asks which.

### 10. Write the migration baseline

Two blocks, because a migration is one comparison and many failures, and the two do not fit in one
row. The first is written once per pass. The second repeats once per new-only failure you opened —
that is where `signature`, `phase` and `class` live, taking their spelling and their values from
`dv-sim-log-first-error` and `_shared/failure-signature-schema.md` so a failure raised here reads
beside one raised there. `run id`, `coverage` and `notes` keep their pack-wide spellings too;
everything else below is local to this skill.

```
migration : <the axes that moved, with from-version and to-version of each>
axis      : simulator | uvm | vip | compound
proof     : <banner lines quoted verbatim from each side, with log path and line number>
markers   : <fatal and pass markers still match on the new side, or what changed>
frozen    : <of step 1's six — RTL revision, testbench revision, filelists, seed set, coverage exclusion files, farm queue — which are pinned, and name any that are not>
pass rate : <old pass of total> vs <new pass of total>; noise floor <old-versus-old spread, or "unmeasured">
new fails : <count new-only, how many of them opened, and one per-failure block below for each opened>
old fails : <count failing only on the old side, and whether each is fixed or hidden>
unsigned  : <count never opened, grouped by summary status string>
cov bins  : <covered of total, each side, top level plus the three biggest movers by covergroup>
cov model : identical | changed | unknown
perf      : <compile; elaboration; run rate; peak memory — median of k repeats, k stated, per side>
gate      : accept | accept-with-debt | hold
debt      : <switches left on, diagnostics waived, unmatched exclusions — each with an owner and a date>
vendor    : <cases opened, and the reduced case each rests on>
run id    : <whatever identifies the two runs for us>
coverage  : <which figures you read from a file, which were reported to you, how many failures opened of how many>
notes     : <anything the next person would otherwise rediscover>
```

Then one of these per opened new-only failure, and never one for the migration as a whole:

```
signature : <phase|kind|where|what, derived per _shared/failure-signature-schema.md, ? for any field not traceable to the log>
phase     : compile | elab | run | finalise | post
class     : design | infrastructure | unknown
cause     : <which of step 6's eight rows this matched, in that row's own words>
route     : <where it went — the sibling skill, the VIP owner, or the vendor case named in that row's Proves it column>
```

**Fill `gate` before you hand the blocks over.** It is the preparer's proposal, not the decision;
the profile's Sign-off row names who accepts or refuses it, and this field is what they are ruling
on. Take the three in order and stop at the first that fits:

- **`hold`** if any one of these is true: step 2's fatal or pass markers did not match on the new
  side; the old side no longer exists, so there is no comparison at all (step 3); a per-failure
  block still carries `class : design` with no fix landed; the `vendor` line carries an open case; or
  new-side peak memory is over the **Farm limits** rather than merely above the old release. Each of
  those makes the numbers above it unsafe to act on, so the gate holds however good the rate looks.
- **`accept-with-debt`** if nothing holds it but the `debt` line is non-empty — a deprecation switch
  still on, a new diagnostic waived rather than fixed, an exclusion set recorded as unverified — or
  `cov model` is `unknown`, or `unsigned` is non-zero. This is the ordinary honest outcome of a
  migration and the one people round up to `accept`; the whole difference between the two words is
  whether work that moved rather than happened has an owner and a date against it.
- **`accept`** only with an empty `debt` line, `unsigned` at zero, and every pass-rate difference
  either inside step 4's noise floor or explained failure by failure. Three conditions, all
  checkable from the first block without reopening anything.

Leave a field empty rather than filling it plausibly. Then state the handoffs rather than implying
them: ask the engineer for step 4's old-side control run, for both coverage reports generated under
their own versions, for step 9's repeat timings and peak memory, and for the removed-symbol list if
the release notes are unreadable — then ask whoever the profile's Sign-off row names to accept or
refuse the gate you proposed on that evidence.

## Gotchas

- **A simulator bump is often a UVM bump too.** Where the library comes from the simulator's built-in
  package rather than our own compile, the version underneath moves without anyone choosing it, and
  the migration everyone calls one axis is two. The banner in step 2 is the only proof.
- **Same seed, different stimulus.** Reproducibility is a property of a fixed executable, not of a
  seed. Across the boundary a test that fails on new and passes on old at seed *s* is a candidate,
  never a finding; what survives is an aggregate rate over a seed population with its sample size
  written next to it.
- **The percentage is the least informative number in a coverage report.** One added coverpoint
  raises the denominator and lowers the percentage with no verification change at all. Covered bins
  and total bins per covergroup separate a real loss from denominator inflation; a percentage cannot.
- **Coverage databases generally do not merge across tool versions.** Where the merge refuses you
  lose an afternoon; where it silently drops one side you lose the migration, because the result
  reads as a clean pass. Produce two whole reports and compare them.
- **Exclusions and waivers are keyed on names.** A covergroup rename in a VIP drop, or a hierarchy
  change, leaves them matching nothing and coverage appears to fall — or matching more than intended,
  which inflates it. Both are invisible unless the tool reports what matched nothing.
- **A covergroup reporting zero bins is not zero coverage.** It was never instantiated or never
  sampled: a build or configuration bug in a coverage costume, and waiving it buries the cause.
- **A stricter new release is not a tool regression.** A construct the old version accepted and the
  new one rejects is usually the new one reading the standard correctly, and a warning promoted to an
  error is a deliberate change. File a source fix, not a vendor case, unless a reduced case shows the
  tool contradicting itself.
- **Turning the deprecation switch on is a loan.** Green with legacy APIs enabled means the work
  moved, not that it happened, and the next release usually removes the switch along with the APIs.
  Debt with an owner and a date; never a pass.
- **Memory, not speed, is what breaks the farm.** A bigger footprint pushes the largest tests past
  the job limit, and the kill arrives as a failure with a clean log — indistinguishable in the
  summary from a design bug and from a licence outage.
- **The old version disappears and takes the comparison with it.** Once it is uninstalled or
  delicensed no baseline can be rebuilt at any price. Copy the old side's summary, coverage report
  and a handful of representative logs into retained storage before the switch, not after.

## Human verification — what a wrong answer looks like

Before anyone signs the gate, check:

- every rate carries its denominator, and the pass-rate comparison carries a noise floor or says
  plainly that the noise floor is unmeasured
- the versions came from **banner lines quoted out of a log**, not from the module or wrapper someone
  believes they loaded, and exactly one axis moved unless the baseline is labelled compound
- no per-seed pass-to-fail pair is presented as evidence on its own
- coverage is reported as covered bins of total bins per covergroup, and every mover is classified as
  a model change or a verification change
- the three performance figures are separate, each a median with its repeat count stated, and peak
  memory is compared against the farm limit and not only against the old release
- the debt line names every deprecation switch left on and every diagnostic waived, with an owner and
  a date each, and the coverage line says which figures a person reported rather than a file
- `cov model` says `identical` only if every compared covergroup carried the same bins total on both
  sides, and `unknown` rather than `identical` wherever only part of the report was read
- `phase` and `class` appear once per opened failure and nowhere at the top of the block — a single
  `class` for a migration with eleven new failures is a rollup nobody defined
- the proposed `gate` follows step 10's three conditions rather than the preparer's mood: `hold` on a
  marker mismatch, a missing old side, an open `class : design` row or a case, or peak memory over
  the farm limit; `accept` only with an empty debt line and `unsigned` at zero

A wrong answer is a one-page summary saying the new release is 4 percent worse on pass rate and 2
points down on coverage, with no denominators, no control run, no per-covergroup breakdown, and forty
"new failures" that are mostly the same forty tests failing at different seeds. Its mirror image is
rarer and worse: an unblemished report on a run whose fatal marker string changed, so nothing failed
because nothing was ever detected.

## Done when

The three baselines each carry a denominator and a stated measurement method, every genuinely new
failure you opened has its own block with a class and a destination, the gate carries the value step
10's three conditions produce, and the sign-off owner can accept or refuse the version change from
the two blocks alone.
