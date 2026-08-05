# HANDOFF — SemiSkill, Phase J

_Written 2026-08-05T17:00Z. Last commit: `1ea933c`. Branch: `main`._

Read this, then `STATUS.md`, then `docs/AUTHORING_CONTRACT.md`. `docs/LEARNINGS.md` explains why the
rules are what they are — read it before changing any check.

---

## Resume prompt — paste into a fresh terminal

```
Read HANDOFF.md, STATUS.md, MEMORY.md (tail), docs/AUTHORING_CONTRACT.md and docs/LEARNINGS.md
first. Do not trust any status claim you have not measured — the previous session's record said
"77 skills through the full gate" and the truth was 0 published.

Context: SemiSkill is an internal security-verified Agent-Skills marketplace. 84 DV skills are
authored across 16 roles (>=5 each). All lint 1.000, zero pack-consistency errors, 456 tests green.
NOTHING is published, and nothing may be: `semiskill wave` now refuses any skill whose
skills/<slug>/REVIEW.json does not record an INDEPENDENT recheck with ready:true. 3 are ready,
32 failed a first recheck with real findings, 49 have never been reviewed.

Verify state first:
  docker compose up -d db
  python tools/gate_args.py --size 12      # never-reviewed / not-ready / ready
  python tools/gate2_args.py               # the not-ready set and their open findings
  python -c "from semiskill.authoring.consistency import check_pack; print([f.rule for f in check_pack('skills') if f.level=='error'])"
  python -m pytest -q                      # NEVER run this while an agent is also running it

Then work the queue in this order, using a pool of subagents:
 1. Round 2 over the 32 not-ready skills:  tools/dv-gate2.js  (args: tools/gate2_args.py --emit)
 2. First gate over the 49 never-reviewed: tools/dv-gate.js   (args: tools/gate_args.py --batch N --size 12)
 3. After EVERY batch: python tools/collect_wave.py <workflow-run-dir> --wave <name>
    then re-run check_pack — fix agents introduce defects (2 caught last session).
 4. Only when skills are ready:true, publish and prove coverage:
      python -m semiskill.cli wave skills/ --yes
      python -m semiskill.cli scoreboard --strict-gate
      python -m semiskill.cli site && python -m semiskill.cli pack
 5. Keep MEMORY.md / STATUS.md current — a commit-msg hook blocks commits when STATUS.md is >30min
    stale.

Rules that cost real time to learn, do not rediscover them:
 - Run at most 3 gate workflows concurrently; 4+ exhausted the session token limit mid-flight.
 - Never run pytest while an agent runs it (shared dev DB TRUNCATEs `artifacts`; 30 phantom failures).
 - A skill whose recheck agent dies must get NO gate record, never ready:false.
 - Nobody certifies their own fix. The recheck agent must not see the fixer's reasoning.
```

---

## Where things stand

| Metric | Value |
|---|---|
| Skills authored | **84** — all 16 roles at >=5 (registry: `specs/skill_registry.json`) |
| Lint | 84/84 at `approve 1.000`, clean |
| Pack consistency | **0 errors**; 60 warns (C005 54, C002 3, C008 2, C001 1) |
| Tests | **456 green** (was 404 at session start) |
| Gate: ready | **3** — dv-build-filelist-hygiene, dv-ral-bringup, dv-repo-orientation |
| Gate: not-ready with findings | **32** |
| Gate: never reviewed | **49** |
| **Published to catalog** | **0** |

---

## Pending tasks, in dependency order

1. **[J-003a] Round 2 over the 32 not-ready skills.** `tools/dv-gate2.js`. Each fixer reads its own
   `skills/<slug>/REVIEW.json` for the open findings; the recheck sorts everything BLOCKING /
   NON-BLOCKING and sets `ready` iff BLOCKING is empty. This was launched once and died on the token
   limit having completed nothing — it is a clean re-run.
2. **[J-003b] First gate over the 49 never-reviewed skills.** `tools/dv-gate.js`, batches of 12,
   args from `tools/gate_args.py`. Includes 17 whose fix agent ran last session but whose recheck
   never did — their SKILL.md edits are on disk, their gate record deliberately is not.
3. **[J-003c] Author-gate the new skill.** `dv-security-build-divergence-audit` is authored and
   lint-clean but has never been reviewed. It is in the never-reviewed 49.
4. **[J-006] Publish.** `semiskill wave skills/ --yes`. Expect it to publish only what is ready and
   name every refusal — that is correct behaviour, not a bug.
