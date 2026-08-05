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
| published catalog size (when the read API is up) | |
| the action queue itself | |

The page auto-refreshes every 60s while it is visible. `model.json` is plain data — edit it and
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

## Running commands

The Overview page can run a small whitelist locally (`RUNNABLE` in `server.py`): the test suite, the
seed demo, the Postgres container, the read API, and `git status`. Output lands on the
**Quality & Bugs** page and in `dashboard/runs/`. Nothing else is runnable — the server never
executes a caller-supplied string, and binds to `127.0.0.1` only.

## Design

shadcn/ui token system (HSL CSS variables, card / badge / button / table / progress primitives) in a
tweakcn-style dark theme. Charts are Chart.js from a pinned, integrity-checked CDN; diagrams are
inline SVG driven by the same tokens, so they follow the theme. No build step, no framework, no npm.

If the CDN is unreachable the page still renders — tables, diagrams and KPIs are plain DOM; only the
charts go blank.
