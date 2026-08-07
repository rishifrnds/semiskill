# SemiSkill project handoff

_Updated: 2026-08-07 UTC. Scope: the existing 84 active DV skills only. The 20 declined registry
candidates remain non-crediting provenance; the proposed 19-level expansion is deferred._

## Executive verdict

**Launch status: NO-GO.** The platform has substantial verified implementation, all 84 skill
directories exist and pass strict authoring lint, but **0/84 skills currently have a complete,
current, canonical security + independent-review + human-approval + publication chain**. A passing
platform test suite does not convert authored skills into approved skills.

The next legitimate milestone is not “publish 84.” It is: migrate the development artifact store
through 0023 under an exact approved plan, finish Stage 2/Stage 5/review issuance/scoreboard v3, then
vertically prove one skill end to end before expanding to five and then 84.

Use the repository skill at `.agents/skills/semiskill-project/SKILL.md` to resume work. It routes all
state, gate, review, and release tasks through this file and `STATE_RULES.md`.

## One-screen command centre truth

| Measure | Current | Launch target | Authority |
|---|---:|---:|---|
| Active registry skills | 84 | 84 | `specs/skill_registry.json` |
| Declined provenance records | 20 | 20 | registry, non-crediting |
| Roles represented | 16 | 16 | registry |
| Roles with at least 5 authored skills | 16 | 16 | registry + filesystem |
| Authored skill directories | 84 | 84 | `skills/*/SKILL.md` |
| Strict-lint pass | 84 | 84 | deterministic authoring lint |
| Pack consistency errors | 0 | 0 | deterministic pack check |
| Pack consistency warnings | 60 | reviewed/disposed | non-blocking until classified |
| Security-complete current payloads | 0 | 84 | canonical artifacts |
| Canonically reviewed | 0 | 84 | exact-hash append-only reviews |
| Recheck-ready | 0 | 84 | deterministic zero-open-blocker gate |
| Authenticated human-approved | 0 | 84 | exact-evidence approval projection |
| Projection-backed published | 0 | 84 | catalog projection |
| Development DB schema | **0023, verified** | 0023 before review issuance | `schema_migrations`, 23 rows, J-010d6 |
| Test DB schema | 0023 | current | isolated test observation |
| Canonical scoreboard | unavailable/expired | fresh and reconciled | fail-closed snapshot |
| Market launch | NO-GO | all release invariants true | canonical release gate only |

The read-only dashboard last observed the development database at `2026-08-07T03:17:28Z` as
`postgresql / development / semiskill`, identity
`sha256:9b98194d3901734a63746f50dbe98dc1c161fd99bc9fd497080cba2c6a2002a9`.
It contained 39 artifacts: 35 imported legacy reviews, 2 `scan_run`, 1 `skill_version`, and 1
`gate_decision`; it contained no approval. That observation has `credit: none` and does not prove the
migration authority chain, whose privileged read is unavailable. Legacy reviews are append-only
provenance and earn no current readiness credit.

The current canonical anomaly set is unavailable because scoreboard v3 has not been regenerated.
Never infer zero anomalies from the stale v2 snapshot.

## Unrecorded session of 2026-08-07 (preserved under J-010d3, credited nothing)

A session ran roughly `05:48Z-06:12Z` and died without checkpointing. Its work was preserved, not
trusted. It committed `c8f5fa3` with no STEP-ID and no MEMORY entry.

- **VERIFIED (J-010d6):** the `0015 -> 0023` forward migration executed. `schema_migrations` holds
  23 rows, last `0023_review_unbound_parameter_binding.sql`, with 0016-0023 all present. The human
  has confirmed they approved that exact plan digest, so BLK-002 is closed.
- **VERIFIED (J-010d6):** all 84 registry-active slugs have a `skill_version` artifact. Counts
  reconcile exactly against the earlier 39-artifact baseline: scan_run 338, review 119,
  skill_version 85, injection_test 84, gate_decision 2.
- **FINDING:** the 85th `skill_version` slug is `dv/cve`, a TEST FIXTURE from
  `tests/spine/test_pipeline.py`, captured into the DEVELOPMENT store at 2026-08-06T06:57:44. The
  artifact store is append-only, so it stays. It is non-crediting pollution: every funnel, scoreboard
  and reconciliation reader must exclude unregistered slugs explicitly rather than assume 1:1 with
  the registry.
- It left `tools/issue_batch.py` + tests (the SPEC B review-issuance producer) and
  `docs/UNBLOCK_SPECS.md`. That code is **inherited and unreviewed**; it mints review leases, so it
  must be tested against `collect_wave.py::_validate` before it touches real work.
