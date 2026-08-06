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

## [ADR-007] Parse SKILL.md frontmatter with PyYAML safe_load
- Date: 2026-07-13
- Status: accepted
- Context: L1 capture must parse the YAML frontmatter of submitted SKILL.md files. Frontmatter can be
  arbitrary YAML and is UNTRUSTED submitter input.
- Decision: Add `pyyaml>=6` and parse frontmatter with `yaml.safe_load` (never `yaml.load`, which can
  construct arbitrary Python objects). The body and files are stored as untrusted content and never
  executed; Phase C scans them before publish.
- Alternatives considered:
  - Hand-rolled minimal frontmatter parser — rejected: fragile on real YAML (nested/quoted/list forms),
    and a parser bug on untrusted input is itself a risk.
- Consequences: One small, standard, hermetic dependency (no egress). `safe_load` must be used everywhere.
- Related: ADR-001, semiskill/capture/intake.py, plan §Phase B

## [ADR-008] SKILL.md conforms to the Agent Skills open standard; SemiSkill taxonomy moves under `metadata:`
- Date: 2026-08-05
- Status: accepted
- Context: SemiSkill reads flat frontmatter keys (`slug, function, role, level, owner, tags, version`)
  that are rejected by the Agent Skills open standard and by Anthropic's skill validator, both of which
  permit only `{name, description, license, compatibility, metadata, allowed-tools}`. Independently, the
  runtime the pilot team actually uses — Cursor 2.4+, which gained native Agent Skills support on
  2026-01-22 — requires `name` to be kebab-case and to equal the skill's parent directory name, and
  discovers skills purely by file placement (there is no install command). Our eight published seeds
  carry `name: RTL Onboarding for Freshers` and `slug: dv/rtl-onboarding-fresher`, so **no currently
  published SemiSkill skill can be loaded by Cursor**. Separately, the standard defines `allowed-tools`
  as a space-separated string, which `intake.py` iterates character-by-character, yielding ~10 unlisted
  "tools" and a stage-1 safety score of 0.000 — any spec-compliant submission scores zero today.
- Decision: One SKILL.md that is simultaneously spec-valid, Cursor-loadable and SemiSkill-ingestible.
  Frontmatter is restricted to the six standard keys; `name` is the kebab identifier and the directory
  name (replacing the slash-bearing `slug`); SemiSkill taxonomy moves under `metadata:` with
  `semiskill-`-prefixed keys. `intake.py` resolves each field `metadata["semiskill-<k>"]` →
  `metadata["<k>"]` → top-level `"<k>"` (backward compatible with the existing seeds), sources
  `payload["name"]` from `semiskill-title` so the catalog card stays readable with no schema migration,
  and parses `allowed-tools` from either a YAML list or a whitespace/comma-separated string. **The
  delivered bytes are the verified bytes**: packaging performs placement only, never rewriting.
- Alternatives considered:
  - Keep the flat keys and give up the standard's tooling — rejected: it gives up **Cursor**, the actual
    delivery target, not merely a packaging script, and forks us permanently from a standard that
    Cursor, Claude Code, Codex and VS Code have all adopted.
  - Emit two variants from one source (verified form + delivered form) — rejected: the file that passes
    the gate would not be the file the engineer runs, so the verification badge, the scan report and the
    rollback path would all describe bytes nobody executes. A transformer bug becomes a silent security
    regression that no test can close without reimplementing the pipeline, and a personalized fork could
    not be resubmitted through the gate without a lossy reverse transform.
- Consequences: The slash-slug convention retires; the eight published seeds are non-conformant and are
  **superseded, never deleted** (ADR-003) by the Phase H wave. The `intake.py` changes are additive and
  backward compatible — `tests/capture/test_intake.py` and `tests/seed/test_generated_seeds.py` must pass
  unmodified as the regression gate. Facet values become an enumerated, lint-validated vocabulary, because
  a typo under `metadata` is as silently unreachable as a top-level one. `allowed-tools` remains a
  governance declaration that stage 1 scores, even though Cursor does not enforce it at runtime — so the
  verification badge means "this text passed our scans on this date", never a runtime guarantee.
