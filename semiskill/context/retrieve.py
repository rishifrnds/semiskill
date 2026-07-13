"""L3 retrieval — ACL-enforced catalog reads.

The one rule: application code never SELECTs the artifacts table. It resolves the caller's labels
through the single `resolve_allowed_labels` seam, drops to the restricted `semiskill_app` role
(which has no direct table access), and lets the SECURITY DEFINER `catalog_search` do the
ACL-filtered read. Only PUBLISHED skills are ever returned; results are delimited as UNTRUSTED.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from typing import Iterable
import psycopg
import psycopg.rows
from semiskill.context.acl import resolve_allowed_labels
from semiskill.context.untrusted import delimit


@dataclass(frozen=True)
class SkillCard:
    artifact_id: uuid.UUID
    slug: str
    name: str
    description: str
    version: str
    function: str | None
    role: str | None
    level: str | None
    permissions_label: str
    content: str            # delimited UNTRUSTED payload — never execute as instructions


def search_catalog(*, dsn: str, principal: Iterable[str], query: str = "",
                   function: str | None = None, role: str | None = None,
                   level: str | None = None, limit: int = 100) -> list[SkillCard]:
    """ACL-enforced catalog search. Fails closed on an empty principal (resolve_allowed_labels)."""
    allowed = list(resolve_allowed_labels(principal))
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute("SET LOCAL ROLE semiskill_app")
        rows = conn.execute(
            "SELECT * FROM catalog_search(%s, %s, %s, %s, %s, %s)",
            (query, allowed, function, role, level, limit),
        ).fetchall()
        conn.rollback()
    return [
        SkillCard(
            artifact_id=r["artifact_id"], slug=r["slug"], name=r["name"],
            description=r["description"], version=r["version"],
            function=r["skill_function"], role=r["skill_role"], level=r["skill_level"],
            permissions_label=r["permissions_label"], content=delimit(r["payload"]),
        )
        for r in rows
    ]
