---
name: dv-fault-campaign-iso26262
description: Derive the fault list and the per-mechanism detection criteria for a safety-targeted block, then assemble the fault-injection campaign evidence a safety assessor will accept. Use when someone asks for ISO 26262 fault-injection results on an IP, when you need to say what a safety mechanism actually detects, when a campaign has finished and nobody agrees what detected means, when a safe-fault pruning list is being challenged, or when you are about to report raw fault counts as diagnostic coverage. Stops at counts and hands metric computation to the safety engineer.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Fault-Injection Campaign and Diagnostic-Coverage Evidence
  semiskill-function: design-verification
  semiskill-role: safety-verification-engineer
  semiskill-level: staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-10-02
  semiskill-tags: iso26262, functional-safety, fault-injection, fault-list, diagnostic-coverage, safety-mechanism, evidence
---

# Fault-Injection Campaign and Diagnostic-Coverage Evidence

A fault campaign is cheap to launch and expensive to defend. The launch is a tool invocation; the
defence is a written argument that the fault list was the right fault list, that "detected" meant one
thing all the way through, and that every fault removed from the denominator was removed for a stated
reason. Campaigns are rejected at assessment almost never for the injection and almost always for the
bookkeeping around it — a safe-fault list with no justification column, a detection criterion nobody
wrote down, or a percentage got by counting faults that should have been weighted by failure rate.

This covers the two ends the verification engineer owns: **deriving the fault list and the detection
criteria**, and **assembling the campaign evidence**. It stops before the metrics. The single-point
fault metric, the latent fault metric and the probabilistic metric for random hardware failures are
failure-rate weighted and belong to the safety engineer holding the FMEDA — step 7 is that handoff.

## When to use something else

