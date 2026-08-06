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
                   level: str | None = None, limit: int = 100,
                   trusted_clearance: bool = False) -> list[SkillCard]:
    """ACL-enforced catalog search.

    Restricted labels are honored only when the caller explicitly declares that ``principal`` came
    from a trusted authentication/authorization resolver. The database independently enforces that
    distinction through the role used for the query; an ordinary catalog role is always reduced to
    public visibility even if application input contains more privileged labels.
    """
    allowed = list(resolve_allowed_labels(principal))
    reader_role = "semiskill_acl_reader" if trusted_clearance else "semiskill_app"
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(f"SET LOCAL ROLE {reader_role}")
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


def get_skill_detail(*, dsn: str, skill_version_id, principal: Iterable[str],
                     trusted_clearance: bool = False) -> dict | None:
    """Detail for a PUBLISHED, visible skill: its card fields + the verification/scan report (the
    UI badge). Returns None if the skill is not published or not visible to the caller."""
    principal = list(principal)
    card = next((c for c in search_catalog(
        dsn=dsn, principal=principal, limit=1000, trusted_clearance=trusted_clearance,
    )
                 if str(c.artifact_id) == str(skill_version_id)), None)
    if card is None:
        return None
    allowed = list(resolve_allowed_labels(principal))
    reader_role = "semiskill_acl_reader" if trusted_clearance else "semiskill_app"
    with psycopg.connect(dsn, row_factory=psycopg.rows.dict_row) as conn:
        conn.execute(f"SET LOCAL ROLE {reader_role}")
        row = conn.execute("SELECT * FROM skill_scan_report(%s, %s)",
                            (skill_version_id, allowed)).fetchone()
        conn.rollback()
    return {
        "artifact_id": str(card.artifact_id), "slug": card.slug, "name": card.name,
        "description": card.description, "version": card.version, "function": card.function,
        "role": card.role, "level": card.level, "permissions_label": card.permissions_label,
        "install": {"method": "file-placement",
                    "path": f".cursor/skills/{card.slug}/SKILL.md",
                    "invoke": f"/{card.slug}"},
        "verification": ({"verdict": row["verdict"],
                          "aggregate_safety": float(row["aggregate_safety"]) if row["aggregate_safety"] is not None else None,
                          "stages": row["stages"]} if row else None),
    }
