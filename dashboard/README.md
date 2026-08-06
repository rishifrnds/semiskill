# SemiSkill Command Centre

A live, single-page control surface for project build state, architecture, verification, features,
security, catalog coverage, launch planning, go-to-market hypotheses, analytics and governed work
requests.

```bash
python dashboard/server.py        # http://127.0.0.1:8899
```

## What is live versus curated

| Live and re-derived | Curated in `model.json` |
|---|---|
| Git branch, commits and dirty files | Feature register and declared status |
| Module inventory and LOC | Risks and launch checklist |
| Static test-function inventory (no execution result) | Metric targets, proposed pricing and channels |
| Read-only Postgres artifact-store liveness | Integrity-pinned schema-v1 request templates |
| Raw artifact counts when the database is available | Go-to-market hypotheses and draft assets |
| Server-validated canonical scoreboard and progress | |
| Exact migration/schema witness and redacted adoption provenance | |
| Red-team input inventory and explicit execution availability | |
| Durable request receipts | |

Curated values are planning inputs, not measured outcomes. The UI must label them as such and must
not turn their presence into feature, verification, adoption or launch credit.

Configure the authoritative catalog inputs before starting the server:

```powershell
$env:SEMISKILL_ENVIRONMENT = "development"
$env:SEMISKILL_SCOREBOARD_SNAPSHOT = "reports/scoreboard/latest.json"
$env:SEMISKILL_PROGRESS_SNAPSHOT = "reports/scoreboard/progress.json" # optional
$env:SEMISKILL_SCOREBOARD_MAX_AGE_SECONDS = "900" # 15..3600
$env:SEMISKILL_PROGRESS_MAX_AGE_SECONDS = "300"   # 15..3600
```

The dashboard accepts only an observation-bound `semiskill.scoreboard/v2` snapshot for the exact
`dv-84` scope and canonical registry/skills paths. It verifies age, the exact clean Git commit,
registry bytes, every file below `skills/**` including `_shared`, per-skill payload hashes, live
database identity/state, all migration checksums and current structural security attestations. The
Git witness is checked again after recomputation to close source-change races.

If any witness is absent or mismatched, catalog metrics remain unavailable. API rows, database
counts, seeds and fixtures are never substitutes. Progress is independently age- and causality-
checked. Only a sanitized migration/adoption projection reaches the browser. The adversarial corpus
is input inventory only until a corpus-hash-bound execution result exists; no inferred escape or pass
outcome receives credit.

## Governed request loop

Every action control submits only a template ID, page-level dashboard context, priority and UUID.
The server hashes the exact `model.json` bytes before parsing, verifies the adjacent `model.sha256`,
validates the complete `semiskill.dashboard-model/v1` non-crediting contract, and requires every
resolved schema-v1 action template to match its code-reviewed digest allowlist. It then durably
appends a non-crediting journal row to `dashboard/inbox.jsonl` and responds only after `fsync`.
Each model-dependent operation performs one raw model read, checks the adjacent and startup hashes
before UTF-8 decoding or JSON parsing, then derives both curated state and public actions from that
one parsed snapshot. `/api/state` obtains the model and inbox view together under the queue lock;
body-only drift and a correctly re-pinned post-start body both return fail-closed unavailability.

The durable journal row contains the template provenance and server-only prompt; prompt text and the
registry hash are removed from every browser projection:

```json
{"schema_version":"semiskill.dashboard-request/v1","receipt_id":"ACT-...","request_id":"...","template_id":"A-01","template_sha256":"sha256:...","status":"queued","credit":"none"}
```

The smaller HTTP acceptance receipt contains only the receipt/request IDs, accepted timestamp,
request type, template ID, action hash and queued status. Neither representation earns workflow or
launch credit.

The browser cannot submit a title, prompt, kind, status, executable command or free text. A mutation
requires the exact loopback Host and Origin, a per-process same-origin CSRF capability, strict UTF-8
JSON, a bounded body and one of the 36 unique server templates. UUID retries are idempotent only for
the same pinned model registry; a UUID from another registry or reused for another action fails closed.

The request library spans Build, Security, Ops, Marketing, Sales, Analytics and Quality. Section-level
controls select fixed templates and a page-level context; they do not claim that a particular table
row was selected and never synthesize prompt prose in the browser. Legacy/raw rows are displayed as
quarantined and must never be auto-worked.

`Archive current request journal` is protected by the same Host/Origin/CSRF boundary and may include
requests accepted after the browser's last refresh. The server first commits a canonical archive
intent, then moves the exact journal to its collision-safe recovery file. Restart recovery completes
an interrupted intent exactly once. Every model-dependent read, replay and mutation first reloads one
pinned semantic model snapshot and then validates the sidecar's IDs, timestamp, path, byte hash and
row count plus global request/receipt uniqueness before proceeding. The response records the row
count, file hash and recovery reference.

## Queue-only authority

Dashboard mutation requests never start tests, containers, migrations, approvals, publications or
external communications. Read-only state collection may run bounded local probes. A separate worker
must validate a receipt and perform work under the normal repository, identity and isolated-database
gates before attaching evidence.

A dashboard receipt is not an artifact, scan, review, approval, publication, test result or authority
to contact an external party. It never changes the deterministic scoreboard or launch gate.

## Design

The page uses shadcn-style HSL tokens, responsive cards, badges, tables and progress primitives in a
dark theme. Charts use a pinned integrity-checked Chart.js CDN; diagrams are inline SVG. Tables,
diagrams and KPIs still render if the chart CDN is unavailable.

The page refreshes every 15 seconds while visible. `model.json` is security-sensitive server
configuration: its prompt strings become separate-worker input even though they are never
browser-executable. The adjacent digest detects inconsistent checkout/runtime drift, while the exact
schema and action-template allowlist stop a correctly re-pinned model from gaining evidence credit or
widening worker prompts. Neither proves human review or defends against an actor who can also rewrite
the validator code. Any one-file pin mismatch, semantic violation, unapproved prompt or post-start
model drift fails all model-dependent state and queue surfaces closed. Production authenticity must
come from the normal reviewed commit/release provenance, not this local digest alone.

The local queue integrity boundary covers accidental corruption, interrupted writes and cooperating
processes that respect the queue lease. Its hashes are unkeyed: an actor with direct write access to
the journal or archive can construct self-consistent forged rows without changing the server or
model. The lease is therefore a coordination mechanism, not an authorization boundary. Repository
and host filesystem ACLs are the trust root for every direct writer.
