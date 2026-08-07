# SemiSkill — Adoption Guide

How to publish, verify, discover, and reuse skills. Nothing you submit becomes discoverable until it
passes the pipeline **and** a human approves it — by design.

## For authors — publish a skill
1. Write a skill directory with a `SKILL.md` using the frontmatter contract in
   `docs/AUTHORING_CONTRACT.md`, plus any local text helpers. Do not add governance files or a local
   `_shared` shadow. The canonical three-file shared source is snapshotted by capture.
2. Submit it:
   ```bash
   semiskill submit ./my-skill --actor you@corp --label team
   ```
   State becomes **submitted** — not published. You cannot publish your own skill (structurally).
3. The pipeline records stages 1/2/3/4/5 and a stage-6 aggregate. Stage 5 is calibrated and may say
   `not sampled`; it must never be displayed as a pass when skipped. If a scan hard-fails (dangerous tool, injection lure, embedded
   secret, executable payload…), it is **blocked at the gate** and quarantined with a full artifact
   trail. Fix the finding and resubmit as a new version.
4. If the aggregate verdict is `approve`, it enters the independent content-review queue. Typed P1
   and fresh P5 review artifacts bind the exact shared-inclusive payload. Deterministic readiness
   requires passing checks and zero open/disputed blocking findings before human approval is offered.

**Tips to pass:** declare only the tools you need (avoid `Bash`/`Exec`); never embed credentials or
internal URLs; keep the body free of "ignore previous instructions"-style directives and encoded
payloads; bundle source, not binaries.

## For approvers — the human gate
- The approval queue (`GET /queue`) is ranked **risk-first** (lowest aggregate safety at the top).
- Each item shows the verdict, aggregate safety, and per-stage scan results — the scan report that
  ships with the skill.
- Approving runs the authenticated decision boundary (`governance.publish.decide_publication`). It
  re-checks the exact version/hash, required scan chain, independent content review, permissions,
  actor identity, decision, and reason before the verified projection can become discoverable.
- To pull a published skill, append an authenticated unpublication correction. The immutable prior
  evidence remains auditable while the active projection is removed.

## For everyone — discover & reuse
- Browse the catalog (SharePoint page / read API `GET /catalog?q=&function=&role=&level=`): faceted by
  function / role / level, full-text search, every card leading with its **verification badge**.
- Open a skill for its README, allowed tools, scan report, provenance (submitted → … → published),
  version history, comments, and rating.
- Reuse it by **placing the complete approved folder**: `SKILL.md`, local helpers, and the vendored
  `_shared/` support files listed in its install inventory. Put that self-contained skill directory
  in `~/.cursor/skills/` (or your project's `.cursor/skills/`), reload, and type `/<name>`. There is
  no install command — Agent Skills runtimes discover skills by walking that directory (ADR-010).
- The installed `_shared/` directory belongs to that one approved skill payload; it is not a global
  writable store. Editing any delivered file removes the verification guarantee until the fork is
  resubmitted through scans, independent review, and human approval.
- You only ever see skills your clearance allows — a `need-to-know` skill is invisible to those
  without it.

## For operators - reviewed development schema checkpoint

Generic migration bootstrap is restricted to isolated `*_test` databases. An already-adopted
development catalog advances only through an explicitly coded checkpoint policy. The current policy
is exactly `0015_projection_truncate_hardening.sql` to
`0023_review_unbound_parameter_binding.sql`; a different start or end fails closed.

The repository must be clean and committed. Configure the four non-secret identity selectors and
the migration-owner DSN shown in `.env.example`, then create a read-only, operator-and-reason-bound
plan:

```powershell
python -m semiskill.cli migrate-forward `
  --expected-database semiskill `
  --environment development `
  --repo-root . `
  --reason "Reviewed the exact 0015 to 0023 review-authority checkpoint." `
  --plan-out reports/migrations/0015-to-0023.json
```

Planning changes no database state and refuses to replace a different plan file. Review the complete
JSON, including source commit, database identity, operator hash, reason, prior audit, exact pending
bytes, pre-attestation and post-attestation contract. Only then execute the same plan with the exact
same reason:

```powershell
python -m semiskill.cli migrate-forward `
  --expected-database semiskill `
  --environment development `
  --repo-root . `
  --reason "Reviewed the exact 0015 to 0023 review-authority checkpoint." `
  --plan-file reports/migrations/0015-to-0023.json `
  --expected-plan-sha256 sha256:<digest-from-the-reviewed-plan> `
  --yes
```

Execution reacquires the OS identity, rebuilds the plan under database locks, applies the exact eight
migrations and appends one deterministic, chained audit artifact in the same transaction. A changed
operator, reason, source, tracker, database, migration byte or attestation rolls back everything.
An ambiguous retry returns the original exact audit only; a final tracker without that audit is
treated as corruption. Production is intentionally unavailable until the Entra/OIDC migration
adapter and distinct production migrator are configured.

## Roles at a glance
- **Author** → submits; cannot publish.
- **Approver** → the human signoff that opens the gate; can also unpublish.
- **Everyone** → discovers + reuses within their ACL.
