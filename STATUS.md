<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-09T01:40:58Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills to the DEVELOPMENT
catalog (ADR-029 — production/SharePoint is a separate, later milestone); prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes
- Local Postgres is now TWO separate docker-compose services (ADR-032): `db` (port 5432) is the
  real dev catalog + the 3 actuator logins; `db-test` (port 5433, new) is pytest's isolated
  database on its own cluster. **IMPORTANT**: run pytest with ONLY `TEST_DATABASE_URL` exported
  (now `...5433/semiskill_test`) - never the full `.env`, or `SEMISKILL_APPROVAL_DATABASE_URL`/
  `_REVIEW_COORDINATOR_DATABASE_URL`/`_EXPORT_DATABASE_URL` silently redirect a test-DB store's
  actuator calls to the real `db` cluster. See `.env.example` and ADR-032.
- This session found and corrected TWO real regressions from its own earlier work (J-010f1) by
  actually running the full suite before checkpointing, not by trusting identity-method checks
  alone - see J-010f3 / ADR-032 for the full diagnosis. Both are fixed; full suite is clean.

## Active step
- none in flight. Next: close the scoreboard v3 gap (artifact-level re-verification, HANDOFF.md
  gap 4 / J-010e9 finding-2).

## J-010f2 + J-010f3 results: review-issue CLI wired, then a real regression found and fixed
- **J-010f2 (done)**: `review-issue` CLI command wired. Orchestration moved from unpackaged
  `tools/issue_batch.py` into importable `semiskill/authoring/issue_batch.py` (needed so
  `semiskill review-issue` works from an installed package, not just a repo checkout).
  `tools/issue_batch.py` is now a thin delegator - direct script invocation still works.
  Same `_test`-refusal / `--yes` safety pattern as `wave`. 5 new CLI tests.
- **J-010f3 (done)**: the FIRST full-suite run after J-010f2 found 7 failed + 23 errors, ALL in
  `tests/artifacts/test_forward_migration.py` - caused by J-010f1's DB roles, not by J-010f2's
  changes. Root cause: Postgres roles are CLUSTER-WIDE, not per-database; J-010f1's 3 new logins
  (granted into capability roles) were visible from `semiskill_test` too, breaking exact
  role/membership attestation tests that treat unexpected grants as a privilege-escalation signal.
  Fixed by splitting Postgres into `db` (real catalog, unchanged container/data, now also the 3
  logins) + new disposable `db-test` cluster for pytest (ADR-032). A SECOND full-suite run then
  found a DIFFERENT problem (95 failed, 44 errors): `PostgresArtifactStore.__init__` reads the
  three actuator DSN env vars unconditionally, so a sourced `.env` silently redirected even
  test-DB stores' approval/review/export calls to the real catalog. Fixed by convention
  (`.env.example` now warns explicitly; pytest must export only `TEST_DATABASE_URL`).
