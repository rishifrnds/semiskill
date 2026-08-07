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


## Completed Steps (continued)
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


## Completed Steps (continued)
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


## Completed Steps (continued)
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


## Completed Steps (continued)
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


## Completed Steps (continued)
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


## Completed Steps (continued)
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


## Completed Steps (continued)
- [J-010c3] 2026-08-07T01:40:44Z  status: abandoned
  what: generated the exact read-only 0015->0023 development migration plan at `91cdd50`
  reason: the first source-bound full-suite run on that commit returned a complete FAIL, so asking a
  human to approve its migration digest would preserve a known non-green checkpoint
  artifacts: migration plan sha256:948d874415c4b7aecf2cdb0dabb19b46afa0f93f981847ea5773cbac10bd4364,
  C:/Users/rishi/.codex/visualizations/2026/08/06/019fd5bf-32dd-7c23-bc64-75d408656e96/
  migration-0015-to-0023-plan.json


## Completed Steps (continued)
- [J-010c3a] 2026-08-07T01:40:44Z  status: done
  what: ran and preserved the first immutable full suite for the forward-migration checkpoint, then
  grouped its 26 failures/errors into test-environment isolation, invalid legacy review fixtures,
  cross-version permission drift and now-impossible invalid-state simulation
  artifacts: this J-010c3a checkpoint,
  dashboard/runs/full-suite/runs/7bfb4263-98ab-4836-8b17-ce4e8f13db83.json,
  sha256:f55d1d9a04eae5887087fb2ca621695966ee5b373b590811a2dd7a70455b5117;
  1047 passed, 13 failed, 13 errors, 7 skipped and 1 xpassed on exact `semiskill_test`
  next: J-010c3b correct the four root causes and rerun the source-bound suite


## Completed Steps (continued)
- [J-010c3b] 2026-08-07T01:54:11Z  status: done
  what: preserved every tightened production gate while repairing stale role/level and permission
  fixtures, exact review-contract witnesses in adversarial MemoryStore state, full-suite adapter
  environment isolation, complete lineage expectations, post-test row cleanup and stale XPASS debt;
  missing review facets now fail in Python before the SQL actuator
  artifacts: this J-010c3b checkpoint, semiskill/authoring/review_collection.py,
  tests/conftest.py, tests/verification/test_full_suite.py, affected API/context/controller/snapshot
  fixtures; 75 root-cause tests passed, followed by 206 affected tests passed with 2 skips; Ruff,
  Python compilation and diff checks passed; post-run database rows were zero, protected triggers
  4/4 enabled and capability memberships restored
  next: J-010c3c run the immutable full suite on the corrected clean commit and regenerate the exact
  read-only development migration plan only after a complete PASS


## Completed Steps (continued)
- [J-010c3c] 2026-08-07T03:04:15Z  status: done
  what: produced a clean-source immutable full-suite PASS at `b36f250` and generated the exact
  read-only 0015-to-0023 development migration plan; subsequent read-only pooled audits prepared
  the Stage-2, Stage-5, authenticated review-issuance and scoreboard-v3 implementation contracts
  without changing the reviewed source
  delayed: true, reason: the completed run and its plan were intentionally held byte-stable while
  awaiting the exact human migration decision; the user then requested a versioned handoff and
  project-skill/state refresh, which explicitly supersedes the still-unapproved source-bound plan
  artifacts: b36f250, dashboard/runs/full-suite/runs/d7af92e6-f0fc-455c-b368-739355bf0043.json,
  sha256:33045ec0f96509209441e9bf855f8e37cc2dd3fc5419546ff809bdd664044f8f,
  migration plan sha256:ed397d3454c73094852e1da1d3723ddb53007c2ac175f56358ae4e3c7a7cb864;
  1078 passed, 0 failed, 0 errors, 7 skipped, 0 xfailed/xpassed on exact `semiskill_test`
  next: J-010d1 refresh the canonical handoff, project skill, learnings and state, then regenerate
  the exact migration plan and push the synchronized main branch

