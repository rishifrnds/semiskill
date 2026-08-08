from __future__ import annotations
import hashlib
import json
import os
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Literal
from typing import Protocol
import psycopg
import psycopg.rows
from psycopg.types.json import Jsonb
from psycopg_pool import ConnectionPool
from semiskill.artifacts.schema import (
    PERMISSIONS_LABELS,
    Artifact,
    ArtifactType,
    SourceSystem,
    ActorKind,
)

_COLS = (
    "artifact_id artifact_type source_system actor actor_kind timestamp_start "
    "timestamp_end input_refs output_refs permissions_label objective_tag "
    "ground_truth_ref eval_score rollback_ref cost_usd corrects_ref payload"
).split()


@dataclass(frozen=True, slots=True)
class PublicationProjectionRow:
    approval_id: uuid.UUID
    skill_version_id: uuid.UUID
    automated_review_id: uuid.UUID
    content_review_id: uuid.UUID
    corrects_ref: uuid.UUID | None
    decision: Literal["approve", "unpublish"]
    slug: str
    version: str
    payload_sha256: str
    permissions_label: str
    environment: Literal["development", "test", "production"]
    policy_version: str
    approve_threshold: Decimal
    chain_sha256: str
    activated_at: datetime
    activated_by: str


@dataclass(frozen=True, slots=True)
class PublicationReconciliationBundle:
    artifacts: tuple[Artifact, ...]
    projections: tuple[PublicationProjectionRow, ...]
    verified_review_contract_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True, slots=True)
class VerifiedPublicationHead:
    approval_id: uuid.UUID
    skill_version_id: uuid.UUID
    automated_review_id: uuid.UUID
    content_review_id: uuid.UUID
    slug: str
    permissions_label: str


@dataclass(frozen=True, slots=True)
class ScopedPublicationBundle:
    """One repeatable-read view containing only one label's active publication chains."""

    heads: tuple[VerifiedPublicationHead, ...]
    artifacts: tuple[Artifact, ...]
    verified_review_contract_ids: tuple[uuid.UUID, ...] = ()


class ArtifactStore(Protocol):
    def append(self, a: Artifact) -> Artifact: ...
    def append_approval(self, a: Artifact) -> Artifact: ...
    def append_review_contract(self, a: Artifact) -> Artifact: ...
    def activate_approval(self, approval_id: uuid.UUID) -> uuid.UUID: ...
    def append_many(self, artifacts: list[Artifact]) -> list[Artifact]: ...
    def get(self, artifact_id: uuid.UUID) -> Artifact | None: ...
    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]: ...
    def by_type(self, t: ArtifactType) -> list[Artifact]: ...
    def verified_publication_ids(self) -> set[uuid.UUID]: ...
    def verified_review_contract_ids(self) -> set[uuid.UUID]: ...
    def review_contract_verified(
        self, contract_id: uuid.UUID, permissions_label: str,
    ) -> bool: ...
    def publication_reconciliation_bundle(self) -> PublicationReconciliationBundle: ...
    def publication_registry_entry(self, slug: str) -> dict | None: ...
    def scoped_publication_bundle(self, permissions_label: str) -> ScopedPublicationBundle: ...


