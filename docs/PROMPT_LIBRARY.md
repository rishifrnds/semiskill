# Prompt library

Verbatim prompts for every stage of the SemiSkill gate. Copy them as-is and substitute the
`{{PLACEHOLDERS}}`. They encode lessons that cost real review rounds; the notes under each say what
breaks if you shorten it.

`{{REPO}}` = `E:/code/VLSI/semiskill` · `{{SLUG}}` = e.g. `dv-ral-bringup` ·
`{{ROLE}}` / `{{LEVEL}}` = from `specs/skill_registry.json`, exactly.

**Every prompt begins with the same preamble.** Do not drop it — it is what makes the contract a
single source of truth instead of a copy that drifts.

---

## P0-PREAMBLE — prepend to every prompt below

```
Read {{REPO}}/docs/AUTHORING_CONTRACT.md in full before you do anything else. It is the single
source of truth for what a skill in this pack must be: the standing rules, the mechanical
lint-blockers, the handoff vocabulary (ADR-011), the frontmatter contract (ADR-008), the required
body structure, and the review calibration.

Also read, as the contract tells you to:
  {{REPO}}/skills/_shared/team-profile.md
  {{REPO}}/skills/_shared/failure-signature-schema.md
  {{REPO}}/skills/_shared/handoff-vocabulary.md
  {{REPO}}/skills/dv-sim-log-first-error/SKILL.md   (golden: voice, structure, density)
  {{REPO}}/skills/dv-ral-bringup/SKILL.md           (golden: a decision-tree skill)

The agent that will EXECUTE the skill you are working on has only Read, Grep and Glob over text
files already on disk. No shell, no network, no tool invocation.

lint 1.000 is a SECURITY score. It says nothing about whether the DV content is correct.
```

---

## P1-ADVERSARIAL-REVIEW

Model: strongest available. Reads only; edits nothing.

```
{{P0-PREAMBLE}}

# YOUR TASK — adversarially review one already-written skill

Read {{REPO}}/skills/{{SLUG}}/SKILL.md in full and attack it. Default to finding problems: a clean
review of an unreviewed draft is almost certainly a failed review. Nobody has looked at this yet.

 1. **Verb honesty** — quote every step where the AGENT is made to run a tool, merge a database,
    compute a metric, open a waveform, or submit a job. It has only Read, Grep and Glob.
 2. **Hallucination risk** — every specific tool flag, message string, file name, default or
    convention the author could not have known and that is not a [[FILL:]] slot. These are the lines
    that make a senior engineer close the file and never reopen it.
 3. **Technical errors** — anything wrong or misleading about the DV domain. Cite the line. This is
    the most valuable thing you can find.
 4. **Budget violations** — steps that cannot be carried out within the skill's own stated caps, and
    Greps or Reads the steps spend that the budget never accounts for. Count them; do not eyeball.
 5. **Unused slots** — declared and never consumed.
 6. **Dead handoff values** — a value the report block offers that no step tells the reader to
    assign. Two engineers will fill those in differently.
 7. **Would a busy DV engineer open it twice?** Answer honestly.

{{MACHINE_FINDINGS}}

Do NOT edit any file. Report only.

Return JSON: {"slug", "verb_honesty":[], "hallucination_risks":[], "technical_errors":[],
"budget_violations":[], "unused_slots":[], "must_fix":[], "open_twice":""}
```

`{{MACHINE_FINDINGS}}`: when `gate_args.py` reports findings for this slug, insert
*"The machine checker already found these — treat them as confirmed and include them in must_fix:"*
followed by the list. Otherwise leave empty. **Why:** without it the reviewer re-derives what a
40ms check already knows, and sometimes misses it.

---

## P2-FIX

Model: strong. Edits only its own skill directory.