- [J-010d1a-correction-of-J-010b3e2b] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `12c0bac`; `e12f403` is the implementation commit
  corrects: J-010b3e2b
  reason: independent state reconciliation separated implementation evidence from its checkpoint

- [J-010d1b-correction-of-J-010b3e3a] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `d58b488`; `814187e` is the implementation commit
  corrects: J-010b3e3a
  reason: independent state reconciliation separated implementation evidence from its checkpoint

- [J-010d1c-correction-of-J-010b3e3b] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `eb0357a`; `a673e39` is the implementation commit
  corrects: J-010b3e3b
  reason: independent state reconciliation separated implementation evidence from its checkpoint

- [J-010d1d-correction-of-J-010b3e3c] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `7fb92c1`; `eb0357a` was prior checkpoint evidence
  corrects: J-010b3e3c
  reason: independent state reconciliation separated source evidence from its checkpoint

- [J-010d1e-correction-of-J-010c1] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `037435e` and introduced ADR-023 only; ADR-024 is introduced
    by J-010d1, not J-010c1
  corrects: J-010c1
  reason: the original self-reference also named an ADR that did not exist in that checkpoint

- [J-010d1f-correction-of-J-010c2] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `91cdd50`
  corrects: J-010c2
  reason: independent state reconciliation resolved the original self-reference

- [J-010d1g-correction-of-J-010c3a] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `ca7096f`
  corrects: J-010c3a
  reason: independent state reconciliation resolved the original self-reference

- [J-010d1h-correction-of-J-010c3b] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `b36f250`
  corrects: J-010c3b
  reason: independent state reconciliation resolved the original self-reference

- [J-010d1i-correction-of-J-010c3c] 2026-08-07T03:19:10Z  status: correction
  delayed: true
  what: the durable checkpoint commit is `83b876f`; `b36f250` is the immutable suite evidence source
  corrects: J-010c3c
  reason: independent state reconciliation separated source-bound evidence from its checkpoint

- [J-010d1j-correction-of-I-006-launch] 2026-08-07T03:26:24Z  status: correction
  delayed: true
  what: the old launch entry is abandoned and non-crediting; later measurement disproved its claim
    that 77 skills completed the full gate
  corrects: I-006 launch
  reason: append-only repair of a historical active marker and phantom completion claim

- [J-010d1k-correction-of-J-003-partial] 2026-08-07T03:26:24Z  status: correction
  delayed: true
  what: the interrupted partial review wave is superseded and non-crediting; current exact hashes
    must restart through canonical review issuance
  corrects: J-003 partial
  reason: append-only repair of a historical active marker after the shared-payload gate changed

## Completed Steps (continued)

- [J-010d1] 2026-08-07T03:30:11Z  status: done
  delayed: true, reason: three independent audits exposed scanner-suppression, state self-reference,
    stale-command and historical-marker defects that required correction beyond the atomic ceiling
  what: created the canonical 84-skill/launch handoff and reusable project-operator skill; recorded
    exact Stage-2, Stage-5, migration and market blockers; repaired checkpoint semantics and
    append-only history; updated security, learnings, README and agent instructions
  artifacts: this J-010d1 checkpoint, HANDOFF.md, .agents/skills/semiskill-project/SKILL.md,
    ADR-024, ADR-025, BLOCKERS.md, STATUS.md, STATE_RULES.md, docs/LEARNINGS.md, docs/SECURITY.md;
    project skill validator passed; strict lint 84/84 clean with 0 errors/advisories; consistency
    0 errors/60 warnings; registry 84 active + 20 declined across 16 roles; diff check passed; three
    read-only closure audits reported no remaining scoped P0/P1/P2
  next: J-010d2 synchronize/push main and produce a new clean-source immutable full-suite run

