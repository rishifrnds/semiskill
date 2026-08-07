# SemiSkill

SemiSkill is an **internal, security-verified Agent Skill marketplace**: a company-private analogue
of skills.sh where employees can publish, discover, comment on, rate and reuse skills. A skill is
discoverable only after its exact payload passes the automated verification chain, independent
content review and an authenticated human approval gate. Publishing is a gated actuator, never a
submitter write.

## Current launch truth

The repository contains exactly **84 active DV skills across 16 roles**, with at least five authored
skills per role. All 84 pass strict authoring lint. **None currently has a complete current canonical
review/approval/publication chain, so launch status is NO-GO.** Historical sidecars, fixtures, demo
cards and prior shared-file hashes receive no publication credit.

Read [HANDOFF.md](./HANDOFF.md) for every skill, exact evidence IDs, live blockers, implementation
status, forecasts and the ordered route to launch. Project operators should use
[the SemiSkill project skill](./.agents/skills/semiskill-project/SKILL.md).

## Load-bearing property

> No skill is discoverable until its exact full payload has complete required scan evidence,
> independent hash-bound content review, and an authenticated human approval. The catalog is written
> only by the approval actuator, and every transition is an immutable ACL-labeled artifact.

This is enforced structurally. The held-out injection corpus remains outside pipeline-agent write
scope. A green platform test run is non-crediting and does not imply any skill is approved.

## AIOS mapping

| Layer | Modules | Responsibility |
|---|---|---|
| L1 Capture | `semiskill/capture/`, `semiskill/cli.py` | Capture exact submitted payloads |
| L2 Spine + artifacts | `semiskill/artifacts/`, `semiskill/spine/` | Append-only artifacts and lifecycle |
| L3 Context | `semiskill/context/`, `semiskill/api.py` | ACL-enforced catalog, lineage and reuse |
| L4 Governance | `semiskill/governance/`, `semiskill/spine/pipeline.py` | Six-stage gate and human approval |
| L5 Intelligence | `semiskill/intelligence/` | Suggest-only stability/controller logic |
| L6 Sensor | `semiskill/scanners/`, `semiskill/sensor/` | Deterministic scans and calibrated judge |

Required flow: static structure → deterministic security scan → held-out injection corpus →
secret/PII scan → calibrated judge when required → aggregate verdict → independent content review →
authenticated human approval → publication projection.

## Local development

```powershell
docker compose up -d db
pip install -e ".[dev]"

# Authoring evidence only; this does not publish anything.
python -m semiskill.cli lint skills --strict

# Fixed serial, source-bound platform proof against the isolated test database.
python -m semiskill.cli verify-full-suite --expected-database semiskill_test

# Read API and local command centre.
python -m semiskill.api
python dashboard/server.py
```

Use `127.0.0.1`, not `localhost`, in Windows database/runtime URLs. Never run database tests in
parallel: the fixtures intentionally reset isolated tables and concurrent runs corrupt each other's
evidence.

Local command centre: [http://127.0.0.1:8899/](http://127.0.0.1:8899/). It is read-only and must show
unavailable when its canonical scoreboard or source evidence is stale.

## Interfaces

- Production catalog path: [`ui/`](./ui/README.md) — Next.js per ADR-004; implementation and launch
  verification remain incomplete.
- Offline/demo artifact: [`ui/catalog-demo.html`](./ui/catalog-demo.html) — not a production catalog
  and not authoritative evidence.
- Workflow: [`docs/WORKFLOW.md`](./docs/WORKFLOW.md)
- Prompt contracts: [`docs/PROMPT_LIBRARY.md`](./docs/PROMPT_LIBRARY.md)
- Security model: [`docs/SECURITY.md`](./docs/SECURITY.md)
- Authoring contract: [`docs/AUTHORING_CONTRACT.md`](./docs/AUTHORING_CONTRACT.md)
- Accumulated lessons: [`docs/LEARNINGS.md`](./docs/LEARNINGS.md)
- Architecture/state: [`DECISIONS.md`](./DECISIONS.md), [`STATUS.md`](./STATUS.md),
  [`MEMORY.md`](./MEMORY.md), [`BLOCKERS.md`](./BLOCKERS.md), [`STATE_RULES.md`](./STATE_RULES.md)

## Current high-risk gaps

- The held-out red-team corpus has no current result to report, because
  authoritative corpus execution is currently unavailable. No adversarial pass rate, escape count or
  blocking claim should be read into this repository. Absence of a result is not a clean result.
- Stage 2 needs the internally governed deterministic scanner selected by ADR-024; the old
  claude-flow path cannot earn credit.
- Stage 5 needs a loopback-only runtime, exact adapter and independently labeled calibration report.
- Coordinator-only review issuance, scoreboard v3 and shared live reconciliation remain to build.
- The Next.js production catalog, Entra/OIDC, SharePoint tenant integration, distinct production
  identities, CI/deploy/backup/alerts and market-launch approvals remain incomplete.

See [HANDOFF.md](./HANDOFF.md) and [BLOCKERS.md](./BLOCKERS.md) rather than inferring progress from
test counts or historical publication records.
