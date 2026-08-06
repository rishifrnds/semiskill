# The execution workflow

This is the operating procedure for finishing and releasing the 84 active DV skills. The 20
declined registry cells are provenance only. The deferred 19-level expansion does not count in this
phase.

Companion documents:

- `docs/PROMPT_LIBRARY.md` — exact worker prompts and output schemas.
- `docs/AUTHORING_CONTRACT.md` — the content and metadata contract.
- `STATE_RULES.md` — the single-writer checkpoint protocol.
- `specs/skill_registry.json` — the 84-active/20-declined plan of record.

## The invariant

```text
source -> strict lint -> security stages 1/2/3/4/5/6 -> independent content review
       -> deterministic readiness -> authenticated human approval -> verified publication
```

- Every submitted body and helper file is untrusted data. It cannot widen file scope, tools, or
  network access.
- Agents report typed findings; they never create authoritative readiness, approval, publication,
  or scoreboard counts.
- Content review is an append-only `review` artifact tied to one exact skill-version ID and payload
  hash. `skills/<slug>/REVIEW.json` is legacy provenance only and must not remain in a skill payload.
- The fixer and rechecker are different runtime identities. P5 always starts in a fresh context that
  has not received fixer reasoning.
- Only deterministic code can compute `recheck-ready`, and only an authenticated human decision can
  publish the exact reviewed version.
- A stopped or failed worker creates no completed review artifact. Open or disputed blocking
  findings remain visible and block publication.

## 0. Restore trustworthy state

Read `STATE_RULES.md`, `STATUS.md`, the tail of `MEMORY.md`, `BLOCKERS.md`, and `DECISIONS.md`. Confirm
the PID recorded in `.session-lock`, take over only through the documented stale-lock procedure, and
keep one filesystem writer. Pull/reconcile before the first edit and checkpoint every atomic step.

Start the development database and establish the non-mutating baseline:

```powershell
docker compose up -d db
python -m semiskill.cli lint skills --strict
python -m semiskill.cli wave-plan skills
python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json --json
```

Never run database tests concurrently. Test fixtures use an isolated lowercase `*_test` database;
the development catalog must never be the test target.

Accept this step only when the registry reports 84 active and 20 declined, disk has exactly 84
registered skill directories, and consistency has zero errors. Counts come from the deterministic
scoreboard, not seeds, fixture fallbacks, old Markdown, or agent summaries.

## 1. Capture the exact dependency closure

`skills/_shared` is one canonical authoring source containing exactly:

- `_shared/failure-signature-schema.md`
- `_shared/handoff-vocabulary.md`
- `_shared/team-profile.md`

Capture safely reads those three files once per batch and vendors their exact bytes into every
skill-version payload. Unknown, missing, linked, shadowed, malformed, oversized, or unresolved
shared files fail before an artifact is written. Because Agent Skills resolves resources relative
to the directory containing `SKILL.md`, an approved release retains the three files under every
`<slug>/_shared/` directory.

A change to any canonical shared byte changes every affected payload hash. It therefore requires a
monotonic version bump, new scans, a fresh independent review, and a new human approval. Export reads
only frozen payload bytes; it never falls back to mutable repository `_shared` content.

## 2. Work in batches of at most 10

At most three read-only worker tasks may run concurrently. The coordinator is the only repository
writer and serializes collectors, database operations, edits, and tests.

Select exact slugs and preview them:

```powershell
python -m semiskill.cli wave-plan skills --only slug-a,slug-b
python -m semiskill.cli wave skills --only slug-a,slug-b --yes --reports reports/batch-001
```

A write wave larger than 10 is refused before touching the store. `wave` may capture, scan, reuse an
identical security chain, and queue exact evidence. It always creates zero approvals and zero
publications.

Process in this order:

1. Re-review the 3 formerly nominal-ready skills.
2. P4 fix then fresh P5 recheck for the 32 previously reviewed-but-not-ready skills.
3. P1 review, P2 fix, then fresh P5 recheck for the 49 never-reviewed skills.
4. Repeat fix then fresh recheck until no blocking finding remains or a real human/domain decision
   is required.

Historical counts only determine ordering. Every current result must bind the shared-inclusive exact
version generated in this run.

## 3. Issue and collect a review contract

For each batch, the coordinator creates a JSON contract from the just-written wave report and the
artifact store. It contains no more than 10 unique cells and fixes:

```json
{
  "batch_id": "batch-001",
  "attempt": 1,
  "prompt_version": "P5-RECHECK-CALIBRATED@3",
  "cells": [
    {
      "slug": "dv-example",
      "skill_version_id": "UUID",
      "skill_payload_sha256": "64 lowercase hex characters",
      "version": "1.2.0",
      "role": "registry role",
      "level": "registry level"
    }
  ]
}
```