- [J-010d2] 2026-08-07T07:16:49Z  status: abandoned
  delayed: true, reason: recorded at takeover; the step's own session died before it could checkpoint
  what: commit/push the reconciled main branch, verify local/remote equality, then run a new
    source-bound immutable full suite before replacement migration planning
  reason: superseded by events. An unrecorded session (~2026-08-07T05:48Z-06:12Z, PID 21120, since
    confirmed absent) skipped this step's push/full-suite preconditions and instead committed
    `c8f5fa3` (reports/migration-plan.json, no STEP-ID), reportedly executed the 0015->0023 forward
    migration, and ran the wave across all 84 skills. The step's premise ("development schema is
    0015 and no wave has run") no longer describes reality, so it cannot be completed as written.
  artifacts: c8f5fa3 (unrecorded, no STEP-ID); superseded by J-010d3

- [J-010d3] 2026-08-07T07:16:49Z  status: done
  delayed: true, reason: state repair at crash takeover; the work being recorded was performed by a
    prior session that died without checkpointing, so this entry's timestamp is NOW, not then
  what: took over the stale crash lock with explicit user approval, preserved the crashed session's
    evidence, and reconciled STATUS/BLOCKERS/HANDOFF to measured truth instead of inherited prose
  artifacts: this J-010d3 checkpoint, docs/UNBLOCK_SPECS.md, tools/issue_batch.py,
    tests/tools/test_issue_batch.py, reports/scoreboard.json, 9 reports/wave-*.json|md from
    2026-08-07T05:52-05:54Z, STATUS.md, BLOCKERS.md, HANDOFF.md, MEMORY.md
  verification: strict authoring lint exit 0, `84/84 clean, 0 errors, 0 advisories`;
    `python -m py_compile tools/issue_batch.py tests/tools/test_issue_batch.py` OK; git remote
    0 behind / 1 ahead so no rebase was pending. NO database verification was possible: the Docker
    daemon is down and `psycopg.connect` to the development store raised ConnectionTimeout, so the
    crashed session's migration-executed and 84-captured claims are UNVERIFIED file evidence, not
    confirmed state. Credit toward review, approval, publication or launch readiness: none.
  next: J-010d4 resolve the SPEC A judge-policy contradiction that blocks all 84 at the scan gate

- [J-010d4] 2026-08-07T07:52:00Z  status: done
  what: made the unsatisfiable stage-5 judge policy refuse the wave up front instead of writing six
    artifacts per skill that the security gate was always going to reject
  artifacts: this J-010d4 checkpoint, semiskill/wave.py, tests/wave/test_wave.py, ADR-026
  verification: four new DB-free tests written first and observed failing, then passing (wave
    refuses when judge required and no scanner; refuses in dry run too; a supplied judge scanner
    satisfies the policy; an explicitly not-judge-required wave is allowed). Full DB-free subset of
    tests/wave + tests/cli + tests/spine + tests/authoring + tests/governance: 361 passed, 40
    skipped, 0 failed. Integration tests NOT run - the Docker daemon is still down (BLK-005).
    Two pre-existing DB-free tests (`test_dry_run_writes_nothing`,
    `test_write_wave_refuses_more_than_ten_skills_before_touching_store`) needed a judge scanner
    supplied so they exercise the behaviour they name rather than the judge policy.
  credit: none toward security_pass, review, approval or publication. `security_pass` stays 0 by
    design; the judge policy was deliberately NOT relaxed.
  next: J-010d5 make the CLI wave-plan/--dry-run path honest, then re-verify against the store

- [J-010d5-correction-of-J-010d4] 2026-08-07T07:35:00Z  status: correction
  what: J-010d4's entry and the STATUS.md stamp read 2026-08-07T07:52:00Z; the checkpoint was
    actually written and committed at 2026-08-07T07:32:04Z (commit 1494750). The correct time is
    07:32:04Z. Nothing else in that entry changes.
  corrects: J-010d4
  reason: a forward-dated timestamp is the same defect as a backdated one - it makes the durable log
    disagree with the commit it describes, and the next session's 15-minute freshness gate reads it