- Undocumented `migrate-forward` prerequisites it recorded, because they cost real time:
  `SEMISKILL_MIGRATOR_ROLE` must equal both the session user and the database owner;
  `SEMISKILL_DEVELOPMENT_DATABASE_NAME` and `SEMISKILL_PRODUCTION_DATABASE_NAME` must both be set
  and different; the tree must be clean; and the plan's `source_commit` must equal HEAD - so the
  plan must be written **outside** the repository, because committing it invalidates it.

Its one genuinely valuable finding is the SPEC A contradiction in gap 9 below.

## Exact platform proof already completed

The current clean-source immutable full-suite run is the standing platform proof:

- Run ID: `5eb6210d-8f6a-41a1-a48b-8190a696b416`
- Source commit/tree: `854ae71` / `a493c56ca1699ec64b9e0b531bd4bf41dbba7e28` (`clean: true`)
- Run artifact SHA-256: `52aec9b0e2b7f8d67dcfe9581acc1f1be66e0754e02c34597f8b94f07e27c83f`
- Output SHA-256: `936972ccba1eab17c634b6e7cfbe769511a037e81c6bf810b36ca0fcf22d1e66`
- Result: 1,117 collected; 1,110 passed; 7 skipped; 0 failed; 0 errors; 0 xfailed/xpassed
- Database: exact isolated `semiskill_test`, migration 0023
- Credit: **none** toward skill review, approval, publication, or launch readiness

It supersedes the historical `b36f250` run (1,078 passed), which had gone stale and was concealing a
README regression introduced by `105b3cb`. Any source change after `854ae71` makes this run stale
too; produce another before approving a migration or release checkpoint.

## Superseded migration evidence

Never approve or execute either old plan:

- Obsolete plan digest from `91cdd50`: `948d874415c4b7aecf2cdb0dabb19b46afa0f93f981847ea5773cbac10bd4364`
- Superseded plan digest from `b36f250`: `ed397d3454c73094852e1da1d3723ddb53007c2ac175f56358ae4e3c7a7cb864`
- Superseded file SHA-256: `1bdf0df54b5dc8608f9d86f4cc6bc644e3192bfac70496c6e62a3b14c38e96aa`

Generate a replacement read-only 0015-to-0023 plan only from the final clean source commit and a
current immutable full-suite PASS. Execution still requires the human to approve that exact new
digest; a general instruction to continue work is not migration approval.

## The complete 84-skill catalog inventory

Every item below is **authored + strict-lint-pass, but not canonically approved or published**.

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
approval or publication.

## What has been implemented and verified

- Append-only canonical artifacts, lifecycle spine, ACL-aware context, gated approval/publication,
  deterministic Stage-1/3/4 scanners, Stage-2/5 interfaces, controller/sensor contracts, and the
  migration framework. Live Stage 2 and calibrated Stage 5 remain incomplete below.
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

1. **Development migration approval:** schema 0015 must reach 0023 under a newly generated,
   source-bound, digest-approved plan. Old digests are invalid.
2. **Stage 2 is not production-usable:** the current `@claude-flow/cli security scan` can write into
   the target, depends on networked `npm audit`, does not scan Markdown `SKILL.md`, and swallows some
   errors. It cannot earn a pass.
3. **Stage 5 is not calibrated:** local Ollama exists, but the daemon listens on wildcard IPv6
   `[::]:11434`; activation must fail until it is loopback-only. The model has no approved held-out
   calibration report or drift baseline.
4. **Review issuance + scoreboard v3 are incomplete:** migrations contain the required authority
   primitives, but the coordinator-only issuance command, strict nested scoreboard/progress schemas,
   complete 104-cell/176-role-level views, and live reconciliation are not yet implemented.
5. **The Next.js production catalog is incomplete:** API failure is hidden, some safety/stage data is
   fabricated, install types disagree, and list/detail/facets/a11y/responsive/build evidence is absent.
6. **Production tenant infrastructure is absent:** Entra/OIDC, SharePoint, distinct service identities,
   deployment, CI, backup, alerting, incident response, privacy/legal and commercial launch inputs are
   not configured.
7. **No 84-skill content gate has run:** historical sidecars and former “ready” labels are invalid
   after shared-payload hashing. Independent domain review remains human/agent work, not a code-only
   shortcut.
8. **Dashboard market data is planning only:** social, distribution, analytics, marketing, sales,
   pricing, assets and funnels are typed hypotheses or unavailable observations—not measured traction.
