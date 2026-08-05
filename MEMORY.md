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

- [H-010..H-013] 2026-08-05T04:48Z  status: done
  what: ADR-009 + semiskill/wave.py + `semiskill wave-plan|wave`. Content-addressed and idempotent:
  identical slug+hash is skipped (the catalog is its own checkpoint, so a wave is resumable with no
  side state), changed content publishes then supersedes the old via unpublish_skill in that order
  (never leaving the catalog with a hole). Item errors are isolated and recorded; infrastructure
  errors abort with the item they died on. `request-changes` is now a reported failure instead of a
  silent published=False. seed_skill gained permissions_label/files; seed_catalog DELETED so no call
  site can pick the unguarded path. CLI refuses to write to the test DSN without --yes because the
  pytest fixture TRUNCATEs artifacts. 15 wave tests incl. the two failure modes this exists to fix
  artifacts: DECISIONS.md ADR-009, semiskill/wave.py, semiskill/seed.py, semiskill/cli.py,
  tests/wave/test_wave.py — 310 tests green
  next: H-014 (author skills 2-6 — a Workflow fan-out is running), then H-016 run the wave

- [H-014..H-016] 2026-08-05T05:05Z  status: done
  what: wave 1 authored and PUBLISHED through the real gate. Six task-based DV skills (sim-log
  first-error, regression triage+routing, build/filelist hygiene, repo orientation, RAL bring-up,
  minimal reproducer) generated by a Workflow fan-out against the ADR-008 authoring spec, each
  iterated to lint 1.000 with zero advisories. `semiskill wave` published all six at aggregate 1.000
  into a dedicated catalog DB (semiskill_catalog, so the pytest TRUNCATE cannot destroy it), each
  carrying a passing 3-stage scan_run chain + a real published approval. Verified live: an anonymous
  `public` caller sees all six, role/level facets and full-text search return them, and the detail
  payload carries the real per-stage verification report
  fix: cmd_wave built its store from the environment default, so --dsn steered the pipeline while
  artifacts silently landed in another database — the store is now resolved from the same dsn
  artifacts: skills/*/SKILL.md (6), reports/wave-*.md, semiskill/cli.py
  next: H-017 (pack builder)

- [H-017/H-018] 2026-08-05T05:25Z  status: done
  what: semiskill/authoring/pack.py + `semiskill pack` — the last mile. What goes in the pack is
  decided by the CATALOG (only skills whose active approval says published), never the filesystem, so
  a blocked skill structurally cannot reach an engineer. Packaging PLACES bytes (shutil.copy2) and
  refuses outright if the source has drifted since it published, so nothing ever ships carrying a
  badge it did not earn — verified live: it refused, the wave was re-run, then it packed. Ships
  README-INSTALL.md (the real Cursor paths; states plainly that the badge is not a runtime guarantee
  because Cursor does not enforce allowed-tools), PERSONALIZING.md, _shared/, MANIFEST.json with a
  checksum of the DELIVERED bytes, and tools/lint_body.py so a fork can be checked inside the
  firewall. 10 pack tests
  fix: the manifest hashed newline-normalised text, so its checksum would not have matched the file
  a recipient actually holds — it now hashes the delivered bytes
  artifacts: semiskill/authoring/pack.py, semiskill/cli.py, tests/authoring/test_pack.py,
  dist/semiskill-dv.zip (6 skills, 44 fill-in slots, 48K) — 320 tests green
  next: H-019..H-022 (truthful install string, SharePoint catalog generator, delimiter hardening)

- [H-014b] 2026-08-05T06:05Z  status: done
  what: content remediation after an adversarial review returned "NOT ready to publish as a set" on
  the six wave-1 skills. Round 1 fixed real technical errors (bit-bash is bidirectional, not a walking
  one; UVM map endianness orders bus words of a wide register and does NOT govern bit position; the
  "unmapped register resolves to the block base" mechanism was fabricated; the determinism cause list
  was wrong; build-filelist's flatten step was unexecutable under its own retrieval budget;
  repo-orientation asserted a mixed-vendor tool-flag grab bag as universal). The re-review then found
  round 1 had INTRODUCED a bug: consolidation was done as prose cross-references and 3 of 4 were
  factually wrong about which facts were "the same" while telling the team to fill once and reuse —
  propagating wrong marker strings. Fixed structurally with skills/_shared/team-profile.md (the facts
  filled ONCE) + corrected pointers, NOACCESS row (a NOACCESS field IS mapped), build-filelist's
  sequential-print claim re-qualified, and the golden brought up to the set standard (pasted-input
  branch, coverage line, staggered review-by, consistent compatibility). All 6 re-published via the
  gate at 1.000 and re-packed
  honest status: 2 of 6 (dv-ral-bringup, dv-regression-triage-routing) the reviewer would hand over
  today; the set needs one more focused pass — remaining issues listed in STATUS.md
  artifacts: skills/_shared/team-profile.md, skills/*/SKILL.md (6, v1.1.0), dist/semiskill-dv.zip
  next: H-019..H-022, and a third content pass before anything reaches a real DV team

