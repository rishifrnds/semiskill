import json
import uuid

import pytest

from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.authoring.review_collection import (
    BatchRejected,
    ReviewBatchContract,
    ReviewCellContract,
    issue_review_batch_contract,
    review_batch_contract_document,
)
from semiskill.capture.intake import build_skill_version
from tools.collect_wave import load_contract, load_results


SKILL = """---
name: dv-a
description: Check dv-a. Use when it needs review.
allowed-tools: Read Grep Glob
metadata:
  semiskill-title: dv-a
  semiskill-function: design-verification
  semiskill-role: dv-engineer
  semiskill-level: senior
  semiskill-version: 1.0.0
---
# Procedure

1. Inspect bounded evidence and record the result.
"""


class Store:
    def __init__(self, rows=()):
        self.rows = list(rows)
        self.review_contract_ids = set()

    def append(self, artifact):
        self.rows.append(artifact)
        return artifact

    def append_review_contract(self, artifact):
        self.rows.append(artifact)
        self.review_contract_ids.add(artifact.artifact_id)
        return artifact

    def verified_review_contract_ids(self):
        return set(self.review_contract_ids)

    def get(self, artifact_id):
        return next((row for row in self.rows if row.artifact_id == artifact_id), None)


def _checks():
    return {
        "strict_lint": {"passed": True, "evidence": "lint:pass"},
        "consistency": {"passed": True, "evidence": "consistency:pass"},
        "source_hash": {"passed": True, "evidence": "hash:pass"},
        "artifact_reconciliation": {"passed": True, "evidence": "refs:pass"},
    }


def _issued_contract(store):
    skill = build_skill_version(skill_md=SKILL, actor="author")
    store.rows.append(skill)
    contract = ReviewBatchContract(
        batch_id="batch-1",
        run_id="run-1",
        phase="review",
        prompt_version="P1-ADVERSARIAL-REVIEW@3",
        attempt=1,
        cells={"dv-a": ReviewCellContract(
            skill_version=skill,
            reviewer_identity="reviewer:context-1",
            fixer_identity="fixer:context-1",
            checks=_checks(),
            lineage_id=str(uuid.uuid4()),
        )},
        issuer_identity="review-coordinator:test",
        authentication_context={
            "provider": "test", "subject_sha256": "sha256:" + "a" * 64,
        },
    )
    return issue_review_batch_contract(store=store, contract=contract)


def test_load_results_rejects_malformed_jsonl_instead_of_skipping_it(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text('{"slug":"dv-a"}\nnot-json\n', encoding="utf-8")
    with pytest.raises(BatchRejected, match="malformed JSONL"):
        load_results(path)


def test_load_results_accepts_only_an_array_of_objects(tmp_path):
    path = tmp_path / "results.json"
    path.write_text(json.dumps({"results": [{"slug": "dv-a"}]}), encoding="utf-8")
    assert load_results(path) == [{"slug": "dv-a"}]

    path.write_text(json.dumps({"results": [True]}), encoding="utf-8")
    with pytest.raises(BatchRejected, match="array of result objects"):
        load_results(path)


def test_load_contract_requires_exact_stored_immutable_lease(tmp_path):
    store = Store()
    issued = _issued_contract(store)
    path = tmp_path / "contract.json"
    document = review_batch_contract_document(issued)
    path.write_text(json.dumps(document), encoding="utf-8")

    loaded = load_contract(store, path)
    assert loaded.contract_artifact == issued.contract_artifact
    assert loaded.cells["dv-a"].checks == _checks()

    document["cells"][0]["checks"]["source_hash"]["passed"] = False
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(BatchRejected, match="does not match the stored immutable lease"):
        load_contract(store, path)


def test_load_contract_rejects_unsigned_or_oversized_contract(tmp_path):
    store = Store()
    issued = _issued_contract(store)
    document = review_batch_contract_document(issued)
    document["contract_artifact_id"] = str(uuid.uuid4())
    path = tmp_path / "contract.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(BatchRejected, match="artifact was not found"):
        load_contract(store, path)

    cells = [dict(document["cells"][0], slug=f"dv-{index}") for index in range(11)]
    oversized_payload = {
        **issued.contract_artifact.payload,
        "cells": cells,
    }
    oversized = Artifact.new(
        artifact_type=ArtifactType.GATE_DECISION,
        source_system=SourceSystem.CLI,
        actor="review-coordinator:test",
        actor_kind=ActorKind.SERVICE_ACCOUNT,
        payload=oversized_payload,
    )
    store.rows.append(oversized)
    path.write_text(json.dumps({
        "contract_artifact_id": str(oversized.artifact_id),
        **oversized_payload,
    }), encoding="utf-8")
    with pytest.raises(BatchRejected, match="exactly one skill"):
        load_contract(store, path)
