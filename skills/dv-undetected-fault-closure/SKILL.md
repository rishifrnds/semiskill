---
name: dv-undetected-fault-closure
description: Root-cause the undetected and unclassified faults a fault-injection campaign leaves behind — never activated, activated but not propagated, or propagated but not detected — and draft the safe-fault justification a safety analyst can accept or reject. Use when a campaign closes short of its single-point or latent fault metric, when a list of undetected faults has to be closed before sign-off, when the report says unclassified or dropped and nobody knows why, or when someone proposes calling a fault safe because the campaign never activated it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Undetected-Fault Debug and Safe-Fault Justification
  semiskill-function: design-verification
  semiskill-role: safety-verification-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-09-24
  semiskill-tags: fault-injection, functional-safety, safe-faults, fault-campaign, safety-mechanism, closure
---

# Undetected-Fault Debug and Safe-Fault Justification

A fault campaign is cheap to launch and expensive to close. The leftover list — faults the tool could
not classify as detected — is where the metric is won or lost, and every row on it is one of four
quite different things wearing the same word: a fault the stimulus never activated, one that was
activated and masked, one that propagated to somewhere nobody was looking, and one the campaign never
managed to classify at all. They need opposite fixes, and the report cannot tell them apart.

The output is a **closure record per fault**: which link of the chain it stopped at, the evidence line
for that, and either a drafted safe-fault argument or a named gap. Not a count.

**What this cannot do.** It reads the fault report, the RTL and saved logs. It cannot inject a fault,
re-run a campaign, prove untestability, open a waveform, or compute a metric — and it can never
declare a fault safe. It drafts an argument; the person in the sign-off slot accepts or rejects it.

## When to use something else

