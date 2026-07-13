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
Phase 0 (Foundation & Plan) → archive/MEMORY-P0.md. Phase A (Foundation & Schema) → archive/MEMORY-A.md.
In use / built:
- L2 substrate: semiskill/artifacts/{schema,store,migrate}.py + migrations/0001_artifacts.sql;
  semiskill/spine/{states,lifecycle}.py; semiskill/config.py. 21 tests green.
- Structural invariants proven: append-only trigger (UPDATE/DELETE blocked), corrections via corrects_ref,
  derive_state ADR-002 gate (no APPROVED/PUBLISHED without a positive `approval` artifact), structural ACL
  (semiskill_app can't SELECT artifacts; artifact_get SECURITY DEFINER filters by label).
- ADRs: 001 (AIOS 6-layer), 002 (gated publish), 003 (pipeline-verified seeding), 004 (web-app hosting),
  005 (local Docker Postgres), 006 (all 6 scanners).
- Test/infra (Windows/Docker durable knowledge): DB = Docker Postgres 16 (`docker compose up -d db`,
  binds 127.0.0.1:5432, fsync=off throwaway). USE 127.0.0.1 NOT localhost (IPv6 ::1 stalls ~30s).
  Tests use a session-scoped shared migrated DB + TRUNCATE-per-test isolation (CREATE/DROP DATABASE is
  minutes-slow on the Docker VM FS). Git hooks fixed: message enforcement in .git/hooks/commit-msg
  (pre-commit can't read a `-m` message); original at .git/hooks/pre-commit.bak.
Open threads: Phases C–G unbuilt. pgvector/semantic search deferred (needs Voyage egress) — Phase B uses
Postgres full-text + graph traversal (hermetic).

## Completed Steps
<!-- Append-only. Newest at bottom. -->

- [B-001] 2026-07-13T04:05Z  status: done
  what: L1 capture intake — parse_skill_md (YAML frontmatter via safe_load + untrusted body), build_skill_version (facets slug/name/version/function/role/level/owner/tags/allowed_tools → skill_version artifact, body/files kept untrusted), load_skill_dir (reads SKILL.md + files, flags binaries). 10 unit tests green. Added pyyaml dep
  artifacts: semiskill/capture/intake.py, tests/capture/test_intake.py, pyproject.toml, ADR-007
  next: B-002

- [B-002] 2026-07-13T04:10Z  status: done
  what: L1 event builders — build_comment (threaded via parent_id), build_rating (1-5 validated), build_reuse_event (method); each references the skill_version via input_refs so L3 can build threads/aggregates/reuse graph from the log. 10 unit tests green (20 capture total)
  artifacts: semiskill/capture/events.py, tests/capture/test_events.py
  next: B-003

- [B-003] 2026-07-13T04:15Z  status: done
  what: CLI — `semiskill submit <dir>` (load_skill_dir → build_skill_version → store.append; prints state=submitted, no publish) and `semiskill list`; injectable store for hermetic tests; [project.scripts] entry point registered and working. 4 tests green
  artifacts: semiskill/cli.py, tests/cli/test_cli.py, pyproject.toml
  next: B-004

## In-Flight Step
_(none — B-004 next: L3 acl.py resolve_allowed_labels + untrusted.delimit (verbatim AIOS ports))_

## Pending Steps
1. [B-001] L1 capture intake — parse SKILL.md frontmatter → skill_version artifact (semiskill/capture/intake.py) + unit tests
2. [B-002] L1 events — comment/rating/reuse_event builders (semiskill/capture/events.py) + unit tests
3. [B-003] CLI — `semiskill submit`/`list` (semiskill/cli.py) + pyproject entry point + tests
4. [B-004] L3 acl.py (resolve_allowed_labels) + untrusted.delimit (verbatim AIOS ports) + unit tests
5. [B-005] migration 0002_context.sql — SECURITY DEFINER catalog-search + lineage + reuse-graph fns, ACL-filtered, role grants + test
6. [B-006] L3 retrieve — ACL-enforced catalog browse/search (semiskill/context/retrieve.py) + integration tests (need-to-know invisible)
7. [B-007] L3 provenance — lineage + reuse graph, fail-closed pruning (semiskill/context/provenance.py) + integration tests
8. [B-008] Phase B verify gate

## Current Phase
Phase B: Capture + Context (L1/L3)

Exit criteria (each a concrete verifiable check):
- A submitted skill is queryable only per its ACL — a `need-to-know` skill is invisible to an unauthorized querier
- Catalog read model surfaces only PUBLISHED skill_versions (derived from a positive published `approval`), ACL-filtered
- Lineage (input_refs) and reuse graph (reuse_event → skill_version) return correct edges, pruned fail-closed at unauthorized nodes
- Full-text/faceted search over skill_versions works (function/role/level/tags)
- `docker compose up -d db && pytest` all green
