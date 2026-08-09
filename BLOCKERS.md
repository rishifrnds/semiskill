<!--
Active blockers ONLY. Delete entries the moment they resolve and log the resolution in MEMORY.md.
Full rules: see STATE_RULES.md.
-->

## [BLK-001] Production identities and tenant integration are not configured
- Raised: 2026-08-06T13:29:31Z
- Blocks: J-014 production activation and SharePoint publication (NARROWED 2026-08-09, ADR-029 —
  no longer blocks the "84 published to the development catalog" milestone)
- Type: missing-credential
- Description: Entra/OIDC tenant values, SharePoint target configuration and distinct PRODUCTION
  runtime/migration credentials are absent, and there is no SharePoint/Graph integration code to
  activate even once supplied (verified 2026-08-08). The DEVELOPMENT-environment
  approval-actuator, review-coordinator and export-reader credentials are RESOLVED as of J-010f3
  (2026-08-09, corrected from J-010f1): three local Postgres logins on the `db` cluster (port
  5432), each holding exactly one capability-role grant, verified to actually exercise their
  granted functions. J-010f1's first attempt broke migration-checkpoint attestation tests because
  Postgres roles are cluster-wide and `semiskill_test` shared that cluster; J-010f3 split the
  local Postgres into `db` (real catalog + these logins) and a separate disposable `db-test`
  cluster (ADR-032) to fix it — see ADR-032 for the full diagnosis. Per ADR-029, the near-term
  "published" milestone targets this development catalog, not SharePoint, so this blocker no
  longer gates 84/84.
- What I tried: implemented and tested fail-closed adapters, exact capability contracts and a
  development-only witnessed migration path; no tenant secrets were inferred or fabricated.
  Provisioned and verified the development-scope credentials (J-010f1), then corrected the
  cluster-topology regression it caused (J-010f3/ADR-032) once the full suite caught it.
- What I need to unblock: for the remaining PRODUCTION-only scope — provision the Entra/OIDC
  tenant/app registrations and a real SharePoint target, then supply their approved configuration
  through the documented environment contract. Not needed for 84/84-to-development.
- Escalate at: 2026-08-08T13:29:31Z (already surfaced to and acknowledged by the user this
  session via the ADR-029 scoping decision; production-only scope remains open, non-urgent)

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
- Update 2026-08-09 (ADR-031): asked explicitly, the user chose solo labeling over waiting for a
  second labeler/adjudicator. This is a recorded, explicit deviation from the two-labeler design,
  not a resolution — the resulting kappa will not be a genuine inter-rater statistic. Still BLOCKS
  Stage-5 credit until the solo calibration actually completes.
- Escalate at: 2026-08-09T03:10:37Z

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
