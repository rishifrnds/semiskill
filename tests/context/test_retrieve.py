import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.context.retrieve import search_catalog

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _md(name, slug):
    return f"---\nname: {name}\nslug: {slug}\nfunction: dv\nrole: r\nlevel: l\n---\nbody"


def _publish(store, sv):
    store.append(sv)
    store.append(Artifact.new(
        artifact_type=ArtifactType.APPROVAL, source_system=SourceSystem.WEB, actor="approver",
        actor_kind=ActorKind.HUMAN, input_refs=[sv.artifact_id],
        payload={"verdict": "approve", "published": True}))


@pytest.mark.integration
def test_need_to_know_invisible_to_unauthorized(store, pg_dsn):
    _publish(store, build_skill_version(skill_md=_md("Public Skill", "dv/pub"), actor="a"))
    _publish(store, build_skill_version(skill_md=_md("Secret Skill", "dv/secret"), actor="a",
                                        permissions_label="need-to-know"))

    team_view = {c.slug for c in search_catalog(dsn=pg_dsn, principal=["team"])}
    assert team_view == {"dv/pub"}                      # secret skill is invisible

    cleared = {c.slug for c in search_catalog(dsn=pg_dsn, principal=["team", "need-to-know"])}
    assert cleared == {"dv/pub", "dv/secret"}           # visible with clearance


@pytest.mark.integration
def test_results_are_delimited_untrusted(store, pg_dsn):
    _publish(store, build_skill_version(skill_md=_md("X", "dv/x"), actor="a"))
    cards = search_catalog(dsn=pg_dsn, principal=["team"])
    assert len(cards) == 1
    assert cards[0].content.startswith("<<<UNTRUSTED-ARTIFACT-DATA>>>")


@pytest.mark.integration
def test_unpublished_not_in_catalog(store, pg_dsn):
    store.append(build_skill_version(skill_md=_md("Draft", "dv/draft"), actor="a"))  # no approval
    assert search_catalog(dsn=pg_dsn, principal=["team"]) == []


@pytest.mark.integration
def test_empty_principal_fails_closed(store, pg_dsn):
    with pytest.raises(ValueError):
        search_catalog(dsn=pg_dsn, principal=[])
