from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
import uuid

import psycopg
import pytest

from semiskill.artifacts.schema import ArtifactType
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.gate import make_content_review
from semiskill.authoring.review_collection import (
    ReviewBatchContract,
    ReviewCellContract,
    issue_review_batch_contract,
)
from semiskill.capture.intake import build_skill_version
from tests.support import append_test_content_review, content_checks


SKILL = """---
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


def _contract(
    store,
    skill,
    *,
    batch_id="batch-0022",
    run_id="run-0022",
    reviewer="reviewer:0022",
    lineage_id=None,
):
    return ReviewBatchContract(
        batch_id=batch_id,
        run_id=run_id,
        phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@2",
        attempt=1,
        cells={skill.payload["slug"]: ReviewCellContract(
            skill_version=skill,
            reviewer_identity=reviewer,
            fixer_identity="fixer:0022",
            checks=content_checks(),
            lineage_id=lineage_id or str(uuid.uuid4()),
        )},
        issuer_identity="review-coordinator:test",
        authentication_context=store.review_coordinator_authentication_context(),
    )


def _digest(payload):
    encoded = json.dumps(
        payload, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@pytest.mark.integration
def test_review_coordinator_context_is_bound_to_the_database_login(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    context = store.review_coordinator_authentication_context()
    with psycopg.connect(pg_dsn) as conn:
        session_user = conn.execute("SELECT session_user").fetchone()[0]

    assert context == {
        "provider": "database-role",
        "subject_sha256": "sha256:" + hashlib.sha256(
            session_user.encode("utf-8")
        ).hexdigest(),
    }


@pytest.mark.integration
def test_contract_semantic_retry_returns_one_verified_artifact(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    skill = store.append(build_skill_version(skill_md=SKILL.format(slug="retry"), actor="author"))
    contract = _contract(store, skill)

    first = issue_review_batch_contract(store=store, contract=contract)
    second = issue_review_batch_contract(store=store, contract=contract)

    assert second.contract_artifact == first.contract_artifact
    with psycopg.connect(pg_dsn) as conn:
        artifact_count, projection_count = conn.execute(
            "SELECT "
            "(SELECT count(*) FROM artifacts WHERE artifact_type='gate_decision'),"
            "(SELECT count(*) FROM verified_review_contracts)"
        ).fetchone()
    assert (artifact_count, projection_count) == (1, 1)


@pytest.mark.integration
def test_contract_semantic_retry_rejects_changed_bytes(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    skill = store.append(build_skill_version(skill_md=SKILL.format(slug="collision"), actor="author"))
    contract = _contract(store, skill)
    issue_review_batch_contract(store=store, contract=contract)
    changed_cell = replace(
        contract.cells["collision"], reviewer_identity="reviewer:different",
    )
    conflicting = replace(contract, cells={"collision": changed_cell})

    with pytest.raises(psycopg.errors.CheckViolation, match="different bytes"):
        issue_review_batch_contract(store=store, contract=conflicting)


@pytest.mark.integration
def test_database_rejects_secret_bearing_review_authentication_context(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    skill = store.append(build_skill_version(skill_md=SKILL.format(slug="auth"), actor="author"))
    issued = issue_review_batch_contract(store=store, contract=_contract(store, skill))
    original = issued.contract_artifact
    bad_payload = {
        **original.payload,
        "batch_id": "bad-auth-batch",
        "run_id": "bad-auth-run",
        "authentication_context": {
            **original.payload["authentication_context"],
            "token": "must-never-be-stored",
        },
    }
    forged = replace(
        original,
        artifact_id=uuid.uuid4(),
        payload=bad_payload,
        ground_truth_ref=_digest(bad_payload),
    )

    with pytest.raises(psycopg.errors.CheckViolation, match="authentication_context"):
        store.append_review_contract(forged)
    assert store.get(forged.artifact_id) is None


@pytest.mark.integration
def test_concurrent_different_lineage_roots_have_one_winner(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    skill = store.append(build_skill_version(skill_md=SKILL.format(slug="one-root"), actor="author"))
    first_contract = issue_review_batch_contract(
        store=store,
        contract=_contract(
            store, skill, batch_id="root-batch", run_id="root-a", reviewer="reviewer:root-a",
        ),
    )
    second_contract = issue_review_batch_contract(
        store=store,
        contract=_contract(
            store, skill, batch_id="root-batch", run_id="root-b", reviewer="reviewer:root-b",
        ),
    )
    reviews = [
        make_content_review(
            skill_version=skill,
            phase="review",
            prompt_version="P1-ADVERSARIAL-REVIEW@2",
            run_id=contract.run_id,
            batch_id=contract.batch_id,
            attempt=1,
            reviewer_identity=cell.reviewer_identity,
            fixer_identity=cell.fixer_identity,
            lineage_id=cell.lineage_id,
            contract_artifact=contract.contract_artifact,
            checks=content_checks(),
            findings=[],
        )
        for contract, cell in (
            (first_contract, first_contract.cells["one-root"]),
            (second_contract, second_contract.cells["one-root"]),
        )
    ]

    successes = []
    failures = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.append, review) for review in reviews]
        for future in futures:
            try:
                successes.append(future.result(timeout=10))
            except psycopg.Error as exc:
                failures.append(exc)

    assert len(successes) == len(failures) == 1
    assert isinstance(failures[0], (psycopg.errors.UniqueViolation, psycopg.errors.CheckViolation))
    assert len(store.by_type(ArtifactType.REVIEW)) == 1


@pytest.mark.integration
def test_sql_readiness_requires_p1_then_fresh_p5(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    skill = store.append(build_skill_version(skill_md=SKILL.format(slug="ready"), actor="author"))
    p5 = append_test_content_review(store, skill)
    p1 = store.get(p5.input_refs[2])
    assert p1 is not None

    with psycopg.connect(pg_dsn) as conn:
        p1_ready = conn.execute(
            "SELECT content_review_ready_v1(%s,%s)",
            (p1.artifact_id, skill.artifact_id),
        ).fetchone()[0]
        p5_ready = conn.execute(
            "SELECT content_review_ready_v1(%s,%s)",
            (p5.artifact_id, skill.artifact_id),
        ).fetchone()[0]

    assert p1_ready is False
    assert p5_ready is True