- [J-010d5] 2026-08-07T07:48:00Z  status: done
  what: made the CLI refuse consistently with the wave, so `wave-plan` can no longer promise a run
    that would refuse and `wave` reports a message instead of a traceback
  artifacts: this J-010d5 checkpoint, semiskill/wave.py (`judge_policy_refusal`), semiskill/cli.py
  verification: two DB-free CLI tests written first and observed failing, then passing. Full DB-free
    subset of tests/wave + tests/cli + tests/spine + tests/authoring + tests/governance +
    tests/tools: 391 passed, 40 skipped, 0 failed. Manual check against the real catalog:
    `wave-plan skills` inventories all 84 and then states the wave would refuse, exit 0.
    Integration tests still NOT run - Docker daemon down (BLK-005).
  design: one shared `judge_policy_refusal` predicate backs both `run_wave` and the CLI, so a plan
    can never disagree with a run. No CLI flag to disable the judge was added: a single global
    switch that turns the judge off for everything is the control that gets left on.
  credit: none toward security_pass, review, approval or publication.
  next: J-010d6 restore the store, re-verify the two unverified claims, run the integration suites

- [J-010d6-correction-of-J-010d5] 2026-08-07T07:39:00Z  status: correction
  what: J-010d5's entry and the STATUS.md stamp read 2026-08-07T07:48:00Z; the checkpoint was
    actually written and committed at 2026-08-07T07:38:09Z (commit 2b77b42). The correct time is
    07:38:09Z. Nothing else in that entry changes.
  corrects: J-010d5
  reason: second occurrence of the same defect corrected in J-010d5-correction-of-J-010d4 - the
    timestamp was estimated rather than read. Practice change adopted: read `date -u` immediately
    before writing any timestamp into MEMORY.md or STATUS.md, never estimate it from elapsed work.

- [J-010d6] 2026-08-07T08:30:50Z  status: done
  what: restored the development store, independently verified the crashed session's two claims,
    and repaired the wave integration tests that the ADR-026 refusal correctly broke
  artifacts: this J-010d6 checkpoint, tests/wave/test_wave.py, BLOCKERS.md, STATUS.md
  verification: started the stopped `semiskill-db-1` container (Postgres 16.14, 127.0.0.1:5432).
    CONFIRMED claim 1 - `schema_migrations` holds 23 rows, last `0023_review_unbound_parameter_
    binding.sql`, with 0016-0023 all present. CONFIRMED claim 2 - every one of the 84 registry-active
    slugs has a `skill_version` artifact; artifacts by type are scan_run 338, review 119,
    skill_version 85, injection_test 84, gate_decision 2, which reconciles exactly with the
    pre-existing 39-artifact baseline (35 legacy reviews + 2 scan_run + 1 skill_version +
    1 gate_decision) plus 84 new captures. `tests/wave` + `tests/spine` + `tests/cli` including
    integration: 82 passed, 0 failed.
  finding: the 85th `skill_version` slug is `dv/cve`, a TEST FIXTURE from
    `tests/spine/test_pipeline.py`, captured into the DEVELOPMENT store at 2026-08-06T06:57:44.
    The artifact store is append-only so it cannot be removed; it is recorded as known
    non-crediting pollution and must never be counted. Logged as a gap, not silently ignored.
  test-repair: 10 wave integration tests failed because their shared `run()` helper supplied no
    judge scanner. Nine now supply one, so they exercise capture/scan/reconcile as they name; the
    tenth (`test_clean_wave_captures_and_scans_but_does_not_publish`) now states the exempt path
    explicitly with `judge_required=False`, preserving its real assertion that stage 5 is recorded
    honestly as `not_sampled` rather than as a pass.
  resolved: BLK-002 (human approved the migration digest; execution to 0023 independently verified)
    and BLK-005 (development store reachable).
  credit: none toward security_pass, review, approval or publication.
  next: J-010d7 run the immutable full suite on this clean source

