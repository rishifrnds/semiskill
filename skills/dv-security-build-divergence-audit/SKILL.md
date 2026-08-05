---
name: dv-security-build-divergence-audit
description: Enumerate every way the build that ran the security tests differs from the device that actually ships — compile-time guards around security logic, boundary inputs tied to their safe value, behavioural stand-ins for the fuse, entropy source or key store, testbench reach-in past the control under test, and security behaviour shortened for speed — then rule on which security claims survive each difference and name the evidence that would restore the rest. Use when a security sign-off or a tapeout checklist is coming up, when the security regression is entirely green in a configuration nobody has compared to the shipped one, when someone asks whether the lock was ever exercised against the value silicon can actually drive, or after an escape traced to something simulation never modelled.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: "As-Verified Versus As-Shipped: Divergence Audit for the Security Build"
  semiskill-function: design-verification
  semiskill-role: security-verification-engineer
  semiskill-level: principal
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-06-09
  semiskill-tags: security, sign-off, build-configuration, stand-in-models, tie-off, force-release, tapeout, escape
---

# As-Verified Versus As-Shipped: Divergence Audit for the Security Build

Every security claim a team signs was produced by a *build*, and no build is the device. The lock was proved against an
input the testbench held at one value; the lifecycle test ran against a fuse model whose array is all zeroes; the wipe
counter was cut to four cycles. None of that is misconduct — it is how simulation is made to finish — and none of it
shows in results that stay green either way. This procedure sweeps those differences in five fixed classes, rules on
every numbered claim with one of four verdicts, and names the evidence that would restore each claim that does not
survive. The output is **a difference list, an adjudicated claim list and an honest coverage line**.

## When to use something else

This skill consumes claims; it does not manufacture them. `dv-security-negative-tests` enumerates the illegal actions
that must be refused and audits them for the vacuous pass — its matrix is a claim source for step 2, and a row of it is
a claim here, never a rewrite. `dv-asset-flow-property-authoring` holds the flow specification and property list, whose
`assumes` field records half the class A and class B differences below. `dv-secure-register-policy-audit` says whether a
register's security attribute is represented and exercised, `dv-crypto-kat-coverage-audit` whether a claimed algorithm
has a vector some test applied; neither asks whether the key store and lifecycle state those ran against are shipped.

