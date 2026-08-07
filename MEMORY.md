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

- [I-006 launch] 2026-08-05T08:30Z  status: in-progress
  what: all 13 authoring waves launched — 77 skills, each through the full gate (author -> lint 1.000
  AND pack-consistency clean -> adversarial review by a code-reviewer agent -> fix -> INDEPENDENT
  recheck that never saw the fixer's reasoning). The wave engine is one reusable script
  (tools/dv-wave.js) invoked per role-wave with args, carrying the standing content rules distilled
  from every review round so far: verb honesty, no proprietary lookup, a retrieval budget the
  procedure actually obeys, markers must be slots, every slot must be spent, logs are files not chat
  text, state your own coverage, pack-wide facts referenced not re-asked. tools/collect_wave.py turns
  a wave journal into REVIEW.json per skill so the gate record is a file the scoreboard can read.
  fix: the first two launches returned instantly with zero agents — args arrived as a JSON STRING, so
  args.cells was undefined and the wave reported success having done nothing. The script now parses
  both forms and THROWS on an empty cell list; silently reporting an empty wave as a success is the
  worst failure mode available to a batch driver
  artifacts: tools/dv-wave.js, tools/collect_wave.py
  next: collect each wave, publish what is recheck-ready, scoreboard, site

- [J-001] 2026-08-05T12:20Z  status: done
  what: measured the real state of the 13 launched waves instead of trusting the launch record, and
  it is materially worse than the I-006 entry above implies. 83 skills are AUTHORED, but only 6 have
  a REVIEW.json at all (3 ready, 3 awaiting recheck-2) — the other 77 never got a gate record, so
  nothing has been adversarially reviewed or independently rechecked. The catalog database holds
  ZERO published registry skills; the site's "6 skills" is the whole published catalog.
  Then closed three tooling blockers that were silently gating everything downstream:
  (1) FACET VOCABULARY DRIFT — specs/skill_registry.json plans five cells each for
  memory-ip-dv-engineer, processor-ip-dv-engineer and eda-product-validation-engineer, but
  authoring/facets.py never learned those three roles. Consequence: 10 skills failed lint L019 with
  an unreachable facet, and 5 MORE had been quietly remapped to ip-dv-engineer by their authors to
  get past the linter — facet drift caused by the linter itself. Added the three roles (with the
  reason they are not folded into ip-dv-engineer recorded in the source); L019 10 -> 0, drift 5 -> 0.
  (2) C002 HAD ZERO PRECISION — `\b[A-Z][A-Za-z-]+(?: [a-z-]+){0,3} slot\b` matched any sentence
  starting with a capital and containing "slot", so "If a slot is unfilled" reported a slot named
  "If a". 105 findings on the real pack, 105 false. Fixed by stripping leading function words and
  requiring what remains to still start with a capital — a slot reference names a LABEL, and a
  capital that is merely sentence-initial is not one. 105 -> 1, and the survivor is genuine
  (dv-build-filelist-hygiene references an undeclared "Block-versus-top" slot). 8 regression tests.
  This is the same lesson as the earlier rounds: a rule that fires on everything hides the one real
  finding inside it, so it is worse than no rule.
  (3) the working copy's new C005 rule had broken an existing test (a fixture offering an enum no
  step assigns) — fixture corrected rather than the rule weakened.
  Also: the 10 C003 ERRORs are NOT drift. Measured across all 83 skills, only 16 handoff fields
  appear in more than one skill; `class` (44 skills) and `phase` (23) are genuine pack-wide
  vocabulary, but seven fields (chain, culprit, disposition, divergence, match, mechanism, ruling)
  appear in exactly 2 unrelated skills with COMPLETELY DISJOINT enums. C003 treats field-NAME
  identity as field identity, so it reports a name collision as drift. Handed to a design workflow.
  artifacts: semiskill/authoring/facets.py, semiskill/authoring/consistency.py,
  tests/authoring/test_consistency.py (+8), skills/{dv-csr-warl-access-audit,
  dv-custom-instruction-verification-plan,dv-mem-refresh-lowpower-audit,dv-memory-model-training,
  dv-trap-exception-triage}/SKILL.md facets restored, tools/dv-gate.js, tools/gate_args.py
  next: J-002 handoff vocabulary, J-003 gate the 80 unreviewed skills, J-004 publish + scoreboard

- [J-002] 2026-08-05T12:35Z  status: done
  what: closed the >=5-per-role gap the registry carried. security-verification-engineer had only 4
  active cells — three top-up candidates had been declined earlier on the design rubric (a secure-boot
  log-triage cell duplicated dv-sim-log-first-error; a side-channel RTL review needed a measurement a
  text tool cannot make; a requirement-traceability cell duplicated dv-safety-req-trace-audit). Those
  declines were right, so the fifth cell had to be genuinely different in METHOD, not in nouns. A
  design agent given the full decline record proposed dv-security-build-divergence-audit (principal):
  its unit is not a design object but a DIFFERENCE between two configurations — the build the security
  tests actually compiled versus the shipped device — swept in five classes (compile-time guards,
  boundary inputs tied to their safe value, behavioural stand-ins for fuse/entropy/key-store,
  testbench reach-in past the control under test, security counters shortened for speed) and then
  adjudicated benign/weakens/voids/unknown against a claim list the four existing security cells
  produce. That makes it a consumer of the role's other cells rather than a fifth variant of them.
  Registry now 84 active cells, all 16 roles at >=5. Note carried into authoring: its proposed
  handoff block used `class`, which is pack-wide vocabulary (44 skills) and must be renamed.
  artifacts: specs/skill_registry.json
  next: author it through the gate with the rest

