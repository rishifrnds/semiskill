import json
import hashlib
import threading
import urllib.error
import urllib.request
from contextlib import contextmanager
import pytest
from pathlib import Path
from semiskill.api import serve
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
from semiskill.authoring.snapshot import SnapshotUnavailable, finalize_scoreboard
from tests.support import publish_test_skill

MIG = Path("semiskill/artifacts/migrations")


def _publish(store, slug, label="team"):
    sv = store.append(build_skill_version(
        skill_md=f"---\nname: {slug}\nslug: {slug}\nfunction: dv\n---\nbody", actor="a",
        permissions_label=label))
    publish_test_skill(store, sv, aggregate_safety=0.95)
    return sv


@pytest.fixture
def server(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    store = PostgresArtifactStore(pg_dsn)
    _publish(store, "dv/pub-team", "team")
    _publish(store, "dv/pub-reg", "regulated")
    store.append(build_skill_version(skill_md="---\nname: D\nslug: dv/draft\n---\nb", actor="a"))  # unpublished
    httpd = serve(port=0, dsn=pg_dsn)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", store
    httpd.shutdown()


def _get(base, path, labels="team"):
    req = urllib.request.Request(base + path, headers={"X-Principal-Labels": labels})
    try:
        r = urllib.request.urlopen(req, timeout=5)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _get_with_headers(base, path):
    try:
        response = urllib.request.urlopen(base + path, timeout=5)
        return response.status, json.loads(response.read()), response.headers
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read()), error.headers


def _snapshot():
    from tests.authoring.test_snapshot import _body
    return finalize_scoreboard(_body(), generated_at="2026-08-06T00:00:00Z")


@contextmanager
def _snapshot_server(
    scoreboard_provider, progress_provider=None, *, authorized=True,
    snapshot_environment="test",
):
    httpd = serve(
        port=0, dsn="postgresql://unreachable:secret@127.0.0.1:1/never_used",
        scoreboard_provider=scoreboard_provider, progress_provider=progress_provider,
        operator_authorizer=(lambda _headers: True) if authorized else None,
        snapshot_environment=snapshot_environment,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
    finally:
        httpd.shutdown()


@pytest.mark.integration
def test_health(server):
    base, _ = server
    assert _get(base, "/health")[1]["status"] == "ok"


@pytest.mark.integration
def test_catalog_is_acl_filtered(server):
    base, _ = server
    team = {c["slug"] for c in _get(base, "/catalog", labels="team")[1]["results"]}
    assert team == {"dv/pub-team"}                                   # regulated + draft hidden
    both = {c["slug"] for c in _get(base, "/catalog", labels="team,regulated")[1]["results"]}
    assert both == {"dv/pub-team", "dv/pub-reg"}


@pytest.mark.integration
def test_catalog_install_command_present(server):
    base, _ = server
    card = _get(base, "/catalog", labels="team")[1]["results"][0]
    # ADR-010: installation is file placement; there is no install command to name.
    assert card["install"]["method"] == "file-placement"
    assert card["install"]["path"] == ".cursor/skills/dv/pub-team/SKILL.md"
    assert card["install"]["invoke"] == "/dv/pub-team"


@pytest.mark.integration
def test_skill_detail_has_verification(server):
    base, store = server
    sv_id = next(c["artifact_id"] for c in _get(base, "/catalog", labels="team")[1]["results"])
    code, d = _get(base, f"/skill/{sv_id}", labels="team")
    assert code == 200
    assert d["verification"]["verdict"] == "approve"
    assert d["install"]["method"] == "file-placement"
    assert d["install"]["path"] == ".cursor/skills/dv/pub-team/SKILL.md"


@pytest.mark.integration
def test_unpublished_skill_detail_404(server):
    base, store = server
    from semiskill.artifacts.schema import ArtifactType as AT
    draft = [a for a in store.by_type(AT.SKILL_VERSION) if a.payload.get("slug") == "dv/draft"][0]
    code, _ = _get(base, f"/skill/{draft.artifact_id}", labels="team")
    assert code == 404


def test_scoreboard_returns_validated_injected_document_without_database():
    snapshot = _snapshot()
    with _snapshot_server(lambda: snapshot) as base:
        code, body, headers = _get_with_headers(base, "/scoreboard")
    assert code == 200 and body == snapshot
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path", ["/scoreboard", "/progress"])
def test_snapshot_endpoints_require_verified_operator_authorizer(path):
    snapshot = _snapshot()
    with _snapshot_server(lambda: snapshot, authorized=False) as base:
        code, body, headers = _get_with_headers(base, path)
    assert code == 403
    assert body["error"]["code"] == "OPERATOR_AUTH_REQUIRED"
    assert headers["Cache-Control"] == "no-store"


def test_progress_is_bound_to_the_current_scoreboard_snapshot():
    snapshot = _snapshot()
    received = []

    def progress(snapshot_id):
        received.append(snapshot_id)
        return {
            "schema_version": "semiskill.progress/v1",
            "scoreboard_snapshot_id": snapshot_id,
            "generated_at": "2026-08-06T00:00:01Z",
            "workers": [],
        }

    with _snapshot_server(lambda: snapshot, progress) as base:
        code, body, headers = _get_with_headers(base, "/progress")
    assert code == 200 and body["scoreboard_snapshot_id"] == snapshot["snapshot_id"]
    assert received == [snapshot["snapshot_id"]]
    assert headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path", ["/scoreboard", "/progress"])
def test_snapshot_endpoints_fail_closed_without_leaking_or_falling_back(path):
    def unavailable():
        raise SnapshotUnavailable(
            "C:/private/reports/scoreboard.json postgresql://user:secret@db/catalog"
        )

    with _snapshot_server(unavailable) as base:
        code, body, headers = _get_with_headers(base, path)
    encoded = json.dumps(body)
    assert code == 503
    assert body == {"error": {"code": "SNAPSHOT_UNAVAILABLE",
                               "message": "authoritative scoreboard snapshot unavailable"}}
    assert "private" not in encoded and "secret" not in encoded
    assert "results" not in body and "seeds" not in body and "funnel" not in body
    assert headers["Cache-Control"] == "no-store"


def test_mismatched_progress_provider_is_503():
    snapshot = _snapshot()

    def mismatched(_snapshot_id):
        return {
            "schema_version": "semiskill.progress/v1",
            "scoreboard_snapshot_id": "sha256:" + "0" * 64,
            "generated_at": "2026-08-06T00:00:01Z",
            "workers": [],
        }

    with _snapshot_server(lambda: snapshot, mismatched) as base:
        code, body, _headers = _get_with_headers(base, "/progress")
    assert code == 503 and body["error"]["code"] == "SNAPSHOT_UNAVAILABLE"


def test_snapshot_database_environment_must_match_api_runtime():
    snapshot = _snapshot()
    with _snapshot_server(
        lambda: snapshot, snapshot_environment="production",
    ) as base:
        code, body, _headers = _get_with_headers(base, "/scoreboard")
    assert code == 503 and body["error"]["code"] == "SNAPSHOT_UNAVAILABLE"


def test_self_hashed_semantic_fabrication_is_503():
    snapshot = _snapshot()
    snapshot["registry"]["active"] = 84
    canonical = dict(snapshot)
    canonical.pop("snapshot_id")
    canonical.pop("generated_at")
    snapshot["snapshot_id"] = "sha256:" + hashlib.sha256(json.dumps(
        canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()
    with _snapshot_server(lambda: snapshot) as base:
        code, body, _headers = _get_with_headers(base, "/scoreboard")
    assert code == 503 and body["error"]["code"] == "SNAPSHOT_UNAVAILABLE"