Come here once a block is safety-targeted and a structural fault campaign is the question. For the
**scenario list** the campaign runs — error patterns against ECC, parity, CRC, retry and poison
paths — use `dv-error-injection-ras`; it produces functional error-injection stimulus, this one
classifies structural faults, and a real campaign needs both. If the netlist does not yet simulate
cleanly, `dv-gls-bringup` comes first; if it will not compile or elaborate, `dv-build-filelist-hygiene`.
A single failing campaign run belongs to `dv-sim-log-first-error`, a night of them to
`dv-regression-triage-routing`, and shrinking one to `dv-minimal-reproducer`. A safety mechanism's
error or status register reading back wrong is `dv-ral-bringup`, not a fault. For the
plan-to-coverage-to-checker chain use `dv-testplan-traceability-review`, and for the sign-off itself
`dv-release-gate`. Nothing in this pack computes safety metrics, and this skill must not either.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Safety concept source | [[FILL: where our technical safety concept and its list of safety mechanisms live, and whether that is a file that can be read or a document a person must quote from]] | safety manager |
| Observation points | [[FILL: which signals we treat as functional outputs and which as checker outputs for this block, and the file that records that split]] | block safety owner |
| Time budget | [[FILL: the fault-tolerant time interval and the diagnostic test interval allocated to this block, and the units we write them in]] | safety manager |
| Netlist source | [[FILL: which design view the campaign injects into, where that view is built, and the instance-path prefix the fault list is keyed on]] | DV infra owner |
| Fault-list format | [[FILL: the fault-list and result-file format our fault simulator reads and writes, and which column carries the node path]] | safety verification lead |
| Status vocabulary | [[FILL: the exact status strings our fault simulator writes for observed, unobserved, detected-at-a-checker and dropped faults]] | safety verification lead |
| Safe-fault justification | [[FILL: where we record a safe-fault claim, and what evidence each category of claim needs before it is accepted]] | safety manager |
| Campaign result location | [[FILL: where the fault simulator writes this block's per-fault result file, if that is not where ordinary run logs land]] | DV infra owner |
| Tool confidence record | [[FILL: where our tool-qualification record for the fault simulator lives and which tool version it covers]] | safety manager |

Log location, Run identity and Area to owner map are pack-wide facts and live in
`_shared/team-profile.md` — read them from there rather than re-asking. **Campaign result location is
narrower than the profile's Log location**: a campaign writes a per-fault result file, one row per
injected fault, often not under the ordinary run area at all. If the two are the same path for us,
say so in that slot.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented status string
silently miscounts an entire campaign, and an invented time interval turns a real residual fault into
a clean pass.

## Retrieval budget — read this before opening anything

A per-fault result file for a mid-size block has hundreds of thousands of rows and a gate netlist has
more. Reading either is impossible and teaches nothing — the value is in the counts and in a handful
of sampled rows.

1. **Grep and Read work on files on disk.** If the fault list, the result file or the safety concept
   exists only as a pasted table or as a document nobody can open, say so and resolve it to a path
   first. Anything reasoned from a fragment shown in a chat is provisional, and step 8 says so.
2. **Never open a fault list, a result file or a netlist with Read as the first move.** Locate with
   **Grep**, then Read a bounded window.
3. The whole budget is **two Glob** calls, **six Grep** calls and **four Read** windows of about 40
   lines: Glob for the safety-mechanism list (step 1) and for the fault and result files (step 3);
   Grep for the mechanism names (step 1), the observation-point signals (step 2), the instance-path
   prefix (step 3), the status strings (step 4) and the residual rows (step 6), plus one spare; Read
   for the mechanism rows (step 1), the observation-point list (step 2), the head of the result file
   (step 3) and the residual sample (step 6). Steps 5, 7 and 8 open nothing.
4. **Counts, not listings.** A Grep for a status string will match tens of thousands of rows. Ask for
   the count. If the runtime can only list, cap the listing and treat the number as a floor, not a
   total — and write that down.
5. **Sample at most ten faults by hand.** Ten proves the classification is being read correctly and
   is far too few to be a coverage claim. Never let a sample become a percentage.
6. Stopping rule: when the budget is spent and the fault list still is not derivable, stop and report
   what is defined, what is missing and who owns it. Past that point the classification gets invented,
   and an invented classification is the one error nobody downstream can detect.
7. State what you covered — which rows of the bundle rest on a file you read, which on a number a
   person quoted, and how many of the block's mechanisms the bundle reaches.

## Procedure

### 1. Name the safety mechanisms before naming a single fault

A fault list has no meaning until you can say which mechanism is supposed to catch what. Start from
the **Safety concept source** slot: **Glob** for it, **Grep** for the mechanism names, then **Read**
one window over their rows. For each mechanism record four things — the element it covers, the
failure mode it claims to cover on that element, the signal it asserts when it fires, and how quickly
it must fire.

If the concept is a document **Read** cannot open — a spreadsheet, a signed PDF, a requirements
tool — say so before going further. Ask the safety manager to quote each mechanism row verbatim,
record who supplied it and when, and mark every finding resting on it provisional. A coverage claim
against a mechanism nobody could quote is not evidence.

A mechanism the concept does not name is not a mechanism. Testbench checkers, assertions and
scoreboards catch faults too, and they are not diagnostics — they are not present in the shipped
silicon, so nothing they detect may be counted as detected.

### 2. Fix the observation points, then write the detection criterion

"Detected" is meaningless until two sets of signals are named and kept apart:

- **Functional outputs** — the places where a corrupted value leaves the block and can go on to
  violate the safety goal. Corruption here is the harm the campaign is measuring.
- **Checker outputs** — what the safety mechanisms assert. Assertion here is the diagnosis.

Take both from the **Observation points** slot, **Grep** the design view for those signal names to
confirm each exists and to capture its full instance path, and **Read** the recorded list once.
A signal in the list that Grep cannot find is the finding — stop and raise it.

Then write one detection criterion per mechanism, as a sentence with three parts: which checker
output must assert, within what window, and what the functional outputs are permitted to show
meanwhile. The window comes from the **Time budget** slot — the fault-tolerant time interval for a
mechanism that must act before harm reaches the system, the diagnostic test interval for one that
sweeps periodically. These are different numbers and they are not interchangeable.

Two criteria that look alike and are not: a mechanism whose alarm is a pin, and one whose alarm is
only visible in a status register that software polls. The second is detected only if the bit reaches
that register inside the interval, so the register path is part of the criterion.

### 3. Derive the fault list as a scope statement, not a file dump

The fault list is generated by the fault simulator from the design view; the agent cannot generate it
and must not describe one it has not seen. What the agent can do — and what actually gets skipped —
is write the scope statement the generated list must match, in four parts:

1. **Where.** The instance-path prefix from the **Netlist source** slot, plus the mechanism logic
   itself, which is inside the scope and is the part people forget.
2. **Which models.** Permanent faults, usually stuck-at on cell pins, for the permanent-failure
   argument; transient faults, usually a single bit-flip in a state element, for the soft-error
   argument. Say which of the two this campaign is making. One campaign rarely makes both.
3. **Which nodes.** Everything in the cone of influence of the functional outputs named in step 2.
   Nodes outside every such cone are structurally incapable of causing harm and are the strongest
   safe-fault category there is — see step 5.
4. **What is deliberately out**, and on whose authority.

Then **ask the engineer to generate the fault list with the fault simulator on that design view and
give you the path to it, and to the per-fault result file if the campaign has already been done**.
Once a path exists, **Read** about 40 lines from the head of the file to learn its column layout
against the **Fault-list format** slot, and spend **one Grep** counting the instance-path prefix to
size the in-scope population. Those two numbers — in scope, and total in the file — are the first row
of the bundle, and a large gap between them means the campaign injected somewhere you did not intend.

### 4. Map the tool's status strings to the ISO classes — the mapping is a decision, not a default

The fault simulator's status strings are its own vocabulary. They are not the classes in ISO 26262
part 5, and no tool can assign those classes for you, because they depend on the criterion you wrote
in step 2. Take the strings from the **Status vocabulary** slot, spend **one Grep** to count each in
the result file, and write the mapping down explicitly.

| What the campaign observed | ISO 26262 class | What it means | Whose move next |
|---|---|---|---|
| No functional output disturbed, no checker output asserted, and a structural or formal argument shows it never could be | safe fault | cannot increase the probability of violating the safety goal | nobody — record the argument |
| The same observation, but the only reason is that this stimulus never activated it | not yet a class | unobserved, not safe; count it on the dangerous side until an argument exists | you, with the stimulus owner |
| A checker output asserted inside the window, functional outputs behaved as the criterion permits | detected by the mechanism | this is what diagnostic coverage is made of | nobody |
| A functional output was corrupted, no checker output asserted, on an element a mechanism claims | residual fault | the mechanism has a hole exactly here | the mechanism owner |
| A functional output was corrupted and no mechanism claims that element at all | single-point fault | there is no diagnostic at this point in the architecture | the safety architect |
| Injected into a mechanism's own logic; nothing at the functional outputs and nothing at the checker | latent multiple-point fault candidate | the checker is broken and nothing says so | the mechanism owner, via step 6 |

Faults that need a second independent failure before they can do harm are multiple-point faults; they
are latent only while neither a mechanism nor the driver would notice them. If your architecture
claims a periodic self-test to catch them, that claim is checked by the same injection, run against
the mechanism logic rather than the functional logic.

### 5. Justify the safe-fault list, and treat "unobserved" as unproven

The safe-fault list is the one an assessor reads first, because it is subtracted from the
denominator. Every entry needs a category and evidence, recorded the way the **Safe-fault
justification** slot says. In descending order of strength:

- **Outside the cone of influence** of every functional output. Structural, checkable, and the only
  category that needs no stimulus argument at all.
- **The node is constant by construction** — tied, or driven by a configuration held fixed for this
  application. The fixed configuration is part of the claim and has to be stated with it.
- **The element is not part of the safety-related path** — for example logic reachable only by a
  debug or test mode disabled in the shipped part. Say what disables it.
- **The effect is masked architecturally**, by redundancy or by a downstream saturation. The weakest
  category, because it is an argument about behaviour rather than structure, and the one to expect
  challenge on.

**"The test did not activate it" is not a safe-fault category.** It is the most common wrong entry in
the list and the fastest way to lose an assessment, because it converts a gap in the stimulus into a
property of the design. Keep those faults in a separate count with the stimulus revision beside them.

### 6. Sample the residual list, and inject into the mechanisms themselves

Residual and single-point faults are the campaign's output that changes designs, so they must be
real. Spend **one Grep** for the status string that maps to them together with the instance-path
prefix, take at most ten rows, and **Read** one window over them. For each, check three things: the
node really is inside the mechanism's claimed element, the run really did disturb a functional output
rather than an intermediate signal someone added to the strobe set, and the checker really was quiet
rather than asserting outside the window and being scored late.

A residual list that is entirely one instance is usually one structural cause, not many faults.

The latent side needs its own pass, and it is the one campaigns omit: injecting only into the
functional logic measures nothing about whether the mechanism itself still works. **Ask the engineer
for a second campaign injecting into the mechanism logic named in step 3**, scored against whether
the mechanism still detects a fault it is supposed to detect.

### 7. Hand the metrics to the safety engineer, with the inputs they need

Stop at counts. Diagnostic coverage and the architectural metrics are **failure-rate weighted**, and
the fault list has no failure-rate column: a thousand faults on a small cell and ten inside a memory
can carry the same failure rate, so a ratio of fault counts is not a ratio of failure rates and must
never be reported as one. The rates come from the FMEDA and the technology failure-rate data, neither
of which is in this repository and neither of which may be estimated here.

**Ask the safety engineer to compute the metrics from the bundle below**, and give them the counts,
the status mapping, the safe-fault justifications with their categories, the residual list, the
stimulus revision, the intervals from step 2 and the **Tool confidence record** reference. Say plainly
that the counts are unweighted.

### 8. Assemble the evidence bundle

One block per mechanism, plus one campaign header. Field names match the sibling skills' handoff
blocks so the bundle reads beside them.

```
campaign    : <block, design view, tool and version, campaign date>
mechanism   : <the safety mechanism, named exactly as the safety concept names it>
covers      : <the element and the failure mode this mechanism claims>
criterion   : <which checker output, within what window, and what the functional outputs may show>
fault model : <permanent or transient, and the node set each was applied to>
scope       : <instance-path prefix injected into, and what was deliberately left out and why>
population  : <faults in scope of this prefix; total in the file; whether the tool collapsed them>
status map  : <one line per tool status string, and the class from step 4 it maps to>
counts      : <per class, unweighted — safe, detected, residual, single-point, latent candidate>
unobserved  : <count, and the argument for each group, or "none — stimulus gap">
safe basis  : <count per safe-fault category from step 5>
residual    : <count, path to the list, and how many rows were checked by hand>
stimulus    : <the tests and their revision that this classification rests on>
timing      : <the intervals assumed, their units, and where they came from>
latent pass : <done | not done, and against which mechanism logic>
tool record : <the tool-qualification reference, or "not recorded">
class       : design | infrastructure | unknown
run id      : <whatever identifies this campaign for us>
log         : <path to the per-fault result file, and the rows worth reading>
coverage    : <which rows came from a file you read and which from a person; how many of the
               concept's mechanisms this bundle reaches>
metrics     : not computed here — handed to the safety engineer per step 7
notes       : <anything the safety engineer would otherwise have to rediscover>
```

Write `?` in any row that cannot be filled from text on disk or from a named person. A row left blank
reads as zero, and a zero in a safety bundle is a claim.

## Gotchas

- **Fault coverage is a property of the stimulus, not of the design.** The same netlist under a
  different test yields a different classification. "Not observed" means this workload did not
  activate it, and nothing more; step 5 is where that distinction is either kept or lost.
- **Fault dropping is the quiet killer.** Simulators stop simulating a fault once it is detected, to
  save runtime. If the drop condition is "seen at any strobe" and your functional outputs are also
  strobes, faults that corrupted an output get dropped as detected and never reach the residual list.
  Confirm what the drop condition is before believing any count — this is the setting that most often
  makes a campaign report the opposite of the truth.
- **Counting is not weighting.** Two faults are two faults; two failure rates are not. Every
  percentage that comes out of a fault count and not out of the FMEDA is wrong by an unknown factor.
- **The fault-free run must be quiet.** A mechanism whose alarm asserts on the good-machine reference
  scores every fault as detected and carries no information. Check the reference run first, every
  time the design view changes.
- **Fault collapsing changes the denominator.** If the tool collapsed structurally equivalent faults
  and the FMEDA did not, the two populations are not comparable and the metric built on them is not
  either. Record whether collapsing was on, in the bundle, not in your head.
- **An X at a strobe is not a detection.** A comparison that treats unknown as mismatch scores
  pessimistically and inflates detection; a gate-level model that resolves unknowns optimistically
  hides real propagation. Both distort in the direction nobody notices, because both make the numbers
  look better.
- **Transient faults need an injection time distribution.** A bit-flip injected while the design is
  still in reset is cleared by the reset, and a campaign that injects everything at time zero reports
  a beautiful safe-fault count that means nothing.
- **Latent faults live inside the mechanism.** A campaign that only injects into functional logic can
  say nothing about latent coverage, no matter how good the checker is — and it will not say so; it
  simply produces no latent rows at all.
- **The design view must be the one that ships.** A campaign on a pre-change netlist is evidence
  about a design that does not exist, and re-synthesis renames flattened cells, so the old fault list
  silently stops matching the new hierarchy rather than failing loudly.
- **A testbench checker is not a safety mechanism.** It does not exist in silicon. Anything it
  catches is undetected as far as the safety case is concerned, and a strobe set that quietly includes
  checker signals turns that error into a number.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every mechanism in the bundle is named as the safety concept names it, and the concept row was read
  from a file or attributed to the person who quoted it
- the detection criterion names a **checker** output and a window, not merely "the error was seen"
- the functional-output set and the checker-output set are disjoint, and no testbench-only signal
  appears in either
- every safe-fault entry carries one of the step 5 categories, and none of them is "not activated"
- the counts are stated as unweighted, and no percentage appears anywhere in the bundle
- the `latent pass` row is filled, including when the answer is "not done"
- the `coverage` row says how many of the concept's mechanisms this bundle actually reaches

A wrong answer typically reports a detection percentage as diagnostic coverage; classifies unobserved
faults as safe; counts a testbench assertion as a diagnostic; or presents a residual list of zero from
a campaign whose drop condition retired every dangerous fault before it could be classified.

## Done when

The safety engineer can compute the metrics from the bundle without asking you a single question, and
every fault removed from the denominator has a category and a named source.