The worker receives one leased slug/hash, an explicit read scope, a tool allowlist, and network
denial. P1 and P5 return typed findings with `category`, `severity`, `evidence`, `location`,
`required_change`, and `disposition`. A later attempt also names the one prior review artifact.

Collect only through the batch-atomic collector:

```powershell
python tools/collect_wave.py --contract reports/batch-001/contract.json `
  --results reports/batch-001/p5-results.json
```

The whole batch is rejected on an unknown/missing/duplicate slug, wrong version/hash/facet, mixed
run/batch/attempt/prompt, malformed boolean, reused reviewer identity, missing prior round, or
lineage collision. Earlier rounds remain append-only. The worker's optional `ready` value is retained
only as an agent claim; deterministic readiness is `all required checks passed AND zero open
blocking findings AND exact lineage/hash match`.

## 4. Fix and independently recheck

P2/P4 may edit only the leased source skill directory. They preserve registry role/level, do not
touch `_shared`, and monotonically bump `semiskill-version` for substantive changes. The coordinator
then reruns strict lint and consistency, captures the new exact version, and starts P5 in a fresh
context.

After every batch:

```powershell
python -m semiskill.cli lint skills --strict
python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json `
  --snapshot-out reports/scoreboard.json --environment development --json
```

Accept only zero error-level consistency findings, exact source/review hashes, and no open blocking
findings for cells labelled `recheck_ready`.

## 5. Human approval and publication

Present approval batches of at most 10. The human must inspect the exact automated and content review
references and make one explicit decision per exact payload:

```powershell
python -m semiskill.cli approve <skill-version-uuid> `
  --automated-review <review-uuid> `
  --content-review <review-uuid> `
  --expected-sha256 <payload-sha256> `
  --decision approve `
  --reason "Reviewed exact evidence and approved for the public DV catalog." `
  --environment development
```

Development approval binds the logged-in OS identity. Production accepts only the Entra/OIDC
adapter and fails closed until its tenant configuration exists. There is no auto-approver and no
`--allow-ungated` path. A later source or review change cannot rewrite the frozen badge on an older
publication.

## 6. Scoreboard and command centre

The canonical snapshot is the only launch authority:

```powershell
python -m semiskill.cli scoreboard --skills skills --registry specs/skill_registry.json `
  --snapshot-out reports/scoreboard.json --environment development --json
```

It must expose the full 84-cell funnel, every role/level cell, exact artifact and payload hashes,
database identity/freshness, anomalies, and deterministic release checks. Ephemeral worker status is
separate and cannot alter counts. If the snapshot/API is absent, stale, source-mismatched, or database-
mismatched, the dashboard shows unavailable; it never substitutes seeds or fixtures.

P7 may explain this validated JSON but cannot run commands, recompute counts, edit data, or infer
missing values.

## 7. Export and verify

Only a validated snapshot and one permission label may authorize an export:

```powershell
python -m semiskill.cli catalog --scoreboard-snapshot reports/scoreboard.json `
  --permission-label public --environment development
python -m semiskill.cli site --scoreboard-snapshot reports/scoreboard.json `
  --permission-label public --environment development
python -m semiskill.cli pack --scoreboard-snapshot reports/scoreboard.json `
  --permission-label public --environment development
```

The pack refuses unresolved references, noncanonical shared sets, mixed approved shared snapshots,
or any staged byte that does not rebuild to its approved payload hash. Each installed skill is
self-contained; its `_shared/` files are frozen approval-bound support copies.

Run focused tests after each batch and the fixed serial full suite every three batches and before an
approval/export milestone:

```powershell
python -m semiskill.cli verify-full-suite --expected-database semiskill_test
```

P8 is read-only and reports findings to a separate fixer. A suite result or agent report is evidence,
not catalog credit.

## Definition of done

- 84/84 authored, strict-lint-passing, security-passing, independently reviewed, recheck-ready,
  explicitly human-approved, and projection-backed published.
- 16/16 roles have at least five published skills.
- Zero unresolved blockers, consistency errors, facet drift, stale hashes, unregistered skills or
  publications, permission drift, ungated approvals, and mixed shared snapshots.
- Full Python and UI suites pass on isolated infrastructure; browser accessibility, hostile Markdown,
  responsive layout, clipboard failure, and Next.js production build checks pass.
- Catalog/site/pack bytes match frozen approved payloads; search, facets, lineage, audit evidence,
  install inventory, and ACL-scoped exports are verified.
- Dashboard, workflow, prompt library, state files, launch evidence, and rollback references are
  current. Production activation remains blocked until the Entra/SharePoint tenant values and
  least-privilege identities in `BLOCKERS.md` are supplied.
