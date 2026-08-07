<!--
Active blockers ONLY. Delete entries the moment they resolve and log the resolution in MEMORY.md.
Full rules: see STATE_RULES.md.
-->

## [BLK-001] Production identities and tenant integration are not configured
- Raised: 2026-08-06T13:29:31Z
- Blocks: J-014 production activation and SharePoint publication
- Type: missing-credential
- Description: Entra/OIDC tenant values, SharePoint target configuration and distinct production
  runtime, approval-actuator, export-reader and migration credentials are absent. The loopback
  development owner is intentionally non-crediting and cannot satisfy the production gate.
- What I tried: implemented and tested fail-closed adapters, exact capability contracts and a
  development-only witnessed migration path; no tenant secrets were inferred or fabricated.
- What I need to unblock: provision the tenant/app registrations and least-privilege database
  identities, then supply their approved configuration through the documented environment contract.
- Escalate at: 2026-08-08T13:29:31Z

## [BLK-002] The 0015->0023 migration was executed without a recorded human digest approval
- Raised: 2026-08-07T03:10:37Z
- Blocks: Gate-1 migration authority, canonical review issuance and scoreboard v3
- Type: user-input-needed
- Description: Reframed 2026-08-07T07:16:49Z. This blocker was originally "the dev DB is still at
  0015 and needs a new approved plan digest". An unrecorded session then committed
  `reports/migration-plan.json` as `c8f5fa3` ("reviewed") and, per `docs/UNBLOCK_SPECS.md`,
  executed the forward migration. No MEMORY entry, no recorded human approval of that exact digest,
  and no independent confirmation that the schema is now 0023 exist. The plan's own constraint is
  that `source_commit` must equal HEAD, so committing the plan into the repo invalidates it.
- What I tried: preserved the plan and the two superseded digests as evidence; attempted a
  read-only re-observation of the store, which timed out (see BLK-005).
- What I need to unblock: confirm whether you approved that exact plan digest. If yes, record the
  approval; if no, the executed migration needs an explicit audit of what ran against development
  before any review issuance is allowed to depend on it.
- Escalate at: 2026-08-09T03:10:37Z

## [BLK-003] Stage-2 scanner image and rule pack lack supply-chain approval
- Raised: 2026-08-07T03:10:37Z
- Blocks: Stage-2 production credit and the first end-to-end skill publication
- Type: external-dependency
- Description: ADR-024 selects an internally built and signed Semgrep OSS-mode derivative, but the internal
  image, bundled SemiSkill rules, SBOM/CVE record, license review and signature policy do not yet
  exist as approved artifacts. The former claude-flow path is not a valid fallback.
- What I tried: audited the current runner, recorded its fail-open coverage/egress/write defects and
  pinned provisional upstream coordinates for controlled evaluation only.
- What I need to unblock: AppSec and legal/supply-chain owners must approve the exact image platform
  manifest, rule-pack SHA-256, adapter source commit/digest and policy/schema hashes after the adapter
  and adversarial tests pass.
- Escalate at: 2026-08-09T03:10:37Z

## [BLK-004] Stage-5 held-out calibration needs independent human labels
- Raised: 2026-08-07T03:10:37Z
- Blocks: calibrated Stage-5 credit and the initial/high-risk corpus gate
- Type: external-dependency
- Description: The local model/runtime can be pinned, but no approved held-out corpus, blinded human
  labels, adjudication record, acceptance thresholds or drift baseline exists. The current Ollama
  wildcard listener also fails the planned loopback-only activation contract.
- What I tried: recorded exact local model artifacts and proposed a bounded loopback adapter and a
  120-example balanced calibration design without treating the proposal as completed evidence.
- What I need to unblock: nominate two independent labelers and one adjudicator, ratify the corpus
  and metrics, complete blinded labeling, and configure the runtime loopback-only.
- Escalate at: 2026-08-09T03:10:37Z

## [BLK-005] The development artifact store is unreachable
- Raised: 2026-08-07T07:16:49Z
- Blocks: verification of every migration, capture, scan and funnel claim; J-010d5
- Type: external-dependency
- Description: The Docker daemon is not running (`npipe:////./pipe/dockerDesktopLinuxEngine` cannot
  be opened), so the local Postgres 16 development store at `127.0.0.1:5432/semiskill` is down. A
  read-only `psycopg.connect` raised `ConnectionTimeout`. Consequently the crashed session's two
  material claims - schema advanced to 0023, and 84 skills captured with 6 scan artifacts each -
  remain file evidence only and are recorded as UNVERIFIED.
- What I tried: attempted a read-only table listing against the documented `DATABASE_URL`; confirmed
  the daemon is absent rather than the credentials being wrong; recorded unavailability as
  unavailability rather than inferring zeroes or a pass.
- What I need to unblock: start Docker Desktop and the project's Postgres container, then re-run the
  read-only observation before any step depends on the store.
- Escalate at: 2026-08-09T07:16:49Z

<!-- Template for a new blocker:
## [BLK-NNN] <short title>
- Raised: <ISO timestamp>
- Blocks: <STEP-ID | phase | project>
- Type: external-dependency | ambiguity | bug | missing-credential | decision-pending | user-input-needed
- Description: <2-3 sentences>
- What I tried: <summary>
- What I need to unblock: <concrete action>
- Escalate at: <Raised + 48h, ISO timestamp>
-->
