"""Generate the browsable catalog from what actually published.

Three artifacts, because the places people will look have different constraints:

  * `catalog.html`  — the rich page. Self-contained, no CDN, no fetch: it works from a USB stick, an
                      email attachment, or a SharePoint document library after download. SharePoint
                      Online will NOT render an uploaded .html (it downloads it), so this is a
                      download-and-open artifact, never the entry point.
  * `catalog.md`    — the entry point. SharePoint and OneDrive render Markdown natively in the
                      browser, so this is what a colleague actually clicks.
  * `catalog.csv`   — paste once into a SharePoint list's grid view to get grouped, filterable
                      browse with zero code.

Everything is derived from the catalog read model, so a skill that did not publish cannot appear and
nothing here can be fabricated. `ui/catalog-demo.html` invented install counts, star ratings and an
approver name; presenting invented adoption numbers to the team that is deciding whether to trust
this would be a self-inflicted wound, so none of that exists here.

Skill bodies are UNTRUSTED by this project's own rule. Every value is HTML-escaped on the way in, and
the embedded JSON escapes `</script>` so a body cannot break out of its own data block.
"""
from __future__ import annotations

import csv
import html
import io
import json
from dataclasses import dataclass
from pathlib import Path

from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring import facets as facet_vocab
from semiskill.governance.publish import (
    ApprovalChainInvalid,
    resolve_frozen_approval_evidence,
)
from semiskill.wave import _published_index

LEVEL_ORDER = list(facet_vocab.LEVELS)


class CatalogRefused(Exception):
    """A published record cannot be rendered without a valid frozen approval chain."""


@dataclass(frozen=True)
class CatalogEntry:
    slug: str
    title: str
    description: str
    role: str
    level: str
    function: str
    version: str
    owner: str
    tags: list[str]
    body: str
    slots: int
    verdict: str
    aggregate_safety: float | None
    stages: list[dict]
    approval_id: str
    payload_sha256: str
    automated_review_id: str
    content_review_id: str


def collect(store: ArtifactStore) -> list[CatalogEntry]:
    """Read the published catalog + each skill's real scan report."""
    try:
        published = _published_index(store)
    except ApprovalChainInvalid as exc:
        raise CatalogRefused(f"malformed active approval chain: {exc}") from exc

    out: list[CatalogEntry] = []
    for slug, (sv, approval) in sorted(published.items()):
        try:
            frozen = resolve_frozen_approval_evidence(
                store, skill_version=sv, approval=approval,
            )
        except ApprovalChainInvalid as exc:
            raise CatalogRefused(f"{slug}: malformed active approval chain: {exc}") from exc
        p = sv.payload
        review = frozen.automated_review
        body = p.get("body", "")
        out.append(CatalogEntry(
            slug=slug, title=p.get("name") or slug, description=p.get("description", ""),
            role=p.get("role") or "", level=p.get("level") or "",
            function=p.get("function") or "", version=p.get("version", ""),
            owner=p.get("owner") or "", tags=list(p.get("tags") or []),
            body=body, slots=body.count("[[FILL:"),
            verdict=review.payload["verdict"],
            aggregate_safety=float(review.payload["aggregate_safety"]),
            stages=[{
                "artifact_id": str(scan.artifact_id),
                "stage": scan.payload["stage"],
                "status": scan.payload["status"],
                "sampled": scan.payload["sampled"],
                "safety": float(scan.payload["safety_score"]),
                "hard_fail": scan.payload["hard_fail"],
            } for scan in frozen.scans],
            approval_id=str(approval.artifact_id),
            payload_sha256=approval.payload["skill"]["payload_sha256"],
            automated_review_id=str(frozen.automated_review.artifact_id),
            content_review_id=str(frozen.content_review.artifact_id),
        ))
    return out


def _matrix(entries: list[CatalogEntry]) -> tuple[list[str], list[str], dict]:
    roles = sorted({e.role for e in entries if e.role})
    levels = [l for l in LEVEL_ORDER if any(e.level == l for e in entries)]
    cells: dict[str, list[str]] = {}
    for e in entries:
        cells.setdefault(f"{e.role}|{e.level}", []).append(e.slug)
    return roles, levels, cells