9. **TWO independent blockers hold every skill at the scan gate, not one.** Computing the gate for
   `dv-minimal-reproducer` returns `['REQUIRED_JUDGE_NOT_PASSED', 'REQUIRED_STAGE_BLOCKED']`.
   Observed stage statuses across all 84 captures: stage 1 `passed`, **stage 2 `not_run`**, stage 3
   `passed`, stage 4 `passed`, stage 5 `not_sampled`. `snapshot.py` requires stages 1-4 to all be
   `passed`, so **Stage 2 blocks every skill on its own** and needs the ADR-024 scanner plus its
   supply-chain approval (gap 2 / BLK-003). `docs/UNBLOCK_SPECS.md` originally claimed the judge was
   "the single reason"; that claim is corrected in place. Resolving the judge alone yields zero
   published skills. The second blocker is:
   **SPEC A — the judge policy is self-contradictory.**
   `semiskill/spine/pipeline.py::run_pipeline` writes a stage-5 artifact with status `not_sampled`
   when `judge_risk_scanner is None`, which is correct: a skipped judge must never render as a pass.
   But `semiskill/authoring/snapshot.py` (~line 642) appends `REQUIRED_JUDGE_NOT_PASSED` whenever
   `judge_required` and the judge is not `passed`. The wave supplies no judge scanner, so all 84
   skills are `SECURITY_BLOCKED` even though every stage that ran scored 1.000 and the aggregate
   verdict is `approve`. **No skill can reach `security_pass` in this environment until one of the
   two rules is rescoped.** This is the failure class named in `docs/LEARNINGS.md`: when two rules
   can only be satisfied by violating each other, one of them is scoped wrong. Resolve it with a
   failing test first, and do not widen the judge policy merely to make the counts move —
   `judge_required=true` exists because the initial corpus is exactly what a calibrated judge is
   for. Full analysis and the proposed resolution: `docs/UNBLOCK_SPECS.md`.

`BLOCKERS.md` is the active external-dependency register. Implementation defects remain visible here
and in the ordered backlog rather than being mislabeled as external blockers.

## Accepted Stage 2 direction

ADR-024 replaces the live Ruflo/claude-flow scanner direction. Build an internally mirrored and
signed Semgrep OSS-mode derivative with a bundled SemiSkill Markdown/security rule pack, exact image
digest, no network, read-only input, dropped capabilities, `no-new-privileges`, and non-root
execution. The trusted host must project the captured payload into scanner-owned staging, reject or
isolate payload-controlled scanner files such as `.semgrepignore`, enumerate every expected file,
and invoke the fixed engine with `--oss-only`, `--disable-nosem`, `--no-git-ignore`,
`--scan-unknown-extensions`, `--metrics=off`, and `--disable-version-check`. Supply no auth token.

Any ignored, skipped, unparsed, truncated, timed-out, resource-killed, extra, or missing file makes
Stage 2 `not_run` and blocking. The host—not container prose—binds the bounded exact-key report to
slug, version, full payload hash, exact image platform-manifest digest, independently computed
`rule_pack_sha256`, adapter source commit/digest, policy/schema/engine versions and hashes,
expected/analyzed files, findings, errors, skips, truncation and resource status. Reject unknown
fields/severities, duplicate finding IDs, absolute/traversing paths, mismatched counts and
container-supplied identity/digests. AppSec/legal/signature promotion approves this exact immutable
chain, not a tag or version label.

Provisional upstream supply-chain coordinates are for evaluation only:

- image: `semgrep/semgrep:1.172.0-nonroot`
- OCI index: `sha256:d1012a3bf2acf47721216fbf7ff12d4c2971cc7f9c7b77cf6c6e9dcf006bd487`
- linux/amd64 manifest: `sha256:2e01772afbd85789464594ca86e22896748cbc78a5d9751dfc947a40b214ccc2`

The observed upstream metadata includes proprietary/Pro setup, so the tag does not itself prove CE
or OSS-only execution. These coordinates are **not production-approved** until AppSec, SBOM/CVE,
legal/license, engine-attestation and signature review closes on the internal derivative.

## Proposed Stage 5 direction

- Runtime: Ollama 0.32.5, exact loopback HTTP adapter using the standard library only.
- Model: `qwen3-coder:30b`; manifest
  `06c1097efce0431c2045fe7b2e5108366e43bee1b4603a7aded8f21689e90bca`.
- Model blob: `1194192cf2a187eb02722edcc3f77b11d21f537048ce04b67ccf8ba78863006a`
  (18,556,688,736 bytes); config
  `24a94682582c6045f4950846fc7711479dcecb478b86759f0306a2ef8484d318`;
  parameters `69aa441ea44ff5e1e7b56cac4f471e71e8a5e2e3963c29684a9234d5d5e5f7aa`.
