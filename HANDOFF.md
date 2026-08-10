# SemiSkill project handoff

_Updated: 2026-08-10 UTC. Scope: the existing 84 active DV skills only. The 20 declined registry
candidates remain non-crediting provenance; the proposed 19-level expansion is deferred._

## Executive verdict

**Launch status: NO-GO**, but the shape of "why" changed completely across 2026-08-08 → 2026-08-10.
All 84 skill directories exist and pass strict authoring lint; **0/84 currently have a complete,
current, canonical security + independent-review + human-approval + publication chain.** What
changed: the near-term milestone itself was rescoped (ADR-029 — the "84 published" target is the
**internal development catalog**, not SharePoint/production, which has zero integration code and
was never going to be reachable soon), and **both remaining code blockers are now actually built,
wired, and proven** — not just designed. Stage 2 (a real Semgrep scanner) and Stage 5 (a real
Ollama-backed judge) both exist, are wired into `pipeline.py`/`wave.py`, and were proven end to end
with real execution (real Docker containers, the real local Ollama daemon) rather than mocks. Both
are now blocked on exactly one thing each, and neither is more engineering:

- **BLK-003** (Stage 2): needs the user's explicit sign-off on an exact, already-built digest triple.
- **BLK-004** (Stage 5): needs a real 120-item calibration corpus (not yet built) and then the
  user's solo blind-labeling of it (already agreed to be solo, ADR-031).

An **interactive decision page** was published this session for the user to review and mark BLK-003
(and one small related question) — see "Pending decisions" below. As of this handoff, the user has
not yet reported back their decisions from that page into this thread.

The next legitimate milestones, in order: close BLK-003 (a review, not new work) → build and hand
off the Stage-5 calibration corpus → vertically prove one skill end to end against the now-real
gates → expand to five, then the remaining 79 in batches of ≤10.

Use the repository skill at `.agents/skills/semiskill-project/SKILL.md` to resume work. It routes
all state, gate, review, and release tasks through this file and `STATE_RULES.md`. **Read
DECISIONS.md's ADR-029 through ADR-032 before anything else in this file** — they rescope what
"done" means and this file's prose assumes them throughout.

## One-screen command centre truth

| Measure | Current | Near-term target | Authority |
|---|---:|---:|---|
| Active registry skills | 84 | 84 | `specs/skill_registry.json` |
| Declined provenance records | 20 | 20 | registry, non-crediting |
| Roles represented | 16 | 16 | registry |
| Roles with at least 5 authored skills | 16 | 16 | registry + filesystem |
| Authored skill directories | 84 | 84 | `skills/*/SKILL.md` |
| Strict-lint pass | 84 | 84 | deterministic authoring lint |
| Pack consistency errors | 0 | 0 | deterministic pack check |
| Pack consistency warnings | 60 | reviewed/disposed | non-blocking until classified |
| **Stage-2 scanner: code** | **DONE, tested with real Docker execution** | approved | J-010f4, `docker/stage2/` |
| **Stage-2 scanner: approval** | **awaiting user (BLK-003)** | approved | see exact digest triple below |
| **Stage-5 judge: code** | **DONE, wired, proven against real Ollama** | calibrated | J-010f6 |
| **Stage-5 judge: calibration** | **not started (BLK-004)** | 120-item corpus + solo labels | ADR-031 |
| **`review-issue` CLI command** | **DONE** | — | J-010f2, `semiskill review-issue` |
| **Local dev DB identities (approval/review/export)** | **DONE, verified, on a dedicated cluster** | — | J-010f1/f3, ADR-032 |
| Security-complete current payloads | 0 | 84 (development catalog) | canonical artifacts |
| Canonically reviewed | 0 | 84 | exact-hash append-only reviews |
| Recheck-ready | 0 | 84 | deterministic zero-open-blocker gate |
| Authenticated human-approved | 0 | 84 | exact-evidence approval projection |
| Projection-backed published (**development catalog**, ADR-029) | 0 | 84 | catalog projection |
| Projection-backed published (production/SharePoint) | 0 | out of near-term scope | BLK-001, narrowed |
| Development DB schema | 0023, verified | 0023 before review issuance | `schema_migrations`, `db` cluster |
| Test DB schema | 0023 | current | **own cluster since ADR-032** (`db-test`, port 5433) |
| Full test suite (dirty-tree, this session) | **1261 passed, 7 skipped, 0 failed** | green | J-010f6, 2026-08-10 |
| Last IMMUTABLE clean-source full-suite PASS | `a6792604...` on `28379ab` — **10 commits stale** | fresh before any release gate | J-010e6 |
| Market launch | NO-GO | all release invariants true (development catalog) | canonical release gate only |

## Pending decisions — an interactive page exists for this

An HTML decision page was published this session (via the Artifacts feature) so the user can review
evidence and mark calls without digging through files. **It has no live connection back to this
repo or to Claude** — the user must paste its "copy my decisions" summary back into the chat for
anything to actually happen. As of this handoff, that summary has not yet been pasted back.

