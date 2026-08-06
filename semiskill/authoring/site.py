"""The browsable site — skills.sh shape, our data.

A static multi-page tree with a real page per skill, generated from the **published catalog**. It is
written to work from a plain folder: relative links throughout, one stylesheet, no CDN, no fetch, no
build step. Zip it, email it, drop it in a SharePoint document library and download it — every link
still resolves.

    dist/site/
      index.html            ranked table + search
      skills/<slug>.html    per skill: install block, rendered SKILL.md, metadata, related
      roles/<role>.html     browse one role
      matrix.html           the role x level grid
      install.html          the two-minute install guide
      assets/site.css

**Two deliberate departures from skills.sh.** It ranks by install count; we have no install telemetry
and will not invent any, so where skills.sh shows installs we show the scan verdict and the number of
blanks left to fill, and ordering is curated rather than popularity-derived. And it renders full
Markdown; ours is a restricted subset (`authoring.markdown`) because skill bodies are untrusted.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring import facets as facet_vocab
from semiskill.authoring.catalog_page import CatalogEntry, collect, render_csv, render_markdown as render_catalog_md
from semiskill.authoring.markdown import render_markdown, strip_markdown

E = html.escape
LEVEL_ORDER = list(facet_vocab.LEVELS)

# Curated first impression. Anything not listed keeps registry/alphabetical order after these.
START_HERE = ("dv-sim-log-first-error", "dv-regression-triage-routing", "dv-build-filelist-hygiene")


@dataclass(frozen=True)
class SiteResult:
    root: Path
    pages: tuple[str, ...]
    entries: tuple[CatalogEntry, ...]


def _rank_key(e: CatalogEntry):
    try:
        first = START_HERE.index(e.slug)
    except ValueError:
        first = len(START_HERE)
    return (first, e.role, LEVEL_ORDER.index(e.level) if e.level in LEVEL_ORDER else 99, e.slug)


def _install_prompt(e: CatalogEntry) -> str:
    return (f"Create the file .cursor/skills/{e.slug}/SKILL.md in this workspace, creating "
            f"directories as needed. Write exactly the content between the markers - do not "
            f"summarise, reformat or \"improve\" it.\n"
            f"----- BEGIN SKILL.md -----\n{e.body}\n----- END SKILL.md -----")


def _json_block(obj, element_id: str) -> str:
    # `</` is neutralised so an untrusted body cannot terminate its own data block.
    payload = json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")
    return f'<script id="{element_id}" type="application/json">{payload}</script>'


# A preview build renders skills that have NOT passed the gate, so it must not wear the published
# site's footer, which promises every field came from a published skill. `build_site(preview=...)`
# sets this for the duration of the build; the default is the honest published-catalog wording.
_PREVIEW: str = ""


def _shell(*, title: str, depth: int, body: str, generated_at: str, scripts: str = "") -> str:
    up = "../" * depth
    banner = (f'<div class="preview-banner"><b>PREVIEW — not the published catalog.</b> '
              f'{E(_PREVIEW)}</div>' if _PREVIEW else "")
    footer = (f'PREVIEW build · {E(generated_at)} · These skills have NOT all passed the '
              f'verification gate. Each card shows its real gate status; scan scores are real, '
              f'the content review is not complete.'
              if _PREVIEW else
              f'Generated from the verified catalog · {E(generated_at)} · Nothing here is estimated '
              f'or illustrative — every field comes from a published skill and its real scan report.')
    return f"""<!doctype html>
<html lang="en" class="dark">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)}</title>
<link rel="stylesheet" href="{up}assets/site.css">
</head>
<body>
<header class="top">
  <a class="brand" href="{up}index.html"><span class="logo">DV</span> Agent Skills</a>
  <nav>
    <a href="{up}index.html">Catalog</a>
    <a href="{up}matrix.html">Coverage</a>
    <a href="{up}install.html">Install</a>
  </nav>
