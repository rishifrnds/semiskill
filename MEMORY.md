<!--
Durable runtime state log for this project. Strict format — no prose-only entries.
Full rules and entry schemas: see STATE_RULES.md.

Edit by replacing <placeholders>. Append new entries to Completed Steps;
never edit past entries. Move Pending -> In-Flight -> Completed as work progresses.
-->

## Project
- Name: SemiSkill — Internal Security-Verified Skill Marketplace
- Goal (one sentence): Give the company one internal, SharePoint-hosted place to publish,
  discover, comment on, rate, and reuse Agent Skills — where every skill passes an automated
  security-verification pipeline and a human approval gate before it is published.
- Started: 2026-07-13
- CLAUDE.md version: 2026-07-13
- Repo: https://github.com/rishifrnds/semiskill
- Architecture: AIOS 6-layer (L1 Capture · L2 Spine/Artifacts · L3 Context · L4 Agents/Governance
  · L5 Intelligence · L6 Sensor) — mirrors E:\code\aios
- Build plan (approved 2026-07-13): C:\Users\rishi\.claude\plans\semiskill-ultra-mode-logical-lagoon.md

## Carry-forward from archives
Phase 0 (Foundation & Plan) complete — see archive/MEMORY-P0.md (steps P0-001..P0-003).
Still in use:
- State system files (CLAUDE.md, AGENTS.md, STATE_RULES.md, STATUS/DECISIONS/BLOCKERS).
- ULTRA_PLAN_PROMPT.md (build spec) and specs/ROLE_TAXONOMY.md (Phase G work-list).
- ADR-001 (AIOS 6-layer backbone), ADR-002 (gated publish actuator), ADR-003 (pipeline-verified seeding).
- research/ now populated with the 3 AIOS reference docs (system prompt context, phases, L5/L6 doc).
Open threads: Phases B–G unbuilt; the approved plan is the roadmap.

## Completed Steps
<!-- Append-only. Newest at bottom. Format:
- [A-001] <ISO-8601 timestamp>  status: done
  what: <one-line description>
  artifacts: <commit SHA first, then file paths, URLs, ADR-IDs>
  next: <STEP-ID of what follows, or "end-of-phase">
-->

- [A-001] 2026-07-13T02:45Z  status: done
  what: Scaffolded semiskill package (pyproject, docker-compose pg16, .env.example, config.py, package + tests dirs); package installs editable and pytest collects cleanly
  artifacts: pyproject.toml, docker-compose.yml, .env.example, semiskill/__init__.py, semiskill/config.py, semiskill/{artifacts,spine}/__init__.py, tests/{,artifacts,spine}/__init__.py
  note: Fixed an off-by-one in the state-system git hook — moved message-type enforcement from pre-commit to a new commit-msg hook. A pre-commit hook cannot read a `git commit -m` message, so the old hook read a stale COMMIT_EDITMSG and validated each commit against the PREVIOUS commit's message (a wip: commit was blocked under rotate: rules). Original preserved at .git/hooks/pre-commit.bak. Hooks live in .git/ (untracked) so this is not a committed change. Also gitignored *.egg-info/.
  next: A-002

- [A-002] 2026-07-13T02:48Z  status: done
  what: Ported the five-class event spine verbatim from AIOS (EventClass CAPTURED..OBSERVED + next_state/is_terminal); 2 tests green
  artifacts: semiskill/spine/states.py, tests/spine/test_states.py
  next: A-003
  note: Reordered remaining Phase A — schema (A-003) before lifecycle (A-004) since lifecycle imports ArtifactType/Artifact.

- [A-003] 2026-07-13T02:52Z  status: done
  what: Ported 17-column frozen Artifact + Artifact.new + with_eval_score from AIOS with SemiSkill domain enums (8 lifecycle ArtifactTypes + 4 L5/L6; source_system/actor_kind; permissions/objective vocabularies); 3 tests green incl. enum-vocabulary lock
  artifacts: semiskill/artifacts/schema.py, tests/artifacts/test_schema.py, ADR-001
  next: A-004

- [A-004] 2026-07-13T02:56Z  status: done
  what: Implemented derived domain lifecycle (SkillState + derive_state + STATE_SPINE_CLASS) — the ADR-002 structural gate. RED→GREEN: 6 tests incl. no_published_state_without_approval (submitter forging verdict/published on non-approval artifacts is floored at REVIEWED), rejected-approval, unrelated-artifact isolation
  artifacts: semiskill/spine/lifecycle.py, tests/spine/test_lifecycle.py, ADR-002
  next: A-005

