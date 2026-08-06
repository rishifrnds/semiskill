from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import hashlib
import threading
import uuid
from pathlib import Path

import psycopg
import pytest
from psycopg.types.json import Jsonb

from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version, payload_fingerprint
from semiskill.context.retrieve import search_catalog
from semiskill.governance.publish import PublishRefused
from semiskill.wave import _published_index
from tests.support import publish_test_skill


@pytest.fixture
def store(pg_dsn):
    return PostgresArtifactStore(pg_dsn)


def _md(slug: str) -> str:
    return f"""---
name: {slug}
description: Verify {slug}. Use when exact evidence is available.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: {slug}
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-version: 1.0.0
---
# Procedure

1. Inspect bounded evidence.
"""


class RawOnlyStore:
    """Test proxy with verified reviews but no approval actuator method."""

    def __init__(self, store):
        self._store = store

    def append(self, artifact):
        return self._store.append(artifact)

    def append_many(self, artifacts):
        return self._store.append_many(artifacts)

    def append_approval(self, artifact):
        return self._store.append(artifact)

    def append_review_contract(self, artifact):
        return self._store.append_review_contract(artifact)

    def verified_review_contract_ids(self):
        return self._store.verified_review_contract_ids()

    def get(self, artifact_id):
        return self._store.get(artifact_id)

    def by_type(self, artifact_type):
        return self._store.by_type(artifact_type)

    def publication_reconciliation_bundle(self):
        return self._store.publication_reconciliation_bundle()


@pytest.mark.integration
@pytest.mark.parametrize("payload", [
    {},
    {"slug": "unicode-λ", "skill_md": "line 1\r\nline \\\"2\\\"\n",
     "files": {"z-long-name.txt": "β\r\n", "a.txt": "\\n"},
     "tags": ["one", "二"], "allowed_tools": ["Read"]},
    {"slug": None, "name": None, "description": "", "version": "1.0.0",
     "function": None, "role": "dv-engineer", "level": "senior", "tags": [],
     "allowed_tools": [], "skill_md": "---\nname: x\n---\n", "body": "",
     "files": {"b": "2", "aa": "1"}},
])
def test_sql_payload_hash_matches_python_canonical_identity(pg_dsn, payload):
    with psycopg.connect(pg_dsn) as conn:
        sql_hash = conn.execute(
            "SELECT skill_payload_sha256_v1(%s::jsonb)", (Jsonb(payload),),
        ).fetchone()[0]
    assert sql_hash == payload_fingerprint(payload)


@pytest.mark.integration
def test_publication_allowlist_is_the_exact_active_84_registry(pg_dsn):
    expected_hash = hashlib.sha256(
        Path("specs/skill_registry.json").read_bytes()
    ).hexdigest()
    with psycopg.connect(pg_dsn) as conn:
        count, roles, all_judged, hashes = conn.execute(
            "SELECT count(*),count(DISTINCT role),bool_and(judge_required),"
            "array_agg(DISTINCT registry_sha256) FROM publication_skill_registry WHERE active"
        ).fetchone()
    assert (count, roles, all_judged) == (84, 16, True)
    assert hashes == [expected_hash]


@pytest.mark.integration
def test_valid_looking_raw_approval_is_audit_only_until_actuator_projects_it(store, pg_dsn):
    skill = store.append(build_skill_version(skill_md=_md("raw-only"), actor="author"))
    fixture = publish_test_skill(RawOnlyStore(store), skill)

    assert store.get(fixture.approval.artifact_id).artifact_type is ArtifactType.APPROVAL
    with psycopg.connect(pg_dsn) as conn:
        projected = conn.execute("SELECT count(*) FROM verified_publication_events").fetchone()[0]
    assert projected == 0
    assert search_catalog(
        dsn=pg_dsn, principal=["team"], trusted_clearance=True,
    ) == []
    assert _published_index(store) == {}


