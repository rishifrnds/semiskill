<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-07T07:52:00Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills; prove 16 roles at >=5.

## Session
- ID: 20260807T071649Z-RISHI_PC-cdcf04 - lock held: yes
- Crash-resume: user explicitly approved takeover after the prior lock
  (`20260806T064411Z-RISHI_PC-1faced`, stamped 2026-08-07T03:30:11Z, 3.5h stale) was found held by
  PID 21120, confirmed absent via `Get-Process`.
- Coordinator PID 3408 is the sole writer; pooled agents are read-only auditors.

## Active step
- none in flight. J-010d5 (make the CLI wave-plan path honest) is selected, not started.

## J-010d4 result: the judge contradiction now fails loudly, and unblocks nothing on purpose
Per explicit user decision, the stage-5 judge policy was NOT relaxed. `run_wave` now accepts
`judge_risk_scanner`/`judge_required` and refuses the whole wave before touching the store when
stage 5 is required and no judge scanner is configured (ADR-026). `semiskill wave` therefore refuses
until BLK-004 is resolved - which is the honest state, because it was previously writing six
artifacts per skill that the security gate was always going to reject. `security_pass` remains 0.
Known remaining gap: the CLI `wave-plan`/`--dry-run` path returns before `run_wave` and still prints
an over-optimistic plan. That is J-010d5, not a claim that it works.

## What the crashed session actually did (recorded, not credited)
An unrecorded session ran ~2026-08-07T05:48Z-06:12Z and died without checkpointing. Its output is
now preserved under J-010d3. It committed `c8f5fa3` with no STEP-ID and no MEMORY entry.

- Claimed and UNVERIFIED: the 0015->0023 forward migration was planned, reviewed and executed
  against the development database (`reports/migration-plan.json`, `docs/UNBLOCK_SPECS.md`).
- Claimed and UNVERIFIED: the wave ran across all 84 skills, each producing a `skill_version` plus
  6 scan artifacts and landing `awaiting-review` (9 `reports/wave-*.json|md`, 05:52-05:54Z).
- Neither claim could be re-verified in this session: the Docker daemon is down and a read-only
  `psycopg.connect` to the development store raised `ConnectionTimeout`. Unavailable is unavailable
  - not zero, not pass, not confirmed.

## Measured baseline
- Registry/filesystem: 84 active + 20 declined, 16 roles, every role >=5, 84 skill directories.
- Authoring: strict lint re-run this session, exit 0, `84/84 clean, 0 errors, 0 advisories`.
- Canonical funnel per the uncommitted v2 snapshot (`reports/scoreboard.json`, generated
  2026-08-07T05:54:16Z from commit `c8f5fa3` with `dirty: true`): authored 84, strict_lint_pass 84,
  security_pass 0, reviewed 0, recheck_ready 0, approved 0, published 0; `blocked.scan` = 84.
  Scoreboard v2 is diagnostic and known-defective; it authorizes nothing.
- Release gate in that snapshot: REGISTRY_ACTIVE/DECLINED/ROLES, ALL_AUTHORED and ALL_STRICT_LINT
  pass; ALL_REVIEWED, ALL_RECHECK_READY, ALL_APPROVED and ALL_PUBLISHED all read 0 of 84.
- Development DB identity has been observed as three different values as schema advanced:
  `sha256:9b98194d...` (dashboard, 03:17Z), `sha256:85a8cb63...` (migration plan, ~05:48Z),
  `sha256:d29b329d...` (scoreboard, 05:54Z). None of the three is currently re-observable.
- Git: HEAD `c8f5fa3`, `main` is 0 behind / 1 ahead of `origin/main`; no rebase was pending.
- Canonical anomaly set: still unavailable; scoreboard v3 does not exist.

## The structural blocker found by the crashed session (SPEC A)
`semiskill/spine/pipeline.py::run_pipeline` correctly writes a stage-5 artifact with status
`not_sampled` when `judge_risk_scanner is None` - a skipped judge is never rendered as a pass. But
`semiskill/authoring/snapshot.py` (~line 642) raises `REQUIRED_JUDGE_NOT_PASSED` whenever
`judge_required` and the judge is not `passed`. The wave supplies no judge scanner, so all 84 skills
sit at `SECURITY_BLOCKED` even though every stage that ran scored 1.000 and the aggregate verdict is
`approve`. **No skill can reach `security_pass` in this environment until one of those two rules is
rescoped.** Details and the proposed resolution are in `docs/UNBLOCK_SPECS.md`.

## Immediate order
1. Make the CLI `wave-plan`/`--dry-run` path refuse consistently with `run_wave`.
2. Restore the development store, re-verify schema 0023 and the 84 captures, then run the
   integration suites deferred by BLK-005 serially.
3. Review and test the inherited `tools/issue_batch.py` before it leases any real work.
4. Scoreboard v3/progress v2, then Stage 2 and calibrated Stage 5, then prove 1 -> 5 -> 84.

## Active blockers
- BLK-001: production Entra/OIDC, SharePoint and least-privilege identities are absent.
- BLK-002: the 0015->0023 migration was reportedly executed by the crashed session without a
  recorded human digest approval; the execution and its authority chain need audit.
- BLK-003: the internal Stage-2 image/rule pack needs AppSec/legal/supply-chain approval.
- BLK-004: Stage-5 needs loopback-only runtime plus independent labels/adjudication/calibration.
- BLK-005: the development database is unreachable (Docker daemon down), so no canonical artifact,
  migration or funnel claim can be verified.

## Standing hazards
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- Shared dependencies changed all 84 full payload hashes, so historical reviews credit none.
- A lint hash covers `SKILL.md` only; review/approval uses the full captured payload hash.
- `84/84 lint clean` is a SECURITY score and says nothing about whether the DV content is correct.
- Scoreboard v2 nested evidence/progress validation has a reproduced P0 gap and is stale/dirty-source.
- An unavailable observation, migration authority or scoreboard remains unavailable - not zero.
- `tools/issue_batch.py` is inherited, unreviewed code that mints review leases. Treat it as
  untrusted until J-010d6 tests it against `collect_wave.py::_validate`.

## Last checkpoint
- J-010d3 is the containing state-repair checkpoint (`artifacts: this J-010d3 checkpoint`).
- It abandons J-010d2 as superseded by events and preserves the crashed session's evidence without
  granting it any review, approval, publication or launch-readiness credit.