</header>
{banner}
<main>
{body}
</main>
<footer>
  {footer}
</footer>
{scripts}
</body>
</html>
"""


def _badges(e: CatalogEntry, *, depth: int) -> str:
    up = "../" * depth
    return (f'<a class="b role" href="{up}roles/{E(e.role)}.html">{E(e.role)}</a>'
            f'<span class="b">{E(e.level)}</span>'
            + (f'<span class="b slot">{e.slots} to fill in</span>' if e.slots else "")
            + f'<span class="b ok">scanned {e.aggregate_safety:.3f}</span>'
            if e.aggregate_safety is not None else "")


def render_index(entries: list[CatalogEntry], *, generated_at: str) -> str:
    rows = []
    for i, e in enumerate(entries, 1):
        rows.append(
            f'<tr data-hay="{E((e.title + " " + e.slug + " " + e.description + " " + " ".join(e.tags)).lower())}">'
            f'<td class="num">{i}</td>'
            f'<td><a class="name" href="skills/{E(e.slug)}.html">{E(e.title)}</a>'
            f'<div class="sub mono">/{E(e.slug)}</div></td>'
            f'<td><a class="b role" href="roles/{E(e.role)}.html">{E(e.role)}</a>'
            f'<span class="b">{E(e.level)}</span></td>'
            f'<td class="num">{e.slots}</td>'
            f'<td class="num">{"" if e.aggregate_safety is None else f"{e.aggregate_safety:.3f}"}</td>'
            f'</tr>')

    body = f"""
<section class="hero">
  <h1>DV Agent Skills</h1>
  <p>{len(entries)} procedures your agent can use, each one a single Markdown file. Install takes
     about two minutes and needs no admin rights. Every skill ships generic on purpose — the blanks
     are where your team's specifics go.</p>
  <div class="cmd"><code>~/.cursor/skills/</code><span>drop the pack folder here, reload Cursor, done</span></div>
  <p class="note"><b>What “verified” means.</b> Each skill was scanned before publication: no shell or
     network tools, no credentials, and no text aimed at your agent as an instruction. That describes
     <b>this text on the day it published</b> — it is not a runtime guarantee (Cursor does not enforce
     the declared tool list), and it is not a promise the procedure is right for your team.</p>
</section>

<section>
  <div class="bar">
    <input type="search" id="q" placeholder="Search skills, tags, descriptions…" autocomplete="off">
    <span class="count" id="count">{len(entries)} skills</span>
  </div>
  <table class="rank">
    <thead><tr><th class="num">#</th><th>Skill</th><th>Role · level</th>
      <th class="num">Blanks</th><th class="num">Scan</th></tr></thead>
    <tbody id="rows">
{chr(10).join(rows)}
    </tbody>
  </table>
  <p class="empty" id="empty" hidden>Nothing matches that search.</p>
</section>
"""
    script = """<script>
const q = document.getElementById('q'), rows = [...document.querySelectorAll('#rows tr')];
const count = document.getElementById('count'), empty = document.getElementById('empty');
q.addEventListener('input', () => {
  const t = q.value.trim().toLowerCase();
  let n = 0;
  for (const r of rows) {
    const hit = !t || r.dataset.hay.includes(t);
    r.hidden = !hit;
    if (hit) n++;
  }
  count.textContent = n + (n === 1 ? ' skill' : ' skills');
  empty.hidden = n > 0;
});
</script>"""
    return _shell(title="DV Agent Skills", depth=0, body=body,
                  generated_at=generated_at, scripts=script)


def render_skill(e: CatalogEntry, siblings: list[CatalogEntry], *, generated_at: str) -> str:
    stages = "".join(
        f'<tr><td>stage {s["stage"]}</td>'
        f'<td>{"BLOCKED" if s["hard_fail"] else "passed"} · {s["safety"]:.3f}</td></tr>'
        for s in e.stages)
    related = "".join(
        f'<li><a href="{E(s.slug)}.html">{E(s.title)}</a>'
        f'<span class="sub">{E(s.level)}</span></li>'
        for s in siblings[:5]) or '<li class="sub">Nothing else in this role yet.</li>'

    body = f"""
