"""L3 read API — a thin, dependency-free JSON HTTP layer the catalog UI reads.

Read-only by design: it exposes the ACL-enforced catalog read model (search, detail with the
verification/scan report, review-queue, lineage, reuse) but NEVER writes the catalog — publishing
stays behind the human-gated actuator (ADR-002). Restricted labels come only from an injected,
authenticated principal resolver; request headers never assert clearance by themselves.
"""
from __future__ import annotations
import json
import os
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
from urllib.parse import urlparse, parse_qs
from semiskill.config import Config
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.context.retrieve import search_catalog, get_skill_detail
from semiskill.context.provenance import get_lineage, get_reuse
from semiskill.context.acl import (
    PrincipalResolutionUnavailable,
    PrincipalUnauthenticated,
    ResolvedPrincipal,
)
from semiskill.intelligence.controller import review_queue

_DEFAULT_PRINCIPAL = ["public"]


class InvalidArtifactId(ValueError):
    pass


def _artifact_id(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidArtifactId("artifact ID must be a UUID") from exc


def _install(slug: str) -> dict:
    """How a skill is actually installed (ADR-010): by placing a folder. There is no install command
    — Cursor and the other Agent Skills runtimes discover skills by walking a skills directory."""
    return {"method": "file-placement",
            "path": f".cursor/skills/{slug}/SKILL.md",
            "invoke": f"/{slug}",
            "instruction": (f"Put the pack folder in ~/.cursor/skills/ (or your project's "
                            f".cursor/skills/), reload, then type /{slug}.")}


def _card(c) -> dict:
    return {"artifact_id": str(c.artifact_id), "slug": c.slug, "name": c.name,
            "description": c.description, "version": c.version, "function": c.function,
            "role": c.role, "level": c.level, "install": _install(c.slug)}


def make_handler(
    dsn: str,
    *,
    scoreboard_provider: Callable[[], dict] | None = None,
    progress_provider: Callable[[str], dict] | None = None,
    operator_authorizer: Callable[[object], bool] | None = None,
    principal_resolver: Callable[[object], ResolvedPrincipal] | None = None,
    clearance_dsn: str | None = None,
    snapshot_environment: str | None = None,
):
    from semiskill.authoring.snapshot import (
        SnapshotUnavailable,
        load_progress,
        load_scoreboard_snapshot,
        validate_progress_snapshot,
        validate_scoreboard_snapshot,
    )

    runtime_environment = snapshot_environment or os.environ.get(
        "SEMISKILL_ENVIRONMENT", "development",
    )
    if runtime_environment == "production" and (
        principal_resolver is None or not clearance_dsn
    ):
        raise RuntimeError(
            "production catalog API requires an Entra principal resolver and clearance database"
        )

    def canonical_scoreboard() -> dict:
        if scoreboard_provider is not None:
            snapshot = validate_scoreboard_snapshot(scoreboard_provider())
        else:
            path = os.environ.get("SEMISKILL_SCOREBOARD_SNAPSHOT")
            if not path:
                raise SnapshotUnavailable("scoreboard snapshot path is not configured")
            snapshot = load_scoreboard_snapshot(path)
        if snapshot["sources"]["database"].get("environment") != runtime_environment:
            raise SnapshotUnavailable("scoreboard runtime environment does not match")
        return snapshot

    def current_progress(snapshot_id: str) -> dict:
        if progress_provider is not None:
            return validate_progress_snapshot(progress_provider(snapshot_id), snapshot_id)
        path = os.environ.get("SEMISKILL_PROGRESS_SNAPSHOT")
        if not path:
            raise SnapshotUnavailable("progress snapshot path is not configured")
        return load_progress(path, snapshot_id)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the test output quiet
            pass

        def _send(self, code: int, body: dict, *, no_store: bool = False):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            if no_store:
                self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def _snapshot_unavailable(self):
            return self._send(503, {
                "error": {
                    "code": "SNAPSHOT_UNAVAILABLE",
                    "message": "authoritative scoreboard snapshot unavailable",
                },
            }, no_store=True)

        def _operator_refused(self):
            return self._send(403, {
                "error": {
                    "code": "OPERATOR_AUTH_REQUIRED",
                    "message": "verified catalog-operator identity required",
                },
            }, no_store=True)

        def _operator_allowed(self) -> bool:
            if operator_authorizer is None:
                return False
            try:
                return operator_authorizer(self.headers) is True
            except Exception:
                return False

        def _principal(self) -> tuple[list[str], bool, str]:
            if principal_resolver is None:
                return list(_DEFAULT_PRINCIPAL), False, dsn
            if not clearance_dsn:
                raise PrincipalResolutionUnavailable(
                    "authenticated catalog reader is not configured"
                )
            try:
                resolved = principal_resolver(self.headers)
                if not isinstance(resolved, ResolvedPrincipal):
                    raise PrincipalResolutionUnavailable(
                        "principal resolver returned an invalid result"
                    )
                if runtime_environment == "production" and resolved.provider != "entra_oidc":
                    raise PrincipalUnauthenticated(
                        "production catalog requires an Entra identity"
                    )
                return list(resolved.labels), True, clearance_dsn
            except PrincipalUnauthenticated:
                raise
            except PrincipalResolutionUnavailable:
                raise
            except Exception as exc:
                raise PrincipalResolutionUnavailable(
                    "authenticated principal could not be resolved"
                ) from exc

        def do_GET(self):
            u = urlparse(self.path)
            parts = [p for p in u.path.split("/") if p]
            q = parse_qs(u.query)
            try:
                if u.path == "/health":
                    return self._send(200, {"status": "ok"})
                if u.path == "/scoreboard":
                    if not self._operator_allowed():
                        return self._operator_refused()
                    try:
                        return self._send(200, canonical_scoreboard(), no_store=True)
                    except Exception:  # provider details must not cross the API boundary
                        return self._snapshot_unavailable()
                if u.path == "/progress":
                    if not self._operator_allowed():
                        return self._operator_refused()
                    try:
                        snapshot = canonical_scoreboard()
                        return self._send(
                            200, current_progress(snapshot["snapshot_id"]), no_store=True,
                        )
                    except Exception:  # provider details must not cross the API boundary
                        return self._snapshot_unavailable()
                if u.path == "/queue":
                    if not self._operator_allowed():
                        return self._operator_refused()
                    store = PostgresArtifactStore(dsn)
                    return self._send(200, {"queue": [
                        {"skill_version_id": str(i.skill_version_id), "slug": i.slug,
                         "verdict": i.verdict, "aggregate_safety": i.aggregate_safety}
                        for i in review_queue(store)]})
                principal_route = (
                    u.path == "/catalog"
                    or (len(parts) == 2 and parts[0] in {"skill", "lineage", "reuse"})
                )
                if not principal_route:
                    return self._send(404, {"error": "unknown route"})
                principal, trusted_clearance, catalog_dsn = self._principal()
                if u.path == "/catalog":
                    cards = search_catalog(dsn=catalog_dsn, principal=principal,
                                           query=q.get("q", [""])[0],
                                           function=q.get("function", [None])[0],
                                           role=q.get("role", [None])[0],
                                           level=q.get("level", [None])[0],
                                           trusted_clearance=trusted_clearance)
                    return self._send(200, {"results": [_card(c) for c in cards]})
                if len(parts) == 2 and parts[0] == "skill":
                    d = get_skill_detail(
                        dsn=catalog_dsn, skill_version_id=_artifact_id(parts[1]),
                        principal=principal,
                        trusted_clearance=trusted_clearance,
                    )
                    return self._send(200 if d else 404, d or {"error": "not found or not visible"})
                if len(parts) == 2 and parts[0] == "lineage":
                    r = get_lineage(
                        dsn=catalog_dsn, start_artifact_id=_artifact_id(parts[1]),
                        principal=principal,
                        trusted_clearance=trusted_clearance,
                    )
                    return self._send(200, {"nodes": [{"artifact_id": str(n.artifact_id),
                                                       "type": n.artifact_type.value, "depth": n.depth}
                                                      for n in r.nodes],
                                            "edges": [[str(a), str(b)] for a, b in r.edges]})
                if len(parts) == 2 and parts[0] == "reuse":
                    recs = get_reuse(
                        dsn=catalog_dsn, skill_version_id=_artifact_id(parts[1]),
                        principal=principal,
                        trusted_clearance=trusted_clearance,
                    )
                    return self._send(200, {"reuse": [{"actor": x.actor, "method": x.method}
                                                      for x in recs]})
            except PrincipalUnauthenticated:
                return self._send(401, {"error": {
                    "code": "AUTHENTICATION_REQUIRED",
                    "message": "authenticated catalog identity required",
                }}, no_store=True)
            except PrincipalResolutionUnavailable:
                return self._send(503, {"error": {
                    "code": "IDENTITY_UNAVAILABLE",
                    "message": "catalog identity service unavailable",
                }}, no_store=True)
            except InvalidArtifactId:
                return self._send(400, {"error": {
                    "code": "INVALID_ARTIFACT_ID",
                    "message": "artifact ID must be a UUID",
                }}, no_store=True)
            except ValueError:
                return self._send(403, {"error": {
                    "code": "NO_CLEARANCE",
                    "message": "catalog permission clearance is unavailable",
                }}, no_store=True)
            except Exception:  # provider details must not cross the API boundary
                return self._send(500, {"error": {
                    "code": "CATALOG_READ_FAILED",
                    "message": "catalog read failed",
                }}, no_store=True)

    return Handler


def serve(
    host: str = "127.0.0.1",
    port: int = 8787,
    dsn: str | None = None,
    *,
    scoreboard_provider: Callable[[], dict] | None = None,
    progress_provider: Callable[[str], dict] | None = None,
    operator_authorizer: Callable[[object], bool] | None = None,
    principal_resolver: Callable[[object], ResolvedPrincipal] | None = None,
    clearance_dsn: str | None = None,
    snapshot_environment: str | None = None,
) -> ThreadingHTTPServer:
    dsn = dsn or Config.from_env().database_url
    return ThreadingHTTPServer((host, port), make_handler(
        dsn, scoreboard_provider=scoreboard_provider, progress_provider=progress_provider,
        operator_authorizer=operator_authorizer, principal_resolver=principal_resolver,
        clearance_dsn=clearance_dsn, snapshot_environment=snapshot_environment,
    ))


def main():
    httpd = serve()
    h, p = httpd.server_address
    print(f"SemiSkill read API on http://{h}:{p}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