One failing simulation log — including the good-machine run that died before any fault was injected —
is `dv-sim-log-first-error`. A whole regression of red tests is `dv-regression-triage-routing`. A
failure you want smaller before handing over is `dv-minimal-reproducer`. A campaign that never built
is `dv-build-filelist-hygiene`. A repository you have never seen is `dv-repo-orientation`. Come here
only once a campaign has finished and produced a per-fault report.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Fault report location | [[FILL: where the campaign's per-fault results land, and whether the format is one row per fault or a multi-line stanza per fault]] | safety verification lead |
| Status vocabulary | [[FILL: the exact strings this report prints for undetected, for unclassified or dropped, and for each detected category, spelled as the tool emits them]] | safety verification lead |
| Fault list source | [[FILL: what generated the fault list, which hierarchy and which fault models it covers, and whether it is collapsed — if so, what one representative row stands for]] | DV infra |
| Observation points | [[FILL: where the list of observation points is recorded — the nodes the campaign compares against the fault-free run]] | safety verification lead |
| Detection points | [[FILL: where the list of detection points is recorded — the error flags and alarms each safety mechanism raises — and which mechanism owns each one]] | safety mechanism owner |
| Detection window | [[FILL: by what point in the run a detection has to have happened for this campaign to count it, and what the campaign does with a later one]] | functional safety manager |
| Safe-fault categories | [[FILL: the justification categories our safety case already accepts, where they are written down, and the wording each one requires]] | functional safety manager |
| Campaign log location | [[FILL: where the per-fault run logs are saved, and whether they are kept for every fault or only for a sample]] | DV infra |

Three facts this procedure spends are pack-wide and live in `_shared/team-profile.md` — read them
from there rather than re-asking: **Run identity** for the `run id` field, **Infra markers** for step
7, and **Sign-off** for who accepts a justification. Two of the rows above are deliberately narrower
than a profile row and are **not** the same fact: *Campaign log location* is the per-fault faulty-run
log, which many flows keep somewhere other than the profile's Log location and often discard after a
week — if they are in fact the same place, write that down rather than leaving it to be assumed. And
*Fault report location* is not the profile's Coverage output row; a fault report and a merged
functional-coverage database are different artifacts with different owners.

**If a slot is unfilled, stop and ask. Do not guess a convention** — and in particular do not guess a
status string. A skill that Greps for a status word the tool does not emit reports every fault as
absent, which reads exactly like a clean campaign.

**The standard's own definitions are normative; this file is not.** Where the wording of a fault class
or of a justification category matters, take it from your team's copy of the standard and from the
Safe-fault categories slot. Nothing here is a quotation of it.

## Retrieval budget — read this before opening anything

A fault report for a mid-sized block has tens of thousands of rows and the RTL under it has thousands
of files. Reading either one through is impossible, so the budget is deliberately per fault:

1. **Grep and Read work on files on disk.** If the report or the fault list arrived pasted into the
   conversation, ask for the path, or ask for it to be saved to a file and be given that path. Until a
   path exists you may reason over the pasted rows by eye — but say that is what you did, and mark
   every conclusion provisional. You have not searched the report.
2. **One Glob** to locate the report. **Never** open it with Read first.
3. **At most six Greps**: the report header in step 1, the undetected status string in step 2, the
   fault site's name in the RTL in step 3, its readers in step 4, then the observation-point list and
   the detection-point list in step 5.
4. **At most four windowed Reads of about 60 lines**: the report around the chosen fault, the fault
   site's driver, the first masking construct downstream of it, and one spare for wherever the answer
   actually lands.
5. **One fault per pass.** The budget above closes one fault properly. Step 2 groups the rest from
   Grep output alone, which costs nothing extra and is all the grouping this budget can honestly buy.
6. A Grep returning more than about 200 hits is too broad — anchor the name on a delimiter the report
   or the RTL actually uses before reading anything.
7. Stopping rule: when the six Greps and four windows are spent with no settled answer, stop, say
   which link of the chain you got to, and name the one artifact you still need. The
   `no-verdict` branch in step 7 spends one Grep and one window *instead of* steps 3 to 5, never in
   addition to them.
8. State your coverage in the closure record: one fault closed out of how many undetected, how the
   rest were grouped, and how many groups were never opened.

## Procedure

### 1. Resolve the report to a path and confirm which campaign it is

The Fault report location slot says where ours land; **Glob** for it rather than asking again. Then
one **Grep** of its header region for the design revision, the fault list it was run against, and the
safety goal or safety mechanism it targets.

If the report does not name the fault list it was run against, stop here. Without it you cannot tell
whether a fault that is missing from the report was never injected or was injected and dropped, and
those are different problems with different owners. Record the run identity from the profile's Run
identity row; it goes in the `run id` field untouched.

### 2. Group the undetected rows before opening any of them

One **Grep** of the report for the undetected string from the Status vocabulary slot, in content mode,
capped at the first 200 hits. Each hit line normally carries the fault identifier and the fault site,
so the grouping can be done on the Grep output with no Read at all: group by the longest hierarchy
prefix the hit lines share, and record the count per group.

Then pick **one** fault to close — the one in the largest group, because a structural argument written
for one site usually closes every fault at that site and its neighbours, and a fault picked at random
closes one. Spend one 60-line **Read** window on the report around that row to recover its full set of
columns: identifier, site, fault model and injected value, and the status string verbatim.

Keep the unclassified and dropped rows in a group of their own. They are not undetected — they have no
verdict at all, and step 7 handles them. Merging the two groups is how a broken campaign gets reported
as a coverage result.

If the report is a multi-line stanza per fault rather than one row per fault, the Grep output will not
carry the site, and this grouping cannot be done. Say so, group only what the first window shows, and
cap the coverage line accordingly.

### 3. Was the fault ever activated?

A stuck-at fault is activated only while the fault-free node holds the **opposite** value. If the node
never takes that value during the campaign, nothing was ever injected in any meaningful sense.

**Grep** the RTL for the leaf signal named in the fault site, then **Read** a 60-line window at its
driver. Three cases fall out, and only the first is a safe-fault candidate:

- **Constant by construction.** The driver is a tie-off, an unconnected port, a branch of a generate
  that this configuration does not take, or a mode bit fixed by the parameters this build used. The
  node cannot take the opposite value, so the fault cannot be activated at all.
- **Toggles, but this stimulus never got there.** The node is driven by real logic that simply never
  reached that state in this campaign. This is a **stimulus gap**, not a safe fault, and the fix is
  more stimulus. Ask the engineer to re-run the campaign with the state added and to give you the path
  to the new report; the agent cannot inject anything.
- **Transient model, wrong injection window.** For a transient or upset model the injection times are
  part of the campaign setup, and a node that is only sensitive during a mode the injection window
  missed reports as not activated. This is campaign setup, not design.

Read alone cannot separate the first case from the second when the driver is more than one level deep.
Where the driver is itself computed, say that the constancy is unproven and hand it to the structural
check in step 4 rather than claiming it.

### 4. Activated but not propagated — name the masking construct

**Grep** for the readers of the same signal to get its immediate fan-out, then **Read** one 60-line
window at the first construct that can block it. What blocks a fault effect, in rough order of how
often it turns out to be the answer:

- an AND with a constant zero, or an OR with a constant one, on the only path out
- a multiplexer whose select is fixed for the configuration this campaign built
- a register whose enable never asserts, so the corrupted value is never captured
- the corrupted bits sitting in the unused upper part of a wider field that nothing downstream reads
- two copies of the value re-converging into a comparison that cancels the difference

Then separate the two kinds of masking, because they route to different people. **Logical masking** is
structural: the constant is a constant in every configuration, and it is a safe-fault candidate.
**Functional masking** is this workload only: the select could have been the other way, the enable
could have asserted, and it is a stimulus gap wearing a masking costume.

**A read of the RTL gives you a candidate, never a proof.** Propagation is a temporal question — an
effect that needs twelve cycles to reach an observation point will look masked to a campaign that
stops strobing at cycle eight, and no amount of reading the cone settles that. To prove that no path
exists, ask the engineer to run the structural or formal untestability analysis over that cone and to
give you the path to its report; quote that report rather than your own reading.

### 5. Propagated but not detected — the expensive case

This is the one that costs metric. Take the names the effect reached in step 4 and **Grep** the
Observation points list, then **Grep** the Detection points list. Four outcomes, and they are not
interchangeable:

- **The name is in neither list.** The campaign never looked there. Nothing is known about this fault
  yet; the finding is a campaign setup gap, and the report's "undetected" was never evidence.
- **In the observation list, not in any detection list, and no safety mechanism claims this element.**
  A fault that reaches a safety-goal-relevant output with no mechanism watching is the single-point
  case. The hole is in the safety concept, and it belongs to whoever owns the architecture.
- **A mechanism does claim this element but its flag never asserted.** The mechanism's real coverage
  is narrower than the coverage the safety analysis credited it with — the residual case. It belongs
  to the mechanism owner, not to the architect, and it is the finding people most often mis-file as
  "undetected, low priority".
- **The flag asserted, but outside the Detection window.** A late detection is not a detection for
  metric purposes. Whether it was late needs the per-fault log or a waveform — ask the engineer for
  whichever your flow keeps and record that the timing came from a person, not from a file.

One sorting rule comes before all four: **where does the fault site sit?** A fault in the functional
logic that reaches a safety-goal-relevant output is a single-point or residual fault. A fault in the
safety mechanism itself does not violate the goal on its own — it quietly disables the detection, and
it belongs to the latent-fault side of the arithmetic. The report will not do this split for you.

### 6. Draft the justification — and only the categories our safety case accepts

Write the argument against a category from the Safe-fault categories slot, in that slot's wording.
This table is the shape of each argument and, more usefully, what each one is **not**.

| Argument | What it claims | Evidence it needs | What it is not |
|---|---|---|---|
| Structurally constant | the node cannot take the value the fault needs, in any legal configuration | the driver, and every configuration input that could change it | "this test never toggled it" |
| Outside the cone | no path from the node to any safety-goal-relevant output | a structural cone report from step 4's handoff | "I could not see a path in the file I opened" |
| Logically masked | every path out is blocked by a value that is constant in all configurations | the blocking construct, and what fixes it | a select or enable that firmware can change |
| Not safety-related | the element's failure cannot violate the safety goal | the allocation in the safety analysis that says so | "it looks like debug logic" |
| Equivalent to fault-free | the faulty value equals the good value at every observation point | the equivalence, usually from the tool's own collapsing | "it was not observed" |
| Excluded by assumption | the operating mode that activates it is outside the assumed use | the assumption, quoted from the safety case | an assumption you inferred |

Two rules hold over all six. **Undetected is not safe** — the absence of a detection is the question,
never the answer. And the agent drafts; the person in the profile's **Sign-off** row decides. Never
write a justification into the safety case yourself, and never present a drafted argument as an
accepted one.

### 7. Unclassified and dropped faults — a missing verdict, not a result

These rows mean the campaign could not classify the fault: the faulty run timed out, hung, went to X,
or the job died. Every one of them is conservatively worse than undetected until someone looks.

**Grep** the Campaign log location for the profile's **Infra markers** — licence, queue, host, disk.
A hit means `class: infrastructure`: the fault needs re-injecting, not debugging, and nothing about
the design has been learned. No hit, and the faulty run hung or timed out on its own, means the
injected fault stalled a handshake or parked a state machine — `class: design`, and often the most
interesting thing the campaign found all night. Spend the one 60-line **Read** window here, at the
last activity in that log.

X is its own trap. A faulty run that goes to X is neither detected nor safe, and whether the engine
treated the X optimistically or pessimistically changes the answer completely. Ask which X mode the
campaign ran in rather than assuming; it is a campaign setting, and it is not usually in the report.

### 8. Write the closure record

```
fault id     : <the campaign's own identifier for this fault, verbatim>
fault site   : <the node path exactly as the report spells it>
fault model  : <the fault model and injected value, verbatim from the report>
reported as  : <the report's own status string for this fault, verbatim>
blocked at   : activation | propagation | detection | no-verdict
fault verdict: safe-candidate | stimulus-gap | observation-gap | mechanism-gap | undecided
class        : design | infrastructure | unknown
argument     : <one sentence naming the step-6 category it rests on, or empty>
evidence     : <a file path and line for every claim above, and the report line for every quoted status>
signature    : <phase|kind|where|what, per the shared schema — on the no-verdict branch only>
sign-off     : <who from the profile's Sign-off row must accept this — never the agent>
run id       : <whatever identifies this campaign for us>
log          : <path, and the line range worth reading>
coverage     : <1 of n undetected faults closed; how the rest were grouped; how many groups unopened>
notes        : <anything the next person would otherwise rediscover, including any value that came from a person rather than a file>
```

`class` uses the pack's three values and answers only *whose problem the missing verdict is*; it is
meaningful when `blocked at: no-verdict` and `unknown` everywhere else. The `signature` line is
deliberately conditional: an undetected fault is a coverage hole, not a failure, and it has no failure
message to normalise. Only the `no-verdict` branch has a real failure behind it, and there the
schema's own `kind` tokens — `timeout`, `xprop`, `tool`, `fatal` — already fit, so use
`_shared/failure-signature-schema.md` as written and invent nothing. Leave the field empty otherwise
rather than filling it with something that will never match anyone else's.

Fill nothing from memory. If a line cannot be filled from text on disk, write `?`.

## Gotchas

- **Undetected is not safe, and the arithmetic punishes the confusion.** A fault reclassified as safe
  leaves the metric's denominator entirely, so a wrong safe-fault argument does not merely lose
  information — it silently raises the number the safety case rests on. An honest unclosed fault is
  cheaper than a confident wrong justification, every time.
- **A fault in the safety mechanism is a different metric from a fault in the logic it watches.** The
  first cannot violate the safety goal by itself; it disables the detection and counts as latent. The
  second is single-point or residual. Sort by which hierarchy the site sits in before anything else —
  the report almost never does it for you, and the two have different owners and different fixes.
- **"Not activated" is a property of the stimulus, not of the design.** It becomes a property of the
  design only when the node is constant by construction, and only in the configurations this build
  actually compiled. A mode bit that is tied off in this build and programmable in the next one has
  produced an argument with a shelf life of one release.
- **Collapsed fault lists hide the count.** Where the list is collapsed, one representative row stands
  for a set of equivalent faults, so closing one row can be worth forty in the metric — or the "3
  undetected" you are quoting can be worth three hundred. Read the Fault list source slot before
  quoting any number, and say in the record whether the count is collapsed or flat.
- **Stuck-at-0 and stuck-at-1 at the same site are two faults with two answers.** One can be
  structurally never activated while the other is a live residual fault. A record that names a site
  without naming the model has closed nothing.
- **A detection outside the window is not a detection.** A campaign that only compares at end of test
  will happily report detections the safety concept cannot use, and the metric it prints will be
  wrong in the optimistic direction. Fill the Detection window slot before believing any detected
  count.
- **The observation-point list is where the silent gaps live.** A fault that propagated to a node
  nobody compares and a fault that propagated nowhere are printed identically. One needs a campaign
  setup change and the other needs a masking argument, and only the Observation points list separates
  them — never the report.
- **A faulty run that hangs is a finding, not a dropped row.** Under sign-off pressure these get bulk
  re-queued, and the hang — a fault that stalls a handshake or parks a state machine — is exactly the
  behaviour the safety mechanism was supposed to catch.
- **RTL fault sites and gate-level fault sites are not the same set.** Synthesis merges, duplicates
  and removes nodes, so a node justified safe against RTL names can reappear as several gate-level
  nodes with no justification at all, and a node justified at gate level may have no RTL name. Every
  justification must say which netlist the campaign was run against.
- **A safety mechanism covers a fault type, not a region.** Error-correcting code over a memory's data
  bits says nothing about faults in its address decode or its control path, and a comparator on one
  output says nothing about the paths that reach the others. "The block is covered by a mechanism" is
  not an argument; naming the specific fault the mechanism would have flagged is.

## Human verification — what a wrong answer looks like

Before acting on the record, check:

- `blocked at` names **one** link, and the evidence line points at a file and line that actually
  shows it. "Probably masked somewhere downstream" means step 4 was not finished.
- no fault is called safe. `fault verdict: safe-candidate` is the strongest value available here, and
  it names a category from the Safe-fault categories slot, not a category invented in the record.
- a structural argument quotes the driver or the blocking construct with a path and a line — and says
  which configuration it holds in.
- a non-propagation claim rests on the structural analysis handoff from step 4, not on a reading of
  one cone. A propagation delay longer than the strobe window has been ruled out explicitly.
- the single-point and residual cases have not been merged, and neither has been merged with a latent
  fault in the safety mechanism itself.
- `reported as` is the tool's own string, character for character, not a paraphrase of it.
- the `coverage` line is present and its denominator is the number of undetected faults the report
  actually holds — not the number of groups, and not the number you looked at.

A wrong answer typically calls a stimulus gap a safe fault because the campaign never activated it;
files a residual fault as low priority because the word in the report was "undetected"; quotes a
collapsed count as though it were flat; or writes a justification in the safety case's own voice when
nobody has signed it.

## Done when

One fault has a named link, an evidence line, a drafted argument or a named gap, and a person to
accept it — and the record says honestly how many of the rest are still open.
