# The authoring contract

**Read this before writing, fixing or reviewing a skill in `skills/`.** It is the single source of
truth for what a SemiSkill DV skill must be. It used to live inline in three workflow scripts
(`tools/dv-wave.js`, `tools/dv-gate.js`, `tools/dv-gate2.js`); three copies of a contract is three
contracts, so they now point here instead.

Every rule below exists because a specific review round found a specific defect. Where the reason is
not obvious the defect is named, because a rule whose reason is forgotten is a rule that gets
"simplified" away.

---

## 1. What a skill is

A single Markdown procedure a DV engineer's agent loads and follows. The reader is a working
verification engineer at an EDA-and-IP company. **The agent executing it has only `Read`, `Grep` and
`Glob` over text files already on disk** — no shell, no network, no tool invocation.

The skill ships **generic on purpose**. Everything team-specific is a `[[FILL: ...]]` slot. A skill
that bakes in one team's conventions is not reusable, and a skill that *invents* them is worse than
no skill.

---

## 2. Standing rules

1. **Verb honesty.** The agent cannot run VCS, Verdi, URG, a formal engine, an emulator, or submit a
   farm job. Every step is an analysis or authoring verb (read, locate, classify, rank, draft,
   cross-check) **or** an explicit handoff: *"ask the engineer to run X and give you the path to the
   output."* Never write a bare Run/Execute/Merge/Compute as something the agent performs. This is
   the single most common way a skill like this becomes shelfware.
   *Corollary:* never report what a run **would** have shown. Name the handoff and stop.

2. **No proprietary lookup.** You do not know their tool flags, message strings, house conventions,
   VIP knob names, or licensed spec text — and must not pretend to. Every such fact is a
   `[[FILL: ...]]` slot. These are the lines that make a senior engineer close the file forever.

3. **A retrieval budget the procedure actually obeys.** DV artifacts are enormous — 100MB+ logs,
   filelists with thousands of entries. State an explicit bounded budget (Grep to locate, then
   bounded windowed Reads, with a stopping rule), then verify that **no step exceeds it** and that
   the budget **accounts for every Grep and Read the steps actually spend**.
   This is the most-found defect class in the whole project. Two real examples:
   - a step granted 2 Greps that needs 3, so its third branch is unreachable and the procedure
     silently degrades to a weaker rule — the reader never learns it degraded;
   - a budget itemising "one Glob" that no step ever spends.
   The budget is a **claim about the skill**, not a constraint imposed from outside: if the procedure
   genuinely needs more, change the budget and say you did.

4. **Markers must be slots.** If a step Greps for a "fatal marker" or "pass marker", the slot table
   must declare it. Never Grep for a string the engineer was never asked to define.

5. **Every slot must be spent** by some step (machine-checked: **C001**). A slot the procedure never
   consumes sends the reader to interrupt a colleague for nothing.

6. **Every value a handoff block offers must have a step that assigns it** (machine-checked:
   **C005**). A value the reader can never legitimately produce is either a missing branch or a
   value that should not exist — two engineers will fill it in differently.
   *Exception:* registered pack-wide fields (see §4) are governed by the registry, not by local
   reachability, and C005 does not fire on them.

7. **Logs are files on disk.** Grep and Read cannot search text pasted into a chat. If the
   description advertises the pasted-in case, step 1 must resolve it to a path first, or say plainly
   what cannot be done and mark the result provisional.

8. **State your own coverage.** If the procedure stops early under its budget, the output says how
   much it actually covered, and which slots were unfilled. An unstated shortcut is far worse than a
   stated one.

9. **Pack-wide facts are authored once in `skills/_shared/team-profile.md`** — log locations,
   fatal/pass/infra markers, run identity, known-issue list, area-to-owner map, sign-off, simulator,
   and filelist convention. Reference them; do not re-ask them. Capture vendors the exact three-file
   canonical shared snapshot into each skill-version payload, and an installed skill carries those
   approval-bound copies under its own `_shared/` directory. If your skill needs something
   **narrower** than the profile records, say exactly how it is narrower. Never claim two
   differently-named facts are "the same fact" unless they genuinely are.

10. **Signatures** come from `skills/_shared/failure-signature-schema.md`. Use its field names and
    rules as written rather than re-deriving them. Cite the file; do not restate it, or the two
    drift.