- [A-005] 2026-07-13T03:00Z  status: done
  what: Security hardening from background review — bound the dev Postgres to loopback (127.0.0.1:5432) instead of all interfaces; documented that the config.py DATABASE_URL fallback + compose creds are local-dev-only non-secrets (real deploys set DATABASE_URL from a secret)
  artifacts: docker-compose.yml, semiskill/config.py, ADR-005
  reason: security review flagged insecure-network-exposure (compose) + hardcoded-credentials-fallback (config); mirrored from AIOS but hardened given SemiSkill's security-first mandate
  next: A-006

- [A-006] 2026-07-13T03:10Z  status: done
  what: L2 DB layer — migration 0001 (append-only trigger, CHECKs, corrects_ref self-FK, artifact_get SECURITY DEFINER + restricted semiskill_app role), migrate.py runner (verbatim AIOS), conftest pg_dsn disposable-DB fixture (skips if no PG), test_migrate (idempotency + real-0001-applies). Suite: 11 passed, 2 integration skipped pending a live Postgres
  artifacts: semiskill/artifacts/migrations/0001_artifacts.sql, semiskill/artifacts/migrate.py, tests/conftest.py, tests/artifacts/test_migrate.py
  note: conda Postgres 15 failed to start on Windows (DLL-init 0xC0000142); launched Docker Desktop to run integration tests. pg_dsn skips gracefully when no DB reachable so the unit suite stays green.
  next: A-007

- [A-007] 2026-07-13T03:40Z  status: done
  what: DB-backed L2 verified end-to-end — PostgresArtifactStore (append/get/by_type, INSERT/SELECT only), append-only trigger blocks UPDATE/DELETE, corrections are new rows via corrects_ref (self-FK enforced), structural ACL (semiskill_app cannot SELECT artifacts; artifact_get SECURITY DEFINER filters by label). Full suite 21 passed in 0.9s against live Postgres 16
  artifacts: semiskill/artifacts/store.py, tests/artifacts/test_store.py, tests/artifacts/test_append_only.py, tests/artifacts/test_corrections.py, tests/artifacts/test_acl.py
  note: Two Docker-for-Windows test-infra fixes (durable knowledge): (1) pg_dsn switched from disposable-DB-per-test to a session-scoped shared migrated DB + TRUNCATE-per-test isolation — CREATE/DROP DATABASE takes minutes on the Docker VM filesystem; TRUNCATE bypasses the append-only trigger so tests can reset while app code still cannot mutate. (2) DSN uses 127.0.0.1 not localhost — localhost resolves to IPv6 ::1 which the IPv4-bound container never answers, stalling every connection ~30s (suite went 917s -> 0.9s). Also fsync=off on the throwaway test DB. test_migrate rewritten isolation-independent.
  next: A-008

## In-Flight Step
_(none — A-008 next: Phase A verify gate — full suite green + confirm exit criteria, then checkpoint for user review before Phase B)_

## Pending Steps
1. [A-001] Scaffold Python package (semiskill/) + pyproject.toml + docker-compose.yml + config.py + tests skeleton
2. [A-002] Spine states (TDD): tests/spine/test_states.py + semiskill/spine/states.py (verbatim AIOS port)
3. [A-003] Spine lifecycle (TDD): tests/spine/test_lifecycle.py (incl. no_published_state_without_approval) + semiskill/spine/lifecycle.py
4. [A-004] Artifact schema (TDD): tests/artifacts/test_schema.py + semiskill/artifacts/schema.py (17-col dataclass + domain enums)
5. [A-005] Migration + runner + conftest: migrations/0001_artifacts.sql + migrate.py + tests/conftest.py + tests/artifacts/test_migrate.py
6. [A-006] Store (TDD): tests/artifacts/test_store.py + semiskill/artifacts/store.py (PostgresArtifactStore, INSERT/SELECT only)
7. [A-007] Append-only test: tests/artifacts/test_append_only.py (UPDATE/DELETE blocked at DB)
8. [A-008] Corrections test: tests/artifacts/test_corrections.py (correction is a new row via corrects_ref)
9. [A-009] ACL test: tests/artifacts/test_acl.py (semiskill_app cannot SELECT artifacts; artifact_get filters by label)
10. [A-010] Phase A verify gate: full pytest (unit + integration) green; confirm ADR-001 schema locked

## Current Phase
Phase A: Foundation & Schema (L2 substrate — append-only artifact store + five-class spine + derived domain lifecycle)

Exit criteria (each a concrete verifiable check):
- `docker compose up -d db && pytest` — all unit + integration tests green
- Schema round-trips (append→get returns equal); corrections append a new row (never UPDATE)
- Structural gate proven: `derive_state` returns no published/approved state without a positive `approval` artifact
- `semiskill_app` restricted role cannot SELECT the artifacts table directly; `artifact_get` ACL-filters by label
- ADR-001 canonical artifact schema confirmed/locked; ADR-004/005/006 recorded