- [H-020] 2026-08-05T06:40Z  status: done
  what: semiskill/authoring/catalog_page.py + `semiskill catalog` — the browsable page, generated
  from the published catalog so nothing on it can be fabricated. Three artifacts because the places
  people look have different constraints: catalog.md (SharePoint renders Markdown natively, so this
  is the entry point — an uploaded .html downloads instead), catalog.html (rich, self-contained, zero
  network, shadcn/tweakcn dark: search, role/level facets, role×level coverage matrix where an empty
  cell is an explicit invitation to contribute, detail view with the REAL per-stage scan report, and
  a copy-install-prompt button that writes the skill into .cursor/skills/ via the agent), and
  catalog.csv (paste into a SharePoint list for grouped browse with no code). Skill bodies are
  untrusted: the embedded JSON escapes `</` so a body cannot terminate its own data block, and a test
  asserts a hostile body cannot break out. A second test asserts the page fabricates nothing —
  ui/catalog-demo.html invented install counts, star ratings and an approver name
  artifacts: semiskill/authoring/catalog_page.py, semiskill/cli.py,
  tests/authoring/test_catalog_page.py (9), dist/site/{catalog.md,catalog.html,catalog.csv}
  verified: rendered in Chrome — 6 real skills, real scan scores, matrix, detail dialog. 329 green
  next: H-019 truthful install string, H-021 delimiter hardening, H-022 backlog, content pass 3

- [I-002/I-003] 2026-08-05T07:25Z  status: done
  what: Phase I infrastructure. semiskill/authoring/markdown.py — a deliberately RESTRICTED renderer
  for untrusted skill bodies: html.escape runs over the whole document before any parsing, so no tag
  a body contains can reach the output as markup; the parser then emits its own tags around
  already-safe text. Links and images render as inert text, never anchors. 23 tests, the security
  ones asserting a TAG ALLOWLIST (the right invariant — checking for the substring "onerror=" was
  wrong, since it is harmless once escaped). Escaping-first cost us the raw blockquote marker, so
  the quote regex matches the escaped form as well. semiskill/authoring/scoreboard.py +
  `semiskill scoreboard` — deterministic coverage of specs/skill_registry.json against the PUBLISHED
  catalog, never the filesystem and never an agent's claim: a skill on disk that never published
  counts as missing, a published skill with no independent recheck is `unreviewed` and fails
  --strict-gate, a published skill absent from the registry is a failure, and a declined cell counts
  toward a role's target only when it carries a reason. 11 tests
  artifacts: semiskill/authoring/{markdown,scoreboard}.py, semiskill/cli.py,
  tests/authoring/test_{markdown,scoreboard}.py — 363 tests green
  next: I-001 registry (top-up design workflow running), then I-004 site

- [I-001] 2026-08-05T07:32Z  status: done
  what: specs/skill_registry.json — the 84-cell plan of record. 53 cells from the research matrix
  (slugs normalised per ADR-008: no dv/ prefix, no level suffix, level is a facet) + 30 top-up cells
  designed by a 12-agent fan-out, one per under-served role, each agent explicitly permitted to
  DECLINE rather than pad. An adversarial audit rejected 1 of 31 as a cross-role duplicate
  (dv-security-requirement-traceability vs dv-safety-req-trace-audit — same method, same gap classes,
  only certification nouns differing, and those were already FILL slots), keeping the safety cell as
  canonical and leaving security honestly at 4/5. 83 active cells + 20 recorded declines.
  Two scoreboard rules this exposed: (1) a decline may only credit a role that has already published
  everything it planned, otherwise "we decided not to write a fifth" silently becomes "we are
  finished"; (2) facet drift — a published skill whose role/level disagrees with the registry — is a
  failure. On its first real run the drift check caught all 6 published skills, which is the exact
  regression the Phase-H remediation introduced and nothing had detected mechanically
  artifacts: specs/skill_registry.json, semiskill/authoring/scoreboard.py, tests (13)
  next: I-004 site, then wave 0 retrofit