Open items on that page (mirrors this file exactly, nothing on the page is independent of it):

1. **BLK-003** — approve/reject the Stage-2 digest triple (below).
2. **Small, live-system question** — reconfigure the local Ollama daemon to loopback-only
   (`OLLAMA_HOST=127.0.0.1`)? It is currently wildcard-bound (`0.0.0.0:11434`/`[::]:11434`,
   confirmed via `netstat` on 2026-08-10, not assumed stale). Reconfiguring would let Stage-5
   complete a full successful round-trip proof instead of only the refusal-path proof it has
   today. This changes a real running service outside the repo, hence asking first.

If the user reports a decision in a fresh session without the page in front of them, both items
above are still exactly reproducible from this file — nothing on the page is the only copy of
anything.

## Exact Stage-2 digest triple (BLK-003, awaiting approval)

```
image_manifest_digest = sha256:2e01772afbd85789464594ca86e22896748cbc78a5d9751dfc947a40b214ccc2
rule_pack_sha256       = sha256:81a5e721b1ce52c9e165c1d35696f7a1df38d2351a1f939b0418f7251a3844e1
adapter_commit          = a9833db0a3681b66765df0fbc28b49e225bded0e
```

- `image_manifest_digest` is the **upstream** `semgrep/semgrep` image, referenced directly by exact
  platform-manifest digest — there is no locally-built derivative to trust; anyone can
  `docker pull semgrep/semgrep@<digest>` and get byte-identical bits. Confirmed non-root
  (`semgrep` user by default), confirmed it needs `--disable-version-check --metrics=off` or it
  hangs trying to phone home under `--network none`.
- `rule_pack_sha256` is `docker/stage2/rules/semiskill.yml` — 9 rules, real detection content, not
  a placeholder. Read the file directly; it's short. Categories: dangerous command execution
  (pipe-to-shell, base64-decode-execute, reverse-shell shape, destructive `rm -rf`), data
  exfiltration (HTTP POST of file/env contents), prompt-injection phrasing (deliberate
  defense-in-depth overlap with stage 3's held-out corpus probe), and disabling this project's own
  safety tooling (`--no-verify` etc.). Deliberately does not duplicate stage 4's credential-format
  regexes (already covered in `secret_pii.py`).
- `adapter_commit` is the repo HEAD at the time this triple was minted (J-010f4).
- Approving this means setting `Stage2Policy.approved=True` in real (non-test) usage somewhere —
  that flip has NOT happened anywhere outside test fixtures. **Explicitly deferred, not silently
  skipped** (ADR-030): cosign/sigstore image signing, automated SBOM/CVE scanning, formal
  legal/license review. Revisit before any production/external launch.
- Proof this triple actually works: `tests/scanners/test_stage2_engine.py` (19 tests, 5 of them
  real Docker invocations) and `tests/spine/test_pipeline.py` (3 stage2 tests) — a benign skill
  scans clean with exact file coverage; a `curl ... | bash` skill body gets a real `critical`
  finding and correctly hard-fails the pipeline.

## Session log: 2026-08-08 → 2026-08-10 (this handoff's authors)

Everything below happened after the 2026-08-07 handoff (preserved history further down). Commits
`27f14ec` through `d101818` on `main`, all pushed, `origin/main` verified equal to local `HEAD`
after each push.

- **J-010e7** — resumed after a session gap; found and repaired real state corruption: `STATUS.md`
  had grown from 9.5 KB to 8.4 MB via a runaway append (already committed to HEAD), and
  `MEMORY.md`'s `Pending Steps` list was stale (named six already-done STEP-IDs as pending, which
  had camouflaged one genuinely-undone item, `tools/issue_batch.py` review). Took over a stale
  `.session-lock` with the user's explicit approval first.
- **J-010e8** — `PostgresArtifactStore` pooled connections per-DSN (`ADR-027`), fixing the Windows
  ephemeral-port-exhaustion flake from the prior session.
- **J-010e9** — reviewed the inherited, previously-untested `tools/issue_batch.py`; found and fixed
  a real path-containment defect (`_verify_snapshot_freshness` let an untrusted snapshot field
  escape `repo_root` via an absolute path or `..` traversal — an arbitrary local file-read
  primitive). 5 adversarial tests added.
- **J-010e10** — built the Stage-5 Ollama loopback judge adapter (`ADR-028`):
  `semiskill/scanners/stage5_ollama.py` (`Stage5Policy`, `OllamaJudge`, `Stage5Refused`), fail-closed
  on unapproved/non-loopback/model-digest-mismatch/malformed-response. Along the way found and
  fixed a real pre-existing gap: `JudgeRiskScanner.scan()` had no `try/except` around
  `self.judge.score(...)`, so any real network-backed judge would have crashed the whole pipeline
  on a transport error instead of degrading to `judge-skipped` like `JudgeUncalibrated` already did.
