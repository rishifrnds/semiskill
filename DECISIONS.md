<!--
Append-only Architecture Decision Record (ADR). Never edit past entries.
Full rules (including the concrete ADR trigger test): see STATE_RULES.md.

Numbering is monotonic across the entire project lifetime (no reset on rotation).
To change a decision, add a new ADR with `supersedes: ADR-NNN`.
-->

# DECISIONS

## [ADR-001] Adopt AIOS 6-layer architecture as the SemiSkill backbone
- Date: 2026-07-13
- Status: accepted
- Context: SemiSkill must be safe, inspectable, and reversible from day one. AIOS (E:\code\aios)
  already defines a closed-loop, artifact-first, security-gated architecture with an L5 controller
  and L6 sensor. Reusing it avoids reinventing governance and gives us a proven layer separation.
- Decision: Structure SemiSkill as an AIOS instance across six layers — L1 Capture, L2 Spine+Artifacts,
  L3 Context, L4 Agents+Governance, L5 Intelligence, L6 Sensor — with the canonical append-only
  artifact schema and five-class event spine (Captured→Analyzed→Proposed→Executed→Observed).
- Alternatives considered:
  - Plain SharePoint list + manual review — rejected: no provenance, no injection defense, not queryable.
  - Off-the-shelf marketplace platform — rejected: can't enforce our verification gate or artifact schema.
- Consequences: More upfront structure, but every skill submission/scan/approval/reuse is an
  immutable, queryable artifact and publishing is a gated actuator, not a direct write.
- Related: CLAUDE.md, ULTRA_PLAN_PROMPT.md, E:\code\aios research/

## [ADR-002] Publishing to SharePoint is a gated actuator, never a direct write
- Date: 2026-07-13
- Status: accepted
- Context: The whole point is that skills are blocked today because unverified skills are dangerous.
- Decision: A skill can only reach the SharePoint catalog through the approval actuator after
  passing L6 scanners + L5 verdict + a human approval gate. Submitters never write the catalog.
  Every publish has a `rollback_ref` (unpublish/quarantine path).
- Alternatives considered:
  - Let authors publish and scan asynchronously — rejected: a malicious skill is live before the scan lands.
- Consequences: Slightly slower time-to-publish; guaranteed no unverified skill is ever discoverable.
- Related: ADR-001, ULTRA_PLAN_PROMPT.md §Security Pipeline

<!-- Template for a new entry — copy, fill in, append at the bottom:
## [ADR-NNN] <short decision title>
- Date: <YYYY-MM-DD>
- Status: accepted
- Context: <2–4 sentences>
- Decision: <1–2 sentences>
- Alternatives considered:
  - <option A> — rejected because <reason>
- Consequences: <trade-offs>
- Related: <STEP-IDs, ADRs>
-->
