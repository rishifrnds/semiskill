"""L3 read API — a thin, dependency-free JSON HTTP layer the catalog UI reads.

Read-only by design: it exposes the ACL-enforced catalog read model (search, detail with the
verification/scan report, review-queue, lineage, reuse) but NEVER writes the catalog — publishing
stays behind the human-gated actuator (ADR-002). The caller's permission labels come from the
X-Principal-Labels header (comma-separated); absent ⇒ 'public' only.
"""
from __future__ import annotations
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from semiskill.config import Config
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.context.retrieve import search_catalog, get_skill_detail
from semiskill.context.provenance import get_lineage, get_reuse
from semiskill.intelligence.controller import review_queue

_DEFAULT_PRINCIPAL = ["public"]


def _principal(headers) -> list[str]:
    raw = headers.get("X-Principal-Labels")
    if not raw:
        return list(_DEFAULT_PRINCIPAL)
    return [x.strip() for x in raw.split(",") if x.strip()] or list(_DEFAULT_PRINCIPAL)


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


def make_handler(dsn: str):
    store = PostgresArtifactStore(dsn)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the test output quiet
            pass

        def _send(self, code: int, body: dict):
            data = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            parts = [p for p in u.path.split("/") if p]
            q = parse_qs(u.query)
            principal = _principal(self.headers)
            try:
                if u.path == "/health":
                    return self._send(200, {"status": "ok"})
                if u.path == "/catalog":
                    cards = search_catalog(dsn=dsn, principal=principal, query=q.get("q", [""])[0],
                                           function=q.get("function", [None])[0],
                                           role=q.get("role", [None])[0],
                                           level=q.get("level", [None])[0])
                    return self._send(200, {"results": [_card(c) for c in cards]})
                if len(parts) == 2 and parts[0] == "skill":
                    d = get_skill_detail(dsn=dsn, skill_version_id=parts[1], principal=principal)
                    return self._send(200 if d else 404, d or {"error": "not found or not visible"})
                if u.path == "/queue":
                    return self._send(200, {"queue": [
                        {"skill_version_id": str(i.skill_version_id), "slug": i.slug,
                         "verdict": i.verdict, "aggregate_safety": i.aggregate_safety}
                        for i in review_queue(store)]})
                if len(parts) == 2 and parts[0] == "lineage":
                    r = get_lineage(dsn=dsn, start_artifact_id=parts[1], principal=principal)
                    return self._send(200, {"nodes": [{"artifact_id": str(n.artifact_id),
                                                       "type": n.artifact_type.value, "depth": n.depth}
                                                      for n in r.nodes],
                                            "edges": [[str(a), str(b)] for a, b in r.edges]})
                if len(parts) == 2 and parts[0] == "reuse":
                    recs = get_reuse(dsn=dsn, skill_version_id=parts[1], principal=principal)
                    return self._send(200, {"reuse": [{"actor": x.actor, "method": x.method}
                                                      for x in recs]})
                return self._send(404, {"error": "unknown route"})
            except ValueError as e:                       # e.g. empty principal fails closed
                return self._send(403, {"error": str(e)})
            except Exception as e:                        # noqa: BLE001
                return self._send(500, {"error": str(e)})

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8787, dsn: str | None = None) -> ThreadingHTTPServer:
    dsn = dsn or Config.from_env().database_url
    return ThreadingHTTPServer((host, port), make_handler(dsn))


def main():
    httpd = serve()
    h, p = httpd.server_address
    print(f"SemiSkill read API on http://{h}:{p}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