<nav class="crumbs"><a href="../index.html">Catalog</a> ›
  <a href="../roles/{E(e.role)}.html">{E(e.role)}</a> › <span>{E(e.title)}</span></nav>

<div class="cols">
  <article>
    <h1>{E(e.title)}</h1>
    <div class="sub mono">/{E(e.slug)}</div>
    <div class="badges">
      <a class="b role" href="../roles/{E(e.role)}.html">{E(e.role)}</a>
      <span class="b">{E(e.level)}</span>
      <span class="b">{E(e.function)}</span>
      {f'<span class="b slot">{e.slots} blanks to fill in</span>' if e.slots else ''}
    </div>
    <p class="lede">{E(e.description)}</p>

    <div class="install">
      <div class="install-head">Install — about a minute</div>
      <ol>
        <li>Click <b>Copy install prompt</b>.</li>
        <li>Paste it into Cursor Agent chat (<code>Ctrl+I</code>).</li>
        <li>The agent writes <code>.cursor/skills/{E(e.slug)}/SKILL.md</code>.</li>
        <li>Type <code>/{E(e.slug)}</code>, or just describe your task.</li>
      </ol>
      <div class="row">
        <button class="btn primary" id="copy-prompt">Copy install prompt</button>
        <button class="btn" id="copy-body">Copy the file</button>
      </div>
      <p class="sub">Working on a remote box over SSH? The prompt path needs no download at all.</p>
    </div>

    <section class="rendered">{render_markdown(e.body)}</section>
  </article>

  <aside>
    <div class="panel">
      <h3>This skill</h3>
      <dl>
        <dt>Version</dt><dd>{E(e.version)}</dd>
        <dt>Owner</dt><dd>{E(e.owner or '—')}</dd>
        <dt>Blanks to fill</dt><dd>{e.slots}</dd>
        <dt>Size</dt><dd>{len(e.body.encode('utf-8')):,} bytes</dd>
      </dl>
    </div>
    <div class="panel">
      <h3>Scan report</h3>
      <table class="scan"><tbody>{stages}
        <tr class="agg"><td><b>aggregate</b></td><td><b>{E(e.verdict)}
        {'' if e.aggregate_safety is None else f'· {e.aggregate_safety:.3f}'}</b></td></tr>
      </tbody></table>
      <p class="sub">Generated by our own pipeline on publication. Not a runtime guarantee.</p>
    </div>
    <div class="panel">
      <h3>More in {E(e.role)}</h3>
      <ul class="related">{related}</ul>
    </div>
    {f'<div class="panel"><h3>Tags</h3><div class="badges">{"".join(f"<span class=b>{E(t)}</span>" for t in e.tags)}</div></div>' if e.tags else ''}
  </aside>
</div>
"""
    script = _json_block({"prompt": _install_prompt(e), "body": e.body}, "skill-data") + """
<script>
const D = JSON.parse(document.getElementById('skill-data').textContent);
function toast(m){const d=document.createElement('div');d.className='toast';d.textContent=m;
  document.body.appendChild(d);setTimeout(()=>d.remove(),2600);}
function copy(t,m){navigator.clipboard.writeText(t).then(()=>toast(m),
  ()=>toast('Copy failed — select the text below instead.'));}
