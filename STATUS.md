<!--
Ephemeral right-now snapshot. OVERWRITE this file, never append.
Target length: under 40 lines. Full rules: see STATE_RULES.md.
-->

# STATUS — SemiSkill
_Last updated: 2026-08-05T06:40Z_

## Session
- ID: 20260805T031906Z-Rishi_PC-f97e05
- Started: 2026-08-05
- Host: Rishi_PC
- Lock held: yes (.session-lock taken over 2026-08-05T03:19Z from stale
  20260713T024006Z-Rishi_PC-2a55fa, ~3 weeks past the 2h window — user approved takeover in the
  Phase H plan)
- Session goal: Phase H — make the catalog reach a real DV team (Cursor pack + SharePoint page).

## Right now
Phases A–G complete (183 tests), dashboard committed, Phase G archived. Now in
**Phase H**: author a validated first wave of DV skills and deliver them as an Agent-Skills pack a
Cursor user can install, plus a SharePoint-native catalog page.

Plan: `C:\Users\rishi\.claude\plans\the-problem-statement-is-generic-llama.md` (approved 2026-08-05).

## Active step
- Step ID: H-020 (done) — browsable catalog page generated from the published catalog
- Sub-state: CONTENT IS NOT SET-READY. 2 of 6 shippable; see "Content status" below
- Started: 2026-08-05T03:19Z

## Last commit
- SHA: 1c16c85
- Message: wip: H-014b content remediation r2
- Time: 2026-08-05

## Two findings that reshape the work (verified 2026-08-05)
- **Cursor 2.4+ supports Agent Skills natively** (`.cursor/skills/`, `~/.cursor/skills/`, legacy
  `.claude/skills/`). Install = file placement. BUT `name` must be kebab-case and match the folder —
  so **none of the 8 published seeds would load in Cursor** (`name: RTL Onboarding for Freshers`,
  `slug: dv/rtl-onboarding-fresher`). ADR-008 fixes this.
- **SharePoint downloads `.html` but renders `.md` natively** (Apr–May 2026). The deliverable is a
  Markdown pack + a native Site Page, not the Next.js app (which cannot build) or `catalog-demo.html`.

## Content status — DO NOT ship the pack to a team yet
An adversarial review of the six wave-1 skills returned "not ready to publish as a set", twice.
Round-2 fixes landed (all 6 at lint 1.000, re-published, re-packed), but the re-review still says no.
- READY: dv-ral-bringup, dv-regression-triage-routing
- NEEDS WORK: dv-repo-orientation (weakest — step 1 still exceeds its own Glob cap; step 2 reads a
  doc/ directory step 1 no longer locates), dv-build-filelist-hygiene (two step-6 audits cannot obey
  its own one-directory rule), dv-minimal-reproducer (revert trigger unmeasurable at its own scale)
- SET-LEVEL: slot count 44 -> 50 and _shared/retrieval-budget.md was never created, so the budget
  block is still duplicated 6x with the same magic numbers; repo-orientation lost the shared
  200-Grep-hit guard; two ral-bringup gotchas lost their sharpest closing lines in the rewrite
- The lesson worth keeping: lint 1.000 is a SECURITY score. It says nothing about whether the DV
  content is correct, and the two rounds above are what that distinction costs.

## Known gaps (unchanged; each needs an external resource)
Stage-2 live security-audit (egress sandbox), stage-5 live judge (API keys), pgvector, SharePoint
tenant. Plus: no auth, nothing deployed, no CI, no backups.

## If resumed
Read MEMORY.md (Phase H) and the approved plan above. DB: `docker compose up -d db` (127.0.0.1).
Tests: `pytest` (329, Docker PG running). Nothing pushed to remote.