11. **Handoff fields follow `skills/_shared/handoff-vocabulary.md`** (ADR-011). Read it before
    naming any enum-valued field. See §4.

12. Every skill ends with **"Human verification — what a wrong answer looks like."**

13. **Route honestly.** `## When to use something else` must name the real neighbours — including
    the ones whose territory you overlap. A skill that routes only to distant siblings while
    silently duplicating its nearest one is a maintenance trap.

---

## 3. Mechanical constraints — any one silently prevents publication

The skill is scanned by the security pipeline and must score exactly **1.000**. These block it:

- ANY url (`http` followed by `://`). Cite documents by name and clause instead.
- The words `curl`, `wget`, `urllib`, `requests.get`, `socket.`, `fetch(`, or `nc -`.
- Any of `{eval, exec, function}` immediately followed by `(` — **case-insensitive**. So
  "transfer function (H(s))" is fatal; write "transfer function H(s)".
- "run the following command/script/shell/bash" — instant hard fail. Use the handoff phrasing.
- "you are now a/an/the ..." — instant hard fail. Write "as the block owner, you ...".
- "ignore ... previous/prior/above instructions", "disregard the above/previous/system".
- The letters `exfiltrat` in any word. Write "unauthorised data egress".
- "execute arbitrary code/commands".
- A dotted quad like `10.2.1.4` (reads as a private IP). Write "v10.2 patch 1.4".
- An `NNN-NN-NNNN` number (reads as a US SSN). Re-punctuate part and clause numbers.
- Four groups of four digits; a 200+ character unbroken alphanumeric run.
- `{token, secret, password, api_key, passwd, pwd}` followed by `:` or `=` then 16+ characters —
  **even as a fake placeholder**. Use angle brackets: `token: <your-token>`.
- `<<<` or `>>>` anywhere. A `[[FILL:]]` slot named after a credential.
- Unquoted YAML values containing `: ` or starting with `@ \` % * & ! | > [ {`.

> **`lint 1.000` is a SECURITY score. It says nothing about whether the DV content is correct.**
> This distinction cost two full review rounds to learn. A skill can be perfectly clean and still
> tell an engineer something false.

---

## 4. Handoff vocabulary (ADR-011)

A handoff field name is the **consumer's join key**: blocks from different skills get pasted into
one table and compared by exact token, so a name is a promise about the value space.

- **Same name must mean same values. Same values need not mean same name.**
- Before naming an enum-valued field, read `skills/_shared/handoff-vocabulary.md` and ask one
  question: *is the field I am about to write one of the registered ones?* If yes, copy the
  canonical values verbatim. If no, the name is yours — subject to the held-noun rule.
- **Held bare nouns** (`chain`, `verdict`, `status`, `type`, `result`, `kind`, `mode`, `reason` …)
  read as universal columns. Qualify them with the axis they classify: `req chain`, `match key`,
  `card result`, `input parity`.
- **Narrowing** a registered enum is legal where the registry says `declared`, and must be declared
  as a registry row. A subset is safe for *joins* but unsafe for *denominators*: "0 of 12
  finalise-phase failures" is meaningless if half the contributing skills structurally cannot emit
  `finalise`.
- **Never union two unrelated enums under one name to silence a collision.** That makes both wider
  than either skill can produce and still forces every consumer to know which skill a row came from.

Local-by-default is the healthy state: most field names appear in exactly one skill, and that is
correct.

---

## 5. Required frontmatter (ADR-008)

Exactly these keys at top level — `name` must be kebab-case and **identical to the directory name**,
or Cursor will not load the skill.

```
---
name: <the kebab folder name, identical to the directory>
description: <what it does>. Use when <concrete triggers in the engineer's own words>.
license: Proprietary - internal use only
compatibility: Any Agent Skills runtime with Read, Grep and Glob over files on disk. Read-only; no shell, no network.
allowed-tools: Read, Grep, Glob
metadata:
  semiskill-title: <human title>
  semiskill-function: design-verification
  semiskill-role: <from specs/skill_registry.json — must match the registry exactly>
  semiskill-level: <from specs/skill_registry.json>
  semiskill-owner: dv-guild
  semiskill-version: <bump on every substantive edit>
  semiskill-review-by: <a date 6-14 months out; STAGGER it, do not reuse a sibling's>
  semiskill-tags: <comma separated>
---
```

Add `Write` or `Edit` to `allowed-tools` **only** if producing a file is the named deliverable.