def render_markdown(entries: list[CatalogEntry], *, generated_at: str) -> str:
    roles, levels, cells = _matrix(entries)
    L: list[str] = [
        "# DV Agent Skills", "",
        f"{len(entries)} skills, each a single Markdown file you drop into Cursor. "
        "Nothing to install, no admin rights.", "",
        "## Install — about two minutes", "",
        "1. Download the `semiskill-dv` folder from the library beside this page.",
        "2. Put it in `~/.cursor/skills/` (Windows: `%USERPROFILE%\\.cursor\\skills\\`), or in "
        "`<your repo>/.cursor/skills/` to share it with your team through git.",
        "3. Reload Cursor. Type `/` in Agent chat to pick one, or just describe your problem — the "
        "agent reads each description and reaches for the right skill itself.", "",
        "> Needs Cursor 2.4 or newer (Help → About). The same files work in Claude Code, Codex, "
        "Copilot and VS Code — only the folder name changes.", "",
        "## Start here", "",
    ]
    for e in entries[:3]:
        L += [f"### {e.title}", "", f"`/{e.slug}`  ·  {e.role} · {e.level}", "",
              e.description, ""]

    L += ["## Everything in the catalog", "",
          "| Skill | Invoke | Role | Level | Blanks | Verified |", "|---|---|---|---|---|---|"]
    for e in entries:
        safety = f"{e.aggregate_safety:.3f}" if e.aggregate_safety is not None else "—"
        L.append(f"| **{e.title}** | `/{e.slug}` | {e.role} | {e.level} | {e.slots} | "
                 f"{e.verdict} {safety} |")
    L += ["", "## Coverage — who is served, and what nobody has written down yet", "",
          "A green cell means a published skill serves that role at that level. An empty cell is not "
          "a gap in the tool — it is something nobody has written down yet, and the person best "
          "placed to write it is whoever just solved it for the third time.", "",
          "| Role | " + " | ".join(levels) + " |",
          "|---" * (len(levels) + 1) + "|"]
    for r in roles:
        row = [r]
        for l in levels:
            got = cells.get(f"{r}|{l}", [])
            row.append("✅ " + ", ".join(f"`{s}`" for s in got) if got else "—")
        L.append("| " + " | ".join(row) + " |")

    L += ["", "## Making them yours", "",
          "Every skill ships **generic on purpose**, with `[[FILL: ...]]` blanks where your team's "
          "specifics belong. Fill `_shared/team-profile.md` in once — it holds the facts the whole "
          "pack shares (log locations, markers, who signs off) — then open any skill and ask the "
          "agent to fill the rest from your repo.", "",
          "A skill with unfilled blanks will stop and ask rather than invent an answer. That is "
          "deliberate: a confidently invented rerun command costs more than no answer at all.", "",
          "## Adding one", "",
          "The best contributions are usually a single line in a **Gotchas** section — the thing you "
          "only learn by losing a day to it.", "",
          "1. Copy the closest existing skill as a starting shape.",
          "2. Write the procedure the way you would explain it to someone joining next week.",
          "3. Run `python tools/lint_body.py <your-skill>/SKILL.md` — it catches the things that "
          "would stop it being published.",
          "4. Send it back. It goes through the same scan and human approval as everything here.", "",
          "## What \"verified\" means", "",
          "Each skill was scanned before publication: it declares no shell or network tools, "
          "contains no credentials, and its text carries no instructions aimed at your agent. The "
          "per-stage scores are in the table above.", "",
          "That is a statement about **this text on the day it was published**. It is not a runtime "
          "guarantee — Cursor does not enforce the declared tool list — and it is not a promise the "
          "procedure is right for your team. Read anything before you rely on it.", "",
          f"_Generated {generated_at} from the verified catalog._"]
    return "\n".join(L)