class ReconciledArtifactStore:
    """Immutable read view used so one decision never spans multiple database snapshots."""

    def __init__(self, bundle: PublicationReconciliationBundle):
        if not isinstance(bundle, PublicationReconciliationBundle):
            raise ValueError("publication reconciliation bundle has the wrong type")
        rows = tuple(bundle.artifacts)
        projections = tuple(bundle.projections)
        if any(not isinstance(row, Artifact) for row in rows):
            raise ValueError("publication reconciliation bundle has a malformed artifact row")
        if any(not isinstance(row, PublicationProjectionRow) for row in projections):
            raise ValueError("publication reconciliation bundle has a malformed projection row")
        by_id = {row.artifact_id: row for row in rows}
        projection_ids = {row.approval_id for row in projections}
        if len(by_id) != len(rows):
            raise ValueError("publication reconciliation bundle has duplicate artifact IDs")
        if len(projection_ids) != len(projections):
            raise ValueError("publication reconciliation bundle has duplicate projection IDs")
        self._rows = rows
        self._by_id = by_id
        self._projections = projections
        self._projected_ids = frozenset(projection_ids)
        contract_ids = tuple(bundle.verified_review_contract_ids)
        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError("publication reconciliation bundle has duplicate contract witnesses")
        for contract_id in contract_ids:
            contract = by_id.get(contract_id)
            if contract is None or contract.artifact_type is not ArtifactType.GATE_DECISION:
                raise ValueError("publication reconciliation bundle has an invalid contract witness")
        self._verified_review_contract_ids = frozenset(contract_ids)

    def get(self, artifact_id: uuid.UUID) -> Artifact | None:
        return self._by_id.get(artifact_id)

    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]:
        return [self._by_id[artifact_id] for artifact_id in artifact_ids if artifact_id in self._by_id]

    def by_type(self, t: ArtifactType) -> list[Artifact]:
        return [row for row in self._rows if row.artifact_type is t]

    def verified_publication_ids(self) -> set[uuid.UUID]:
        return set(self._projected_ids)

    def verified_review_contract_ids(self) -> set[uuid.UUID]:
        return set(self._verified_review_contract_ids)

    def review_contract_verified(
        self, contract_id: uuid.UUID, permissions_label: str,
    ) -> bool:
        artifact = self._by_id.get(contract_id)
        return (
            contract_id in self._verified_review_contract_ids
            and artifact is not None
            and artifact.artifact_type is ArtifactType.GATE_DECISION
            and artifact.permissions_label == permissions_label
        )

    def publication_projections(self) -> tuple[PublicationProjectionRow, ...]:
        return self._projections


def _insert_values(a: Artifact) -> tuple:
    return (
        a.artifact_id, a.artifact_type.value, a.source_system.value, a.actor,
        a.actor_kind.value, a.timestamp_start, a.timestamp_end, a.input_refs,
        a.output_refs, a.permissions_label, a.objective_tag, a.ground_truth_ref,
        a.eval_score,
        Jsonb(a.rollback_ref) if a.rollback_ref is not None else None,
        a.cost_usd, a.corrects_ref, Jsonb(a.payload),
    )


def _approval_values(a: Artifact) -> tuple:
    """Arguments for the role-scoped approval append function (artifact_type is hard-coded there)."""
    return (
        a.artifact_id, a.source_system.value, a.actor, a.actor_kind.value,
        a.timestamp_start, a.timestamp_end, a.input_refs, a.output_refs,
        a.permissions_label, a.objective_tag, a.ground_truth_ref, a.eval_score,
        Jsonb(a.rollback_ref) if a.rollback_ref is not None else None,
        a.cost_usd, a.corrects_ref, Jsonb(a.payload),
    )


def _row_to_artifact(row: dict) -> Artifact:
    return Artifact(
        artifact_id=row["artifact_id"],
        artifact_type=ArtifactType(row["artifact_type"]),
        source_system=SourceSystem(row["source_system"]),
        actor=row["actor"],
        actor_kind=ActorKind(row["actor_kind"]),
        timestamp_start=row["timestamp_start"],
        timestamp_end=row["timestamp_end"],
        input_refs=list(row["input_refs"]),
        output_refs=list(row["output_refs"]),
        permissions_label=row["permissions_label"],
        objective_tag=row["objective_tag"],
        ground_truth_ref=row["ground_truth_ref"],
        eval_score=float(row["eval_score"]) if row["eval_score"] is not None else None,
        rollback_ref=row["rollback_ref"],
        cost_usd=float(row["cost_usd"]) if row["cost_usd"] is not None else None,
        corrects_ref=row["corrects_ref"],
        payload=row["payload"],
    )