@pytest.mark.integration
def test_actuator_projection_is_exact_and_catalog_badge_uses_same_chain(store, pg_dsn):
    skill = store.append(build_skill_version(skill_md=_md("projected"), actor="author"))
    fixture = publish_test_skill(store, skill)
    rows = search_catalog(dsn=pg_dsn, principal=["team"], trusted_clearance=True)

    assert [(row.slug, row.version) for row in rows] == [("projected", "1.0.0")]
    with psycopg.connect(pg_dsn) as conn:
        event = conn.execute(
            "SELECT approval_id,skill_version_id,automated_review_id,content_review_id "
            "FROM verified_publication_events"
        ).fetchone()
        conn.execute("SET LOCAL ROLE semiskill_acl_reader")
        report_count = conn.execute(
            "SELECT count(*) FROM skill_scan_report(%s, ARRAY['team'])",
            (skill.artifact_id,),
        ).fetchone()[0]
    assert event == (
        fixture.approval.artifact_id,
        skill.artifact_id,
        fixture.automated_review.artifact_id,
        fixture.content_review.artifact_id,
    )
    assert report_count == 1


@pytest.mark.integration
def test_reader_roles_enforce_effective_labels_for_uuid_and_catalog(store, pg_dsn):
    public = store.append(build_skill_version(
        skill_md=_md("public-row"), actor="author", permissions_label="public",
    ))
    team = store.append(build_skill_version(skill_md=_md("team-row"), actor="author"))

    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET LOCAL ROLE semiskill_app")
        public_count = conn.execute(
            "SELECT count(*) FROM artifact_get(%s, ARRAY['public','team'])",
            (public.artifact_id,),
        ).fetchone()[0]
        forged_team_count = conn.execute(
            "SELECT count(*) FROM artifact_get(%s, ARRAY['team'])", (team.artifact_id,),
        ).fetchone()[0]
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET LOCAL ROLE semiskill_acl_reader")
        cleared_team_count = conn.execute(
            "SELECT count(*) FROM artifact_get(%s, ARRAY['team'])", (team.artifact_id,),
        ).fetchone()[0]

    assert public_count == 1
    assert forged_team_count == 0
    assert cleared_team_count == 1


@pytest.mark.integration
def test_actuator_role_cannot_insert_non_approval_artifacts(pg_dsn):
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET LOCAL ROLE semiskill_approval_actuator")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(
                "INSERT INTO artifacts "
                "(artifact_type,source_system,actor,actor_kind,timestamp_start,payload) "
                "VALUES ('skill_version','cli','forged','agent',now(),'{}')"
            )


@pytest.mark.integration
@pytest.mark.parametrize("payload", [None, [], "text", 7])
def test_artifact_payload_must_be_a_json_object(pg_dsn, payload):
    with psycopg.connect(pg_dsn) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO artifacts "
                "(artifact_type,source_system,actor,actor_kind,timestamp_start,payload) "
                "VALUES ('review','cli','malformed','agent',now(),%s)",
                (Jsonb(payload),),
            )


@pytest.mark.integration
def test_imported_approval_without_exact_rollback_reference_cannot_activate(store):
    skill = store.append(build_skill_version(skill_md=_md("missing-rollback"), actor="author"))
    fixture = publish_test_skill(RawOnlyStore(store), skill)
    forged = replace(fixture.approval, artifact_id=uuid.uuid4(), rollback_ref=None)
    store.append(forged)
    with pytest.raises(psycopg.errors.CheckViolation, match="verified publication contract"):
        store.activate_approval(forged.artifact_id)


