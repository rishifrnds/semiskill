<!-- Ephemeral right-now snapshot; overwrite, never append. See STATE_RULES.md. -->

# STATUS - SemiSkill
_Last updated: 2026-08-10T09:45:36Z_

## Phase
Phase J: independently verify, approve and publish the 84 active DV skills to the DEVELOPMENT
catalog (ADR-029 — production/SharePoint is a separate, later milestone); prove 16 roles at >=5.

## Session
- ID: 20260808T165438Z-RISHI_PC-392cc5 - lock held: yes (same session, resumed after a real-world
  gap - `.session-lock` timestamp refreshed 2026-08-10T09:43:56Z; nothing else changed hands)
- Since the last checkpoint (J-010f4): user asked for the 84-skill role/level matrix (answered
  inline from HANDOFF.md data, no file changes) and then asked to consolidate this session's
  lessons into SKILL.md and docs/LEARNINGS.md (J-010f5, this checkpoint). No engineering work
  happened in between - the state below is otherwise identical to J-010f4.
- **BLK-003 is still ready for the user's decision** - the real Stage-2 scanner is built, wired
  in, and tested with real Docker execution. Nothing left but the user's sign-off. See BLOCKERS.md
  for the exact digest triple, or MEMORY.md's J-010f4 entry for full detail.

## Active step
- none in flight. Next: present the Stage-2 digest triple to the user (task #8) - or continue to
  task #9 (Stage-5 CLI wiring) if the user wants engineering to keep advancing while BLK-003
  awaits review; that path doesn't need their input yet either.

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
- Stage 5: adapter exists (J-010e10) but unwired into pipeline.py/wave.py yet, no calibration -
  BLK-004. Next engineering task if the user wants to keep moving without waiting on BLK-003.

## Immediate order
1. User decision needed: approve/reject the Stage-2 digest triple (BLK-003) - see BLOCKERS.md.
2. Independent of #1: wire `OllamaJudge`/`Stage5Policy` into `pipeline.py`/`wave.py` the same way
   Stage-2 was just wired; build + propose the 120-item calibration gold set (ADR-031 solo
   labeling); run calibration (BLK-004).
3. Once both blockers close: vertical-prove `dv-minimal-reproducer` end to end, then the 5-skill
   wave-0 cohort, then the remaining 79 in batches <=10.
4. Deferred, not urgent: scoreboard v3 artifact-reconciliation gap (task #6); full retirement of
   the old SecurityAuditScanner/npx runner once stage2_policy reaches CLI flags;
   `apply_migrations()`'s same-transaction enum bug (J-010f3).

## Active blockers
- BLK-001: narrowed to PRODUCTION-only scope; doesn't gate 84/84-to-development (ADR-029/J-010f3).
- BLK-003: code done and tested (J-010f4); needs the user's explicit digest-triple approval.
- BLK-004: Stage-5 needs CLI wiring, a real gold-set, and the user's solo calibration labeling.

## Full-suite status
Last full `pytest tests/` run: **1253 passed, 7 skipped, 0 failed, 365.35s** (J-010f4, this
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
- J-010f5 is the containing checkpoint for the SKILL.md/LEARNINGS.md documentation update
  (`artifacts: this J-010f5 checkpoint`).
- This session: J-010e7 -> e8 -> e9 -> e10 -> (pushed) -> f0 -> f1 -> f2 -> f3 -> f4 -> f5, all
  done, about to commit f5. Next: user decision on BLK-003, or continue to Stage-5 wiring.
- No step this session earns any review, approval, publication or launch-readiness credit yet -
  Stage 2 is code-proven but not yet approved; nothing has reached security_pass.