def _row_to_projection(row: dict) -> PublicationProjectionRow:
    return PublicationProjectionRow(
        approval_id=row["approval_id"],
        skill_version_id=row["skill_version_id"],
        automated_review_id=row["automated_review_id"],
        content_review_id=row["content_review_id"],
        corrects_ref=row["corrects_ref"],
        decision=row["decision"],
        slug=row["slug"],
        version=row["version"],
        payload_sha256=row["payload_sha256"],
        permissions_label=row["permissions_label"],
        environment=row["environment"],
        policy_version=row["policy_version"],
        approve_threshold=row["approve_threshold"],
        chain_sha256=row["chain_sha256"],
        activated_at=row["activated_at"],
        activated_by=row["activated_by"],
    )


class PostgresArtifactStore:
    """Append-only artifact store. INSERT + SELECT only — there is no update path (corrections are
    new rows linked by corrects_ref; the DB trigger blocks UPDATE/DELETE regardless)."""

    def __init__(self, dsn: str, *, approval_dsn: str | None = None,
                 review_contract_dsn: str | None = None, export_dsn: str | None = None):
        self._dsn = dsn
        self._pools: dict[str, ConnectionPool] = {}
        self._pools_lock = threading.Lock()
        configured_approval_dsn = approval_dsn or os.environ.get(
            "SEMISKILL_APPROVAL_DATABASE_URL"
        )
        runtime_info = psycopg.conninfo.conninfo_to_dict(dsn)
        database_name = runtime_info.get("dbname", "")
        if configured_approval_dsn and not database_name.lower().endswith("_test"):
            approval_info = psycopg.conninfo.conninfo_to_dict(configured_approval_dsn)
            if approval_info.get("dbname") != database_name:
                raise ValueError("approval actuator must target the catalog database")
            runtime_user = runtime_info.get("user")
            approval_user = approval_info.get("user")
            if not runtime_user or not approval_user or runtime_user == approval_user:
                raise ValueError("approval actuator requires a distinct database identity")
        self._approval_dsn = configured_approval_dsn or (
            dsn if database_name.lower().endswith("_test") else None
        )
        configured_review_dsn = review_contract_dsn or os.environ.get(
            "SEMISKILL_REVIEW_COORDINATOR_DATABASE_URL"
        )
        if configured_review_dsn and not database_name.lower().endswith("_test"):
            review_info = psycopg.conninfo.conninfo_to_dict(configured_review_dsn)
            if review_info.get("dbname") != database_name:
                raise ValueError("review coordinator must target the catalog database")
            runtime_user = runtime_info.get("user")
            review_user = review_info.get("user")
            if not runtime_user or not review_user or runtime_user == review_user:
                raise ValueError("review coordinator requires a distinct database identity")
            approval_user = (
                psycopg.conninfo.conninfo_to_dict(configured_approval_dsn).get("user")
                if configured_approval_dsn else None
            )
            if approval_user and review_user == approval_user:
                raise ValueError("review coordinator and approval actuator identities must differ")
        self._review_contract_dsn = configured_review_dsn or (
            dsn if database_name.lower().endswith("_test") else None
        )
        configured_export_dsn = export_dsn or os.environ.get("SEMISKILL_EXPORT_DATABASE_URL")
        if configured_export_dsn and not database_name.lower().endswith("_test"):
            export_info = psycopg.conninfo.conninfo_to_dict(configured_export_dsn)
            if export_info.get("dbname") != database_name:
                raise ValueError("export reader must target the catalog database")
            runtime_user = runtime_info.get("user")
            export_user = export_info.get("user")
            if not runtime_user or not export_user or runtime_user == export_user:
                raise ValueError("export reader requires a distinct database identity")
            approval_user = (
                psycopg.conninfo.conninfo_to_dict(configured_approval_dsn).get("user")
                if configured_approval_dsn else None
            )
            if approval_user and export_user == approval_user:
                raise ValueError("export reader and approval actuator identities must differ")
            review_user = (
                psycopg.conninfo.conninfo_to_dict(configured_review_dsn).get("user")
                if configured_review_dsn else None
            )
            if review_user and export_user == review_user:
                raise ValueError("export reader and review coordinator identities must differ")
        self._export_dsn = configured_export_dsn or (
            dsn if database_name.lower().endswith("_test") else None
        )

    def _pool(self, dsn: str) -> ConnectionPool:
        """Return this instance's connection pool for `dsn`, creating it lazily on first use.

        Every public method used to open-and-close a brand new physical connection per call,
        which exhausted Windows ephemeral ports under serial test load (J-010e6, ADR-027). One
        small pool per distinct DSN is kept instead — up to four, since the approval actuator,
        review coordinator and export reader must be distinct database logins and so cannot
        share a pool. `min_size=1` matches actual single-connection-at-a-time usage; `max_size=4`
        gives the threaded dashboard API headroom without recreating the original problem.
        """
        pool = self._pools.get(dsn)
        if pool is not None:
            return pool
        with self._pools_lock:
            pool = self._pools.get(dsn)
            if pool is None:
                pool = ConnectionPool(dsn, min_size=1, max_size=4, open=True)
                self._pools[dsn] = pool
        return pool

    @contextmanager
    def _connection(self, dsn: str, *, row_factory=psycopg.rows.tuple_row):
        """Check out a pooled connection with the exact row_factory the caller needs.

        `pool.connection()` wraps the checked-out connection in the same commit-on-success /
        rollback-on-exception behaviour as bare `psycopg.connect(...)`, so no call site's
        transaction semantics change. `row_factory` is always reset to the default before the
        connection returns to the pool so a `dict_row` setting can never leak into a later
        call site on a reused physical connection.
        """
        with self._pool(dsn).connection() as conn:
            conn.row_factory = row_factory
            try:
                yield conn
            finally:
                conn.row_factory = psycopg.rows.tuple_row

    def close(self) -> None:
        """Close every pooled connection. Safe to call multiple times or never (see __del__)."""
        with self._pools_lock:
            pools, self._pools = self._pools, {}
        for pool in pools.values():
            pool.close()

    def database_identity(self, *, environment: str) -> dict:
        """Return a stable non-secret identity for scoreboard provenance."""
        info = psycopg.conninfo.conninfo_to_dict(self._dsn)
        safe = {
            "engine": "postgresql",
            "environment": environment,
            "database_name": info.get("dbname") or "",
            "host": info.get("host") or "",
            "port": str(info.get("port") or "5432"),
        }
        digest_input = json.dumps(safe, sort_keys=True, separators=(",", ":")).encode("utf-8")
        safe["identity_sha256"] = "sha256:" + hashlib.sha256(digest_input).hexdigest()
        return safe

    def export_database_identity(self, *, environment: str) -> dict:
        """Bind an export scope to the least-privilege reader login without exposing its name."""
        if self._export_dsn is None:
            raise ValueError("export reader database identity is not configured")
        info = psycopg.conninfo.conninfo_to_dict(self._export_dsn)
        with self._connection(self._export_dsn) as conn:
            session_user, roles, has_reader = conn.execute(
                "SELECT session_user, coalesce(array_agg(granted.rolname) "
                "FILTER (WHERE granted.rolname LIKE 'semiskill_export_label_%'), ARRAY[]::name[]) "
                ", pg_has_role(session_user,'semiskill_export_reader','MEMBER') "
                "FROM pg_roles login LEFT JOIN pg_auth_members membership "
                "ON membership.member=login.oid LEFT JOIN pg_roles granted "
                "ON granted.oid=membership.roleid WHERE login.rolname=session_user "
                "GROUP BY session_user"
            ).fetchone()
        role_labels = {
            "semiskill_export_label_public": "public",
            "semiskill_export_label_team": "team",
            "semiskill_export_label_need_to_know": "need-to-know",
            "semiskill_export_label_regulated": "regulated",
        }
        memberships = [role_labels[role] for role in roles if role in role_labels]
        if not has_reader or len(memberships) != 1:
            raise ValueError("export reader must have exactly one permission-label capability")
        safe = {
            "engine": "postgresql",
            "environment": environment,
            "database_name": info.get("dbname") or "",
            "host": info.get("host") or "",
            "port": str(info.get("port") or "5432"),
            "required_role": "semiskill_export_reader",
            "permission_label": memberships[0],
            "session_user_sha256": "sha256:" + hashlib.sha256(
                str(session_user).encode("utf-8")
            ).hexdigest(),
        }
        digest_input = json.dumps(safe, sort_keys=True, separators=(",", ":")).encode("utf-8")
        safe["identity_sha256"] = "sha256:" + hashlib.sha256(digest_input).hexdigest()
        return safe

    def review_coordinator_authentication_context(self) -> dict[str, str]:
        """Return the non-secret identity claim bound to the dedicated coordinator login."""
        if self._review_contract_dsn is None:
            raise RuntimeError("dedicated review coordinator database identity is not configured")
        with self._connection(self._review_contract_dsn) as conn:
            session_user, authorized = conn.execute(
                "SELECT session_user,"
                "pg_has_role(session_user,'semiskill_review_coordinator','MEMBER')"
            ).fetchone()
        if authorized is not True:
            raise RuntimeError("review coordinator database identity lacks its capability")
        return {
            "provider": "database-role",
            "subject_sha256": "sha256:" + hashlib.sha256(
                str(session_user).encode("utf-8")
            ).hexdigest(),
        }

    def append(self, a: Artifact) -> Artifact:
        with self._connection(self._dsn) as conn:
            conn.execute(
                f"INSERT INTO artifacts ({','.join(_COLS)}) VALUES ({','.join(['%s'] * len(_COLS))})",
                _insert_values(a),
            )
            conn.commit()
        return a

    def append_approval(self, a: Artifact) -> Artifact:
        """Atomically append a human decision and activate only publishing corrections.

        Reject decisions remain immutable audit artifacts but cannot affect catalog visibility.
        Approve/unpublish decisions commit only if the role-scoped database actuator accepts the
        exact chain and writes its append-only verified projection in the same transaction.
        """
        if a.artifact_type is not ArtifactType.APPROVAL:
            raise ValueError("append_approval requires an approval artifact")
        if self._approval_dsn is None:
            raise RuntimeError("dedicated approval actuator database identity is not configured")
        with self._connection(self._approval_dsn) as conn:
            appended = conn.execute(
                "SELECT append_verified_approval(" + ",".join(["%s"] * 16) + ")",
                _approval_values(a),
            ).fetchone()
            if appended is None or not isinstance(appended[0], uuid.UUID):
                raise RuntimeError("verified approval actuator did not confirm the append")
            conn.commit()
        if appended[0] == a.artifact_id:
            return a
        existing = self.get(appended[0])
        if existing is None or existing.artifact_type is not ArtifactType.APPROVAL:
            raise RuntimeError("verified approval actuator returned an unknown idempotent decision")
        return existing

    def append_review_contract(self, a: Artifact) -> Artifact:
        """Append a coordinator-issued review contract through its dedicated DB actuator."""
        if a.artifact_type is not ArtifactType.GATE_DECISION:
            raise ValueError("append_review_contract requires a gate_decision artifact")
        if self._review_contract_dsn is None:
            raise RuntimeError("dedicated review coordinator database identity is not configured")
        with self._connection(self._review_contract_dsn) as conn:
            appended = conn.execute(
                "SELECT append_verified_review_contract(" + ",".join(["%s"] * 16) + ")",
                _approval_values(a),
            ).fetchone()
            if appended is None or not isinstance(appended[0], uuid.UUID):
                raise RuntimeError("verified review coordinator did not confirm the append")
            conn.commit()
        if appended[0] == a.artifact_id:
            return a
        existing = self.get(appended[0])
        if existing is None or existing.artifact_type is not ArtifactType.GATE_DECISION:
            raise RuntimeError("verified review coordinator returned an unknown idempotent lease")
        return existing

    def activate_approval(self, approval_id: uuid.UUID) -> uuid.UUID:
        """Activate an imported exact approval through the same role-scoped deterministic gate."""
        if self._approval_dsn is None:
            raise RuntimeError("dedicated approval actuator database identity is not configured")
        with self._connection(self._approval_dsn) as conn:
            row = conn.execute(
                "SELECT activate_verified_publication(%s)", (approval_id,),
            ).fetchone()
            if row is None or row[0] != approval_id:
                raise RuntimeError("verified publication actuator did not confirm the approval")
            conn.commit()
        return approval_id

    def append_many(self, artifacts: list[Artifact]) -> list[Artifact]:
        """Append a collector batch in one transaction or append none of it.

        Validation belongs before this boundary, but database constraints still can reject an
        insert.  The connection context rolls the entire transaction back if any row fails.
        """
        rows = list(artifacts)
        if not rows:
            return []
        statement = (
            f"INSERT INTO artifacts ({','.join(_COLS)}) "
            f"VALUES ({','.join(['%s'] * len(_COLS))})"
        )
        with self._connection(self._dsn) as conn:
            for artifact in rows:
                conn.execute(statement, _insert_values(artifact))
            conn.commit()
        return rows

    def get(self, artifact_id: uuid.UUID) -> Artifact | None:
        with self._connection(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id=%s", (artifact_id,)
            ).fetchone()
        return _row_to_artifact(row) if row else None

    def get_many(self, artifact_ids: list[uuid.UUID]) -> list[Artifact]:
        ids = list(dict.fromkeys(artifact_ids))
        if not ids:
            return []
        with self._connection(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ANY(%s)", (ids,),
            ).fetchall()
        by_id = {row["artifact_id"]: _row_to_artifact(row) for row in rows}
        return [by_id[artifact_id] for artifact_id in ids if artifact_id in by_id]

    def by_type(self, t: ArtifactType) -> list[Artifact]:
        with self._connection(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_type=%s ORDER BY timestamp_start", (t.value,)
            ).fetchall()
        return [_row_to_artifact(r) for r in rows]

    def verified_publication_ids(self) -> set[uuid.UUID]:
        """Return actuator-projected decisions; raw approval JSON never enters this set."""
        with self._connection(self._dsn) as conn:
            rows = conn.execute(
                "SELECT approval_id FROM verified_publication_events"
            ).fetchall()
        return {row[0] for row in rows}

    def verified_review_contract_ids(self) -> set[uuid.UUID]:
        with self._connection(self._dsn) as conn:
            rows = conn.execute(
                "SELECT contract_id FROM verified_review_contract_ids_v1()"
            ).fetchall()
        return {row[0] for row in rows}

    def review_contract_verified(
        self, contract_id: uuid.UUID, permissions_label: str,
    ) -> bool:
        if permissions_label not in PERMISSIONS_LABELS:
            return False
        with self._connection(self._dsn) as conn:
            row = conn.execute(
                "SELECT review_contract_verified_v1(%s,%s)",
                (contract_id, permissions_label),
            ).fetchone()
        return bool(row and row[0] is True)

    def publication_reconciliation_bundle(self) -> PublicationReconciliationBundle:
        """Read evidence and actuator state from one repeatable-read transaction."""
        with self._connection(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_type IN "
                "('skill_version','scan_run','injection_test','review','approval','gate_decision') "
                "ORDER BY timestamp_start, artifact_id"
            ).fetchall()
            projected = conn.execute(
                "SELECT approval_id,skill_version_id,automated_review_id,content_review_id,"
                "corrects_ref,decision,slug,version,payload_sha256,permissions_label,"
                "environment,policy_version,approve_threshold,chain_sha256,activated_at,"
                "activated_by FROM verified_publication_events ORDER BY activated_at,approval_id"
            ).fetchall()
            contract_ids = conn.execute(
                "SELECT contract_id FROM verified_review_contract_ids_v1()"
            ).fetchall()
        return PublicationReconciliationBundle(
            artifacts=tuple(_row_to_artifact(row) for row in rows),
            projections=tuple(_row_to_projection(row) for row in projected),
            verified_review_contract_ids=tuple(row["contract_id"] for row in contract_ids),
        )

    def publication_registry_entry(self, slug: str) -> dict | None:
        """Read the actuator's immutable current-phase publication allowlist."""
        with self._connection(self._dsn, row_factory=psycopg.rows.dict_row) as conn:
            row = conn.execute(
                "SELECT slug,role,level,permissions_label,active,judge_required,registry_sha256 "
                "FROM publication_registry_entry_v1(%s)",
                (slug,),
            ).fetchone()
        return dict(row) if row is not None else None

    def scoped_publication_bundle(self, permissions_label: str) -> ScopedPublicationBundle:
        """Read exactly one label's active heads and frozen dependencies in one snapshot.

        Exporters must not materialize every label and filter afterward: even transiently reading a
        restricted skill body is an ACL failure.  The SECURITY DEFINER head function has already
        proved the active actuator chain; this method narrows it before any artifact payload is
        selected and follows only the immutable IDs named by those heads.
        """
        if permissions_label not in PERMISSIONS_LABELS:
            raise ValueError("unsupported scoped publication permission label")
        if self._export_dsn is None:
            raise ValueError("export reader database identity is not configured")

        with self._connection(self._export_dsn, row_factory=psycopg.rows.dict_row) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
            conn.execute("SET LOCAL ROLE semiskill_export_reader")
            rows = conn.execute(
                "SELECT * FROM export_scoped_publication_bundle_v2(%s)",
                (permissions_label,),
            ).fetchall()
            conn.rollback()

        heads_by_slug: dict[str, VerifiedPublicationHead] = {}
        artifacts: dict[uuid.UUID, Artifact] = {}
        verified_review_contract_ids: set[uuid.UUID] = set()
        for row in rows:
            head = VerifiedPublicationHead(
                approval_id=row["head_approval_id"],
                skill_version_id=row["head_skill_version_id"],
                automated_review_id=row["head_automated_review_id"],
                content_review_id=row["head_content_review_id"],
                slug=row["head_slug"],
                permissions_label=row["head_permissions_label"],
            )
            previous_head = heads_by_slug.setdefault(head.slug, head)
            if previous_head != head:
                raise ValueError("scoped export reader returned conflicting heads")
            artifact = _row_to_artifact({key: row[key] for key in _COLS})
            previous_artifact = artifacts.setdefault(artifact.artifact_id, artifact)
            if previous_artifact != artifact:
                raise ValueError("scoped export reader returned conflicting artifacts")
            if row["artifact_is_verified_review_contract"]:
                if artifact.artifact_type is not ArtifactType.GATE_DECISION:
                    raise ValueError("scoped export reader returned an invalid contract witness")
                verified_review_contract_ids.add(artifact.artifact_id)
        return ScopedPublicationBundle(
            heads=tuple(heads_by_slug[key] for key in sorted(heads_by_slug)),
            artifacts=tuple(artifacts[key] for key in sorted(artifacts, key=str)),
            verified_review_contract_ids=tuple(sorted(verified_review_contract_ids, key=str)),
        )
