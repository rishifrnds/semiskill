# The execution workflow

The operating procedure for finishing SemiSkill's catalog. Written to be executed by **any** capable
model or person. Every step has a command, an acceptance criterion, and a stated failure mode.

Companion documents:
- **`docs/PROMPT_LIBRARY.md`** — the verbatim prompts each step uses.
- **`docs/AUTHORING_CONTRACT.md`** — what a skill must be. Every agent reads this first.
- **`docs/LEARNINGS.md`** — why the rules are what they are. Read before changing a check.
- **`HANDOFF.md`** — current state and the pending list.

---

## The invariant everything else serves

```
author → lint 1.000 → adversarial review → fix → INDEPENDENT recheck → REVIEW.json → publish
```

Three things are non-negotiable:

1. **Nobody certifies their own fix.** The recheck agent must be a fresh context that has not seen
   the fixer's reasoning.
2. **The gate record is a file on disk** (`skills/<slug>/REVIEW.json`), never a claim in a chat log.
3. **A step that did not run leaves no record.** If an agent dies, the skill keeps its previous
   status. Never write `ready:false` for a review that never happened — that is indistinguishable
   from a real rejection and it poisons every count downstream.

---

## Step 0 — Establish real state (always, every session)

```bash
docker compose up -d db
python tools/gate_args.py --size 12        # never-reviewed / not-ready / ready, read from disk
python tools/gate2_args.py                 # the not-ready set and their open findings
python -c "from semiskill.authoring.consistency import check_pack; \
  print([f.rule for f in check_pack('skills') if f.level=='error'])"
python -m pytest -q                        # see the hazard below
```

**Accept when:** consistency errors `[]`, tests all pass, and the three counts sum to 84.

**Hazard — do not skip:** never run `pytest` while an agent is also running it. The fixture
`TRUNCATE`s the shared dev Postgres `artifacts` table before every test; two concurrent runs destroy
each other and produce ~30 phantom failures that look exactly like a real regression.

---

## Step 1 — Round 2 over the not-ready skills (32 today)

These already have an independent review recorded in their `REVIEW.json`. The fixer reads its own
gate record; you do not need to pass the findings in.

**Prompts:** `P4-FIX-ROUND-2`, then `P5-RECHECK-CALIBRATED`.
**Driver (if using the Workflow tool):** `tools/dv-gate2.js`, args from `tools/gate2_args.py --emit`.

```bash
python tools/gate2_args.py --emit --size 11 --batch 1
```

Run **at most 3 batches concurrently** (4+ has exhausted a session token budget mid-flight).
Batch size 10–12 skills.

**Accept when:** every skill returns a verdict with `blocking` and `non_blocking` populated, and
`ready` is true if and only if `blocking` is empty.

---

## Step 2 — First gate over the never-reviewed skills (49 today)

**Prompts:** `P1-ADVERSARIAL-REVIEW` → `P2-FIX` → `P3-RECHECK` (or `P5` for the calibrated verdict —
preferred; see the note in the prompt library).
**Driver:** `tools/dv-gate.js`, args from `tools/gate_args.py`.

```bash
python tools/gate_args.py --batch 1 --size 12
```

Each cell carries its own machine-checked consistency findings so agents do not rediscover them.

**Accept when:** every skill has a `REVIEW.json` whose `recheck` records a real verdict.

---

## Step 3 — Collect and re-verify, after EVERY batch

```bash
python tools/collect_wave.py <workflow-run-dir> --wave <name>
python -c "from semiskill.authoring.consistency import check_pack; from collections import Counter; \
  print(Counter((f.rule,f.level) for f in check_pack('skills')))"
python -m semiskill.cli lint skills/
```

**Why this is not optional:** fix agents introduce defects. Two were caught this way in one session
— an undeclared `phase` narrowing (C007) and a wave-blocking value-wearing-a-sentence (C009) — and
neither appeared in any review.

**Accept when:** zero error-level consistency findings, and every touched skill still lints 1.000.
If a new error appears, fix it before starting the next batch; errors compound.

---