- **User asked to "continue till all 84 published," then chose (via AskUserQuestion) how to scope
  the remaining blockers** — recorded as three ADRs:
  - **ADR-029**: the near-term "published" target is the development catalog, not SharePoint —
    traced the actual code and found SharePoint publication is 100% "generate static files, a
    human uploads them manually," zero Graph/SharePoint API integration exists anywhere.
  - **ADR-030**: BLK-003 resolved with pragmatic rigor for this internal/solo project — exact
    pinned digest + real rule pack + wired in, but formal signing/SBOM/CVE automation deferred.
  - **ADR-031**: BLK-004 resolved via solo calibration labeling by the user, recorded as an
    explicit, real deviation from the two-independent-labeler design, not presented as satisfying
    the original protocol.
- **J-010f1** — provisioned three local Postgres logins (approval-actuator/review-coordinator/
  export-reader identities) for the development catalog chain to work outside the isolated test DB.
- **J-010f2/f3** — wired the `review-issue` CLI command (moved orchestration from the unpackaged
  `tools/` tree into importable `semiskill/authoring/issue_batch.py`), then **found and fixed two
  real regressions** the DB-role provisioning had silently caused, both caught only by running the
  FULL test suite before checkpointing "done" (not by the identity-method spot-checks that seemed
  sufficient): (1) Postgres roles are cluster-wide, not per-database — the new logins broke
  migration-checkpoint attestation tests that assert an exact role/membership set for the
  cluster hosting `semiskill_test`; (2) once fixed by splitting Postgres into two docker-compose
  clusters, a second, unrelated regression surfaced — sourcing the full `.env` before running
  pytest silently redirected test-database stores' actuator calls to the real catalog. **ADR-032**
  documents the full diagnosis and formally corrects ADR-029's wrong "10-minute, zero-risk"
  characterization of the original provisioning.
- **J-010f4** — built the actual Stage-2 scanner (rule pack + `docker run` engine + pipeline
  wiring) and proved it end to end with real Docker execution. Exact digest triple above.
- **J-010f5** — at the user's request, consolidated this session's hard-won lessons into
  `.agents/skills/semiskill-project/SKILL.md` and `docs/LEARNINGS.md`.
