---
name: dv-vip-integration
description: Bring a commercial protocol VIP up in a testbench and prove that link-up, the protocol checkers and the coverage model are all genuinely switched on rather than silently absent. Use when you are dropping a purchased VIP into an environment for the first time, when the VIP compiles and runs but prints nothing at all, when you cannot tell whether a quiet log means clean or means unconnected, when someone asks whether VIP protocol checks and VIP coverage are actually enabled, or when a VIP release upgrade has changed the defaults under you.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Integrating and Configuring a Protocol VIP into an Environment
  semiskill-function: design-verification
  semiskill-role: soc-dv-engineer
  semiskill-level: intermediate
  semiskill-owner: dv-guild
  semiskill-version: 1.0.1
  semiskill-review-by: 2027-04-09
  semiskill-tags: vip, integration, protocol, checkers, coverage, link-up, bring-up
---

# Integrating and Configuring a Protocol VIP into an Environment

A commercial protocol VIP arrives as a protected library, a configuration object and a wall of
documentation, and the first integration almost never fails loudly — it compiles, elaborates, runs,
and prints nothing. That silence is indistinguishable from a link that never came up and checkers that
were never switched on; weeks of clean runs later somebody notices the coverage database is empty.
This procedure turns silence into positive evidence at each of five joins — **compile, connect,
link-up, checkers, coverage** — and says which of them are confirmed from a file and which are assumed.

## When to use something else

- The VIP's filelist will not compile or elaborate — `dv-build-filelist-hygiene`; step 2 routes it.
- One failing simulation log, VIP or not — `dv-sim-log-first-error`, which produces the signature this
  skill's report reuses.
- A whole night of failures to sort and route — `dv-regression-triage-routing`.
- A register-model mismatch behind the VIP's bus — `dv-ral-bringup`.
- A failure found here that now needs shrinking for a vendor ticket — `dv-minimal-reproducer`.
- You have never seen this repository before — `dv-repo-orientation` first, then come back.

## Fill this in for our team

Every row is product-specific or house-specific and **none is guessable**. This skill deliberately
contains no vendor knob names: an invented field name reads as authoritative and costs an afternoon.

