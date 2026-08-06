<!--
Ephemeral right-now snapshot. OVERWRITE this file, never append.
Target length: under 40 lines. Full rules: see STATE_RULES.md.
-->

# STATUS — SemiSkill
_Last updated: 2026-08-06T00:05Z_

## Phase
Phase J: 84 authored DV skills through a REAL content gate (adversarial review -> fix -> INDEPENDENT
recheck -> REVIEW.json), then publish and prove 16 roles x >=5 on the scoreboard.

## Session
- ID: 20260805T031906Z-Rishi_PC-f97e05 · lock held: yes
- **Execution delegated to another model (GLM) to conserve tokens.** This session's role is now
  review and quality control. Procedure: `docs/WORKFLOW.md`. Prompts: `docs/PROMPT_LIBRARY.md`.
- Three round-2 workflows were launched and STOPPED on request. 3 skills carry partial fix edits
  (dv-compute-license-efficiency, dv-emulation-dump-strategy, dv-uvm-agent-checker) — all three
  still lint 1.000, and no gate record was written for them, so they correctly remain not-ready.

## Gate state — measured from REVIEW.json on disk, not from any claim
- ready **3** · not-ready with real findings **32** · never-reviewed **49** · **published 0**
- 0 of 44 skills that completed a full first pass were judged ready. The findings are genuine; the
  round-1 verdict was also uncalibrated (nits counted as blockers), which `tools/dv-gate2.js` fixes.

## Health
- 84/84 lint `approve 1.000` · **zero pack-consistency errors** · 456 tests green
- Consistency warns 60: C005 54, C002 3, C008 2, C001 1 (the authoring backlog the gate is closing)
- Registry: 84 active cells, every one of the 16 roles at >=5

## Done since the last commit
- `docs/AUTHORING_CONTRACT.md` — the project skill, extracted from three inline copies in
  tools/dv-{wave,gate,gate2}.js, which now point at it. Caught while doing it: the pointer paths
  were Windows backslashes inside a JS template literal, where \c \V \s \d collapse — every path
  would have rendered as "E:codeVLSIsemiskilldocs...". Forward slashes now; all three parse.
- `docs/LEARNINGS.md` — why each rule exists, the four representative content defects, and a table
  of every mechanism here that can record something that did not happen.
- `HANDOFF.md` — resume prompt, ordered pending list, full known-gaps list.
- CLAUDE.md current phase corrected (said Phase 0) and pointed at the three docs above.

## Next, in order
1. `tools/dv-gate2.js` over the 32 not-ready (args: `python tools/gate2_args.py --emit`)
2. `tools/dv-gate.js` over the 49 never-reviewed (args: `python tools/gate_args.py --batch N --size 12`)
3. `collect_wave.py` + re-run `check_pack` after EVERY batch — fix agents introduce defects
4. `semiskill wave skills/ --yes` -> `scoreboard --strict-gate` -> `site` -> `pack`

## Standing hazards
- Max **3** gate workflows concurrently; 4+ exhausted the token limit mid-flight.
- Never run `pytest` while an agent runs it (shared dev DB fixture TRUNCATEs `artifacts`).

## Last commit
- 1ea933c. This checkpoint adds the contract, learnings, handoff and CLAUDE.md fix.
