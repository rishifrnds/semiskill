import uuid

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from semiskill.artifacts.store import PostgresArtifactStore


def _login_dsn(base_dsn: str, user: str, password: str) -> str:
    values = conninfo_to_dict(base_dsn)
    values.update(user=user, password=password)
    return make_conninfo(**values)


@pytest.mark.integration
def test_runtime_clearance_and_actuator_are_distinct_least_privilege_logins(pg_dsn):
    suffix = uuid.uuid4().hex[:10]
    password = "SemiSkill-test-only-9f!"
    names = {
        "runtime": f"ss_runtime_{suffix}",
        "clearance": f"ss_clearance_{suffix}",
        "actuator": f"ss_actuator_{suffix}",
    }
    with psycopg.connect(pg_dsn, autocommit=True) as admin:
        can_create_roles = admin.execute(
            "SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=current_user"
        ).fetchone()[0]
        if not can_create_roles:
            pytest.skip("test database owner cannot create isolated login fixtures")
        for name in names.values():
            admin.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(
                sql.Identifier(name), sql.Literal(password),
            ))
        admin.execute(sql.SQL("GRANT semiskill_app TO {}").format(
            sql.Identifier(names["runtime"])
        ))
        admin.execute(sql.SQL("GRANT semiskill_acl_reader TO {}").format(
            sql.Identifier(names["clearance"])
        ))
        admin.execute(sql.SQL("GRANT semiskill_approval_actuator TO {}").format(
            sql.Identifier(names["actuator"])
        ))

    dsns = {key: _login_dsn(pg_dsn, value, password) for key, value in names.items()}
    try:
        PostgresArtifactStore(dsns["runtime"], approval_dsn=dsns["actuator"])

        with psycopg.connect(dsns["runtime"]) as runtime:
            session_user, current_user = runtime.execute(
                "SELECT session_user,current_user"
            ).fetchone()
            assert session_user == current_user == names["runtime"]
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                runtime.execute("SELECT * FROM artifacts")
            runtime.rollback()
            assert runtime.execute(
                "SELECT count(*) FROM catalog_search('',ARRAY['public'],NULL,NULL,NULL,10)"
            ).fetchone()[0] >= 0
            assert runtime.execute(
                "SELECT pg_has_role(session_user,'semiskill_approval_actuator','MEMBER')"
            ).fetchone()[0] is False

        with psycopg.connect(dsns["clearance"]) as clearance:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                clearance.execute("SELECT * FROM artifacts")
            clearance.rollback()
            clearance.execute("SET ROLE semiskill_acl_reader")
            session_user, current_user = clearance.execute(
                "SELECT session_user,current_user"
            ).fetchone()
            assert session_user == names["clearance"]
            assert current_user == "semiskill_acl_reader"
            assert clearance.execute(
                "SELECT count(*) FROM artifact_get(%s,ARRAY['team'])", (uuid.uuid4(),)
            ).fetchone()[0] == 0

        with psycopg.connect(dsns["actuator"]) as actuator:
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                actuator.execute("SELECT * FROM artifacts")
            actuator.rollback()
            assert actuator.execute(
                "SELECT pg_has_role(session_user,'semiskill_approval_actuator','MEMBER')"
            ).fetchone()[0] is True
            assert actuator.execute(
                "SELECT has_function_privilege(current_user,"
                "'append_verified_approval(uuid,source_system,text,actor_kind,timestamptz,"
                "timestamptz,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,jsonb)',"
                "'EXECUTE')"
            ).fetchone()[0] is True
            assert actuator.execute(
                "SELECT pg_has_role(session_user,'semiskill_acl_reader','MEMBER')"
            ).fetchone()[0] is False
    finally:
        with psycopg.connect(pg_dsn, autocommit=True) as admin:
            for name in names.values():
                admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(name)))