document.getElementById('copy-prompt').onclick=()=>copy(D.prompt,'Install prompt copied — paste it into Cursor Agent chat.');
document.getElementById('copy-body').onclick=()=>copy(D.body,'SKILL.md copied.');
</script>"""
    return _shell(title=f"{e.title} · DV Agent Skills", depth=1, body=body,
                  generated_at=generated_at, scripts=script)


def render_role(role: str, entries: list[CatalogEntry], *, generated_at: str) -> str:
    cards = "".join(
        f'<a class="card" href="../skills/{E(e.slug)}.html">'
        f'<h3>{E(e.title)}</h3><div class="sub mono">/{E(e.slug)}</div>'
        f'<div class="badges"><span class="b">{E(e.level)}</span>'
        + (f'<span class="b slot">{e.slots} to fill in</span>' if e.slots else "")
        + f'</div><p>{E(strip_markdown(e.description, limit=180))}</p></a>'
        for e in entries)
    body = f"""
<nav class="crumbs"><a href="../index.html">Catalog</a> › <span>{E(role)}</span></nav>
<h1>{E(role)}</h1>
<p class="lede">{len(entries)} published skill{'' if len(entries) == 1 else 's'} for this role.</p>
<div class="grid">{cards}</div>
"""
    return _shell(title=f"{role} · DV Agent Skills", depth=1, body=body, generated_at=generated_at)


def render_matrix(entries: list[CatalogEntry], *, generated_at: str) -> str:
    roles = sorted({e.role for e in entries if e.role})
    levels = [l for l in LEVEL_ORDER if any(e.level == l for e in entries)]
    by: dict[str, list[CatalogEntry]] = {}
    for e in entries:
        by.setdefault(f"{e.role}|{e.level}", []).append(e)

    head = "".join(f"<th>{E(l)}</th>" for l in levels)
    rows = []
    for r in roles:
        cells = []
        for l in levels:
            got = by.get(f"{r}|{l}", [])
            if got:
                links = " ".join(f'<a href="skills/{E(g.slug)}.html">{E(g.title)}</a>' for g in got)
                cells.append(f'<td class="on" title="{E(", ".join(g.title for g in got))}">'
                             f'<span class="n">{len(got)}</span><div class="pop">{links}</div></td>')
            else:
                cells.append('<td class="off">·</td>')
        rows.append(f'<tr><th class="rowh"><a href="roles/{E(r)}.html">{E(r)}</a></th>'
                    + "".join(cells) + "</tr>")

    body = f"""
<h1>Coverage</h1>
<p class="lede">A filled cell means a published skill serves that role at that level. An empty cell is
   not a gap in the tool — it is something nobody has written down yet, and the person best placed to
   write it is whoever just worked it out for the third time.</p>
<div class="matrix-wrap">
  <table class="matrix"><thead><tr><th></th>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>
</div>
<p class="sub">{len(entries)} skills · {len(roles)} roles · {len(levels)} levels in use.</p>
"""
    return _shell(title="Coverage · DV Agent Skills", depth=0, body=body, generated_at=generated_at)


def render_install(entries: list[CatalogEntry], *, generated_at: str) -> str:
    body = f"""
<h1>Install — about two minutes</h1>
<p class="lede">{len(entries)} skills, each a single Markdown file. Nothing to run, no admin rights.</p>

<h2>Cursor</h2>
<p>Put the whole <code>semiskill-dv</code> folder in <b>one</b> of these, then reload Cursor:</p>
<table class="plain">
  <tr><td><code>~/.cursor/skills/</code></td><td>available in every project
      (Windows: <code>%USERPROFILE%\\.cursor\\skills\\</code>)</td></tr>
  <tr><td><code>&lt;your repo&gt;/.cursor/skills/</code></td><td>available in that project, and
      shareable with your team through git</td></tr>
</table>
<p>Then type <code>/</code> in Agent chat and pick one, or just describe your problem — the agent
   reads each skill's description and reaches for the right one itself.</p>
<p class="note">Needs <b>Cursor 2.4 or newer</b> (Help → About). On an older build, save the same file
   as <code>.cursor/rules/&lt;name&gt;.mdc</code> and add <code>alwaysApply: false</code>. The same
   files work in Claude Code, Codex, Copilot and VS Code — only the folder name changes.</p>

