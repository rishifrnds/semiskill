---
name: dv-vip-release-compat
description: Classify every change in a VIP release candidate against the previous release, decide what it does to the installed base of customer configurations, and write the migration note. Use when you are about to cut a VIP release, when someone asks whether a change is a minor or a major, when you have renamed or removed a class, method, macro or config key that customers may already be using, when a default or a constraint moved, or when you need to say whether a customer's pinned seeds still reproduce.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk (Cursor 2.4+, Claude Code). Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: VIP Release Compatibility and API-Stability Review
  semiskill-function: design-verification
  semiskill-role: vip-engineer
  semiskill-level: senior-staff
  semiskill-owner: dv-guild
  semiskill-version: 1.0.0
  semiskill-review-by: 2027-04-14
  semiskill-tags: vip, release, api-stability, compatibility, deprecation, migration, installed-base
---

# VIP Release Compatibility and API-Stability Review

A VIP release is not judged by whether it builds here. It is judged by what it does to the
testbenches that already integrate the previous release, and the changes that hurt those are rarely
the ones that fail to compile. A renamed virtual method, an inserted enum value, a tightened
constraint and a moved default all pass our own regression cleanly, and all of them reach a customer
as silence — a knob with no effect, an override nobody calls, a seed that stopped reproducing.

The output is **a break class, the single worst change behind it, the release level our own tiers
allow for that class, and a migration note** — plus one line stating how much of the change set that
rests on. Not a summary of the diff.

## When to use something else

- The sign-off gate itself — exit criteria, waivers, the recorded go or no-go — is `dv-release-gate`.
  This skill produces **one** artifact that gate consumes and never substitutes for it.
- The candidate does not build in our own tree: `dv-build-filelist-hygiene` decodes compile and
  elaboration failures. A review of a tree that does not compile is a review of a guess.
- A customer has already taken a release and something fails. One log is `dv-sim-log-first-error`,
  shrinking it is `dv-minimal-reproducer`, and turning it into a record R&D can act on is
  `dv-customer-defect-handoff`. Those start from a failure; this runs before one exists.
- Proving a VIP is genuinely switched on in someone's environment after an upgrade is
  `dv-vip-integration`. If the change under review *is* the shipped coverage model, draft it with
  `dv-vip-coverage-model` and bring the delta back here.

## Fill this in for our team

| Slot | What to fill in | Who knows |
|---|---|---|
| Release identity | [[FILL: how our VIP releases are identified, and where the previous release tree is unpacked so it can be read from disk]] | VIP release manager |
| Change manifest | [[FILL: how we obtain the list of files changed between two releases, and where that list is saved so it can be read]] | VIP release manager |
| Public API boundary | [[FILL: which directories and which classes we treat as the customer-visible surface, and how that boundary is marked in the source]] | VIP architect |
| Compatibility tiers | [[FILL: what each of our release levels promises a customer, and which kinds of change each level permits]] | VIP release manager |
| Config key surface | [[FILL: where our configuration keys, knob names and factory type names are declared, and whether customers set them by string]] | VIP architect |
| Deprecation policy | [[FILL: our source-visible deprecation marker, and how many releases a deprecated symbol survives before it may be removed]] | VIP architect |
| Installed base | [[FILL: which customer-shaped configurations, integration examples or compliance tests we keep on disk, and where they live]] | applications engineer |
| Random stability | [[FILL: whether we promise seed-for-seed stimulus reproduction across a release, and at which release levels]] | verification lead |
| Release note destination | [[FILL: where our release notes live, and which fields the migration section must carry]] | VIP release manager |

Two pack-wide facts are read from `_shared/team-profile.md` rather than re-asked here. The
**Filelist convention** row decides whether a moved file is a customer build break at all: it is one
only if customers can list our files individually instead of including the filelist we ship, and
that row is what says which. The **Sign-off** row names who releases and on what evidence — step 8
hands them the block rather than deciding for them. Nothing else in the profile applies; this
procedure never opens a simulation log, so its marker rows are deliberately not repeated above.

**If a slot is unfilled, stop and ask. Do not guess a convention.** An invented release level or
deprecation window is worse than no answer, because it is the answer a customer plans an upgrade
around.

## Retrieval budget — read this before opening anything

Two full VIP trees plus a change manifest is more text than any budget absorbs, and a release diff
after a busy quarter runs to thousands of lines.

1. **Grep, Read and Glob work on files on disk.** A diff pasted into the conversation cannot be
   searched. Get the path it came from, or ask for it to be saved to a file and be given that path.
   Until a path exists you may read the pasted hunks by eye — say that is what you did, and mark
   every finding provisional: you compared two fragments, not two trees.
2. **Never Read the manifest or a source file whole.** Under about 300 lines, one **Read**. Above
   that, **Grep** it once per public-API path prefix from the **Public API boundary** slot, at most
   four.