def render_csv(entries: list[CatalogEntry]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Title", "Slug", "Role", "Level", "Function", "Description", "Blanks",
                "Version", "Owner", "Verified", "Safety", "Tags"])
    for e in entries:
        w.writerow([e.title, e.slug, e.role, e.level, e.function, e.description, e.slots,
                    e.version, e.owner, e.verdict,
                    f"{e.aggregate_safety:.3f}" if e.aggregate_safety is not None else "",
                    ", ".join(e.tags)])
    return buf.getvalue()


def render_html(entries: list[CatalogEntry], *, generated_at: str) -> str:
    roles, levels, cells = _matrix(entries)
    data = {
        "generated_at": generated_at,
        "skills": [{"slug": e.slug, "title": e.title, "description": e.description,
                    "role": e.role, "level": e.level, "function": e.function,
                    "version": e.version, "owner": e.owner, "tags": e.tags,
                    "slots": e.slots, "verdict": e.verdict,
                    "safety": e.aggregate_safety, "stages": e.stages, "body": e.body,
                    "approval_id": e.approval_id, "payload_sha256": e.payload_sha256,
                    "automated_review_id": e.automated_review_id,
                    "content_review_id": e.content_review_id}
                   for e in entries],
        "roles": roles, "levels": levels, "cells": cells,
    }
    # A skill body is untrusted; </script> inside the JSON would close the block early.
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return _HTML.replace("__DATA__", payload).replace("__COUNT__", str(len(entries)))


def build_catalog(*, store: ArtifactStore, out_dir: str | Path,
                  generated_at: str = "unset") -> tuple[Path, list[CatalogEntry]]:
    entries = collect(store)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "catalog.md").write_text(render_markdown(entries, generated_at=generated_at),
                                    encoding="utf-8")
    (out / "catalog.csv").write_text(render_csv(entries), encoding="utf-8")
    (out / "catalog.html").write_text(render_html(entries, generated_at=generated_at),
                                      encoding="utf-8")
    return out, entries


