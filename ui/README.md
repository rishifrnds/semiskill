# SemiSkill Catalog UI (production path — ADR-004)

The catalog is a **Next.js + shadcn/ui** web app that reads the ACL-enforced L3 read API
(`semiskill/api.py`) and is **embedded into a SharePoint page** via an iframe web part (or a thin SPFx
wrapper). It is **read-only**: nothing here writes the catalog — publishing stays behind the
human-gated approval actuator (ADR-002). The demonstrable design lives in
[`catalog-demo.html`](./catalog-demo.html) (self-contained, theme-aware); this directory is the
production scaffold.

## What ships
- **Catalog** — full-text + faceted browse (`function` / `role` / `level` / tags), each card leading
  with its **verification badge** (verdict + safety meter + the 6 scan-stage results). skills.sh's
  "Audits" made mandatory: a skill with no passing `scan_run` + `approval` is simply not here.
- **Skill detail** — README, allowed tools, provenance (submitted → scanned → reviewed → approved ·
  human → published), the full scan report, version history, comments, rating, one-click reuse
  (`skills add <slug>` copy).
- **Review queue** (reviewer role) — pending skills ranked risk-first (`GET /queue`).
- Motion polish via `heygen-com/hyperframes`; components from `shadcn/ui`.

## Data source
All data comes from the read API — never a direct DB call from the browser:
`GET /catalog?q=&function=&role=&level=` · `GET /skill/<id>` · `GET /queue` · `GET /lineage/<id>` ·
`GET /reuse/<id>`. Restricted requests carry a verified Entra/OIDC bearer token. The API maps the
authenticated tenant, object ID, and groups to permission labels server-side; caller-supplied label
headers are ignored. Requests without a token receive public-only results. See `lib/api.ts`.

## Run (production path — remaining productionization)
```bash
docker compose up -d db                      # from the repo root
python -m semiskill.api                       # read API on http://127.0.0.1:8787
cd ui && npm install && npm run dev            # Next.js on http://localhost:3000
```
> GAP: `npm install`/`build` and the SharePoint tenant embedding are **not exercised in this
> environment** (no M365 tenant per ADR-004). The design is demonstrated by `catalog-demo.html`; the
> read API is tested (`tests/api/`). Wiring shadcn/hyperframes and the SPFx web part is the remaining
> step.

## SharePoint embedding (ADR-004)
1. Host the Next.js app (internal URL, egress-controlled).
2. Add an **Embed** web part (or a minimal SPFx web part) to the SharePoint page pointing at it.
3. Forward the signed-in user's Entra/OIDC bearer token to the API. Configure the server-side group
   mapping and a dedicated clearance database identity; never trust browser-supplied labels.