<h2>No download? Use the install prompt</h2>
<p>Every skill page has a <b>Copy install prompt</b> button. It copies a prompt that has your own
   agent write the file for you — which works even when your workspace is a remote Linux box over SSH
   and your Downloads folder is unreachable from it.</p>

<h2>Before they are useful</h2>
<p>Every skill ships generic on purpose, with <code>[[FILL: …]]</code> blanks where your team's
   specifics belong. Fill <code>_shared/team-profile.md</code> in once — it holds the facts the whole
   pack shares — then open any skill and ask the agent to fill the rest from your repo.</p>
<p class="note">A skill with unfilled blanks will stop and ask rather than invent an answer. That is
   deliberate: a confidently invented rerun command costs more than no answer at all.</p>

<h2>Adding one</h2>
<p>The best contributions are usually a single line in a <b>Gotchas</b> section — the thing you only
   learn by losing a day to it. Copy the closest existing skill, write the procedure the way you would
   explain it to someone joining next week, run
   <code>python tools/lint_body.py &lt;your-skill&gt;/SKILL.md</code>, and send it back. It goes
   through the same scan and human approval as everything here.</p>
"""
    return _shell(title="Install · DV Agent Skills", depth=0, body=body, generated_at=generated_at)


def build_site(*, store: ArtifactStore | None = None, out_dir: str | Path,
               generated_at: str = "unset",
               entries: list[CatalogEntry] | None = None,
               preview: str = "") -> SiteResult:
    """Render the catalog site.

    By default the source is the PUBLISHED catalog, and that invariant is load-bearing — an
    unpublished skill must never reach the site. `entries` exists for one purpose: a clearly-marked
    PREVIEW build of authored-but-not-yet-verified skills, which every page then declares in a
    banner and its footer. Passing `entries` without `preview` is refused, so a preview can never be
    mistaken for the real catalog by omission.
    """
    if entries is not None and not preview:
        raise ValueError("entries= builds a preview and requires preview=<what it is>; refusing to "
                         "render unpublished skills in the published site's clothing")
    global _PREVIEW
    _PREVIEW = preview
    try:
        return _build(store=store, out_dir=out_dir, generated_at=generated_at, entries=entries)
    finally:
        _PREVIEW = ""


def _build(*, store: ArtifactStore | None, out_dir: str | Path,
           generated_at: str, entries: list[CatalogEntry] | None) -> SiteResult:
    if entries is None:
        if store is None:
            raise ValueError("build_site needs either a store or an explicit entries list")
        entries = collect(store)
    entries = sorted(entries, key=_rank_key)
    out = Path(out_dir)
    (out / "skills").mkdir(parents=True, exist_ok=True)
    (out / "roles").mkdir(parents=True, exist_ok=True)
    (out / "assets").mkdir(parents=True, exist_ok=True)

    pages: list[str] = []

    def write(rel: str, text: str) -> None:
        (out / rel).write_text(text, encoding="utf-8")
        pages.append(rel)

    write("assets/site.css", _CSS)
    write("index.html", render_index(entries, generated_at=generated_at))
    write("matrix.html", render_matrix(entries, generated_at=generated_at))
    write("install.html", render_install(entries, generated_at=generated_at))

    by_role: dict[str, list[CatalogEntry]] = {}
    for e in entries:
        by_role.setdefault(e.role, []).append(e)
    for role, items in by_role.items():
        write(f"roles/{role}.html", render_role(role, items, generated_at=generated_at))
    for e in entries:
        siblings = [s for s in by_role.get(e.role, []) if s.slug != e.slug]
        write(f"skills/{e.slug}.html", render_skill(e, siblings, generated_at=generated_at))

    # The SharePoint entry point and the list import travel with the site.
    write("catalog.md", render_catalog_md(entries, generated_at=generated_at))
    write("catalog.csv", render_csv(entries))

    return SiteResult(root=out, pages=tuple(pages), entries=tuple(entries))


_CSS = """/* shadcn/tweakcn dark tokens — one stylesheet, no build step, no CDN */
:root{
  --background:240 10% 3.9%; --foreground:0 0% 98%;
  --card:240 8% 5.5%; --muted:240 4% 11%; --muted-foreground:240 5% 62%;
  --primary:162 72% 46%; --primary-foreground:160 30% 6%;
  --accent:240 5% 15%; --border:240 5% 14%; --warning:38 92% 55%; --info:212 92% 62%;
  --radius:.65rem;
}
*{box-sizing:border-box;margin:0;padding:0}
body{background:hsl(var(--background));color:hsl(var(--foreground));
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  font-size:14px;line-height:1.6;-webkit-font-smoothing:antialiased}
code,pre,.mono{font-family:ui-monospace,SFMono-Regular,"JetBrains Mono",Menlo,Consolas,monospace}
a{color:inherit;text-decoration:none}
a:hover{text-decoration:underline}
main{max-width:1180px;margin:0 auto;padding:26px 22px 70px}