- **J-010f6** — wired `OllamaJudge`/`Stage5Policy` into `pipeline.py`/`wave.py` (mirroring
  `stage2_policy`'s pattern exactly) while the user reviewed the Stage-2 digest in parallel. Proved
  the wiring against the REAL local Ollama daemon (confirmed still wildcard-bound via `netstat`,
  not assumed) — it correctly refuses rather than scoring anything.
- **This turn** — published the interactive decision page (see "Pending decisions" above), then
  refreshed this file, `MEMORY.md`, `STATUS.md`, `BLOCKERS.md`, the project skill, and
  `docs/LEARNINGS.md` at the user's request, and produced a resume prompt for a fresh terminal
  (bottom of this file).

Full detail for every step above lives in `MEMORY.md`'s J-010e7 through J-010f6 entries — this
section is a summary, not a replacement.

## Exact platform proof

The 2026-08-07 immutable full-suite record is now **10 commits stale** — do not treat it as current
evidence for anything:

- Run ID: `a6792604-42ec-4111-a801-b55de5a43669`
- Source commit: `28379ab` (`clean: true`)
- Result: 1198 collected, 1191 passed, 7 skipped, 0 failed
- Database: exact isolated `semiskill_test`, migration 0023 (on the OLD single-cluster topology,
  before ADR-032's split — the isolated database it ran against no longer exists in that form)

This session's own full-suite runs were all **dirty-tree** (uncommitted-at-test-time or simply
never re-run on a clean checkout after committing), so none of them supersede the record above as
*immutable* evidence, even though they're more current in every practical sense:

- **1261 passed, 7 skipped, 0 failed, 373.04s** — J-010f6, 2026-08-10, `TEST_DATABASE_URL` only
  against the new `db-test` cluster (ADR-032). This is the right number to trust for "is the
  platform healthy," not for "is this the source-bound immutable proof a release gate needs."

**Generate a fresh immutable full-suite PASS before any migration plan or release checkpoint** —
Gate 0 below.

## The complete 84-skill catalog inventory

Every item below is **authored + strict-lint-pass, but not canonically approved or published**.
Unchanged since 2026-08-07 — no skill content was touched this session.

### AMS verification engineer (5)

- `dv-connect-module-discipline-debug` — intermediate
- `dv-real-signal-behavioural-checks` — junior
- `dv-ams-convergence-triage` — senior
- `dv-rnm-authoring-correlation` — senior
- `dv-ams-view-binding-audit` — staff

### Applications engineer (5)

- `dv-artifact-redaction-egress` — fresher
- `dv-customer-escalation-isolation` — intermediate
- `dv-customer-defect-handoff` — junior
- `dv-customer-flow-deployment` — senior
- `dv-regression-runtime-tuning` — staff

### DV engineer (5)

- `dv-sim-log-first-error` — fresher
- `dv-minimal-reproducer` — intermediate
- `dv-coverage-hole-disposition` — junior
- `dv-tb-architecture-record` — principal
- `dv-signal-trace-localisation` — senior

### DV infrastructure engineer (6)

- `dv-repo-orientation` — fresher
- `dv-coverage-merge-report` — intermediate
- `dv-build-filelist-hygiene` — junior
- `dv-compute-license-efficiency` — principal
- `dv-regression-tiering-farm` — senior
- `dv-tool-version-migration` — staff

### EDA product validation engineer (5)

- `dv-tool-bug-testcase-extraction` — intermediate
- `dv-tool-feature-testplan` — intermediate
- `dv-tool-release-behaviour-diff` — junior
- `dv-lrm-conformance-matrix` — senior
- `dv-cross-tool-mismatch-adjudication` — staff

### Emulation engineer (5)

- `dv-emulation-test-porting-audit` — intermediate
- `dv-emulation-bringup` — senior
- `dv-emulation-sim-mismatch-triage` — senior
- `dv-emulation-throughput-triage` — senior-staff
- `dv-emulation-dump-strategy` — staff

### Formal verification (5)

- `dv-formal-property-authoring` — intermediate
- `dv-formal-apps` — junior
- `dv-formal-convergence` — senior
- `dv-formal-target-scoping` — senior-staff
- `dv-formal-overconstraint-credit` — staff

### IP DV engineer (6)

- `dv-uvm-agent-checker` — intermediate
- `dv-regression-triage-routing` — junior
- `dv-config-space-coverage` — principal
- `dv-coverage-hole-closure` — senior
- `dv-error-injection-ras` — senior-staff
- `dv-gls-bringup` — staff

### Memory IP DV engineer (5)

- `dv-memory-model-training` — intermediate
- `dv-mem-refresh-lowpower-audit` — intermediate
- `dv-mem-timing-check-triage` — junior
- `dv-memory-perf-bandwidth` — senior
- `dv-dfi-boundary-blame` — staff

### Processor IP DV engineer (5)

- `dv-csr-warl-access-audit` — intermediate
- `dv-trap-exception-triage` — junior
- `dv-custom-instruction-verification-plan` — senior
- `dv-isa-step-compare` — senior
- `dv-memory-ordering-litmus` — staff

### Safety verification engineer (5)

- `dv-safety-req-trace-audit` — intermediate
- `dv-safety-manual-aou` — principal
- `dv-undetected-fault-closure` — senior
- `dv-safety-mechanism-verification-map` — senior-staff
- `dv-fault-campaign-iso26262` — staff

### Security verification engineer (5)

- `dv-secure-register-policy-audit` — intermediate
- `dv-crypto-kat-coverage-audit` — junior
- `dv-security-build-divergence-audit` — principal
- `dv-asset-flow-property-authoring` — senior
- `dv-security-negative-tests` — staff

### SoC DV engineer (5)

- `dv-connectivity-table-checks` — fresher
- `dv-vip-integration` — intermediate
- `dv-ral-bringup` — junior
- `dv-reset-clock-scenario-matrix` — senior
- `dv-soc-scenario-boot` — staff

### Static sign-off engineer (5)

- `dv-lint-triage` — fresher
- `dv-cdc-rdc-triage` — intermediate
- `dv-xprop-triage` — senior
- `dv-waiver-corpus-audit` — senior-staff
- `dv-power-aware-sim-debug` — staff

### Verification lead (5)

- `dv-escalation-ownership` — director
- `dv-status-rollup` — lead
- `dv-testplan-traceability-review` — lead
- `dv-release-gate` — manager
- `dv-escape-analysis` — senior-manager

### VIP engineer (7)

- `dv-compliance-test-authoring` — fresher
- `dv-vip-coverage-model` — intermediate
- `dv-protocol-checker-rule` — junior
- `dv-spec-interpretation-ledger` — principal
- `dv-spec-feature-extract` — senior
- `dv-vip-release-compat` — senior-staff
- `dv-spec-ecn-delta` — staff

Full role × level matrix (crosstab + per-skill table) was regenerated and shared with the user
this session from this exact inventory — regenerate from here again if needed, don't re-derive
from memory.

## First vertical proof cohort

The five wave-0 candidates are selected for the first end-to-end proof. Their **full payload hashes**
include the three vendored `_shared` files; the lint JSON hash covers only `SKILL.md` and must not be
used for review or approval.

| Skill | Version | Full payload SHA-256 | Role / level |
|---|---|---|---|
| `dv-minimal-reproducer` | 1.4.1 | `bc2f60627cf006e7f3a2686b541346f7fb08a4c292b9d533c28398ae89b5cccb` | dv-engineer / intermediate |
| `dv-sim-log-first-error` | 1.4.1 | `7126735aab199a646f44c58d7906b3f74c09574383ac9ce8028c9c29c21fe268` | dv-engineer / fresher |
| `dv-build-filelist-hygiene` | 1.2.1 | `542c8628a23ce9e0f66d19d677e898ce7dcd0aba1931223f7b837e8a328b8cf3` | dv-infra-engineer / junior |
| `dv-repo-orientation` | 1.2.1 | `42c2295f5c2cd5a2522ed5e9716912c8bbf0e436f703e7848da9efc60f648587` | dv-infra-engineer / fresher |
| `dv-regression-triage-routing` | 1.1.1 | `c128ed8787f4fa63b80b96456df2e7410c6f6ef5913d61366c7d01c5f7b84582` | ip-dv-engineer / junior |

All five are `public`, strict-lint-pass, and `judge_required=true`. That is candidate metadata, not
approval or publication. Re-verify these hashes against the live store before leasing any of them —
they predate this session's work and nothing has re-confirmed them since 2026-08-07.

## What has been implemented and verified

- Append-only canonical artifacts, lifecycle spine, ACL-aware context, gated approval/publication,
  deterministic Stage-1/3/4 scanners, the migration framework, controller/sensor contracts.
- **Stage 2 (security scanner): CODE COMPLETE and PROVEN** (J-010e3/e4/e5/f4) — host-side staging/
  report validation, the real digest-pinned Semgrep engine (`semiskill/scanners/stage2_engine.py`),
  a real 9-rule pack (`docker/stage2/rules/semiskill.yml`), wired into `pipeline.py`/`wave.py` via
  `stage2_policy`. Proven against real Docker execution: benign passes clean, malicious hard-fails.
  Awaiting BLK-003 approval only.
- **Stage 5 (judge): CODE COMPLETE and PROVEN** (J-010e10/f6) — `OllamaJudge`/`Stage5Policy`
  (loopback-only enforcement, model-digest pinning, bounded I/O, no fabricated pass), wired into
  `pipeline.py`/`wave.py` via `stage5_policy`. Proven against the REAL local Ollama daemon (still
  wildcard-bound — correctly refuses). Awaiting BLK-004 calibration only.
- **`review-issue` CLI command: DONE** (J-010f2) — the coordinator-only review-batch issuer moved
  from `tools/issue_batch.py` into importable `semiskill/authoring/issue_batch.py`, exposed as
  `semiskill review-issue`, with the same `_test`-refusal/`--yes` safety pattern as `wave`.
- **Local development identity chain: DONE** (J-010f1/f3) — three distinct Postgres logins for the
  approval-actuator/review-coordinator/export-reader capabilities, on their own cluster (`db`, port
  5432), verified to actually exercise their granted functions, not just resolve role membership.
- **Postgres topology: split into two clusters** (ADR-032) — `db` (real catalog, port 5432) and
  `db-test` (isolated pytest cluster, port 5433, fully disposable). `TEST_DATABASE_URL` points at
  the latter; the three actuator DSN env vars must never be exported for pytest runs.
- Exact skill capture with the three canonical `_shared` files vendored into each payload; any shared
  change invalidates downstream evidence.
- Typed review findings, one-skill exact contracts, append-only lineage, retry semantics, deterministic
  readiness, and collector rejection of stale/mixed/forged batches through migration 0023.
- Authenticated exact-evidence approval and projection boundaries; `semiskill wave` cannot fabricate
  an approval.
- Strict authoring lint, registry/facet validation, pack consistency, collision-safe install/export
  contracts, and 84 current authored skills.
- Read-only command-centre dashboard with integrity-pinned planning data, non-crediting action queue,
  typed operational observations, immutable full-suite reader, freshness/identity display, mobile and
  accessibility hardening.
- Fail-closed migration planning/execution boundary and dashboard authority-chain projection.

## Known gaps, defects, and launch blockers

1. **Development migration approval**: still needs a fresh source-bound, digest-approved plan if a
   new forward migration is ever required — schema is currently AT 0023 on `db`, verified, so this
   is dormant, not active, unless new migrations are authored.
2. **BLK-003 — Stage 2 approval**: code done and proven; needs the user's explicit sign-off on the
   exact digest triple above. Not more engineering.
3. **BLK-004 — Stage 5 calibration**: code done and proven; needs (a) a real 120-item gold set
   (not yet built — next task), (b) the user's solo blind-labeling of it (ADR-031), (c) running
   `calibrate_judge`/computing kappa afterward.
4. **Review issuance + scoreboard v3 are partially incomplete**: `review-issue` now exists
   (closing most of this gap), but scoreboard v3's real remaining piece — independent
   artifact-level re-verification of a snapshot cell's claims against the live store, rather than
   trusting the snapshot's self-reported status — is designed but NOT implemented (deferred below
   the critical path; see "Deferred, tracked, not urgent" below for why and how to resume it).
