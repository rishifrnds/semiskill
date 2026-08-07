"""Capture and scan an authored skill wave without crossing the human publication boundary.

``semiskill wave`` is a queue builder. It captures (or reuses) the exact content-addressed
``skill_version``, runs the automated security pipeline once, reconciles canonical independent
content-review evidence, and reports the exact inputs required by a later authenticated human
decision. It never creates approvals, publishes, unpublishes, or supersedes catalog entries.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from semiskill.artifacts.schema import Artifact, ArtifactType
from semiskill.artifacts.store import ArtifactStore
from semiskill.authoring.gate import readiness_for_version
from semiskill.capture.intake import (
    build_skill_version,
    load_skill_source,
    payload_fingerprint,
    shared_bundle_for_skills_root,
)
from semiskill.spine.pipeline import PipelineResult, run_pipeline

# Queue states. Old publication names remain exported as tombstone constants so imports fail by
# behavior rather than at module import; this module never emits them.
AWAITING_REVIEW = "awaiting-review"
REVIEW_BLOCKED = "review-blocked"
AWAITING_APPROVAL = "awaiting-approval"
SKIPPED_IDENTICAL = "skipped-identical"
CHANGES_REQUESTED = "changes-requested"
BLOCKED = "blocked"
LINT_FAILED = "lint-failed"
ERROR = "error"
WOULD_CAPTURE = "would-capture"

PUBLISHED = "published"          # tombstone: no longer emitted
SUPERSEDED = "superseded"        # tombstone: no longer emitted
GATE_MISSING = AWAITING_REVIEW    # compatibility alias
GATE_NOT_READY = REVIEW_BLOCKED   # compatibility alias

SUCCESS = frozenset({AWAITING_REVIEW, AWAITING_APPROVAL, SKIPPED_IDENTICAL, WOULD_CAPTURE})
MAX_WAVE_BATCH_SIZE = 10


class WaveAborted(RuntimeError):
    """Infrastructure failed; remaining candidates were not attempted."""


@dataclass(frozen=True)
class WaveItem:
    path: str
    slug: str
    name: str
    version: str
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
    gate: str | None = None
    blocked_at: int | None = None
    aggregate_safety: float | None = None
    automated_review_id: str | None = None
    content_review_id: str | None = None
    scan_artifact_ids: tuple[str, ...] = ()
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
    items: tuple[WaveItemResult, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.items) and all(item.ok for item in self.items)

    @property
    def allow_ungated(self) -> bool:
        """Compatibility signal proving the retired escape hatch is always disabled."""
        return False

    @property
    def ungated_published(self) -> tuple[str, ...]:
        return ()


def payload_hash(payload: dict) -> str:
    """Compatibility alias for the canonical installable-payload fingerprint."""
    return payload_fingerprint(payload)


def load_wave(root: str | Path) -> list[WaveItem]:
    """Load every skill directory under ``root``; embedded governance metadata fails closed."""
    root_path = Path(root)
    items: list[WaveItem] = []
    shared_bundle = shared_bundle_for_skills_root(root_path)
    for skill_md_path in sorted(root_path.rglob("SKILL.md")):
        directory = skill_md_path.parent
        skill_md, files = load_skill_source(directory, shared_bundle=shared_bundle)
        payload = build_skill_version(skill_md=skill_md, actor="wave-loader", files=files).payload
        items.append(WaveItem(
            path=str(directory),
            slug=payload["slug"],
            name=payload["name"],
            version=payload["version"],
            skill_md=skill_md,
            files=files,
            payload_sha256=payload_hash(payload),
        ))
    return items


def _published_index(store: ArtifactStore) -> dict[str, tuple[Artifact, Artifact]]:
    """Return active exact approval/v1 publications; legacy approvals never enter the catalog."""
    from semiskill.governance.publish import ApprovalChainInvalid
    from semiskill.governance.reconciliation import reconcile_publications

    bundle_reader = getattr(store, "publication_reconciliation_bundle", None)
    if not callable(bundle_reader):
        raise ApprovalChainInvalid("verified publication reconciliation bundle is unavailable")
    try:
        result = reconcile_publications(bundle_reader())
    except (TypeError, ValueError) as exc:
        raise ApprovalChainInvalid("verified publication reconciliation bundle is malformed") from exc
    if result.issues:
        raise ApprovalChainInvalid("verified publication reconciliation found projection anomalies")
    return {
        slug: (publication.skill_version, publication.approval)
        for slug, publication in result.active_by_slug.items()
    }


def _exact_version(versions: Iterable[Artifact], item: WaveItem) -> Artifact | None:
    versions = [
        artifact for artifact in versions
        if isinstance(artifact.payload, dict)
        and artifact.payload.get("slug") == item.slug
        and payload_hash(artifact.payload) == item.payload_sha256
    ]
    return max(versions, key=lambda artifact: artifact.timestamp_start, default=None)


def _security_review(store: ArtifactStore, skill_version: Artifact) -> Artifact | None:
    reviews = [
        artifact for artifact in store.by_type(ArtifactType.REVIEW)
        if isinstance(artifact.payload, dict)
        and artifact.payload.get("review_kind") == "security_aggregate"
        and artifact.input_refs
        and artifact.input_refs[0] == skill_version.artifact_id
    ]
    return max(reviews, key=lambda artifact: artifact.timestamp_start, default=None)


def _pipeline_from_review(store: ArtifactStore, skill_version: Artifact, review: Artifact) -> PipelineResult:
    scans = [store.get(artifact_id) for artifact_id in review.input_refs[1:]]
    scans = [artifact for artifact in scans if artifact is not None]
    return PipelineResult(
        skill_version_id=skill_version.artifact_id,
        scan_artifacts=scans,
        review=review,
        verdict=str(review.payload.get("verdict") or "reject")
        if isinstance(review.payload, dict) else "reject",
        blocked_at=None,
    )


def _is_infrastructure_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in {
        "OperationalError", "InterfaceError", "InsufficientPrivilege", "UndefinedTable",
        "UndefinedFunction", "AdminShutdown", "CannotConnectNow",
    }:
        return True
    return (type(exc).__module__ or "").startswith("psycopg") and "Data" not in name


def run_wave(
    *,
    store: ArtifactStore,
    dsn: str,
    items: Iterable[WaveItem],
    actor: str = "wave-driver",
    permissions_label: str = "public",
    on_duplicate: str = "supersede",
    dry_run: bool = False,
    only: set[str] | None = None,
    allow_ungated: bool | None = None,
    journal_path: str | Path | None = None,
    progress: Callable[[WaveItemResult], None] | None = None,
    now: Callable[[], float] = time.time,
    security_audit_runner=None,
    judge_risk_scanner=None,
    judge_required: bool = True,
) -> WaveReport:
    """Capture/scan candidates and stop before approval.

    ``allow_ungated`` is accepted only to produce an explicit migration error for stale callers; it
    can never widen the gate.

    ``judge_required`` mirrors the stage-5 policy the security gate will apply. It is never widened
    here: refusing early cannot make anything publishable that would otherwise be blocked.
    """
    if allow_ungated:
        raise ValueError("allow_ungated was removed: wave cannot publish or bypass content review")
    if judge_required and judge_risk_scanner is None:
        # The two rules are individually right and jointly unsatisfiable: run_pipeline records
        # stage 5 as `not_sampled` when no judge is supplied (a skipped judge must never be
        # rendered as a pass), and the security gate then refuses the skill with
        # REQUIRED_JUDGE_NOT_PASSED. Capturing and scanning anyway writes six artifacts per skill
        # that are known in advance to fail, and buries the cause a step downstream. Refuse here,
        # before anything is written, and name what is missing.
        raise ValueError(
            "stage 5 is required by policy but no judge_risk_scanner is configured: every skill "
            "in this wave would be captured, scanned, and then refused at the security gate with "
            "REQUIRED_JUDGE_NOT_PASSED. Supply a calibrated judge scanner (see BLK-004), or pass "
            "judge_required=False for a wave the policy genuinely exempts. Do not resolve this by "
            "rewriting a not_sampled stage 5 into a pass."
        )
    if on_duplicate not in {"supersede", "skip", "fail"}:
        raise ValueError(f"on_duplicate must be supersede|skip|fail, got {on_duplicate!r}")

    selected = [item for item in items if only is None or item.slug in only]
    if not dry_run and len(selected) > MAX_WAVE_BATCH_SIZE:
        raise ValueError(
            f"wave batches are limited to {MAX_WAVE_BATCH_SIZE} skills; select an explicit batch"
        )
    wave_id = f"wave-{uuid.uuid4().hex[:8]}"
    started = _iso(now())
    results: list[WaveItemResult] = []
    journal = Path(journal_path) if journal_path else None
    if journal:
        journal.parent.mkdir(parents=True, exist_ok=True)

    for item in selected:
        began = now()
        try:
            result = _run_one(
                store=store,
                dsn=dsn,
                item=item,
                actor=actor,
                permissions_label=permissions_label,
                dry_run=dry_run,
                security_audit_runner=security_audit_runner,
                judge_risk_scanner=judge_risk_scanner,
                judge_required=judge_required,
            )
        except Exception as exc:  # noqa: BLE001 - isolate content errors, abort infrastructure
            if _is_infrastructure_error(exc):
                raise WaveAborted(
                    f"{type(exc).__name__}: {exc} (aborted at {item.slug}; "
                    f"{len(results)} of {len(selected)} items completed)"
                ) from exc
            result = WaveItemResult(
                slug=item.slug,
                path=item.path,
                status=ERROR,
                payload_sha256=item.payload_sha256,
                error=f"{type(exc).__name__}: {exc}",
            )
        result = replace(result, elapsed_s=round(now() - began, 3))
        results.append(result)
        if journal:
            with journal.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(result), ensure_ascii=False) + "\n")
        if progress:
            progress(result)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    counts["total"] = len(results)
    counts["ok"] = sum(result.ok for result in results)
    counts["approvals-created"] = 0
    counts["published"] = 0
    return WaveReport(
        wave_id=wave_id,
        started_at=started,
        finished_at=_iso(now()),
        permissions_label=permissions_label,
        on_duplicate=on_duplicate,
        items=tuple(results),
        counts=counts,
    )


def _run_one(
    *,
    store: ArtifactStore,
    dsn: str,
    item: WaveItem,
    actor: str,
    permissions_label: str,
    dry_run: bool,
    security_audit_runner,
    judge_risk_scanner=None,
    judge_required: bool = True,
) -> WaveItemResult:
    if dry_run:
        return WaveItemResult(
            slug=item.slug,
            path=item.path,
            status=WOULD_CAPTURE,
            payload_sha256=item.payload_sha256,
            error="dry run - nothing was written",
        )

    skill_versions = store.by_type(ArtifactType.SKILL_VERSION)
    skill_version = _exact_version(skill_versions, item)
    already_captured = skill_version is not None
    if skill_version is None:
        collisions = [
            artifact for artifact in skill_versions
            if isinstance(artifact.payload, dict)
            and artifact.payload.get("slug") == item.slug
            and artifact.payload.get("version") == item.version
        ]
        if collisions:
            raise ValueError(
                f"{item.slug}: semantic version {item.version} already exists with different "
                "payload bytes; bump semiskill-version before capture"
            )
        skill_version = store.append(build_skill_version(
            skill_md=item.skill_md,
            actor=actor,
            permissions_label=permissions_label,
            files=item.files,
        ))

    automated = _security_review(store, skill_version)
    if automated is None:
        pipeline = run_pipeline(
            store=store,
            dsn=dsn,
            skill_version_id=skill_version.artifact_id,
            security_audit_runner=security_audit_runner,
            judge_risk_scanner=judge_risk_scanner,
            judge_required=judge_required,
        )
    else:
        pipeline = _pipeline_from_review(store, skill_version, automated)
    automated = pipeline.review
    common = dict(
        slug=item.slug,
        path=item.path,
        skill_version_id=str(skill_version.artifact_id),
        verdict=pipeline.verdict,
        payload_sha256=item.payload_sha256,
        blocked_at=int(pipeline.blocked_at) if pipeline.blocked_at is not None else None,
        aggregate_safety=(automated.payload.get("aggregate_safety") if automated else None),
        automated_review_id=(str(automated.artifact_id) if automated else None),
        scan_artifact_ids=tuple(str(scan.artifact_id) for scan in pipeline.scan_artifacts),
    )
    if pipeline.blocked_at is not None:
        return WaveItemResult(status=BLOCKED, gate="unreviewed", **common)
    if pipeline.verdict != "approve" or automated is None:
        return WaveItemResult(
            status=CHANGES_REQUESTED,
            gate="unreviewed",
            error=f"aggregate verdict {pipeline.verdict!r}; candidate was not queued for approval",
            **common,
        )

    readiness = readiness_for_version(store, skill_version)
    common["gate"] = readiness.status
    common["content_review_id"] = (
        str(readiness.review.artifact_id) if readiness.review is not None else None
    )
    if readiness.status == "unreviewed":
        return WaveItemResult(
            status=AWAITING_REVIEW,
            error="captured and scanned; independent content recheck is still required",
            **common,
        )
    if not readiness.ready:
        detail = "; ".join(readiness.errors) or (
            f"{readiness.open_blocking_findings} open blocking finding(s)"
        )
        return WaveItemResult(status=REVIEW_BLOCKED, error=detail, **common)
    if already_captured and automated is not None:
        # Still return the full immutable approval inputs; skipped means no new artifact was written.
        return WaveItemResult(status=AWAITING_APPROVAL, **common)
    return WaveItemResult(status=AWAITING_APPROVAL, **common)


def _iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def render_report(report: WaveReport, *, style: str = "markdown") -> str:
    payload = {
        "wave_id": report.wave_id,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "ok": report.ok,
        "permissions_label": report.permissions_label,
        "on_duplicate": report.on_duplicate,
        "allow_ungated": False,
        "ungated_published": [],
        "counts": report.counts,
        "items": [asdict(item) for item in report.items],
    }
    if style == "json":
        return json.dumps(payload, indent=2, sort_keys=True)

    lines = [
        f"# Wave {report.wave_id}",
        "",
        f"- started: {report.started_at} · finished: {report.finished_at}",
        f"- label: `{report.permissions_label}`",
        "- publication boundary: **human approval required; wave cannot publish**",
        f"- result: **{'queue updated' if report.ok else 'INCOMPLETE'}**",
        "",
        "| skill | state | security | content review | payload hash |",
        "|---|---|---|---|---|",
    ]
    for item in report.items:
        lines.append(
            f"| `{item.slug}` | {item.status} | {item.verdict or '—'} | {item.gate or '—'} | "
            f"`{item.payload_sha256[:12]}` |"
        )
    lines += ["", " · ".join(f"{key}: {value}" for key, value in sorted(report.counts.items()))]
    failures = [item for item in report.items if not item.ok]
    if failures:
        lines += ["", "## Blocked candidates", ""]
        lines.extend(f"- `{item.slug}` — {item.status}: {item.error or 'see evidence'}" for item in failures)
    return "\n".join(lines)


def write_wave_report(report: WaveReport, out_dir: str | Path) -> tuple[Path, Path]:
    directory = Path(out_dir)
    directory.mkdir(parents=True, exist_ok=True)
    markdown = directory / f"{report.wave_id}.md"
    json_path = directory / f"{report.wave_id}.json"
    markdown.write_text(render_report(report, style="markdown"), encoding="utf-8")
    json_path.write_text(render_report(report, style="json"), encoding="utf-8")
    return markdown, json_path
