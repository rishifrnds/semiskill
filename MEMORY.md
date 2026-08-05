<!--
Durable runtime state log for this project. Strict format — no prose-only entries.
Full rules and entry schemas: see STATE_RULES.md.
-->

## Project
- Name: SemiSkill — Internal Security-Verified Skill Marketplace
- Goal: One internal SharePoint-hosted place to publish/discover/comment/rate/reuse Agent Skills —
  every skill passing an automated security pipeline + human approval before publish.
- Started: 2026-07-13 · Repo: https://github.com/rishifrnds/semiskill · Architecture: AIOS 6-layer (E:\code\aios)
- Phase H plan (approved 2026-08-05): C:\Users\rishi\.claude\plans\the-problem-statement-is-generic-llama.md
- Session goal: make the catalog reach a real DV team — a Cursor-installable skill pack + a
  SharePoint-native catalog page, validated with real engineers before bulk authoring.

## Carry-forward from archives
Phases 0/A/B/C/D/E/F/G done → archive/MEMORY-{P0,A,B,C,D,E,F,G}.md. Built + green (183 tests):
- All 6 AIOS layers implemented + tested; gated publish; held-out corpus; red-team zero-escape;
  L5 stability/controller/cost; read API + UI scaffold; calibration report + docs; 8 seeded DV skills;
  `scripts/demo.py`; `dashboard/` command centre (G-006).
- Roles: semiskill_app / semiskill_submitter / semiskill_pipeline. ADRs 001-007. migrations 0001..0008.
- INFRA: Docker PG16 (127.0.0.1, fsync=off); shared-DB TRUNCATE tests; git enforcement in commit-msg hook.
- Pipeline verification helper: redteam/harness.run_case (submit → pipeline → publish attempt).
- GAPS: stage-2 live security-audit / stage-5 live judge / pgvector / SharePoint embedding need external
  resources (tested via fakes / demonstrated). No auth, nothing deployed, no CI, no backups.

### Phase H research findings (2026-08-05) — these reshape the delivery
- **Cursor 2.4+ (22 Jan 2026) supports Agent Skills natively.** Roots: project `.cursor/skills/`,
  `.agents/skills/`; user `~/.cursor/skills/`, `~/.agents/skills/`; legacy `.claude/skills/`,
  `.codex/skills/`. Required frontmatter `name` (kebab, **must equal the parent folder name**) +
  `description`; optional `paths`, `disable-model-invocation`, `metadata`. **No install command —
  installation is file placement.** ⇒ none of the 8 published seeds would load (title-case `name`,
  slash-bearing `slug`). ADR-008 resolves it.
- **SharePoint downloads uploaded `.html`; it renders `.md` natively** (rolled out Apr–May 2026). Every
  HTML workaround (Embed allow-list, Script Editor, SPFx) needs a site admin. ⇒ deliverable is a
  Markdown pack + a native Site Page of stock web parts, not `ui/` (which cannot build) and not
  `ui/catalog-demo.html` (100% fabricated data).
- **Authoring landmines measured empirically** (must score exactly 1.000 on stages 1/3/4 to publish):
  one bare `https://` ⇒ 0.70 ⇒ silently unpublished; `\bFunction\s*\(` is case-INsensitive so
  "transfer function (H(s))" ⇒ 0.15 reject; "run the following command" and "you are now a" are stage-3
  hard fails; `10.2.1.4` reads as a private IP; `NNN-NN-NNNN` reads as an SSN; a YAML ScannerError is
  not a ValueError and aborts a whole wave via `seed_catalog`'s bare comprehension.
- **`allowed-tools` as the open standard's space-separated string is iterated character-by-character**
  by intake.py ⇒ ~10 unknown tools ⇒ stage-1 safety 0.000. Any spec-compliant skill scores zero today.
- **New security finding:** a body containing `<<<END-UNTRUSTED-ARTIFACT-DATA>>>` escapes the fence in
  `context/untrusted.py`; nothing checks it (H-021).
- **Content model:** skills route on `description` alone, so level-in-the-slug is a routing failure and
  40 always-loaded skills cost ~3-4k tokens/session. Wave 1 = 6 task skills with role/level as *facets*;
  the role×level grid stays as the browse layout. Backlog = the ranked 53-cell matrix.

## Completed Steps
<!-- Append-only. Newest at bottom. -->

- [H-001] 2026-08-05T03:26Z  status: done
  what: ADR-008 — one SKILL.md that is simultaneously Agent-Skills-spec valid, Cursor-loadable and
  SemiSkill-ingestible: six standard frontmatter keys, kebab `name` == folder name (replaces the
  slash slug), taxonomy under `metadata:` with semiskill- prefixes, intake resolves
  metadata[semiskill-k] -> metadata[k] -> top-level k, `allowed-tools` parsed str-or-list, delivered
  bytes == verified bytes (packaging places, never rewrites)
  artifacts: DECISIONS.md ADR-008
  next: H-002

