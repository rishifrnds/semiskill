# SemiSkill

An **internal, security-verified Agent-Skill marketplace** — a company-private analogue of `skills.sh`
where employees publish, discover, search, comment on, rate, and reuse Agent Skills, and where **no
skill becomes discoverable until it passes an automated security-verification pipeline and a human
approval gate.** Publishing is a *gated actuator*, never a direct write.

Built as a concrete [AIOS](https://…) 6-layer instance (mirrors `E:\code\aios`).

## Why
Agent Skills are high-leverage but a malicious or careless skill is a prompt-injection /
data-exfiltration / tool-abuse vector (cf. EchoLeak, CVE-2025-32711). SemiSkill makes **verification a
precondition of publishing**, so there is one internal place to safely share skills.

## The load-bearing property
> No skill is discoverable in the catalog until it has been **scanned** (six stages) and
> **human-approved**. The catalog is written **only** by the approval actuator. Every action is an
> immutable, ACL-labeled, provenanced artifact.

This is enforced *structurally*, not by prompting, and exercised by deterministic and fixture-backed
security tests. The seven-entry adversarial corpus is input inventory only; authoritative corpus execution is currently unavailable, so it supplies no blocked-attack or zero-escape claim.

## Architecture (AIOS 6 layers)
| Layer | Module(s) | Role |
|-------|-----------|------|
| L1 Capture | `capture/`, `cli.py` | ingest submissions → `skill_version` artifacts |
| L2 Spine + Artifacts | `artifacts/`, `spine/` | append-only store + five-class spine + derived lifecycle |
| L3 Context | `context/`, `api.py` | ACL-enforced catalog search / lineage / reuse (+ read API) |
| L4 Governance | `governance/`, `spine/pipeline.py` | 6-stage pipeline + gated publish + rollback |
| L5 Intelligence | `intelligence/`, `governance/cost.py` | stability gate + queue ranking + model routing |
| L6 Sensor | `scanners/`, `sensor/` | deterministic scanners + calibrated LLM-judge |

The verification pipeline (per submission): **static structure → security-audit → held-out injection
corpus → secret/PII → calibrated LLM-judge → aggregate verdict** → human approval → publish.

## Quick start
```bash
docker compose up -d db                        # local Postgres 16 (127.0.0.1, egress-controlled)
pip install -e ".[dev]"
pytest                                          # full suite (unit + integration; ~180 tests)

semiskill submit ./path/to/skill-dir            # L1 intake (state: submitted — NOT published)
python -m semiskill.api                          # L3 read API on http://127.0.0.1:8787
```
> Use `127.0.0.1`, not `localhost`, in `DATABASE_URL` on Windows (localhost prefers IPv6 and stalls).

## UI
- Demonstrable catalog design: [`ui/catalog-demo.html`](./ui/catalog-demo.html) (verification-badge-centric).
- Production path: [`ui/`](./ui/README.md) — Next.js + shadcn, SharePoint-embeddable (ADR-004).

## Docs
- [`docs/SECURITY.md`](./docs/SECURITY.md) — the security model, invariants, roles, egress, redaction, rollback.
- [`docs/ADOPTION.md`](./docs/ADOPTION.md) — how to submit, review/approve, discover, and reuse.
- `DECISIONS.md` — ADRs. `MEMORY.md` / `STATUS.md` — build state (see `STATE_RULES.md`).

## Known gaps (see `MEMORY.md`)
Live stage-2 security-audit (egress sandbox + claude-flow), live stage-5 judge (API keys), pgvector
semantic search (Voyage egress), and SharePoint tenant embedding are stubbed/deferred — each needs an
external resource not available in this environment; all are tested via injected fakes or demonstrated.