## Step 4 — Publish

```bash
python -m semiskill.cli wave-plan skills/          # dry run; shows what the gate will refuse
python -m semiskill.cli wave skills/ --yes
```

The wave refuses any skill whose `REVIEW.json` is missing (`gate-missing`) or not ready
(`gate-not-ready`), before writing anything. **That is correct behaviour, not a bug.** Expect the
first run to refuse most of the pack.

`--allow-ungated` exists for fixtures and seeds only, and names every skill it lets through in the
wave report. Do not use it to hit a number.

**Accept when:** the wave report's published count equals the ready count from Step 0, and
`gate-refused` accounts for the rest.

---

## Step 5 — Prove coverage

```bash
python -m semiskill.cli scoreboard --strict-gate
```

**Accept when:** 16/16 roles at ≥5 published, zero facet drift, zero "published without an
independent recheck".

The registry (`specs/skill_registry.json`) is the plan of record. A skill's `semiskill-role` and
`semiskill-level` must match it exactly. If a role is missing from the linter's vocabulary, fix
`semiskill/authoring/facets.py` — **do not** remap the skill to a role that happens to lint. That
inversion has already happened once and produced five silently-drifted skills.

---

## Step 6 — Ship the front end

```bash
python -m semiskill.cli site      # dist/site — the browsable catalog, published skills only
python -m semiskill.cli pack      # dist/semiskill-dv + .zip — the Cursor-installable pack
```

The site is deliberately driven by the **published** catalog; an unpublished skill must never reach
it, and a test enforces that. For a look at authored-but-unverified work, `build_site` accepts an
explicit `entries` list **only** together with `preview="<what it is>"`, which stamps a banner and a
different footer on every page. Passing `entries` without `preview` raises.

**Accept when:** every internal link resolves, no page makes a network call, and no page carries a
fabricated metric. All three are tested — `ui/catalog-demo.html` once shipped "1.3k installs ·
★4.8", which is why the regex test exists.

---

## Step 7 — Keep the record honest

A commit-msg hook blocks commits when `STATUS.md` is more than 30 minutes stale.

- **`STATUS.md`** — overwrite, right-now snapshot, under 40 lines.
- **`MEMORY.md`** — append-only step log. `status: done` plus a timestamp is the only completion
  marker; prose is not.
- **`DECISIONS.md`** — append-only ADRs.
- **`HANDOFF.md`** — refresh the counts and the pending list before ending a session.

---

## Batching and cost

| Setting | Value | Why |
|---|---|---|
| Concurrent batches | **3 max** | 4+ exhausted a session token budget mid-flight |
| Batch size | 10–12 skills | ~30 agent runs per batch at 3 stages each |
| Model — review / recheck | strongest available | this is where the value is; it finds domain errors |
| Model — fix | strong | it must fix correctly, not plausibly |
| Model — scoreboard | small/cheap (Sonnet-class) | it reads deterministic output and tabulates |
| Model — author | strong | 200–260 lines of correct DV content |

Cheap-model steps: scoreboard, collection, and any step whose output is checked by a command.
Expensive-model steps: anything producing a judgement nobody re-derives.

---

## Expect rounds

One fix pass followed by a strict recheck converged on **zero of 44** skills. Two causes, and only
one was the content: the findings were real, *and* the round-1 verdict counted nits as blockers so
`ready:true` was unreachable by construction. Budget for at least two rounds, and use the calibrated
verdict (`P5`) from the start.

---

## Definition of done

- [ ] 84/84 skills have a `REVIEW.json` recording an independent recheck
- [ ] Every published skill's recheck `blocking` list is empty
- [ ] `scoreboard --strict-gate` shows 16/16 roles at ≥5, zero drift, zero ungated publishes
- [ ] Zero error-level consistency findings; C005/C008/C011 warns at zero or explicitly accepted
- [ ] Full test suite green
- [ ] `dist/site` and `dist/semiskill-dv.zip` regenerated from the published catalog
- [ ] `STATUS.md`, `MEMORY.md`, `HANDOFF.md` current
