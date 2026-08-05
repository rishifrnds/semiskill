<!--
Ephemeral right-now snapshot. OVERWRITE this file, never append.
Target length: under 40 lines. Full rules: see STATE_RULES.md.
-->

# STATUS — SemiSkill
_Last updated: 2026-08-05T14:07Z_

## Phase
Phase J: take the 84 authored DV skills through a REAL content gate (adversarial review -> fix ->
INDEPENDENT recheck -> REVIEW.json), publish them through the pipeline, and prove coverage of
16 roles x >=5 with a deterministic scoreboard.

## Session
- ID: 20260805T031906Z-Rishi_PC-f97e05
- Lock held: yes

## Right now
Tooling is unblocked and committed; the content gate is RUNNING. Batches 1-3 (36 skills) are in
flight through review -> fix -> independent recheck. Batches 4-7 (45 skills) are queued.

## Active step
- [J-003] content gate, 7 batches of 12 via tools/dv-gate.js (args: tools/gate_args.py).
  Batches 1,2,3 in flight. Nothing may publish until a skill's REVIEW.json says recheck.ready.

## Done this session (all verified, 454 tests green)
- [J-001] facet vocabulary learned the 3 registry roles it lacked (L019 10->0); it had been CAUSING
  the drift it existed to catch (5 skills remapped by their authors to get past it) — drift 5->0.
  C002 rescued from zero precision: 105 findings on the pack, all false; now 1, genuine.
- [J-002] dv-security-build-divergence-audit authored; security-verification-engineer 4/5 -> 5/5.
  Registry is 84 active cells and every one of the 16 roles is at >=5.
- [J-004 / ADR-011] skills/_shared/handoff-vocabulary.md is the signed field registry. The 10 C003
  "errors" were name COLLISIONS, not drift. C003 rescoped, C006-C012 added, 11 field + 2 value
  renames landed. Zero consistency errors pack-wide. C005 no longer contradicts the registry
  (205 -> 129). Measured: the only 7 enum names shared across skills are exactly the 7 registered.
- [J-005] the recheck gate is a PRECONDITION now, not a scoreboard report. `wave` refuses
  gate-missing / gate-not-ready per item before writing, --allow-ungated is recorded in the report,
  and the wave runs the pack check too. wave-plan currently refuses 81 of 84 — correct.

## Known gaps still open
- 81 skills still carry no independent recheck. 0 registry skills are published.
- 129 C005 + 4 C008 + 3 C011 + 1 C001 + 1 C002 warns: the authoring backlog the gate is closing.
- C008/C011 pack assertions are deliberately CEILINGS while the gate runs; tighten to `== set()`
  when it finishes.
- Never run `pytest` while an agent runs it — the shared dev DB fixture TRUNCATEs `artifacts` and
  both runs fail confusingly. Cost an hour of misdiagnosis this session.

## Last commit
- pending: J-001..J-005 tooling checkpoint (skills/ deliberately excluded, gate mid-run)