- [J-010d7] 2026-08-07T08:45:25Z  status: done
  what: ran the immutable full suite on clean source, fixed the one real regression it exposed, and
    characterised the one flaky failure instead of papering over it
  artifacts: this J-010d7 checkpoint, README.md,
    dashboard/runs/full-suite/runs/08e18e7c-90c3-4d3a-8383-c604edfc57e5.json
  verification: run `08e18e7c-90c3-4d3a-8383-c604edfc57e5` on commit `cc3508a` reported 1105 passed,
    2 failed, 7 skipped, 0 errors, 0 xfailed/xpassed against isolated `semiskill_test` at 0023.
    Both failures were diagnosed rather than assumed:
  finding-1 (real, PRE-EXISTING, now fixed): `test_root_readme_does_not_claim_unexecuted_redteam_
    results` failed because commit `105b3cb` (J-010d1) rewrote README.md and deleted the red-team
    section including its required "authoritative corpus execution is currently unavailable"
    caveat. It went unnoticed because the previous full-suite run predates that commit - exactly the
    staleness HANDOFF.md warned about. README now states the unavailability explicitly; the same
    edit removed the now-false "development schema 0015" claim.
  finding-2 (flaky, NOT fixed, characterised): `test_host_origin_csrf_and_media_type_fail_closed`
    failed with `ConnectionAbortedError [WinError 10053]` while READING the response. It hit
    `overrides10-415` in the suite run and `overrides0-421` on the next run, then passed 12/12 three
    consecutive times (36/36). It is a Windows TCP race: the server sends its fail-closed response
    and closes while the client is still writing, so Windows sends RST and discards the unread
    response. The server's status codes are correct. Deliberately NOT silenced with a retry - a
    green suite bought by hiding a race is worth less than a recorded one.
  credit: none toward security_pass, review, approval or publication.
  next: J-010d8 re-run the immutable suite on this clean source to obtain a current PASS record

- [J-010d8] 2026-08-07T08:56:49Z  status: done
  what: re-ran the immutable full suite on clean source, confirmed the README fix, and root-caused
    the remaining flake without patching a security-sensitive path under time pressure
  artifacts: this J-010d8 checkpoint,
    dashboard/runs/full-suite/runs/350ecd33-8f78-4a76-a7eb-7f2b6ec97908.json
  verification: run `350ecd33-8f78-4a76-a7eb-7f2b6ec97908` on commit `a1d8746` reported 1106 passed,
    1 failed, 7 skipped, 0 errors against isolated `semiskill_test` at 0023. The README regression is
    gone (1105 -> 1106 passed). The sole remaining failure is the known flake, which hit a THIRD
    distinct parametrization (`overrides2-421`, after `overrides10-415` and `overrides0-421`) -
    conclusive evidence of a race rather than a defect in any specific rejection path.
  root-cause: `dashboard/server.py::Handler._json` writes the rejection response and returns without
    draining the unread request body. On Windows, closing a socket with unread data in the receive
    buffer sends RST, which discards the response the client has not yet read. The server's status
    codes are correct; only delivery races.
  not-fixed-deliberately: every obvious remedy has a sharp edge in a fail-closed security path. An
    unbounded drain is a DoS vector; a blocking drain hangs the existing `413` case, which sets
    Content-Length 16385 and deliberately never sends the body; a test-side retry hides the race.
    The correct fix is a bounded, non-blocking drain (or an explicit half-close) with its own tests,
    which is a designed step, not an end-of-session patch.
  consequence: the immutable full suite is NOT a current PASS. Any gate that requires a full-suite
    PASS - a new migration plan, a release checkpoint - remains blocked until J-010d9 lands.
  credit: none toward security_pass, review, approval or publication.
  next: J-010d9 implement the bounded non-blocking drain (or half-close) and re-run the full suite

