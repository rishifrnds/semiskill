<!--
Tiny index of what lives in each archive file. Updated on every rotation.
Full rules (including field-derivation at rotation time): see STATE_RULES.md.

Archives themselves are FROZEN — never edited. Corrections to an archived
entry go in the ACTIVE MEMORY.md as a `status: correction` entry.
-->

# Archive Index
_Last updated: 2026-07-13_

## MEMORY archives (phase-based)

- MEMORY-P0.md — Phase 0: Foundation & Plan
  - Timespan: 2026-07-13 → 2026-07-13
  - STEP-IDs: P0-001 → P0-003
  - Step count: 3 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: ULTRA_PLAN_PROMPT.md reviewed by user and build plan approved (2026-07-13)

- MEMORY-A.md — Phase A: Foundation & Schema (L2 substrate)
  - Timespan: 2026-07-13T02:45Z → 2026-07-13T03:45Z
  - STEP-IDs: A-001 → A-008
  - Step count: 8 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: `pytest` 21 green vs live Postgres (schema round-trips, corrections append-not-update, no-published-without-approval gate, semiskill_app blocked from direct reads)

- MEMORY-B.md — Phase B: Capture + Context (L1/L3)
  - Timespan: 2026-07-13T04:05Z → 2026-07-13T04:50Z
  - STEP-IDs: B-001 → B-008
  - Step count: 8 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: `pytest` 59 green — need-to-know invisible to unauthorized, catalog published-only, lineage+reuse ACL-pruned, facet/text search

- MEMORY-C.md — Phase C: Security-Verification Pipeline (L4/L6)
  - Timespan: 2026-07-13T05:00Z → 2026-07-13T06:50Z
  - STEP-IDs: C-001 → C-012 (incl. C-011b)
  - Step count: 13 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: `pytest` 146 green — 6-stage pipeline, gated publish, held-out corpus unreadable by pipeline role, red-team zero escapes (battery + 7 novel LLM-crafted attacks)

- MEMORY-D.md — Phase D: Intelligence Controller (L5)
  - Timespan: 2026-07-13T07:00Z → 2026-07-13T07:20Z
  - STEP-IDs: D-001 → D-004
  - Step count: 4 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: `pytest` 171 green — six-control stability gate (no oscillation), model routing + cost-per-verified-skill, review-queue ranking, drift-blocks-auto-act

- MEMORY-E.md — Phase E: SharePoint hosting + Catalog UI
  - Timespan: 2026-07-13T07:35Z → 2026-07-13T07:55Z
  - STEP-IDs: E-001 → E-003
  - Step count: 3 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: `pytest` 176 green — stdlib read API (ACL-filtered catalog + verification badge), demonstrable catalog UI Artifact, Next.js production scaffold

- MEMORY-F.md — Phase F: Governance hardening & docs
  - Timespan: 2026-07-13T08:05Z → 2026-07-13T08:10Z
  - STEP-IDs: F-001 → F-003
  - Step count: 3 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: `pytest` 180 green — calibration/κ report + governance posture, rollback drill re-verified, README/SECURITY/ADOPTION docs

<!-- Entry format after first rotation:

- MEMORY-P1.md — Phase 1: <phase name>
  - Timespan: <first-step ISO timestamp> → <last-step ISO timestamp>
  - STEP-IDs: P1-001 → P1-<NNN>
  - Step count: <N> done, <M> abandoned, <K> rolled-back
  - Exit criterion met: <which criterion from MEMORY.md triggered rotation>
-->

- MEMORY-G.md — Phase G: Seed the catalog with role-based skills (dogfood the pipeline)
  - Timespan: 2026-07-13T08:20Z → 2026-08-05T03:19Z
  - STEP-IDs: G-001 → G-006
  - Step count: 6 done, 0 abandoned, 0 rolled-back
  - Exit criterion met: every published seed reached the catalog via a passing scan_run + approval (no
    back-door), a deliberately-broken seed blocked identically, catalog faceted by function/role/level,
    183 tests green; plus `scripts/demo.py` and the `dashboard/` command centre

## DECISIONS archives (quarterly)
_No quarterly rotations yet._

<!-- Entry format after first rotation:

- DECISIONS-2026-Q1.md — <start date> → <end date>
  - ADR range: ADR-<first> → ADR-<last>
  - ADR count: <total>, of which <n> superseded
-->

## Cross-archive references
_None yet._

<!-- Populate only for frequently-referenced entries (optional):

- ADR-007 (auth scheme) → archived in DECISIONS-2026-Q1.md
- STEP P1-042 (initial migration) → archived in MEMORY-P1.md
-->