| Slot | What to fill in | Who knows |
|---|---|---|
| VIP release | [[FILL: where the VIP release is unpacked in our tree, exactly which release we compile against, and which file in it documents integration — plus whether that file is one Read can open or a packaged document set that cannot be]] | DV infra |
| VIP type names | [[FILL: the type names our release spells for the VIP's top component, its configuration object, and its interface]] | whoever integrated it first |
| Interface handle key | [[FILL: the exact string our environment publishes the VIP's interface handle under, and the component path that retrieves it]] | block DV owner |
| Protocol profile | [[FILL: the protocol revision, data and address widths, and optional features this instance must be configured to — and where the DUT's own declared values live]] | RTL designer |
| Link-up marker | [[FILL: the string this VIP prints when the link is up, or when it accepts its first legal transfer]] | VIP applications contact |
| Protocol-error markers | [[FILL: the strings this VIP prints on a protocol violation, and the rule groups it separates them into]] | VIP applications contact |
| Checker enable knobs | [[FILL: the configuration fields that switch this VIP's protocol checking on, their defaults in our release, and any house override we apply]] | DV infra |
| Coverage enable knobs | [[FILL: the fields that switch this VIP's coverage model on, whether there is also a compile-time gate, and where its database lands]] | DV infra |
| Log location | [[FILL: where our simulation and regression logs land]] | your mentor |
| Pass marker | [[FILL: the string a clean run prints at the end]] | DV lead |

The last two are pack-wide facts and live in `_shared/team-profile.md` — read them from there rather
than re-interviewing anyone. Four more profile rows are used without being re-asked: **Filelist
convention** and **Simulator** in step 2, **Coverage output** in step 7, **Run identity** in the report
block, and **Sign-off** for who accepts a finished integration.

**Protocol-error markers is narrower than the profile's Fatal markers.** The profile records what our
*flow* prints when a run fails; this row is what the *VIP* prints when the protocol is violated. A VIP
reporting violations under its own identifier may never emit a flow-level fatal marker at all, so
record both and never assume one covers the other.

**If a slot is unfilled, stop and ask. Do not guess a convention.**

## Retrieval budget — read this before opening anything

A VIP release is tens of thousands of files, most of them protected and unreadable, and the smoke-run
log is the usual hundreds of megabytes. Work in this order and stop as soon as a stage settles.

1. **Grep and Read work on files, not on chat text.** If the log or a configuration snippet arrived
   pasted into the conversation, ask for the path on disk. Until a path exists you may reason over the
   fragment by eye, but say so — you have not searched anything.
2. **Glob before Read.** Two Globs: one over the **VIP release** path, one over our own environment and
   testbench-top files.
3. **Five Greps, and no more**: the VIP type names (step 2), the Interface handle key with the
   agent-mode fields (step 3), the log markers (step 5), the Checker enable knobs with the severity
   overrides (step 6), the Coverage enable knobs (step 7). Each of those steps alternates its patterns
   into **one** call. A sixth is allowed only if a coverage report already exists on disk (step 7).
4. **Six windowed Reads**: about 40 lines at the head of the release notes (step 1), about 50 at each of
   the two integration joins (step 2), about 50 at the handle publication (step 3), about 80 in the log
   (step 5), and one spare 50-line window for wherever the answer lands — usually the checker
   construction in step 6. Steps 4 and 8 reuse windows already open.
5. **Do not Read protected or encrypted VIP source.** It is not text and it spends the budget. What is
   readable: the release notes, the integration templates and examples, the filelists, and any
   unprotected package or interface declaration.
6. More than about 150 hits from a Grep means the pattern is too broad — anchor it on a leading quote, a
   trailing comma, or the enclosing type name before reading anything.
7. **Stopping rule.** Once the budget is spent with a stage unsettled, stop and report the furthest stage
   confirmed plus the one fact still needed. Past that point answers get invented, and an invented knob
   name is the most expensive output this skill can produce.
8. State what you covered. A stage asserted from the absence of errors is **not** confirmed, and step 8's
   `coverage` line has to separate the two.

## Procedure

### 1. Pin the release before believing any fact about the VIP

**Glob** the **VIP release** path for release-note and version files, **Read** about 40 lines at the head
of the one you find, and record the release identifier verbatim. This is first because every other fact
here is release-specific — field names, defaults, rule groupings and the coverage model all move between
releases — so a fact from the wrong release's guide is worse than no fact: it is a confident answer that
matches nothing in the code. If the slot says the integration document is a packaged set **Read** cannot
open, say so now and treat every value from it as a handoff: ask the person who read it, record who
supplied it, and mark any finding resting on it *provisional*.

### 2. Locate the three joins — this is where the whole job lives

Every protocol VIP integration is the same three joins, whoever sells it:

- **compile** — the VIP's filelist or package pulled into our build, in an order that satisfies the
  profile's **Filelist convention** and the **Simulator** it names;
- **construct and configure** — where the VIP's top component and its configuration object are created
  and their fields set, in the environment's build phase;
- **connect** — where the interface instance sits in the testbench top, wired to the DUT pins, and where
  its handle is published.

**Glob** our environment and testbench-top files, then use **one Grep** alternating the **VIP type names**
to find every file that touches the VIP. **Read** one bounded window at the construct-and-configure join
and one at the connect join. If the compile join is what is broken, stop and hand it to
`dv-build-filelist-hygiene` with the phase — `compile` or `elab` — and the first diagnostic line.

### 3. Confirm the handle reached the agent, and that the agent is in the mode you think

**One Grep** alternating the **Interface handle key** with `is_active`, `UVM_ACTIVE` and `UVM_PASSIVE`,
then **Read** a bounded window at the publication site.

A virtual-interface handle is matched on **three** things, not one: the scope the publication was made in,
the key string exactly as text, and the type it was published under — a retrieval naming the same key
under a different type parameter never matches. Whether that miss is loud depends on our own code: a
retrieval whose result is checked errors at build time, while one that quietly keeps a default handle
produces an agent that drives nothing and says nothing.

Then settle the mode. A passive agent observes and never drives, so a testbench expecting stimulus from it
runs to its timeout with no traffic and no errors — a symptom that looks like a DUT hang and is not one.
The opposite mistake, two active drivers on one interface, puts X on the bus from time zero. Count the
agents too: most protocols need an initiator and a target, and an interconnect one per port.

### 4. Make the three parameter sets agree before believing any checker

Widths, revision and optional features are declared in three places — the DUT, the interface instance, and
the VIP's configuration object — and all three must agree. Use the windows **already open** from steps 2
and 3, plus the DUT's declared values from the **Protocol profile** slot. A mismatch does not reliably
error, and each direction fails differently:

| Mismatch | What you see | Who owns it |
|---|---|---|
| Interface narrower than the DUT port | upper bits never observed; every transaction looks legal | testbench integration |
| VIP configured above the revision the DUT implements | absent optional features flagged as violations | configuration, not RTL |
| VIP configured below the revision the DUT implements | newer legal traffic flagged, **or** the newer rules silently unchecked | configuration, not RTL |
| Feature enabled in the VIP that the DUT never claimed | violations concentrated on one transaction class | read the profile again |

Rows two and three waste a week, because both produce protocol violations that look exactly like RTL bugs.
Quote all three values, with a file and a line each, before any violation is written up against the design.

### 5. Establish link-up from positive evidence, never from silence

The agent cannot start a simulation. **Ask the engineer to run the shortest test that exercises this VIP
and to save the log under the profile's Log location so it can be read from disk**, then work from that
file. **One Grep** alternating the **Link-up marker**, the **Protocol-error markers**, the **Pass marker**,
`UVM_ERROR` and `UVM_FATAL`; spend the single 80-line log window on the *first* hit. Two protocol families,
and their evidence is not alike:

- **Links with a bring-up sequence** — reset exit, training or negotiation, an agreed speed and width, then
  ready. Each stage prints its own message and stopping partway through is the common first-integration
  outcome. Record the **negotiated result**, not just the marker: a link that comes up at half the intended
  width has linked up, and reads as a pass.
- **Buses with no bring-up sequence** — nothing is negotiated. Link-up means reset is deasserted, the clock
  is running, and the first legal transfer completed. Its evidence is a non-zero transaction count from the
  monitor, not a message.

With neither a Link-up marker nor a transaction count, the honest classification is *unknown*. A quiet log
is the default output of a VIP that was never connected, and treating it as a pass is the single most
common way this integration goes wrong.

### 6. Prove the checkers are on, and that a violation would actually be visible

Three states look identical in a quiet log, and only the first is what anyone assumes: **enabled and
reporting**, where violations reach the report server at a severity that fails the run; **instantiated but
disabled**, where a field switches checking off or restricts it to one rule group while the group you care
about is a separate field; and **never constructed**, where the sub-component was gated off at build time
or a separately licensed feature was unavailable, so nothing was created at all.

**One Grep** alternating the **Checker enable knobs** with the standard report-severity overrides —
`set_report_severity_override`, `set_report_severity_id_override`, and the `+uvm_set_severity` plusarg. The
overrides matter as much as the enables: a demoted error fails nothing, and a demotion applied to one noisy
rule identifier at two in the morning silences every message sharing that identifier, for everyone, until
someone re-reads the file.

**Positive proof needs an injected violation, and only a human can make one.** Ask the engineer to drive one
deliberately illegal transfer — an unaligned access, a protocol-illegal response, whatever the
**Protocol-error markers** slot says this VIP reports — and to confirm the VIP flagged it at a severity that
failed the run. Record who did it and when. This is the most valuable step here, and the only one that
separates state one from states two and three.

### 7. Prove the coverage model is on, and that what it writes will merge

**One Grep** for the **Coverage enable knobs**. Coverage is enabled separately from checking and is usually
off by default because sampling costs runtime — so switching on "the VIP" switches on neither by itself, and
switching on checking does not switch on coverage. Three questions, in order:

1. **Is the model constructed?** The same three states as step 6, including the licensed-feature case.
2. **Is it sampling?** A constructed model whose bins are all at zero after a run that definitely moved
   traffic is not collecting. The usual causes are a sample event tied to a clock that is not running, or a
   monitor that is passive or unconnected — step 3's finding arriving late.
3. **Will it merge?** The coverage model ships *inside* the release. Data written by two releases either
   refuses to merge or silently drops the groups that differ, and the merged report cannot tell you which
   happened. Record the release identifier from step 1 against every database.

The agent cannot start a merge or a report tool. **Ask the engineer to produce the coverage report into the
profile's Coverage output location and to give you the path**; only then spend the budget's one conditional
Grep on it, looking for the VIP's own groups by the type names from step 2. With no report, say the coverage
stage is unconfirmed rather than reporting the enable field as proof.

### 8. Record the finding

Write any failure found along the way as a signature following `_shared/failure-signature-schema.md` — same
field order, same normalisation rules — then fill in this block, which reuses `class`, `run id`, `log`,
`notes` and `coverage` from the sibling skills' blocks so the two read side by side.

```
vip        : <product and release identifier, verbatim from step 1>
reached    : compile | connect | link-up | checkers | coverage
class      : design | infrastructure | unknown
evidence   : <a file path and line, or a log line number, for every stage claimed reached>
signature  : <phase>|<kind>|<where>|<what> for any failure found, or "-"
run id     : <what identifies this smoke run for us, from the profile's Run identity>
log        : <path, and the line range worth reading>
owner      : <VIP vendor | testbench integration | RTL | infra>
blocked by : <the one thing stopping the next stage, or "-">
coverage   : <which stages were confirmed from a file, and which are asserted from silence>
notes      : <anything the next person would otherwise rediscover, including any fact that came from a person rather than a file>
```

`reached` names the furthest stage with evidence behind it, so `reached: connect` means link-up was never
demonstrated — not that it failed. The `coverage` field is the honesty line every skill in this pack carries,
and here it means *how much of this checklist was confirmed*, not functional coverage; the
functional-coverage result is step 7's finding and belongs on the `evidence` line. If a line cannot be
filled from text on disk, write `?` rather than inventing it.

## Gotchas

- **Silence has three causes and a quiet log distinguishes none of them**: nothing was driven, nothing was
  checked, or everything really was legal. Only a non-zero transaction count separates the first from the
  other two, and only an injected violation separates the second from the third.
- **Checking and coverage are separate switches, and coverage usually defaults off.** A release note saying
  protocol checking is on by default is silent about the coverage model, because collecting it costs
  simulation time the vendor is not going to spend for you.
- **A demoted error fails nothing.** A severity override lives in one line of one file, applies to every
  message under that identifier, and survives forever because nobody greps for it — which is why step 6
  checks the overrides and the enables in one pass.
- **A passive agent explains an empty run better than any DUT theory.** Check the mode before anyone opens a
  waveform; a testbench that times out with no traffic is far more often a mode or a handle miss than a hang.
- **Link-up at the wrong negotiated width or speed is still link-up.** The marker fires, the log looks
  healthy, and every performance number afterwards is wrong. Record the negotiated result.
- **A revision mismatch produces violations that belong to the configuration.** Before filing the first
  protocol violation against RTL, put the revision the VIP was configured to next to the revision the DUT
  claims. If they differ, that is the finding, and the RTL owner does not need it.
- **Separately licensed features fail quietly.** A feature whose licence is unavailable can leave its
  sub-component unconstructed — no checker, no coverage group, no message. The run is clean and a whole class
  of checks never existed. That is `class: infrastructure`; route it, do not debug it.
- **Coverage bins at zero and coverage never enabled are the same picture once merged.** The only thing
  telling them apart afterwards is the release identifier recorded alongside the database.
- **Most VIP checkers are inhibited while reset is asserted and re-arm on deassertion.** A mid-run reset the
  testbench asserts but the VIP is never told about leaves the checkers either complaining about entirely
  legal reset behaviour or inhibited for the rest of the run — and which you get is a property of the
  release, so read it rather than reasoning it out.
- **Upgrading the release mid-project moves the ground.** Field names, defaults, rule groups and the coverage
  model all change. Repeat this whole procedure on an upgrade, and do not carry the old coverage database
  forward either.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- every one of the five stages is either backed by a named file and line or listed as unconfirmed — no stage
  is asserted from the absence of errors
- the link-up claim rests on a Link-up marker or a non-zero transaction count, and the negotiated width and
  speed are recorded where the protocol negotiates them
- the checker claim names the enable field **and** its value, says whether the severity overrides were
  checked, and says whether an injected violation was seen to fire — and if it was, who drove it
- the coverage claim names the release identifier the database was written by
- widths, revision and features are quoted from three places — DUT, interface, VIP configuration
- `class` is infrastructure for a licence or build failure, and design only where there is real DUT traffic
  behind the violation, and the `coverage` line separates confirmed stages from assumed ones

A wrong answer typically declares the VIP integrated and clean on the strength of a log with no errors in it;
reports coverage as enabled because a field says so, with no database and no report; or files the VIP's first
protocol violation against the RTL when the VIP was configured to a revision the DUT never claimed.

## Done when

You can name the furthest stage that has a file and a line behind it, the one thing blocking the next stage,
and which stages you are still taking on trust.
