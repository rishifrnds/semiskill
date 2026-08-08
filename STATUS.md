<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-08T23:14:59Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills; prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes
- User asked for three queued follow-ups done sequentially: pool the artifact store (done,
  J-010e8), review `tools/issue_batch.py` (done, J-010e9), start the Stage-5 adapter (next).
- Coordinator PID 2038 (this session's shell) is the sole writer.

## Active step
- none in flight. Next: start the Stage-5 loopback adapter (Ollama), code-only progress blocked
  on BLK-004 for credit, same pattern as Stage-2 being done-but-blocked on BLK-003.

## J-010e9 result: tools/issue_batch.py reviewed and fixed (done)
Found and fixed a real path-containment defect; reviewed everything else and found it holds.

- **Fixed**: `_verify_snapshot_freshness` joined untrusted snapshot fields
  (`sources.registry.path`, `sources.skills.root`) onto `repo_root` with no containment check -
  an absolute path silently discarded `repo_root` (stdlib `Path.__truediv__` behaviour) and a
  relative `..`-laden string escaped once resolved, turning this freshness check into an
  arbitrary local file read / directory enumeration. Added `_confined_path()`
  (tools/issue_batch.py:81-101), mirroring the containment check the trusted snapshot generator
  already applies on write (`semiskill/authoring/snapshot.py` ~1383) on the read side too. 5 new
  adversarial tests (absolute escape x2, relative traversal, empty path) written first, observed
  failing pre-fix, passing after.
- **Deliberately deferred, not dropped**: `_cell_checks` trusts the snapshot document's own
  self-reported pass/fail claims rather than independently re-reading the real
  `automated_review`/`scan_run` artifacts from the store. Not exploitable today
  (`security_pass` is 0/84 under honest generation), but the trust boundary has no independent
  re-verification. This is the SAME gap already tracked as "scoreboard v3" (HANDOFF.md gap 4,
  next pending item) - belongs there, not as a further patch to `issue_batch.py`.
  - Verified positive findings (no action needed): the contract schema `issue_batch.py` emits
    matches `collect_wave.load_contract`'s required shape field-for-field (confirmed by reading
    both, not just trusting the round-trip tests); slug-derived output filenames are safe because
    capture-time `_slugify` already strips everything but `[a-z0-9-]` and `_lease_cell` requires
    the artifact's own stored slug to match.
- Verification: targeted suite (`test_issue_batch.py` + `test_collect_wave.py` +
  `test_review_collection.py`) 60/60 passed. Full `pytest tests/`: **1200 passed, 7 skipped,
  0 failed, 205s**, live DB, no port-exhaustion failure - second consecutive clean full run,
  confirming J-010e8's pooling fix holds under repeated heavy load.

## J-010e8 result: PostgresArtifactStore connection pooling (done, carried forward)
Fixed the Windows port-exhaustion flake from J-010e6 with a per-DSN `psycopg_pool.ConnectionPool`
(new dependency; ADR-027 in DECISIONS.md). Full detail in MEMORY.md's J-010e8 entry. Known
remaining gap (recorded, not fixed): test-fixture-driven churn from 29 files each constructing a
fresh store per test is unchanged by this fix.

## TWO blockers still hold every skill at the scan gate, not one
Measured, not inferred. Stage statuses across all 84 captures: stage 1 `passed`, **stage 2
`not_run`**, stage 3 `passed`, stage 4 `passed`, stage 5 `not_sampled`.
- Stage 2 blocks every skill on its own (needs ADR-024 scanner approval, BLK-003).
- Stage 5 judge policy fails loudly by design (ADR-026) rather than being relaxed; BLK-004 unresolved.

## Stage-5 adapter — what exists and what's needed (research done this session, not yet built)
- Nothing exists yet: zero Ollama/Stage-5 code anywhere in the repo (confirmed by grep).
- What a new adapter must satisfy: the `Judge` Protocol (`semiskill/sensor/judge.py:42-43`,
  `score(*, candidate: str, rubric: str) -> float`, returns `[0,1]`), consumed by
  `JudgeRiskScanner` (`semiskill/scanners/judge_risk.py`, already exists, already wired into
  `run_pipeline` via `judge_risk_scanner`, but UNTESTED - no `test_judge_risk.py` exists).
  `Scanner` protocol requires `stage = ScanStage.JUDGE_RISK` and a `ScanResult`
  (`semiskill/scanners/base.py:22,56-65`).
- No HTTP client, stdlib or third-party, is used anywhere in this codebase yet - `urllib.request`
  for the loopback call is a genuinely new pattern, not a new dependency (already stdlib).
- Must follow ADR-024/ADR-026 rigor: fail-closed, exact-key validated report, host-bound identity
  never trusted from model output, no fabricated pass. Must NOT touch `judge_policy_refusal`
  (`semiskill/wave.py:201-222`) or `REQUIRED_JUDGE_NOT_PASSED` (`semiskill/authoring/snapshot.py`
  ~636-645) - the adapter's job is only to become a real judge that can legitimately earn
  `"passed"`, never to relax the policy that currently refuses without one.
- Proposed direction (HANDOFF.md:355-368, not yet approved as implementation, just a proposal):
  Ollama 0.32.5, exact loopback 127.0.0.1 HTTP, model `qwen3-coder:30b` with pinned manifest/blob/
  config/parameter hashes, no proxies/redirects/tools, temperature 0, strict JSON schema, bounded
  request/response/time, fail-closed daemon binding checks (current local Ollama listens on
  wildcard `[::]:11434` - activation must fail until it's loopback-only, per HANDOFF.md gap 3).
  This remains code-only progress even once built - BLK-004 (independent human calibration
  labels/adjudication/thresholds) is what actually earns Stage-5 credit, same pattern as Stage-2
  code being done-but-blocked on BLK-003.

## Active blockers
- BLK-001: production Entra/OIDC, SharePoint and least-privilege identities are absent. Past its
  escalation deadline (`2026-08-08T13:29:31Z`); surfaced to the user at this session's start.
- BLK-003: the internal Stage-2 image/rule pack needs AppSec/legal/supply-chain approval.
- BLK-004: Stage-5 needs loopback-only runtime plus independent labels/adjudication/calibration.

## Full-suite status
Last FULL `pytest tests/` run (this session, dirty tree, not an immutable record): 1200 passed,
7 skipped, 0 failed, 205s, live DB, zero port-exhaustion failures (second consecutive clean run).
Last IMMUTABLE (clean-source) full-suite PASS record remains
`a6792604-42ec-4111-a801-b55de5a43669` on source `28379ab` (J-010e6) - source has since changed
twice more (J-010e8, J-010e9); re-run on the clean committed tree before treating any of these as
current evidence for a migration or release gate.

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

## Last checkpoint
- J-010e9 is the containing checkpoint for the issue_batch.py review
  (`artifacts: this J-010e9 checkpoint`).
- This session so far: J-010e7 (state repair) -> J-010e8 (connection pooling) -> J-010e9
  (issue_batch.py review), all done. Next: Stage-5 adapter.
- No step this session earns any review, approval, publication or launch-readiness credit.
