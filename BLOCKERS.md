<!--
Active blockers ONLY. Delete entries the moment they resolve — log the
resolution in MEMORY.md as a step with `resolves: BLK-NNN`.
Full rules: see STATE_RULES.md.
-->

No active blockers as of 2026-07-13.

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