.top{position:sticky;top:0;z-index:10;display:flex;align-items:center;gap:22px;
  padding:12px 22px;border-bottom:1px solid hsl(var(--border));
  background:hsl(var(--background)/.9);backdrop-filter:blur(10px)}
.brand{display:flex;align-items:center;gap:9px;font-weight:600;letter-spacing:-.01em}
.brand:hover{text-decoration:none}
.logo{display:grid;place-items:center;width:26px;height:26px;border-radius:7px;font-size:11px;
  font-weight:800;background:linear-gradient(145deg,hsl(var(--primary)),hsl(var(--info)));
  color:hsl(var(--primary-foreground))}
.top nav{display:flex;gap:16px;font-size:13px;color:hsl(var(--muted-foreground))}
.top nav a:hover{color:hsl(var(--foreground))}

h1{font-size:26px;font-weight:700;letter-spacing:-.02em;margin-bottom:6px}
h2{font-size:17px;font-weight:600;margin:28px 0 10px}
.lede{color:hsl(var(--muted-foreground));max-width:78ch;margin-bottom:14px}
.sub{font-size:12px;color:hsl(var(--muted-foreground))}
.note{margin-top:14px;padding:12px 14px;border:1px solid hsl(var(--border));border-radius:var(--radius);
  background:hsl(var(--muted)/.5);font-size:12.5px;color:hsl(var(--muted-foreground));max-width:88ch}
.note b{color:hsl(var(--foreground))}
.hero{margin-bottom:26px}
.cmd{display:flex;align-items:center;gap:12px;margin:14px 0;padding:11px 14px;
  border:1px solid hsl(var(--border));border-radius:var(--radius);background:hsl(var(--muted)/.5)}
.cmd code{color:hsl(var(--primary));font-size:13px}
.cmd span{font-size:12.5px;color:hsl(var(--muted-foreground))}
.crumbs{font-size:12.5px;color:hsl(var(--muted-foreground));margin-bottom:14px}

.bar{display:flex;gap:10px;align-items:center;margin-bottom:12px}
input[type=search]{flex:1;background:hsl(var(--muted));border:1px solid hsl(var(--border));
  color:hsl(var(--foreground));border-radius:calc(var(--radius) - 2px);padding:8px 12px;
  font-size:13px;font-family:inherit;outline:none}
input[type=search]:focus{border-color:hsl(var(--primary));box-shadow:0 0 0 3px hsl(var(--primary)/.16)}
.count{font-size:12px;color:hsl(var(--muted-foreground));white-space:nowrap}

table.rank{width:100%;border-collapse:collapse;font-size:13px}
table.rank th{text-align:left;font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;
  font-weight:600;color:hsl(var(--muted-foreground));padding:8px 10px;
  border-bottom:1px solid hsl(var(--border))}