- Related: ADR-002, ADR-003, ADR-007; semiskill/capture/intake.py; cursor.com/docs/skills; agentskills.io

## [ADR-009] Waves are content-addressed and idempotent; generic skills publish as `public`
- Date: 2026-08-05
- Status: accepted
- Context: `seed_catalog` is a bare list comprehension with no error handling, no idempotency and no
  report: one malformed skill raises out and abandons the rest of the wave, a `request-changes`
  verdict returns `published=False` silently with no exception, and re-running a wave appends a
  second `skill_version` for the same slug and publishes it too — the catalog has no unique
  constraint on slug, so the duplicate is invisible. Separately, `seed_skill` never passes
  `permissions_label`, so every seeded skill is labelled `team`, while `api.py` defaults an
  unauthenticated caller to `public` — a successful wave therefore yields an empty-looking catalog.
- Decision: A wave is driven by `semiskill.wave.run_wave`, which is **content-addressed**: each item's
  canonical payload is hashed, and an already-published slug with an identical hash is skipped as a
  no-op, while a different hash publishes the new version and then unpublishes the old one through
  `governance.rollback.unpublish_skill` (publish-new-before-unpublish-old, so the catalog never has a
  hole). The catalog is therefore its own checkpoint and a wave is resumable with no side state.
  Item-level failures are isolated and recorded; infrastructure failures abort the whole wave.
  `request-changes` is reported as a failure, never silently. Generic, slot-bearing skills publish with
  `permissions_label="public"`; a personalized fork that contains team specifics publishes as `team`
  or `need-to-know`.
- Alternatives considered:
  - Skip any slug that already exists — rejected: a corrected skill would never reach the catalog, and
    the author would get no signal that their fix was ignored.
  - Always publish a new version and leave the old one — rejected: ADR-003 requires supersession, and
    two live cards with the same slug produce two different install instructions for one name.
  - A separate wave state/checkpoint file — rejected: a second source of truth about what published is
    a second thing to desynchronize from the artifact log.
  - Keep `team` as the wave label — rejected: it is factually wrong for content that contains no
    internal information, and it is the direct cause of the empty-catalog symptom. Making `public`
    mean "contains nothing internal" gives the label boundary real meaning.
- Consequences: `seed_catalog` is deleted rather than fixed, so no call site can pick the unguarded
  path by accident; `seed_skill` gains `permissions_label` and `files` parameters. Supersession relies
  on `unpublish_skill`, which requires the old published approval id, so the driver must resolve the
  active approval for a slug — the same active-approval-wins rule `derive_state` uses. Waves must be
  run against a catalog database, never the test DSN, and `scripts/demo.py` (which TRUNCATEs) is
  retired to `archive/`.
- Related: ADR-002, ADR-003, ADR-008; semiskill/wave.py; semiskill/governance/rollback.py

## [ADR-010] The catalog describes installation as file placement; `skills add <slug>` is retired
- Date: 2026-08-05
- Status: accepted
- Context: Every catalog card, the detail payload, the demo UI and `docs/ADOPTION.md` told the reader
  to run `skills add <slug>`. No such command exists anywhere in this repo, on this machine, or in any
  registry that knows our slugs — it was a literal f-string asserted only by string-equality tests.
  Meanwhile the actual runtime, Cursor 2.4+, has no install command at all: it discovers skills by
  walking `.cursor/skills/`, `.agents/skills/` and their `~` equivalents for any `SKILL.md`
  (ADR-008). Teaching an engineer a command that does not exist is worse than teaching them nothing,
  because it burns the first thirty seconds of their first encounter with the catalog.
- Decision: Replace the `install` string with a structured object describing what actually happens —
  `{method: "file-placement", path: ".cursor/skills/<name>/SKILL.md", invoke: "/<name>", instruction}`
  — and reword every consumer to match. Installation is placing a folder; the site additionally
  offers a copy-the-prompt path so the engineer's own agent writes the file, which works over SSH
  where a download folder is unreachable.
- Alternatives considered:
  - Implement a `semiskill add` CLI — rejected for now: it would have to reach a hosted service that
    does not exist, and it duplicates what the runtime already does by reading a folder. The honest
    artifact is the folder.
  - Leave the string and document the gap — rejected: `docs/ADOPTION.md` already carried the claim,
    and a documented lie is still the first thing a new user tries.
