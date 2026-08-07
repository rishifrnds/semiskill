from dataclasses import replace
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.capture.events import build_reuse_event
from semiskill.context.provenance import get_lineage, get_reuse
from tests.support import publish_test_skill

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _art(t, refs=(), label="team", payload=None):
    a = Artifact.new(artifact_type=t, source_system=SourceSystem.CLI, actor="svc",
                     actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=list(refs), payload=payload or {})
    return a if label == "team" else replace(a, permissions_label=label)


def _md(slug):
    return (f"---\nname: {slug}\nslug: {slug}\nfunction: design-verification\n"
            "role: dv-engineer\nlevel: senior\n---\nbody")


@pytest.mark.integration
def test_lineage_traces_verification_trail(store, pg_dsn):
    sv = store.append(build_skill_version(skill_md=_md("dv/x"), actor="a"))
    fixture = publish_test_skill(store, sv)

    res = get_lineage(
        dsn=pg_dsn, start_artifact_id=fixture.approval.artifact_id, principal=["team"],
        trusted_clearance=True,
    )
    ids = {n.artifact_id for n in res.nodes}
    expected = {
        sv.artifact_id, fixture.approval.artifact_id,
        *[review.artifact_id for review in store.by_type(ArtifactType.REVIEW)],
        *store.verified_review_contract_ids(),
        *[scan.artifact_id for scan in fixture.scans],
    }
    assert ids == expected
    assert (fixture.automated_review.artifact_id, sv.artifact_id) in res.edges


@pytest.mark.integration
def test_lineage_prunes_unauthorized_at_boundary(store, pg_dsn):
    sv = store.append(build_skill_version(
        skill_md=_md("dv/secret"), actor="a", permissions_label="need-to-know",
    ))
    fixture = publish_test_skill(store, sv)

    res = get_lineage(
        dsn=pg_dsn, start_artifact_id=fixture.approval.artifact_id, principal=["team"],
        trusted_clearance=True,
    )
    assert res.nodes == []


@pytest.mark.integration
def test_untrusted_lineage_reader_cannot_self_assert_team(store, pg_dsn):
    skill = store.append(build_skill_version(skill_md=_md("dv/team"), actor="a"))
    fixture = publish_test_skill(store, skill)
    assert get_lineage(
        dsn=pg_dsn, start_artifact_id=fixture.approval.artifact_id, principal=["team"],
    ).nodes == []


@pytest.mark.integration
def test_unpublished_lineage_is_not_queryable_even_with_clearance(store, pg_dsn):
    skill = _art(ArtifactType.SKILL_VERSION)
    store.append(skill)
    assert get_lineage(
        dsn=pg_dsn, start_artifact_id=skill.artifact_id, principal=["team"],
        trusted_clearance=True,
    ).nodes == []


@pytest.mark.integration
def test_reuse_graph(store, pg_dsn):
    sv = build_skill_version(skill_md=_md("dv/x"), actor="a")
    store.append(sv)
    publish_test_skill(store, sv)
    store.append(build_reuse_event(skill_version_id=sv.artifact_id, actor="u1"))
    store.append(build_reuse_event(skill_version_id=sv.artifact_id, actor="u2", method="copy"))
    recs = get_reuse(
        dsn=pg_dsn, skill_version_id=sv.artifact_id, principal=["team"],
        trusted_clearance=True,
    )
    assert {r.actor for r in recs} == {"u1", "u2"}
    assert {r.method for r in recs} == {"skills-add", "copy"}


@pytest.mark.integration
def test_reuse_gated_on_skill_visibility(store, pg_dsn):
    sv = build_skill_version(skill_md=_md("dv/secret"), actor="a", permissions_label="need-to-know")
    store.append(sv)
    publish_test_skill(store, sv)
    store.append(build_reuse_event(skill_version_id=sv.artifact_id, actor="u1",
                                   permissions_label="need-to-know"))
    # a team-only querier cannot see the skill, so its reuse graph is empty (fail closed)
    assert get_reuse(
        dsn=pg_dsn, skill_version_id=sv.artifact_id, principal=["team"],
        trusted_clearance=True,
    ) == []


@pytest.mark.integration
def test_untrusted_reuse_reader_cannot_self_assert_team(store, pg_dsn):
    skill = build_skill_version(skill_md=_md("dv/team"), actor="a")
    store.append(skill)
    publish_test_skill(store, skill)
    store.append(build_reuse_event(skill_version_id=skill.artifact_id, actor="u1"))
    assert get_reuse(
        dsn=pg_dsn, skill_version_id=skill.artifact_id, principal=["team"],
    ) == []


@pytest.mark.integration
def test_unpublished_reuse_is_not_queryable_even_with_clearance(store, pg_dsn):
    skill = build_skill_version(skill_md=_md("dv/draft"), actor="a")
    store.append(skill)
    store.append(build_reuse_event(skill_version_id=skill.artifact_id, actor="u1"))
    assert get_reuse(
        dsn=pg_dsn, skill_version_id=skill.artifact_id, principal=["team"],
        trusted_clearance=True,
    ) == []
