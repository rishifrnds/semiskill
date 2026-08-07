import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from dashboard import server as dashboard_server
from semiskill.artifacts.migrate import (
    MigrationAdoptionRefused,
    _ADOPTION_SCHEMA_ATTESTATION_KEYS,
    _attest_checkpoint_0015,
    _canonical_rows,
    _database_identity,
    _forward_audit_id,
    _post_migration_attestations,
    _trusted_legacy_manifest,
    apply_migrations,
    execute_forward_migrations,
    load_forward_migration_plan,
    plan_forward_migrations,
    write_forward_migration_plan,
)
from semiskill.governance.identity import AuthenticatedHuman


MIGRATIONS = Path("semiskill/artifacts/migrations")
CHECKPOINT = "0015_projection_truncate_hardening.sql"


def _operator(*, actor: str = "test-operator", subject: str = "uid:1001"):
    return AuthenticatedHuman(
        actor=actor,
        subject=subject,
        provider="local_os",
        auth_context={"account": actor, "uid": int(subject.split(":", 1)[1])},
    )


def _manifest(directory: Path) -> list[dict]:
    rows = []
    for path in sorted(directory.glob("*.sql")):
        raw = path.read_bytes()
        rows.append({
            "filename": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return rows


@pytest.fixture
def forward_database(tmp_path, monkeypatch):
    source_dsn = os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql://semiskill:semiskill@127.0.0.1:5432/semiskill_test",
    )
    params = conninfo_to_dict(source_dsn)
    params.pop("dbname", None)
    admin_dsn = make_conninfo(**params, dbname="postgres")
    database = f"semiskill_forward_{uuid.uuid4().hex[:10]}_test"
    with psycopg.connect(admin_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    dsn = make_conninfo(**params, dbname=database)

    full = tmp_path / "migrations"
    prefix = tmp_path / "prefix"
    full.mkdir()
    prefix.mkdir()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        shutil.copyfile(path, full / path.name)
        if path.name <= CHECKPOINT:
            shutil.copyfile(path, prefix / path.name)

    monkeypatch.setenv("SEMISKILL_MIGRATOR_ROLE", params.get("user", "semiskill"))
    apply_migrations(dsn, prefix)
    with psycopg.connect(dsn) as conn:
        conn.execute("SET LOCAL search_path = pg_catalog, public")
        database_identity = _database_identity(conn)
        tracker = [
            {"filename": filename, "sha256": checksum, "applied_at": applied_at.isoformat()}
            for filename, checksum, applied_at in conn.execute(
                "SELECT filename,sha256,applied_at FROM public.schema_migrations "
                "ORDER BY filename"
            )
        ]
        repository = _manifest(prefix)
        trusted_legacy, trusted_legacy_sha256 = _trusted_legacy_manifest(_manifest(full))
        final_tracker = [
            {"filename": row["filename"], "sha256": row["sha256"]}
            for row in repository
        ]
        adoption_id = uuid.uuid4()
        tracked_evidence = [
            {**row, "sha256": None} for row in tracker[:10]
        ]
        schema_attestations = {
            key: True for key in _ADOPTION_SCHEMA_ATTESTATION_KEYS
        }
        adopted_filenames = [row["filename"] for row in repository[:10]]
        applied_filenames = [row["filename"] for row in repository[10:]]
        adoption_plan = {
            "schema_version": "migration-checksum-adoption-plan/v1",
            "database": database_identity,
            "environment": "test",
            "source_commit": "b" * 40,
            "tracked_prefix": [row["filename"] for row in trusted_legacy["migrations"]],
            "tracked_manifest": tracked_evidence,
            "repository_manifest": repository,
            "trusted_manifest_sha256": trusted_legacy_sha256,
            "orphaned_test_fixtures_to_remove": [],
            "orphaned_relations_to_drop": [],
            "legacy_null_filenames": adopted_filenames,
            "legacy_null_count": len(adopted_filenames),
            "pending_filenames": applied_filenames,
            "schema_attestations": schema_attestations,
            "historical_limit": trusted_legacy["historical_limit"],
        }
        plan_sha256 = "sha256:" + hashlib.sha256(
            json.dumps(
                adoption_plan,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        payload = {
            "schema_version": "migration-checksum-adoption/v1",
            "adoption_id": str(adoption_id),
            "decision": "adopt_and_apply",
            "environment": "test",
            "reason": "Reviewed the exact legacy foundation before the forward migration test.",
            "source_commit": "b" * 40,
            "plan_sha256": plan_sha256,
            "database": database_identity,
            "tracked_manifest": tracked_evidence,
            "repository_manifest": repository,
            "trusted_manifest_sha256": trusted_legacy_sha256,
            "schema_attestations": schema_attestations,
            "post_migration_attestations": _attest_checkpoint_0015(conn),
            "historical_limit": trusted_legacy["historical_limit"],
            "operator_authentication": {
                "provider": "local_os",
                "subject_sha256": "sha256:" + "d" * 64,
            },
            "adopted_filenames": adopted_filenames,
            "removed_orphaned_test_fixtures": [],
            "removed_orphaned_relations": [],
            "applied_filenames": applied_filenames,
            "final_tracker": final_tracker,
        }
        assert set(payload["post_migration_attestations"].values()) == {True}
        conn.execute(
            "INSERT INTO public.artifacts ("
            "artifact_id,artifact_type,source_system,actor,actor_kind,timestamp_start,"
            "timestamp_end,input_refs,output_refs,permissions_label,objective_tag,"
            "ground_truth_ref,eval_score,rollback_ref,cost_usd,corrects_ref,payload"
            ") VALUES ("
            "%s,'gate_decision','cli','test-operator','human',clock_timestamp(),"
            "clock_timestamp(),'{}'::uuid[],'{}'::uuid[],'need-to-know','compliance',"
            "%s,NULL,%s,NULL,NULL,%s)",
            (
                adoption_id,
                plan_sha256,
                json.dumps({
                    "supported": False,
                    "reason": "historical checksum adoption is an irreversible attestation",
                }),
                json.dumps(payload),
            ),
        )
        conn.commit()

    monkeypatch.setattr(
        "semiskill.artifacts.migrate._resolve_migration_source",
        lambda _repo_root: (full, "e" * 40),
    )
    try:
        yield dsn, database, full, adoption_id
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname=%s AND pid<>pg_backend_pid()",
                (database,),
            )
            conn.execute(sql.SQL("DROP DATABASE {}").format(sql.Identifier(database)))


def _plan(dsn, database, *, reason=None, identity=None):
    reason = reason or "Reviewed the exact 0015 to 0023 migration plan and trust boundary."
    identity = identity or _operator()
    return plan_forward_migrations(
        dsn,
        ".",
        expected_database=database,
        environment="test",
        identity=identity,
        reason=reason,
    )


def _execute(dsn, database, plan, *, reason=None, identity=None, digest=None):
    return execute_forward_migrations(
        dsn,
        ".",
        plan=plan,
        expected_plan_sha256=digest or plan["plan_sha256"],
        expected_database=database,
        environment="test",
        identity=identity or _operator(),
        reason=reason or plan["reason"],
    )


def _redigest(plan):
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    plan["plan_sha256"] = "sha256:" + hashlib.sha256(
        json.dumps(
            unsigned,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    return plan


def _append_duplicate_adoption(dsn, adoption_id):
    with psycopg.connect(dsn) as conn:
        row = conn.execute(
            "SELECT ground_truth_ref,rollback_ref,payload FROM public.artifacts "
            "WHERE artifact_id=%s",
            (adoption_id,),
        ).fetchone()
        duplicate_id = uuid.uuid4()
        duplicate_payload = {**row[2], "adoption_id": str(duplicate_id)}
        conn.execute(
            "INSERT INTO public.artifacts ("
            "artifact_id,artifact_type,source_system,actor,actor_kind,timestamp_start,"
            "timestamp_end,input_refs,output_refs,permissions_label,objective_tag,"
            "ground_truth_ref,eval_score,rollback_ref,cost_usd,corrects_ref,payload"
            ") VALUES ("
            "%s,'gate_decision','cli','test-operator','human',clock_timestamp(),"
            "clock_timestamp(),'{}'::uuid[],'{}'::uuid[],'need-to-know','compliance',"
            "%s,NULL,%s,NULL,NULL,%s)",
            (duplicate_id, row[0], json.dumps(row[1]), json.dumps(duplicate_payload)),
        )
        conn.commit()
    return duplicate_id


def test_forward_attestation_row_order_is_database_collation_independent():
    rows = [
        ("zeta", "-dash"),
        ("Alpha", "underscore_value"),
        ("álpha", "unicode"),
    ]
    assert _canonical_rows(rows) == _canonical_rows(reversed(rows))


@pytest.mark.integration
def test_forward_plan_is_read_only_and_binds_exact_checkpoint_operator_and_reason(
    forward_database,
):
    dsn, database, directory, adoption_id = forward_database
    plan = _plan(dsn, database)
    assert plan["schema_version"] == "migration-forward-plan/v1"
    assert plan["from_filename"] == CHECKPOINT
    assert plan["to_filename"] == "0023_review_unbound_parameter_binding.sql"
    assert [row["filename"] for row in plan["pending_manifest"]] == [
        f"{number:04d}_{name}.sql" for number, name in (
            (16, "verified_review_contracts"),
            (17, "jsonb_contract_helpers"),
            (18, "review_contract_hardening"),
            (19, "review_contract_policy"),
            (20, "review_runtime_corrections"),
            (21, "review_contract_parameter_binding"),
            (22, "review_authority_consolidation"),
            (23, "review_unbound_parameter_binding"),
        )
    ]
    assert plan["operator_authentication"]["actor"] == "test-operator"
    assert plan["prior_audit"]["artifact_id"] == str(adoption_id)
    target = directory.parent / "forward-plan.json"
    assert write_forward_migration_plan(target, plan) == target
    assert write_forward_migration_plan(target, plan) == target
    assert load_forward_migration_plan(target) == plan
    target.write_text("{}\n", encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="already exists with other bytes"):
        write_forward_migration_plan(target, plan)
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM public.schema_migrations").fetchone()[0] == 15
        assert conn.execute(
            "SELECT count(*) FROM public.artifacts WHERE payload->>'schema_version'="
            "'migration-forward-execution/v1'"
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_forward_execute_is_atomic_chained_audited_and_semantically_idempotent(
    forward_database, monkeypatch,
):
    dsn, database, _directory, adoption_id = forward_database
    plan = _plan(dsn, database)
    first = _execute(dsn, database, plan)
    second = _execute(dsn, database, plan)
    assert first["migration_id"] == second["migration_id"]
    assert first["semantic_retry"] is False
    assert second["semantic_retry"] is True
    assert first["applied_filenames"] == [row["filename"] for row in plan["pending_manifest"]]
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM public.schema_migrations").fetchone()[0] == 23
        row = conn.execute(
            "SELECT input_refs,ground_truth_ref,payload FROM public.artifacts "
            "WHERE artifact_id=%s",
            (uuid.UUID(first["migration_id"]),),
        ).fetchone()
        assert list(row[0]) == [adoption_id]
        assert row[1] == plan["plan_sha256"]
        assert row[2]["final_tracker"] == [
            {"filename": item["filename"], "sha256": item["sha256"]}
            for item in plan["repository_manifest"]
        ]
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("SEMISKILL_ENVIRONMENT", "test")
    witness = dashboard_server.migration_witness_signal()
    assert witness["status"] == "verified"
    assert witness["adoption"]["artifact_id"] == str(adoption_id)
    assert witness["forward"]["artifact_id"] == first["migration_id"]
    assert witness["authority_chain"]["forward_artifact_id"] == first["migration_id"]


@pytest.mark.integration
def test_forward_retry_allows_legitimate_policy_data_after_recorded_empty_start(
    forward_database,
):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    first = _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO public.publication_trust_policy "
            "(environment,database_name,policy_version,approve_threshold) "
            "VALUES ('test',%s,'test-policy/v1',0.8)",
            (database,),
        )
        conn.commit()
    second = _execute(dsn, database, plan)
    assert second["migration_id"] == first["migration_id"]
    assert second["semantic_retry"] is True


@pytest.mark.integration
def test_forward_execute_rejects_operator_reason_or_digest_change_without_writes(
    forward_database,
):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    with pytest.raises(MigrationAdoptionRefused, match="operator, reason"):
        _execute(dsn, database, plan, reason=plan["reason"] + " changed")
    with pytest.raises(MigrationAdoptionRefused, match="operator, reason"):
        _execute(dsn, database, plan, identity=_operator(actor="other", subject="uid:1002"))
    with pytest.raises(MigrationAdoptionRefused, match="identity is invalid"):
        _execute(dsn, database, plan, digest="sha256:" + "f" * 64)
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM public.schema_migrations").fetchone()[0] == 15
        assert conn.execute(
            "SELECT count(*) FROM public.artifacts WHERE payload->>'schema_version'="
            "'migration-forward-execution/v1'"
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_forward_post_attestation_failure_rolls_back_all_pending_ddl(
    forward_database, monkeypatch,
):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    monkeypatch.setattr(
        "semiskill.artifacts.migrate._post_migration_attestations",
        lambda _conn: {
            **{key: True for key in plan["post_attestation_contract"]["required_keys"]},
            "required_functions_present": False,
        },
    )
    with pytest.raises(MigrationAdoptionRefused, match="post-migration attestation failed"):
        _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM public.schema_migrations").fetchone()[0] == 15
        assert conn.execute(
            "SELECT to_regclass('public.verified_review_contracts')"
        ).fetchone()[0] is None


@pytest.mark.integration
def test_forward_plan_rejects_tracker_or_precheckpoint_drift(forward_database):
    dsn, database, _directory, _adoption_id = forward_database
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "UPDATE public.schema_migrations SET sha256=%s WHERE filename=%s",
            ("0" * 64, CHECKPOINT),
        )
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match="exact checksummed repository prefix"):
        _plan(dsn, database)


@pytest.mark.integration
def test_forward_plan_rejects_exact_schema_body_drift(forward_database):
    dsn, database, _directory, _adoption_id = forward_database
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "CREATE OR REPLACE FUNCTION public.content_review_ready_v1("
            "content_id uuid,skill_id uuid) "
            "RETURNS boolean LANGUAGE plpgsql STABLE SECURITY DEFINER "
            "SET search_path = pg_catalog, public, pg_temp AS "
            "'BEGIN RETURN false; END'"
        )
        conn.commit()
        coarse = _attest_checkpoint_0015(conn)
        assert all(value is True for value in coarse.values())
    with pytest.raises(MigrationAdoptionRefused, match="schema_inventory_exact"):
        _plan(dsn, database)


@pytest.mark.integration
def test_forward_plan_rejects_ambiguous_prior_adoption_chain(forward_database):
    dsn, database, _directory, adoption_id = forward_database
    _append_duplicate_adoption(dsn, adoption_id)
    with pytest.raises(MigrationAdoptionRefused, match="one exact prior authority artifact"):
        _plan(dsn, database)


@pytest.mark.integration
def test_forward_retry_rejects_post_0023_function_body_drift(forward_database):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "CREATE OR REPLACE FUNCTION public.content_review_ready_v1("
            "content_id uuid,skill_id uuid) RETURNS boolean LANGUAGE sql STABLE "
            "SECURITY DEFINER SET search_path = pg_catalog, public, pg_temp "
            "AS 'SELECT false'"
        )
        conn.commit()
        attestations = _post_migration_attestations(conn)
        assert attestations["schema_inventory_exact"] is False
        assert all(
            value is True for key, value in attestations.items()
            if key not in {"schema_inventory_exact", "projection_and_policy_start_empty"}
        )
    with pytest.raises(MigrationAdoptionRefused, match="no longer passes"):
        _execute(dsn, database, plan)


@pytest.mark.integration
def test_forward_retry_rejects_post_0023_rewrite_rule_drift(forward_database):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "CREATE RULE artifacts_insert_sink AS ON INSERT TO public.artifacts "
            "DO INSTEAD NOTHING"
        )
        conn.commit()
        assert _post_migration_attestations(conn)["schema_inventory_exact"] is False
    with pytest.raises(MigrationAdoptionRefused, match="no longer passes"):
        _execute(dsn, database, plan)


@pytest.mark.integration
def test_forward_retry_revalidates_unique_prior_authority_root(forward_database):
    dsn, database, _directory, adoption_id = forward_database
    plan = _plan(dsn, database)
    _execute(dsn, database, plan)
    _append_duplicate_adoption(dsn, adoption_id)
    with pytest.raises(MigrationAdoptionRefused, match="one exact prior authority artifact"):
        _execute(dsn, database, plan)


@pytest.mark.integration
@pytest.mark.parametrize("drift", ["registry", "corpus"])
def test_forward_retry_rejects_fixed_authority_row_drift(forward_database, drift):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        if drift == "registry":
            conn.execute(
                "UPDATE public.publication_skill_registry SET judge_required=false "
                "WHERE slug=(SELECT slug FROM public.publication_skill_registry "
                "WHERE judge_required ORDER BY slug LIMIT 1)"
            )
        else:
            conn.execute(
                "UPDATE public.injection_corpus SET permissions_label='public' "
                "WHERE probe_id=(SELECT probe_id FROM public.injection_corpus LIMIT 1)"
            )
        conn.commit()
        attestations = _post_migration_attestations(conn)
        expected = (
            "registry_rows_exact" if drift == "registry" else "held_out_baseline_intact"
        )
        assert attestations[expected] is False
    with pytest.raises(MigrationAdoptionRefused, match="no longer passes"):
        _execute(dsn, database, plan)


@pytest.mark.integration
def test_forward_retry_allows_additive_held_out_corpus_evolution(forward_database):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    first = _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO public.injection_corpus(probe_class,pattern,permissions_label) "
            "VALUES('new-class','new-safe-pattern','restricted')"
        )
        conn.commit()
        assert _post_migration_attestations(conn)["held_out_baseline_intact"] is True
    retry = _execute(dsn, database, plan)
    assert retry["migration_id"] == first["migration_id"]
    assert retry["semantic_retry"] is True


