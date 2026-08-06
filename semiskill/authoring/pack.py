"""Build the deliverable pack — the last mile from "row in Postgres" to "working in Cursor".

The integrity claim of this whole project is one identity:

    sha256(pack/<name>/SKILL.md) == sha256(source) == the payload that passed the gate

so packaging **places bytes, it never rewrites them** (ADR-008). If the source file has changed since
it published, packing refuses rather than shipping content that carries a verification badge it did
not earn.

What goes in the pack is decided by the CATALOG, not by the filesystem: only skills whose active
approval says published. A blocked or superseded skill structurally cannot appear (ADR-002/003).

Installation is file placement — Cursor 2.4+ discovers skills by walking `.cursor/skills/`,
`.agents/skills/` and their `~` equivalents for any SKILL.md. There is no install command to
implement, and none to invent.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from semiskill.artifacts.store import ArtifactStore
from semiskill.governance.publish import (
    ApprovalChainInvalid,
    resolve_frozen_approval_evidence,
)
from semiskill.wave import _published_index, payload_hash

PACK_NAME = "semiskill-dv"


class PackRefused(Exception):
    """A precondition failed. Nothing was written."""


@dataclass(frozen=True)
class PackedSkill:
    name: str
    title: str
    description: str
    role: str | None
    level: str | None
    function: str | None
    version: str
    sha256: str
    bytes_len: int
    slots: int
    verdict: str
    aggregate_safety: float | None
    approval_artifact_id: str
    payload_sha256: str
    automated_review_artifact_id: str
    content_review_artifact_id: str
    scan_artifact_ids: tuple[str, ...]


@dataclass(frozen=True)
class PackManifest:
    pack: str
    generated_at: str
    skill_count: int
    skills: tuple[PackedSkill, ...]

    def to_json(self) -> str:
        return json.dumps({"pack": self.pack, "generated_at": self.generated_at,
                           "skill_count": self.skill_count,
                           "skills": [asdict(s) for s in self.skills]},
                          indent=2, sort_keys=True)


def build_pack(*, store: ArtifactStore, source_root: str | Path, out_dir: str | Path,
               pack_name: str = PACK_NAME, generated_at: str = "unset",
               include_tools: bool = True, make_zip: bool = True) -> tuple[Path, PackManifest]:
    """Assemble the pack from what the catalog says is published."""
    src = Path(source_root)
    out = Path(out_dir)
    pack_root = out / pack_name

    try:
        published = _published_index(store)
    except ApprovalChainInvalid as exc:
        raise PackRefused(f"malformed active approval chain: {exc}") from exc
    if not published:
        raise PackRefused("nothing is published — run `semiskill wave` first")

    preflight = []
    for slug, (sv, approval) in sorted(published.items()):
        try:
            frozen = resolve_frozen_approval_evidence(
                store, skill_version=sv, approval=approval,
            )
        except ApprovalChainInvalid as exc:
            raise PackRefused(f"{slug}: malformed active approval chain: {exc}") from exc
        skill_md = src / slug / "SKILL.md"
        if not skill_md.exists():
            raise PackRefused(f"{slug} is published but its source is missing at {skill_md}")
        raw = skill_md.read_bytes()
        text = raw.decode("utf-8")
        from semiskill.capture.intake import build_skill_version, load_skill_dir
        _, sibling_files = load_skill_dir(skill_md.parent)
        fresh = build_skill_version(skill_md=text, actor="pack", files=sibling_files).payload
        if payload_hash(fresh) != payload_hash(sv.payload):
            raise PackRefused(
                f"{slug}: the source file has changed since it published. Packing it would ship "
                f"bytes carrying a verification badge they did not earn. Re-run `semiskill wave`.")
        preflight.append((slug, sv, approval, frozen, skill_md, raw, text, fresh))

    if pack_root.exists():
        shutil.rmtree(pack_root)
    pack_root.mkdir(parents=True)

    packed: list[PackedSkill] = []
    for slug, sv, approval, frozen, skill_md, raw, text, fresh in preflight:
        dest = pack_root / slug
        dest.mkdir()
        # copy2, not a re-serialisation: the delivered bytes are the verified bytes
        shutil.copy2(skill_md, dest / "SKILL.md")

        review = frozen.automated_review
        packed.append(PackedSkill(
            name=slug, title=fresh.get("name") or slug, description=fresh.get("description", ""),
            role=fresh.get("role"), level=fresh.get("level"), function=fresh.get("function"),
            version=fresh.get("version", "0.1.0"),
            # checksum of the DELIVERED bytes, so a recipient can actually verify the file they hold
            sha256=hashlib.sha256(raw).hexdigest(), bytes_len=len(raw),
            slots=text.count("[[FILL:"),
            verdict=review.payload["verdict"],
            aggregate_safety=float(review.payload["aggregate_safety"]),
            approval_artifact_id=str(approval.artifact_id),
            payload_sha256=approval.payload["skill"]["payload_sha256"],
            automated_review_artifact_id=str(frozen.automated_review.artifact_id),
            content_review_artifact_id=str(frozen.content_review.artifact_id),
            scan_artifact_ids=tuple(str(scan.artifact_id) for scan in frozen.scans)))

    shared_src = src / "_shared"
    if shared_src.is_dir():
        shutil.copytree(shared_src, pack_root / "_shared")

    if include_tools:
        (pack_root / "tools").mkdir()
        from semiskill.authoring import lint_body
        shutil.copy2(Path(lint_body.__file__), pack_root / "tools" / "lint_body.py")

    manifest = PackManifest(pack=pack_name, generated_at=generated_at,
                            skill_count=len(packed), skills=tuple(packed))
    (pack_root / "MANIFEST.json").write_text(manifest.to_json(), encoding="utf-8")
    (pack_root / "README-INSTALL.md").write_text(_install_doc(pack_name, manifest), encoding="utf-8")
    (pack_root / "PERSONALIZING.md").write_text(_personalizing_doc(pack_name), encoding="utf-8")

    if make_zip:
        zip_path = out / f"{pack_name}.zip"
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(pack_root.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(out).as_posix())

    return pack_root, manifest


def _install_doc(pack_name: str, manifest: PackManifest) -> str:
    rows = "\n".join(
        f"| `/{s.name}` | {s.title} | {s.role or '—'} | {s.level or '—'} | {s.slots} |"
        for s in manifest.skills)
    return f"""# DV skills — install (about two minutes)

