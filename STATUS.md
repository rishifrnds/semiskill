<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-07T11:56:09Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills; prove 16 roles at >=5.

## Session
- ID: 20260807T071649Z-RISHI_PC-cdcf04 - lock held: yes
- Crash-resume: user explicitly approved takeover after the prior lock
  (`20260806T064411Z-RISHI_PC-1faced`, stamped 2026-08-07T03:30:11Z, 3.5h stale) was found held by
  PID 21120, confirmed absent via `Get-Process`.
- Coordinator PID 3408 is the sole writer; pooled agents are read-only auditors.

## Active step
- none in flight. J-010e4 (Stage-2 report validation and fail-closed coverage) is selected.

## J-010d4 + J-010d5 result: the judge contradiction now fails loudly, and unblocks nothing
Per explicit user decision, the stage-5 judge policy was NOT relaxed. One shared predicate
`semiskill.wave.judge_policy_refusal` now backs both `run_wave` and the CLI (ADR-026):

- `run_wave` refuses the whole wave before touching the store when stage 5 is required and no judge
  scanner is configured.
- `semiskill wave` prints `wave refused: ...` and exits 2 instead of raising a traceback.
- `semiskill wave-plan` still inventories all 84 skills, but says the wave would refuse rather than
  claiming they "would be captured/scanned". Verified against the real catalog.

`semiskill wave` therefore refuses until BLK-004 is resolved. That is the honest state: it was
previously writing six artifacts per skill that the security gate was always going to reject.
`security_pass` remains 0 by design. Neither step earns any catalog credit.

## What the crashed session did - now independently VERIFIED
An unrecorded session ran ~2026-08-07T05:48Z-06:12Z and died without checkpointing. It committed
`c8f5fa3` with no STEP-ID and no MEMORY entry. Its work was preserved under J-010d3 and both of its
material claims were re-checked against the live store under J-010d6:

- CONFIRMED: the `0015 -> 0023` forward migration executed. `schema_migrations` holds 23 rows,
  last `0023_review_unbound_parameter_binding.sql`; 0016-0023 are all present. The human has since
  confirmed they approved that plan digest, so BLK-002 is resolved.
- CONFIRMED: all 84 registry-active slugs have a `skill_version` artifact. Counts reconcile exactly
  against the earlier 39-artifact baseline: scan_run 338 (2 + 336), review 119 (35 + 84),
  skill_version 85 (1 + 84), injection_test 84, gate_decision 2.
- FINDING: the 85th `skill_version` slug is `dv/cve`, a TEST FIXTURE from
  `tests/spine/test_pipeline.py`, captured into the DEVELOPMENT store at 2026-08-06T06:57:44. The
  store is append-only, so it cannot be removed - it is known non-crediting pollution and must never
  be counted. Any funnel or scoreboard reader must exclude unregistered slugs explicitly.

## Measured baseline
- Registry/filesystem: 84 active + 20 declined, 16 roles, every role >=5, 84 skill directories.
- Authoring: strict lint re-run this session, exit 0, `84/84 clean, 0 errors, 0 advisories`.
- Canonical funnel per the uncommitted v2 snapshot (`reports/scoreboard.json`, generated
  2026-08-07T05:54:16Z from commit `c8f5fa3` with `dirty: true`): authored 84, strict_lint_pass 84,
  security_pass 0, reviewed 0, recheck_ready 0, approved 0, published 0; `blocked.scan` = 84.
  Scoreboard v2 is diagnostic and known-defective; it authorizes nothing.
- Release gate in that snapshot: REGISTRY_ACTIVE/DECLINED/ROLES, ALL_AUTHORED and ALL_STRICT_LINT
  pass; ALL_REVIEWED, ALL_RECHECK_READY, ALL_APPROVED and ALL_PUBLISHED all read 0 of 84.
- Development DB reachable again: `semiskill-db-1`, PostgreSQL 16.14, 127.0.0.1:5432, schema 0023.
  Identity was observed as three different values as schema advanced (`9b98194d` dashboard 03:17Z,
  `85a8cb63` migration plan ~05:48Z, `d29b329d` scoreboard 05:54Z); re-pin it before binding
  evidence to it.
- Git: `c8f5fa3` and `3ce5694` are pushed; `1494750`, `47c4aaf` and this J-010d5 checkpoint are
  local-only. Re-verify local/remote equality before treating any of them as shared.
- Canonical anomaly set: still unavailable; scoreboard v3 does not exist.

