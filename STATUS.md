<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-08T23:06:59Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills; prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes
- Continuing from the same-session repair (J-010e7): took over a stale prior lock with explicit
  user approval, repaired STATUS.md append-corruption and a stale MEMORY.md backlog list.
- User then asked for all three queued follow-ups done sequentially: pool the artifact store,
  review `tools/issue_batch.py`, start the Stage-5 adapter. This session is 1 of 3.
- Coordinator PID 2038 (this session's shell) is the sole writer; pooled agents this session were
  used read-only (three parallel Explore agents for research) before any file was written.

## Active step
- none in flight. Next: review and test `tools/issue_batch.py` against `collect_wave.py::_validate`.

## J-010e8 result: PostgresArtifactStore connection pooling (done)
Fixed the Windows port-exhaustion flake from J-010e6. `PostgresArtifactStore` now keeps a
`psycopg_pool.ConnectionPool` per distinct DSN (up to 4: `_dsn`/`_approval_dsn`/
`_review_contract_dsn`/`_export_dsn`), `min_size=1, max_size=4`, lazily created on first use, with
row_factory reset on every checkout so no dict/tuple leakage is possible across a reused
connection. New dependency: `psycopg-pool` (pyproject.toml). New ADR: ADR-027 (DECISIONS.md).

- Verification: `tests/artifacts/test_store.py` 10/10 passed (6 new tests). Full `pytest tests/`:
  **1196 passed, 7 skipped, 0 failed in 200.13s** - on a dirty (uncommitted-at-test-time) tree, so
  not an immutable full-suite PASS record, but a real zero-failure run against the live DB with no
  port-exhaustion failure.
- Environment note: Docker Desktop and the `semiskill-db-1` Postgres container were both down at
  this session's start and were started as routine local dev setup (not a project state change).
- Known remaining gap (recorded in ADR-027, not silently dropped): this does NOT fix
  test-fixture-driven churn - 29 test files each construct a fresh `PostgresArtifactStore` per
  test, and `tests/conftest.py`'s `pg_dsn` fixture separately opens two more bare (unpooled)
  connections per test for its TRUNCATE reset. A larger fixture-architecture change, not done here.
- Test-design note worth remembering: the first version of the reuse test asserted
  `connections_num <= 1` and failed at `2 <= 1` - a legitimate pool-warmup race (the background
  `min_size` fill vs. an immediate first call), not a bug. Rewritten to assert steady-state reuse
  (count stops moving) instead of an exact warm-up count. Watch for the same false-failure shape
  in any future test that touches `psycopg_pool` internals directly.

## TWO blockers still hold every skill at the scan gate, not one
Measured, not inferred. `_security_projection` for `dv-minimal-reproducer` returns status `blocked`
with errors `['REQUIRED_JUDGE_NOT_PASSED', 'REQUIRED_STAGE_BLOCKED']`. Stage statuses across all 84
captures: stage 1 `passed`, **stage 2 `not_run`**, stage 3 `passed`, stage 4 `passed`, stage 5
`not_sampled`.
- Stage 2 blocks every skill on its own (needs ADR-024 scanner approval, BLK-003).
- Stage 5 judge policy fails loudly by design (ADR-026) rather than being relaxed; BLK-004 unresolved.

## Stage-2 build progress (ADR-024) - unchanged since J-010e5
Approval-gated, not code-gated.
- DONE (J-010e3/e4/e5): host-side staging projection, bounded exact-key report validator, host
  adapter. An unapproved chain never invokes the engine; every failure path returns blocking
  `not_run`, never a clean score.
- KNOWN GAP: the binding record is returned but not yet persisted into the scan artifact (needs a
  schema/migration change).
- STILL BLOCKED: cannot pass anywhere until AppSec/legal promote the exact image manifest digest
  and rule pack (BLK-003).

## Immediate order (this session, user-approved: do all three sequentially)
1. DONE - pool artifact-store connections (J-010e8, above).
2. NEXT - review and test `tools/issue_batch.py` (SPEC B) against `collect_wave.py::_validate`
   before it is allowed to lease any real work; currently unreviewed inherited code
   (HANDOFF.md gap 4). Existing coverage found this session: `tests/tools/test_issue_batch.py`
   already exists and round-trips through `collect_wave.load_contract`, but per HANDOFF.md it has
   only been "preserved," not independently reviewed/trusted. Read-only research this session
   already found one real gap worth fixing: `_verify_snapshot_freshness` joins
   `sources.registry.path`/`sources.skills.root` from the snapshot JSON onto `repo_root` with no
   containment check (no absolute-path or `..`-traversal rejection) before reading/hashing - an
   arbitrary local file-read/directory-enumeration primitive driven by attacker-controlled path
   strings in `tools/issue_batch.py:110-128`. Fix this as part of the review, not just test it.
3. THEN - start the Stage-5 loopback adapter (Ollama). Research this session confirmed: zero
   Ollama/Stage-5 code exists yet anywhere in the repo; the `Judge` Protocol
   (`semiskill/sensor/judge.py:42-43`, `score(*, candidate: str, rubric: str) -> float`) and
   `JudgeRiskScanner` (`semiskill/scanners/judge_risk.py`) already exist and are what a new
   adapter must satisfy; no HTTP client (stdlib or third-party) is used anywhere in this codebase
   yet, so `urllib.request` for the loopback call would be a genuinely new pattern, not a
   dependency addition. Must follow the ADR-024/ADR-026 rigor (fail-closed, exact-key validated,
   no fabricated pass) and must NOT touch `judge_policy_refusal`/`REQUIRED_JUDGE_NOT_PASSED`. This
   remains code-only progress - it cannot earn credit until BLK-004 (human calibration) closes.
4. Scoreboard v3/progress v2, then Stage 2 and calibrated Stage 5 promotion, then prove 1 -> 5 -> 84.

## Active blockers
- BLK-001: production Entra/OIDC, SharePoint and least-privilege identities are absent. Past its
  escalation deadline (`2026-08-08T13:29:31Z`); surfaced to the user at this session's start.
- BLK-003: the internal Stage-2 image/rule pack needs AppSec/legal/supply-chain approval.
- BLK-004: Stage-5 needs loopback-only runtime plus independent labels/adjudication/calibration.

## Full-suite status
Last FULL `pytest tests/` run (this session, dirty tree, not an immutable record): 1196 passed,
7 skipped, 0 failed, 200.13s, live DB, zero port-exhaustion failures.
Last IMMUTABLE (clean-source) full-suite PASS record remains
`a6792604-42ec-4111-a801-b55de5a43669` on source `28379ab` (J-010e6): 1198 collected, 1191 passed,
7 skipped, 0 failed. Re-run on the clean committed tree before treating either as current evidence
for a migration or release gate - source has changed since both.

## Standing hazards
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- Shared dependencies changed all 84 full payload hashes, so historical reviews credit none.
- A lint hash covers `SKILL.md` only; review/approval uses the full captured payload hash.
- `84/84 lint clean` is a SECURITY score and says nothing about whether the DV content is correct.
- Scoreboard v2 nested evidence/progress validation has a reproduced P0 gap and is stale/dirty-source.
- An unavailable observation, migration authority or scoreboard remains unavailable - not zero.
- The development store contains a test-fixture `skill_version` (`dv/cve`). Append-only means it
  stays; every count must exclude unregistered slugs explicitly rather than assuming 1:1.
- Docker Desktop / the local Postgres container are not guaranteed to be running at session start
  on this machine - check `docker ps` before assuming `semiskill-db-1` is reachable.
- A state file (STATUS.md) can itself become corrupted by a runaway append - verify its size and
  content sanity, don't just trust that "it was updated last session".

## Last checkpoint
- J-010e8 is the containing checkpoint for the pooling fix (`artifacts: this J-010e8 checkpoint`).
- This session so far: J-010e7 (state repair) then J-010e8 (connection pooling), both done.
- No step this session earns any review, approval, publication or launch-readiness credit.
