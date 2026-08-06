# SemiSkill handoff

Current objective: finish and ship the existing 84 active DV skills. The 20 declined registry cells
remain non-crediting provenance; the proposed 19-level expansion is deferred.

## Truth now

- Registry: 84 active + 20 declined across 16 roles; each role has at least five authored skills.
- Source: exactly 84 skill payloads. Strict lint is clean; pack consistency has zero errors and 60
  non-blocking warnings.
- Canonical readiness/approval/publication: 0/84. Old sidecar claims and test fixtures receive no
  credit.
- Production activation: blocked by `BLK-001` until Entra/OIDC, SharePoint, and least-privilege
  production identities are supplied. Development work can continue.
- Single writer: obey `.session-lock` and `STATE_RULES.md`. Never run database tests concurrently.

## Approval-bound shared topology

ADR-023 resolves the previous unapproved dependency gap. `skills/_shared` contains exactly three
allowlisted source files. Capture safely snapshots them once per batch and vendors the exact bytes
into each skill-version payload under `_shared/`. Those bytes now participate in payload hashing,
all scanners, content review, human approval, publication, install prompts, catalog and release
verification.

Release stays per skill (`<slug>/_shared/...`) because Agent Skills resolves relative resources from
the skill root. The pack refuses missing/extra/shadowed/unresolved files, mixed shared epochs, or any
staged byte that does not rebuild to the approved payload hash. A shared-source edit invalidates the
affected evidence and requires semver, scans, fresh review and a new approval.

## Current gate contract

- `semiskill wave` captures/scans only and creates zero approvals/publications.
- Write waves and review collections are capped at 10 unique skills.
- P1 and P5 return typed findings. P1 is preserved as an initial canonical review but cannot create
  readiness; P5 is the calibrated independent recheck.
- The atomic collector rejects stale hashes/facets, unknown or missing slugs, mixed attempts/runs,
  malformed booleans, reused identities, and lineage collisions.
- Deterministic code alone computes readiness. Only an authenticated human exact-evidence decision
  may publish.
- The old file-based JS/Python gate drivers are explicit tombstones. Use `docs/WORKFLOW.md` and
  `docs/PROMPT_LIBRARY.md`.

## Immediate order

1. Finish J-010c scoreboard/dashboard exposure of current-source versus approval-bound shared
   digests and verify the command-centre views.
2. Build/verify the production Next.js catalog and accessibility/security contract.
3. Re-review/fix/fresh-recheck all 84 in batches of at most 10: 3 provisional-ready, then 32
   reviewed-not-ready, then 49 never-reviewed.
4. Present human approval batches of at most 10, publish only exact approved versions, regenerate
   scoped outputs, and prove 84/84 plus 16/16 roles at five or more.
5. Run the immutable serial full suite on the final clean commit and repeat desktop/mobile browser
   verification before launch.

## Primary commands

```powershell
python -m semiskill.cli lint skills --strict
python -m semiskill.cli wave-plan skills --only slug-a,slug-b
python -m semiskill.cli wave skills --only slug-a,slug-b --yes --reports reports/batch-001
python tools/collect_wave.py --contract reports/batch-001/contract.json --results reports/batch-001/p5-results.json
python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json --snapshot-out reports/scoreboard.json --environment development --json
python -m semiskill.cli verify-full-suite --expected-database semiskill_test
```

Exports require the validated canonical scoreboard snapshot and one exact permission label. Never
substitute a seed, fixture, preview, old run, or agent-calculated count.