- [H-002/H-003] 2026-08-05T03:40Z  status: done
  what: intake.py implements the ADR-008 contract — `_str_list` parses `allowed-tools` from a YAML list
  OR the standard's space/comma-separated string (was iterated per CHARACTER: ~10 unlisted tools ->
  stage-1 safety 0.000, so every spec-compliant skill scored zero); `_field` resolves each taxonomy
  field metadata[semiskill-k] -> metadata[k] -> top-level k; payload name comes from semiskill-title
  while slug is the kebab spec `name`. 12 new tests; the 8 legacy seeds' tests pass UNMODIFIED
  artifacts: semiskill/capture/intake.py, tests/capture/test_intake.py, 195 tests green vs live PG
  next: H-004

- [H-004] 2026-08-05T03:52Z  status: done
  what: semiskill/authoring/lint_body.py — stdlib-only positional body linter (21 rules): stage-1 and
  stage-4 mirrors of the real scanner regexes with line/col/excerpt/fix, independently-authored
  ADVISORY phrasing rules for stage 3 (corpus deliberately NOT mirrored — this file ships to
  engineers inside the pack), plus L060 untrusted-delimiter escape, L062 credential-named slot,
  L034 oversize, L065 thin body. 26 tests incl. a near-miss negative per rule and an AST check that
  the module imports nothing outside the stdlib
  artifacts: semiskill/authoring/lint_body.py, tests/authoring/test_lint_body.py
  next: H-005

- [H-005/H-006] 2026-08-05T04:10Z  status: done
  what: semiskill/authoring/facets.py (enumerated function/role/level vocabulary + typo suggester;
  a facet typo is silently unreachable because catalog_search matches exact and case-sensitive) and
  semiskill/authoring/lint.py (frontmatter contract L005-L022 incl. kebab name == folder name,
  description trigger, tool allowlist, facet validity; scores taken FROM the real
  StaticStructureScanner/SecretPiiScanner and thresholds imported from pipeline, never copied;
  yaml.YAMLError surfaced as a finding instead of aborting a wave; duplicate-slug detection across a
  tree) + `semiskill lint` (needs no DB — cli.main only builds a store for commands that declare it)
  + the drift guard asserting linter and scanner fire on the same codes
  artifacts: semiskill/authoring/{facets,lint}.py, semiskill/cli.py,
  tests/authoring/{test_facets,test_lint,test_lint_drift}.py, tests/cli/test_cli.py — 295 tests green
  next: H-007

- [H-007/H-008] 2026-08-05T04:22Z  status: done
  what: first authored content — skills/_shared/failure-signature-schema.md (the normalisation rules
  four wave-1 skills will reference instead of restating) and skills/dv-sim-log-first-error/SKILL.md
  (ADR-008 frontmatter, 6 [[FILL:]] slots, an explicit retrieval budget for 100MB+ logs, verb-honest
  steps that never claim to run a tool, a design-vs-infrastructure split, gotchas, and a
  human-verification section naming what a wrong answer looks like) + docs/DV_INTAKE.md, the
  10-question intake for the DV manager. Both lint at aggregate 1.000 with zero advisories
  artifacts: skills/dv-sim-log-first-error/SKILL.md, skills/_shared/failure-signature-schema.md,
  docs/DV_INTAKE.md
  next: H-010 (wave driver)

## In-Flight Step
_(none)_

## Pending Steps
1. [H-001] ADR-008 — SKILL.md conforms to the Agent Skills open standard; taxonomy under `metadata:`
2. [H-002] intake.py: parse `allowed-tools` as str-or-list (fixes the 0.000 bug)
3. [H-003] intake.py: metadata facet fallback + `semiskill-title` display name (back-compat)
4. [H-004] semiskill/authoring/lint_body.py — stdlib-only body linter + rule table
5. [H-005] semiskill/authoring/facets.py — enumerated facet vocabulary
6. [H-006] semiskill/authoring/lint.py + `semiskill lint` + lint/scanner drift guard
7. [H-007] shared references (failure-signature schema, report schemas, triage buckets)
8. [H-008] author skill 1 + draft the intake questionnaire for the DV manager
9. [H-009] 3-day validation with her + two engineers (kill criterion agreed up front)
10. [H-010..H-013] wave.py driver: hash/dry-run, ADR-009, per-item isolation, idempotent supersede
11. [H-014..H-016] author skills 2-6, retire scripts/demo.py, run the wave
12. [H-017..H-022] pack.py, pack docs, ADR-010 truthful install, SharePoint generator, harden delimiter, backlog

## Current Phase
Phase H: Deliver a validated DV skill pack a Cursor user can install, plus a SharePoint catalog page

Exit criteria:
- One SKILL.md form is simultaneously Agent-Skills-spec valid, Cursor-loadable, and SemiSkill-ingestible
  (ADR-008), with the existing 8 seeds' tests passing unmodified
- `semiskill lint` catches every empirically-measured wave-killer offline, and its scores provably match
  the real scanners (drift guard)
- A wave of ≥6 DV skills published **only** via the gate (passing scan_run + approval, no back-door),
  re-runnable idempotently, with a wave report
- `semiskill pack` emits a Cursor-installable pack whose bytes are identical to what published
- A real DV engineer installs a skill in Cursor and it fires unprompted on a realistic phrasing
- `docker compose up -d db && pytest` all green