3. **Per symbol the allowance is two Greps and one windowed Read** — one **Grep** in the candidate
   tree, one in the previous release tree, one **Read** of about 40 lines wherever a declaration has
   to be seen in full. Cap the symbols at **ten**. Every "what settles it" cell in step 3 is spent
   out of this allowance, never on top of it.
4. Four named allowances sit outside the per-symbol one and nothing else does: **four Greps** in
   step 4, **four** in step 5, **two** in step 6, and **five** in step 7 — one per symbol carried
   into the kept configurations.
5. Scope every **Glob** and **Grep** to one directory of one tree. Rooted at a VIP tree a search
   returns tens of thousands of paths; rooted at both it returns them twice. Above about 200 hits
   the pattern is too broad — anchor it before reading anything.
6. The whole ledger: two Globs and one Read (or four Greps) on the manifest, twenty Greps and ten
   Reads on symbols, fifteen Greps across steps 4 to 7 — about **forty Greps, twelve Reads and a
   handful of Globs**, already a full session's attention.
7. **Stopping rule.** Stop when the ten symbols are classified or the ledger is spent, whichever
   comes first, and name the changed public-API files you did not open rather than opening an
   eleventh.
8. **State the coverage.** Every count carries a denominator — how many changed public files were
   opened out of how many the manifest lists. An unstated shortcut is far worse than a stated one.

## Procedure

### 1. Get the change manifest and the previous release onto disk

Every question below is a comparison, so both sides must be readable before anything is classified.

Use **Glob** on the path the **Release identity** slot gives for the previous release tree and
confirm it is really there. If it is not — the release is an archive nobody unpacked, or exists only
in version control — ask the engineer to unpack the previous release somewhere readable and to give
you that path. Version history is not reachable from here: blame, log and tag comparison all need a
shell, so "what did this look like last release" is either a file on disk or a handoff to a person.

Then the manifest. Ask the engineer to produce the list of files changed between the previous release
and the candidate, save it to a file, and give you the path; the **Change manifest** slot records how
our flow produces it. A pasted diff is not searchable — budget rule 1.

If neither comparison can be arranged, say plainly what a one-tree review can claim. It can describe
what exists in the candidate. It can never say what moved, and what moved is the entire question.

### 2. Split the changed files into public API and internal implementation

**Read** the manifest, or **Grep** it per path prefix under budget rule 2, and partition every
changed path three ways using the **Public API boundary** slot: public API, internal implementation,
and packaging — filelists, scripts, examples, release metadata. Record the three counts. They are the
denominators the coverage line needs, and the only honest way to say later how much was reviewed.

Internal-only changes are **not** automatically safe: a behaviour change in an internal class reaches
the customer through the public one that calls it. What the split buys is ordering, not exemption.
Review public files first, and open an internal file only when a public symbol's behaviour is
defined there.

If the boundary slot is unfilled, stop. Guessing which directories are customer-visible produces a
careful review of the wrong half of the tree, which reads exactly like a careful review of the right
half.

### 3. Classify each public-API change against the break table

Choose at most ten symbols by blast radius rather than by manifest order: base classes customers
extend, then whatever the **Config key surface** names, then the rest. The right-hand column is what
settles the row from files — a **Grep** in each tree, plus a windowed **Read** where two declarations
must be compared line by line.

| What changed | Break class | How it reaches the customer | What settles it here |
|---|---|---|---|
| a public class, member or macro removed | source | their build stops, naming the symbol | present in the previous tree, absent in the candidate |
| a virtual method renamed, old name gone | behaviour | their override compiles and is never called again | old name in the previous tree, new name in the candidate |
| a method's or the constructor's arguments, types or return changed | source | their override, or every extension's call to the parent constructor, stops matching | read both declarations, compare argument by argument |
| a class made non-virtual, or a member made local or protected | source | only customers who extended or reached it are hit | the class header in both trees |
| a parameter added to a parameterised class or interface | source | old instantiations still elaborate; the registered type name moves | how that class registers itself with the factory |
| an enum value inserted rather than appended | behaviour | stored numeric values and value-keyed bins shift | the enum body in both trees |
| a default value or default constraint changed | behaviour | every customer who never set that knob gets different traffic | both declarations, and whether the knob is in the config surface |
| a constraint added or tightened | behaviour | their own constraint on the same field can become unsatisfiable | the constraint block in both trees |
| a random field added, removed or reordered | seed | their pinned seeds stop reproducing their bugs | the random declarations in both trees |
| a covergroup, coverpoint or bin renamed | coverage | their merged history for that item is orphaned | the covergroup in both trees |
| a shipped file moved or dropped, or a package renamed | source | their filelist points at a path that is gone, or an import stops resolving | both paths, against the profile's Filelist convention |
| a configuration key string changed | behaviour | the setting stops arriving and the old default stands | the key literal in both trees |

