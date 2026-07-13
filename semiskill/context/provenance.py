"""L3 provenance — a skill's verification trail (lineage) and its reuse graph.

Both run under the restricted `semiskill_app` role and resolve the caller's labels through the single
ACL seam. Lineage is ACL-pruned at each hop (an unauthorized node halts that branch — fail closed,
never leak existence); the reuse graph is gated on the skill itself being visible. Node content is
delimited as UNTRUSTED. Mirrors aios/context/provenance.py.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Iterable
import psycopg
import psycopg.rows
from semiskill.artifacts.schema import ArtifactType
from semiskill.context.acl import resolve_allowed_labels
from semiskill.context.untrusted import delimit


@dataclass(frozen=True)
class ProvenanceNode:
    artifact_id: uuid.UUID
    artifact_type: ArtifactType
    content: str                 # delimited UNTRUSTED data
    permissions_label: str
    depth: int | None = None


@dataclass(frozen=True)
class ProvenanceResult:
    nodes: list[ProvenanceNode]
    edges: list[tuple[uuid.UUID, uuid.UUID]]


@dataclass(frozen=True)
class ReuseRecord:
    artifact_id: uuid.UUID
    actor: str
    method: str


def get_lineage(*, dsn: str, start_artifact_id, principal: Iterable[str],
                max_depth: int = 10) -> ProvenanceResult:
    """Ancestry via input_refs (e.g. approval → review → scan_runs → skill_version), ACL-pruned at
    each hop. Returns empty unless the start node itself is visible to the caller."""
    allowed = list(resolve_allowed_labels(principal))
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("SET LOCAL ROLE semiskill_app")
        rows = conn.execute("SELECT * FROM lineage(%s, %s, %s)",
                            (start_artifact_id, allowed, max_depth)).fetchall()
        conn.rollback()
    best: dict = {}
    raw_edges: list[tuple] = []
    for r in rows:
        aid = r["artifact_id"]
        if aid not in best or r["depth"] < best[aid]["depth"]:
            best[aid] = r
        if r["parent_id"] is not None:
            raw_edges.append((r["parent_id"], aid))
    nodes = [ProvenanceNode(artifact_id=r["artifact_id"],
                            artifact_type=ArtifactType(r["artifact_type"]),
                            content=delimit(r["payload"]), permissions_label=r["permissions_label"],
                            depth=r["depth"]) for r in best.values()]
    edges = sorted({(p, c) for (p, c) in raw_edges if p in best and c in best}, key=str)
    return ProvenanceResult(nodes=nodes, edges=edges)


def get_reuse(*, dsn: str, skill_version_id, principal: Iterable[str]) -> list[ReuseRecord]:
    """Who reused a skill (the reuse graph), ACL-filtered and gated on the skill being visible."""
    allowed = list(resolve_allowed_labels(principal))
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("SET LOCAL ROLE semiskill_app")
        rows = conn.execute("SELECT * FROM reuse_events_for_skill(%s, %s)",
                            (skill_version_id, allowed)).fetchall()
        conn.rollback()
    return [ReuseRecord(artifact_id=r["artifact_id"], actor=r["actor"], method=r["method"])
            for r in rows]