5. **The Next.js production catalog is incomplete**: unchanged since 2026-08-07, and explicitly
   out of near-term scope per ADR-029 (development catalog needs no web UI). Revisit before any
   production/SharePoint launch.
6. **Production tenant infrastructure is absent**: Entra/OIDC, SharePoint, distinct production
   service identities, deployment, CI, backup, alerting, incident response are not configured —
   **narrowed to production-only scope by ADR-029/032; does not block 84/84-to-development.**
7. **No 84-skill content gate has run**: independent domain content review (adversarial P1 + fresh
   P5 recheck) has not started for any skill. This is the actual remaining bulk of the work once
   BLK-003/004 close — see the Ordered plan below.
8. **Dashboard market data is planning only**: unchanged, still not measured traction.
9. **The historical stage-2/judge "two blockers, not one" defect (SPEC A) is now moot** — both
   Stage 2 and Stage 5 have real implementations; the old diagnosis (`docs/UNBLOCK_SPECS.md`)
   describes a state that no longer exists in the code, only in the approval/calibration gates.
   Worth a follow-up pass over `docs/UNBLOCK_SPECS.md` to mark it historical, not urgent.

### Deferred, tracked, not urgent

- **Scoreboard v3's artifact-reconciliation gap** (gap 4 above): `_lease_cell`/`_cell_checks` in
  `semiskill/authoring/issue_batch.py` trust a snapshot cell's self-reported
  `checks.security.status` rather than independently re-fetching and verifying the referenced
  `automated_review`/`scan_run` artifacts from the live store. Not exploitable today
  (`security_pass` is 0/84 under honest generation), and properly fixing it needs the ~15 call
  sites in `tests/tools/test_issue_batch.py`'s `Store`/`_cell` fixtures reworked to seed a real
  matching `REVIEW` artifact — bigger than it sounds. Resume by adding a `_security_review()` test
  helper + a `_cell_with_security()` variant, then wiring the live check into `_lease_cell`.