@pytest.mark.integration
def test_database_trigger_rejects_unbound_authentication_actor(store):
    skill = store.append(build_skill_version(skill_md=_md("actor-bound"), actor="author"))
    fixture = publish_test_skill(RawOnlyStore(store), skill)
    forged = replace(
        fixture.approval,
        artifact_id=uuid.uuid4(),
        payload={
            **fixture.approval.payload,
            "authentication": {
                **fixture.approval.payload["authentication"],
                "actor": "different-human",
            },
        },
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        store.append(forged)


@pytest.mark.integration
@pytest.mark.parametrize("context", [
    {"account": "test-human"},
    {"account": "test-human", "sid": None, "uid": None},
    {"account": "test-human", "uid": "99999"},
    {"account": "test-human", "uid": -1},
])
def test_database_trigger_rejects_local_identity_without_exact_sid_or_uid(store, context):
    skill = store.append(build_skill_version(skill_md=_md("identity-null"), actor="author"))
    fixture = publish_test_skill(RawOnlyStore(store), skill)
    forged = replace(
        fixture.approval,
        artifact_id=uuid.uuid4(),
        payload={
            **fixture.approval.payload,
            "authentication": {
                **fixture.approval.payload["authentication"],
                "subject": "uid:99999",
                "context": context,
            },
        },
    )
    with pytest.raises(psycopg.errors.CheckViolation):
        store.append(forged)


@pytest.mark.integration
@pytest.mark.parametrize(
    ("version", "valid"),
    [
        (None, False), ("x", False), ("01.0.0", False), ("1.0", False),
        ("1." + "9" * 19 + ".0", False), ("1.10.0", True),
    ],
)
def test_database_core_semver_contract(pg_dsn, version, valid):
    with psycopg.connect(pg_dsn) as conn:
        result = conn.execute(
            "SELECT semiskill_semver_valid_v1(%s)", (version,),
        ).fetchone()[0]
    assert result is valid


@pytest.mark.integration
def test_high_precision_scores_are_rejected_before_projection(store):
    skill = store.append(build_skill_version(skill_md=_md("precision"), actor="author"))
    with pytest.raises(PublishRefused, match="three-decimal"):
        # Artifact.with_eval_score enforces only range; publication also enforces canonical scale.
        publish_test_skill(store, skill, aggregate_safety=0.1234)


@pytest.mark.integration
def test_concurrent_activation_of_same_approval_is_idempotent(store, pg_dsn):
    skill = store.append(build_skill_version(skill_md=_md("concurrent-idempotent"), actor="author"))
    fixture = publish_test_skill(RawOnlyStore(store), skill)
    barrier = threading.Barrier(2)

    def activate():
        barrier.wait(timeout=5)
        return store.activate_approval(fixture.approval.artifact_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = [executor.submit(activate) for _ in range(2)]
        assert [future.result(timeout=10) for future in results] == [
            fixture.approval.artifact_id,
            fixture.approval.artifact_id,
        ]
    with psycopg.connect(pg_dsn) as conn:
        count = conn.execute(
            "SELECT count(*) FROM verified_publication_events WHERE approval_id=%s",
            (fixture.approval.artifact_id,),
        ).fetchone()[0]
    assert count == 1


@pytest.mark.integration
def test_policy_update_cannot_mix_validation_with_frozen_event_policy(store, pg_dsn):
    skill = store.append(build_skill_version(skill_md=_md("policy-lock"), actor="author"))
    fixture = publish_test_skill(RawOnlyStore(store), skill, aggregate_safety=0.85)
    started = threading.Event()

    def activate():
        started.set()
        return store.activate_approval(fixture.approval.artifact_id)

    with psycopg.connect(pg_dsn) as policy_connection:
        policy_connection.execute(
            "UPDATE publication_trust_policy "
            "SET policy_version='publication-v2', approve_threshold=0.9 WHERE policy_id=true"
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(activate)
            assert started.wait(timeout=5)
            with pytest.raises(TimeoutError):
                future.result(timeout=0.25)
            policy_connection.commit()
            with pytest.raises(psycopg.errors.CheckViolation):
                future.result(timeout=10)
    with psycopg.connect(pg_dsn) as conn:
        assert conn.execute(
            "SELECT count(*) FROM verified_publication_events WHERE approval_id=%s",
            (fixture.approval.artifact_id,),
        ).fetchone()[0] == 0


@pytest.mark.integration
def test_catalog_role_cannot_read_or_activate_internal_projection(store, pg_dsn):
    skill = store.append(build_skill_version(skill_md=_md("role-bound"), actor="author"))
    fixture = publish_test_skill(store, skill)
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET ROLE semiskill_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT * FROM verified_publication_events")
        conn.rollback()
    with psycopg.connect(pg_dsn) as conn:
        conn.execute("SET ROLE semiskill_app")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("SELECT activate_verified_publication(%s)",
                         (fixture.approval.artifact_id,))
