---
name: dv-compliance-test-authoring
description: Turn one normative statement from a protocol specification into one directed compliance test and the traceability row behind it, in the shape the shipped suite already uses. Use when adding a test for a newly ratified clause, when an audit finds a requirement with no test behind it, when a customer asks which test covers a clause, or when you have a clause number and do not know whether the suite already covers it.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Directed Compliance Tests from Spec Normative Items
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: fresher
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-04-09
  semiskill-tags: compliance, conformance, protocol, vip, traceability, test-authoring, spec
---

# Directed Compliance Tests from Spec Normative Items

A shipped compliance suite is judged on two things — that every mandatory statement in the spec has a
test behind it, and that the test would go red if a device broke that statement. Tests added under
audit pressure satisfy the first and quietly fail the second: they never reach the condition the
clause is about, they check something the device produces anyway, and they pass green on an
implementation that does not carry the clause at all.

The output is three things: **a drafted test in the suite's own template, a traceability row, and a
coverage line** saying which parts rest on text you actually read. Not a summary of the clause.

## When to use something else

`dv-protocol-checker-rule` starts from the same sentence and produces something different: a numbered
always-on passive rule that watches every test in the suite. This skill produces the directed test
that *creates* the condition, plus the row. Most mandatory items want both — the rule does the
judging, the test makes sure the rule ever gets the chance. If the obligation is one the monitor
could judge on ordinary traffic with no special stimulus, write the rule there first and come back
here for the stimulus and the row.

A whole chapter or databook rather than one sentence is `dv-spec-feature-extract`. Two readings that
both look legal is `dv-spec-interpretation-ledger` — do not pick one and bake it into a shipped test.
A published ECN or a new revision is `dv-spec-ecn-delta`, which hands you the item list; come back
here one item at a time. Auditing the matrix as a whole is `dv-testplan-traceability-review`.

