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
from semiskill.context.acl import (
    PrincipalUnauthenticated,
    ResolvedPrincipal,
)
from tests.support import publish_test_skill

MIG = Path("semiskill/artifacts/migrations")


def _test_principal_resolver(headers) -> ResolvedPrincipal:
    raw = headers.get("X-Principal-Labels", "public")
    labels = tuple(label.strip() for label in raw.split(",") if label.strip())
    return ResolvedPrincipal(subject="test-user", provider="test-resolver", labels=labels)


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
    httpd = serve(
        port=0, dsn=pg_dsn, clearance_dsn=pg_dsn,
        principal_resolver=_test_principal_resolver,
    )
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
        principal_resolver=_test_principal_resolver,
        clearance_dsn="postgresql://clearance:secret@127.0.0.1:1/never_used",
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
def test_clearance_header_cannot_self_assert_restricted_labels(server, pg_dsn):
    httpd = serve(port=0, dsn=pg_dsn)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, body = _get(base, "/catalog", labels="team,regulated")
        assert code == 200
        assert body["results"] == []
    finally:
        httpd.shutdown()


@pytest.mark.integration
def test_explicit_resolver_ignores_forged_labels_outside_its_result(server, pg_dsn):
    def team_only(_headers):
        return ResolvedPrincipal(
            subject="team-user", provider="test-resolver", labels=("team",),
        )

    httpd = serve(
        port=0, dsn=pg_dsn, clearance_dsn=pg_dsn, principal_resolver=team_only,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        slugs = {
            row["slug"] for row in _get(base, "/catalog", labels="regulated")[1]["results"]
        }
        assert slugs == {"dv/pub-team"}
    finally:
        httpd.shutdown()


@pytest.mark.integration
def test_resolver_is_called_once_for_skill_detail(server, pg_dsn):
    _base, store = server
    skill = next(
        artifact for artifact in store.by_type(ArtifactType.SKILL_VERSION)
        if artifact.payload.get("slug") == "dv/pub-team"
    )
    calls = 0

    def resolver(_headers):
        nonlocal calls
        calls += 1
        return ResolvedPrincipal(
            subject="team-user", provider="test-resolver", labels=("team",),
        )

    httpd = serve(
        port=0, dsn=pg_dsn, clearance_dsn=pg_dsn, principal_resolver=resolver,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        code, _body = _get(base, f"/skill/{skill.artifact_id}")
        assert code == 200 and calls == 1
    finally:
        httpd.shutdown()


@pytest.mark.integration
def test_lineage_and_reuse_endpoints_are_bound_to_published_artifacts(server):
    base, store = server
    approval = next(
        artifact for artifact in store.by_type(ArtifactType.APPROVAL)
        if artifact.payload.get("skill", {}).get("slug") == "dv/pub-team"
    )
    skill_id = approval.input_refs[0]
    lineage_status, lineage = _get(base, f"/lineage/{approval.artifact_id}", labels="team")
    reuse_status, reuse = _get(base, f"/reuse/{skill_id}", labels="team")
    assert lineage_status == 200
    assert {node["artifact_id"] for node in lineage["nodes"]} >= {
        str(approval.artifact_id), str(skill_id),
    }
    assert reuse_status == 200 and reuse == {"reuse": []}


@pytest.mark.integration
def test_operator_queue_is_not_authorized_by_catalog_clearance(server):
    base, _store = server
    status, body = _get(base, "/queue", labels="team,regulated")
    assert status == 403 and body["error"]["code"] == "OPERATOR_AUTH_REQUIRED"


@pytest.mark.integration
@pytest.mark.parametrize("route", ["skill", "lineage", "reuse"])
def test_artifact_routes_reject_malformed_uuid(server, route):
    base, _store = server
    status, body = _get(base, f"/{route}/not-a-uuid", labels="team")
    assert status == 400 and body["error"]["code"] == "INVALID_ARTIFACT_ID"


def test_configured_resolver_without_clearance_database_fails_closed():
    httpd = serve(
        port=0, dsn="postgresql://unreachable:secret@127.0.0.1:1/never_used",
        principal_resolver=_test_principal_resolver,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, body = _get(base, "/catalog")
        assert status == 503 and body["error"]["code"] == "IDENTITY_UNAVAILABLE"
    finally:
        httpd.shutdown()


def test_production_server_refuses_missing_entra_composition():
    with pytest.raises(RuntimeError, match="Entra principal resolver"):
        serve(
            port=0, dsn="postgresql://runtime:secret@db/semiskill",
            snapshot_environment="production",
        )


def test_operator_authorizer_exception_fails_closed():
    def broken(_headers):
        raise RuntimeError("secret operator detail")

    httpd = serve(
        port=0, dsn="postgresql://unreachable:secret@127.0.0.1:1/never_used",
        operator_authorizer=broken,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, body = _get(base, "/queue")
        assert status == 403 and body["error"]["code"] == "OPERATOR_AUTH_REQUIRED"
        assert "secret" not in json.dumps(body)
    finally:
        httpd.shutdown()


@pytest.mark.parametrize(
    ("resolver", "expected_status", "expected_code"),
    [
        (lambda _headers: (_ for _ in ()).throw(PrincipalUnauthenticated("secret-token")),
         401, "AUTHENTICATION_REQUIRED"),
        (lambda _headers: (_ for _ in ()).throw(RuntimeError("secret-token")),
         503, "IDENTITY_UNAVAILABLE"),
        (lambda _headers: ["team"], 503, "IDENTITY_UNAVAILABLE"),
    ],
)
def test_principal_resolution_failures_are_structured_and_do_not_leak(
    resolver, expected_status, expected_code,
):
    unreachable = "postgresql://unreachable:secret@127.0.0.1:1/never_used"
    httpd = serve(
        port=0, dsn=unreachable, clearance_dsn=unreachable,
        principal_resolver=resolver,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, body = _get(base, "/catalog")
        assert status == expected_status
        assert body["error"]["code"] == expected_code
        assert "secret-token" not in json.dumps(body)
    finally:
        httpd.shutdown()


def test_unknown_route_does_not_invoke_principal_resolver():
    called = False

    def resolver(_headers):
        nonlocal called
        called = True
        raise RuntimeError("must not run")

    httpd = serve(
        port=0, dsn="postgresql://unreachable:secret@127.0.0.1:1/never_used",
        clearance_dsn="postgresql://unreachable:secret@127.0.0.1:1/never_used",
        principal_resolver=resolver,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{httpd.server_address[1]}"
        status, _body = _get(base, "/unknown")
        assert status == 404 and called is False
    finally:
        httpd.shutdown()


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