- [J-010d9] 2026-08-07T09:45:28Z  status: done
  what: fixed the response-delivery race by draining a bounded, time-limited amount of unread
    request body before a rejection responds and closes
  artifacts: this J-010d9 checkpoint, dashboard/server.py, tests/dashboard/test_action_queue_http.py
  verification: three tests written first. The key one reproduced the race DETERMINISTICALLY - 25
    consecutive 415 rejections with an 8 KiB unread body failed before the fix and pass after it, so
    this is a real repair rather than a lucky green run. Full file: 111 passed, 0 failed, including
    the twelve previously flaky parametrizations. `--durations` confirms no systematic slowdown: the
    slowest tests are all pre-existing at ~1.1s and none of the new ones appear.
  design: the drain is bounded in size (capped at `_MAX_ACTION_BODY_BYTES`) AND in time
    (`_MAX_DRAIN_SECONDS` 0.25s), because the two obvious implementations are each a
    denial-of-service shape - an unbounded drain lets a client stream forever into an already
    rejected request, and a drain that waits for a declared-but-never-sent body pins the worker.
    It is best-effort: a drain that cannot finish gives up rather than failing the rejection.
    `_body_consumed` is set before the real body read so a later drain never re-reads or re-waits.
  credit: none toward security_pass, review, approval or publication.
  next: J-010e1 re-run the immutable full suite for a current PASS record

- [J-010e1] 2026-08-07T09:54:08Z  status: done
  what: recorded a current clean-source immutable full-suite PASS, the first since `b36f250`
  artifacts: this J-010e1 checkpoint,
    dashboard/runs/full-suite/runs/5eb6210d-8f6a-41a1-a48b-8190a696b416.json, HANDOFF.md, STATUS.md
  verification: run `5eb6210d-8f6a-41a1-a48b-8190a696b416`; source commit
    `854ae714eec13bf216d697b7ec2c2ea2565fe1e6`, tree `a493c56ca1699ec64b9e0b531bd4bf41dbba7e28`,
    `clean: true`; 1117 collected, 1110 passed, 7 skipped, 0 failed, 0 errors, 0 xfailed/xpassed;
    isolated `semiskill_test` at 0023; run SHA-256
    `52aec9b0e2b7f8d67dcfe9581acc1f1be66e0754e02c34597f8b94f07e27c83f`, output SHA-256
    `936972ccba1eab17c634b6e7cfbe769511a037e81c6bf810b36ca0fcf22d1e66`.
  credit: none toward skill review, approval, publication or launch readiness. This is platform
    proof only, and it goes stale the moment the source changes.
  unblocks: gates that require a current full-suite PASS - notably a new source-bound migration plan
    and any release checkpoint. It does NOT move any skill through the security gate.
  next: J-010e2 correct the false single-blocker claim in docs/UNBLOCK_SPECS.md

- [J-010e2] 2026-08-07T09:55:06Z  status: done
  what: corrected the false "single blocker" claim in docs/UNBLOCK_SPECS.md and HANDOFF.md gap 9
  artifacts: this J-010e2 checkpoint, docs/UNBLOCK_SPECS.md, HANDOFF.md
  evidence: `_security_projection` for `dv-minimal-reproducer` returns status `blocked` with errors
    `['REQUIRED_JUDGE_NOT_PASSED', 'REQUIRED_STAGE_BLOCKED']`. Stage statuses across all 84
    captures, read from the store: stage 1 `passed` 84, stage 2 `not_run` 84, stage 3 `passed` 84,
    stage 4 `passed` 84, stage 5 `not_sampled` 84. `snapshot.py` requires stages 1-4 to all be
    `passed`, so stage 2 blocks every skill independently of the judge.
  why-it-matters: SPEC A's stated acceptance criterion (`security_pass: 84`, `blocked.scan: 0`) is
    unreachable by resolving the judge policy alone. Anyone implementing SPEC A as written would
    finish the work and find all 84 still blocked. Stage 2 must also pass, which needs the ADR-024
    scanner and its AppSec/legal approval (BLK-003).
  credit: none toward security_pass, review, approval or publication.
  next: J-010e3 build and test the ADR-024 Stage-2 adapter, whose only remaining gate is approval