Afterwards: a draft that does not compile is `dv-build-filelist-hygiene`; one that compiles, runs and
fails is `dv-sim-log-first-error`. Register or field behaviour rather than protocol on the wire is
`dv-ral-bringup`. If you cannot yet name the paths of the suite, the matrix and the run list, start
with `dv-repo-orientation` — everything below assumes those three.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Spec source | [[FILL: which specification and revision this suite certifies against, whether that document is a file the agent can open, and how much of its wording we are permitted to reproduce inside the repository]] | compliance lead |
| Conventions clause | [[FILL: what our spec's own conventions section says its modal verbs mean, and which of them it treats as normative]] | compliance lead |
| Requirement key | [[FILL: how one normative item is keyed for us — clause number, a requirement id the spec carries, or a house id — and whether that key includes the spec revision]] | compliance lead |
| Traceability matrix | [[FILL: where our requirement-to-test matrix lives, its format, and the exact order of its columns]] | VIP suite owner |
| Result vocabulary | [[FILL: the exact status strings a matrix cell is allowed to hold]] | compliance lead |
| Suite location | [[FILL: where the shipped compliance tests live, and which existing test we treat as the canonical example to copy]] | VIP suite owner |
| Test list registration | [[FILL: how a new test is added to the suite's run list so it actually runs, and what a row in that list carries]] | VIP suite owner |
| Capability gating | [[FILL: how a test declares itself not-applicable when the feature is not implemented, and where the capability flags for a device under test are set]] | VIP architect |
| Checker inventory | [[FILL: where the VIP's always-on protocol checks live and how each one is named or numbered]] | VIP architect |
| Stimulus hooks | [[FILL: the VIP knobs that let a test create an illegal, corner or error condition — name them exactly]] | VIP architect |

Log location and Sign-off are pack-wide facts and live in `_shared/team-profile.md` — read them from
there rather than re-asking. Step 7 needs the first when a log comes back; step 8 needs the second.

Two rows above look like profile rows and are not. **Result vocabulary is narrower than the profile's
Pass marker**: the pass marker is a string a run prints into a log, the result vocabulary is the set
of strings a matrix cell may hold, and neither is derivable from the other. **Test list registration
is narrower than the profile's Filelist convention**: the filelist decides what compiles, the run
list decides what runs, and a test can be in one and missing from the other.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented status string or hook
name produces a test that looks finished, never runs, and is found by a customer.

## Retrieval budget — read this before opening anything

A protocol spec runs to hundreds of pages and a shipped suite to thousands of files. You are
answering one question about one sentence, so the budget is small on purpose.

1. **Grep and Read work on files, not on chat text.** If the sentence arrived pasted, ask for the
   path to the file holding it — a requirements export, a clause excerpt, the suite's own copy of the
   wording. If the spec is a format Read cannot open, or one the Spec source slot forbids copying
   into the repository, say so and work from the pasted sentence with every field resting on it
   marked *provisional*. You have not read the clause; you have read a quotation of it.
2. At most **two Glob calls** — one for where requirement text lives, one for the suite's tests.
3. At most **five Grep calls over our repository**: the matrix and the suite-plus-checkers in step 4,
   the nearest sibling test in step 5, the run list in step 6, and one spare. Each log the engineer
   returns in step 7 costs one further Grep, at most two.
4. At most **four bounded Read windows**: about 40 lines at the requirement text (step 1), 40 at the
   checker (step 4), 80 at the canonical example test (step 5), 40 at the matrix header and its
   neighbouring rows (step 7). Step 2 reuses step 1's window and step 6 reuses step 5's.
5. If a Grep for a clause key returns more than about 200 hits it is too generic — a bare 7.2 matches
   version strings, offsets and array bounds. Anchor it with whatever punctuation the matrix and the
   tests actually put around it before reading anything.
6. **Stopping rule.** If after the canonical-example window the template's fixed parts are still not
   clear, stop and ask the suite owner which test to copy. A test written against an inferred
   template is sent back in review and costs more than the question would have.
7. State what you covered — how many of the sentence's obligations you handled, and whether the
   wording came from a file or a pasted fragment. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Resolve the sentence to text on disk, and to a key

If the clause arrived pasted, resolve that first — budget rule 1. **Glob** for where requirement text
lives under the **Spec source** slot, then one bounded **Read** of about 40 lines around the clause so
you have the sentence *and* its neighbours. Neighbours matter: a definition one paragraph up routinely
supplies the precondition the sentence assumes without restating it.

Record four things verbatim — clause number, the requirement id if the spec carries one, the spec
revision, and the sentence itself, quoted only as far as the Spec source slot permits. Convert the
first three into the **Requirement key** slot's form; that becomes `req key` and `spec ref` in step 8.

Then **count the obligations, not the sentences.** "The device shall assert A and shall not assert B
until C" is two obligations, two tests and two rows. Splitting is cheap now; merging produces one red
cell later that maps to no single clause — the exact failure the matrix exists to prevent.

### 2. Classify the obligation using the spec's own conventions

Reuse step 1's window. Many specs adopt the familiar keyword convention by reference, several redefine
it, and a few use the same words in explanatory prose — so the **Conventions clause** slot governs,
not habit. Read this table as the common case and let that slot overrule it.

| Wording | Usual meaning | What it produces here |
|---|---|---|
| shall | mandatory | one directed test, one mandatory row |
| shall not | mandatory prohibition | a test with a stated bound — see the second gotcha |
| must, must not | mandatory in most specs, but some reserve them for explanatory prose | check the conventions clause before treating either as mandatory |
| should, should not | recommended, not required | a test may exist, but a failure is not a compliance failure |
| may, need not, optional | permitted, either way conformant | not a test that the device does it; at most one that the suite tolerates both |
| is, does, present indicative | descriptive in some specs, normative in others | the conventions clause decides; never guess this one |
| reserved | not a behaviour at all | whatever the conventions clause says about reserved encodings, and nothing else |

Set `strength` in step 8 to the spec's **own word**, not a paraphrase — that field is shared with
`dv-protocol-checker-rule` and the two are compared exactly. Map `must` to `strength: shall` only when
the conventions clause says they are equivalent, and record in `notes` that you did. Then set
`applies` separately: `applies: conditional` when the obligation holds only under a stated
precondition, which is most of them, and which decides whether step 6 needs a witness.

### 3. Decide testability before drafting anything

The step people skip, and the only one that prevents an invented test.

| Category | What it means | What to do |
|---|---|---|
| `interface` | visible in the signalling the VIP monitor already observes | draft the test |
| `hook` | visible only if the test creates an illegal, corner or error condition | draft it **only** if the **Stimulus hooks** slot names the knob; otherwise stop and ask |
| `window` | true only over a long window, across a reset, or across many transactions | draft it and state the window in the row — a sampled claim, not a proof |
| `not-observable` | constrains the other agent, is electrical or analog, is about documentation, or deliberately leaves the implementation free | no test — write the row with the reason, using the **Result vocabulary** slot's string for an uncovered item, and stop |

A `testable: not-observable` row is a good outcome. An honest gap is auditable; a test invented to
fill a cell is a green row with nothing behind it, found later by whoever trusted it.

### 4. Find out whether it is already covered — the matrix first, then the checkers

Two **Grep** calls. First the **Traceability matrix**, with one pattern alternating the requirement
key with a distinctive four-to-six word fragment of the sentence. Both, not just the key: clause
numbers get renumbered between revisions, so the key alone misses a row filed under the old number,
and the wording alone misses a row whose author paraphrased.

Second the suite and the **Checker inventory** area, for the same key. Three outcomes:

- **A test already claims it.** Stop. Report which test, and whether its wording still matches this
  revision's sentence. A second test for one obligation splits the evidence across two cells.
- **An always-on checker covers it, but nothing creates the condition.** The common case. What is
  missing is *stimulus*, not another check — draft a test that reaches the condition, let the existing
  checker judge it, and put that checker's name in `check`. One bounded **Read** of about 40 lines at
  the checker gives its exact name and what it actually compares; never copy that name from memory.
- **Nothing at all.** Continue — and if the obligation is judgeable on ordinary traffic, say in
  `notes` that a passive rule belongs beside this test, per `dv-protocol-checker-rule`.

### 5. Read the canonical example, and list the template's fixed parts

**Glob** the **Suite location**, then one **Grep** for the nearest sibling — same protocol area and
the same shape as yours, so a prohibition test for a prohibition. Then one bounded **Read** of about
80 lines of it.

Write down the parts you will copy unchanged rather than reinvent: the header block and every field
in it, the naming convention the file and the test class follow, the registration macro, which phases
the test uses, how the clause reference is carried in the file, how capability gating is expressed,
and how a check reports its result. A compliance suite is reviewed for uniformity as much as for
correctness, and a test that is right but shaped differently is sent back.

**Never draft from a blank file.** Every convention you cannot see in that window is one you would be
inventing.

### 6. Draft the test — four parts, in this order

The agent drafts text; the engineer saves and commits it. Keep the parts visibly separate, because a
reviewer checks them separately.

1. **Reach the precondition.** Set the configuration and drive whatever the clause assumes has already
   happened. If that needs an illegal or corner condition, it comes from a knob named in the
   **Stimulus hooks** slot, never an invented one.
2. **Prove the precondition was reached.** A separate observation whose only job is to confirm the
   condition occurred, and which fails the test when it did not. This is `witness`. Skip it and a
   conditional obligation passes vacuously — the first gotcha, and the defect that survives review
   because the test does pass.
3. **Apply the stimulus** the clause is about, once, at the boundary rather than the comfortable
   middle of a range.
4. **Check the response.** Either call the checker found in step 4, or write one check whose message
   string you choose now and write down — step 7 Greps the log for exactly that string.

Numbers in the requirement are the spec's or they are configuration. A bound that varies with mode or
line rate is read from where the **Capability gating** slot says a device's flags are set, never
hardcoded from the one value you happened to see. If the obligation applies only when an optional
feature is implemented, gate the test on that flag and make the skipped case report the
not-applicable string from the **Result vocabulary** slot — never a pass.

Finally, one **Grep** of the run list for a sibling's name gives you the **Test list registration**
row verbatim; emit the new row beside the draft. Do not edit the matrix or the run list yourself —
they are shipped artifacts, and both rows belong to a human who reviews them first.

### 7. Ask for two runs, and Grep for your own message

The agent cannot start a simulation. **Ask the engineer to run the drafted test twice — once as
written, once with the check's expected value deliberately changed so it must fail — and to give you
the path to both logs** under the profile's Log location.

Then one **Grep** of each log for the message string you chose in step 6. You know it verbatim
because you wrote it, so it needs no slot. Read the two together:

- absent from the first log means the check never ran — the test is vacuous whatever its result said.
  Go back to part 2 of step 6. That is `fired: not-confirmed`.
- present and passing in the first, present and failing in the second, is the only evidence that this
  test distinguishes a conforming device from a broken one. That, and only that, is `fired: confirmed`.
- no second run yet is `fired: not-run`, and the row ships that way rather than pretending.
- a log whose run died before the test started is a different problem — take it to
  `dv-sim-log-first-error` rather than diagnosing it here.

One bounded **Read** of about 40 lines at the matrix header and the rows either side of yours confirms
the column order and the exact spelling of the status strings before you set `result`.

### 8. Write the row and state the coverage

Field names are shared with `dv-protocol-checker-rule` so the two blocks read side by side.

```
req key    : <our requirement key for this item, in the form the matrix keys rows on>
spec ref   : <document name, revision and clause, in our citation form>
statement  : <the normative sentence, verbatim, and who supplied it>
strength   : shall | shall-not | should | may | reserved
applies    : unconditional | conditional
testable   : interface | hook | window | not-observable
test       : <the test name, and the path the draft belongs at>
check      : <the checker this test exercises, as the checker inventory names it, or new-in-test>
witness    : <what proves the precondition was reached, and whether it was seen in a log>
capability : <the capability flag the test is gated on, or ungated>
neg test   : <what was changed to make the check fail, and the path of that log>
result     : <one string from our result vocabulary, blank until a run has reported one>
fired      : confirmed | not-confirmed | not-run
coverage   : <obligations in the sentence and rows written; wording from a file or from a fragment>
notes      : <anything the next person would otherwise have to rediscover>
```

Fill every line from text on disk or write `?`. Then hand it to whoever the profile's **Sign-off** row
names, with the drafted test and the registration row. A row whose `result` is blank and whose `fired`
is `not-run` is an honest work in progress; the same row carrying a confident result nobody ran is
exactly what an audit is looking for.

## Gotchas

- **A conditional obligation passes vacuously far more often than it fails.** "When X, the device
  shall Y" — if the test never establishes X, nothing checks Y and the test is green on a device that
  does not carry the clause. It survives review precisely because it passes. `witness` exists for it.
- **A prohibition has a bound, and the row must carry it.** You cannot demonstrate absence over all
  inputs. Construct the conditions where a plausible implementation slips and say how many you
  constructed. "Not observed under the four conditions in this test" is earned; "the device does not
  do X" is not.
- **A checker that never fires is indistinguishable from a device that never violates.** If the VIP
  already checks this item, a second check adds a green row and no evidence. A passive rule and a
  directed test are not substitutes: the rule judges, the test creates the situation to judge.
- **Clause numbers are not stable across revisions.** A renumber silently repoints a row at a
  different requirement and the matrix stays green through it. Key on a requirement id where the spec
  has one, always record the revision, and keep enough quoted wording to re-find the clause by hand.
- **Not-applicable is not pass.** A test gated off because the capability is absent must land as the
  not-applicable string. A report counting skipped tests as passes is the lie a customer finds first.
- **Boundary values, not comfortable ones.** A range requirement is exercised at both ends and just
  outside them. A stimulus from the middle passes on implementations that get both edges wrong, and
  those are the implementations that exist.
- **Reserved is not a behaviour.** Whether a device must ignore, preserve, or return zero for a
  reserved encoding is stated in the spec's own conventions and differs between protocols. Testing
  what you remember from a different spec produces a confident, wrong failure report.
- **A parameterised bound hardcoded once fails twice.** Frozen at one mode's value it fails conformant
  devices in every other mode, and passes real violations in the mode it was taken from.
- **A test absent from the run list is a green row for a test nobody ran.** Registration is a separate
  change from the test file and the one forgotten under audit pressure. Check the run list, not the
  directory listing.
- **Do not reproduce licensed spec text beyond what the Spec source slot permits**, in the repository
  or in the conversation. Quote the minimum that identifies the requirement and cite the document by
  name, revision and clause for the rest.

## Human verification — what a wrong answer looks like

Before acting on the output, check:

- `strength` is the spec's own word, quoted rather than paraphrased — a `should` filed as `shall`
  starts failing conformant devices, and a `shall` filed as `should` ships a real gap
- `spec ref` carries a revision, and `statement` quotes enough wording to re-find the clause after a
  renumber
- every row with `applies: conditional` has a `witness`, and that witness fails the test when the
  precondition is not reached
- `fired: confirmed` appears only where a deliberately broken run reported the failure in a log that
  was actually Grepped — never because the test looks like it would fail
- `testable: not-observable` rows carry a reason and no test file, and no cell anywhere was filled by
  inventing a test to fill it
- nothing in the draft rests on a template that was inferred rather than read from the canonical
  example, and `result` holds a vocabulary string only once a run reported one

A wrong answer typically produces a test that passes on a device that does not carry the clause at
all; a row keyed on a clause number with no revision behind it; a prohibition row claiming proof of
absence; or two obligations merged into one cell that no longer maps to a clause.

## Done when

You can hand the suite owner the drafted test, its registration row, the traceability row and the
coverage line, and the only open question left is whether they like the stimulus.
