# SemiSkill — Adoption Guide

How to publish, verify, discover, and reuse skills. Nothing you submit becomes discoverable until it
passes the pipeline **and** a human approves it — by design.

## For authors — publish a skill
1. Write a skill directory with a `SKILL.md` (YAML frontmatter: `name`, `slug`, `description`,
   `function`, `role`, `level`, `tags`, `allowed-tools`) + any helper files.
2. Submit it:
   ```bash
   semiskill submit ./my-skill --actor you@corp --label team
   ```
   State becomes **submitted** — not published. You cannot publish your own skill (structurally).
3. The pipeline scans it (six stages). If a scan hard-fails (dangerous tool, injection lure, embedded
   secret, executable payload…), it is **blocked at the gate** and quarantined with a full artifact
   trail. Fix the finding and resubmit as a new version.
4. If the aggregate verdict is `approve`, it enters the **review queue** for a human approver.

**Tips to pass:** declare only the tools you need (avoid `Bash`/`Exec`); never embed credentials or
internal URLs; keep the body free of "ignore previous instructions"-style directives and encoded
payloads; bundle source, not binaries.

## For approvers — the human gate
- The review queue (`GET /queue`) is ranked **risk-first** (lowest aggregate safety at the top).
- Each item shows the verdict, aggregate safety, and per-stage scan results — the scan report that
  ships with the skill.
- Approving runs the **publish actuator** (`governance.publish.publish_skill`): it re-checks the
  verdict is `approve` and no hard-fail scan is in the chain, then writes the published `approval`.
  Only then is the skill discoverable.
- To pull a published skill: **unpublish/quarantine** (`governance.rollback.unpublish_skill`) — a gated
  action that removes it from the catalog immediately.

## For everyone — discover & reuse
- Browse the catalog (SharePoint page / read API `GET /catalog?q=&function=&role=&level=`): faceted by
  function / role / level, full-text search, every card leading with its **verification badge**.
- Open a skill for its README, allowed tools, scan report, provenance (submitted → … → published),
  version history, comments, and rating.
- Reuse it by **placing the folder**: put the skill directory in `~/.cursor/skills/` (or your
  project's `.cursor/skills/`), reload, and type `/<name>`. There is no install command —
  Agent Skills runtimes discover skills by walking that directory (ADR-010).
- You only ever see skills your clearance allows — a `need-to-know` skill is invisible to those
  without it.

## Roles at a glance
- **Author** → submits; cannot publish.
- **Approver** → the human signoff that opens the gate; can also unpublish.
- **Everyone** → discovers + reuses within their ACL.