table.rank td{padding:10px;border-bottom:1px solid hsl(var(--border)/.7);vertical-align:top}
table.rank tr:hover td{background:hsl(var(--accent)/.45)}
.num{text-align:right;font-variant-numeric:tabular-nums;color:hsl(var(--muted-foreground))}
a.name{font-weight:600}
.empty{padding:26px;text-align:center;color:hsl(var(--muted-foreground))}

.b{display:inline-flex;align-items:center;border-radius:999px;padding:2px 9px;font-size:11px;
  font-weight:600;border:1px solid hsl(var(--border));background:hsl(var(--muted));
  color:hsl(var(--muted-foreground));margin-right:5px;white-space:nowrap}
a.b:hover{text-decoration:none;background:hsl(var(--accent))}
.b.role{background:hsl(var(--info)/.12);color:hsl(var(--info));border-color:hsl(var(--info)/.3)}
.b.slot{background:hsl(var(--warning)/.13);color:hsl(var(--warning));border-color:hsl(var(--warning)/.3)}
.b.ok{background:hsl(var(--primary)/.14);color:hsl(var(--primary));border-color:hsl(var(--primary)/.35)}
.badges{display:flex;flex-wrap:wrap;gap:4px;margin:10px 0}

.cols{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:26px;align-items:start}
@media(max-width:900px){.cols{grid-template-columns:1fr}}
aside{display:flex;flex-direction:column;gap:14px;position:sticky;top:70px}
.panel{border:1px solid hsl(var(--border));border-radius:var(--radius);background:hsl(var(--card));
  padding:14px 16px}
.panel h3{font-size:12px;text-transform:uppercase;letter-spacing:.06em;
  color:hsl(var(--muted-foreground));margin-bottom:9px}
.panel dl{display:grid;grid-template-columns:auto 1fr;gap:5px 12px;font-size:12.5px}
.panel dt{color:hsl(var(--muted-foreground))}
.panel dd{text-align:right}
table.scan{width:100%;font-size:12.5px;border-collapse:collapse}
table.scan td{padding:3px 0}
table.scan td:last-child{text-align:right;color:hsl(var(--primary))}
table.scan tr.agg td{border-top:1px solid hsl(var(--border));padding-top:6px}
ul.related{list-style:none;display:flex;flex-direction:column;gap:7px;font-size:12.5px}
ul.related li{display:flex;justify-content:space-between;gap:8px}

.install{border:1px solid hsl(var(--primary)/.3);border-radius:var(--radius);
  background:hsl(var(--primary)/.06);padding:14px 16px;margin:18px 0}
.install-head{font-weight:600;margin-bottom:8px}
.install ol{margin:0 0 12px 18px;font-size:13px;color:hsl(var(--muted-foreground))}
.install code{color:hsl(var(--primary))}
.row{display:flex;gap:8px}
.btn{cursor:pointer;border-radius:calc(var(--radius) - 2px);font-size:12.5px;font-weight:500;
  padding:8px 13px;border:1px solid hsl(var(--border));background:hsl(var(--muted));
  color:hsl(var(--foreground));font-family:inherit}
.btn:hover{background:hsl(var(--accent))}
.btn.primary{background:hsl(var(--primary));color:hsl(var(--primary-foreground));
  border-color:hsl(var(--primary));font-weight:600}

.rendered{margin-top:22px;border-top:1px solid hsl(var(--border));padding-top:20px}
.rendered h2{font-size:19px;margin:26px 0 10px}
.rendered h3{font-size:15px;margin:20px 0 8px}
.rendered h4{font-size:13.5px;margin:16px 0 6px;color:hsl(var(--muted-foreground))}
.rendered p{margin:9px 0}
.rendered ul,.rendered ol{margin:9px 0 9px 22px}
.rendered li{margin:4px 0}
.rendered code{background:hsl(var(--muted));padding:1px 5px;border-radius:4px;font-size:12.5px}
.rendered pre{background:hsl(var(--muted));border:1px solid hsl(var(--border));border-radius:8px;
  padding:13px;overflow-x:auto;margin:12px 0}