- Consequences: `api.py` and `context/retrieve.py` change a public response field, so the API tests
  assert the object rather than a string. `ui/catalog-demo.html` and `ui/README.md` retain the dead
  string only until they are archived (they are superseded by `semiskill site`).
- Related: ADR-002, ADR-008; semiskill/api.py; semiskill/context/retrieve.py; cursor.com/docs/skills

## [ADR-011] Project verified publication through a capability-separated append-only actuator
- Date: 2026-08-06
- Status: accepted
- Context: Approval JSON stored beside ordinary artifacts was mutable only by convention and catalog
  readers could mistake a forged, stale or contradictory record for an active publication. Runtime,
  ACL clearance and approval operations also shared one database identity, so application code held
  more authority than its read path required.
- Decision: The catalog recognizes only rows in `verified_publication_events`, written atomically by
  a `SECURITY DEFINER` actuator after deterministic validation of the exact skill hash, registry
  facets, immutable scan/review chain, authenticated human decision, environment policy and monotonic
  correction lineage. Runtime, clearance and actuator use distinct login capabilities; production
  requires Entra/OIDC claim binding, while local OS identity is development-only. The test-only
  unregistered-fixture exception is constrained to a database whose name ends in `_test`.
- Alternatives considered:
  - Treat any well-shaped approval artifact as published — rejected because an ordinary artifact
    append could forge a badge or detach it from evidence.
  - Let application code choose the newest approval — rejected because duplicate heads, branches and
    clock/order ambiguity require deterministic quarantine, not a heuristic winner.
  - Share one database login and rely on call-site discipline — rejected because a compromised read
    path would inherit publication and ACL authority.
- Consequences: Every catalog consumer reconciles typed projection rows with frozen artifacts and
  fails closed on orphan, drift, duplicate-head or topology anomalies. Approval activation needs a
  separately configured actuator DSN outside tests; production stays unavailable until Entra and
  capability credentials are supplied. Migration checksum adoption is explicit and never silently
  blesses legacy NULL checksums.
- Related: ADR-002, ADR-005, ADR-009, J-009c1;
  semiskill/artifacts/migrations/0011_verified_publication_projection.sql;
  semiskill/governance/reconciliation.py

## [ADR-012] Materialize offline exports through one exact-label database capability
- Date: 2026-08-06
- Status: accepted
- Context: Static files cannot enforce ACLs after download, and filtering an owner-level all-label
  result in Python would disclose restricted payloads before the filter. A caller-supplied label or
  a constructible principal record is not sufficient authorization for a distributable export.
- Decision: Every export is authorized by a resolver-issued principal and read through a distinct
  `semiskill_export_reader` login that holds exactly one label-marker role. A bounded
  `SECURITY DEFINER` function selects that label before returning only active frozen evidence; the
  export then reconciles database identity, canonical snapshot, active heads, artifact IDs and
  payload hashes. Local OS identity can issue only a public scope; production requires Entra/OIDC.
- Alternatives considered:
  - Load all publications through the owner/runtime DSN and filter in Python - rejected because
    unauthorized bodies would already have crossed the query boundary.
  - Reuse the general ACL clearance login - rejected because downloadable materialization is a
    narrower capability and needs an exact single-label credential, not a multi-label query session.
- Consequences: `SEMISKILL_EXPORT_DATABASE_URL` is required outside isolated tests and must identify
  a separate login with exactly one marker role. Restricted exports use separately provisioned
  credentials; missing or multi-label capability fails closed. Export scope stamps contain a
  one-way principal reference, never the raw employee subject or authentication context.
- Related: ADR-002, ADR-005, ADR-011, J-010a1;
  semiskill/artifacts/migrations/0012_scoped_export_reader.sql;
  semiskill/authoring/export_scope.py

## [ADR-013] Legacy migration adoption is a commit-bound witnessed operation
- Date: 2026-08-06
- Status: accepted
- Context: The development database predates checksum tracking: migrations 0001-0010 are recorded
  with NULL hashes and a historical test probe appears in the tracker. Silently filling those hashes
  would bless unknown history, while generic migration bootstrap previously had enough authority to
  touch a catalog database.
