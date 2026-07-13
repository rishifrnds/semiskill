<!--
Durable runtime state log for this project. Strict format — no prose-only entries.
Full rules and entry schemas: see STATE_RULES.md.
-->

## Project
- Name: SemiSkill — Internal Security-Verified Skill Marketplace
- Goal (one sentence): Give the company one internal, SharePoint-hosted place to publish, discover,
  comment on, rate, and reuse Agent Skills — every skill passing an automated security-verification
  pipeline + human approval gate before publish.
- Started: 2026-07-13
- CLAUDE.md version: 2026-07-13
- Repo: https://github.com/rishifrnds/semiskill
- Architecture: AIOS 6-layer — mirrors E:\code\aios
- Build plan (approved): C:\Users\rishi\.claude\plans\semiskill-ultra-mode-logical-lagoon.md
- Session goal: complete all planned tasks (Phases C–G) and surface gaps/issues (do not pause per-phase).

## Carry-forward from archives
Phase 0 → archive/MEMORY-P0.md. Phase A → archive/MEMORY-A.md. Phase B → archive/MEMORY-B.md.
Built + green (59 tests):
- L2: semiskill/artifacts/{schema,store,migrate}.py + migrations 0001_artifacts.sql; spine/{states,lifecycle}.py.
  Append-only trigger, corrects_ref, derive_state ADR-002 gate, structural ACL (semiskill_app + artifact_get).
- L1: semiskill/capture/{intake,events}.py + cli.py (`semiskill submit`/`list`).
- L3: semiskill/context/{acl,untrusted,retrieve,provenance}.py + migration 0002_context.sql
  (SECURITY DEFINER catalog_search [published-only, ACL-filtered, facets/text] / lineage / reuse; semiskill_app EXECUTE).
- ADRs: 001 AIOS 6-layer, 002 gated publish, 003 pipeline-seeded, 004 web-app host, 005 local Docker PG,
  006 all-6-scanners, 007 pyyaml.
