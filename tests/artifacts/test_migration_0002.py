import psycopg
import pytest
from pathlib import Path
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from tests.support import publish_test_skill

MIG = Path("semiskill/artifacts/migrations")


def _md(name, slug, function="dv", role="r", level="l"):
    return f"---\nname: {name}\nslug: {slug}\nfunction: {function}\nrole: {role}\nlevel: {level}\n---\nbody"


@pytest.fixture
def store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _publish(store, sv):
    store.append(sv)
    publish_test_skill(store, sv)


def _search(dsn, q, labels, f_function=None, f_role=None, f_level=None):
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            "SELECT slug FROM catalog_search(%s,%s,%s,%s,%s,%s)",
            (q, labels, f_function, f_role, f_level, 100),
        ).fetchall()
    return {r[0] for r in rows}


@pytest.mark.integration
def test_catalog_shows_only_published_and_acl_filtered(store, pg_dsn):
    _publish(store, build_skill_version(skill_md=_md("Team Skill", "dv/team"), actor="a"))
    _publish(store, build_skill_version(skill_md=_md("Reg Skill", "dv/reg"), actor="a",
                                        permissions_label="regulated"))
    store.append(build_skill_version(skill_md=_md("Draft", "dv/draft"), actor="a"))  # unpublished

    assert _search(pg_dsn, "", ["team"]) == {"dv/team"}                 # regulated + draft hidden
    assert _search(pg_dsn, "", ["team", "regulated"]) == {"dv/team", "dv/reg"}


@pytest.mark.integration
def test_facet_and_text_filters(store, pg_dsn):
    _publish(store, build_skill_version(skill_md=_md("RTL Lint", "dv/rtl-lint", function="dv"), actor="a"))
    _publish(store, build_skill_version(skill_md=_md("STA Closure", "pd/sta", function="pd"), actor="a"))
    assert _search(pg_dsn, "", ["team"], f_function="pd") == {"pd/sta"}
    assert _search(pg_dsn, "rtl", ["team"]) == {"dv/rtl-lint"}


@pytest.mark.integration
def test_semiskill_app_can_execute_catalog_search(store, pg_dsn):
    _publish(store, build_skill_version(skill_md=_md("X", "dv/x"), actor="a"))
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET ROLE semiskill_app")
        n = conn.execute(
            "SELECT count(*) FROM catalog_search('', ARRAY['team'], NULL, NULL, NULL, 100)"
        ).fetchone()[0]
        conn.execute("RESET ROLE")
    assert n == 1
