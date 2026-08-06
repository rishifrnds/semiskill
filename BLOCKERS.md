<!--
Active blockers ONLY. Delete entries the moment they resolve — log the
resolution in MEMORY.md as a step with `resolves: BLK-NNN`.
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

<!-- Note for the build phase — these are decisions to confirm with the user, not yet blockers:
  - SharePoint hosting model: SPFx web part vs. SharePoint list + embedded SPA vs. Power Platform.
  - Where the artifact store / pipeline runs (Azure Functions, container, on-prem) given egress control.
  - Which security scanners are in-scope for v1 (cloudflare/security-audit-skill + static + injection corpus).
Surface these as ADRs or questions when the build starts, per CLAUDE.md.
-->

<!-- Template for a new blocker — copy, fill in, append above this comment:
## [BLK-001] <short title>
- Raised: <ISO timestamp>
- Blocks: <STEP-ID | phase | project>
- Type: external-dependency | ambiguity | bug | missing-credential | decision-pending | user-input-needed
- Description: <2–3 sentences>
- What I tried: <bulleted list, or "nothing yet">
- What I need to unblock: <concrete action>
- Escalate at: <Raised + 48h, ISO timestamp>
-->