5. **[J-007] Scoreboard.** `scoreboard --strict-gate` must show 16/16 roles at >=5 published.
6. **[J-008] Regenerate the site and pack** (`semiskill site`, `semiskill pack`) and re-verify the
   site has no fabricated metric and no outbound network call (tests cover both).
7. **[J-009] Tighten the two ceiling assertions** in `tests/authoring/test_consistency.py`
   (`test_c008_...`, `test_c011_...`) from `<= KNOWN` to `== set()` once the gate has cleared them.
8. **[J-010] Update `CLAUDE.md`'s "Current phase"** — it still says Phase 0.

---

## Known gaps and issues

### Content (the real work)
- **0 of 44 skills that completed a full first gate pass were judged ready.** The findings are
  genuine — see `docs/LEARNINGS.md` §"On the content itself" for four representative examples. This
  is the single biggest open item and it is content, not tooling.
- **60 consistency warns** remain: 54 × C005 (a handoff value no step assigns), 3 × C002, 2 × C008
  (a field duplicating a registered enum under a different name), 1 × C001 (unused slot in
  `dv-repo-orientation`). Each is fed to its own skill's fix agent by `gate_args.py`.
- **3 × C011 dangling cross-skill citations** were open at last count and are being closed by the
  gate: `dv-coverage-hole-disposition` cites a `disposition` field `dv-coverage-hole-closure` does
  not have; `dv-cross-tool-mismatch-adjudication` promises `run id` and writes `runs`;
  `dv-tool-version-migration` promises `signature` and has no such line.
- **Body length has drifted.** Contract says 180–260 lines; the shipped pack averages ~350 and one
  skill reached 429. Not blocking, but the contract and the pack disagree — decide which moves.

### Process / infrastructure
- **Session token limit** ended the last run mid-flight. Run at most **3** gate workflows
  concurrently.
- **Shared dev DB test hazard** — never run `pytest` concurrently with an agent that runs it.
- **`REVIEW.json` is inside the hashed payload.** `capture.intake.load_skill_dir` sweeps every
  non-`SKILL.md` file into `files`, so writing a gate record changes `payload_sha256` and
  re-publishes the skill as a supersede — and the record ships inside the installable pack.
  Arguably it is metadata *about* a skill rather than part of it, but excluding it would change
  every published hash. Decide deliberately before the first real publish.
- **`semiskill/wave.py` defines `LINT_FAILED`** which is never assigned or read. Pre-existing dead
  constant.
- **Windows ephemeral-port exhaustion** has been seen once in a full suite run
  (`Address already in use`, 10048) from the many short-lived connections the pipeline opens.
  Re-ran clean. Worth a connection-reuse look eventually.
- **The dev catalog DB is empty** and two fixture slugs (`dv-alpha`, `dv-beta`) have appeared in a
  scoreboard run as "published but not in the registry". Verify the catalog contains exactly the
  registry's skills after the first real publish.

### Deferred / not started
- No auth, nothing deployed, no CI, no backups (carried forward from earlier phases).
- Stage-2 live security-audit, stage-5 live judge, pgvector and SharePoint embedding all still need
  external resources; they are exercised via fakes.
- The SharePoint-native catalog page (Phase H deliverable) has not been regenerated since the pack
  grew from 6 to 84 skills.

---

## Key files

| Path | What it is |
|---|---|
| `docs/AUTHORING_CONTRACT.md` | **The project skill.** Single source of truth for authoring/reviewing. |
| `docs/LEARNINGS.md` | Why the rules are what they are. Read before changing a check. |
| `specs/skill_registry.json` | The 84-cell plan of record. Role/level here is authoritative. |
| `skills/_shared/handoff-vocabulary.md` | ADR-011 signed field registry (7 enums, 5 shape locks, 19 held nouns). |
| `skills/_shared/team-profile.md`, `failure-signature-schema.md` | Pack-wide facts; reference, never restate. |
| `tools/dv-gate.js` + `gate_args.py` | First gate: review → fix → independent recheck. |
| `tools/dv-gate2.js` + `gate2_args.py` | Round 2: fix → recheck with BLOCKING/NON-BLOCKING verdict. |
| `tools/collect_wave.py` | Turns a workflow journal into `REVIEW.json`. Leaves no record when a recheck never ran. |
| `semiskill/authoring/consistency.py` | Pack-level checks C001–C012, registry-driven. |
| `semiskill/authoring/gate.py` | The single reader of `REVIEW.json`. |
| `DECISIONS.md` | ADRs. ADR-008 frontmatter, ADR-009 wave, ADR-010 install, ADR-011 handoff vocabulary. |