- Decision: Legacy adoption is a two-step human operation: a read-only plan binds an exact clean Git
  commit, tracked migration set, trusted raw hashes, deep pre-schema witness, database/environment
  identity and optional exact empty probe removal; execution requires the plan digest, replans under
  locks, applies the pending suffix and appends one immutable gate-decision artifact in one transaction.
  Generic `apply_migrations` is test-database-only. The explicit contract is
  `SEMISKILL_MIGRATION_DATABASE_URL`, `SEMISKILL_MIGRATOR_ROLE`,
  `SEMISKILL_DEVELOPMENT_DATABASE_NAME` and `SEMISKILL_PRODUCTION_DATABASE_NAME`.
- Alternatives considered:
  - Backfill NULL hashes automatically on startup - rejected because current files cannot prove the
    bytes that created historical state and a tampered tracker would become trusted silently.
  - Edit the tracker and remove the probe manually - rejected because cleanup, pending DDL and audit
    could diverge or partially commit.
  - Reuse the runtime `DATABASE_URL` - rejected because migration authority must be explicit and must
    fail closed on a wrong environment or database identity.
- Consequences: Migrations 0013-0015 protect authoritative tables from TRUNCATE, remove ambient
  capability memberships, revoke public schema creation, pin every SECURITY DEFINER search path and
  protect the publication projection. Loopback development may use the owner for this one witnessed
  adoption but earns no production-separation credit; production remains blocked until a dedicated
  migrator and Entra/OIDC identity are configured.
- Related: ADR-011, ADR-012, J-010a7; semiskill/artifacts/migrate.py;
  semiskill/artifacts/legacy_migration_manifest.json

## [ADR-014] Dashboard catalog credit requires an observation-bound live trust witness
- Date: 2026-08-06
- Status: accepted
- Context: A semantically self-consistent scoreboard could be restamped, sourced from another path,
  outlive its Git/database state, or omit top-level `_shared` bytes. The browser also compared an
  abbreviated commit itself while still rendering counts, and migration adoption was display-only
  historical evidence rather than a current schema gate.
- Decision: `semiskill.scoreboard/v2` binds `generated_at` into its identity and records both
  per-skill payload and complete `skills/**` input-tree hashes. The DV command centre accepts only
  the fixed 84-active/20-declined/16-role scope, canonical paths, an exact clean HEAD checked before
  and after live recomputation, the configured database state, an exact migration tracker and
  current structural attestations. Scoreboard/progress age is bounded by
  `SEMISKILL_SCOREBOARD_MAX_AGE_SECONDS` and `SEMISKILL_PROGRESS_MAX_AGE_SECONDS` (15-3600 seconds).
  Only an allowlisted migration/adoption projection reaches the browser.
- Alternatives considered:
  - Keep v1 and apply age checks outside its hash — rejected because a copied file could be
    restamped without changing its purported observation identity.
  - Let the browser compare Git/database labels — rejected because presentation code is not a trust
    boundary and already rendered authoritative counts after mismatch.
  - Hash only discovered skill payloads — rejected because shared instructions affect all 84 skills
    and must invalidate the source witness even before their approval topology is resolved.
- Consequences: Every v1 report is non-crediting and must be regenerated; an expired report or dirty
  worktree intentionally hides catalog counts. State-only commits also require a fresh snapshot.
  The separate `_shared` approval topology remains release-blocking until its bytes are part of every
  affected scan/review/approval chain.
- Related: ADR-011, ADR-013, J-010a9; dashboard/server.py;
  semiskill/authoring/snapshot.py

## [ADR-015] Dashboard mutations are queue-only and cannot invoke command actuators
- Date: 2026-08-06
- Status: accepted
- Context: Loopback-only binding and a fixed command allowlist did not make browser-triggered test,
  container or process execution a safe control plane. A cross-site request, duplicate click or
  compromised dashboard could invoke mutable repository code outside the repository and database gates.
