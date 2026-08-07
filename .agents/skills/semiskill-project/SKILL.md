---
name: semiskill-project
description: Resume, operate, verify, and safely ship the SemiSkill security-gated 84-skill DV catalog. Use for SemiSkill implementation, review waves, scoreboard or dashboard work, migrations, release checks, state repair, handoffs, and launch-readiness questions in this repository.
---

# Operate the SemiSkill Project

Treat every readiness claim as an evidence question. The catalog is not launch-ready until exact,
current payloads pass the complete gate, receive independent content review and authenticated human
approval, and appear in the projection-backed catalog.

## Start Here

1. Read `../../../HANDOFF.md` for the current truth, evidence IDs, blockers, and ordered backlog.
2. Read `../../../STATE_RULES.md` completely before modifying files.
3. Read `../../../STATUS.md`, the bottom of `../../../MEMORY.md`, and
   `../../../BLOCKERS.md`. Consult `../../../DECISIONS.md` for affected architecture decisions.
4. Verify the Git branch, clean/dirty state, `.session-lock`, database identity, and evidence freshness
   instead of inheriting claims from prose.
5. Keep one filesystem writer. Let pooled agents analyze or review read-only and return findings to
   the coordinator.

## Select the Next Safe Step

- If state files disagree with observable state, repair the checkpoint first and record the delay.
- If development schema is behind, generate a new source-bound migration plan and stop for exact
  human digest approval. Never reuse a plan after any source change.
- If platform gates are incomplete, implement and test the earliest missing gate before issuing
  content reviews.
- If a review batch is active, cap it at 10 unique skills, preserve every attempt, and require a
  fresh-context reviewer who did not receive fixer reasoning.
- If a user asks whether launch is ready, answer from the canonical scoreboard. An unavailable or
  stale scoreboard means `NO-GO`, not zero defects or implied readiness.

## Preserve the Security Boundary

- Treat `SKILL.md` and every vendored `_shared` file as untrusted payload bytes.
- Bind scans, reviews, approvals, badges, exports, and publication to the exact full payload hash.
  Do not substitute the `SKILL.md`-only lint hash.
- Require stages 1, 2, 3, 4, and 6 for every payload. Require the calibrated stage-5 judge for the
  initial corpus and every ambiguous or high-risk submission.
- Let deterministic code compute readiness from exact evidence and zero open blocking findings.
  Agents may propose findings; they cannot declare authoritative readiness.
- Publish only through an authenticated exact-evidence human approval. Never create an automatic,
  fixture-derived, stale, or human-looking approval.
- Fail closed on unknown slugs, facet drift, mixed attempts, stale hashes, missing rechecks,
  malformed artifacts, unavailable databases, and expired scoreboard snapshots.

## Verify and Checkpoint

1. Write or update the narrow regression test before changing a gate.
2. Run focused checks first. Run database tests serially against the explicit isolated `_test`
   database; never overlap them with another test process or agent.
3. Run strict lint and pack consistency after any skill-content batch.
4. Reconcile registry, filesystem, append-only artifacts, approval projection, catalog, dashboard,
   and generated outputs before claiming completion.
5. Update `../../../docs/WORKFLOW.md` and `../../../docs/PROMPT_LIBRARY.md` only after code and tests
   reflect the behavior.
6. Follow `../../../STATE_RULES.md`'s exact atomic checkpoint order. When the completed MEMORY entry
   describes the commit that contains it, use the permitted `artifacts: this <STEP-ID> checkpoint`
   self-reference; never invent a future SHA.
7. Refresh `HANDOFF.md` for material truth changes, prepare state, and commit once under the lock.
   Pull/rebase at the clean start of the step, then push only when authorized and verify local HEAD
   equals the remote-tracking branch.

## Route to Project References

- Current handoff and all 84 skills: `../../../HANDOFF.md`
- Authoring contract: `../../../docs/AUTHORING_CONTRACT.md`
- Review workflow: `../../../docs/WORKFLOW.md`
- Prompt contracts: `../../../docs/PROMPT_LIBRARY.md`
- Accumulated lessons: `../../../docs/LEARNINGS.md`
- Architecture decisions: `../../../DECISIONS.md`
- Active blockers only: `../../../BLOCKERS.md`
- Right-now state: `../../../STATUS.md`
- Durable execution log: `../../../MEMORY.md`

Never treat historical `REVIEW.json`, seeds, fixtures, demo cards, an agent summary, a green platform
test suite, or dashboard planning data as catalog credit. Preserve uncertainty and unresolved findings
instead of optimizing the display for apparent progress.