- **`apply_migrations()`'s same-transaction enum-value bug** (found J-010f3): applying the full
  ~23-migration history to a truly empty `_test` database in one shot hits Postgres's "unsafe use
  of new enum value" restriction (a real, pre-existing latent bug, not introduced this session).
  Worked around via `pg_dump`/`pg_restore` when `db-test` was created; not fixed at the source. If
  `db-test` is ever wiped, restore that way again rather than a raw `apply_migrations()` bootstrap,
  or fix the underlying bug first (add commits between migration files in the bootstrap path).
- **Full retirement of the old `SecurityAuditScanner`/npx runner**: `stage2_policy`/`stage5_policy`
  are additive parameters (omitting them behaves exactly as before); the old runner still exists as
  the fallback. Retire it once both policies reach CLI flags (deliberately not done yet, mirroring
  how the whole session kept "code path ready, not yet CLI-activated" until each blocker closes).
- **Local Ollama loopback reconfiguration**: offered to the user (interactive page + this file),
  not done. Only needed for a full successful Stage-5 round-trip proof, not for the refusal-path
  proof that already exists.

## Accepted Stage 2 direction (ADR-024, pragmatically scoped by ADR-030, IMPLEMENTED J-010f4)

ADR-024's full vision: an internally mirrored and signed Semgrep OSS-mode derivative with a bundled
SemiSkill Markdown/security rule pack, exact image digest, no network, read-only input, dropped
capabilities, `no-new-privileges`, and non-root execution.

**What's actually built** (ADR-030's pragmatic scope — signing/SBOM/CVE explicitly deferred):
the upstream `semgrep/semgrep` image referenced directly by exact platform-manifest digest (no
local derivative build — simpler and more independently auditable), a real 9-rule pack mounted
read-only and separately from the payload, and a `docker run` invocation hardened with
`--network none --read-only --cap-drop ALL --security-opt no-new-privileges --user semgrep`
plus `--tmpfs /tmp -e HOME=/tmp` (Semgrep needs a writable settings dir even read-only) and
`--metrics=off --disable-version-check` (or it hangs trying to phone home). See the exact digest
triple above for what's awaiting approval.

## Proposed Stage 5 direction (IMPLEMENTED J-010e10/f6, calibration still BLK-004)

- Runtime: Ollama, exact loopback HTTP adapter using the standard library only (`urllib.request`,
  no new dependency). **Built**: `semiskill/scanners/stage5_ollama.py`.
- Model: `qwen3-coder:30b`; manifest digest
  `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca` — confirmed still installed
  and this exact digest via a live `/api/tags` call, 2026-08-10.
- The local Ollama daemon is **confirmed still wildcard-bound** (`0.0.0.0:11434`/`[::]:11434`),
  not loopback-only — `OllamaJudge._is_loopback_only()` correctly refuses against it as proven
  by a real (not synthetic) integration test. Reconfiguring it is offered as a pending decision,
  not done (see "Pending decisions" above).
- Require exact `127.0.0.1`, no proxies/redirects/tools, temperature 0, strict JSON schema, bounded
  request/response/time, exact prompt/model/calibration hashes, and fail-closed daemon binding
  checks — all **implemented and tested**, not just proposed.
- Calibration acceptance set: 120 blinded examples (60 unsafe, 60 matched safe) — **NOT YET BUILT**.
  ADR-031: solo-labeled by the user (not the originally-proposed two-labeler + adjudicator design),
  an explicit, recorded deviation, not presented as satisfying the original protocol.

## Ordered implementation and release plan

### Gate 0 — synchronize this handoff (status: mostly done, one item open)

1. ~~At the clean pre-step checkpoint, pull/rebase and stop on any conflict before editing.~~ Done
   continuously this session.
2. ~~Change and validate the project skill plus documentation/state, then commit them atomically.~~
   Done (J-010f5, and this refresh).