@pytest.mark.integration
def test_forward_execute_holds_fixed_authority_rows_through_final_audit(
    forward_database, monkeypatch,
):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    lock_probes = []

    def attest_with_lock_probe(conn):
        with psycopg.connect(dsn) as contender:
            contender.execute("SET LOCAL lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable):
                contender.execute(
                    "UPDATE public.publication_skill_registry SET judge_required=false "
                    "WHERE slug=(SELECT slug FROM public.publication_skill_registry "
                    "ORDER BY slug LIMIT 1)"
                )
            contender.rollback()
        lock_probes.append(True)
        return _post_migration_attestations(conn)

    monkeypatch.setattr(
        "semiskill.artifacts.migrate._post_migration_attestations",
        attest_with_lock_probe,
    )
    _execute(dsn, database, plan)
    assert lock_probes == [True]


@pytest.mark.integration
@pytest.mark.parametrize(
    "drift", [
        "column_acl", "corpus_label", "judge_gold", "registry", "rewrite_rule",
    ],
)
def test_forward_plan_rejects_hidden_checkpoint_state_drift(forward_database, drift):
    dsn, database, _directory, _adoption_id = forward_database
    with psycopg.connect(dsn) as conn:
        if drift == "column_acl":
            conn.execute("GRANT SELECT(actor) ON public.artifacts TO semiskill_app")
        elif drift == "corpus_label":
            conn.execute(
                "UPDATE public.injection_corpus SET permissions_label='public' "
                "WHERE probe_id=(SELECT probe_id FROM public.injection_corpus LIMIT 1)"
            )
        elif drift == "judge_gold":
            conn.execute(
                "INSERT INTO public.judge_gold_set(candidate,human_label) VALUES('probe',1)"
            )
        elif drift == "registry":
            conn.execute(
                "UPDATE public.publication_skill_registry SET judge_required=false "
                "WHERE slug=(SELECT slug FROM public.publication_skill_registry "
                "WHERE judge_required ORDER BY slug LIMIT 1)"
            )
        else:
            conn.execute(
                "CREATE RULE artifacts_insert_sink AS ON INSERT TO public.artifacts "
                "DO INSTEAD NOTHING"
            )
        conn.commit()
    expected = {
        "column_acl": "schema_inventory_exact",
        "corpus_label": "held_out_seed_exact",
        "judge_gold": "judge_gold_set_empty",
        "registry": "registry_rows_exact",
        "rewrite_rule": "schema_inventory_exact",
    }[drift]
    with pytest.raises(MigrationAdoptionRefused, match=expected):
        _plan(dsn, database)


@pytest.mark.integration
@pytest.mark.parametrize("collision_kind", ["deterministic_id", "matching_plan"])
def test_forward_execute_rejects_audit_slot_collision_before_ddl(
    forward_database, collision_kind,
):
    dsn, database, _directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    migration_id = _forward_audit_id(
        plan["database"]["identity_sha256"], plan["plan_sha256"],
    )
    artifact_id = migration_id if collision_kind == "deterministic_id" else uuid.uuid4()
    payload = {} if collision_kind == "deterministic_id" else {
        "schema_version": "migration-forward-execution/v1",
        "plan_sha256": plan["plan_sha256"],
    }
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO public.artifacts ("
            "artifact_id,artifact_type,source_system,actor,actor_kind,timestamp_start,"
            "timestamp_end,input_refs,output_refs,permissions_label,objective_tag,"
            "ground_truth_ref,eval_score,rollback_ref,cost_usd,corrects_ref,payload"
            ") VALUES ("
            "%s,'gate_decision','cli','collision-probe','human',clock_timestamp(),"
            "clock_timestamp(),'{}'::uuid[],'{}'::uuid[],'need-to-know','compliance',"
            "'collision-probe',NULL,%s,NULL,NULL,%s)",
            (
                artifact_id,
                json.dumps({"supported": False, "reason": "collision probe"}),
                json.dumps(payload),
            ),
        )
        conn.commit()
    with pytest.raises(MigrationAdoptionRefused, match="audit slot"):
        _execute(dsn, database, plan)
    with psycopg.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) FROM public.schema_migrations").fetchone()[0] == 15