- [J-003 partial] 2026-08-05T16:25Z  status: in-progress (stopped on the session token limit)
  what: four gate batches (48 skills) ran author-already-done -> adversarial review -> fix ->
  INDEPENDENT recheck. 44 completed a full pass and **0 were judged ready**. That is the honest
  headline and it is not a malfunction: the reviews are finding real defects no linter can reach --
  dv-signal-trace-localisation's only log window points AWAY from the value step 1 tells you to
  record (the pack's own schema puts "expected N got N" on the line AFTER the marker);
  dv-coverage-hole-disposition budgets 2 Greps for a step that needs 3, so a branch is unreachable
  and the procedure silently degrades to a weaker ranking rule, and it asserts "a failing test
  contributes no coverage" as universal fact when coverage is sampled regardless of verdict and
  merging is flow policy -- a claim the same skill handles correctly everywhere else.
  Round 1 also CONFLATED a nit with a blocker: reviewers listed date collisions and phrasing
  preferences beside genuine blockers and then failed the skill, so ready:true was unreachable by
  construction. tools/dv-gate2.js fixes the calibration -- every finding must be sorted into
  BLOCKING (would make an engineer take a wrong action, or a step cannot be executed) or
  NON-BLOCKING, ready:true iff BLOCKING is empty, with explicit instruction not to inflate a nit to
  look rigorous nor demote a real defect to look generous.
  the integrity fix that matters: ~40 agents died on the session limit, and collect_wave.py would
  have written ready:false for every one of them -- recording "an independent reviewer rejected
  this" when nobody looked, indistinguishable from a real rejection. It now SKIPS a skill with no
  recheck record entirely, so 17 skills stay "never-reviewed", which is true. A wave that dies
  halfway must leave no gate record rather than a false one.
  also closed two defects the fix agents INTRODUCED, which is why the pack check runs after every
  batch: an undeclared `phase` narrowing (C007) in dv-emulation-sim-mismatch-triage and a
  value-wearing-a-sentence (C009, wave-blocking) in dv-dfi-boundary-blame. And made the registry
  snapshot tests assert SHAPE -- every narrowing a proper subset, no name in two categories -- since
  the magic counts failed on correct work and taught you to bump them without reading.
  correction: I diagnosed 30 test failures as C006 erroring on identical fixture enums. Wrong. The
  cause was my own pytest racing an agent's against the shared dev DB, whose fixture TRUNCATEs
  `artifacts`. The C006 flaw was real and is fixed, but it was not what broke those tests.
  state: ready 3, not-ready-with-findings 32, never-reviewed 49, published 0. 456 tests green,
  zero consistency errors, all 84 at lint 1.000, findings 214 -> 62.
  artifacts: tools/dv-gate.js, tools/dv-gate2.js, tools/gate_args.py, tools/gate2_args.py,
  tools/collect_wave.py, skills/*/REVIEW.json (32), skills/_shared/handoff-vocabulary.md
  next: rerun round 2 over the 32, then the gate over the 49, then publish + scoreboard + site


- [J-006] 2026-08-05T17:05Z  status: done
  what: extracted the project's authoring contract into ONE file and wrote the learnings down.
  docs/AUTHORING_CONTRACT.md is now the single source of truth (what a skill is, the 13 standing
  rules with the defect each was written for, the mechanical lint-blockers, ADR-011 handoff
  vocabulary, ADR-008 frontmatter, body structure, the verify commands, the BLOCKING/NON-BLOCKING
  review calibration, and the gate). It had been pasted inline in tools/dv-wave.js, dv-gate.js and
  dv-gate2.js -- three copies of a contract is three contracts -- so all three now point at the file
  and inline only the mechanical constraints, since a lint failure wastes a whole agent run.
  bug caught while doing it: the pointer paths were written as Windows backslash paths inside a JS
  TEMPLATE LITERAL, where \c \V \s \d collapse to c V s d -- every path would have rendered as
  "E:codeVLSIsemiskilldocs...". Switched to forward slashes and verified all three parse and render.
  docs/LEARNINGS.md records why the rules exist: lint 1.000 is a SECURITY score; a rule with zero
  precision is worse than no rule (C002, 105/105 false); a linter can CAUSE the drift it catches
  (facets vs registry); field-name identity is not field identity (ADR-011); a governed value set
  must be exempt from local-reachability rules (C005 vs the registry); snapshot tests that pin
  current defects go stale when you fix them (assert shape or a ceiling instead); one fix pass then a
  strict recheck converges on zero; a wave that dies halfway must leave NO gate record rather than a
  false one; fix agents introduce defects so re-run check_pack after every batch; never run pytest
  while an agent runs it. Plus the four representative content defects the recheck found, and a table
  of every mechanism in this project that can record something that did not happen.
  HANDOFF.md carries a paste-ready resume prompt, the measured state, the ordered pending list and
  the full known-gaps list, so a new terminal can pick this up cold.
  artifacts: docs/AUTHORING_CONTRACT.md, docs/LEARNINGS.md, HANDOFF.md, tools/dv-{wave,gate,gate2}.js,
  CLAUDE.md (current phase), and 3 durable cross-session memories
  next: J-003a round 2 over the 32 not-ready, then J-003b over the 49 never-reviewed, then publish


- [J-007] 2026-08-06T06:44:11Z  status: done
  what: recovered the unrecorded workflow/prompt-library checkpoint and repaired stale session state
  after the user approved takeover; measured 84 authored, 83 predicted lint-pass, 35 review records,
  3 nominal ready, 0 registered published, 2 unregistered fixture publishes, and 455 tests collected
  artifacts: 2df246c, docs/WORKFLOW.md, docs/PROMPT_LIBRARY.md, STATUS.md, .session-lock
  next: J-008 harden the review and human-approval gates before any content batch


- [J-008a] 2026-08-06T06:49:58Z  status: done
  what: established the review/payload trust boundary with failing-first tests; root legacy
  REVIEW.json is no longer shipped, scanned, or included in source hashes, while every other skill
  file remains untrusted deliverable content
  artifacts: c78d410, semiskill/capture/intake.py, semiskill/authoring/lint.py,
  tests/capture/test_intake.py, tests/authoring/test_lint.py, tests/wave/test_wave.py
  next: J-008b implement hash-bound canonical review artifacts and deterministic readiness


- [J-008b] 2026-08-06T06:57:54Z  status: done
  what: implemented canonical content-review/v1 evidence bound to the exact installable payload,
  typed findings, continuous attempt lineage, independent fixer/reviewer identities and four
  required checks; readiness ignores agent claims and is derived from valid evidence with zero open
  blocking findings; security reviews have a separate discriminator and batch appends are atomic
  artifacts: d1b5b39, semiskill/authoring/gate.py, semiskill/capture/intake.py,
  semiskill/artifacts/store.py, semiskill/spine/pipeline.py, tests/authoring/test_gate_artifacts.py
  next: J-008c implement strict atomic collection and non-authoritative legacy migration


- [J-008c] 2026-08-06T07:04:15Z  status: done
  what: replaced the lossy file-overwrite collector with a strict max-10 batch contract and atomic
  artifact append, added non-authoritative legacy import/archive support, and isolated pytest in a
  guarded semiskill_test database; 110 targeted tests pass and dev artifacts stayed 3 before/after
  artifacts: 1134b7f, semiskill/authoring/review_collection.py, tools/collect_wave.py,
  tests/authoring/test_review_collection.py, tests/tools/test_collect_wave.py, tests/conftest.py,
  docker/postgres/init-test-db.sql
  next: J-008d execute legacy import/archive and close the temporary REVIEW.json compatibility seam


- [J-008d] 2026-08-06T07:06:42Z  status: done
  what: imported all 35 legacy file reviews into the dev artifact store as unbound,
  non-authoritative provenance (35 of 38 artifacts), moved each source record to a hash-addressed
  archive path, and made exact original SKILL.md text part of the canonical payload fingerprint
  artifacts: dea76c8, archive/content-reviews/, semiskill/capture/intake.py,
  semiskill/authoring/pack.py, development artifact IDs recorded by tools/collect_wave.py output
  next: J-008e make wave queue-only and reject embedded review metadata


- [J-008e] 2026-08-06T07:13:08Z  status: done
  what: converted wave into an exact-version capture/scan/content-reconciliation queue that exposes
  immutable approval inputs and cannot publish, unpublish, supersede or bypass review; embedded
  REVIEW.json now fails closed; stages 1/2/3/4/5 and stage-6 aggregate are recorded with truthful
  not_run/not_sampled states; 67 targeted queue/pipeline/capture/lint tests pass
  artifacts: d88e6d2, semiskill/wave.py, semiskill/spine/pipeline.py,
  semiskill/capture/intake.py, semiskill/cli.py, tests/wave/test_wave.py
  next: J-008f implement authenticated approval/v1 and make legacy approvals non-authoritative


- [J-008f] 2026-08-06T07:21:08Z  status: done
  what: implemented approval/v1 as the only catalog-authoritative publication decision, binding an
  explicit approve/reject to exact version/hash, security aggregate and scan IDs, latest canonical
  content review, reason and authenticated human identity; local CLI uses OS SID/uid, production is
  Entra-only/fail-closed, legacy callback APIs are tombstones, and unpublish is a correcting v1 row
  artifacts: 8936e12, semiskill/governance/identity.py, semiskill/governance/publish.py,
  semiskill/governance/rollback.py, semiskill/artifacts/migrations/0009_approval_contract.sql,
  semiskill/artifacts/migrations/0010_unpublish_contract.sql, semiskill/cli.py
  next: J-008g migrate development and reconcile every approval/badge consumer and test


- [J-008g] 2026-08-06T07:30:59Z  status: done
  what: replaced legacy callback and ungated publication fixtures in the API, catalog, pack, site
  and retrieval tests with a test-only complete approval/v1 evidence chain; the focused serial run
  passed 40 tests and isolated remaining failures to mutable latest-review badge consumers
  artifacts: 2b7366b, tests/support.py, tests/api/test_api.py,
  tests/artifacts/test_migration_0002.py, tests/context/test_retrieve.py,
  tests/authoring/test_catalog_page.py, tests/authoring/test_pack.py, tests/authoring/test_site.py
  next: J-008h freeze every export badge and pack manifest to the active approval evidence chain


- [J-008h] 2026-08-06T07:39:39Z  status: done
  what: added one fail-closed frozen approval-chain resolver and made active publication indexing,
  catalog, site and pack derive verification only from the exact approval-bound security review,
  content review and scan IDs; later scans/reviews cannot rewrite a badge and 46 focused tests pass
  artifacts: 0d4323a, semiskill/governance/publish.py, semiskill/wave.py,
  semiskill/authoring/gate.py, semiskill/authoring/catalog_page.py,
  semiskill/authoring/site.py, semiskill/authoring/pack.py
  next: J-008i remove remaining retired auto-publish and REVIEW.json assumptions, run full suite


- [J-008i] 2026-08-06T07:49:20Z  status: done
  what: removed the remaining automatic-publication and file-review assumptions from scoreboard,
  seed intake, controller queueing and red-team harnesses; declines are non-crediting provenance,
  valid published cells use frozen content evidence, and the full isolated suite is green
  artifacts: db89147, semiskill/authoring/scoreboard.py, semiskill/seed.py,
  semiskill/intelligence/controller.py, semiskill/redteam/harness.py, 486 passed, 1 xpassed
  next: J-009a build the canonical deterministic scoreboard snapshot and persistence contract


- [J-009a] 2026-08-06T07:52:34Z  status: done
  what: established canonical scoreboard/progress document schemas, timestamp-independent snapshot
  IDs, strict fail-closed loaders, atomic JSON persistence and a stable non-secret database identity
  artifacts: 496d424, semiskill/authoring/snapshot.py, semiskill/artifacts/store.py,
  tests/authoring/test_snapshot.py, 8 passed
  next: J-009b compute the full 84/20 cell/funnel/anomaly snapshot from authoritative inputs


- [J-009b] 2026-08-06T08:00:26Z  status: done
  what: derived the canonical 84-active/20-declined scoreboard from registry, source payloads,
  strict lint, consistency and exact security/review/approval chains; every cell now exposes
  state, hashes, provenance and blockers, while role/funnel conservation and anomaly-driven
  release checks fail closed; exact-version reviews can no longer be shadowed by other versions
  artifacts: dab1562, semiskill/authoring/snapshot.py, semiskill/authoring/gate.py,
  tests/authoring/test_snapshot_builder.py, 21 passed
  next: J-009c expose explicit snapshot generation and fail-closed read-only API endpoints


- [J-009c] 2026-08-06T08:27:41Z  status: done
  what: exposed opt-in atomic canonical snapshot generation and operator-authorized, environment-
  bound read APIs; provider/file snapshots now recompute every registry/cell/funnel/role/release
  equation, review and approval lineages fail closed, rejects require exact evidence, permission
  provenance is explicit, and the Terra explainer can only interpret validated JSON
  artifacts: c6ee01d, 5f4cea7, 61105e5, reports/scoreboard/latest.json,
  semiskill/authoring/snapshot.py, semiskill/api.py, semiskill/cli.py, 87 focused tests
  next: J-009c1 close the SQL catalog projection and skill-directory containment defects found by QA


- [J-009c1] 2026-08-06T10:33:52Z  status: done
  what: made publication a typed append-only SQL projection over exact frozen evidence and immutable
  registry policy, added pure reconciliation and separated runtime/clearance/actuator identities;
  hardened review continuity, payload hashing, filesystem containment and local/Entra identity
  binding; a causal activation timestamp fixed the only full-suite regression
  delayed: true, reason: the security checkpoint accumulated across the prior long-running turn and
  was repaired immediately when the checkpoint self-check detected the dirty tree
  artifacts: 0c0ec18, ADR-011, semiskill/artifacts/migrations/0011_verified_publication_projection.sql,
  semiskill/governance/reconciliation.py, semiskill/capture/intake.py,
  tests/artifacts/test_privilege_separation.py, recreated isolated semiskill_test database,
  657 passed, 4 skipped, 1 xpassed
  next: J-009d remove dashboard fixture fallbacks and consume only validated canonical snapshots


- [J-009d] 2026-08-06T10:46:59Z  status: done
  what: removed seed, raw-approval and ACL-filtered API count fallbacks from the local command centre;
  it now loads semantically validated environment-bound scoreboard/progress documents, preserves
  unavailable states, renders all registry role/level cells and exact skill states, exposes source
  commit/database/freshness/worker provenance, and refreshes every 15 seconds
  artifacts: 01275da, dashboard/server.py, dashboard/index.html, dashboard/README.md,
  semiskill/authoring/snapshot.py, tests/dashboard/test_dashboard.py,
  674 passed, 4 skipped, 1 xpassed; inline browser script and model JSON parsed
  next: J-010a make every offline export explicitly permission-scoped and reject mixed labels


- [J-010a1] 2026-08-06T11:12:08Z  status: done
  what: established a resolver-issued export principal and a dedicated database capability whose
  login is authorized for exactly one permission label; snapshot references, active SQL heads,
  frozen evidence IDs, payload hashes and database identities must all reconcile before a payload
  can be materialized, and direct owner/runtime/table reads are outside the export path
  artifacts: 9f24b4f, ADR-012, semiskill/artifacts/migrations/0012_scoped_export_reader.sql,
  semiskill/authoring/export_scope.py, semiskill/artifacts/store.py,
  tests/authoring/test_export_scope.py, tests/artifacts/test_privilege_separation.py, 36 passed
  next: J-010a2 route every offline materializer through the capability and emit atomic manifests


- [J-010a2] 2026-08-06T11:28:46Z  status: done
  what: bound standalone catalog and production static-site exports to one exact-label capability,
  reproduced frozen approved payload bytes and full multi-file install prompts, stamped safe scope
  provenance, and transactionally replaced owned complete trees with independently verified manifests
  delayed: true, reason: the combined materializer and fault-injection test cycle crossed the atomic
  checkpoint window; the coordinator stopped, repaired the stale test assertion, and checkpointed
  artifacts: 1679115, semiskill/authoring/export_files.py,
  semiskill/authoring/catalog_page.py, semiskill/authoring/site.py,
  tests/authoring/test_export_files.py, 38 focused tests passed on isolated semiskill_test
  next: J-010a3 bind the pack and CLI, then remove residual unexecuted-fixture KPI claims


- [J-010a3] 2026-08-06T11:38:07Z  status: done
  what: closed export-materializer QA gaps with portable contained paths, exact scope/evidence
  reconciliation, collision-safe per-file install blocks, clipboard-independent manual fallbacks,
  scope-complete stamps and deeply reconciled staged/owned-tree manifests
  artifacts: c47aa6d, semiskill/authoring/catalog_page.py,
  semiskill/authoring/export_files.py, semiskill/authoring/site.py, 41 focused tests passed
  next: J-010a4 bind the pack and export CLI to the exact-label capability


- [J-010a4] 2026-08-06T11:45:13Z  status: done
  what: replaced source-copy packaging with an exact-scope frozen-byte release, deterministic ZIP
  and evidence manifest; raw repository `_shared` and authoring tools are excluded, unresolved
  dependencies fail closed, and all export CLI commands require an explicit snapshot and label
  artifacts: 5ea37da, semiskill/authoring/pack.py, semiskill/cli.py,
  tests/authoring/test_pack.py, tests/cli/test_cli.py, 86 focused tests passed
  next: J-010a5 remove unexecuted red-team fixture claims from the live dashboard


- [J-010a5] 2026-08-06T11:50:31Z  status: done
  what: converted the red-team fixture into non-crediting input inventory, removed fabricated
  blocked/zero-escape outcomes from API and UI, downgraded feature/launch/analytics credit until a
  corpus-bound result exists, and restarted the live dashboard on the corrected contract
  artifacts: 81f4e9f, dashboard/server.py, dashboard/index.html, dashboard/model.json,
  dashboard/README.md, tests/dashboard/test_dashboard.py, 10 tests passed,
  live dashboard http://127.0.0.1:8899 process 31268
  next: J-010a6 run the full isolated verification gate for the export/dashboard tranche


- [J-010a6] 2026-08-06T11:58:43Z  status: done
  what: ran the full suite serially on the isolated test database and independently audited the
  deterministic scoreboard, corrected live dashboard, exact-scope exporters and shared dependencies
  artifacts: c3dc355, 711 passed, 4 skipped, 1 xpassed; scoreboard snapshot
  sha256:902575ca982023f8e122dfc5756d67bc398475a70d125a3f836f57fc0621a480;
  catalog-contract, Terra-scoreboard and shared-vendor read-only audits
  next: J-010a7 add explicit audited legacy migration-checksum adoption and refresh development state


- [J-010a7] 2026-08-06T13:29:31Z  status: done
  what: implemented a two-step, commit-bound legacy migration adoption gate with exact schema and
  history attestation, explicit environment/database/migrator identity, safe orphan-fixture removal,
  atomic pending-DDL/audit rollback, hardened authority triggers and transactional test isolation
  delayed: true, reason: the security review and full-suite order regression crossed the checkpoint
  ceiling; the commit hook stopped the stale checkpoint and state was repaired without bypassing it
  artifacts: 2c0b3b5, ADR-013, semiskill/artifacts/migrate.py,
  semiskill/artifacts/legacy_migration_manifest.json, migrations 0013-0015,
  tests/artifacts/test_migration_adoption.py, 771 passed, 4 skipped, 1 xpassed;
  two independent read-only audits found no scoped local-development P0/P1
  next: J-010a8 execute the exact development adoption plan and regenerate canonical live state


- [J-010a8] 2026-08-06T13:42:28Z  status: done
  what: independently reproduced and executed the exact development adoption digest, atomically
  adopted checksums for 0001-0010, removed only the attested empty historical probe, applied
  0011-0015, reconciled every tracker/authority invariant, and restored the canonical live dashboard
  artifacts: source commit 7e953cd; adoption artifact 6e35b460-df59-418c-9eee-c46803cbc0cb;
  plan sha256:b4468c6acc026d385f8bf854a03984cf5886f6adfbb301802240092ba65384ad;
  database identity sha256:85a8cb63ef46388373584988b555648732b80b136e5cc317f51412d6e624ebf1;
  snapshot sha256:30491e583ae11c5819cc99d1e1e4cabf1cf6be73836c452871cc724698c1710d;
  15/15 tracker hashes exact, 11/11 post-attestations true, projection rows 0, dashboard process 2348
  next: J-010a9 make dashboard source/database/freshness validation fail closed


- [J-010a9] 2026-08-06T15:06:20Z  status: done
  what: made the command centre accept only an observation-bound v2 scoreboard for the exact clean
  DV-84 source and live database state; every skills byte including `_shared`, current schema and
  migration tracker, sanitized legacy adoption, causal progress and a final Git witness now gate
  catalog visibility, with no client-side or fixture authority
  delayed: true, reason: the interrupted step failed its checkpoint self-check and was repaired by
  completing the trust contract, focused regression gate and clean runtime validation before resuming
  artifacts: ff70fce, ADR-014, dashboard/server.py, dashboard/index.html,
  semiskill/authoring/snapshot.py, 101 focused tests passed; live tracker 15/15, structural
  attestations 10/10, adoption attestations 11/11; v2 snapshot
  sha256:430ab94ebd8590d123b8e23944b462ed38883e4c89275ff6d320b0522bdce06d
  next: J-010b remove unsafe dashboard actuators and fabricated launch credit


- [J-010b1] 2026-08-06T15:21:53Z  status: done
  what: removed every dashboard mutation route and browser control that could directly start tests,
  processes, containers or database work; replaced them with non-crediting queue requests, corrected
  the isolated-suite and database-diagnostic templates, and added accessible busy/live feedback
  delayed: true, reason: the interrupted prior turn left a verified dirty tree and stale checkpoint;
  the checkpoint was repaired before any new implementation and the unsafe ingestion boundary remains
  explicitly in-flight rather than receiving security credit
  artifacts: 3a0f545, ADR-015, dashboard/server.py, dashboard/index.html,
  dashboard/model.json, dashboard/README.md, tests/dashboard/test_dashboard.py; 42 passed;
  Python, JavaScript and JSON syntax plus forbidden-route scans passed
  next: J-010b2 harden the append-only action queue and archive boundary


- [J-010b2] 2026-08-06T16:46:46Z  status: done
  what: replaced arbitrary dashboard ingestion with a same-origin, per-process-CSRF,
  server-template-derived request journal; canonical UUID-bound rows and non-crediting receipts now
  survive concurrent writers, rotation, ambiguous fsync/rename failures and restart reconciliation,
  while hostile framing, model drift, forged history and every retired actuator fail closed
  delayed: true, reason: the adversarial crash/durability review crossed the checkpoint ceiling; the
  commit hook then stopped stale state and a rebase-normalized integrity pin was repaired and
  independently rechecked before committing without bypassing hooks
  artifacts: fd8d70f, ADR-016, dashboard/action_queue.py, dashboard/server.py,
  dashboard/index.html, dashboard/model.json, dashboard/model.sha256,
  tests/dashboard/test_action_queue_http.py, tests/dashboard/test_dashboard.py; 116 focused tests;
  Ruff, Python, JavaScript, JSON, exact model-pin and diff checks passed; independent backend and
  visual/truth audits found no remaining P0/P1/P2 in the scoped queue contract
  next: J-010b3 remove remaining stale or fabricated dashboard evidence and runtime probes


- [J-010b3a] 2026-08-06T17:07:28Z  status: done
  what: removed request-triggered pytest collection, Docker execution and HTTP health egress from
  dashboard state reads; test counts are now explicit static function-definition inventory, the
  remaining Postgres probe is read-only with sanitized failure output, and obsolete live/green model
  claims were removed under the integrity-pinned configuration contract
  artifacts: 6a4c8cd, ADR-017, dashboard/server.py, dashboard/index.html,
  dashboard/model.json, dashboard/model.sha256, dashboard/README.md,
  tests/dashboard/test_dashboard.py; 117 focused tests passed; Ruff, Python, JavaScript, JSON,
  exact model-pin and diff checks passed
  next: J-010b3b reconcile stale pipeline, publication and artifact-schema claims


- [J-010b3b] 2026-08-06T17:18:38Z  status: done
  what: reconciled pipeline hard-fail and complete-trail semantics, authenticated exact-evidence
  publication and unpublication, migrations/capability descriptions and approval projection; the
  browser now imports all 17 artifact fields and complete constrained vocabularies directly from the
  canonical schema instead of duplicating a stale subset
  artifacts: 931e76e, ADR-018, semiskill/spine/pipeline.py, dashboard/server.py,
  dashboard/index.html, dashboard/model.json, dashboard/model.sha256,
  tests/dashboard/test_dashboard.py; 119 dashboard tests and 34 targeted pipeline/publication tests;
  independent truth audit found zero scoped P0/P1/P2
  next: J-010b3c separate curated plans and hypotheses from observed evidence


- [J-010b3c] 2026-08-06T18:08:34Z  status: done
  what: separated every curated feature, pipeline, risk, launch, asset, analytics and go-to-market
  record from observed verification credit; typed hypotheses, cohorts and measurements remain
  explicitly unvalidated, unmeasured or unpublished, while only the canonical scoreboard release
  gate can claim launch readiness and prepared requests preserve no-side-effect boundaries
  artifacts: 929c7e1, ADR-019, dashboard/index.html, dashboard/model.json,
  dashboard/model.sha256, dashboard/server.py, tests/dashboard/test_dashboard.py;
  122 dashboard tests and 42 targeted pipeline/publication/reconciliation tests; Ruff, Python,
  JavaScript, JSON, exact model-pin and diff checks passed; independent freshness, visual and
  scoreboard audits found zero scoped P0/P1/P2
  next: J-010b3d make the integrity-pinned model one semantic trust root and close replay/drift bypasses


- [J-010b3d] 2026-08-06T19:00:38Z  status: done
  what: made one hash-before-decode, schema-v1 semantic model snapshot the source for dashboard state
  and queue actions; exact code-reviewed template digests prevent prompt widening, every model-dependent
  surface rejects post-start drift, and UUID replay is bound to the original registry across restarts
  delayed: true, reason: adversarial single-snapshot, semantic-authority, replay, malformed-type and
  hostile-rendering audits expanded the regression matrix and crossed the atomic checkpoint ceiling
  artifacts: 93cfdb0, ADR-020, dashboard/action_queue.py, dashboard/server.py,
  dashboard/model.json, dashboard/model.sha256, dashboard/README.md, README.md,
  tests/dashboard/test_action_queue_http.py, tests/dashboard/test_dashboard.py;
  164 dashboard tests and 42 targeted pipeline/publication/reconciliation tests; Ruff, Python,
  JSON, exact model-pin and diff checks passed; freshness, queue and scoreboard audits found zero P0/P1/P2
  next: J-010b3e fail closed on unavailable repository/state/ADR/runtime signals and persist a
  clean-tree, source-bound isolated full-suite run artifact


- [J-010b3e1] 2026-08-06T20:09:53Z  status: done
  what: made repository, project-state, ADR and runtime database observations typed, identity-bound,
  source-validated, freshness-aware and fault-isolated; the browser now invalidates stale transport,
  preserves only current user interaction across ordered refreshes, and exposes accessible source and
  coverage detail without converting absent evidence into zero, clean, green or launch credit
  delayed: true, reason: adversarial source-shape, TOCTOU, browser-race, mobile and accessibility
  reviews expanded the regression matrix and the repository hook required a fresh STATUS witness in
  the implementation commit after the atomic checkpoint ceiling was crossed
  artifacts: e6b6509, ADR-021, dashboard/server.py, dashboard/index.html, dashboard/README.md,
  tests/dashboard/test_dashboard.py; 189 dashboard tests and 30 targeted
  pipeline/scoreboard/reconciliation tests; Ruff, Python, JavaScript, JSON, exact model-pin and diff
  checks passed; two independent exact-byte audits found zero P0/P1/P2 and Chrome verified all 11
  views at 375px with focus, scroll, refresh ordering, invalidation and console checks green
  next: J-010b3e2 persist clean-tree, source-bound isolated full-suite run evidence


- [J-010b3e2a] 2026-08-06T20:44:48Z  status: done
  what: added the fixed no-passthrough serial pytest producer, exact explicit `_test` database lease,
  clean Git source binding, bounded process-tree execution, built-in outcome reporter and append-only
  self-hashed run/output chain with fail-closed crash recovery; evidence is explicitly non-crediting
  artifacts: 30ebe79, ADR-022, semiskill/verification/evidence.py,
  semiskill/verification/full_suite.py, semiskill/verification/pytest_reporter.py,
  semiskill/cli.py, tests/verification/test_full_suite.py; 58 focused tests passed, 1 platform-link
  capability test skipped; Ruff, Python compilation and diff checks passed; independent exact-byte
  audit found zero remaining P0/P1 after all five earlier findings received regressions
  next: J-010b3e2b expose the immutable chain through a strict file-only dashboard reader and
  non-crediting Quality/Launch presentation


## In-Flight Step
- [J-010b3e2b] 2026-08-06T21:04:36Z  status: done
  what: added a fixed-root, file-only full-suite reader bound to the separately validated exact clean
  commit/tree; Quality, Launch and health surfaces now distinguish PASS, FAIL, STALE and UNAVAILABLE,
  show complete sanitized provenance and remain structurally unable to change canonical skill credit
  delayed: true, reason: Git-redirection, broken-marker, read-race, freshness, stale-presentation,
  touch-target and release-boundary audits expanded the adversarial regression matrix beyond the
  atomic checkpoint ceiling; all findings were fixed before commit
  artifacts: e12f403, ADR-022, dashboard/server.py, dashboard/index.html,
  dashboard/README.md, semiskill/verification/evidence.py, tests/dashboard/test_dashboard.py,
  tests/verification/test_full_suite.py; 152 dashboard/producer/CLI tests passed, 2 platform symlink
  capability tests skipped; Ruff, Python compilation, JavaScript syntax and diff checks passed;
  independent reader and UI audits found zero remaining P0/P1/P2
  next: J-010b3e3a execute the fixed suite on the current clean committed source and exact isolated
  test database, then verify the dashboard consumes that immutable run


## In-Flight Step
- [J-010b3e3a] 2026-08-06T21:12:15Z  status: done
  what: executed the first immutable full suite, preserved its truthful FAIL, traced both failures to
  unit tests that implicitly consumed the runner's intentionally pinned privileged adapter DSNs, and
  made those tests explicitly isolate the irrelevant environment before a clean-source rerun
  artifacts: 814187e, dashboard/runs/full-suite/runs/0d5b5dbb-89e4-4dab-adca-54de4580d8ce.json,
  sha256:40f0fbd66d6f086449926df0e73f88ef1a6f11c4641a3ff197f73470223f2476,
  tests/artifacts/test_store.py, tests/authoring/test_snapshot.py; immutable run recorded 987 passed,
  2 failed, 6 skipped and 1 xpassed; both corrected tests pass under the same pinned environment
  next: J-010b3e3b rerun the fixed serial suite on the corrected clean committed source and verify the
  dashboard's exact file-only projection


## In-Flight Step
- [J-010b3e3b] 2026-08-06T21:24:11Z  status: done
  what: reran the complete suite to a source-bound PASS, proved the strict dashboard projection at
  desktop/mobile widths, and fixed the only browser finding - a missing favicon request - with an
  inline icon that adds no route or external dependency
  artifacts: a673e39, dashboard/runs/full-suite/runs/219ba923-2db4-443a-a3fc-9b70aafcf4ae.json,
  sha256:35878b3738f4a62fe174e60e0c81f5bf49cc1b67ea18b0c2d3b59bb772c781af,
  dashboard/index.html, tests/dashboard/test_dashboard.py; immutable run on `d58b488` recorded
  989 passed, 0 failed, 0 errors, 6 skipped and 1 xpassed; file-only projection matched its exact
  commit/tree/database/run hashes; isolated Chrome at 1440px and 375px found no overflow and the
  favicon correction removed the sole 404 with a clean console/network recheck
  next: J-010b3e3c produce the final immutable run against the favicon-corrected checkpoint and repeat
  the live Quality/Launch browser verification without further source edits


## In-Flight Step
- [J-010b3e3c] 2026-08-06T21:33:52Z  status: done
  what: produced the final source-bound suite PASS for the favicon-corrected clean checkpoint and
  independently verified its non-crediting Quality and Launch presentation at desktop/mobile widths
  delayed: true, reason: the immutable run and browser audit completed after the preceding state
  checkpoint, so this repair records the already-finished evidence before any new source work
  artifacts: eb0357a, dashboard/runs/full-suite/runs/b20a98a6-ff70-4c89-bc1c-b81a8e6efb90.json,
  sha256:edd0511c0a789c3b2af5a78bfed873e0959fccf7e93be7451213919d4d9d7be2;
  989 passed, 0 failed, 0 errors, 6 skipped and 1 xpassed on exact `semiskill_test`; strict API
  projection matched commit/tree/database/run identities; isolated Chrome at 1440px and 375px had
  zero console, page, HTTP, request or horizontal-overflow failures and retained the hard no-go for
  the expired canonical scoreboard
  next: J-010c1 resolve the approval-bound `_shared` payload topology


## In-Flight Step
- [J-010c1] 2026-08-06T23:47:36Z  status: done
  what: bound every skill version to its exact shared dependency closure; replaced mutable review
  readiness with authenticated append-only one-skill leases, typed review lineage and deterministic
  publication-safe readiness; added atomic <=10-contract collection, semantic retry, database root
  uniqueness, strict coordinator privileges and migration adoption through 0023
  delayed: true, reason: the shared-payload correction exposed contradictory historical review state,
  and the required SQL/Python authority consolidation plus adversarial retry/concurrency coverage
  exceeded the atomic checkpoint ceiling; no historical claim was allowed to retain credit
  artifacts: this J-010c1 checkpoint, ADR-023/024, migrations 0016-0023,
  semiskill/authoring/gate.py, semiskill/authoring/review_collection.py,
  semiskill/artifacts/store.py, semiskill/artifacts/migrate.py, tools/collect_wave.py, all 84
  current skill payloads; 51 migration/adoption/privilege tests and 75 collector/gate/publication
  tests passed in separate serial runs; focused Ruff, Python compilation and diff checks passed
  next: J-010c2 add coordinator-only operator issuance and expose its authoritative queue on
  scoreboard v3


## In-Flight Step
- [J-010c2] 2026-08-07T01:16:58Z  status: done
  what: added a fail-closed, authenticated and commit-bound 0015->0023 forward-migration plan and
  execution boundary with exact schema/corpus/registry attestations, semantic retry and a strict
  dashboard projection of the full legacy-adoption plus forward-migration authority chain
  delayed: true, reason: adversarial review found schema-equivalence, audit-collision, retry-lineage
  and partial-dashboard-chain gaps that required exact regression coverage before any live mutation
  artifacts: this J-010c2 checkpoint, semiskill/artifacts/migrate.py, semiskill/cli.py,
  dashboard/server.py, dashboard/index.html, docs/ADOPTION.md,
  tests/artifacts/test_forward_migration.py; 328 affected tests passed serially on exact
  `semiskill_test`; focused Ruff, Python compilation and diff checks passed; three independent
  read-only audits found no remaining P0/P1 issue
  next: J-010c3 generate the exact read-only development migration plan, obtain digest-bound human
  approval before execution, then add authenticated one-skill review-contract issuance


## In-Flight Step
- [J-010c3] generate the exact read-only 0015->0023 development migration plan, obtain explicit
  digest-bound human approval before execution, then add authenticated one-skill review contracts.

## Pending Steps
1. [J-008] hash-bound review artifacts, calibrated collection, deterministic readiness, real approval
2. [J-009] canonical scoreboard snapshot + live dashboard without seed/fixture fallback
3. [J-010] ACL/provenance-bound catalog API and skills.sh-shaped list/detail UI
4. [J-011] re-review and close the 3 nominal-ready skills
5. [J-012] fix + fresh recheck the 32 reviewed-not-ready skills in batches <=10
6. [J-013] review + fix + fresh recheck the 49 never-reviewed skills in batches <=10
7. [J-014] explicit human approvals, publish 84, regenerate site/pack, adversarial final verify

## Current Phase
Phase J: Finish and ship the security-verified 84-skill DV catalog

Exit criteria:
- All 84 active registry skills have hash-bound independent rechecks with zero open blocking findings.
- All 84 exact versions have explicit human approval artifacts and are published; no automatic,
  fixture, unregistered, stale-hash, facet-drifted or ungated publication exists.
- Deterministic scoreboard reports 16/16 roles at >=5 and the dashboard reconciles registry, disk,
  review artifacts and catalog without inferred or fallback counts.
- Catalog list/detail, static export and installable pack are ACL/provenance-correct and contain no
  fabricated metric; bytes match the approved payloads.
- Full Python and UI verification suites pass serially on isolated test infrastructure.
