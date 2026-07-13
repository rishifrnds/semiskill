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
Phases 0/A/B/C/D/E done → archive/MEMORY-{P0,A,B,C,D,E}.md. Built + green (176 tests):
- L1 capture, L2 store/spine (migrations 0001..0008), L3 context (ACL retrieve/provenance + read API),
  L4/L6 pipeline (6 stages + gated publish + rollback + held-out corpus + red-team zero-escape),
  L5 intelligence (stability/controller/cost). UI: catalog-demo.html Artifact + Next.js scaffold.
- Roles: semiskill_app / semiskill_submitter / semiskill_pipeline. ADRs 001-007.
- INFRA: Docker PG16 (127.0.0.1, fsync=off); shared-DB TRUNCATE tests; git enforcement in commit-msg hook.
- GAPS: stage-2 security-audit + stage-5 live judge + pgvector + SharePoint embedding all need external
  resources (egress sandbox / API keys / tenant); tested with injected fakes / demonstrated via Artifact.

## Completed Steps
<!-- Append-only. Newest at bottom. -->

- [F-001] 2026-07-13T08:05Z  status: done
  what: governance/report.py — calibration_report (κ series/latest/calibrated-vs-0.6/drift status) + governance_posture (egress-deny-by-default, 3 restricted roles, tool allowlist/dangerous set, total spend + cost-per-verified-skill). 4 tests (uncalibrated / calibrated-passes-gate / drift-floor / posture)
  artifacts: semiskill/governance/report.py, tests/governance/test_report.py
  next: F-002

- [F-002] 2026-07-13T08:10Z  status: done
  what: Docs — top-level README.md (what/why, architecture table, quick start, gaps), docs/SECURITY.md (5 structural invariants + restricted roles + pipeline + Rule-of-Two + egress/redaction + rollback + calibration), docs/ADOPTION.md (author/approver/everyone workflows)
  artifacts: README.md, docs/SECURITY.md, docs/ADOPTION.md
  next: F-003

- [F-003] 2026-07-13T08:10Z  status: done
  what: Phase F verify gate PASSED — 180 green. Rollback drill re-verified (publish→unpublish→not discoverable); κ≥0.6 calibration report + governance posture (egress-deny / 3 roles / tool allowlist / cost-per-verified-skill); egress deny-by-default documented; README + SECURITY + ADOPTION present
  artifacts: 180-test suite green
  next: end-of-phase → Phase G (seed the catalog via the pipeline). Rotate at Phase G kickoff.

## In-Flight Step
_(none — Phase F COMPLETE. Continuing to Phase G per session goal.)_

## Pending Steps
1. [F-001] semiskill/governance/report.py — calibration_report (κ series/latest/drift vs 0.6) + governance_posture (egress-deny, roles, tool allowlist, cost-per-verified-skill) + tests
2. [F-002] Docs — top-level README.md + docs/SECURITY.md (invariants/roles/egress/redaction/rollback) + docs/ADOPTION.md (how employees use it)
3. [F-003] Phase F verify gate (rollback drill re-verified; κ≥0.6 reported; egress deny-by-default documented; full suite green)

## Current Phase
Phase F: Governance hardening & docs

Exit criteria:
- Calibration report computes κ (≥0.6 gate) + drift status from the judge readings
- Governance posture surfaces egress-deny-by-default, the three restricted roles, the tool allowlist, cost-per-verified-skill
- Rollback drill re-verified (publish → unpublish/quarantine → not discoverable)
- Docs: README + SECURITY + ADOPTION present
- `docker compose up -d db && pytest` all green
