from dataclasses import replace
import uuid
import pytest

from semiskill.artifacts.store import (
    PostgresArtifactStore,
    PublicationReconciliationBundle,
    ReconciledArtifactStore,
)
from semiskill.capture.intake import build_skill_version
from semiskill.governance.reconciliation import reconcile_publications
from tests.support import publish_test_skill


SKILL_MD = """---
name: dv-reconcile
description: Reconcile a frozen publication. Use when projection evidence must be audited.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: Reconcile Projection
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-version: 1.0.0
---
# Procedure

1. Compare immutable projection fields with their exact artifacts.
"""


@pytest.fixture
def published_bundle(pg_dsn):
    store = PostgresArtifactStore(pg_dsn)
    skill = store.append(build_skill_version(skill_md=SKILL_MD, actor="author"))
    publish_test_skill(store, skill)
    return store.publication_reconciliation_bundle()


@pytest.mark.integration
def test_typed_bundle_preserves_decimal_and_reconciles_one_active_head(published_bundle):
    row = published_bundle.projections[0]
    result = reconcile_publications(published_bundle, environment="test")
    assert row.approve_threshold.as_tuple().exponent <= 0
    assert list(result.active_by_slug) == ["dv-reconcile"]
    assert result.issues == ()


@pytest.mark.integration
def test_missing_projection_artifact_is_orphaned_and_never_published(published_bundle):
    row = published_bundle.projections[0]
    orphaned = PublicationReconciliationBundle(
        artifacts=tuple(
            artifact for artifact in published_bundle.artifacts
            if artifact.artifact_id != row.automated_review_id
        ),
        projections=published_bundle.projections,
    )
    result = reconcile_publications(orphaned, environment="test")
    assert result.active_by_slug == {}
    assert {issue.code for issue in result.issues} == {"PROJECTION_ORPHAN"}


@pytest.mark.integration
@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: replace(row, slug="dv-drifted"),
        lambda row: replace(row, payload_sha256="0" * 64),
        lambda row: replace(row, permissions_label="regulated"),
        lambda row: replace(row, environment="development"),
        lambda row: replace(row, policy_version="publication-forged"),
        lambda row: replace(row, chain_sha256="0" * 64),
    ],
)
def test_projection_field_or_chain_drift_is_quarantined(published_bundle, mutation):
    drifted = PublicationReconciliationBundle(
        published_bundle.artifacts,
        (mutation(published_bundle.projections[0]),),
    )
    result = reconcile_publications(drifted, environment="test")
    assert result.active_by_slug == {}
    assert any(issue.code == "PROJECTION_DRIFT" for issue in result.issues)


def test_reconciled_store_rejects_duplicate_artifact_and_projection_ids(published_bundle):
    with pytest.raises(ValueError, match="duplicate artifact IDs"):
        ReconciledArtifactStore(PublicationReconciliationBundle(
            (*published_bundle.artifacts, published_bundle.artifacts[0]),
            published_bundle.projections,
        ))
    with pytest.raises(ValueError, match="duplicate projection IDs"):
        ReconciledArtifactStore(PublicationReconciliationBundle(
            published_bundle.artifacts,
            (*published_bundle.projections, published_bundle.projections[0]),
        ))
    with pytest.raises(ValueError, match="malformed projection row"):
        ReconciledArtifactStore(PublicationReconciliationBundle(
            published_bundle.artifacts,
            ({"approval_id": str(published_bundle.projections[0].approval_id)},),
        ))


@pytest.mark.integration
def test_invalid_child_projection_does_not_resurrect_its_parent(published_bundle):
    parent = published_bundle.projections[0]
    parent_approval = next(
        artifact for artifact in published_bundle.artifacts
        if artifact.artifact_id == parent.approval_id
    )
    child_id = uuid.uuid4()
    child_payload = {
        **parent_approval.payload,
        "decision": "unpublish",
        "verdict": "approve",
        "published": False,
        "reason": "Quarantine the exact frozen publication.",
        "quarantined": True,
    }
    child = replace(
        parent_approval,
        artifact_id=child_id,
        timestamp_start=parent.activated_at,
        corrects_ref=parent.approval_id,
        rollback_ref={"action": "reapprove", "approval_id": str(parent.approval_id)},
        payload=child_payload,
    )
    child_row = replace(
        parent,
        approval_id=child_id,
        corrects_ref=parent.approval_id,
        decision="unpublish",
        activated_at=parent.activated_at,
        chain_sha256="0" * 64,
    )
    result = reconcile_publications(PublicationReconciliationBundle(
        (*published_bundle.artifacts, child),
        (*published_bundle.projections, child_row),
    ), environment="test")
    assert result.active_by_slug == {}
    assert any(issue.code == "PROJECTION_DRIFT" for issue in result.issues)