def test_forward_plan_loader_rejects_duplicate_keys_and_non_finite_numbers(tmp_path):
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        '{"plan_sha256":"sha256:' + "a" * 64
        + '","plan_sha256":"sha256:' + "b" * 64 + '"}',
        encoding="utf-8",
    )
    with pytest.raises(MigrationAdoptionRefused, match="unavailable"):
        load_forward_migration_plan(duplicate)
    non_finite = tmp_path / "non-finite.json"
    non_finite.write_text('{"plan_sha256":NaN}', encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="unavailable"):
        load_forward_migration_plan(non_finite)


@pytest.mark.integration
def test_forward_plan_loader_rejects_invalid_nested_identity(forward_database):
    dsn, database, directory, _adoption_id = forward_database
    plan = _plan(dsn, database)
    plan["prior_audit"]["artifact_id"] = "not-a-uuid"
    _redigest(plan)
    target = directory.parent / "invalid-forward-plan.json"
    target.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="identity is invalid"):
        load_forward_migration_plan(target)

    endpoint_plan = _plan(dsn, database)
    endpoint_plan["from_filename"] = []
    _redigest(endpoint_plan)
    endpoint_target = directory.parent / "invalid-forward-endpoint.json"
    endpoint_target.write_text(json.dumps(endpoint_plan), encoding="utf-8")
    with pytest.raises(MigrationAdoptionRefused, match="identity is invalid"):
        load_forward_migration_plan(endpoint_target)