Record each classified symbol with its file and line **in both trees**. A symbol quoted from one tree
only is not evidence of a change; it is evidence that the symbol exists.

### 4. The changes that compile and still break the installed base

None of these appears in a build log. Four **Greps**, one per question, across the changed public
classes and their counterparts — and for each, record the previous value and the candidate value
verbatim with both line numbers. "The default changed" without the two values is not yet a finding.

- **Random field set and order.** A field added, removed or moved changes what a given seed produces.
  The language standard promises stability for an *unchanged* program; nothing in it preserves a
  solution across a changed variable or constraint set, and no solver does. If **Random stability**
  promises seed-for-seed reproduction at this release level, this finding contradicts the promise and
  outranks everything else in the review.
- **Constraints.** A tightened constraint can make a customer's own constraint on the same field
  unsatisfiable, which arrives as a randomisation failure in their test, in their code, on their line.
- **Defaults.** A moved default changes behaviour for exactly the customers who never configured that
  knob, which is most of them.
- **Enum bodies.** Appending is cheap; inserting renumbers every value after the insertion point, and
  anything holding a stored numeric value moves with it.

### 5. The string-keyed couplings nothing checks

Four more **Greps**. No compiler verifies these and our own regression never exercises them, because
we do not override our own components by string.

- **Configuration keys.** A renamed key means the customer's setting is written where nothing reads
  it and the VIP quietly keeps its default. Neither side prints a diagnostic.
- **Factory type names.** A customer overriding by string is matching a name we changed. How that
  name is spelled for a parameterised class depends on the registration idiom used, so read what the
  class actually registers rather than assuming it follows the class name.
- **Macros.** A renamed macro or a changed argument list breaks the customer's tests rather than
  their integration, so it surfaces late and looks like their bug.
- **File paths.** **Grep** the shipped filelist in both trees for each moved file. Whether this
  matters at all is the profile's **Filelist convention** — if customers include the filelist we
  ship, a move is invisible to them; if they list our files individually, it is a silent build break.
  That row is the answer, not the tree.

### 6. Deprecation — what may be removed now, and what may only be marked

Two **Greps**, one per tree, for the marker recorded in the **Deprecation policy** slot.

A removal is legitimate only if the symbol already carried that marker in the previous release, and
only after the number of releases the policy names. Anything removed in the candidate that was not
marked in the previous release is a removal with no deprecation window, whatever the release note
calls it — list those by name, because that list is the argument for holding the release or for
restoring the symbol as a thin forwarder.

List the reverse case too: symbols marked for the first time in the candidate. They cost the customer
nothing today, and a candidate that removes more symbols than it marks is running the policy
backwards.

### 7. Check the verdict against the configurations we actually keep on disk

Take the five most damaging symbols from steps 3 to 5 and **Grep** the **Installed base** paths for
each — one Grep per symbol.

- **A hit is proof.** A kept configuration naming a removed or renamed symbol is a break with a file
  and a line, and it stops being a judgement call.
- **A miss is weak.** Our examples are the configurations we thought of. They structurally cannot
  contain the shapes that break customers most often — an override of a method we never override
  ourselves, a factory override by a string we never use, a parameter combination we never build.
  Report a miss as "not used by the configurations we keep", never as "not used".

Two things here need a machine and neither is ours to do: ask the engineer to build one kept
configuration against the candidate and to give you the path of the resulting build log — if it
carries diagnostics, `dv-build-filelist-hygiene` decodes them — and ask for one kept example repeated
on both releases at the same pinned seed, with both log paths. That second comparison is the only
thing that actually answers the random-stability question; step 4 can only say whether to expect it
to fail.

### 8. Set the break class and the release level

The break class is the **worst** class observed across steps 3 to 7 — `breaks: source`, then
`breaks: behaviour`, then `breaks: seed`, then `breaks: coverage`, and `breaks: none` only when every
changed public file was opened. If the ledger stopped early, the honest answer is the class of what
was reviewed with the unreviewed count beside it.

The mapping from a break class to a release level is **our policy, not your judgement**: read it out
of the **Compatibility tiers** slot and apply it. If that slot is unfilled, report the break class and
stop rather than naming a level. Two classes are the ones tier tables usually forget — a seed break
and a coverage break, because neither is an API change and both are invisible to a compiler. If our
tiers are silent about them, that silence is a finding to raise with the release manager, not
permission to call them compatible.

Then hand the block to whoever the profile's **Sign-off** row names, with the evidence that row
requires. This procedure produces the argument for a release decision; `dv-release-gate` records the
decision, and neither of them is you deciding alone.

### 9. Write the migration note

