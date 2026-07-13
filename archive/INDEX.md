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

<!-- Entry format after first rotation:

- MEMORY-P1.md — Phase 1: <phase name>
  - Timespan: <first-step ISO timestamp> → <last-step ISO timestamp>
  - STEP-IDs: P1-001 → P1-<NNN>
  - Step count: <N> done, <M> abandoned, <K> rolled-back
  - Exit criterion met: <which criterion from MEMORY.md triggered rotation>
-->

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
