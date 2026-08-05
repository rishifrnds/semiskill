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


def cmd_lint(args, store, out) -> int:
    """Pre-flight lint. Deliberately needs no database: authoring feedback must be instant, and a
    wave must be provably clean before the first artifact is ever written."""
    from semiskill.authoring.lint import lint_wave_dir, render
    report = lint_wave_dir(args.path, probe_dsn=args.probe_dsn)
    print(render(report, style="json" if args.json else "text"), file=out)
    if not report.ok:
        return 1
    if args.strict and any(f.level != "error" for r in report.reports for f in r.findings):
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="semiskill", description="SemiSkill CLI (L1 capture)")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("submit", help="submit a skill directory (SKILL.md + files)")
    s.add_argument("path", help="path to a skill directory containing SKILL.md")
    s.add_argument("--actor", default="cli-user")
    s.add_argument("--label", default="team", choices=_LABELS, help="permissions label")
    s.set_defaults(func=cmd_submit, needs_store=True)

    ls = sub.add_parser("list", help="list submitted skills")
    ls.set_defaults(func=cmd_list, needs_store=True)

    lt = sub.add_parser("lint", help="pre-flight lint a skill or a wave directory (no database)")
    lt.add_argument("path", help="a SKILL.md, a skill directory, or a tree of them")
    lt.add_argument("--json", action="store_true", help="machine-readable output")
    lt.add_argument("--strict", action="store_true", help="also fail on warnings and advisories")
    lt.add_argument("--probe-dsn", default=None,
                    help="consult the real held-out injection corpus (returns class names only)")
    lt.set_defaults(func=cmd_lint, needs_store=False)
    return p


def main(argv=None, store=None, out=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out if out is not None else sys.stdout
    args = build_parser().parse_args(argv)
    if store is None and getattr(args, "needs_store", True):
        store = _default_store()
    return args.func(args, store, out)


if __name__ == "__main__":
    raise SystemExit(main())
