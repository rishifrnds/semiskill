"""SemiSkill CLI (L1 capture entry point).

`semiskill submit <dir>` ingests a skill directory into a `skill_version` artifact (state: submitted).
`semiskill list` shows submitted skills. Submitting does NOT publish — nothing is discoverable until it
passes the Phase-C pipeline + human approval (ADR-002).
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
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


def cmd_approve(args, store, out) -> int:
    """Record one explicit decision bound to the logged-in OS identity and exact evidence IDs."""
    from semiskill.governance.identity import IdentityRefused, local_os_identity
    from semiskill.governance.publish import PublishRefused, decide_publication

    if args.environment == "production":
        print("approval refused: production requires the configured Entra/OIDC adapter", file=out)
        return 2
    try:
        identity = local_os_identity()
        approval = decide_publication(
            store=store,
            skill_version_id=args.skill_version_id,
            automated_review_id=args.automated_review,
            content_review_id=args.content_review,
            expected_payload_sha256=args.expected_sha256,
            decision=args.decision,
            reason=args.reason,
            identity=identity,
            environment=args.environment,
        )
    except (IdentityRefused, PublishRefused) as exc:
        print(f"approval refused: {exc}", file=out)
        return 2
    print(
        f"decision={approval.payload['decision']} published={approval.payload['published']} "
        f"approval_id={approval.artifact_id} actor={approval.actor}",
        file=out,
    )
    return 0


def cmd_unpublish(args, store, out) -> int:
    """Append an authenticated correction to an exact active approval/v1."""
    from semiskill.governance.identity import IdentityRefused, local_os_identity
    from semiskill.governance.rollback import RollbackRefused, decide_unpublication

    if args.environment == "production":
        print("unpublish refused: production requires the configured Entra/OIDC adapter", file=out)
        return 2
    try:
        identity = local_os_identity()
        correction = decide_unpublication(
            store=store,
            published_approval_id=args.approval_id,
            reason=args.reason,
            identity=identity,
            environment=args.environment,
            quarantine=not args.no_quarantine,
        )
    except (IdentityRefused, RollbackRefused) as exc:
        print(f"unpublish refused: {exc}", file=out)
        return 2
    print(f"unpublished approval={args.approval_id} correction={correction.artifact_id}", file=out)
    return 0


def cmd_lint(args, store, out) -> int:
    """Pre-flight lint. Deliberately needs no database: authoring feedback must be instant, and a
    wave must be provably clean before the first artifact is ever written."""
    from semiskill.authoring.consistency import check_pack, render as render_pack
    from semiskill.authoring.lint import lint_wave_dir, render
    report = lint_wave_dir(args.path, probe_dsn=args.probe_dsn)
    print(render(report, style="json" if args.json else "text"), file=out)

    # Per-skill lint asks "is this file publishable"; the pack check asks "does this pack agree with
    # itself". Four review rounds showed the second class is where the real defects hide.
    pack = [] if args.json else check_pack(args.path)
    if pack:
        print("\n" + render_pack(pack), file=out)
    if not report.ok or any(f.level == "error" for f in pack):
        return 1
    if args.strict and any(f.level != "error" for r in report.reports for f in r.findings):
        return 1
    return 0


def cmd_wave(args, store, out) -> int:
    """Capture and scan authored skills, then queue exact evidence for later human approval.

    Wave never publishes. It also refuses the isolated pytest database unconditionally because the
    fixture truncates it between tests.
    """
    from semiskill.authoring.lint import lint_wave_dir, render as render_lint
    from semiskill.wave import load_wave, render_report, run_wave, write_wave_report

    dsn = args.dsn or Config.from_env().database_url
    writes = args.command == "wave" and not args.dry_run
    dbname = dsn.rsplit("/", 1)[-1].split("?")[0]
    if writes and dbname.endswith("_test"):
        print("refusing to queue candidates in the isolated pytest database\n"
              f"  dsn: {dsn}\n"
              "  point --dsn at the development catalog database.",
              file=out)
        return 2
    if writes and not args.yes and dbname == "semiskill":
        print("refusing to write to the development catalog without --yes\n"
              f"  dsn: {dsn}\n  pass --yes after checking the target database.", file=out)
        return 2

    if args.lint_first:
        lint = lint_wave_dir(args.path)
        # The per-skill lint asks "is this file publishable"; the pack check asks "does this pack
        # agree with itself". `semiskill lint` has always run both, but the wave ran only the first,
        # so a pack that disagreed with itself could still publish — the gate was advisory exactly
        # where it needed to be a precondition. Only error-level findings abort; warns are the
        # authoring backlog and must not block a release.
        from semiskill.authoring.consistency import check_pack, render as render_pack
        pack_errors = [f for f in check_pack(args.path) if f.level == "error"]
        if not lint.ok or pack_errors:
            if not lint.ok:
                print(render_lint(lint, style="text"), file=out)
            if pack_errors:
                print("\n" + render_pack(pack_errors), file=out)
            print("\nwave aborted before any artifact was written — fix the errors above first.",
                  file=out)
            return 1

    items = load_wave(args.path)
    if not items:
        print(f"no SKILL.md found under {args.path}", file=out)
        return 1

    # Build the store from the RESOLVED dsn, not the environment default — otherwise --dsn would
    # steer the pipeline's corpus probe while artifacts silently landed in a different database.
    if store is None and writes:
        from semiskill.artifacts.store import PostgresArtifactStore
        store = PostgresArtifactStore(dsn)

    if args.command == "wave-plan" or args.dry_run:
        for i in items:
            print(f"{i.slug}\t{i.payload_sha256[:12]}\t{i.path}", file=out)
        print(f"\n{len(items)} skill(s) would be captured/scanned against {dsn}; "
              "wave would create zero approvals and zero publications.", file=out)
        return 0

    report = run_wave(store=store, dsn=dsn, items=items, permissions_label=args.label,
                      on_duplicate=args.on_duplicate,
                      journal_path=Path(args.reports) / "journal.jsonl" if args.reports else None)
    print(render_report(report, style="markdown"), file=out)
    if args.reports:
        md, js = write_wave_report(report, args.reports)
        print(f"\nreport: {md}", file=out)
    return 0 if report.ok else 1


def cmd_pack(args, store, out) -> int:
    """Build the deliverable pack from what the catalog says is published (ADR-008/009)."""
    from datetime import datetime, timezone
    from semiskill.artifacts.store import PostgresArtifactStore
    from semiskill.authoring.pack import PackRefused, build_pack

    dsn = args.dsn or Config.from_env().database_url
    store = store or PostgresArtifactStore(dsn)
    try:
        root, manifest = build_pack(
            store=store, source_root=args.path, out_dir=args.out, pack_name=args.name,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            make_zip=not args.no_zip)
    except PackRefused as e:
        print(f"pack refused: {e}", file=out)
        return 1
    print(f"{manifest.skill_count} skill(s) packed to {root}", file=out)
    for s_ in manifest.skills:
        print(f"  {s_.name:32} {s_.slots} slot(s)  {s_.sha256[:12]}", file=out)
    if not args.no_zip:
        print(f"\nzip: {Path(args.out) / (args.name + '.zip')}", file=out)
    print("install: unzip and drop the folder into ~/.cursor/skills/ — see README-INSTALL.md",
          file=out)
    return 0


def cmd_catalog(args, store, out) -> int:
    """Generate the browsable catalog from what published: catalog.md (SharePoint renders it
    natively), catalog.html (rich, self-contained, download-and-open) and catalog.csv (paste into a
    SharePoint list for grouped browse)."""
    from datetime import datetime, timezone
    from semiskill.artifacts.store import PostgresArtifactStore
    from semiskill.authoring.catalog_page import build_catalog

    dsn = args.dsn or Config.from_env().database_url
    store = store or PostgresArtifactStore(dsn)
    d, entries = build_catalog(store=store, out_dir=args.out,
                               generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    if not entries:
        print("nothing is published yet — run `semiskill wave` first", file=out)
        return 1
    print(f"{len(entries)} skill(s) -> {d}", file=out)
    for f in ("catalog.md", "catalog.html", "catalog.csv"):
        print(f"  {d / f}", file=out)
    print("\nSharePoint: upload catalog.md to a document library (it renders in the browser);",
          file=out)
    print("paste catalog.csv into a list for grouped browse; catalog.html is download-and-open.",
          file=out)
    return 0


def cmd_scoreboard(args, store, out) -> int:
    """Coverage of the planned registry by the PUBLISHED catalog. Deterministic by design — a
    scoreboard that can be talked into optimism is worse than none."""
    from datetime import datetime, timezone
    from semiskill.artifacts.store import PostgresArtifactStore
    from semiskill.authoring.scoreboard import build_scoreboard, render

    dsn = args.dsn or Config.from_env().database_url
    store = store or PostgresArtifactStore(dsn)
    sb = build_scoreboard(store=store, registry_path=args.registry, skills_root=args.skills,
                          target=args.fail_under, strict_gate=args.strict_gate,
                          generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                          lint=not args.no_lint)
    style = "json" if args.json else ("markdown" if args.markdown else "text")
    print(render(sb, style=style), file=out)
    return 0 if sb.ok else 1


def cmd_site(args, store, out) -> int:
    """Generate the browsable multi-page site from the published catalog."""
    from datetime import datetime, timezone
    from semiskill.artifacts.store import PostgresArtifactStore
    from semiskill.authoring.site import build_site

    dsn = args.dsn or Config.from_env().database_url
    store = store or PostgresArtifactStore(dsn)
    res = build_site(store=store, out_dir=args.out,
                     generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    if not res.entries:
        print("nothing is published yet — run `semiskill wave` first", file=out)
        return 1
    print(f"{len(res.entries)} skill(s) -> {len(res.pages)} pages in {res.root}", file=out)
    print(f"  open {res.root / 'index.html'}", file=out)
    print("  SharePoint: upload catalog.md (it renders in the browser); the .html tree is "
          "download-and-open.", file=out)
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

    approve = sub.add_parser("approve", help="record an explicit authenticated publication decision")
    approve.add_argument("skill_version_id")
    approve.add_argument("--automated-review", required=True)
    approve.add_argument("--content-review", required=True)
    approve.add_argument("--expected-sha256", required=True)
    approve.add_argument("--decision", required=True, choices=["approve", "reject"])
    approve.add_argument("--reason", required=True)
    approve.add_argument("--environment", choices=["development", "production"],
                         default="development")
    approve.set_defaults(func=cmd_approve, needs_store=True)

    unpublish = sub.add_parser("unpublish", help="append an authenticated unpublication correction")
    unpublish.add_argument("approval_id")
    unpublish.add_argument("--reason", required=True)
    unpublish.add_argument("--environment", choices=["development", "production"],
                           default="development")
    unpublish.add_argument("--no-quarantine", action="store_true")
    unpublish.set_defaults(func=cmd_unpublish, needs_store=True)

    lt = sub.add_parser("lint", help="pre-flight lint a skill or a wave directory (no database)")
    lt.add_argument("path", help="a SKILL.md, a skill directory, or a tree of them")
    lt.add_argument("--json", action="store_true", help="machine-readable output")
    lt.add_argument("--strict", action="store_true", help="also fail on warnings and advisories")
    lt.add_argument("--probe-dsn", default=None,
                    help="consult the real held-out injection corpus (returns class names only)")
    lt.set_defaults(func=cmd_lint, needs_store=False)

    for name, helptext, needs_store in (
        ("wave-plan", "show what a wave would do, without writing anything", False),
        ("wave", "capture/scan skills and queue exact evidence for human approval", False),
    ):
        w = sub.add_parser(name, help=helptext)
        w.add_argument("path", help="directory containing skill folders")
        w.add_argument("--dsn", default=None, help="catalog database (defaults to DATABASE_URL)")
        w.add_argument("--label", default="public", choices=_LABELS,
                       help="permissions label for the wave (ADR-009: generic skills are public)")
        w.add_argument("--on-duplicate", default="supersede",
                       choices=["supersede", "skip", "fail"], dest="on_duplicate")
        w.add_argument("--reports", default="reports", help="where to write the wave report")
        w.add_argument("--dry-run", action="store_true")
        w.add_argument("--no-lint-first", dest="lint_first", action="store_false", default=True,
                       help="skip the pre-flight lint (not recommended)")
        w.add_argument("--yes", action="store_true", help="confirm writing to this database")
        w.set_defaults(func=cmd_wave, needs_store=needs_store)

    pk = sub.add_parser("pack", help="build the installable pack from the published catalog")
    pk.add_argument("path", help="the skill source tree")
    pk.add_argument("--dsn", default=None, help="catalog database (defaults to DATABASE_URL)")
    pk.add_argument("--out", default="dist", help="output directory")
    pk.add_argument("--name", default="semiskill-dv", help="pack folder name")
    pk.add_argument("--no-zip", action="store_true")
    pk.set_defaults(func=cmd_pack, needs_store=False)

    cat = sub.add_parser("catalog", help="generate the browsable catalog page from the published catalog")
    cat.add_argument("--dsn", default=None, help="catalog database (defaults to DATABASE_URL)")
    cat.add_argument("--out", default="dist/site", help="output directory")
    cat.set_defaults(func=cmd_catalog, needs_store=False)

    sc = sub.add_parser("scoreboard", help="coverage of the planned registry by the published catalog")
    sc.add_argument("--registry", default="specs/skill_registry.json")
    sc.add_argument("--skills", default="skills", help="the skill source tree")
    sc.add_argument("--dsn", default=None)
    sc.add_argument("--fail-under", type=int, default=5, dest="fail_under",
                    help="minimum published skills per role (exit 1 below it)")
    sc.add_argument("--strict-gate", action="store_true", dest="strict_gate",
                    help="also fail if a published skill has no independent recheck")
    sc.add_argument("--no-lint", action="store_true", dest="no_lint")
    sc.add_argument("--json", action="store_true")
    sc.add_argument("--markdown", action="store_true")
    sc.set_defaults(func=cmd_scoreboard, needs_store=False)

    st = sub.add_parser("site", help="generate the browsable multi-page catalog site")
    st.add_argument("--dsn", default=None)
    st.add_argument("--out", default="dist/site")
    st.set_defaults(func=cmd_site, needs_store=False)
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
