<!--
Ephemeral right-now snapshot. OVERWRITE this file, never append.
Target length: under 40 lines. Full rules: see STATE_RULES.md.
-->

# STATUS — SemiSkill
_Last updated: 2026-08-05T03:19Z_

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
- Step ID: H-000 (done) — lock taken over, dashboard committed, Phase G archived
- Sub-state: Phase H started; next H-001 (ADR-008)
- Started: 2026-08-05T03:19Z

## Last commit
- SHA: 3a07124
- Message: wip: G-006 dashboard command centre
- Time: 2026-08-05

## Two findings that reshape the work (verified 2026-08-05)
- **Cursor 2.4+ supports Agent Skills natively** (`.cursor/skills/`, `~/.cursor/skills/`, legacy
  `.claude/skills/`). Install = file placement. BUT `name` must be kebab-case and match the folder —
  so **none of the 8 published seeds would load in Cursor** (`name: RTL Onboarding for Freshers`,
  `slug: dv/rtl-onboarding-fresher`). ADR-008 fixes this.
- **SharePoint downloads `.html` but renders `.md` natively** (Apr–May 2026). The deliverable is a
  Markdown pack + a native Site Page, not the Next.js app (which cannot build) or `catalog-demo.html`.

## Known gaps (unchanged; each needs an external resource)
Stage-2 live security-audit (egress sandbox), stage-5 live judge (API keys), pgvector, SharePoint
tenant. Plus: no auth, nothing deployed, no CI, no backups.

## If resumed
Read MEMORY.md (Phase H) and the approved plan above. DB: `docker compose up -d db` (127.0.0.1).
Tests: `pytest` (183). Nothing pushed to remote.