- INFRA (Windows/Docker): DB = Docker PG16 (`docker compose up -d db`, 127.0.0.1:5432, fsync=off). USE
  127.0.0.1 NOT localhost. Tests: session-scoped shared migrated DB + TRUNCATE-per-test. Hooks: message
  enforcement in .git/hooks/commit-msg (pre-commit can't read a -m message); backup pre-commit.bak.
- Catalog is DERIVED from artifacts (a published `approval`), no separate catalog table. Phase C must
  make the publish path structurally unbypassable (a submitter must not be able to forge an approval).
- Deferred: pgvector/semantic search (needs Voyage egress).

## Completed Steps
<!-- Append-only. Newest at bottom. -->

- [C-001] 2026-07-13T05:00Z  status: done
  what: migration 0003_pipeline.sql — added pipeline artifact types (gate_decision/sensor_reading/gold_set); created semiskill_submitter role (INSERT-only) + BEFORE INSERT trigger restricting it to skill_version/comment/rating/reuse_event, so a submitter structurally cannot forge approval/scan_run/injection_test/review (publish-path invariant foundation). 7 tests green; full suite 66 green (no regression from the new trigger)
  artifacts: semiskill/artifacts/migrations/0003_pipeline.sql, tests/artifacts/test_migration_0003.py
  next: C-002

- [C-002] 2026-07-13T05:05Z  status: done
  what: scanners/base.py — Scanner Protocol, ScanStage(1-6), Finding, SkillSubmission (untrusted body/files/tools + texts()), ScanResult (safety_score [0,1], hard_fail), result_from (fold findings → safety=1-Σseverity clamped, hard_fail if any severity ≥0.9); governance/policy.py tool_risk allowlist (allowed=0, dangerous≥0.95, unknown=0.4). 9 unit tests
  artifacts: semiskill/scanners/base.py, semiskill/governance/policy.py, tests/scanners/test_base.py, tests/governance/test_policy.py
  next: C-003

- [C-003] 2026-07-13T05:10Z  status: done
  what: scanners/static_structure.py (stage 1, deterministic) — flags dangerous/unlisted tools (policy.tool_risk), binary-executable (hard_fail) / binary-blob / shell-script files, dynamic-exec + base64 obfuscation, outbound network refs, oversized. 7 unit tests (benign clean; Bash + .exe hard_fail; eval/base64 → low score)
  artifacts: semiskill/scanners/static_structure.py, tests/scanners/test_static_structure.py
  next: C-004

- [C-004] 2026-07-13T05:15Z  status: done
  what: scanners/secret_pii.py (stage 4, deterministic) — detects private keys / AWS / GitHub / Slack tokens / credential-assignments (all hard_fail), JWT, internal-URL, private-IP, SSN, credit-card. 7 unit tests (benign clean; live creds hard_fail; internal-url/ssn soft flags)
  artifacts: semiskill/scanners/secret_pii.py, tests/scanners/test_secret_pii.py
  next: C-005

- [C-005] 2026-07-13T05:25Z  status: done
  what: Held-out corpus boundary (LOAD-BEARING) — migration 0004_corpus.sql (injection_corpus + judge_gold_set restricted; semiskill_pipeline role REVOKE ALL on both; probe_skill_against_corpus SECURITY DEFINER returns {passed,total,failing_classes} only; 9 seeded signatures: injection/exfiltration/scope-violation/tool-abuse). sensor/corpus.py (seed owner-path + probe pipeline-role-path). scanners/injection_probe.py (stage 3). 5 integration tests: pipeline role CANNOT SELECT corpus/gold-set; probe returns counts not patterns; injection+EchoLeak hard_fail; clean passes. Full suite 94 green
  artifacts: semiskill/artifacts/migrations/0004_corpus.sql, semiskill/sensor/corpus.py, semiskill/scanners/injection_probe.py, tests/artifacts/test_migration_0004.py, tests/scanners/test_injection_probe.py
  next: C-006

- [C-006] 2026-07-13T05:30Z  status: done
  what: governance/gate.py — ported guarded_run deny-precedence gate (Decision/Rule/Policy/ActionDescriptor/evaluate; DENY>REQUIRE_SIGNOFF>ALLOW; action runs only in permitted branch; fail-closed GATE_DECISION audit before side effects). Fixed schema.py — added GATE_DECISION to the Python ArtifactType (it was in the DB enum 0003 but missing in Python). 6 gate tests + schema green
  artifacts: semiskill/governance/gate.py, semiskill/artifacts/schema.py, tests/governance/test_gate.py
  next: C-007

- [C-007] 2026-07-13T05:45Z  status: done
  what: Gated publish actuator + rollback + publish-path invariant. governance/publish.py (publish_skill: DENY-by-default REQUIRE_SIGNOFF; server-side re-check review verdict=approve + no hard_fail scan; appends published approval ONLY inside the gate; sets rollback_ref). governance/rollback.py (unpublish_skill: appends correcting approval published=false via corrects_ref). Switched catalog/derive_state to ACTIVE-approval-wins (supersession via corrects_ref + timestamp tiebreak) → migration 0005_publish.sql + lifecycle.py. 5 publish tests (full path→discoverable; no signoff→GateBlocked+audit, never in catalog; reject-review refused; hard_fail refused; unpublish removes from catalog). Full suite 105 green
  artifacts: semiskill/governance/publish.py, semiskill/governance/rollback.py, semiskill/artifacts/migrations/0005_publish.sql, semiskill/spine/lifecycle.py, tests/governance/test_publish.py
  next: C-008

- [C-008] 2026-07-13T05:55Z  status: done
  what: spine/pipeline.py orchestrator — run_pipeline runs deterministic stages (static/injection/secret-PII) in order, writes scan_run+injection_test per stage (eval_score=safety, hard_fail, findings), hard-fail SHORT-CIRCUITS (no review → unpublishable), else worst-stage safety → suggest-only review verdict (approve≥0.8 / reject<0.5 / request-changes). 5 integration tests: benign→approve→human-publish→discoverable; soft→request-changes; tool-abuse/injection/secret each blocked at their stage, never in catalog, hard-fail trail present. Full suite 110 green. **Core safety property demonstrated end-to-end.**
  artifacts: semiskill/spine/pipeline.py, tests/spine/test_pipeline.py
  next: C-009

- [C-009] 2026-07-13T06:05Z  status: done
  what: scanners/security_audit.py (stage 2) — INJECTABLE runner (default npx_security_runner shells the local security-scan CLI; ToolUnavailable → a VISIBLE `security-audit-skipped` finding in the trail, advisory not silent-fail-open). Maps report severities → findings (critical/high → hard_fail). Wired OPT-IN into pipeline (_build_scanners adds stage 2 only when a runner is passed; default stays deterministic-only for hermeticity + egress control). 4 unit + 2 pipeline tests green
  artifacts: semiskill/scanners/security_audit.py, semiskill/spine/pipeline.py, tests/scanners/test_security_audit.py, tests/spine/test_pipeline.py
  known-gap: live stage-2 execution needs the egress-controlled sandbox + claude-flow installed — NOT exercised here (tested via injected runners only). Same applies to fetching the cloudflare/security-audit-skill.
  next: C-010

## In-Flight Step
_(none — C-010 next: sensor/judge.py (κ calibration + drift + cross-family) + scanners/judge_risk.py stage 5 + aggregate — logic + injected fakes, no live API)_

## Pending Steps
1. [C-001] migration 0003_pipeline.sql — add artifact types (gate_decision/sensor_reading/gold_set) + semiskill_submitter role with type-restricted INSERT trigger (can't forge approval/scan_run/review) + tests
2. [C-002] scanners/base.py (Scanner Protocol, ScanResult{stage,safety_score,verdict,findings,hard_fail}) + governance/policy.py (SKILL allowed-tools allowlist) + unit
3. [C-003] scanners/static_structure.py (stage 1: frontmatter/tools/scripts/exec-payload/network/obfuscation/oversized) + unit
4. [C-004] scanners/secret_pii.py (stage 4: creds/tokens/internal-URLs/PII) + unit
5. [C-005] held-out corpus — migration 0004_corpus.sql (injection_corpus/gold_set tables + semiskill_pipeline role REVOKE + probe_skill_against_corpus SECURITY DEFINER) + sensor/corpus.py + scanners/injection_probe.py (stage 3) + integration tests (corpus UNREADABLE by pipeline role)
6. [C-006] governance/gate.py (port guarded_run deny-precedence + GATE_DECISION audit) + policy tests
7. [C-007] governance/publish.py (gated actuator: require human approval + clean scan chain, append published approval via guarded_run) + rollback.py (unpublish via corrects_ref) + integration tests (publish-path invariant)
8. [C-008] spine/pipeline.py orchestrator (run stages 1/3/4 in order → scan_run+injection_test, hard-fail short-circuit, aggregate review) + integration tests (benign passes / malicious blocked)
9. [C-009] scanners/security_audit.py (stage 2: wrap local security-scan/security-audit; graceful skip if npx absent) + tests
10. [C-010] sensor/judge.py + scanners/judge_risk.py (stage 5) + scanners/aggregate.py (stage 6 dual-LLM) — logic + injected fakes; κ≥0.6 + drift + cross-family guard
11. [C-011] redteam/harness.py + red-team Workflow fan-out (adversarial verify; corpus stays unreadable)
12. [C-012] Phase C verify gate

## Current Phase
Phase C: Security-Verification Pipeline (L4 + L6) — the load-bearing safety core

Exit criteria:
- Benign skill: submit → passes deterministic scans → aggregate review → human approval → published/discoverable
- Malicious skill (from corpus classes): submit → hard-fail at scan → never discoverable → quarantined with trail
- Publish-path invariant: a submitter role cannot forge an approval/scan_run; publish without a human approval is rejected
- Held-out corpus + gold-set are UNREADABLE by the pipeline role (probe returns counts only)
- Red-team panel: zero escapes; corpus-unreadable holds every round
- `docker compose up -d db && pytest` all green
