---
name: dv-artifact-redaction-egress
description: Check a log, script, report, RTL fragment or customer package for what must come out of it before it leaves your hands, then produce a redaction map and a release-or-hold decision. Use when you are about to attach a log to a customer case, paste a run script into a ticket or into a chat session, hand a reproducer to a partner, quote one customer's material in another customer's thread, or file an internal defect that carries customer content.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: Pre-Share Redaction and Egress Check for Design and Customer Artifacts
  semiskill-function: design-verification
  semiskill-role: applications-engineer
  semiskill-level: fresher
  semiskill-owner: dv-guild
  semiskill-version: 1.1.0
  semiskill-review-by: 2027-05-12
  semiskill-tags: redaction, egress, disclosure, customer-artifacts, sharing, provenance
---

# Pre-Share Redaction and Egress Check for Design and Customer Artifacts

Every artifact an applications engineer touches was produced inside one boundary and is about to be
read inside another. One account's log quoted in another account's case, a run script carrying our
farm and licence layout attached to a public forum reply, an internal defect carrying a customer's
RTL fragment — ordinary Tuesday afternoons, none of them malice, not one retractable. The output here
is **a redaction map, an egress record, and one of three verdicts** — release, redact then release, or
hold. It is not a cleaned file: the agent never modifies the artifact, and step 6 says why.

## When to use something else

This is the last step before a boundary, not a debugging procedure. Triage with the right sibling
first, then come here before its output leaves the building. `dv-sim-log-first-error` emits a repro
block whose `log` and `run id` fields are a path and a machine identity; `dv-regression-triage-routing`
a table of internal owner names; `dv-build-filelist-hygiene` lines that are almost entirely paths;
`dv-repo-orientation` a map made of little else. `dv-minimal-reproducer` belongs *before* this rather
than after — a smaller reproducer is also the cheapest redaction, because it contains less.

