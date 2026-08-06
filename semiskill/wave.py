"""Wave driver — publish a directory of authored skills through the real gate, idempotently.

Replaces `seed.seed_catalog` (ADR-009). What that one-liner got wrong, and this fixes:

  * **A malformed item aborted the wave.** A YAML error is not a `ValueError`, so it propagated out
    of the comprehension and abandoned every remaining skill. Here, item failures are isolated and
    recorded; only infrastructure failures abort, because forty rows of "connection refused" are
    strictly worse than one clean stop.
  * **`request-changes` was silent.** It returned `published=False` with no exception, so a wave that
    published nothing looked like a wave that succeeded. Here it is a reported failure.
  * **Re-running double-published.** Slugs are not unique-constrained in the catalog, so a second run
    appended a second card nobody could tell apart. Here the wave is content-addressed: an identical
    slug+hash is skipped, a changed one supersedes.

  * **The content gate was advisory.** A skill published without `skills/<slug>/REVIEW.json`
    recording an *independent* recheck (`recheck.ready: true`), and only `scoreboard --strict-gate`
    noticed — after the catalog was already written. Here an unready recheck is a precondition
    failure: the item is skipped, loudly, and the rest of the wave proceeds. `--allow-ungated`
    restores the old behaviour for fixtures and seeds, and every skill it lets through is named in
    the report.

The catalog is its own checkpoint — there is no side state to desynchronize. A crash at item 27
replays items 1-26 as no-ops in seconds.

Publishing still goes through `governance.publish.publish_skill`; nothing here writes the catalog
directly (ADR-002).
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

from semiskill.artifacts.schema import Artifact, ArtifactType
from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.gate import READY, REVIEW_FILENAME, gate_status, has_review, read_review_dir
from semiskill.capture.intake import build_skill_version, load_skill_dir, payload_fingerprint
from semiskill.governance.publish import PublishRefused, publish_skill
from semiskill.governance.rollback import RollbackRefused, unpublish_skill
from semiskill.spine.pipeline import run_pipeline

# Item statuses. `published` and `superseded` are the only successes.
PUBLISHED = "published"
SUPERSEDED = "superseded"
SKIPPED_IDENTICAL = "skipped-identical"
CHANGES_REQUESTED = "changes-requested"
BLOCKED = "blocked"
LINT_FAILED = "lint-failed"
ERROR = "error"
# The content gate refused the item. Two statuses, not one, because "nobody ever reviewed this" and
# "a reviewer looked and said no" need different people to do different things.
GATE_MISSING = "gate-missing"
GATE_NOT_READY = "gate-not-ready"

SUCCESS = frozenset({PUBLISHED, SUPERSEDED, SKIPPED_IDENTICAL})

class WaveAborted(RuntimeError):
    """Infrastructure failed. The remaining items were not attempted."""


@dataclass(frozen=True)
class WaveItem:
    path: str
    slug: str
    name: str
    skill_md: str
    files: dict[str, str]
    payload_sha256: str


@dataclass(frozen=True)
class WaveItemResult:
    slug: str
    path: str
    status: str
    skill_version_id: str | None = None
    verdict: str | None = None
    gate: str | None = None          # content-gate status of REVIEW.json (authoring.gate)
    blocked_at: int | None = None
    aggregate_safety: float | None = None
    superseded_approval_id: str | None = None
    payload_sha256: str = ""
    error: str | None = None
    elapsed_s: float = 0.0

    @property
    def ok(self) -> bool:
        return self.status in SUCCESS


@dataclass(frozen=True)
class WaveReport:
    wave_id: str
    started_at: str
    finished_at: str
    permissions_label: str
    on_duplicate: str
    allow_ungated: bool = False
    items: tuple[WaveItemResult, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.items) and all(i.ok for i in self.items)

    @property
    def ungated_published(self) -> tuple[str, ...]:
        """Slugs that reached the catalog without a ready recheck — only possible under the
        escape hatch. An override that leaves no trace is the problem it was meant to solve."""
        return tuple(i.slug for i in self.items
                     if i.status in (PUBLISHED, SUPERSEDED) and i.gate != READY)


def payload_hash(payload: dict) -> str:
    """Compatibility alias for the canonical installable-payload fingerprint."""
    return payload_fingerprint(payload)


def load_wave(root: str | Path) -> list[WaveItem]:
    """Load every skill directory under `root` (any directory containing a SKILL.md)."""
    r = Path(root)
    items: list[WaveItem] = []
    for skill_md_path in sorted(r.rglob("SKILL.md")):
        d = skill_md_path.parent
        skill_md, files = load_skill_dir(d)
        payload = build_skill_version(skill_md=skill_md, actor="wave-loader", files=files).payload
        items.append(WaveItem(path=str(d), slug=payload["slug"], name=payload["name"],
                              skill_md=skill_md, files=files,
                              payload_sha256=payload_hash(payload)))
    return items


def _published_index(store: ArtifactStore) -> dict[str, tuple[Artifact, Artifact]]:
    """{slug: (skill_version, active published approval)} for everything currently discoverable.

    Uses the same active-approval-wins rule as `spine.lifecycle.derive_state`: an approval that some
    later approval corrects is inactive.
    """
    approvals = store.by_type(ArtifactType.APPROVAL)
    superseded = {a.corrects_ref for a in approvals if a.corrects_ref is not None}
    out: dict[str, tuple[Artifact, Artifact]] = {}
    for sv in store.by_type(ArtifactType.SKILL_VERSION):
        related = [a for a in approvals
                   if sv.artifact_id in a.input_refs and a.artifact_id not in superseded]
        if not related:
            continue
        latest = max(related, key=lambda a: a.timestamp_start)
        if latest.payload.get("verdict") == "approve" and latest.payload.get("published") is True:
            slug = sv.payload.get("slug")
            if slug:
                prior = out.get(slug)
                if prior is None or sv.timestamp_start >= prior[0].timestamp_start:
                    out[slug] = (sv, latest)
    return out


def _gate_refusal(item: WaveItem, review: dict | None) -> tuple[str, str]:
    """(status, reason) for an item whose content gate is not `recheck-ready`.

    The reason has to name the fix, not just the fault: a missing record means nobody has reviewed
    this skill yet, an unready one means somebody did and said no.
    """
    if review is None:
        if has_review(item.path):
            return GATE_MISSING, (f"{REVIEW_FILENAME} in {item.path} is unreadable — a gate record "
                                  "that will not parse proves nothing; re-run the authoring gate")
        return GATE_MISSING, (f"no {REVIEW_FILENAME} in {item.path} — this skill has had no "
                              "independent content recheck; run the authoring gate, or pass "
                              "--allow-ungated if this is a fixture")
    why = str((review.get("recheck") or {}).get("why") or "").strip()
    remaining = (review.get("recheck") or {}).get("remaining") or []
    detail = why or (f"{len(remaining)} item(s) remaining" if remaining else "no reason recorded")
    return GATE_NOT_READY, (f"{REVIEW_FILENAME} records recheck.ready is not true "
                            f"({gate_status(review)}): {detail}")


def _is_infrastructure_error(exc: BaseException) -> bool:
    """Connection/permission/migration failures mean the next 39 items will fail identically."""
    name = type(exc).__name__
    if name in {"OperationalError", "InterfaceError", "InsufficientPrivilege", "UndefinedTable",
                "UndefinedFunction", "AdminShutdown", "CannotConnectNow"}:
        return True
    module = type(exc).__module__ or ""
    return module.startswith("psycopg") and "Data" not in name


def run_wave(*, store: ArtifactStore, dsn: str, items: Iterable[WaveItem],
             actor: str = "wave-driver", approver_actor: str = "wave-approver",
             permissions_label: str = "public", on_duplicate: str = "supersede",
             dry_run: bool = False, only: set[str] | None = None,
             allow_ungated: bool = False,
             journal_path: str | Path | None = None,
             progress: Callable[[WaveItemResult], None] | None = None,
             now: Callable[[], float] = time.time) -> WaveReport:
    """Run a wave. Publishes only through the gated actuator; never writes the catalog directly.

    `allow_ungated` skips the `REVIEW.json` precondition — for fixtures, seeds and local
    experiments only. The report names every skill it lets through.
    """
    if on_duplicate not in {"supersede", "skip", "fail"}:
        raise ValueError(f"on_duplicate must be supersede|skip|fail, got {on_duplicate!r}")

    items = [i for i in items if only is None or i.slug in only]
    wave_id = f"wave-{uuid.uuid4().hex[:8]}"
    started = _iso(now())
    results: list[WaveItemResult] = []
    journal = Path(journal_path) if journal_path else None
    if journal:
        journal.parent.mkdir(parents=True, exist_ok=True)

    published = {} if dry_run else _published_index(store)

    for item in items:
        t0 = now()
        try:
            result = _run_one(store=store, dsn=dsn, item=item, actor=actor,
                              approver_actor=approver_actor, permissions_label=permissions_label,
                              on_duplicate=on_duplicate, dry_run=dry_run, published=published,
                              allow_ungated=allow_ungated)
        except WaveAborted:
            raise
        except Exception as exc:                                   # noqa: BLE001 — isolate the item
            if _is_infrastructure_error(exc):
                raise WaveAborted(
                    f"{type(exc).__name__}: {exc} (aborted at {item.slug}; "
                    f"{len(results)} of {len(items)} items completed)") from exc
            result = WaveItemResult(slug=item.slug, path=item.path, status=ERROR,
                                    payload_sha256=item.payload_sha256,
                                    error=f"{type(exc).__name__}: {exc}")
        result = _with_elapsed(result, now() - t0)
        results.append(result)
        if journal:
            with journal.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(_as_dict(result), ensure_ascii=False) + "\n")
        if progress:
            progress(result)

    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    counts["total"] = len(results)
    counts["ok"] = sum(1 for r in results if r.ok)
    # Gate arithmetic is part of the counts, not a footnote: a wave that quietly published half of
    # what it loaded, or published anything ungated, must be visible from the numbers alone.
    counts["gate-refused"] = sum(1 for r in results if r.status in (GATE_MISSING, GATE_NOT_READY))
    counts["ungated-published"] = sum(1 for r in results
                                      if r.status in (PUBLISHED, SUPERSEDED) and r.gate != READY)

    return WaveReport(wave_id=wave_id, started_at=started, finished_at=_iso(now()),
                      permissions_label=permissions_label, on_duplicate=on_duplicate,
                      allow_ungated=allow_ungated, items=tuple(results), counts=counts)


def _run_one(*, store, dsn, item: WaveItem, actor, approver_actor, permissions_label,
             on_duplicate, dry_run, published, allow_ungated=False) -> WaveItemResult:
    # The content gate is a PRECONDITION, so it is evaluated before the duplicate check and before
    # anything is written — including in a dry run, where reporting "would publish" for a skill the
    # gate will refuse is a lie you find out about later.
    review = read_review_dir(item.path)
    gate = gate_status(review)
    if gate != READY and not allow_ungated:
        status, reason = _gate_refusal(item, review)
        return WaveItemResult(slug=item.slug, path=item.path, status=status, gate=gate,
                              payload_sha256=item.payload_sha256, error=reason)

    prior = published.get(item.slug)

    if prior is not None:
        prior_sv, prior_approval = prior
        if payload_hash(prior_sv.payload) == item.payload_sha256:
            return WaveItemResult(slug=item.slug, path=item.path, status=SKIPPED_IDENTICAL,
                                  skill_version_id=str(prior_sv.artifact_id), gate=gate,
                                  payload_sha256=item.payload_sha256)
        if on_duplicate == "skip":
            return WaveItemResult(slug=item.slug, path=item.path, status=SKIPPED_IDENTICAL,
                                  skill_version_id=str(prior_sv.artifact_id), gate=gate,
                                  payload_sha256=item.payload_sha256,
                                  error="content changed but on_duplicate=skip")
        if on_duplicate == "fail":
            return WaveItemResult(slug=item.slug, path=item.path, status=ERROR, gate=gate,
                                  payload_sha256=item.payload_sha256,
                                  error=f"slug {item.slug!r} is already published with different content")

    if dry_run:
        return WaveItemResult(slug=item.slug, path=item.path,
                              status=SKIPPED_IDENTICAL if prior else PUBLISHED, gate=gate,
                              payload_sha256=item.payload_sha256,
                              error="dry run — nothing was written")

    sv = store.append(build_skill_version(skill_md=item.skill_md, actor=actor,
                                          permissions_label=permissions_label, files=item.files))
    res = run_pipeline(store=store, dsn=dsn, skill_version_id=sv.artifact_id)
    common = dict(slug=item.slug, path=item.path, skill_version_id=str(sv.artifact_id),
                  verdict=res.verdict, gate=gate, payload_sha256=item.payload_sha256,
                  blocked_at=int(res.blocked_at) if res.blocked_at is not None else None)
    aggregate = res.review.payload.get("aggregate_safety") if res.review is not None else None

    if res.blocked_at is not None:
        return WaveItemResult(status=BLOCKED, aggregate_safety=aggregate, **common)
    if res.verdict != "approve":
        # The silent failure this driver exists to make loud.
        return WaveItemResult(status=CHANGES_REQUESTED, aggregate_safety=aggregate,
                              error=f"aggregate verdict {res.verdict!r} — not published", **common)

    try:
        publish_skill(store=store, skill_version_id=sv.artifact_id,
                      review_id=res.review.artifact_id, approver_actor=approver_actor,
                      approver=lambda d: True)
    except PublishRefused as exc:
        return WaveItemResult(status=ERROR, aggregate_safety=aggregate,
                              error=f"PublishRefused: {exc}", **common)

    # Publish-new-BEFORE-unpublish-old: the reverse order would leave the catalog with a hole if the
    # new publish failed.
    superseded_id = None
    if prior is not None:
        prior_sv, prior_approval = prior
        try:
            unpublish_skill(store=store, skill_version_id=prior_sv.artifact_id,
                            published_approval_id=prior_approval.artifact_id,
                            approver_actor=approver_actor, approver=lambda d: True,
                            quarantine=False)
            superseded_id = str(prior_approval.artifact_id)
        except RollbackRefused as exc:
            return WaveItemResult(status=ERROR, aggregate_safety=aggregate,
                                  error=f"published but could not supersede the old version: {exc}",
                                  **common)
        return WaveItemResult(status=SUPERSEDED, aggregate_safety=aggregate,
                              superseded_approval_id=superseded_id, **common)

    return WaveItemResult(status=PUBLISHED, aggregate_safety=aggregate, **common)


def _with_elapsed(r: WaveItemResult, seconds: float) -> WaveItemResult:
    from dataclasses import replace
    return replace(r, elapsed_s=round(seconds, 3))


def _as_dict(r: WaveItemResult) -> dict:
    from dataclasses import asdict
    return asdict(r)


def _iso(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_report(report: WaveReport, *, style: str = "markdown") -> str:
    if style == "json":
        return json.dumps({
            "wave_id": report.wave_id, "started_at": report.started_at,
            "finished_at": report.finished_at, "ok": report.ok,
            "permissions_label": report.permissions_label, "on_duplicate": report.on_duplicate,
            "allow_ungated": report.allow_ungated,
            "ungated_published": list(report.ungated_published),
            "counts": report.counts, "items": [_as_dict(i) for i in report.items],
        }, indent=2, sort_keys=True)

    gate_line = "**BYPASSED (--allow-ungated)**" if report.allow_ungated else "enforced"
    lines = [f"# Wave {report.wave_id}", "",
             f"- started: {report.started_at} · finished: {report.finished_at}",
             f"- label: `{report.permissions_label}` · on duplicate: `{report.on_duplicate}`",
             f"- content gate: {gate_line}",
             f"- result: **{'all items succeeded' if report.ok else 'INCOMPLETE'}**", "",
             "| skill | status | verdict | gate | safety |", "|---|---|---|---|---|"]
    for i in report.items:
        safety = f"{i.aggregate_safety:.3f}" if i.aggregate_safety is not None else "—"
        lines.append(f"| `{i.slug}` | {i.status} | {i.verdict or '—'} | {i.gate or '—'} | {safety} |")
    lines.append("")
    lines.append(" · ".join(f"{k}: {v}" for k, v in sorted(report.counts.items())))
    failures = [i for i in report.items if not i.ok]
    if failures:
        lines += ["", "## Not published", ""]
        for i in failures:
            lines.append(f"- `{i.slug}` — {i.status}: {i.error or 'see the scan report'}")
    ungated = report.ungated_published
    if ungated:
        lines += ["", "## Published WITHOUT an independent content recheck", "",
                  "`--allow-ungated` was used. These skills reached the catalog with no "
                  f"`{REVIEW_FILENAME}` recording `recheck.ready: true`:", ""]
        for slug in ungated:
            lines.append(f"- `{slug}`")
    return "\n".join(lines)


def write_wave_report(report: WaveReport, out_dir: str | Path) -> tuple[Path, Path]:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    md = d / f"{report.wave_id}.md"
    js = d / f"{report.wave_id}.json"
    md.write_text(render_report(report, style="markdown"), encoding="utf-8")
    js.write_text(render_report(report, style="json"), encoding="utf-8")
    return md, js
