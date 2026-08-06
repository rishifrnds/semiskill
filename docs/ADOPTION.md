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

## Roles at a glance
- **Author** → submits; cannot publish.
- **Approver** → the human signoff that opens the gate; can also unpublish.
- **Everyone** → discovers + reuses within their ACL.
