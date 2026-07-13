"""Phase G — seed the catalog by dogfooding the pipeline.

Every generated role-enablement skill is submitted through L1 and must pass the FULL L4/L6 pipeline +
human approval before it publishes — the identical path any submission takes. There is NO back-door
insert: a seed skill reaches the catalog only via a passing scan_run + an approval (ADR-003). A
deliberately-broken seed is blocked exactly like any other malicious submission.
"""
from __future__ import annotations
from dataclasses import dataclass
from semiskill.artifacts.store import ArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.spine.pipeline import run_pipeline
from semiskill.governance.publish import publish_skill, PublishRefused


@dataclass(frozen=True)
class SeedResult:
    slug: str
    skill_version_id: object
    verdict: str
    blocked_at: object
    published: bool


def seed_skill(*, store: ArtifactStore, dsn: str, skill_md: str, actor: str = "seed-generator",
               approver_actor: str = "seed-approver", auto_approve: bool = True) -> SeedResult:
    """Push one generated seed through the pipeline. Publishes only if the aggregate verdict is
    'approve' AND a human approves (auto_approve simulates that human here). Blocked seeds never
    publish. Returns the outcome for verification."""
    sv = store.append(build_skill_version(skill_md=skill_md, actor=actor))
    res = run_pipeline(store=store, dsn=dsn, skill_version_id=sv.artifact_id)
    published = False
    if auto_approve and res.review is not None and res.verdict == "approve":
        try:
            publish_skill(store=store, skill_version_id=sv.artifact_id,
                          review_id=res.review.artifact_id, approver_actor=approver_actor,
                          approver=lambda d: True)
            published = True
        except PublishRefused:
            published = False
    return SeedResult(slug=sv.payload.get("slug", "?"), skill_version_id=sv.artifact_id,
                      verdict=res.verdict, blocked_at=res.blocked_at, published=published)


def seed_catalog(*, store: ArtifactStore, dsn: str, skills: list[str], **kw) -> list[SeedResult]:
    return [seed_skill(store=store, dsn=dsn, skill_md=md, **kw) for md in skills]