3. ~~Push `main` and prove local HEAD equals `origin/main` with a clean tree.~~ Done after every
   commit this session.
4. **OPEN**: run a new immutable serial full suite on the exact clean committed source (not a
   dirty-tree run) — none of this session's runs qualify; the last immutable record is 10 commits
   stale. Do this before generating any new migration plan or release checkpoint.
5. Generate a replacement migration plan only if a new migration is actually needed — schema is
   currently at 0023 on `db`, verified; this step is dormant unless that changes.

### Gate 1 — activate canonical review infrastructure (status: mostly done)

1. ~~Execute only the exact approved migration plan.~~ Done (0023, verified).
2. ~~Implement the shared review-contract parser and coordinator-only `review-issue` command.~~
   Done (J-010f2).
3. Implement scoreboard v3 plus progress v2 strict nested/self-hash/binding validation — **partially
   deferred**, see "Deferred, tracked, not urgent" above. Not blocking Gate 2.
4. Build one shared live-observation module for API, dashboard, and scoped export — not started,
   not blocking Gate 2 either (still three independent reimplementations of freshness-checking).
5. ~~Implement/pin Stage 2, calibrate/pin Stage 5, and prove hostile payloads cannot widen files,
   tools, network, or output scope.~~ Stage 2/5 code+wiring done and proven; calibration (Stage 5
   only) is BLK-004, still open. Hostile-payload containment proven for Stage 2 (staging/report
   validators, adversarial tests); Stage 5 doesn't touch payload files so this doesn't apply there.

### Gate 2 — vertical proof, then controlled expansion (status: NOT STARTED — the real next work)

1. Prove `dv-minimal-reproducer` end to end: exact capture → stages 1/2/3/4/5/6 → P1 → fixer if
   needed → fresh-context P5 → deterministic ready → explicit human approval → projection publish
   **to the development catalog** (ADR-029). Requires BLK-003 and BLK-004 both closed first.
2. Repeat for the five wave-0 skills; audit the whole cohort and dashboard reconciliation.
3. Process the remaining catalog in batches of at most 10 with no more than three concurrent read-only
   agent tasks. Serialize collection, edits, DB work, and tests.
4. Run the full suite every three batches and immediately before each human approval batch.
5. Preserve disputed findings as blocking until a named human/domain adjudicator resolves them.

### Gate 3 — production catalog and market readiness (status: explicitly deferred, ADR-029)

Unchanged from 2026-08-07, and now explicitly out of near-term scope. Revisit only once Gate 2
completes and an actual production/SharePoint launch is being planned.

1. Finish the Next.js list/detail experience, ACL query traversal, install/copy fallback, related
   skills, exact audit evidence, hostile Markdown containment, responsive/a11y behavior and build.
2. Configure Entra/OIDC, SharePoint, least-privilege service identities, CI/deploy, backup/restore,
   monitoring/alerts, rollback and incident response.
3. Obtain security, privacy, legal, product, brand and commercial approvals. Connect analytics only
   after consent/data contracts exist; never backfill launch metrics with estimates.
4. Release only when the canonical scoreboard reports 84/84 at every gate, 16/16 roles at >=5,
   zero anomalies/open blockers, exact output-byte reconciliation, and all Python/UI suites green.

## Dashboard and operator commands

