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
Phases 0/A/B/C/D done → archive/MEMORY-{P0,A,B,C,D}.md. Built + green (171 tests):
- L2 store (schema/store/migrate + migrations 0001..0007), spine (states/lifecycle).
- L1 capture (intake/events/cli). L3 context (acl/untrusted/retrieve/provenance + catalog_search/lineage/reuse fns).
- L4/L6 pipeline: 6 stages (static/security-audit/injection/secret-PII/judge/aggregate) + orchestrator
  + gated publish + rollback + held-out corpus (semiskill_pipeline can't read it) + red-team (zero escapes).
- L5: intelligence/{stability(six-control),controller(queue-rank + drift-blocks-auto-act)} + governance/cost.
- Roles: semiskill_app (read), semiskill_submitter (can't forge verification), semiskill_pipeline (can't read corpus).
- ADRs 001-007. INFRA: Docker PG16 (127.0.0.1 not localhost, fsync=off); shared-DB TRUNCATE tests;
  git enforcement in .git/hooks/commit-msg. Catalog is DERIVED from artifacts (active published approval).
- GAPS: stage-2 security-audit needs egress sandbox+claude-flow (injected-runner tested); stage-5 live judge
  needs API keys (FakeJudge tested); pgvector semantic search deferred; live SharePoint embedding needs a tenant.

## Completed Steps
<!-- Append-only. Newest at bottom. -->

## In-Flight Step
_(none — starting Phase E: E-001 read API)_

## Pending Steps
1. [E-001] semiskill/api.py — stdlib HTTP JSON read API over L3 (health/catalog/skill/queue/lineage/reuse), ACL via principal header + integration tests
2. [E-002] Demonstrable catalog UI (HTML Artifact) — verification-badge-centric, faceted browse, skill cards + detail, one-click reuse (skills.sh / outskill reference)
3. [E-003] ui/ Next.js + shadcn production scaffold (ADR-004 SharePoint-embeddable) + Phase E gate

## Current Phase
Phase E: SharePoint hosting + Catalog UI

Exit criteria:
- Read API serves ACL-enforced catalog search (facets/text) + skill detail (README/tools/scan-report/provenance) + review-queue + lineage + reuse
- A skill appears in the catalog read model ONLY after human approval (already structurally guaranteed; re-verified via API)
- Verification badge is the centerpiece of every skill card; comment/rate/reuse represented
- Demonstrable catalog UI (renderable); Next.js production scaffold recorded (full SharePoint embedding deferred, ADR-004)
- `docker compose up -d db && pytest` all green