{manifest.skill_count} skills, each one a single Markdown file. Nothing to run, nothing to install,
no admin rights.

## Cursor

Put the whole `{pack_name}` folder in **one** of these, then reload Cursor:

| Where | Effect |
|---|---|
| `~/.cursor/skills/` | available in every project (Windows: `%USERPROFILE%\\.cursor\\skills\\`) |
| `<your repo>/.cursor/skills/` | available in that project, and shareable via git |

Then either type `/` in Agent chat and pick one, or just describe your problem — the agent reads each
skill's description and reaches for the right one on its own.

**Working over SSH on a remote box?** You do not need the zip at all. Open the skill in the browser,
copy it, and ask the agent: *"create `.cursor/skills/<name>/SKILL.md` in this workspace with exactly
this content"*.

Skills need **Cursor 2.4 or newer** (Help → About). On an older build, save the same file as
`.cursor/rules/<name>.mdc` and add `alwaysApply: false` to the top block.

Claude Code, Codex, Copilot and VS Code read the same format — the folder is `~/.claude/skills/`,
`~/.codex/skills/` and so on.

## What is in here

| Invoke | Skill | Role | Level | Blanks to fill |
|---|---|---|---|---|
{rows}

## Before they are useful

Every skill ships **generic on purpose** and has `[[FILL: ...]]` blanks where your team's specifics
belong — log locations, build invocations, who signs off. A skill with unfilled blanks will tell you
so and ask, rather than inventing an answer. Filling them takes one message: see `PERSONALIZING.md`.

## What "verified" means here

Each skill was scanned before publication: it declares no shell or network tools, contains no
credentials, and its text carries no instructions aimed at your agent. `MANIFEST.json` records the
scan verdict and a checksum for each file.

That is a statement about **this text on the day it was published**. It is not a runtime guarantee —
Cursor does not enforce the tool list — and it is not a promise that the procedure is right for your
team. Read anything before you rely on it.
"""


def _personalizing_doc(pack_name: str) -> str:
    return f"""# Making these yours

The generic procedure is the cheap part. **The blanks are the product** — they are exactly the places
where advice written outside your team would otherwise be wrong.

## Fill the blanks (one message)

Open a skill in Cursor and ask:

> Fill the `[[FILL: ...]]` blanks in this file from this repository. Ask me for anything you cannot
> work out from the code.

The agent will find your filelists, build targets and log locations. Anything it cannot infer, it
asks. Roughly ten minutes per skill, once, forever.

**Never put a credential, a customer name, or anything export-controlled in a blank.** If a blank
seems to be asking for one, it is a bug in the skill — say so.

## Keep your version

Save your filled-in copy as `<name>-local` (folder and `name:` both), and add to its `metadata:`

```
  semiskill-derived-from: <name>
  semiskill-personalized: "true"
```

Yours and the shared one can then live side by side, and it stays obvious which is which.

## Check it still passes

The pack ships the same body linter that gates the shared skills:

```
python tools/lint_body.py <name>-local/SKILL.md
```

It catches the things that would stop your version being contributed back — pasted URLs, internal
host names, anything credential-shaped. It checks the body only, so a clean run means *probably*
fine, not certainly.

## Take an update without losing your work

When a newer pack arrives, ask:

> Here is v1.1 of the skill I have at `.cursor/skills/{pack_name}/<name>/SKILL.md`. Merge it: take
> the new procedure text, keep everything I filled into the blanks and anything under my own notes
> heading. Show me the diff before writing.

## Send an improvement back

If something you filled in is true for the **whole team** rather than just you, it belongs in the
shared skill. Send the file back and it goes through the same scan and approval as everything else,
so the shared copy keeps its provenance. Anything specific to you or one project stays in your copy.

The best contributions are usually a line in **Gotchas** — the thing you only learn by losing a day
to it.
"""
