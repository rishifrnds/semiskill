<!--
Ephemeral right-now snapshot. OVERWRITE this file, never append.
Target length: under 40 lines. Full rules: see STATE_RULES.md.
-->

# STATUS — SemiSkill
_Last updated: 2026-07-13T04:38Z_

## Session
- ID: 20260713T024006Z-Rishi_PC-2a55fa
- Started: 2026-07-13
- Host: Rishi_PC
- Lock held: yes (.session-lock refreshed 2026-07-13T04:38Z)

## Right now
Phase B nearly done. L1 (B-001..003) + L3 (B-004 acl/untrusted, B-005 migration, B-006 retrieve).
ACL acceptance criterion proven (need-to-know invisible to unauthorized). Next: B-007 provenance.py
(lineage + reuse graph wrappers), then B-008 Phase B verify gate.

## Active step
- Step ID: B-006 (done) -> B-007 (context/provenance.py)
- Sub-state: committing B-006
- Started: 2026-07-13T04:38Z

## Last commit
- SHA: 2bee3df (B-005)
- Message: wip: B-005 migration 0002 L3 context fns
- Time: 2026-07-13

## Next action (one step ahead)
B-007: semiskill/context/provenance.py — get_lineage(dsn, start, principal, max_depth) and
get_reuse(dsn, skill_id, principal) via SET LOCAL ROLE semiskill_app + lineage()/reuse_events_for_skill();
delimited-untrusted nodes, fail-closed pruning. Integration tests (verification trail + reuse; ACL prune).

## If I crash right now, resume by:
Read MEMORY.md → Phase B Pending (B-007 provenance, B-008 gate). DB: `docker compose up -d db` (127.0.0.1).
Tests: `pytest`. Pattern: aios provenance.py (ProvenanceNode + SET LOCAL ROLE + rollback + delimit).
