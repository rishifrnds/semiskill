<!--
Durable runtime state log for this project. Strict format — no prose-only entries.
Full rules and entry schemas: see STATE_RULES.md.
-->

## Project
- Name: SemiSkill — Internal Security-Verified Skill Marketplace
- Goal: One internal SharePoint-hosted place to publish/discover/comment/rate/reuse Agent Skills —
  every skill passing an automated security pipeline + human approval before publish.
- Started: 2026-07-13 · Repo: https://github.com/rishifrnds/semiskill · Architecture: AIOS 6-layer (E:\code\aios)
- Build plan (approved): C:\Users\rishi\.claude\plans\semiskill-ultra-mode-logical-lagoon.md
- Session goal: complete all planned tasks (Phases C–G) and surface gaps/issues (no per-phase pause).

## Carry-forward from archives
Phases 0/A/B/C/D/E/F done → archive/MEMORY-{P0,A,B,C,D,E,F}.md. Built + green (180 tests):
- All 6 AIOS layers implemented + tested; gated publish; held-out corpus; red-team zero-escape;
  L5 stability/controller/cost; read API + UI (Artifact + Next.js scaffold); calibration report + docs.
- Roles: semiskill_app / semiskill_submitter / semiskill_pipeline. ADRs 001-007. migrations 0001..0008.
- INFRA: Docker PG16 (127.0.0.1, fsync=off); shared-DB TRUNCATE tests; git enforcement in commit-msg hook.
- Pipeline verification helper: redteam/harness.run_case (submit → pipeline → publish attempt).
- GAPS: stage-2 live security-audit / stage-5 live judge / pgvector / SharePoint embedding need external
  resources (tested via fakes / demonstrated). specs/ROLE_TAXONOMY.md is the Phase G work-list.

## Completed Steps
<!-- Append-only. Newest at bottom. -->

- [G-001] 2026-07-13T08:20Z  status: done
  what: semiskill/seed.py — seed_skill (generated skill → build_skill_version → run_pipeline → human-approve-if-clean → published; NO back-door insert) + seed_catalog. 2 tests: clean seed publishes via gate (carries a passing scan_run + a real published approval, faceted by function); broken seed (Bash) blocked identically (never discoverable)
  artifacts: semiskill/seed.py, tests/seed/test_seed.py
  next: G-002

## In-Flight Step
_(none — G-002 next: generate a Design/Verification role×level wave via a Workflow fan-out)_

## Pending Steps
1. [G-001] semiskill/seed.py — seed_skill (generated skill → full pipeline → human approve → published; no back-door) + tests (clean publishes, broken blocked)
2. [G-002] Generate a representative Design/Verification wave (role×level) via a Workflow fan-out
3. [G-003] Run the wave through seed_skill; verify each published carries a passing scan_run + approval; a deliberately-broken seed blocked identically; catalog faceted by function/role/level
4. [G-004] Phase G verify gate (+ final project summary)

## Current Phase
Phase G: Seed the catalog with role-based skills (dogfood the pipeline)

Exit criteria:
- Every published seed skill carries a passing scan_run + approval artifact (reached publish only via the gate — no back-door)
- A deliberately-broken seed skill is blocked exactly like any other submission
- Catalog is faceted by function / role / level (search returns generated skills by facet)
- Representative wave generated + verified (full-org hundreds flagged as scalable-but-not-exhaustively-run)
- `docker compose up -d db && pytest` all green