If the material has **already** crossed a boundary it should not have, this is the wrong thing to
open. Go to the Incident route slot now, file untouched — reconstruction is somebody else's job.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Boundary list | [[FILL: the boundaries our artifacts cross — inside the team, company-internal, a named account, a partner, public — and which of them one person may cross alone]] | your manager |
| Identity patterns | [[FILL: the shapes our machine *and* human identities take — host names, user names, queue names, licence server entries, corporate mail addresses, and the form a person's name takes in a signature block — each written so it can be searched for]] | DV infra owner |
| Sensitive-string shapes | [[FILL: what a licence checkout line, an environment-variable dump line and a long high-entropy string look like in our artifacts, written as patterns that can be searched for]] | DV infra owner |
| Path roots | [[FILL: the top-level directory roots that appear inside our logs and scripts, and which of them are safe to show outside]] | DV infra owner |
| Customer markers | [[FILL: how an account's material is marked in our tree — the directory level, the file prefix, or the tag that says whose artifact this is]] | applications lead |
| Restricted vocabulary | [[FILL: the project codenames, unreleased part names and internal feature-flag strings that must never leave, and where that list is maintained]] | program owner |
| Regulated classes | [[FILL: which kinds of artifact are export-controlled or otherwise regulated here, and who decides]] | legal or compliance owner |
| Placeholder convention | [[FILL: the placeholder spellings we already use in customer-facing material, where the mapping from placeholder back to the real value is filed, and who may read that mapping]] | applications lead |
| Egress authoriser | [[FILL: who authorises a crossing this procedure marks hold, and the route that reaches them]] | your manager |
| Incident route | [[FILL: who is told when material has already crossed a boundary it should not have, and within what time]] | your manager |

**Identity patterns** deliberately spans machines and people: sweep classes 1 and 6 ask the same
question of two kinds of name. The DV infra owner has the host, user, queue and licence-server half;
the applications lead usually has the mail-address and signature half. Ask both — a half-filled row
leaves class 6 unchecked while looking answered.

One pack-wide fact is spent here and **not** re-asked: `_shared/team-profile.md`'s **Log location**,
used in step 1 to turn *a log* into a path, and only a log — nothing in the shared profile locates a
script, a report, an RTL fragment or a package. Two profile facts sit close to rows above and are
different facts: **Path roots** is the set of roots appearing *inside* logs, a larger set including
tool, release and home areas; **Sign-off** is verification sign-off, not the **Egress authoriser**.

**If a slot is unfilled, stop and ask — do not guess a convention.** An invented host pattern or path
root produces a sweep that finds nothing and a report that says "clean": the worst output here.

## Retrieval budget — read this before opening anything

A customer package can be hundreds of files, one of which may be larger than everything else you read
this month. The sweep is search-shaped, not reading-shaped.

1. **Grep, Read and Glob work on files on disk.** They cannot search text pasted into a chat — and
   pasting the artifact in order to have it checked *is itself the crossing this procedure exists to
   prevent*. Step 1 handles that case; it is not a detail.
2. **At most 2 Globs**: one to list a package, a second only if it nests one directory deep. Record
   paths only; do not open a file during the listing.
3. **At most 10 Greps**: one for provenance in step 2, eight class sweeps in step 4, and one spare to
   re-narrow a single class that came back too broad. There is no second spare.
4. **At most 4 windowed Reads of about 60 lines**, in step 5, each entered at a line number a Grep
   already returned. Never open the artifact with Read first.
5. If a class Grep returns more than about 200 hits the pattern is too broad — spend the spare and
   narrow it once. If it is still that broad the class is *pervasive*: step 7 turns it into
   `egress: hold` with a request for a clean artifact rather than a scrubbed one.
6. **Stopping rule.** Stop when all ten classes have a verdict or the budget is spent. A class the
   budget never reached is not clean — it is unchecked, by name, on the coverage line, alongside how
   many files were swept and which slots were unfilled. An unstated shortcut is worse than a stated one.

## Procedure

### 1. Get the artifact onto disk, and notice if the crossing already happened

If the artifact arrived as text pasted into the session, it has already crossed into the session. Say
so plainly, mark every finding provisional, and check the **Boundary list**: if a chat session is a
boundary for us, this is an **Incident route** matter, not a redaction job. Then ask for the path on
disk — for a simulation or regression log the profile's **Log location** narrows where to look; for a
script, report, RTL fragment or package say plainly that no shared fact locates those, and ask for it.

If the artifact is a package rather than a file, use **Glob** to list it and write the paths down only.
That listing is evidence in its own right: file and directory names are content, and step 4 sweeps them
alongside the bodies. Record what kind of artifact it is — the kind decides which classes can be dropped.

### 2. Establish provenance — whose material is this

Use **one Grep** for the **Customer markers** patterns across the artifact, and read the path
components of its own location by eye, which costs no tool call. An artifact from our own regression
and one from an account's testcase carry different content under different rules, and one that turns
out to contain both is the case this procedure exists for.

If provenance cannot be established from the file and its path, stop. Do not infer it from whoever
handed you the file — the person who forwards an artifact is very often not the boundary it came from.

### 3. Name the boundary, and check the crossing is allowed at all

No tool calls. From the **Boundary list**, name the boundary this send actually crosses, and set
`crossing`: `inbound` if their material comes to us, `outbound` if ours goes to them, `lateral`
between two accounts or two partners. A reply inside somebody else's thread is frequently two of
those at once, and that is the case people get wrong.

Then check **Regulated classes**. If the artifact kind is on that list, no amount of redaction makes
it releasable by you — it is `egress: hold` and a named authoriser. Sweep anyway: it tells the
authoriser what they are deciding about.

### 4. Sweep the ten classes with eight Greps

Two classes are settled by judgement rather than by a pattern, so this step spends eight **Grep**
calls and no more. Take each pattern from the slot in column three; where that slot is unfilled the
class is **unchecked**, not clean.

| # | Class | Pattern from | What it looks like | If hit |
|---|---|---|---|---|
| 1 | Machine identity | Identity patterns | host, user, queue and licence server entries | replace with a stable placeholder |
| 2 | Location | Path roots | absolute paths, mount points, home and release areas | keep the useful tail, replace the root |
| 3 | Attribution | Customer markers | account names in bodies, file names and directory names | replace, then re-check the file name itself |
| 4 | Roadmap | Restricted vocabulary | codenames, unreleased part names, feature-flag strings | replace, or hold if the sentence stops making sense |
| 5 | Credential-shaped | Sensitive-string shapes | licence checkout lines, environment dumps, long high-entropy runs | hold, and rotation by its owner — see the Gotchas |
| 6 | Personal | Identity patterns | engineer names, mail addresses, signature blocks pulled in from a thread | replace with a role, never with initials |
| 7 | Design content | judgement, no Grep | hierarchy paths, register field names, parameter values, netlist lines | ask the recipient what they need before scrubbing |
| 8 | Tool internals | Restricted vocabulary | our own build's file paths and flag names, printed only at raised verbosity | replace; see the Gotchas on verbosity |
| 9 | Regulated | Regulated classes | whatever step 3 named | hold; not yours to release |
| 10 | Second party | Customer markers | any second account's material in the same file | split the artifact; never redact your way out of this one |

Classes 1, 2, 3, 4, 5, 6, 8 and 10 are the eight Greps: class 6 spends the people half of **Identity
patterns** and class 8 the tool half of **Restricted vocabulary** — shared slots, separate patterns,
separate hit counts. Class 7 is judgement, class 9 was settled in step 3. Record per class the hit
count and the line numbers, and **do not copy the matched values into your notes** — step 8 says why.

### 5. Resolve the hits the sweep could not classify

Some hits are ambiguous: a path that might be ours or theirs, a word that might be a codename or
ordinary English. Spend up to four windowed **Read** calls of about 60 lines, each entered at a line
number Grep already gave you. Anything still undecided after those four windows is **residual** — the
honest output of a bounded procedure, not a failure of one. It goes into the record by line number,
and it blocks release until a person rules on it.

### 6. Build the redaction map — and hand it to a person

The map is the deliverable:

```
placeholder      class              occurrences   first line
<host-1>         machine identity   14            40
<work-root>      location           212           17
<account-x>      attribution        3             1
```

Take the placeholder spellings from **Placeholder convention** so the recipient sees shapes they have
seen before, and use **one placeholder per real value, everywhere in the artifact**. File the
placeholder-to-value mapping where that same slot says it belongs, and nowhere else.

The agent does not apply the map, deliberately: a large artifact cannot be edited reliably, a silent
edit destroys the only copy of the evidence, and the person whose name is on the send should have seen
every line that changed. **Ask the engineer to apply the map to a copy, keep the original untouched,
and give you the copy's path** — a redaction nobody re-swept is a redaction nobody verified.

### 7. Decide release, redact then release, or hold

- `egress: release` — every class checked, no hits, no residual, provenance established, and the
  boundary is one you may cross alone. Rarer than it feels.
- `egress: redact-then-release` — the map exists, it has been applied to a copy, and the re-sweep of
  that copy is clean.
- `egress: hold` — anything regulated, anything credential-shaped, any second-party content, any
  residual, any pervasive class from budget rule 5, or any class left unchecked because its slot is
  unfilled. Name the **Egress authoriser** and say exactly what you need from them.

Uncertainty resolves to hold. Holding costs an hour of somebody's afternoon; the other error cannot
be undone and has to be reported.

### 8. Write the egress record

```
artifact        : <what is being released, its path on disk, and its kind>
provenance      : <whose material this is, and how that was established>
crossing        : inbound | outbound | lateral
boundary crossed: <which boundary this send crosses, named from the Boundary list slot>
egress          : release | redact-then-release | hold
findings        : <one line per class: class number, hit count, first line number>
redactions      : <the map from step 6, by placeholder and class>
residual        : <every undecided hit, by line number>
unswept         : <files and formats no search could reach, named>
coverage        : <n of m files swept; which of the ten classes were checked; which were skipped and why>
record          : <where the placeholder mapping was filed>
authoriser      : <who approved a hold, or empty>
notes           : <anything the recipient would otherwise have to ask you for>
```

The field is `boundary crossed`, not `boundary`: three siblings already use the bare word for an
electrical or connectivity edge. **The record must not contain the values it is about** — line numbers
and class names, never the host name, path root or account. A record quoting what it found is a second
copy of the problem, and the copy gets pasted into a ticket. Leave a field empty, never plausible.

## Gotchas

- **The header holds the identity, the tail holds the failure.** The banner at the top of a log
  carries user, host, work area, tool build path and licence checkout; the interesting lines are at the
  bottom. Pasting "the whole thing to be helpful" ships the banner. Cut from the top on purpose.
- **A masked credential is still a compromised one.** A placeholder hides the value from the recipient,
  not from anyone already holding a copy of the file. Class 5 hits go back to whoever owns that value,
  for rotation, and the artifact stays `egress: hold` until they confirm.
- **File names and archive indexes are content.** People scrub a log body and attach it under a name
  carrying the account and the part number; an archive stores every member's full path in its index;
  the ticket shows the directory you dragged it from. Sweep the step 1 listing, not only the bodies.
- **Inconsistent placeholders destroy the artifact.** If one machine is `<host-1>` on line 40 and
  `<machine>` on line 900, the recipient cannot tell whether those are the same machine, and a
  distributed-run failure stops being diagnosable. One value, one placeholder, every occurrence.
- **A hierarchy path is often the only useful part of a failure — and it is design content.** Scrubbing
  it whole turns a reproducible report into a shrug. The last two levels are usually what the recipient
  needs and the top what names the product, so trim from the top; `_shared/failure-signature-schema.md`
  normalises instance paths the same way for the same reason.
- **Verbosity is a disclosure setting.** Raised debug levels print our own build's internal file paths
  and flag names no released version exposes. When you ask for a rerun to capture evidence, ask for
  default verbosity unless the extra output is needed — it is a smaller redaction job.
- **A search only finds what you named.** Eight clean sweeps mean eight named classes were absent, not
  that the artifact is clean. That is why an unfilled slot yields `unchecked` rather than a clean
  verdict, and why the coverage line is not optional.
- **Binary and derived artifacts cannot be swept.** A waveform database, a coverage database, a
  compiled library, a spreadsheet or a rendered document returns nothing or noise, and "no hits" there
  is evidence of nothing. They belong under `unswept`, with a person who has the tool to open them.
- **Two accounts must never share one artifact, even internally.** The internal defect you attached
  both logs to is the file somebody re-attaches to a case eighteen months from now, having missed this
  conversation entirely. Split them at creation; there is no later.
- **Replying inside somebody else's thread moves material both ways at once** — their text into our
  tracker, our analysis into their inbox, in one action. That is why `crossing` is a field and why a
  reply is frequently `crossing: inbound` and `crossing: outbound` together.

## Human verification — what a wrong answer looks like

Before the send, check:

- provenance is stated, and was established from the file and its path rather than from who forwarded it
- every placeholder in the copy appears in the map, and the mapping was filed where **Placeholder
  convention** says — a map that lives only in the chat is a map that is already gone
- the record itself quotes no host name, no path root, no account name and no codename
- the file name, the directory it is sent from, and the message body around it were swept, not only the
  artifact
- the coverage line names every class that was not checked, and none of those sits behind an
  `egress: release`
- class 5 hits went for rotation, not merely under a placeholder
- `crossing` matches what the message actually does, including when it is two of the three

A wrong answer typically reports the artifact clean after eight searches for patterns nobody ever
defined, or produces a beautifully redacted body attached under a file name carrying the account it came
from. Its third signature is a record that helpfully quotes every value it removed.

## Done when

The record is written, every class has a verdict or is named unchecked, and the verdict is carried
through: on `release` nothing further is owed; on `redact-then-release` the copy has been re-swept clean
and the map filed where **Placeholder convention** says; on `hold` the named **Egress authoriser** has
the record and knows what you are asking for. In all three, the one line you would have to defend
afterwards — what crossed, whose it was, and who said yes — is written down.
