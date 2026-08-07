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