## TWO blockers hold every skill at the scan gate, not one
Measured, not inferred. `_security_projection` for `dv-minimal-reproducer` returns status `blocked`
with errors `['REQUIRED_JUDGE_NOT_PASSED', 'REQUIRED_STAGE_BLOCKED']`. Stage statuses across all 84
captures: stage 1 `passed`, **stage 2 `not_run`**, stage 3 `passed`, stage 4 `passed`, stage 5
`not_sampled`.

- `snapshot.py` requires stages 1-4 to ALL be `passed`, so **Stage 2 blocks every skill on its own**,
  independently of the judge. It needs the ADR-024 scanner plus AppSec/legal approval (BLK-003).
- The stage-5 judge contradiction is the second blocker. ADR-026 made it fail loudly; the policy
  decision itself is still open and was deliberately not taken.
- `docs/UNBLOCK_SPECS.md` originally claimed the judge was "the single reason" and that fixing it
  yields `security_pass: 84`. That is false and is now corrected in place. Implementing SPEC A alone
  would leave all 84 blocked.

## Stage-2 build progress (ADR-024)
Approval-gated, not code-gated. The code can be finished and tested now; only BLK-003 unblocks credit.

- DONE (J-010e3): host-side staging projection, `semiskill/scanners/stage2_staging.py`. Untrusted
  paths normalized and refused before any write; payload-supplied scanner config isolated and
  recorded; staged tree compared to the expected coverage set exactly. 32 adversarial tests.
- NEXT (J-010e4): bounded exact-key report validation - reject unknown fields/severities, duplicate
  finding IDs, absolute/traversing paths, mismatched counts and container-supplied identity.
- THEN (J-010e5): identity binding - slug/version/payload hash, image platform-manifest digest,
  independently computed `rule_pack_sha256`, adapter commit, policy/schema/engine hashes.

## Immediate order
1. Re-run the immutable full suite on this clean source for a current PASS record, then regenerate
   a scoreboard from clean source rather than the current `dirty: true` snapshot.
2. Review and test the inherited `tools/issue_batch.py` before it leases any real work.
3. Scoreboard v3/progress v2, then Stage 2 and calibrated Stage 5, then prove 1 -> 5 -> 84.

## Active blockers
- BLK-001: production Entra/OIDC, SharePoint and least-privilege identities are absent.
- BLK-003: the internal Stage-2 image/rule pack needs AppSec/legal/supply-chain approval.
- BLK-004: Stage-5 needs loopback-only runtime plus independent labels/adjudication/calibration.

## Full-suite status: current PASS
Run `5eb6210d-8f6a-41a1-a48b-8190a696b416` on clean source `854ae71`
(tree `a493c56ca1699ec64b9e0b531bd4bf41dbba7e28`): 1117 collected, 1110 passed, 7 skipped,
0 failed, 0 errors, against isolated `semiskill_test` at 0023.

- This is the first clean-source PASS since `b36f250`. It unblocks gates that require one - a new
  source-bound migration plan, a release checkpoint - and moves NO skill through the security gate.
- It goes stale the moment the source changes. Re-run before binding any new decision to it.
- Both prior failures are fixed: the README red-team regression (from `105b3cb`) and the
  response-delivery race (J-010d9).

## Standing hazards
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- Shared dependencies changed all 84 full payload hashes, so historical reviews credit none.
- A lint hash covers `SKILL.md` only; review/approval uses the full captured payload hash.
- `84/84 lint clean` is a SECURITY score and says nothing about whether the DV content is correct.
- Scoreboard v2 nested evidence/progress validation has a reproduced P0 gap and is stale/dirty-source.
- An unavailable observation, migration authority or scoreboard remains unavailable - not zero.
- `tools/issue_batch.py` is inherited, unreviewed code that mints review leases. Treat it as
  untrusted until it is tested against `collect_wave.py::_validate`.
- The development store contains a test-fixture `skill_version` (`dv/cve`). Append-only means it
  stays; every count must exclude unregistered slugs explicitly rather than assuming 1:1.

## Last checkpoint
- J-010d6 is the containing checkpoint (`artifacts: this J-010d6 checkpoint`).
- This session: J-010d3 repaired state after the crash; J-010d4/J-010d5 made the unsatisfiable judge
  policy refuse loudly and consistently (ADR-026); J-010d6 verified the store and repaired the wave
  integration tests. Two correction entries fixed forward-dated timestamps.
- No step this session earns any review, approval, publication or launch-readiness credit.