Author this block and put it where the **Release note destination** slot says, in the fields that
destination requires. Leave a field empty rather than filling it from assumption.

```
release       : <VIP name, candidate release identity, previous release identity>
manifest      : <path to the change manifest, and how it was produced>
reviewed      : <public files opened of public files changed, with internal and packaging counts>
breaks        : source | behaviour | seed | coverage | none
worst         : <the single most damaging change, with its file and line in both trees>
release level : <the level our compatibility tiers permit for that class, or empty>
deprecated    : <symbols marked in this candidate, and the release each may be removed in>
removed       : <symbols removed without a full deprecation window in the previous release>
migration     : <the one action a customer must take, or the word none>
evidence      : <file and line in each tree for every claim above>
unreviewed    : <changed public-API files the ledger did not reach>
notes         : <anything the next reviewer would otherwise rediscover, including any answer that
                 came from a person rather than from a file>
```

`release`, `evidence` and `notes` are the field names `dv-release-gate`, `dv-ral-bringup` and
`dv-sim-log-first-error` already use, so a release review reads beside a gate record and a failure
report without translation. The rest are local to this skill: a release review has no failing run, so
it emits no signature, no phase and no run identity, and inventing those to look familiar would make
this block match nothing.

Under the block add one coverage line — "reviewed 9 of 23 changed public files, both trees on disk",
or "one tree only, provisional". That line is what tells the release manager whether `breaks: none`
means *no break* or *none found in the part we looked at*.

## Gotchas

- **Renaming a virtual method does not break the customer's build — it silently disconnects their
  override.** Change the *prototype* and the tool rejects their mismatched override loudly, which is
  the good case. Rename it and their method becomes an ordinary one nobody calls: compiles,
  elaborates, stops taking effect. It is invisible to every check either side runs.
- **A pure addition can break a build.** A member added to a base class collides with whatever the
  customer already added to their extension — a variable of the same name shadows, usually quietly,
  while a method of the same name becomes an override that must match a prototype it was never
  written against. "We only added things" is not a compatibility argument.
- **Inserting an enum value renumbers everything after it.** Saved coverage databases, stored integer
  casts, value-keyed bins and recorded transaction files all move with it. Append instead, and where
  the encoding is explicit, pin existing labels to the values they already have.
- **A changed default is the most expensive compatible change available.** It compiles, it runs, and
  it changes traffic for exactly the customers who never touched that knob. It surfaces two months
  later as a coverage hole, with the release-note bullet that mentioned it three bullets down.
- **A missed configuration lookup is silent on both sides.** A key the VIP no longer reads is written
  and ignored; a key the customer no longer sets leaves our default standing. Nothing prints, and the
  symptom they report is "the knob does nothing".
- **Adding a parameter keeps old instantiations legal and still breaks string-keyed overrides.** The
  specialisation the factory registers is not the class name and it moves with the parameter list.
  Check what the class registers before promising that overrides by name survive.
- **A deprecation that exists only in the release note is not a deprecation.** It has to be visible
  where the customer's own tool surfaces it, and it has to survive at least one release beside its
  replacement — otherwise "deprecated" and "removed" happened at once and the customer experienced a
  removal with extra paperwork.
- **"Our regression is green" says nothing about the installed base.** Our tests instantiate the VIP
  in the configurations we imagined. The breaks that reach customers are the ones our tests
  structurally cannot contain, which is why step 7 asks for one real customer-shaped build.
- **Coverage-model renames are a sign-off problem, not a code problem.** Their build is fine and
  their tests pass; what they lose is the merged history behind a closure argument they already made.
  That lands on their schedule, and they will not thank you for finding it during the upgrade.

## Human verification — what a wrong answer looks like

Before the block goes to the release manager, check:

- every claimed change cites a file **and a line in both trees**, or the review says explicitly that
  the previous release was never on disk and is provisional throughout
- nothing is called "removed" on the strength of one Grep in one tree
- the break class is the **worst** class observed, not the last one looked at
- `breaks: none` appears only when the reviewed count equals the changed-public count; otherwise the
  unreviewed count sits beside it
- the seed question was answered from the random and constraint declarations, or is marked
  unanswered — "no API change" is not an answer to it
- the release level came out of the **Compatibility tiers** slot, and is left empty if that slot is
  unfilled rather than reasoned out from what the change set looks like
- nothing appearing only in the release note is counted as a deprecation, and every "not used by
  customers" claim says which configurations were searched

A wrong answer is a clean bill of health produced from the candidate tree alone. Every question here
is a comparison, so a one-tree review can only report what exists and never what moved — and it reads
identically to a real review right up until the first customer upgrades.

## Done when

The release manager can approve or hold on the block alone, and every customer whose upgrade breaks
was told which change did it before they hit it.