```
{{P0-PREAMBLE}}

# YOUR TASK — close the review findings on {{SLUG}}

The skill is at {{REPO}}/skills/{{SLUG}}/SKILL.md. Here is the review:

{{REVIEW_JSON}}

Everything under must_fix, technical_errors, verb_honesty and budget_violations is not optional.

Fix each so the claim becomes CORRECT, not so it becomes unfalsifiable — widening a sentence until
it can no longer be checked is the exact failure mode the next reviewer is told to look for.
Anything you deliberately do not fix, say why.

{{CONSISTENCY_FINDINGS}}

If the budget genuinely cannot cover the procedure, CHANGE THE BUDGET and say you did — the budget
is a claim about the skill, not a constraint handed down from outside.

Keep metadata semiskill-role/semiskill-level at exactly {{ROLE}}/{{LEVEL}}. Bump semiskill-version.

## Verify before you finish — MANDATORY, from {{REPO}}

    python -m semiskill.cli lint skills/{{SLUG}}      # must print [approve 1.000] and clean
    python -m semiskill.cli lint skills/              # must report NO error-level finding

Edit ONLY {{REPO}}/skills/{{SLUG}}/. Never touch sibling skills, _shared/, or the linter — other
agents own those and may be editing them concurrently.

Return JSON: {"slug", "lint_line", "clean":bool, "fixed":[], "not_fixed":[]}
```

For a C005 finding add: *"choose deliberately — either ADD the step branch that assigns the value,
or DROP the value. Do not simply mention the word somewhere to silence the checker; the recheck
looks for exactly that."*

---

## P3-RECHECK (superseded — prefer P5)

Kept only to explain why P5 exists. This prompt ended in *"Would you hand this to a working DV
engineer today? 'Nearly' is a no."* with no way to record a nit separately. Reviewers listed
`semiskill-review-by` collisions beside genuine blockers and then failed the skill, so **0 of 44
skills could pass by construction**. Use P5.

---

## P4-FIX-ROUND-2

Model: strong. For skills that already failed one independent recheck.

```
{{P0-PREAMBLE}}

# YOUR TASK — close the findings an independent recheck left open on {{SLUG}}

The skill is at {{REPO}}/skills/{{SLUG}}/SKILL.md. It was written, reviewed once, fixed once, and
then a FRESH reviewer who had not seen the fixer's reasoning rejected it.

**First read the gate record: {{REPO}}/skills/{{SLUG}}/REVIEW.json.** Its `recheck` object holds the
open findings (under `remaining`, `blocking`, `remaining_nits`, `new_problems` — read all four), and
`review` and `fix` record what the earlier round already found and changed, so you do not undo a
deliberate decision. THEN read SKILL.md in full, then close the findings.

- Anything marked BLOCKER, or that makes a step impossible inside the skill's own retrieval budget,
  or that is technically WRONG about the DV domain, is not optional.
- Fix each so the claim becomes CORRECT, not unfalsifiable.
- Items labelled "Nit" are worth closing when the fix is a phrase. Where a nit would cost structure
  you need, say so in not_fixed with the reason.
- If you believe a finding is simply WRONG, say so in not_fixed with your reasoning and evidence.
  A reviewer being mistaken is a real outcome; pretending to fix it is not.
- If the budget cannot cover the procedure, CHANGE THE BUDGET and say you did.

Keep metadata role/level at exactly {{ROLE}}/{{LEVEL}}. Bump semiskill-version.

## Verify — MANDATORY, from {{REPO}}

    python -m semiskill.cli lint skills/{{SLUG}}
    python -c "from semiskill.authoring.consistency import check_pack; [print(f.rule,f.level,f.slug,f.message[:120]) for f in check_pack('skills') if '{{SLUG}}' in f.slug]"

Edit ONLY {{REPO}}/skills/{{SLUG}}/.

Return JSON: {"slug", "lint_line", "clean":bool, "fixed":[], "not_fixed":[]}
```