- Require exact `127.0.0.1`, no proxies/redirects/tools, temperature 0, strict JSON schema, bounded
  request/response/time, exact prompt/model/calibration hashes, and fail-closed daemon binding checks.
- Proposed calibration acceptance set: 120 blinded examples (60 unsafe, 60 matched safe), two
  independent labelers plus adjudicator, with ratified recall/specificity/agreement thresholds. This
  is a proposal—not an approved calibration report.

## Ordered implementation and release plan

### Gate 0 — synchronize this handoff

1. At the clean pre-step checkpoint, pull/rebase and stop on any conflict before editing.
2. Change and validate the project skill plus documentation/state, then commit them atomically.
3. Push `main` and prove local HEAD equals `origin/main` with a clean tree.
4. Run a new immutable serial full suite on that exact clean source.
5. Generate a replacement 0015-to-0023 migration plan; present its exact digest for human approval.

### Gate 1 — activate canonical review infrastructure

1. Execute only the exact approved migration plan.
2. Implement the shared review-contract parser and coordinator-only `review-issue` command.
3. Implement scoreboard v3 plus progress v2 strict nested/self-hash/binding validation.
4. Build one shared live-observation module for API, dashboard, and scoped export.
5. Implement/pin Stage 2, calibrate/pin Stage 5, and prove hostile payloads cannot widen files, tools,
   network, or output scope.

### Gate 2 — vertical proof, then controlled expansion

1. Prove `dv-minimal-reproducer` end to end: exact capture → stages 1/2/3/4/5/6 → P1 → fixer if
   needed → fresh-context P5 → deterministic ready → explicit human approval → projection publish.
2. Repeat for the five wave-0 skills; audit the whole cohort and dashboard reconciliation.
3. Process the remaining catalog in batches of at most 10 with no more than three concurrent read-only
   agent tasks. Serialize collection, edits, DB work, and tests.
4. Run the full suite every three batches and immediately before each human approval batch.
5. Preserve disputed findings as blocking until a named human/domain adjudicator resolves them.

### Gate 3 — production catalog and market readiness

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

# Authored catalog (non-publication evidence)
python -m semiskill.cli lint skills --strict

# Current scoreboard v2 is diagnostic and known-defective; it cannot authorize review or release.
python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json --snapshot-out reports/scoreboard.json --environment development --json

# Fixed serial platform proof on the explicit isolated database
python -m semiskill.cli verify-full-suite --expected-database semiskill_test
```

The intended `review-issue` command and scoreboard v3 do not exist yet; build and verify them in
J-010d4 before running any review wave. `wave` does not issue a review contract, and
`tools/collect_wave.py` requires one separately issued exact one-skill contract per collection.
Check current CLI `--help` before using migration or review commands; never invent an output path or
append `--yes` merely to make a privileged operation continue.

## Human decisions required

1. Approve the newly generated migration-plan digest after reviewing the exact clean source/run.
2. Approve the Stage 2 internally built image, rule pack and supply-chain record.
3. Nominate two independent Stage 5 labelers and one adjudicator; approve the held-out calibration
   set and acceptance thresholds.
4. Supply the production tenant, app registrations, SharePoint target and least-privilege identities.
5. Review approval batches of at most 10 exact skill versions/hashes; accept/reject each explicitly.

## Forecast, not a commitment

Assuming the external decisions and reviewers are available:

- First legitimate published skill: roughly 3–6 working days and another 1–2M model tokens.
- First five: roughly 4–7 working days and 2–5M tokens.
- All 84 through development gates: roughly 3–6 weeks and 4–8M tokens (central estimate 5.5–6M).
- Internal colleague-ready launch: roughly 5–8 weeks.
- External market launch: likely months; tenant, legal, privacy, support and human-review work—not
  tokens—becomes the dominant constraint.

These ranges must be reforecast from measured batch throughput after the first five exact skills.

## Resume checklist

- Acquire/verify `.session-lock`; coordinator remains the sole writer.
- Read `STATUS.md`, the bottom of `MEMORY.md`, `BLOCKERS.md`, and relevant ADRs.
- Verify Git/DB/dashboard evidence directly and note any stale source binding.
- Choose one 2–10 minute atomic step; write the failing check first for behavioral changes.
- Keep subagents read-only; fresh P5 reviewers receive no fixer reasoning.
- Run focused verification, reconcile artifacts, prepare state, commit, and push under
  `STATE_RULES.md`'s atomic self-reference convention.
- Do not say “ready for launch” until the canonical release gate—not this file—proves it.
