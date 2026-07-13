"""SemiSkill CLI (L1 capture entry point).

`semiskill submit <dir>` ingests a skill directory into a `skill_version` artifact (state: submitted).
`semiskill list` shows submitted skills. Submitting does NOT publish — nothing is discoverable until it
passes the Phase-C pipeline + human approval (ADR-002).
"""
from __future__ import annotations
import argparse
import sys
from semiskill.config import Config
from semiskill.artifacts.schema import ArtifactType, SourceSystem
from semiskill.capture.intake import load_skill_dir, build_skill_version

_LABELS = ["public", "team", "need-to-know", "regulated"]


def _default_store():
    from semiskill.artifacts.store import PostgresArtifactStore
    return PostgresArtifactStore(Config.from_env().database_url)


def cmd_submit(args, store, out) -> int:
    skill_md, files = load_skill_dir(args.path)
    art = build_skill_version(skill_md=skill_md, actor=args.actor,
                              source_system=SourceSystem.CLI,
                              permissions_label=args.label, files=files)
    store.append(art)
    p = art.payload
    print(f"submitted {p['slug']} ({p['version']}) -> {art.artifact_id} [state=submitted]", file=out)
    return 0


def cmd_list(args, store, out) -> int:
    rows = store.by_type(ArtifactType.SKILL_VERSION)
    if not rows:
        print("(no skills submitted yet)", file=out)
        return 0
    for a in rows:
        p = a.payload
        print(f"{p.get('slug', '?')}\t{p.get('version', '?')}\t{a.artifact_id}\t{a.actor}", file=out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="semiskill", description="SemiSkill CLI (L1 capture)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("submit", help="submit a skill directory (SKILL.md + files)")
    s.add_argument("path", help="path to a skill directory containing SKILL.md")
    s.add_argument("--actor", default="cli-user")
    s.add_argument("--label", default="team", choices=_LABELS, help="permissions label")
    s.set_defaults(func=cmd_submit)

    ls = sub.add_parser("list", help="list submitted skills")
    ls.set_defaults(func=cmd_list)
    return p


def main(argv=None, store=None, out=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    store = store if store is not None else _default_store()
    return args.func(args, store, out)


if __name__ == "__main__":
    raise SystemExit(main())