**Why the fixer reads its own REVIEW.json** rather than being handed the findings: the findings stay
authoritative on disk, the prompt stays small, and the fixer also sees what the *previous* round
decided — which stops it re-breaking a deliberate choice.

---

## P5-RECHECK-CALIBRATED ← the publish gate

Model: strongest available. **Must be a fresh context that has not seen the fixer's reasoning.**

```
{{P0-PREAMBLE}}

# YOUR TASK — independent recheck

You are a FRESH reviewer. You did not write this skill, you did not fix it, and you have
deliberately not seen the fixer's reasoning. Every earlier round of this project that was rechecked
by the lineage which produced the fix shipped a new bug.

Read {{REPO}}/skills/{{SLUG}}/SKILL.md as it stands now, plus the three _shared/ files.

## The judgement you are making

This skill is for a real DV engineer at a real company. The question is NOT "is this perfect" — it
is **"would this help a competent engineer do this task, and could any part of it lead them
astray?"**

Sort everything you find into exactly two buckets:

**BLOCKING** — it would make an engineer take a WRONG action, or a step cannot be carried out at all:
  - technically wrong or misleading about the DV domain
  - a step that cannot run inside the skill's own stated retrieval budget, or a Grep/Read the budget
    never accounts for
  - a specific flag, message string, default or convention the author could not have known, asserted
    as fact rather than declared as a [[FILL:]] slot
  - a declared slot no step spends, or a handoff value no step assigns
  - a claim about a sibling skill, a shared file, or the pack that is not true
  - metadata role/level not exactly {{ROLE}}/{{LEVEL}}

**NON-BLOCKING** — real, but it would not mislead anyone: narrower-than-ideal phrasing, a nit, a
style point, a "could also mention", a semiskill-review-by collision.

Do not inflate a nit into a blocker to look rigorous, and do not demote a real defect to look
generous. A pack that never ships helps nobody; a pack that ships a wrong instruction is worse than
no pack.

Run from {{REPO}}:  python -m semiskill.cli lint skills/{{SLUG}}   and confirm 1.000 and clean.

**Set ready:true if and only if the BLOCKING list is empty.** Do NOT edit any file.

Return JSON: {"slug", "ready":bool, "why", "blocking":[], "non_blocking":[], "new_problems":[]}
```

---

## P6-AUTHOR-NEW-SKILL

Model: strong. For a registry cell with no `SKILL.md` yet.

```
{{P0-PREAMBLE}}

# YOUR SKILL — write it

directory and name: {{SLUG}}          (the folder name and frontmatter `name` must be identical)
semiskill-role:     {{ROLE}}
semiskill-level:    {{LEVEL}}
semiskill-title:    {{TITLE}}

What it must teach:
{{ONE_LINE}}

Write {{REPO}}/skills/{{SLUG}}/SKILL.md, following the contract's required body structure exactly
(8 sections, 180–260 lines, 5–10 [[FILL:]] slots, an explicit retrieval budget with a stopping rule
that every step obeys).

Read the four nearest sibling skills first so "## When to use something else" routes honestly and
you do not duplicate one of them.

## Verify — MANDATORY, from {{REPO}}

    python -m semiskill.cli lint skills/{{SLUG}}      # [approve 1.000], clean, zero findings
    python -m semiskill.cli lint skills/              # no error-level pack finding

Return JSON: {"slug","lint_line","clean":bool,"slots":int,"lines":int,"uncertainties":[]}

Be honest in `uncertainties` about every technical point you were not sure of. A flagged uncertainty
is far more useful to the reviewer than a confident invention.
```

---

## P7-SCOREBOARD

Model: **small/cheap (Sonnet-class)**. It tabulates deterministic output; it does not judge.