`role` and `level` must match `specs/skill_registry.json` exactly. A mismatch is **facet drift** and
is a failure — the scoreboard checks it. If a role is missing from the linter's vocabulary, fix
`semiskill/authoring/facets.py`; do **not** remap the skill to a role that happens to lint.

The `description` is the most important string in the file — it is the only text the agent sees when
deciding whether to invoke the skill. Name concrete triggers the way an engineer would actually
phrase the problem, and include "Use when".

---

## 6. Required body structure

1. `# <Title>` then two or three sentences framing what actually goes wrong.
2. `## When to use something else` — route to the sibling skills honestly.
3. `## Fill this in for our team` — 5–10 `[[FILL: ...]]` slots with a "Who knows" column, the
   pack-wide-facts pointer, and the do-not-guess rule.
4. `## Retrieval budget — read this before opening anything` — numbered, with a stopping rule.
5. `## Procedure` — numbered `###` steps naming the tool in bold at each step.
6. `## Gotchas` — 6–10 bullets of hard-won specifics. **The most valuable section**; it is what
   actually transfers experience between people. Concrete and technically correct.
7. `## Human verification — what a wrong answer looks like`
8. `## Done when` — one line.

Target 180–260 lines. Substantial, not padded. (Measured drift: the shipped pack averages ~350; if
you exceed the target, that is a judgement to state, not to hide.)

---

## 7. Verify before you finish — mandatory

From the repo root:

```
python -m semiskill.cli lint skills/<your-slug>     # must print [approve 1.000] and clean
python -m semiskill.cli lint skills/                # pack-level: must report NO error-level finding
```

Warns are the authoring backlog and do not block a release. **Errors block the whole wave.**

Edit only your own skill directory. Never modify the linter, the scanners, sibling skills or
`_shared/` — other agents own those and may be editing them concurrently.

---

## 8. The review calibration

A reviewer must sort every finding into exactly two buckets, and the publish verdict depends only on
the first:

- **BLOCKING** — it would make an engineer take a **wrong action**, or a step **cannot be carried
  out at all**: technically wrong about the DV domain; a step outside its own retrieval budget; a
  specific flag/string/default asserted as fact rather than declared as a slot; a slot no step
  spends or a handoff value no step assigns; a false claim about a sibling skill or shared file;
  metadata role/level not matching the registry.
- **NON-BLOCKING** — real, but it would not mislead anyone: narrower-than-ideal phrasing, a nit, a
  style point, a "could also mention", a `semiskill-review-by` collision.

An agent may classify findings, but it does not decide readiness. Deterministic code marks a version
`recheck-ready` if and only if all required checks pass, exact hashes/facets/lineage match, fixer and
reviewer identities are independent, and no blocking finding remains open or disputed.

Do not inflate a nit into a blocker to look rigorous, and do not demote a real defect to look
generous. A pack that never ships helps nobody; a pack that ships a wrong instruction is worse than
no pack.

Why this is written down: the first gate round did not make the distinction, reviewers listed date
collisions beside genuine blockers and then failed the skill, and **0 of 44 skills could pass by
construction**.

---

## 9. The gate

```text
author -> lint 1.000 -> security scan -> adversarial review -> fix -> INDEPENDENT recheck
       -> deterministic readiness -> authenticated human approval -> verified publication
```

- The recheck reviewer must **not** have seen the fixer's reasoning. Every earlier round that was
  rechecked by the lineage that produced the fix shipped a new bug.
- Nobody certifies their own fix. The collector records typed observations; deterministic code owns
  readiness.
- Initial reviews and rechecks are immutable `review` artifacts bound to the exact skill-version ID,
  shared-inclusive payload hash, prompt/run/batch/attempt, registry facets, and runtime identities.
  Legacy `REVIEW.json` files are migration provenance only; new ones are forbidden inside payloads.
- `semiskill wave` captures/scans and queues exact evidence, but always creates zero approvals and
  zero publications. `--allow-ungated` is retired.
- Publication requires an explicit authenticated human decision naming the exact version/hash,
  automated review, independent content review, decision, reason, and authentication context.
- A canonical shared-source change invalidates the affected hashes. It requires a semver bump, new
  scans, a fresh recheck, and a new approval; export never reads mutable source as a fallback.
- Expect **more than one fix round**. One fix pass followed by a strict recheck converged on zero.