- [J-010e3] 2026-08-07T11:56:09Z  status: done
  what: built the ADR-024 Stage-2 host-side staging projection - the trusted-host half that decides
    what reaches the scanner and what the expected coverage set is
  artifacts: this J-010e3 checkpoint, semiskill/scanners/stage2_staging.py,
    tests/scanners/test_stage2_staging.py
  verification: 32 adversarial tests written first and observed failing (module absent), then
    passing. All of tests/scanners: 59 passed, 0 failed. Sanity-checked against a REAL captured
    payload from the store (`dv-minimal-reproducer`), which projects to exactly `SKILL.md` plus the
    three canonical vendored `_shared` files, with nothing isolated.
  contract: paths are untrusted input, so backslash and forward slash are normalized identically
    (a POSIX-legal filename like `refs\\..\\..\\x` becomes a traversal on Windows), Unicode is
    NFC-normalized before duplicate detection, and absolute/drive-qualified/traversing/empty/NUL/
    directory paths are refused. Every path is validated BEFORE any byte is written, so a refusal
    never leaves a half-projected root. Payload-supplied scanner configuration (`.semgrepignore`
    and friends) is ISOLATED and recorded rather than dropped - a skill must not be able to exclude
    itself from the rules that judge it, and silent containment is indistinguishable from a
    coverage hole. The staged tree is finally compared to the expected set exactly.
  credit: none. This is the host side only; no Stage-2 result can earn credit until AppSec approves
    the image, rule pack and supply-chain record (BLK-003).
  next: J-010e4 bounded exact-key report validation and the fail-closed coverage rules

- [J-010e4] 2026-08-07T11:58:23Z  status: done
  what: built the ADR-024 Stage-2 report validator - the bounded exact-key contract that decides
    whether an engine report may be trusted to prove exact coverage
  artifacts: this J-010e4 checkpoint, semiskill/scanners/stage2_report.py,
    tests/scanners/test_stage2_report.py
  verification: 36 tests written first and observed failing (module absent), then passing. All of
    tests/scanners: 95 passed, 0 failed.
  contract: exact-key in both directions - unknown AND missing report/finding fields are refusals.
    Provenance-shaped keys (`image_digest`, `rule_pack_sha256`, `payload_sha256`, `slug`,
    `adapter_commit`, `approved`) are refused as unknown fields, because the container may never
    assert its own identity; the host binds that separately in J-010e5. Coverage must match the
    staged set exactly, with duplicates rejected so a repeated entry cannot fake a count. Any skip,
    error, truncation, timeout or resource kill is blocking. Findings are bounded in count and
    string size, ids must be unique, severities must be known, and a finding may only name a path
    the host actually staged - which refuses absolute, traversing and unstaged paths in one rule.
  design-note: exceeding a bound raises rather than truncates. Truncating would recreate the exact
    silent-coverage-loss defect that retired the previous runner, one layer higher up.
  credit: none. No Stage-2 result can earn credit until AppSec approves the image, rule pack and
    supply-chain record (BLK-003).
  next: J-010e5 bind host-side identity and wire staging + report into an injectable Stage-2 scanner

- [J-010e5] 2026-08-07T12:00:46Z  status: done
  what: wired staging and report validation into the ADR-024 Stage-2 host adapter and bound
    host-computed identity to the result
  artifacts: this J-010e5 checkpoint, semiskill/scanners/stage2_adapter.py,
    tests/scanners/test_stage2_adapter.py
  verification: 13 tests written first and observed failing (module absent), then passing.
    tests/scanners + tests/spine: 126 passed, 0 failed.
  invariant-1: an unapproved supply chain can NEVER pass. `Stage2Policy.approved` defaults to False
    and gates execution, so BLK-003 is enforced in code rather than prose - and the engine is not
    invoked at all, which a test asserts directly.
  invariant-2: every failure is absent evidence, never a pass. Unapproved chain, rule-pack hash
    mismatch, hostile path, engine crash, invalid report and partial coverage all return the
    `security-audit-skipped` finding, which `pipeline._write_scan` maps to `not_run` and
    `snapshot.py` then treats as `REQUIRED_STAGE_BLOCKED`. The previous runner's fail-open gap -
    scoring 1.000 when it had not run - is closed.
  identity: the rule-pack hash is RECOMPUTED by the host, never taken on trust from the policy
    text; the image must be an exact `sha256:` manifest digest, not a tag; the binding carries slug,
    payload fingerprint, image digest, rule-pack hash, adapter commit, analyzed and isolated files.
  known-gap: the binding record is returned by `scan_with_binding` but NOT yet persisted into the
    scan artifact - `pipeline._write_scan` has a fixed payload shape, so persisting it needs a
    schema/migration change. Recorded rather than silently dropped.
  credit: none. Stage 2 still cannot pass anywhere, by design, until BLK-003 closes.
  next: J-010e6 run the full suite, then either persist the binding or build the Stage-5 adapter