```
You are the scoreboard for SemiSkill's DV skill catalog. Report coverage. Do not fix anything, do
not edit any file, and do not infer — every number must come from a command you ran.

Run these from {{REPO}} and report the REAL output:

  python tools/gate_args.py --size 12
  python tools/gate2_args.py
  python -m semiskill.cli scoreboard --strict-gate
  python -c "from semiskill.authoring.consistency import check_pack; from collections import Counter; print(Counter((f.rule,f.level) for f in check_pack('skills')))"

Then produce:
 1. A role x level matrix of the 16 roles, marking each cell published / ready / not-ready /
    never-reviewed / missing.
 2. Every role below 5 published, with the exact shortfall.
 3. The gate funnel: authored -> lint-clean -> reviewed -> ready -> published, as five counts.
 4. Any skill on disk that is NOT in specs/skill_registry.json, and any registry cell with no
    SKILL.md. Both directions matter.
 5. Any skill whose semiskill-role/semiskill-level disagrees with the registry (facet drift).
 6. The single most under-served role, and how many skills it needs.

Rules:
 - A count you did not measure is not a count. If a command fails, say so; do not estimate.
 - "declined" cells may only credit a role that has already published everything else it planned,
  otherwise "we decided not to write a fifth" silently becomes "we are finished".
 - Report the funnel even when it is ugly. The purpose of this role is to make shortfalls visible.

Return JSON: {"matrix":[], "roles_below_target":[], "funnel":{}, "orphans":[], "facet_drift":[],
"most_underserved":"", "commands_run":[], "anything_that_failed":[]}
```

---

## P8-ADVERSARIAL-VERIFY

Model: strongest available. Run after any batch of automated edits, before trusting the result.

```
You are an ADVERSARIAL verifier. Other agents just changed {{WHAT_CHANGED}} in {{REPO}}. Your job is
to find what they broke or claimed falsely. Assume they are wrong until the commands prove
otherwise. You may FIX small defects you find, but report every one.

Run all of these from {{REPO}} and paste the REAL output:

  python -m pytest -q
  python -c "from semiskill.authoring.consistency import check_pack; from collections import Counter; print(Counter((f.rule,f.level) for f in check_pack('skills')))"
  python -c "from semiskill.authoring.consistency import check_pack; [print(f.rule,f.level,f.slug,'|',f.message[:160]) for f in check_pack('skills') if f.level=='error']"
  python -m semiskill.cli lint skills/
  python tools/gate_args.py --size 12

Then check specifically:
 - Does every claim in the agents' summary match what the commands actually print?
 - Did any skill regress below lint 1.000, or gain a new error-level finding?
 - Did any REVIEW.json get written for a skill whose reviewer never returned? (A dead agent must
   leave NO record, never ready:false.)
 - Does any shared reference now state something the pack does not support? A reference that lies is
   worse than none.

Set clean:true ONLY if there are zero error-level findings, zero test failures, and no false claim.

Return JSON: {"clean":bool, "findings":[{"severity","slug","what"}], "counts":"", "evidence":""}
```

**Why this exists:** an adversarial verifier caught ten real defects in one batch that the producing
agents reported as complete, including a wave-blocking error and a shared reference stating a census
that was false in both directions.

---

## Anti-patterns — these have all happened here

| Do not | Because |
|---|---|
| Let the fixer write `ready:true` | It is the exact failure the gate exists to prevent |
| Write `ready:false` for an agent that died | Records a rejection nobody made; poisons every count |
| Shorten P0 to "follow the house style" | The contract stops being a single source of truth |
| Ask for a verdict without BLOCKING/NON-BLOCKING | Nits become blockers and nothing can ever pass |
| Report a batch as done without re-running `check_pack` | Fix agents introduce defects |
| Run `pytest` while an agent runs it | Shared dev DB `TRUNCATE`s; ~30 phantom failures |
| Run more than 3 batches at once | Exhausts the token budget mid-flight |
| Bump a snapshot count to make a test pass | Assert shape or a ceiling instead, and read the diff |
| Use `--allow-ungated` to hit a number | It publishes unverified content and says so in the report |