Two neighbours are close enough to confuse. `dv-build-filelist-hygiene` is for a build that **failed** to compile or
elaborate and audits one filelist's entries; this build compiled perfectly, and the question is what it compiled *in*.
`dv-config-space-coverage` picks which of a legal parameter space to regress — a coverage argument over configurations
all of which ship, where this is a differencing audit between two, one of which does not. One failing security test
goes to `dv-sim-log-first-error`.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Security build definition | [[FILL: how our security regression's build is named, which file holds the define and parameter set it applies, and which source root it compiles]] | DV infra |
| Shipped configuration record | [[FILL: where the configuration the part actually ships in is recorded — the define and parameter set the production netlist is built from — and whether it can be read from disk]] | SoC integrator |
| Claim source | [[FILL: which artifact holds the security claims we sign off against — negative-test matrix, property list, known-answer rows, sign-off checklist — its path and revision, and whether it can be read from disk]] | security architect |
| Security identifiers | [[FILL: the identifier fragments our lock, key, lifecycle, alarm and zeroise logic is actually named with, so a sweep can be anchored on them rather than on the word secure]] | design owner |
| Boundary security inputs | [[FILL: every port on this block carrying a test, scan, debug-enable, lifecycle, secure or privilege attribute or a key-valid handshake, named as the RTL spells it, and the range silicon can drive on each]] | block owner |
| Stand-in models | [[FILL: which behavioural models stand in for the fuse or one-time-programmable macro, the entropy source, the PUF, the key store and any secure memory in this build, where those files live, and who owns each]] | DV infra |
| Reach-in idioms | [[FILL: the testbench reach-in constructs our flow permits — the force, release, deposit and hierarchical-reference spellings, plus any house macro that wraps them]] | DV lead |
| Shortened behaviours | [[FILL: which security durations and counts our simulation build shortens — wipe duration, zeroisation and lockout counters, key-schedule rounds, anti-rollback, retry limits, entropy startup counts — where each shortened value is set, and the shipped value beside it]] | block DV owner |

Four facts below are pack-wide and live in `_shared/team-profile.md`; read them there. **Build log location** for the
elaboration log step 1 needs, **Run identity** for the summary block, **Area to owner map** for every `owner` field,
**Sign-off** for whoever accepts a residual difference. Two rows above are deliberately **narrower** than one of those.
*Security build definition* is narrower than **Build log location** — that says where build output lands, this says
*which* build the security regression used and what it applied. *Shortened behaviours* is narrower than **Run
identity**: an identity separates two runs of one build, this asks what the build changed before either run started.
**If a slot is unfilled, stop and ask. Do not guess** — an invented define name clears claims nobody checked.

## Retrieval budget — read this before opening anything

An SoC tree holds thousands of files named for `secure`. Enumeration and adjudication are free; opening things costs.

1. **Grep, Read and Glob work on files on disk.** A configuration living only in a spreadsheet, a deck or a tracker
   cannot be opened: treat every value in it as supplied by a person, record who, and say so.
2. **Three Glob calls** — Security build definition and Shipped configuration record in step 1, Stand-in models in 5.
3. **Seven Grep calls, one per sweep plus a spare.** Step 1, the elaboration log for the applied define list; step 3
   class A; step 4 class B; step 5 class C; step 6 class D; step 7 class E; one spare for re-anchoring.
4. **Six windowed Reads of about 60 lines** — the elaboration banner (1), the claim source (2), the densest tie-off
   site (4), a stand-in model body (5), the reach-in cluster (6), one spare step 3 may take. Steps 8 and 9 open none.
5. **Scope every Grep to the source root the Security build definition names**, or vendor IP and neighbouring blocks
   blow the hit cap on the first call. Above about 150 hits the anchor is too broad; that retry is rule 3's spare.
6. Stopping rule: when the Greps are spent, stop, write every unswept class `unknown`, then state the coverage — which
   classes were swept, which slots unfilled, how much of the root was reached. Unswept is never `benign`.

## Procedure

### 1. Pin both configurations, and take the applied define set from the banner

Two **Glob** calls — the **Security build definition** and the **Shipped configuration record** — with a revision or
date stamp written down for each; a list built against last year's shipped configuration is worse than no list. If the
shipped side exists only as a synthesis script, an integration guide or a page, **ask the SoC integrator for the define
and parameter set the production netlist is built from**, record who supplied it, and mark those rows provisional.

A filelist records what the build was *asked* for; the set that reached the compiler arrives from the invocation, a
wrapper script, the environment and the filelist together, and only the elaboration banner lists all four at once. The
agent cannot start a build: **ask the engineer for the path to the security build's saved elaboration log** — the
profile's **Build log location** row says where ours land — then one **Grep** for the banner's define and parameter
markers and one windowed **Read** at the first hit. Copy it verbatim; without it every class A row is `unknown`.

### 2. Number the claims — this list is the denominator

One windowed **Read** of the **Claim source**. Number every claim `C1`, `C2`, … in the source's own words, so a
reviewer holding the matrix, property list or checklist can line the two up without translating. A claim says what must
be true of the *device*: a test name is not a claim, nor is a covergroup percentage. If the source cannot be read, **ask
the security architect to export it to text and give you the path, or to read the claims out**, and attribute them.
Never assemble the list from the tests that exist — one derived from the suite can only conclude that the suite covers
itself. Rank as you number; step 8 runs out of budget before it runs out of claims.

### 3. Class A — compile-time guards around security logic

One **Grep**, a single alternation of the conditional-compilation directives (`ifdef`, `ifndef`, `elsif`) against the
**Security identifiers** fragments, scoped to the source root. Compare each hit's condition against step 1's applied
list in the window already open, and record the polarity verbatim: `ifndef` inverts the sense, so a region guarded by a
synthesis-only macro is present in simulation and absent in the netlist.

| Guarded region is | What it means | Verdict floor |
|---|---|---|
| compiled in both | no difference; record it with file and line rather than omitting it | `benign` with evidence |
| compiled in neither | dead in both, so no claim rests on it — though security logic shipping in no configuration is a finding for someone else | `benign` |
| compiled only in the shipped configuration | logic that ships and was never analysed | `unknown` |
| compiled only in the security build | real security logic present only where the tests ran, **or** a bypass — debug hook, shortened path, permissive default — the regression itself switches on; spend the spare Read on the body before deciding which | `weakens` or `voids` |

### 4. Class B — boundary inputs held at their safe value

One **Grep** over the **Boundary security inputs** names across the testbench connection and driver area, then one
windowed **Read** at the densest cluster. Per input record where it is driven, the values it took, and the range the
slot says silicon can drive. A tie-off outside the files you opened — a wrapper, a bind, a chip-level default
parameter, a pad cell — is reported as unlocated, never as driven.

| What you find | Why it matters |
|---|---|
| held constant at the safe value | the lock was never exercised against the value an attacker can present; if the constant is the value that makes the control unreachable, the claim is `voids` rather than `weakens` |
| driven over a subset | two of six privilege encodings, the defined lifecycle states but none of the reserved ones — name the untried values, they are the row |
| not driven at all | bound to something that never changes, or to nothing |

### 5. Class C — behavioural stand-ins for the parts that hold the secret

One **Glob** of the **Stand-in models** directory, one **Grep** confirming which of those module names the security
build actually bound, one windowed **Read** of the highest-ranked body. An unbound model is not a difference.

| Shape in the model body | What it makes pass |
|---|---|
| a constant return — all-zero fuse or one-time-programmable array, status always ready, key-valid asserted from time zero | lifecycle and provisioning tests, in the wrong state |
| an always-successful handshake — a key store answering on the cycle it is asked | everything that should have been checked while the key was not yet available |
| determinism where the device is random — an entropy stand-in returning a counter | the startup health test, every run |
| the interface without the timing — protocol faithful, latency, back-pressure and error responses not | every claim resting on behaviour under back-pressure or error |

### 6. Class D — testbench reach-in past the control under test

One **Grep** over the **Reach-in idioms** across the security test area, then one windowed **Read** at the densest
cluster. Classify every site **per test**, not per line — the same construct is legitimate in one test and fatal in
the next — and carry `not-applicable` on rows of the other four classes.

| Role | What it looks like | Effect on the claim |
|---|---|---|
| `instrument` | ground truth about something the test does not claim to prove — a back-door read confirming the key material is present, so a refusal is not passing on an empty store | none; these are good and should stay |
| `setup-shortcut` | it reached a state the front door was supposed to refuse — forcing a lifecycle register to a provisioned value, depositing an unlock token, releasing a debug gate | any claim about how that state is *entered* is `voids` |
| `check-shortcut` | the observation was taken past the control — reading the protected value through a hierarchical reference, or reading a denial through the back door | `voids`: the path the claim is about was never asked |

### 7. Class E — security behaviour shortened for speed

One **Grep** over the names in the **Shortened behaviours** slot across the parameter and configuration source, checked
against step 1's applied overrides. Per name write the shortened value, the shipped value, and which the claim was
proved under — a test or proof closed under an override is a claim about the override. What matters is not total runtime
but the *window* the shortening removes: a wipe cut to four cycles makes "the clear completes before any state permits a
read" trivially true, where the real case is the long half-wiped window in which something asks for the data. Same for
lockout and retry counters, anti-rollback, rounds and startup counts — a counter at its first value tests only existence.

### 8. Adjudicate, then name the compensating evidence

No retrieval. Cross every difference from steps 3 to 7 against every claim from step 2, one verdict per pair.

| Verdict | What has to be true to write it | The mistake it prevents |
|---|---|---|
| `benign` | you can name the module or path the claim's mechanism runs through and show, with a file and line, that the difference is outside it | writing it because nothing failed — absence of a symptom is not the test |
| `weakens` | the control was genuinely exercised, but over less than the device presents: fewer values, fewer states, a shorter window | promoting a partial exercise to a proof because the row is otherwise green |
| `voids` | the evidence is produced by the difference itself — remove the stand-in, tie-off or reach-in and the test cannot run at all | letting a test that only passed because of a shortcut count as evidence |
| `unknown` | the class was not swept, a slot was unfilled, or deciding needs a run or proof nobody has produced | the downgrade to `benign` this whole audit exists to prevent |

A difference changing what the *test could reach* is usually `voids`; one changing only *how much* of a reachable space
was covered is `weakens`; a claim touched by several takes the worst, never the average. Every `weakens` and `voids` row
names one of these artifacts and one person from the **Area to owner map** — "more testing" is not an artifact:

- **shipped-configuration run** — the security tests rebuilt under the shipped define and parameter set.
- **gate-level run** — the named tests on the netlist; every class A row needs one, a netlist having no directives.
- **proof re-run** — the property discharged again with the parameter override removed.
- **vendor-model run** — a rebuild with the real fuse, entropy or key store model replacing the stand-in.
- **widened-stimulus run** — the boundary input driven over the range the slot says silicon can drive.

Each is a **handoff**: ask the named owner to produce it and give you the path to the output. The agent cannot start a
build, a simulation, a regression or a formal engine and **must never write down what one would have shown**.

### 9. Write the three blocks and the coverage line

`guard`, `tie-off`, `stand-in`, `reach-in` and `shortened` are classes A to E in that order.

```
difference id    : D1
build difference : guard | tie-off | stand-in | reach-in | shortened
reach-in role    : instrument | setup-shortcut | check-shortcut | not-applicable
as verified      : <what the security build actually did, with file and line>
as shipped       : <what the shipped configuration does instead, and where that is recorded>
owner            : <from the profile's area-to-owner map, or blank plus the candidates>
evidence         : <file and line for every claim above, or the person who supplied it>
notes            : <what the next person would otherwise have to rediscover>
```

```
difference id : D1
claim         : <the claim number and its sentence, quoted from the claim source>
claim verdict : benign | weakens | voids | unknown
bearing       : <one sentence on how this difference bears on this claim>
restores      : <the artifact from step 8 that would restore the claim, or none-needed>
produced by   : <the named person or team who must produce it>
```

```
configs     : <the security build's define and parameter set, and the shipped set, with the path of each>
claim list  : <n numbered claims, the artifact each came from, and its revision>
sweep       : <which of the five classes were swept, and which were not>
tally       : <n benign / n weakens / n voids / n unknown, worst-first>
run id      : <whatever identifies the security regression this rests on, or no-run-read>
coverage    : <how much of the source root the sweep reached; which slots were unfilled>
```

Write `?` for anything not traceable to text on disk. **The denominator in `tally` is the number of claims step 2
numbered, never the number you adjudicated** — "adjudicated 9 of 31, the other 22 numbered and unopened" is a document
a reviewer can plan against, where "no voided claims found" gets a part taped out with a hole in it.

## Gotchas

- **The filelist is not the define set.** Defines also arrive from the invocation, a wrapper script and the environment,
  so an audit built from filelists misses the guard switched on by a variable in someone's shell profile.
- **A wildcard port connection hides a tie-off, silently.** An implicit connection binds the port by name to a net in
  the enclosing scope, so a Grep for the port at the instance returns nothing and the constant tie is never seen.
- **An `ifdef` whose guarded region is the real lock is what class A exists for.** A macro set to make something else
  finish also selects a permissive branch, and the whole negative suite runs green against a lock that was compiled out.
- **An all-zero fuse array is a lifecycle state, usually the most permissive one.** It decodes to blank or
  unprovisioned, so a test asserting that a provisioned part refuses an access passes in a state that refuses nothing.
- **The same reach-in is an instrument in one test and a setup shortcut in the next.** A back-door read proving the key
  is present is ground truth; the same force used to reach a state the front door refuses voids the transition claim.
- **A released force can hold for the rest of the run.** Releasing a net with no continuous driver leaves it at the
  forced value, so a one-line setup shortcut stays in effect through checks written hundreds of lines later.
- **A shortened counter tests existence, not arithmetic.** Reduced to its first value it never wraps, never saturates
  and never crosses the boundary the design gets wrong; a shortened wipe removes exactly the half-erased window.

## Human verification — what a wrong answer looks like

Before treating the audit as sign-off evidence, check:

- every `benign` row names the module or path the claim runs through and shows the difference outside it, with a file
  and line. A `benign` justified by "no test failed" is `unknown` wearing a verdict.
- every class the sweep did not reach is `unknown` in the blocks and named in `sweep`; and the applied define set came
  from a banner that was read, a set inferred from a filelist being a reconstruction and labelled one.
- no row reports what a shipped-configuration run, a gate-level run or a re-run proof *would* have shown; those are
  handoffs, and an unarrived handoff leaves the row where it was.
- every `weakens` and `voids` row names one artifact and one person; `reach-in role` is filled on every class D row,
  classified once per test rather than once per file; and `tally`'s denominator is what step 2 numbered.

A wrong answer typically sweeps the classes that were easy to Grep and calls the rest clean, clears a claim because the
regression is green — the exact condition this audit is invoked under — or reports a stand-in as faithful unopened.

## Done when

Every numbered claim carries a verdict against every difference that touches it, every `weakens` and `voids` names the
artifact and the person that would restore it, and the coverage line says what the sweep actually reached.
