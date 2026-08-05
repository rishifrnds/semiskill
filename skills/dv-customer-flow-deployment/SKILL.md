---
name: dv-customer-flow-deployment
description: Turn our release's own stated requirements into a gap list against the customer's tree before any of the time box is spent, then fit a stage ladder and a handover into the days that were agreed. Use when standing up a flow, VIP or methodology inside a customer's environment, when a time-boxed proof-of-concept has been agreed, when a customer has sent their build scripts or a compile log and you need to know what will block before anyone travels, or when a deployment has to be handed over so their own engineers can rerun it without you.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Time-Boxed Deployment of a Verification Flow at a Customer
  semiskill-function: design-verification
  semiskill-role: applications-engineer
  semiskill-level: senior
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-07-09
  semiskill-tags: customer, deployment, proof-of-concept, vip, integration, handover, time-box
---

# Time-Boxed Deployment of a Verification Flow at a Customer

Deployments fail on the environment, not on the technology. The flow works — it works in our own
regression every night — and the engagement still ends without a result because the supported
simulator version was not the one their project is pinned to, because a licence feature nobody
checked needed a purchase order with three weeks of lead time, or because the demo on the final day
only ever ran from the visiting engineer's shell. The expensive discovery is always the one made on
day four of five.

The output is a **gap list**, a **stage ladder fitted to the time box**, and a **handover the
customer can rerun without you** — not a report that the flow was installed. This procedure reads
text files already on disk; it cannot start a build, query a licence server, join a screen-share,
open a PDF integration guide, or see anyone's terminal. Each of those is a handoff to a named
person, and each step says so rather than pretending otherwise.

## When to use something else

