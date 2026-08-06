"""Seed intake: capture and scan generated skills, then stop before human approval."""
from __future__ import annotations
from dataclasses import dataclass
from semiskill.artifacts.store import ArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.spine.pipeline import run_pipeline


@dataclass(frozen=True)
class SeedResult:
    slug: str
    skill_version_id: object
    verdict: str
    blocked_at: object
    published: bool


def seed_skill(*, store: ArtifactStore, dsn: str, skill_md: str, actor: str = "seed-generator",
               permissions_label: str = "team",
               files: dict[str, str] | None = None) -> SeedResult:
    """Push one seed through capture/scanning and stop before independent review and approval.

    This helper cannot create an approval or publication. Seeds use the same explicit authenticated
    human decision boundary as every other submission.

    `permissions_label` decides who can ever see the result: a wave of generic, slot-bearing skills
    publishes as `public` (ADR-009), because labelling content that holds nothing internal as `team`
    is both wrong and the direct cause of the empty-catalog symptom — `api.py` defaults an
    unauthenticated caller to `public`."""
    sv = store.append(build_skill_version(skill_md=skill_md, actor=actor,
                                          permissions_label=permissions_label, files=files))
    res = run_pipeline(store=store, dsn=dsn, skill_version_id=sv.artifact_id)
    return SeedResult(slug=sv.payload.get("slug", "?"), skill_version_id=sv.artifact_id,
                      verdict=res.verdict, blocked_at=res.blocked_at, published=False)


# `seed_catalog` was deleted in favour of `semiskill.wave.run_wave` (ADR-009). It was a bare list
# comprehension: one malformed skill raised out and abandoned the rest of the wave, a
# `request-changes` verdict returned published=False with no exception, and a re-run double-published
# every slug. Leaving a working-looking one-liner beside a guarded driver only invites the wrong call
# site at 40x scale.
