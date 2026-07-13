<!--
Durable runtime state log for this project. Strict format — no prose-only entries.
Full rules and entry schemas: see STATE_RULES.md.
-->

## Project
- Name: SemiSkill — Internal Security-Verified Skill Marketplace
- Goal (one sentence): One internal, SharePoint-hosted place to publish/discover/comment/rate/reuse
  Agent Skills — every skill passing an automated security pipeline + human approval before publish.
- Started: 2026-07-13 · CLAUDE.md version: 2026-07-13 · Repo: https://github.com/rishifrnds/semiskill
- Architecture: AIOS 6-layer — mirrors E:\code\aios
- Build plan (approved): C:\Users\rishi\.claude\plans\semiskill-ultra-mode-logical-lagoon.md
- Session goal: complete all planned tasks (Phases C–G) and surface gaps/issues (no per-phase pause).

## Carry-forward from archives
Phases 0/A/B/C done → archive/MEMORY-{P0,A,B,C}.md. Built + green (146 tests):
- L2: artifacts/{schema,store,migrate}.py + migrations 0001..0006; spine/{states,lifecycle}.py.
- L1: capture/{intake,events}.py + cli.py. L3: context/{acl,untrusted,retrieve,provenance}.py.
- L4/L6 pipeline: scanners/{base,static_structure,security_audit,injection_probe,secret_pii,judge_risk}.py;
  spine/pipeline.py (orchestrator); sensor/{reading,judge,corpus}.py; governance/{gate,policy,publish,rollback}.py;
  redteam/harness.py. Held-out corpus behind semiskill_pipeline role. Publish is gated (human signoff).
- Roles: semiskill_app (read via SECURITY DEFINER), semiskill_submitter (can't forge verification artifacts),
  semiskill_pipeline (can't read corpus/gold-set).
- Invariants proven: no publish without human approval; submitter can't forge approval; malicious blocked
  (battery + 7 novel LLM-crafted attacks, zero escapes); corpus unreadable by pipeline role.
- ADRs 001-007. INFRA: Docker PG16 (127.0.0.1 not localhost; fsync=off); shared-DB TRUNCATE tests;
  git message enforcement in .git/hooks/commit-msg.
- GAPS: stage-2 security-audit + cloudflare skill need egress sandbox+claude-flow (injected-runner tested);
  stage-5 live judge needs API keys (FakeJudge tested); pgvector semantic search deferred (Voyage egress).

## Completed Steps
<!-- Append-only. Newest at bottom. -->

## In-Flight Step
_(none — starting Phase D: D-001 stability gate)_

## Pending Steps
1. [D-001] intelligence/stability.py — six-control gate (deadband/cooldown/circuit-breaker/hysteresis/trajectory/cost) ported from AIOS + tests
2. [D-002] governance/cost.py — model routing (SMALL/LARGE) + guard_llm_call + cost ledger + cost-per-verified-skill + tests
3. [D-003] intelligence/controller.py — verdict aggregation (from pipeline) + review-queue ranking by risk + drift-blocks-auto-act (suggest-only) + tests
4. [D-004] Phase D verify gate (no oscillation on replayed scan stream; cost-per-verified-skill tracked; drift blocks)

## Current Phase
Phase D: Intelligence Controller (L5)

Exit criteria:
- Six-control stability gate: no oscillation on a replayed error stream (deadband/cooldown/breaker/hysteresis/trajectory/cost all covered)
- Model routing SMALL→LARGE on ambiguity; cost-per-verified-skill computable from cost artifacts
- Review-queue ranking orders pending skills by risk/priority
- Drift test: a falling judge-vs-gold κ blocks the L5 controller from auto-acting (require_no_drift)
- `docker compose up -d db && pytest` all green