Mapping the customer's repository is `dv-repo-orientation`, and this skill deliberately does not
re-teach it — come back once you can name their build entry point with a path. Bringing the VIP up
inside a testbench, and proving its checkers and coverage are genuinely on, is `dv-vip-integration`;
this skill only decides when in the time box that work is attempted. The first integrated compile
break belongs to `dv-build-filelist-hygiene`, the first failing simulation to
`dv-sim-log-first-error`. When a failure has to be attributed between their tree and ours, use
`dv-customer-escalation-isolation`, then `dv-customer-defect-handoff` to make it a record; step 7
adds only what a live engagement changes about that. If the gap is that their tool version is not one
we support, `dv-tool-version-migration` is the re-baselining job that follows.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Release under deployment | [[FILL: the exact name and version of the flow, VIP or methodology we are deploying, and the path of the release tree we deploy from]] | release owner |
| Requirements file | [[FILL: which file in that release tree records its supported simulator versions, language and methodology versions and dependencies, and whether it is a file that can be read]] | release owner |
| Integration surface | [[FILL: which files a customer is expected to edit to integrate this release, and which files the next release overwrites and must therefore never be edited]] | release architect |
| Stage markers | [[FILL: for each of the five stages in step 5, the one string a log carries when that stage completed and the one it carries when that stage failed, taken from our release's own example output and our nightly regression]] | release owner |
| Exit criteria | [[FILL: what the customer and our account team agreed counts as success, written as a checkable list, and who signed it]] | account manager |
| Time box | [[FILL: how many engagement days were agreed, and what our agreement says happens to work that does not fit inside them]] | account manager |
| Data-handling rule | [[FILL: what our agreement says about their source, logs and waveforms — what may leave their site, what may be quoted in a report, and where engagement files may be kept]] | contracts owner |
| Escalation route | [[FILL: who takes a blocking defect in our own release during a live engagement, and what they need in hand to act inside the time box]] | support lead |
| Account record | [[FILL: where we write a customer's environment facts down so the next engineer on this account does not rediscover them]] | applications lead |

The **Stage markers** slot is narrower than the profile's **Fatal markers** and **Pass marker**
entries and does not replace them. Those two are pack-wide: any string our flow prints on a real
failure, and the one a clean run prints at the end, in our environment. This slot asks for one
completion string and one failure string *per stage of step 5, for this release only*, because the
question at a customer is which rung of the ladder a log proves — not whether a run passed. Where a
stage's strings genuinely are the profile's, fill it in by naming that entry rather than copying the
strings; where the release prints its own stamp, that stamp is the answer.

Three further pack-wide facts in `_shared/team-profile.md` are spent, each in an unusual way: the
profile records **our** house facts, and at a customer every one has a counterpart that is theirs,
different, and unknown until step 3 reads it. Its **Simulator** entry names what our release is
developed and regressed against — the reference our compatibility claim rests on, never a prediction
of what they run. Its **Filelist convention** entry describes how *our* filelists nest and resolve
relative paths; step 3 observes theirs from a bounded **Read** and must not assume the two agree. Its
**Bug convention** entry is spent unchanged in step 7, because the defect raised there is raised in
our tracker against our release. A customer's value is not our fact under a second name — writing one
into the profile corrupts it for every other skill in the pack.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented supported-version
range, integration file or data-handling permission is worse here than anywhere else in this pack: it
gets quoted to somebody outside the company, and the correction is a commercial conversation.

## Retrieval budget — read this before opening anything

Two trees, two budgets, and they are not the same size. Our release tree is small, documented and
known. Theirs is unfamiliar and may hold hundreds of thousands of files.

1. **Grep, Read and Glob work on files on disk.** A screen-share, a licence server, a PDF, an emailed
   excerpt and a terminal someone else is typing into are none of them files. Resolve each to a path,
   or say plainly which facts could not be established and mark every row resting on them provisional
   — which here means `found via: person`, the one mechanism step 1 defines and the only one there is.
2. **Read our release before opening theirs.** Reversing that order means grepping their tree for
   strings you have not yet confirmed our release needs.
3. **Our release tree costs 1 Glob and at most 2 windowed Reads** of about 60 lines — the
   requirements file, and the integration-surface list if it is a separate file.
4. **Their tree costs at most 6 Glob patterns, 8 Greps and 5 windowed Reads of about 60 lines.** The
   Greps are named and there are no others: one alternating over the simulator command names the
   requirements file lists; one for the methodology package their filelists compile; one for our
   release's top package or module name, which says whether an earlier engagement already left a
   copy; one for our release name and version string, which finds an older copy vendored into their
   tree; and at most four more on requirement rows those did not settle.
5. **Two allowances sit outside that, and nothing else does.** Step 6's fork check spends at most one
   **Grep** per file the **Integration surface** slot names, capped at five. Every build the customer
   attempts during the engagement costs one **Grep** and one **Read** window of about 80 lines around
   the last hit that **Grep** returned; the **Grep** alternates that stage's two **Stage markers**,
   the completion string and the failure string, and never anything else. Eight such builds are in
   scope: the five stage attempts of step 5 and the at most three substitution reruns of step 7. Past
   that one window the log is a triage job and belongs to `dv-sim-log-first-error` under that skill's
   budget, not to this one.
6. A Glob returning more than about 300 paths, or a Grep more than about 200 hits, is too broad —
   narrow it to one directory first. A result that hit your runtime's limit is "at least N,
   truncated", never a count you may quote to a customer.
7. **Stopping rule.** Stop when every requirement row carries a readiness and an actor, or when the
   budget above is spent, whichever comes first. Rows the budget never reached stay `readiness:
   unknown` with `found via: none` — counted, not quietly dropped.
8. State what you covered: how many rows came from files, how many from a person, how many were never
   reached. An unstated shortcut is far worse than a stated one, and here it is quoted back at you in
   a meeting.

## Procedure

### 1. Resolve every input to a path before promising anything

If their build script, filelist or compile log arrived pasted into a mail thread or shown on a call,
there is nothing to **Grep**. Ask for the file, or ask for it to be saved into the engagement area and
be given that path. Until a path exists you may reason over the visible fragment by eye — but say that
is what you did, and every row derived from it is `found via: person`, not `found via: script`.

**Provisional is not a fourth readiness, it is a value of `found via`.** This skill says "mark the row
provisional" in several places and there is exactly one mechanism behind that word: a row is
provisional when its `found via` is `person` or `none`, and settled when it is `script` or `log`.
Nothing else flags it, so a row you would defend in a meeting and a row somebody told you over coffee
must not both come out as `found via: script`.

Read the **Data-handling rule** slot before opening anything under their tree, and again before
writing anything down. It decides three separate things: what may be opened, what may be quoted
verbatim into the gap list, and what may leave the site at all. A procedure that reaches the right
answer by breaking that rule has helped nobody.

### 2. Read our own requirements before opening their tree

**Glob** the release tree named in **Release under deployment** for the file **Requirements file**
identifies, then **Read** it in one bounded window. Extract, verbatim and with line numbers: the
supported simulator names and version ranges, the language and methodology versions, and every
dependency the release names.

That list is the reference each later row is compared against, so it must come from the file. If the
requirements live in a format **Read** cannot open, or the slot is unfilled, say so now: the gap list
is still worth building, but every `readiness: met` in it is then a claim from a person and carries
`found via: person`, which is what marks it provisional. A compatibility statement invented here is
repeated to a customer as fact.

### 3. Inventory their environment from their files, one fact at a time

Spend the Glob allowance on paths only — build wrappers, filelists, tool configuration, the
methodology library, any existing testbench top, and whatever engagement notes exist. Do not open a
file during the survey.

Then the named **Grep** calls from budget rule 4. The first alternates the simulator command names
from step 2 across their build scripts: searching for a simulator they do not run returns nothing on
the one call meant to find their build. The second finds the methodology library their filelists
actually compile — and its version constants live in that library's own version header, whose file
name and macro names differ between UVM 1.2 and the IEEE 1800.2 releases, so **Read** the string out
of the header on their disk rather than assuming which name to expect.

Record every fact with the file and line it came from, or `?`. Two distinctions decide whether the
inventory is worth anything:

- **What their scripts name is not what runs.** A version pinned in a wrapper is a hypothesis until a
  real build echoes it. Ask their engineer to build something they already build today, in a scratch
  area, and to send the path of the log the flow wrote. That echoed version is ground truth; the
  wrapper is the guess.
- **Their filelist convention is not ours.** Take how their lists nest, and what their relative paths
  resolve against, from one bounded **Read** of a real filelist of theirs. The profile's answer
  describes our tree and predicts nothing about theirs.

### 4. Turn the difference into a gap list ranked by who has to act

One row per requirement from step 2, each carrying a readiness, an impact and — the field that
decides the engagement — an actor. Rank by actor, not by technical difficulty.

That ranking is the whole reason to do this before travelling. A gap whose actor is `us` is work you
control and can compress by staying late. A gap whose actor is `customer-it` or `commercial` has a
lead time you cannot compress at all: a licence feature to purchase, a tool version pinned by another
project's sign-off, a compiler or OS upgrade on a shared farm, an amendment before their source may
be touched. Raised on day one those run in parallel with everything else; found on day four they end
the engagement with an unfinished result and a follow-up nobody has budget for.

Three impacts, and the line between them is drawn by the stage ladder in step 5, not by how untidy the
gap feels. Mark an impact `blocking` only when the ladder genuinely cannot proceed past it. Anything
reachable by a documented, reversible detour is `workaround`, and the detour goes into the handover —
an undocumented workaround is indistinguishable from a fork six months later. `cosmetic` is the
narrow third case: the requirement is not met, the ladder reaches `artifact` anyway, and nothing has
to be detoured around — a supported-version range they sit one patch level outside, a dependency
present under a different name, a deprecation warning our release prints in their environment. It is a
recorded deviation, not a task: it needs no actor beyond `us`, no date, and no line in the plan.
The test is mechanical — if you cannot say which stage it stops or which detour it forces, it is
`cosmetic`, and if you find yourself writing a workaround for it, it never was.

### 5. Order the time box so the longest-lead failure is proved earliest

Five stages, in this order. Each is a handoff: ask their engineer to attempt the stage in a scratch
area and to give you the path of the log it wrote, then spend that log's one **Grep** and one **Read**
window from budget rule 5. The **Grep** alternates that stage's two **Stage markers** — the string
that says the stage completed and the string that says it failed — and the **Read** window opens
around the last hit it returned, because that is the one that decides the stage. A log carrying
neither marker has not reached our release at all: it failed in their build before that, which is
`dv-build-filelist-hygiene`'s job and not evidence about this stage either way.

1. `tools` — the supported simulator, and the licence features it needs, are reachable from the
   account the work will actually run under. Not from anyone's personal account.
2. `standalone` — our release compiles and elaborates on its own, in their environment, from our own
   example filelist.
3. `integrated` — it compiles inside their build, from their filelists, with their macro definitions
   and their include-path order. This is the stage that produces the surprises.
4. `connected` — it is bound to their design and moves one transaction end to end. The work inside
   this stage is `dv-vip-integration`'s, not this skill's.
5. `artifact` — it produces the thing the **Exit criteria** name, in a form they accepted.

Write the **Exit criteria** list into the plan on day one and treat every later addition as a change
with a date and a name against it. Criteria drift upward silently otherwise: "it works" becomes "it
works in our regression" becomes "it finds the bug we already knew about", and the engagement is
judged against the last version anyone said out loud.

Reserve a named block at the end of the **Time box** for handover, and stop adding scope on a day you
name in advance. What happens to work that does not fit is recorded in that same slot — that answer,
not an estimate of mine, decides whether the reserve is an afternoon, a day, or a second engagement.

### 6. Keep the integration upgradable, and record every fork

Every edit outside the **Integration surface** is a fork you will support until someone deletes it.
The patch made on Thursday afternoon to get the demo running is the same patch that makes the next
release un-installable at this account.

Spend the fork allowance from budget rule 5: for each file the **Integration surface** slot marks as
never-edited, one **Grep** of their copy for a distinctive line from ours — a header stamp, a version
constant, a declaration you can quote from the release tree. A miss means their copy has diverged.
This is a spot check of named files, not a tree comparison, so report it as `n of m files checked`;
**Read** and **Grep** cannot diff two trees, and claiming a clean integration from five files is
exactly the error this step exists to prevent.

Record each divergence with a path, a line and the reason it was made, even where you intend to
upstream it next week. Intent is not a record, and the next engineer inherits the tree, not the
intention.

Then inventory what of ours is now in their tree, and fill in `left behind` from that inventory —
this is the step that produces it, and no other step does. It is a different list from `forks`: forks
are edits to *their* copy, and this is *our* material sitting at their site. Write it from what you
and the engagement put there — the release tree that was unpacked, the example filelists and tests
copied out of it, the patched build wrapper, the scratch area nobody cleared. It costs no budget
because it is a list of what you did, not a search of their disk, and a **Glob** of their tree could
not tell ours from theirs anyway. Against each entry name the agreement under which it stays, from the
**Data-handling rule** slot; anything with no agreement behind it is either removed before you leave
or raised with the **Escalation route** owner as something that must not have been left. An
unreleased build of ours forgotten in a customer scratch area is found by their next audit, not by us.

### 7. Escalate a defect in our own release without moving their source

Attribute first with `dv-customer-escalation-isolation` and record with `dv-customer-defect-handoff`,
using the profile's **Bug convention** and the **Escalation route** slot. Two things a live,
time-boxed deployment adds to that, and they are the whole of this step.

The first is what may travel. Shrink with `dv-minimal-reproducer`, but change what the shrink
optimises for: the usual objective is the fastest reproducer, and here it is **the reproducer that
uses none of their source**, because the **Data-handling rule** decides what may leave the site and a
reproducer that cannot leave is one nobody at home can act on. That objective adds three substitutions
that are not among `dv-minimal-reproducer`'s own axes and are this skill's alone. You do not perform
them and cannot: each is a separate handoff, one at a time and in this order.

1. Ask their engineer to swap their design for our example design or a stub, rerun the failing
   sequence, and send you the path of the log.
2. If it still fails, ask them to swap their stimulus for our example test, rerun, and send the path.
3. If it still fails, ask them to strip their configuration back to our example configuration, rerun,
   and send the path.

Each returned log costs that build's one **Grep** and one **Read** window from budget rule 5, and the
**Grep** is the `connected`-stage **Stage markers** pair — the question at every substitution is
whether the same failure signature is still there, not whether the run got slower. Confirm the
signature from `_shared/failure-signature-schema.md` matches the original before calling it survived.
A defect whose signature survives all three substitutions uses none of their source and travels
freely. One whose signature changes or disappears at a substitution lives in the seam between the two
trees: escalate it as a description plus their explicit written agreement about what may be quoted,
never by attaching their files because that was faster. If they decline to attempt a substitution, or
the time box runs out first, say which of the three were actually attempted — a reproducer called
portable after one substitution is a claim nobody checked.

The second is the clock. Ask the **Escalation route** owner for a dated answer, not a fix, and put
whatever they promise into the plan as a `workaround` row with them as the actor. An escalation with
no date does not fit inside a time box and must not be planned as though it did.

### 8. Write the gap list and the handover

No **Read**, **Grep** or **Glob** call belongs in this step; everything below is already on paper.
One block per requirement row:

```
fact      : <the requirement, named as our requirements file names it>
required  : <the value our release requires, quoted, with file and line>
found     : <the value their tree shows, quoted, with file and line, or ?>
found via : <where the found value came from — script | log | person | none>
readiness : <met | gap | unknown>
impact    : <blocking | workaround | cosmetic>
actor     : <us | customer-dv | customer-it | release-owner | commercial>
```

`found via` is named that way on purpose and must never be spelled `evidence`, and for the same reason
the fifth rung of step 5 is `artifact`. `_shared/handoff-vocabulary.md` locks `evidence` to a fixed
shape — a file path and line supporting the claims above it, with no token list at all — so a
four-token statement of *how* a value was obtained cannot wear that name without breaking every other
skill's column. The path and line themselves live in `found`, which is where the locked shape wants
them.

Then one engagement record. Exactly one field in it joins against a sibling: `signature` is the four
ordered parts of `_shared/failure-signature-schema.md`, so a defect raised here sorts beside one
raised by `dv-sim-log-first-error` or `dv-minimal-reproducer`. `notes` is last, as it is everywhere.
Every other field below is local to this skill and does not join anything, including two that used to
claim they did:

- there is deliberately no `run id` field here. The registered shape means whatever identifies one run
  *for us*, per the profile's **Run identity** fact, and nothing in this procedure is our run — every
  log came from a build in the customer's environment, identified by their scheme. `customer run` is
  therefore a separate column and must not be poured into the pack's one.
- `rows covered` is not `coverage`. It is a census of requirement rows and the rung reached;
  `dv-minimal-reproducer`'s `coverage` field counts axes tried and repeats behind each accept, and
  `dv-sim-log-first-error` states its coverage as a free-text line beneath its block rather than as a
  field. Three different objects, so three names, and only this one counts rows.

```
engagement   : <account reference in whatever form the Data-handling rule permits, release, version, dates>
time box     : <days agreed, days spent, days left, and the reserved handover block>
stage        : <the highest stage an actual log shows — tools | standalone | integrated | connected | artifact>
exit         : <met | partly-met | not-met | not-agreed>
gaps         : <n blocking, n workaround, n cosmetic, of m requirement rows>
forks        : <every edit outside the integration surface — path, line, reason — or none>
left behind  : <what of ours is now in their tree, and under which agreement it stays there, from step 6>
customer run : <what identifies the build each stage log came from, in their scheme — not ours>
signature    : <phase|kind|where|what for any defect raised, per the shared schema, or none>
rows covered : <rows settled from files, rows resting on a person, rows never reached; substitutions attempted>
notes        : <what the next engineer on this account must not rediscover>
```

Copy the environment facts into the **Account record** destination before the engagement closes. That
record outlives the demo: the next engineer arrives knowing their simulator version, their filelist
convention and which gap is still open, and spends their first day on the work instead of on the
inventory.

## Gotchas

- **The blocker is almost never technical, it is who has to act.** Licences, pinned tool versions,
  shared-farm upgrades and contract amendments all need someone outside the room, and their lead time
  does not compress when you work harder. That is why step 4 ranks on the actor and why the gap list
  is built before anyone travels rather than on the first morning.
- **"We use UVM" is not a version.** Two teams both on UVM can be on 1.2 and on an IEEE 1800.2
  release, and what bites is never the headline difference — it is a deprecated call our release
  still makes, or one theirs does. Read the version out of the library on their disk.
- **A clean standalone compile has proven almost nothing.** The failures that cost days are at the
  seam: their filelist ordering, their macros not reaching our package, their include-path order
  picking a different copy of our header. Reach the `integrated` stage early, and treat the day it
  passes as the halfway mark rather than the finish.
- **A stage completing is not the stage passing, and a missing marker is not a failure.** Our
  compile-completion stamp sits happily in a log whose elaboration then died, so a stage is only as
  high as the *last* marker the one **Grep** returned. A log carrying neither of that stage's markers
  usually never reached our code at all — their build broke first, or the farm killed the job and it
  printed nothing. That is why the **Grep** alternates both strings: searching only for the failure
  string reads a truncated log as a clean one.
- **The demo that only works with you in the room is a failed engagement.** Before the last day, ask
  their engineer to rerun it from their own account, in their own shell, from your written steps,
  while you stay quiet. Whatever they trip over is the handover document you had not written yet.
- **A failure at a customer belongs to their build until proven otherwise.** Reaching first for "it
  must be your simulator version" is usually wrong and expensive socially. Attribute it properly, and
  name an environment cause only with a file and a line behind it.
- **Their source is theirs and ours is ours, in both directions.** Copying their design into a
  reproducer that leaves the site is a contract problem, not a convenience; leaving our unreleased
  source in their tree becomes their problem at their next audit. Step 7's harder shrink exists
  because of this, not despite it.
- **Time-box arithmetic is not linear.** Connecting to a real design surfaces the clocking, reset and
  protocol-configuration assumptions nobody wrote down, so the second half of the days is never the
  easy half. Plan backwards from the handover block, not forwards from day one.
- **A workaround nobody wrote down is a fork.** Six months later no one can tell the deliberate detour
  from the panic edit, and the release upgrade stalls on both equally.
- **The environment record is worth more than the demo.** Demos are cheap to repeat once the
  environment is known; the environment is expensive exactly once, and only if nobody wrote it down.

## Human verification — what a wrong answer looks like

Before the gap list leaves your hands, check:

- every `found` value carries a file and a line from their tree, or is `?` — and anything that came
  from a conversation is marked `found via: person` rather than dressed up as a file, because that
  token is the only thing marking the row provisional
- every `required` value is quoted from the requirements file, never from what the release is
  believed to support
- no row reads `readiness: met` on the strength of a script alone where a real build could have
  confirmed it
- the ranking is by actor, and every `customer-it` or `commercial` row was raised on the first day it
  was known rather than held until it blocked something
- the stage recorded is the one an actual log at a path you searched shows, not the one the plan hoped
  for — and a **Stage markers** hit at a path is what "shows" means
- every `impact: cosmetic` row names neither a stopped stage nor a detour, and every `blocking` row
  names the stage it stops; a row that has a workaround written for it is not `cosmetic`
- `forks` is filled in, including the edits that felt too small to mention, and is reported as
  `n of m files checked`, and `left behind` lists our material at their site with an agreement against
  each entry
- `rows covered` names the rows nobody reached and how many of step 7's three substitutions were
  actually attempted, and the **Exit criteria** in the record are the list that was signed, with every
  later addition carrying a date and a name

A wrong answer is a confident deployment report with every row `readiness: met`, produced from their
build scripts without a single real build, that lands on a licence gap on the fourth morning. Its
close relative is a successful demo with no handover, where the only working invocation lives in the
visiting engineer's shell history and the account record still reads `exit: not-agreed`.

## Done when

Their own engineer reruns the exit-criteria evidence from your handover, without you, and every
remaining gap has a named actor and a date rather than a hope.