Local command centre: [http://127.0.0.1:8899/](http://127.0.0.1:8899/). It is a read-only local
operator view. If the API or canonical scoreboard is unavailable, the UI must show unavailable—not
fixtures, seeds, cached green state, or inferred zeroes.

```powershell
# State and source
git status --short --branch
git rev-parse HEAD
Get-Content .session-lock

# Local Postgres — TWO clusters since ADR-032, not one
docker ps --filter "name=semiskill"          # expect BOTH semiskill-db-1 (5432) and semiskill-db-test-1 (5433)

# Authored catalog (non-publication evidence)
python -m semiskill.cli lint skills --strict

# Current scoreboard v2 is diagnostic and known-defective; it cannot authorize review or release.
python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json --snapshot-out reports/scoreboard.json --environment development --json

# Coordinator-only: mint review-batch contracts (NOW EXISTS, J-010f2)
python -m semiskill.cli review-issue --snapshot reports/scoreboard.json --phase review --prompt-version P1-ADVERSARIAL-REVIEW@3 --size 10 --out-dir reports/contracts/<batch-id>/ --yes

# Fixed serial platform proof — run with ONLY TEST_DATABASE_URL exported, never the full .env
$env:TEST_DATABASE_URL = "postgresql://semiskill:semiskill@127.0.0.1:5433/semiskill_test"
python -m semiskill.cli verify-full-suite --expected-database semiskill_test
```

`review-issue` now exists (see above) — `tools/collect_wave.py` still requires one separately
issued exact one-skill contract per collection, unchanged. Check current CLI `--help` before using
migration or review commands; never invent an output path or append `--yes` merely to make a
privileged operation continue.

## Human decisions required

1. **BLK-003**: approve/reject the exact Stage-2 digest triple above (or via the interactive page).
2. Reconfigure local Ollama to loopback-only? (small, optional, offered not required — see above).
3. Provide/build the Stage-5 120-item calibration corpus content for the user to blind-label
   (agent will draft candidates; the user's own labels are what makes it real — ADR-031).
4. Complete the solo calibration labeling once the corpus exists, then review the resulting kappa
   with the explicit understanding it is not a genuine inter-rater statistic (ADR-031).
5. Review content-review batches of at most 10 exact skill versions/hashes once Gate 2 starts;
   accept/reject each explicitly.
6. Eventually (not now, per ADR-029): supply the production tenant, app registrations, SharePoint
   target and least-privilege identities, only when a real production/SharePoint launch is planned.

## Forecast, not a commitment

Materially better than the 2026-08-07 forecast, because both remaining code blockers are now real
and proven rather than designed:

- BLK-003 close: as fast as the user's review — hours, not days, since the evidence is complete.
- BLK-004 close: bounded by building a good 120-item corpus (agent work, hours) plus the user's own
  labeling pace (not an agent-controllable variable — 120 items to read and judge takes real time).
- First legitimate published-to-development skill: once both blockers close, the vertical proof
  itself (Gate 2 step 1) is now mostly plumbing exercise, not open design — likely fast.
- All 84 through development gates: the actual content-review bottleneck (Gate 2 steps 2-3) is
  unchanged in nature from the 2026-08-07 estimate — batches of ≤10, full suite every 3 batches,
  independent content review is still real reviewer-hours, not something this session shortened.
  Central estimate stays roughly 3-6 weeks of elapsed batch work once Gate 2 starts, though the
  infrastructure preconditions that used to gate STARTING it are now resolved or one decision away.
- External/production market launch: unchanged, explicitly deferred (ADR-029) — likely months,
  gated on tenant/legal/privacy/support work this session did not touch.

Reforecast from measured batch throughput after the first five exact skills, same as before.

## Resume checklist

- Acquire/verify `.session-lock`; coordinator remains the sole writer. If a different session ID
  holds it and its timestamp is >2h old, report contents and ASK before taking over — never
  auto-steal (this session took over exactly one stale lock this way, with explicit approval).
- Read `STATUS.md`, the bottom of `MEMORY.md`, `BLOCKERS.md`, and `DECISIONS.md`'s ADR-029..032.
- Verify Git/DB/dashboard evidence directly — `docker ps` for BOTH Postgres clusters, `docker image
  inspect` for the pinned Stage-2 image if `@pytest.mark.docker` tests matter, `netstat` for
  Ollama's actual bind address if Stage-5 work is planned. Note any stale source binding.
- Check whether the user has responded to the interactive decision page (BLK-003 approval, Ollama
  reconfiguration) since this handoff was written — if so, act on it; if not, it's still pending.
- Choose one 2–10 minute atomic step; write the failing check first for behavioral changes.
- Keep subagents read-only; fresh P5 reviewers receive no fixer reasoning.
- Run focused verification, THEN the full suite before checkpointing any change to shared
  infrastructure as done (database roles, docker-compose topology, environment variables) — two
  real regressions this session shipped past "should be additive/isolated" reasoning.
- Reconcile artifacts, prepare state, commit, and push under `STATE_RULES.md`'s atomic
  self-reference convention.
- Do not say "ready for launch" until the canonical release gate—not this file—proves it, and
  always say WHICH launch (development catalog vs. production/SharePoint, ADR-029).

---

## Historical: 2026-08-07 and earlier

Preserved for archaeology. Superseded by everything above where they conflict.

### Unrecorded session of 2026-08-07 (preserved under J-010d3, credited nothing)

A session ran roughly `05:48Z-06:12Z` and died without checkpointing. Its work was preserved, not
trusted. It committed `c8f5fa3` with no STEP-ID and no MEMORY entry.

- **VERIFIED (J-010d6):** the `0015 -> 0023` forward migration executed. `schema_migrations` holds
  23 rows, last `0023_review_unbound_parameter_binding.sql`, with 0016-0023 all present. The human
  has confirmed they approved that exact plan digest, so BLK-002 is closed.
- **VERIFIED (J-010d6):** all 84 registry-active slugs have a `skill_version` artifact.
- **FINDING:** the 85th `skill_version` slug is `dv/cve`, a TEST FIXTURE from
  `tests/spine/test_pipeline.py`, captured into the DEVELOPMENT store. Append-only, so it stays —
  non-crediting pollution, must always be excluded from counts.

### Superseded migration evidence

Never approve or execute either old plan:

- Obsolete plan digest from `91cdd50`: `948d874415c4b7aecf2cdb0dabb19b46afa0f93f981847ea5773cbac10bd4364`
- Superseded plan digest from `b36f250`: `ed397d3454c73094852e1da1d3723ddb53007c2ac175f56358ae4e3c7a7cb864`

Generate a replacement read-only migration plan only from the final clean source commit and a
current immutable full-suite PASS, if one is ever needed again (schema is currently stable at 0023).
