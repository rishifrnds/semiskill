<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-09T01:02:40Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills to the DEVELOPMENT
catalog (ADR-029 — production/SharePoint is a separate, later milestone); prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes
- Pushed `origin/main` = `ef09db6` (J-010e7..e10) with user authorization.
- User then asked to "continue till we have all 84 skills published." Research found the real
  gates are narrower/differently-shaped than HANDOFF.md implied. Presented 3 scope decisions to
  the user via AskUserQuestion; all recorded as ADR-029/030/031:
  - **ADR-029**: "published" = development catalog (real Postgres approval record), not
    SharePoint (zero SharePoint/Graph code exists anywhere; would be new integration work).
  - **ADR-030**: BLK-003 (Stage-2 image) resolved with pragmatic rigor - exact pinned digest, real
    rule pack, wired in - but signing/SBOM/CVE automation explicitly deferred, not silently
    skipped.
  - **ADR-031**: BLK-004 (Stage-5 calibration) uses solo labeling by the user - explicit deviation
    from the two-labeler design, recorded as a real integrity gap, not resolved-in-the-original-sense.
- 11-item task list created tracking the full path to 84/84-in-development. See tasks #4-14.

## Active step
- none in flight. Next: wire the `review-issue` CLI command (task #5 / Pending Steps item 1).

## J-010f1 result: dev-environment DB roles provisioned and verified (done)
Created `semiskill_approval_login` / `semiskill_review_login` / `semiskill_export_login` as real
local Postgres logins against the existing docker-compose dev DB, each granted exactly one
capability role (migrations 0011/0012/0016). Credentials live in `.env` (gitignored, NOT
committed) - see that file for the actual DSNs, not this document.

- Verified two ways: (1) `PostgresArtifactStore.review_coordinator_authentication_context()` /
  `.export_database_identity()` both resolve correctly (role membership, exactly-one export
  label). (2) Because PG16 has per-grant INHERIT semantics that membership alone doesn't prove,
  empirically called `append_verified_review_contract`/`append_verified_approval` with
  deliberately-invalid data through each new login and confirmed a business-logic
  `CheckViolation`, not `InsufficientPrivilege` - the grant chain genuinely works, not just
  "membership resolves."
- `BLOCKERS.md` updated: BLK-001 narrowed to production-only scope (dev credentials resolved,
  doesn't block 84/84-to-development anymore). BLK-004 updated to note the solo-labeling path,
  still blocking until calibration actually runs.

## Path to 84/84 (development catalog) - current real state
1. DONE (J-010f1): dev approval/review/export DB identities provisioned and verified.
2. NEXT: wire `review-issue` CLI command. Mostly EXISTING logic
   (`tools/issue_batch.py` + `semiskill/authoring/review_collection.py` + DB coordinator
   authority already built and tested) - needs a `semiskill/` module + `cli.py` subparser, not
   new algorithm design.
3. Scoreboard v3 gap: independent artifact-level re-verification of cell claims against the live
   store, replacing trust in the snapshot's self-reported status (J-010e9 finding-2). The
   nested/self-hash validation itself is already thorough (`semiskill/authoring/snapshot.py`
   `_semantic_validate_scoreboard`, ~230 lines) - this is one specific real gap, not a rebuild.
4. Stage-2 real build (ADR-030 pragmatic scope): currently NOTHING exists beyond the tested
   host-side code (staging/report/adapter, J-010e3/e4/e5) - no Dockerfile, no real rule pack (only
   a 2-line test placeholder), no engine wiring, and `Stage2Adapter` isn't even connected to
   `pipeline.py`/`wave.py` yet (still calls the retired `npx` runner). This is genuinely
   multi-step build work, then the user's explicit digest approval closes BLK-003.
5. Stage-5 wiring + calibration (ADR-031 solo path): `OllamaJudge` (J-010e10) isn't wired into
   the pipeline yet either. Needs local Ollama made loopback-only + a pinned model, a 120-item
   gold-set built and proposed, then the user's solo blind-labeling, then kappa computation
   closes BLK-004 (with the explicit ADR-031 caveat attached to every result it produces).
6. Vertical-prove `dv-minimal-reproducer` end to end through the now-real dev approval chain, then
   the 5-skill wave-0 cohort, then the remaining 79 in batches of <=10 (full suite every 3
   batches).
7. Next.js catalog / market-readiness work (HANDOFF.md Gate 3) stays deferred - not required for
   the development-catalog milestone; revisit only before an eventual production/SharePoint push.

## TWO blockers still hold every skill at the scan gate, not one (both approval-only until built)
Stage statuses across all 84 captures: stage 1 `passed`, **stage 2 `not_run`**, stage 3 `passed`,
stage 4 `passed`, stage 5 `not_sampled`.
- Stage 2: code exists but unwired, no real image/rule pack yet - BLK-003, addressed by step 4.
- Stage 5: adapter exists but unwired, no calibration yet - BLK-004, addressed by step 5.

## Active blockers
- BLK-001: narrowed to PRODUCTION-only (Entra/SharePoint tenant + zero SharePoint code to
  activate it). Development identities resolved (J-010f1); no longer gates 84/84-to-development.
- BLK-003: Stage-2 image/rule pack don't exist yet; real build work, then user approval (ADR-030).
- BLK-004: Stage-5 needs a real gold-set + the user's solo calibration labeling (ADR-031).

## Full-suite status
Last full `pytest tests/` run: 1226 passed, 7 skipped, 0 failed (233.92s, J-010e10, before this
session's push). No test-affecting code has changed since (J-010f1 was pure DB/infra setup +
docs) - re-run before the next code change lands, don't assume still current after one.
Last IMMUTABLE (clean-source) full-suite PASS record remains
`a6792604-42ec-4111-a801-b55de5a43669` on source `28379ab` (J-010e6) - four commits stale now.

## Standing hazards
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- Shared dependencies changed all 84 full payload hashes, so historical reviews credit none.
- A lint hash covers `SKILL.md` only; review/approval uses the full captured payload hash.
- `84/84 lint clean` is a SECURITY score and says nothing about whether the DV content is correct.
- Scoreboard v2 nested evidence/progress validation has a reproduced P0 gap and is stale/dirty-source,
  AND its own cell-level claims are not independently re-verified against live artifacts
  (J-010e9 finding-2) - do not treat a v2 snapshot as authoritative for anything beyond source drift.
- An unavailable observation, migration authority or scoreboard remains unavailable - not zero.
- The development store contains a test-fixture `skill_version` (`dv/cve`). Append-only means it
  stays; every count must exclude unregistered slugs explicitly rather than assuming 1:1.
- Docker Desktop / the local Postgres container are not guaranteed to be running at session start
  on this machine - check `docker ps` before assuming `semiskill-db-1` is reachable.
- A state file (STATUS.md) can itself become corrupted by a runaway append - verify its size and
  content sanity, don't just trust that "it was updated last session".
- `.env` now holds real (if low-value, local-only) credentials - gitignored, verify `git status`
  never shows it staged before any commit.
- Any "published"/"security_pass" claim from this point MUST say "development catalog" and, once
  Stage-2/5 land, MUST cite ADR-030/031's explicit rigor caveats - never bare "published" or
  "passed" without that context (ADR-029/030/031).

## Last checkpoint
- J-010f1 is the containing checkpoint for the DB role provisioning
  (`artifacts: this J-010f1 checkpoint`).
- This session: J-010e7 -> e8 -> e9 -> e10 -> (pushed) -> f0 (push record) -> f1 (DB roles +
  3 ADRs), all done, all committed. Next: review-issue CLI wiring.
- No step this session earns any review, approval, publication or launch-readiness credit yet.