_HTML = r"""<!doctype html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DV Agent Skills</title>
<style>
:root{
  --background:240 10% 3.9%; --foreground:0 0% 98%;
  --card:240 8% 5.5%; --muted:240 4% 11%; --muted-foreground:240 5% 62%;
  --primary:162 72% 46%; --primary-foreground:160 30% 6%;
  --accent:240 5% 15%; --border:240 5% 14%; --warning:38 92% 55%;
  --info:212 92% 62%; --radius:.65rem;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:hsl(var(--background));color:hsl(var(--foreground));
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:14px;line-height:1.55;-webkit-font-smoothing:antialiased}
code,pre,.mono{font-family:ui-monospace,SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace}
.wrap{max-width:1180px;margin:0 auto;padding:28px 22px 72px}
header h1{font-size:26px;font-weight:700;letter-spacing:-.02em}
header p{color:hsl(var(--muted-foreground));margin-top:6px;max-width:76ch}
.note{margin-top:14px;padding:12px 14px;border:1px solid hsl(var(--border));
  border-radius:var(--radius);background:hsl(var(--muted)/.5);font-size:12.5px;
  color:hsl(var(--muted-foreground));max-width:88ch}
.note b{color:hsl(var(--foreground))}
h2{font-size:16px;font-weight:600;margin:30px 0 12px;letter-spacing:-.01em}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:14px}
input,select{background:hsl(var(--muted));border:1px solid hsl(var(--border));
  color:hsl(var(--foreground));border-radius:calc(var(--radius) - 2px);padding:7px 11px;
  font-size:13px;font-family:inherit;outline:none}
input:focus,select:focus{border-color:hsl(var(--primary));box-shadow:0 0 0 3px hsl(var(--primary)/.16)}
input[type=search]{min-width:260px;flex:1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px}
.card{background:hsl(var(--card));border:1px solid hsl(var(--border));border-radius:var(--radius);
  padding:16px 18px;display:flex;flex-direction:column;gap:9px}
.card h3{font-size:14.5px;font-weight:600;letter-spacing:-.01em}
.card .slug{font-size:11.5px;color:hsl(var(--muted-foreground))}
.card .desc{font-size:12.5px;color:hsl(var(--muted-foreground));flex:1}
.badges{display:flex;gap:6px;flex-wrap:wrap}
.b{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 9px;
  font-size:11px;font-weight:600;border:1px solid hsl(var(--border));background:hsl(var(--muted));
  color:hsl(var(--muted-foreground))}
.b.ok{background:hsl(var(--primary)/.14);color:hsl(var(--primary));border-color:hsl(var(--primary)/.35)}
.b.slot{background:hsl(var(--warning)/.13);color:hsl(var(--warning));border-color:hsl(var(--warning)/.3)}
.b.role{background:hsl(var(--info)/.12);color:hsl(var(--info));border-color:hsl(var(--info)/.3)}
.row{display:flex;gap:8px;margin-top:2px}
.btn{flex:1;display:inline-flex;align-items:center;justify-content:center;gap:6px;cursor:pointer;
  border-radius:calc(var(--radius) - 2px);font-size:12.5px;font-weight:500;padding:7px 11px;
  border:1px solid hsl(var(--border));background:hsl(var(--muted));color:hsl(var(--foreground));
  font-family:inherit}
.btn:hover{background:hsl(var(--accent))}
.btn.primary{background:hsl(var(--primary));color:hsl(var(--primary-foreground));
  border-color:hsl(var(--primary));font-weight:600}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:600;
  color:hsl(var(--muted-foreground));padding:8px 10px;border-bottom:1px solid hsl(var(--border))}
td{padding:7px 10px;border-bottom:1px solid hsl(var(--border)/.7);vertical-align:top}
.matrix{display:grid;gap:4px;font-size:11px;overflow-x:auto}
.cell{border:1px solid hsl(var(--border));border-radius:6px;padding:8px 4px;text-align:center;
  background:hsl(var(--muted));color:hsl(var(--muted-foreground))}
.cell.on{background:hsl(var(--primary)/.2);border-color:hsl(var(--primary)/.5);
  color:hsl(var(--foreground));font-weight:600;cursor:pointer}
.cell.on:hover{background:hsl(var(--primary)/.32)}
.hdr{color:hsl(var(--muted-foreground));font-weight:600;text-align:center;padding:4px 2px}
.hdr.l{text-align:left}
dialog{background:hsl(var(--card));color:hsl(var(--foreground));border:1px solid hsl(var(--border));
  border-radius:var(--radius);padding:0;width:min(920px,94vw);max-height:88vh}
dialog::backdrop{background:rgba(0,0,0,.7)}
.dh{padding:18px 22px 0;display:flex;gap:12px;align-items:flex-start}
.dh h3{font-size:17px;font-weight:600}
.db{padding:14px 22px 22px;overflow:auto;max-height:70vh}
pre.body{background:hsl(var(--muted));border:1px solid hsl(var(--border));border-radius:8px;
  padding:14px;font-size:11.5px;white-space:pre-wrap;word-break:break-word;line-height:1.5}
.x{margin-left:auto;cursor:pointer;background:none;border:none;color:hsl(var(--muted-foreground));
  font-size:20px;font-family:inherit}
.toast{position:fixed;right:18px;bottom:18px;background:hsl(var(--card));
  border:1px solid hsl(var(--primary)/.4);border-radius:var(--radius);padding:11px 15px;
  font-size:12.5px;box-shadow:0 12px 32px rgba(0,0,0,.55)}
.empty{padding:30px;text-align:center;color:hsl(var(--muted-foreground));font-size:13px}
footer{margin-top:40px;padding-top:18px;border-top:1px solid hsl(var(--border));
  color:hsl(var(--muted-foreground));font-size:12px}
@media(max-width:640px){.grid{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="wrap">
<header>
  <h1>DV Agent Skills</h1>
  <p>__COUNT__ procedures your agent can use, each one a single Markdown file. Install takes about
     two minutes and needs no admin rights. Every one shipped generic on purpose — the blanks are
     where your team's specifics go.</p>
  <div class="note">
    <b>What "verified" means.</b> Each skill was scanned before publication: no shell or network
    tools, no credentials, and no text aimed at your agent as an instruction. That describes
    <b>this text on the day it published</b> — it is not a runtime guarantee (Cursor does not enforce
    the declared tool list), and it is not a promise the procedure is right for your team. Read
    anything before you rely on it.
  </div>
</header>

<h2>Browse</h2>
<div class="bar">
  <input type="search" id="q" placeholder="Search skills, tags, descriptions…">
  <select id="role"><option value="">All roles</option></select>
  <select id="level"><option value="">All levels</option></select>
</div>
<div class="grid" id="grid"></div>

<h2>Coverage — and what nobody has written down yet</h2>
<p style="color:hsl(var(--muted-foreground));font-size:12.5px;margin-bottom:12px;max-width:84ch">
  A filled cell means a published skill serves that role at that level. An empty cell is not a gap in
  the tool — it is something nobody has written down yet, and the person best placed to write it is
  whoever just worked it out for the third time.</p>
<div class="matrix" id="matrix"></div>

<h2>Add one</h2>
<div class="note" style="max-width:none">
  The best contributions are usually a single line in a <b>Gotchas</b> section — the thing you only
  learn by losing a day to it.
  <ol style="margin:10px 0 0 18px;line-height:1.9">
    <li>Copy the closest existing skill as a starting shape.</li>
    <li>Write the procedure the way you would explain it to someone joining next week.</li>
    <li>Run <code>python tools/lint_body.py &lt;your-skill&gt;/SKILL.md</code> — it catches what would
        stop it publishing.</li>
    <li>Send it back. It goes through the same scan and human approval as everything here.</li>
  </ol>
</div>

<footer>Generated from the verified catalog · <span id="gen"></span> ·
  Nothing on this page is estimated or illustrative — every field comes from a published skill and
  its real scan report.</footer>
</div>

<dialog id="dlg">
  <div class="dh">
    <div><h3 id="d-title"></h3><div class="slug mono" id="d-slug"></div></div>
    <button class="x" onclick="document.getElementById('dlg').close()">&times;</button>
  </div>
  <div class="db">
    <div class="badges" id="d-badges" style="margin-bottom:12px"></div>
    <div class="row" style="margin-bottom:14px">
      <button class="btn primary" id="d-copy">Copy install prompt</button>
      <button class="btn" id="d-copybody">Copy the file</button>
    </div>
    <table id="d-scan" style="margin-bottom:16px"></table>
    <pre class="body" id="d-body"></pre>
  </div>
</dialog>

<script id="catalog-data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('catalog-data').textContent);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const $ = s => document.querySelector(s);

document.getElementById('gen').textContent = DATA.generated_at;
for (const r of DATA.roles) $('#role').insertAdjacentHTML('beforeend', `<option>${esc(r)}</option>`);
for (const l of DATA.levels) $('#level').insertAdjacentHTML('beforeend', `<option>${esc(l)}</option>`);

function visible() {
  const q = $('#q').value.trim().toLowerCase();
  const role = $('#role').value, level = $('#level').value;
  return DATA.skills.filter(s =>
    (!role || s.role === role) && (!level || s.level === level) &&
    (!q || (s.title + ' ' + s.slug + ' ' + s.description + ' ' + (s.tags || []).join(' '))
      .toLowerCase().includes(q)));
}

function renderGrid() {
  const list = visible();
  $('#grid').innerHTML = list.length ? list.map(s => `
    <div class="card">
      <div>
        <h3>${esc(s.title)}</h3>
        <div class="slug mono">/${esc(s.slug)}</div>
      </div>
      <div class="badges">
        <span class="b role">${esc(s.role || '—')}</span>
        <span class="b">${esc(s.level || '—')}</span>
        ${s.slots ? `<span class="b slot">${s.slots} to fill in</span>` : ''}
        <span class="b ok">scanned ${s.safety != null ? s.safety.toFixed(3) : '—'}</span>
      </div>
      <div class="desc">${esc(s.description)}</div>
      <div class="row">
        <button class="btn primary" data-install="${esc(s.slug)}">Copy install prompt</button>
        <button class="btn" data-open="${esc(s.slug)}">Read it</button>
      </div>
    </div>`).join('')
    : `<div class="empty">Nothing matches that filter.</div>`;
}

function installPrompt(s) {
  return `Create the file .cursor/skills/${s.slug}/SKILL.md in this workspace, creating directories `
    + `as needed. Write exactly the content between the markers - do not summarise, reformat or `
    + `"improve" it.\n----- BEGIN SKILL.md -----\n${s.body}\n----- END SKILL.md -----`;
}

function toast(msg) {
  const d = document.createElement('div');
  d.className = 'toast'; d.textContent = msg;
  document.body.appendChild(d);
  setTimeout(() => d.remove(), 2600);
}

function copy(text, msg) {
  navigator.clipboard.writeText(text).then(() => toast(msg),
    () => toast('Copy failed — select the text in "Read it" instead.'));
}

function open_(slug) {
  const s = DATA.skills.find(x => x.slug === slug);
  if (!s) return;
  $('#d-title').textContent = s.title;
  $('#d-slug').textContent = '/' + s.slug + '  ·  v' + s.version + '  ·  ' + s.owner;
  $('#d-badges').innerHTML =
    `<span class="b role">${esc(s.role)}</span><span class="b">${esc(s.level)}</span>` +
    `<span class="b">${esc(s.function)}</span>` +
    (s.slots ? `<span class="b slot">${s.slots} blanks to fill in</span>` : '') +
    (s.tags || []).map(t => `<span class="b">${esc(t)}</span>`).join('');
  $('#d-scan').innerHTML =
    `<tr><th>Scan stage</th><th>Result</th></tr>` +
    s.stages.map(st => `<tr><td>stage ${st.stage}</td>` +
      `<td>${st.hard_fail ? 'BLOCKED' : esc(st.status.replaceAll('_', ' '))}` +
      ` · ${st.safety.toFixed(3)}</td></tr>`).join('') +
    `<tr><td><b>aggregate</b></td><td><b>${esc(s.verdict)}` +
    `${s.safety != null ? ' · ' + s.safety.toFixed(3) : ''}</b></td></tr>`;
  $('#d-body').textContent = s.body;
  $('#d-copy').onclick = () => copy(installPrompt(s), 'Install prompt copied — paste it into Cursor Agent chat.');
  $('#d-copybody').onclick = () => copy(s.body, 'SKILL.md copied.');
  $('#dlg').showModal();
}

function renderMatrix() {
  const el = $('#matrix');
  el.style.gridTemplateColumns = `170px repeat(${DATA.levels.length}, minmax(78px, 1fr))`;
  let h = `<div class="hdr"></div>` + DATA.levels.map(l => `<div class="hdr">${esc(l)}</div>`).join('');
  for (const r of DATA.roles) {
    h += `<div class="hdr l">${esc(r)}</div>`;
    for (const l of DATA.levels) {
      const got = DATA.cells[r + '|' + l] || [];
      h += got.length
        ? `<div class="cell on" data-open="${esc(got[0])}" title="${esc(got.join(', '))}">${got.length}</div>`
        : `<div class="cell">·</div>`;
    }
  }
  el.innerHTML = h;
}

document.addEventListener('click', e => {
  const i = e.target.closest('[data-install]');
  if (i) {
    const s = DATA.skills.find(x => x.slug === i.dataset.install);
    if (s) copy(installPrompt(s), 'Install prompt copied — paste it into Cursor Agent chat.');
    return;
  }
  const o = e.target.closest('[data-open]');
  if (o) open_(o.dataset.open);
});
['input', 'change'].forEach(ev => {
  $('#q').addEventListener(ev, renderGrid);
  $('#role').addEventListener(ev, renderGrid);
  $('#level').addEventListener(ev, renderGrid);
});

renderGrid();
renderMatrix();
</script>
</body>
</html>
"""
