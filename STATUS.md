<!--
Ephemeral right-now snapshot. OVERWRITE this file, never append.
Target length: under 40 lines. Full rules: see STATE_RULES.md.
-->

# STATUS — SemiSkill
_Last updated: 2026-07-13T04:20Z_

## Session
- ID: 20260713T024006Z-Rishi_PC-2a55fa
- Started: 2026-07-13
- Host: Rishi_PC
- Lock held: yes (.session-lock refreshed 2026-07-13T04:20Z)

## Right now
Phase B. L1 done (B-001..003); L3 seams done (B-004 acl+untrusted). 27 unit tests green.
Next: B-005 migration 0002_context.sql (SECURITY DEFINER catalog_search / lineage / reuse_graph,
ACL-filtered, EXECUTE-only to semiskill_app), then B-006 retrieve, B-007 provenance, B-008 gate.

## Active step
- Step ID: B-004 (done) -> B-005 (migration 0002 context functions)
- Sub-state: committing B-004
- Started: 2026-07-13T04:20Z

## Last commit
- SHA: 6982e3a (B-003)
- Message: wip: B-003 CLI (semiskill submit/list)
- Time: 2026-07-13

## Next action (one step ahead)
B-005: semiskill/artifacts/migrations/0002_context.sql — catalog_search(query,facets,allowed_labels),
lineage(start,allowed,max_depth), reuse_graph(skill_id,allowed) as SECURITY DEFINER (search_path pinned),
ACL-filtered by permissions_label, GRANT EXECUTE to semiskill_app only. Mirror aios 0004_provenance.sql.

## If I crash right now, resume by:
Read MEMORY.md → Phase B Pending (B-005..B-008). DB: `docker compose up -d db` (127.0.0.1). Tests:
`pytest`. Catalog = PUBLISHED skill_versions (positive published `approval`, per Phase A lifecycle.py).
AIOS ref: migration 0004_provenance.sql (recursive lineage + visibility gate), provenance.py.