- [I-004] 2026-08-05T07:52Z  status: done
  what: semiskill/authoring/site.py + `semiskill site` — the browsable catalog in the skills.sh
  shape: ranked index with client-side search, a real page per skill (breadcrumbs, install block with
  a copy-the-prompt button, the body rendered through the restricted renderer, a metadata panel
  carrying version/owner/blanks/size and the REAL per-stage scan badges where skills.sh puts installs
  and stars, plus more-in-role), per-role pages, the role x level matrix with linked cells, and an
  install guide. One stylesheet, relative links throughout, no CDN and no fetch, so the folder
  survives being zipped, emailed or downloaded from SharePoint. 15 tests including: an unpublished
  skill never reaches the site, every internal link resolves, no page reaches the network, no page
  carries a fabricated metric (regex-checked — `ui/catalog-demo.html` shipped "1.3k installs / star
  4.8"), and a hostile body stays inert on its own page
  three test-fixture bugs worth remembering: a bare "." matched the metric regex in "1. Download";
  a hostile body containing a URL never publishes (0.3 network-call) so it cannot be used to test the
  page; and `<script>` inside the JSON block is inert — only `</script` can terminate it
  artifacts: semiskill/authoring/site.py, semiskill/cli.py, tests/authoring/test_site.py,
  dist/site (14 pages) — 393 tests green
  next: wave 0 retrofit (the matrix currently shows 2 roles x 3 levels — the facet collapse, visible)

- [I-005] 2026-08-05T08:10Z  status: done
  what: closed the two Phase-H correctness debts. (1) context/untrusted.delimit could be FORGED: a
  body containing the literal close marker terminated the fence early and everything after it read as
  trusted text — json.dumps escapes quotes and backslashes but leaves `<` alone. Every `<` is now
  escaped to its JSON unicode form, which makes the marker unrepresentable inside the payload while
  round-tripping losslessly. (2) ADR-010 — `skills add <slug>` was a literal f-string asserted only by
  string-equality tests, naming a command that exists nowhere; Cursor has no install command at all
  and discovers skills by walking a directory. The API and detail payloads now return a structured
  install object {method: file-placement, path, invoke, instruction}, and docs/ADOPTION.md says what
  actually happens
  correction: the I-004 entry above records "393 tests green"; the real count at that commit was 380.
  No other figure in that entry is affected
  artifacts: semiskill/context/untrusted.py, semiskill/api.py, semiskill/context/retrieve.py,
  docs/ADOPTION.md, DECISIONS.md ADR-010, tests (+3)
  next: wave 0 recheck results, then waves 1-13

- [I-007 / wave 0] 2026-08-05T08:06Z  status: done
  what: wave 0 retrofit + the durable fix the review rounds pointed at. All six skills re-published at
  1.000 with registry facets RESTORED — the grid went from 2 roles x 3 levels back to 4 roles x 3.
  recheck-1 passed 3 of 6 (build-filelist, repo-orientation, ral-bringup); the other three I fixed by
  hand, then caught myself writing ready:true on my own fix — the exact Phase-H failure — reverted
  them to pending and ran an INDEPENDENT recheck-2, which failed all three and found two bugs my own
  edits had introduced (a third dangling `novelty` reference I missed, and a `post` enum widened in
  one skill that desynchronised the sibling claiming to match it mechanically).
  The pattern across four review rounds was always the same class: CROSS-FILE inconsistency. So
  semiskill/authoring/consistency.py now checks it deterministically — C001 slot declared but never
  used, C003 handoff enum differing across skills (error when a skill emits a value no sibling
  accepts, warn when merely narrower, since narrowing is often deliberate scoping), C004 prose
  referencing a value its field no longer has. It reproduced the reviewers' phase-enum finding in
  40ms, and `semiskill lint` now fails on a pack-level error so no wave can publish an inconsistent
  pack. 13 tests.
  Also fixed: build_pack recomputed the drift hash from SKILL.md alone, so every skill bundling a
  file (which is now every skill, since the gate writes REVIEW.json beside it) was falsely reported
  as drifted — it now rebuilds the payload from the whole directory as the wave does
  honest status: 3 of 6 carry unresolved recheck-2 findings and would fail --strict-gate
  artifacts: semiskill/authoring/consistency.py, semiskill/authoring/pack.py, semiskill/cli.py,
  skills/*/REVIEW.json (6), tests (+14) — 395+ green
  next: close recheck-2 findings, then waves 1-13

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
