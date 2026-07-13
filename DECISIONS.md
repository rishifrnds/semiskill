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

## [ADR-003] Seed the catalog with a role-based skill for every semiconductor role × level, via the pipeline
- Date: 2026-07-13
- Status: accepted
- Context: To be useful on day one, the marketplace must not launch empty. The company spans the full
  semiconductor org — Design & Verification, Physical Design, Analog/RF, CAD/EDA, Silicon Validation,
  Test, Process/Fab, Packaging, Reliability/Quality, Firmware/SW, Product, Program, Sales, Marketing,
  Finance, HR, Payroll, Ops, IT/Security, Legal/IP, Executive — across every seniority level (fresher
  through fellow/VIP/architect and lead through C-suite).
- Decision: Enumerate all roles×levels in `specs/ROLE_TAXONOMY.md` and generate one role-enablement
  Agent Skill each. Every seed skill is submitted through L1 and must pass the full L4/L6 verification
  pipeline + human approval before publish — no back-door catalog inserts. This is Phase G and dogfoods
  the pipeline. Generate in waves by function, Design/Verification first.
- Alternatives considered:
  - Bulk-insert seed skills directly into SharePoint — rejected: violates ADR-002 (gated publish) and
    would let an unverified generated skill go live.
  - Launch empty and rely on organic submissions — rejected: no day-one value; slow adoption.
- Consequences: Large generation workload (fanned out per function in ultra mode), but the catalog
  launches full, faceted by function/role/level, and every seed skill proves the safety gate works.
- Related: ADR-001, ADR-002, specs/ROLE_TAXONOMY.md, ULTRA_PLAN_PROMPT.md §Phase G

## [ADR-004] Host the catalog as a SharePoint-embeddable web app, not a native SPFx web part
- Date: 2026-07-13
- Status: accepted
- Context: The mission calls for a company SharePoint page "accessible to everyone", but the two
  reference marketplaces (skills.sh, the outskill app) are standalone web apps, and building/testing
  a native SharePoint Framework web part requires M365 tenant access and the SPFx toolchain we don't
  have on this machine. We need something buildable and demoable now.
- Decision: Build the catalog UI as a Next.js + shadcn/ui web app designed to embed into a SharePoint
  page via iframe (or a thin SPFx wrapper) later. The web app reads the L3 read model; the publish
  actuator remains the only writer (ADR-002). Records the "SharePoint hosting model" open decision.
- Alternatives considered:
  - Native SPFx web part in the tenant — rejected for v1: needs tenant access + SPFx toolchain; higher friction.
  - SharePoint list as data store + SPA — rejected: a SharePoint list can't enforce the artifact schema,
    append-only, or DB-role ACL that the safety gate depends on.
- Consequences: One extra embedding step to reach the literal SharePoint page, but the catalog is
  buildable/testable immediately and portable to any host.
- Related: ADR-001, ADR-002, ULTRA_PLAN_PROMPT.md §Phase E, plan §Phase E

## [ADR-005] Run the artifact store + verification pipeline on local Docker Postgres 16
- Date: 2026-07-13
- Status: accepted
- Context: CLAUDE.md mandates egress control (deny-by-default) and ACLs enforced at query traversal.
  AIOS (which we mirror) uses Postgres 16 + pgvector with SECURITY DEFINER functions and a restricted
  DB role for structural ACL. We need the same primitives.
- Decision: The store and pipeline run against a local Docker Postgres 16 (pgvector/pgvector:pg16),
  hermetic and egress-controlled. ACL is a DB privilege boundary (restricted role + SECURITY DEFINER
  functions), not application-level checks. A managed read-model may back the hosted catalog later.
  Records the "where the store + pipeline run given egress control" open decision.
- Alternatives considered:
  - Supabase (managed Postgres) — deferred: introduces external egress to control; keep for a later hosted read-model.
  - SQLite / local file — rejected: the DB-role ACL + SECURITY DEFINER patterns don't port, weakening the safety boundary.
- Consequences: Requires Docker locally (present); integration tests need a live Postgres, gated behind
  a pytest `integration` marker and a disposable-DB-per-test fixture (mirrors AIOS).
- Related: ADR-001, DATABASE_URL env contract, ULTRA_PLAN_PROMPT.md invariant #5, plan §Phase A/C

## [ADR-006] v1 scanner scope is all six pipeline stages, wiring locally-installed security skills
- Date: 2026-07-13
- Status: accepted
- Context: The pipeline spec (ULTRA_PLAN_PROMPT.md §Security Pipeline) defines six stages. The named
  `cloudflare/security-audit-skill` is NOT installed on this machine, but functional equivalents are
  (`security-audit`, `security-scan`, `detecting-indirect-prompt-injection`, `testing-prompt-injection-in-rag-pipelines`,
  `auditing-mcp-servers-for-tool-poisoning`).
- Decision: v1 covers all six stages — (1) static structure, (2) security-audit, (3) injection/policy
  vs. held-out corpus, (4) secret/PII, (5) calibrated LLM-as-judge, (6) L5 verdict aggregation —
  substituting the local `security-audit`/`security-scan` skills for the uninstalled Cloudflare skill.
  Within Phase C the ship order is deterministic stages 1/3/4 + human gate first, then stage 2, then
  stage 5 (LLM-judge) turned on only after κ≥0.6 calibration (CLAUDE.md principle 3, advisory-until-calibrated).
  Records the "which security scanners are in v1" open decision.
- Alternatives considered:
  - Core-4 (defer judge + L5) — rejected: the plan/user chose full scope; judge stays suggest-only until calibrated regardless.
  - Fetch the exact Cloudflare skill first — deferred: `npx skills add cloudflare/security-audit-skill` can be added later behind the same Scanner Protocol with no orchestrator change.
- Consequences: Stage 2's `npx` calls and any later Cloudflare-skill fetch require the egress-controlled
  sandbox with a pinned registry (per ADR-005); the LLM-judge cannot move a verdict until κ≥0.6.
- Related: ADR-001, ADR-002, ADR-005, ULTRA_PLAN_PROMPT.md §Security Pipeline, plan §Phase C

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