.rendered pre code{background:none;padding:0;font-size:12px;line-height:1.5}
.rendered table{width:100%;border-collapse:collapse;font-size:12.5px;margin:12px 0}
.rendered th{text-align:left;padding:7px 9px;border-bottom:1px solid hsl(var(--border));
  font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:hsl(var(--muted-foreground))}
.rendered td{padding:7px 9px;border-bottom:1px solid hsl(var(--border)/.6);vertical-align:top}
.rendered blockquote{border-left:3px solid hsl(var(--primary)/.5);padding:2px 0 2px 13px;
  margin:12px 0;color:hsl(var(--muted-foreground))}
.rendered hr{border:none;border-top:1px solid hsl(var(--border));margin:20px 0}
.fill{background:hsl(var(--warning)/.13);color:hsl(var(--warning));border-radius:4px;padding:1px 5px}

.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:13px}
a.card{border:1px solid hsl(var(--border));border-radius:var(--radius);background:hsl(var(--card));
  padding:15px 17px;display:block}
a.card:hover{text-decoration:none;border-color:hsl(var(--primary)/.4)}
a.card h3{font-size:14px;font-weight:600}
a.card p{font-size:12.5px;color:hsl(var(--muted-foreground));margin-top:7px}

.matrix-wrap{overflow-x:auto;border:1px solid hsl(var(--border));border-radius:var(--radius)}
table.matrix{border-collapse:collapse;width:100%;font-size:12px}
table.matrix th{padding:9px 8px;font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;
  color:hsl(var(--muted-foreground));font-weight:600;white-space:nowrap}
table.matrix th.rowh{text-align:left;position:sticky;left:0;background:hsl(var(--background))}
table.matrix td{text-align:center;padding:9px 8px;border:1px solid hsl(var(--border)/.6);
  position:relative}
table.matrix td.off{color:hsl(var(--muted-foreground)/.5)}
table.matrix td.on{background:hsl(var(--primary)/.16);font-weight:700;cursor:default}
table.matrix td.on .pop{display:none;position:absolute;z-index:5;left:50%;transform:translateX(-50%);
  top:100%;background:hsl(var(--card));border:1px solid hsl(var(--border));border-radius:8px;
  padding:8px 10px;white-space:nowrap;font-weight:400;text-align:left;
  box-shadow:0 10px 26px rgba(0,0,0,.5)}
table.matrix td.on .pop a{display:block;padding:2px 0;font-size:12px}
table.matrix td.on:hover .pop{display:block}

table.plain{border-collapse:collapse;font-size:13px;margin:10px 0}
table.plain td{padding:6px 14px 6px 0;vertical-align:top}

footer{max-width:1180px;margin:0 auto;padding:18px 22px 40px;font-size:12px;
  color:hsl(var(--muted-foreground));border-top:1px solid hsl(var(--border))}
.preview-banner{max-width:1180px;margin:14px auto 0;padding:11px 15px;font-size:13px;
  border-radius:var(--radius);background:hsl(38 92% 50% / .11);
  border:1px solid hsl(38 92% 50% / .45);color:hsl(38 92% 72%)}
.preview-banner b{color:hsl(38 96% 80%)}
.b.gate-ready{background:hsl(142 70% 45% / .16);border-color:hsl(142 70% 45% / .5);
  color:hsl(142 70% 72%)}
.b.gate-open{background:hsl(38 92% 50% / .14);border-color:hsl(38 92% 50% / .45);
  color:hsl(38 92% 74%)}
.b.gate-none{background:hsl(0 0% 50% / .12);border-color:hsl(0 0% 50% / .38);
  color:hsl(0 0% 72%)}
.toast{position:fixed;right:18px;bottom:18px;background:hsl(var(--card));
  border:1px solid hsl(var(--primary)/.4);border-radius:var(--radius);padding:11px 15px;
  font-size:12.5px;box-shadow:0 12px 32px rgba(0,0,0,.55)}
"""
