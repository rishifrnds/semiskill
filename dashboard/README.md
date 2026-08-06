# SemiSkill Command Centre

A live, single-page control surface for the whole project: build state, architecture, the
verification pipeline, features and gaps, security posture, the catalog, launch readiness, and the
go-to-market plan — plus **buttons that queue work for Claude**.

```bash
python dashboard/server.py        # → http://127.0.0.1:8899 (opens your browser)
```

## What is live vs. curated

| Live (re-derived on every load) | Curated (`model.json`) |
|---|---|
| git branch, commits, dirty files | feature register + status |
| module list + LOC per AIOS layer | risks, launch checklist, GTM plan |
| test files + `pytest --collect-only` count | metric targets, pricing, channels |
| Docker / Postgres / read-API liveness | the 30 prepared task prompts |
| artifact counts + type mix (when the DB is up) | |
| server-recomputed canonical scoreboard + worker progress snapshots | |
| exact migration tracker, current schema witness, and redacted adoption provenance | |
| red-team input inventory + explicit execution availability | |
| the action queue itself | |

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
registry bytes, every file below `skills/**` (including `_shared`), per-skill payload hashes, live
database identity/state, all 15 migration checksums, and current structural security attestations.
The Git witness is checked again after recomputation to close source-change races. If any witness is
absent or mismatched, catalog metrics remain explicitly unavailable; API rows, database counts,
seeds and test fixtures are never substitutes. Progress is independently age- and causality-checked
against the loaded scoreboard and may be unavailable while the scoreboard remains available.
Only a fixed, sanitized migration/adoption projection reaches the browser; operator identity,
authentication context, reasons, endpoints and raw manifests remain server-side.
The adversarial fixture is input inventory only. Until a corpus-hash-bound execution result is
persisted, escape counts and outcomes display **not executed** and receive no feature, launch, or
analytics credit.

The page auto-refreshes every 15s while it is visible. `model.json` is plain data — edit it and
reload; nothing in it is code.

## The feedback loop

Every ⌘ button on the dashboard appends one JSON line to `dashboard/inbox.jsonl`:

```json
{"id":"A-01","ts":"…","kind":"build","title":"Build the approver console","prompt":"…","status":"queued"}
```

Then in Claude Code, say **"work the queue"** — Claude reads the file, takes the tasks in order, and
works them. Three ways to queue:

- **Prepared actions** — the task library on the Action Queue page (30 actions across Build,
  Security, Ops, Marketing, Sales, Analytics, Quality).
- **Contextual buttons** — every risk, gap, feature, checklist item, metric, channel, ADR, stage and
  catalog entry has its own ⌘ button that queues a task prefilled with that item's context.
- **Free text** — “Ask Claude anything” in the sidebar, or the box on the Action Queue page.

`Archive queue` rotates `inbox.jsonl` to a timestamped file rather than deleting it.

## Queue-only controls

Dashboard mutation requests never start tests, containers, migrations, approvals, publications,
or external communications. Operational controls append typed requests only; read-only state
collection may run bounded local probes. A separate worker must claim a request, perform the work
under the repository/database gates, and attach verification evidence before any result receives
credit.

## Design

shadcn/ui token system (HSL CSS variables, card / badge / button / table / progress primitives) in a
tweakcn-style dark theme. Charts are Chart.js from a pinned, integrity-checked CDN; diagrams are
inline SVG driven by the same tokens, so they follow the theme. No build step, no framework, no npm.

If the CDN is unreachable the page still renders — tables, diagrams and KPIs are plain DOM; only the
charts go blank.
