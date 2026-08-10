<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-10T14:31:07Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills to the DEVELOPMENT
catalog (ADR-029 — production/SharePoint is a separate, later milestone); prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes (`.session-lock` refreshed 2026-08-10T14:26:38Z)
- **For the full picture, read `HANDOFF.md` — it was comprehensively rewritten this checkpoint
  (J-010f7) and is now the primary reference, not this file.** STATUS.md stays deliberately lean
  from here on; don't let it re-accumulate into a second handoff.

## Active step
- none in flight. This session's work is checkpointed through J-010f7 (documentation wrap-up).
  Next real engineering: task #10 (build the 120-item calibration gold set) once time allows, or
  whatever the user's BLK-003/Ollama decisions (see HANDOFF.md "Pending decisions") direct.

## Right now, in one paragraph
Stage 2 and Stage 5 are both CODE-COMPLETE and proven with real execution (real Docker, the real
local Ollama daemon) — not mocks. Both are blocked on exactly one thing each: BLK-003 needs the
user's sign-off on an already-built exact digest triple; BLK-004 needs a real 120-item calibration
corpus (not yet built) plus the user's solo labeling. An interactive decision page was published
for BLK-003 + one small Ollama-reconfiguration question; the user has not yet reported a decision
back into this thread. Full suite: 1261 passed, 7 skipped, 0 failed (J-010f6, dirty-tree — no
fresh immutable clean-source record since 10 commits ago; generate one before any release gate).

## Standing hazards (durable — HANDOFF.md repeats these too, kept here for a quick scan)
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- **Run pytest with ONLY `TEST_DATABASE_URL` exported, never the full `.env`** (ADR-032).
- Local Postgres is TWO docker-compose services: `db` (5432, real catalog, never recreate its
  container without checking) and `db-test` (5433, pytest only, fully disposable).
- Docker Desktop is not guaranteed running at session start on this machine - check `docker ps`
  for BOTH containers, and `docker image inspect` for the pinned Stage-2 image if
  `@pytest.mark.docker` tests matter (they skip gracefully, not fail, when it's missing).
- On Windows/Git-Bash, `docker run -v`/`-w` args need `MSYS_NO_PATHCONV=1`, and bind-mount SOURCE
  paths must be real Windows paths (`C:/Users/...`), not Git-Bash's `/tmp` alias.
- A state file (STATUS.md) can itself become corrupted by a runaway append - verify its size.
- Any "published"/"security_pass" claim MUST say "development catalog" and cite ADR-030/031's
  explicit rigor caveats once Stage-2/5 are approved - never bare "published" or "passed".

## Last checkpoint
- J-010f7 is the containing checkpoint for this session's documentation wrap-up
  (`artifacts: this J-010f7 checkpoint`).
- This session: J-010e7 -> e8 -> e9 -> e10 -> (pushed) -> f0 -> f1 -> f2 -> f3 -> f4 -> f5 -> f6 ->
  f7, all done. HANDOFF.md, SKILL.md and LEARNINGS.md all refreshed to match.
- No step this session earns any review, approval, publication or launch-readiness credit yet -
  Stage 2 and Stage 5 are both code-proven but not yet approved; nothing has reached security_pass.
