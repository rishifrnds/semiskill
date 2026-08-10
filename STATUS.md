<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-10T10:59:09Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills to the DEVELOPMENT
catalog (ADR-029 — production/SharePoint is a separate, later milestone); prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes (same session, resumed after a real-world
  gap - `.session-lock` timestamp refreshed 2026-08-10T09:43:56Z; nothing else changed hands)
- User asked for the 84-skill role/level matrix (answered inline, no files), then to consolidate
  lessons into SKILL.md/LEARNINGS.md (J-010f5), then to continue Stage-5 wiring while they review
  BLK-003, plus an interactive decision page (this checkpoint covers Stage-5 wiring; the page is
  next, not yet built as of this write).
- **BLK-003 still awaits the user's decision** (Stage-2 digest triple, unchanged since J-010f4).
- **Stage-5 wiring is now also DONE** (J-010f6) - proven against the REAL local Ollama daemon,
  which is genuinely still wildcard-bound (checked via `netstat`, not assumed stale). BLK-004
  still needs the real calibration corpus + the user's labeling.

## Active step
- none in flight. Next: build the interactive HTML decision page the user asked for, then propose
  the 120-item calibration gold set (task #10) once there's a channel for the user to review it.

## J-010f4 result: real Stage-2 scanner built, wired, and proven (done, awaiting BLK-003 approval)
- `docker/stage2/rules/semiskill.yml`: 9 real Semgrep rules (dangerous command execution, data
  exfiltration, prompt-injection phrases, disabling this project's own safety tooling) -
  deliberately complementary to stage 3 (held-out injection corpus) and stage 4 (credential
  regexes), not a duplicate.
- `semiskill/scanners/stage2_engine.py`: the real `docker run` engine, hardened
  (`--network none --read-only --cap-drop ALL --security-opt no-new-privileges --user semgrep`),
  verified working (not assumed) - found and fixed two real Docker/Semgrep gotchas along the way
  (writable `$HOME` needed even read-only; `--metrics=off --disable-version-check` needed or it
  hangs trying to phone home with no network) and one real Semgrep behavior (`check_id` gets a
  `rules.` prefix from the `--config` mount's parent directory name - normalized in `_rule_id()`).
- `Stage2Adapter` now wired into `pipeline.py`/`wave.py` via a new optional `stage2_policy`
  parameter - additive, not a breaking change (omitting it behaves exactly as before).
- Proven end to end with REAL Docker execution, not mocks: a benign skill scans clean with exact
  coverage; a `curl ... | bash` skill body gets a real `critical` finding and correctly hard-fails
  the pipeline. Full `pytest tests/`: **1253 passed, 7 skipped, 0 failed, 365.35s**.
- **Exact digest triple, ready for the user's review** (also in BLOCKERS.md BLK-003):
  - `image_manifest_digest = sha256:2e01772afbd85789464594ca86e22896748cbc78a5d9751dfc947a40b214ccc2`
    (upstream `semgrep/semgrep@<digest>` used directly - no local derivative build)
  - `rule_pack_sha256 = sha256:81a5e721b1ce52c9e165c1d35696f7a1df38d2351a1f939b0418f7251a3844e1`
  - `adapter_commit = a9833db0a3681b66765df0fbc28b49e225bded0e`
- No production/real policy config sets `approved=True` anywhere - only test fixtures do. BLK-003
  stays open until the user explicitly says so.

## TWO blockers still hold every skill at the scan gate, not one
- Stage 2: CODE DONE (J-010f4), awaiting user approval - BLK-003.
- Stage 5: CODE DONE and wired (J-010f6), proven against the real (still wildcard-bound) local
  Ollama daemon. BLK-004 remains open - needs the real 120-item gold set + the user's labeling.

## Immediate order
1. User decision needed: approve/reject the Stage-2 digest triple (BLK-003) - see BLOCKERS.md.
2. Build + propose the 120-item calibration gold set for the user's solo labeling (ADR-031), then
   run calibration once labeled (BLK-004). Stage-5 code wiring itself is done (J-010f6).
3. Once both blockers close: vertical-prove `dv-minimal-reproducer` end to end, then the 5-skill
   wave-0 cohort, then the remaining 79 in batches <=10.
4. Deferred, not urgent: scoreboard v3 artifact-reconciliation gap (task #6); full retirement of
   the old SecurityAuditScanner/npx runner once stage2_policy/stage5_policy reach CLI flags;
   `apply_migrations()`'s same-transaction enum bug (J-010f3); optionally reconfigure local
   Ollama to loopback-only if the user wants a full successful round-trip proof, not just refusal.

## Active blockers
- BLK-001: narrowed to PRODUCTION-only scope; doesn't gate 84/84-to-development (ADR-029/J-010f3).
- BLK-003: code done and tested (J-010f4); needs the user's explicit digest-triple approval.
- BLK-004: code done and wired (J-010f6); needs a real gold-set and the user's solo labeling.

## Full-suite status
Last full `pytest tests/` run: **1261 passed, 7 skipped, 0 failed, 373.04s** (J-010f6, this
session, TEST_DATABASE_URL only per ADR-032). Current, trustworthy baseline.
Last IMMUTABLE (clean-source) full-suite PASS record remains `a6792604...` on source `28379ab`
(J-010e6) - source has changed many times since; generate a fresh one before treating it as
evidence for a release gate.

## Standing hazards
- Never run database tests concurrently; use only the explicit isolated `_test` database.
- **Run pytest with ONLY `TEST_DATABASE_URL` exported, never the full `.env`** (ADR-032/J-010f3).
- Local Postgres is TWO docker-compose services: `db` (5432, real catalog) and `db-test` (5433,
  pytest only, fully disposable).
- Docker Desktop is not guaranteed running at session start on this machine - check `docker ps`.
  Two images now matter: the dev Postgres containers AND the pinned Stage-2 Semgrep image
  (`docker image inspect semgrep/semgrep@sha256:2e01772...` - see BLK-003 for the full digest).
  `@pytest.mark.docker` tests skip gracefully (not fail) when either is unavailable.
- On Windows/Git-Bash, `docker run -v`/`-w` arguments get mangled by MSYS path conversion unless
  prefixed with `MSYS_NO_PATHCONV=1`, and bind-mount SOURCE paths must be real Windows paths
  (`C:/Users/...`), not Git-Bash's internal `/tmp` alias, which Docker Desktop can't see.
- A state file (STATUS.md) can itself become corrupted by a runaway append - verify its size.
- Shared dependencies changed all 84 full payload hashes, so historical reviews credit none.
- `84/84 lint clean` is a SECURITY score and says nothing about whether the DV content is correct.
- Scoreboard v2's cell-level claims are not independently re-verified against live artifacts
  (deferred task #6) - do not treat a v2 snapshot as authoritative beyond source drift.
- The development store contains a test-fixture `skill_version` (`dv/cve`). Append-only means it
  stays; every count must exclude unregistered slugs explicitly rather than assuming 1:1.
- Any "published"/"security_pass" claim from this point MUST say "development catalog" and cite
  ADR-030/031's explicit rigor caveats once Stage-2/5 are actually approved - never bare
  "published" or "passed" without that context (ADR-029/030/031).

## Last checkpoint
- J-010f6 is the containing checkpoint for the Stage-5 wiring
  (`artifacts: this J-010f6 checkpoint`).
- This session: J-010e7 -> e8 -> e9 -> e10 -> (pushed) -> f0 -> f1 -> f2 -> f3 -> f4 -> f5 -> f6, all
  done, about to commit f6. Next: build the interactive decision page, then BLK-004's gold set.
- No step this session earns any review, approval, publication or launch-readiness credit yet -
  Stage 2 and Stage 5 are both code-proven but not yet approved; nothing has reached security_pass.