- Verification after both fixes: full `pytest tests/` (TEST_DATABASE_URL only): **1231 passed,
  7 skipped, 0 failed, 302.67s**. The 628 pre-existing captured artifacts in `db` are untouched
  (`db`'s docker-compose service definition was kept byte-identical specifically so `docker
  compose up` would never recreate that container).
- Process note, worth remembering: ADR-029's "10-minute, zero-risk" framing for the DB role
  provisioning was wrong on two separate counts, both caught only by actually running the full
  suite - not by the identity-method checks (`review_coordinator_authentication_context()` etc.)
  that seemed like sufficient verification at the time. Re-run the full suite after ANY database
  topology or credential change, even ones that look purely additive/local.

## TWO blockers still hold every skill at the scan gate, not one (both approval-only until built)
Stage statuses across all 84 captures: stage 1 `passed`, **stage 2 `not_run`**, stage 3 `passed`,
stage 4 `passed`, stage 5 `not_sampled`.
- Stage 2: code exists but unwired, no real image/rule pack yet - BLK-003, addressed by pending item 2.
- Stage 5: adapter exists but unwired, no calibration yet - BLK-004, addressed by pending item 3.

## Immediate order
1. Close scoreboard v3 gap: independent artifact-level re-verification of cell claims against the
   live store, per J-010e9 finding-2 / HANDOFF.md gap 4.
2. Build the real Stage-2 image + rule pack (ADR-030 pragmatic scope); wire `Stage2Adapter` into
   `pipeline.py`/`wave.py`; get the user's explicit digest approval (BLK-003).
3. Wire `OllamaJudge`/`Stage5Policy` into the CLI/pipeline; build + propose the 120-item
   calibration gold set (ADR-031 solo labeling); run calibration (BLK-004).
4. Vertical-prove `dv-minimal-reproducer` end to end, then the 5-skill wave-0 cohort, then the
   remaining 79 in batches <=10.
5. Follow-up, not urgent: `apply_migrations()`'s same-transaction new-enum-value bug (only
   surfaces bootstrapping a truly empty `_test` DB in one shot; worked around via pg_dump/restore
   for `db-test`, not fixed at the source).

## Active blockers
- BLK-001: narrowed to PRODUCTION-only (Entra/SharePoint tenant + zero SharePoint code to
  activate it). Development identities resolved (J-010f1, corrected J-010f3/ADR-032); no longer
  gates 84/84-to-development.
- BLK-003: Stage-2 image/rule pack don't exist yet; real build work, then user approval (ADR-030).
- BLK-004: Stage-5 needs a real gold-set + the user's solo calibration labeling (ADR-031).

## Full-suite status
Last full `pytest tests/` run: **1231 passed, 7 skipped, 0 failed, 302.67s** (J-010f3, this
session, run with only `TEST_DATABASE_URL` exported against the new `db-test` cluster). This is
the current, trustworthy baseline - both regressions this session introduced and then found are
fixed.
Last IMMUTABLE (clean-source) full-suite PASS record remains
`a6792604-42ec-4111-a801-b55de5a43669` on source `28379ab` (J-010e6) - source has changed
repeatedly since; generate a fresh one before treating it as current evidence for a release gate.

## Standing hazards
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- **Run pytest with ONLY `TEST_DATABASE_URL` exported, never the full `.env`** - the three
  `SEMISKILL_*_DATABASE_URL` actuator vars silently redirect test-DB stores to the real catalog
  (ADR-032, J-010f3). This is enforced by convention/documentation only, not code.
- Local Postgres is TWO docker-compose services now: `db` (5432, real catalog) and `db-test`
  (5433, pytest only, fully disposable, recreate freely). Never grant new roles/logins on `db`
  without checking they can't be reached from `db-test`'s cluster (they can't, by design, but any
  FUTURE third cluster/service needs the same isolation reasoning applied fresh).
  `apply_migrations()` bootstrapping a truly empty `_test` database in one shot can hit a
  Postgres "unsafe use of new enum value" error (pre-existing latent bug, not yet fixed) - if
  `db-test` is ever wiped, restore via `pg_dump`/`pg_restore` from `db`'s `semiskill_test`
  history rather than a raw `apply_migrations()` bootstrap, or fix the underlying bug first.
- Shared dependencies changed all 84 full payload hashes, so historical reviews credit none.
- A lint hash covers `SKILL.md` only; review/approval uses the full captured payload hash.
- `84/84 lint clean` is a SECURITY score and says nothing about whether the DV content is correct.
- Scoreboard v2 nested evidence/progress validation has a reproduced P0 gap and is stale/dirty-source,
  AND its own cell-level claims are not independently re-verified against live artifacts
  (J-010e9 finding-2) - do not treat a v2 snapshot as authoritative for anything beyond source drift.
- An unavailable observation, migration authority or scoreboard remains unavailable - not zero.
- The development store contains a test-fixture `skill_version` (`dv/cve`). Append-only means it
  stays; every count must exclude unregistered slugs explicitly rather than assuming 1:1.
- Docker Desktop is not guaranteed to be running at session start on this machine - check
  `docker ps` before assuming either Postgres container is reachable.
- A state file (STATUS.md) can itself become corrupted by a runaway append - verify its size and
  content sanity, don't just trust that "it was updated last session".
- Any "published"/"security_pass" claim from this point MUST say "development catalog" and, once
  Stage-2/5 land, MUST cite ADR-030/031's explicit rigor caveats - never bare "published" or
  "passed" without that context (ADR-029/030/031).

## Last checkpoint
- J-010f3 is the containing checkpoint for the cluster-split correction
  (`artifacts: this J-010f3 checkpoint`).
- This session: J-010e7 -> e8 -> e9 -> e10 -> (pushed) -> f0 -> f1 -> f2 -> f3, all done, all
  committed except f2/f3 (about to commit together). Next: scoreboard v3 gap.
- No step this session earns any review, approval, publication or launch-readiness credit yet.