- Decision: The dashboard exposes no mutation route that runs commands. Mutation controls can only
  request work through the audited queue; any worker executes it separately under normal locking,
  identity, isolated-database and evidence gates. Bounded read-only state probes remain presentation
  inputs and cannot earn verification credit.
- Alternatives considered:
  - Retain a fixed command allowlist - rejected because the allowed commands still execute mutable
    repository code and can race the serial database-test contract.
  - Keep execution behind a loopback check - rejected because DNS rebinding and cross-site requests
    make network location alone an insufficient authorization boundary.
- Consequences: `/api/run` and `/api/runs` are retired. Queue hardening is a separate required gate;
  until J-010b2 passes, queued requests are untrusted and must not be consumed automatically.
- Related: ADR-014, J-010b1; dashboard/server.py; dashboard/index.html

## [ADR-016] Dashboard feedback is a same-origin template-bound non-crediting journal
- Date: 2026-08-06
- Status: accepted
- Context: A queue-only UI still accepted browser-supplied prompt text and mutable identifiers, so a
  cross-site request, model drift or interrupted append could manufacture work that appeared to come
  from a curated command-centre action. Plain JSON writes and rotation also lacked a recoverable
  commit boundary, global lineage checks and durable request receipts.
- Decision: The only dashboard mutation APIs are `POST /api/action` and
  `POST /api/inbox/archive`. They require an exact same-origin Host/Origin, a per-process CSRF token,
  strict JSON framing and a canonical request UUID; the server selects the exact action from an
  integrity-pinned in-process template and journals it under a cross-process lease with fsync,
  atomic replacement, deterministic receipts and restart reconciliation. Queue and archive records
  explicitly carry `credit:none` and can never satisfy scan, review, approval, publication, test or
  launch gates.
- Alternatives considered:
  - Accept a browser-supplied prompt or arbitrary task body — rejected because untrusted page state
    could widen worker scope or forge a curated request.
  - Execute a fixed command directly from the dashboard — rejected because a loopback UI is not an
    authorization boundary and execution would race repository/database governance.
  - Treat the adjacent SHA-256 pin as an authenticity signature — rejected because it is unkeyed;
    host and repository ACLs remain the trust root for direct filesystem writers.
- Consequences: Restart invalidates browser CSRF state and uncertain requests retry by the same UUID.
  A separate worker must consume requests under the normal repository lock, tool/network limits and
  evidence gates. Cooperative leases protect consistency, not malicious direct writers; deployment
  must restrict filesystem write access. No queue count or receipt may be shown as completed work.
- Related: ADR-014, ADR-015, J-010b2; dashboard/action_queue.py; dashboard/server.py;
  dashboard/index.html

## [ADR-017] Dashboard state reads cannot execute tests or network health probes
- Date: 2026-08-06
- Status: accepted
- Context: `/api/state` executed `pytest --collect-only`, `docker info` and an environment-controlled
  HTTP health request on every cache miss. Collection imports test and plugin code, Docker can target
  a remote daemon, and the HTTP target created an egress/SSRF surface; failure also caused a static
  function count to be mislabeled as collected tests.
- Decision: Request-time state reads expose only static test-function inventory and bounded Git plus
  read-only database observations. The response retires `repo.collected_tests`, `runtime.docker` and
  `runtime.api`; `SEMISKILL_API` is no longer a dashboard environment contract. Full-suite PASS/FAIL
  may appear only from a separately produced, source/tree/test-database-bound immutable run record.
- Alternatives considered:
  - Cache pytest collection — rejected because the first request and every failed/zero collection
    still executes arbitrary import/plugin code and cache races do not create verification evidence.
  - Keep Docker and API probes behind loopback — rejected because environment configuration can
    redirect them and a presentation GET must not trigger unrelated process or network work.
  - Treat static `def test_` discovery as a test result — rejected because parametrization,
    collection errors, fixtures and execution outcomes are unobserved.
- Consequences: The dashboard shows a smaller but truthful health surface and calls its source count
  “test functions.” Until a trusted external runner writes the strict evidence contract, full-suite
  status remains unavailable even when a console run succeeded. Git observations remain bounded
  subprocesses and must not be confused with test execution.
- Related: ADR-014, ADR-016, J-010b3a; dashboard/server.py; dashboard/index.html

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
