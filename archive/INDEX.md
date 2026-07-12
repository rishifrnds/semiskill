<!--
Tiny index of what lives in each archive file. Updated on every rotation.
Full rules (including field-derivation at rotation time): see STATE_RULES.md.

Archives themselves are FROZEN — never edited. Corrections to an archived
entry go in the ACTIVE MEMORY.md as a `status: correction` entry.
-->

# Archive Index
_Last updated: <YYYY-MM-DD>_

## MEMORY archives (phase-based)
_No phase rotations yet._

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