- [J-010e6] 2026-08-07T12:17:22Z  status: done
  what: recorded a clean-source full-suite PASS covering the three new Stage-2 modules, and
    diagnosed the intermittent failure that preceded it rather than accepting the green run
  artifacts: this J-010e6 checkpoint,
    dashboard/runs/full-suite/runs/a6792604-42ec-4111-a801-b55de5a43669.json
  verification: run `a6792604-42ec-4111-a801-b55de5a43669` on clean source `28379ab`; 1198
    collected, 1191 passed, 7 skipped, 0 failed, 0 errors; isolated `semiskill_test` at 0023;
    run SHA-256 `7c230d0ae73d24b465c2a160c0114438b0b5d68dd45cc2a33234f435c84026fc`.
  finding (NEW, not fixed): the immediately preceding run `b4270338` failed one test with
    `psycopg.OperationalError: Address already in use (0x00002740/10048)` - Windows ephemeral port
    exhaustion, not a defect in the new modules, which touch no database. `PostgresArtifactStore`
    opens a FRESH connection per call (`store.get` calls `psycopg.connect` every time). The Windows
    dynamic range is 16,384 ports with a ~4 minute TIME_WAIT, and 2,901 sockets were observed in
    TIME_WAIT during the run. Adding ~81 tests this session pushed connection churn near that
    ceiling, so the suite is now intermittently unable to connect.
  why-it-matters: this failure mode gets worse with every test added and is indistinguishable from
    a real defect at a glance. A passing re-run is NOT a fix. The real remedy is connection reuse or
    pooling in the artifact store, which changes a core component and deserves its own ADR.
  credit: none toward security_pass, review, approval or publication.
  next: J-010e7 either pool artifact-store connections (ADR-worthy) or start the Stage-5 adapter

## In-Flight Step

- none. J-010e7 is selected but not started.

## Pending Steps
1. [J-010d5] make the CLI honest: `cmd_wave` returns early for `wave-plan`/`--dry-run` before
   `run_wave`, so it still prints "N skill(s) would be captured/scanned" for a wave that would in
   fact refuse. Surface the same refusal there, and give `cmd_wave` a clean error path so the
   ValueError prints as a message rather than a traceback.
2. [J-010d6] bring the development store back up and independently re-verify the crashed session's
   two unverified claims: schema really at 0023, and 84 `skill_version` + scan artifacts really
   present. Then run the integration suites deferred by BLK-005, serially.
3. [J-010d7] review and test `tools/issue_batch.py` (SPEC B) against `collect_wave.py::_validate`
   before it is allowed to lease any real work; it is currently unreviewed inherited code.
4. [J-010d8] implement scoreboard v3/progress v2 strict nested validation and one shared live
   observation contract; v2 remains diagnostic and cannot authorize review or release.
5. [J-010d9] implement and promote the ADR-024 Stage-2 scanner plus calibrated loopback Stage 5
6. [J-010e1] run a new clean-source immutable serial full suite and push synchronized `main`
7. [J-011] prove one exact skill and then the five-skill vertical cohort end to end
8. [J-012] re-review/fix the historical 3/32/49 routing cohorts in batches <=10 until 84 are ready
9. [J-013] finish the ACL/provenance-bound Next.js catalog, deployment and market-readiness controls
10. [J-014] obtain explicit approvals, publish 84, regenerate outputs and pass the final launch gate

The 3/32/49 split is historical, non-crediting routing provenance. Every skill must restart against
its exact current full payload hash and fresh independent evidence.

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
