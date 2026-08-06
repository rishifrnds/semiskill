import concurrent.futures
import hashlib
import http.client
import json
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from dashboard import server


_TOKEN = "fixed-test-token-with-at-least-256-bits-0000000000000000"
_OMIT = object()


def _model(actions=None):
    return {
        "actions": actions or [
            {
                "id": "A-01",
                "group": "Build",
                "label": "Build approver console",
                "prompt": "Implement the approver console under the governed workflow.",
            },
            {
                "id": "A-27",
                "group": "Quality",
                "label": "Request isolated full-suite verification",
                "prompt": "Run the suite serially against the exact isolated test database.",
            },
        ]
    }


@contextmanager
def _running_server(tmp_path, *, model=None, monkeypatch=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(model or _model()), encoding="utf-8")
    model_path.with_suffix(".sha256").write_text(
        "sha256:" + hashlib.sha256(model_path.read_bytes()).hexdigest() + "\n",
        encoding="ascii",
    )
    inbox_path = tmp_path / "inbox.jsonl"
    queue = server.ActionQueue(inbox_path=inbox_path, model_path=model_path)
    httpd = server.DashboardHTTPServer(
        ("127.0.0.1", 0),
        server.Handler,
        action_queue=queue,
        csrf_token=_TOKEN,
    )
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd, inbox_path
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _valid_payload(template_id="A-01", request_id=None, context="overview"):
    return {
        "schema_version": "semiskill.dashboard-action/v1",
        "request_type": "prepared",
        "template_id": template_id,
        "priority": "normal",
        "context": context,
        "request_id": request_id or str(uuid.uuid4()),
    }


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _request(
    httpd,
    method,
    path,
    *,
    body=b"",
    host=_OMIT,
    origin=_OMIT,
    token=_OMIT,
    content_type=_OMIT,
    content_length=_OMIT,
    extra_headers=(),
    send_body=True,
):
    port = httpd.server_address[1]
    authority = f"127.0.0.1:{port}"
    if isinstance(body, dict):
        body = json.dumps(body, separators=(",", ":")).encode("utf-8")
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
    if host is _OMIT:
        conn.putheader("Host", authority)
    elif host is not None:
        conn.putheader("Host", host)
    if method == "POST":
        if origin is _OMIT:
            conn.putheader("Origin", f"http://{authority}")
        elif origin is not None:
            conn.putheader("Origin", origin)
        if token is _OMIT:
            conn.putheader("X-SemiSkill-CSRF", _TOKEN)
        elif token is not None:
            conn.putheader("X-SemiSkill-CSRF", token)
        if content_type is _OMIT:
            conn.putheader("Content-Type", "application/json")
        elif content_type is not None:
            conn.putheader("Content-Type", content_type)
        if content_length is _OMIT:
            conn.putheader("Content-Length", str(len(body)))
        elif content_length is not None:
            conn.putheader("Content-Length", str(content_length))
    for name, value in extra_headers:
        conn.putheader(name, value)
    conn.endheaders()
    if send_body and body:
        conn.send(body)
    response = conn.getresponse()
    raw = response.read()
    headers = {name.lower(): value for name, value in response.getheaders()}
    is_json = headers.get("content-type", "").lower().startswith("application/json")
    result = {
        "status": response.status,
        "headers": headers,
        "raw": raw,
        "text": raw.decode("utf-8") if raw else "",
        "json": json.loads(raw.decode("utf-8")) if raw and is_json else None,
    }
    conn.close()
    return result


def test_prepared_action_is_server_derived_durable_and_idempotent(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        payload = _valid_payload()
        first = _request(httpd, "POST", "/api/action", body=payload)
        replay = _request(httpd, "POST", "/api/action", body=payload)

        assert first["status"] == replay["status"] == 202
        assert first["json"] == replay["json"]
        receipt = first["json"]
        assert set(receipt) == {
            "schema_version", "receipt_id", "request_id", "status", "accepted_at",
            "request_type", "template_id", "action_sha256",
        }
        assert receipt["schema_version"] == "semiskill.dashboard-receipt/v1"
        assert receipt["status"] == "queued" and receipt["template_id"] == "A-01"
        assert receipt["receipt_id"] == "ACT-" + receipt["request_id"].replace("-", "")
        assert first["headers"]["location"].endswith(receipt["receipt_id"])

        rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 1
        row = rows[0]
        assert row["schema_version"] == "semiskill.dashboard-request/v1"
        assert row["title"] == "Build approver console"
        assert row["prompt"] == "Implement the approver console under the governed workflow."
        assert row["template_sha256"].startswith("sha256:")
        assert row["template_registry_sha256"].startswith("sha256:")
        assert row["credit"] == "none"
        assert _TOKEN not in json.dumps(row) + json.dumps(receipt)


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"host": None}, 421),
        ({"host": "evil.example"}, 421),
        ({"extra_headers": (("Host", "evil.example"),)}, 421),
        ({"origin": None}, 403),
        ({"origin": "null"}, 403),
        ({"origin": "https://evil.example"}, 403),
        ({"extra_headers": (("Origin", "https://evil.example"),)}, 403),
        ({"token": None}, 403),
        ({"token": "wrong"}, 403),
        ({"extra_headers": (("X-SemiSkill-CSRF", "wrong"),)}, 403),
        ({"content_type": "text/plain"}, 415),
        ({"content_type": "application/json; charset=iso-8859-1"}, 415),
    ],
)
def test_host_origin_csrf_and_media_type_fail_closed(tmp_path, overrides, expected):
    with _running_server(tmp_path) as (httpd, inbox):
        response = _request(httpd, "POST", "/api/action", body=_valid_payload(), **overrides)
        assert response["status"] == expected
        assert not inbox.exists() or inbox.read_bytes() == b""
        assert not any(name.startswith("access-control-") for name in response["headers"])


@pytest.mark.parametrize(
    ("body", "overrides", "expected"),
    [
        (b"{}", {"content_length": None}, 411),
        (b"{}", {"content_length": "-1"}, 400),
        (b"{}", {"content_length": "abc"}, 400),
        (b"", {"content_length": 16_385, "send_body": False}, 413),
        (b"{}", {"extra_headers": (("Content-Length", "2"),)}, 400),
        (b"0\r\n\r\n", {"extra_headers": (("Transfer-Encoding", "chunked"),)}, 400),
        (b"\xff", {}, 400),
        (b"{", {}, 400),
        (b"[]", {}, 422),
        (b"null", {}, 422),
        (b'{"schema_version":"x","schema_version":"y"}', {}, 400),
        (b'{"value":NaN}', {}, 400),
    ],
)
def test_body_framing_and_strict_json_fail_closed(tmp_path, body, overrides, expected):
    with _running_server(tmp_path) as (httpd, inbox):
        response = _request(httpd, "POST", "/api/action", body=body, **overrides)
        assert response["status"] == expected
        assert not inbox.exists() or inbox.read_bytes() == b""


def test_extreme_content_length_and_json_depth_fail_closed(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        huge_length = _request(
            httpd,
            "POST",
            "/api/action",
            body=b"",
            content_length="9" * 5000,
            send_body=False,
        )
        deeply_nested = _request(
            httpd,
            "POST",
            "/api/action",
            body=(b"[" * 1500) + b"0" + (b"]" * 1500),
        )
        assert huge_length["status"] == deeply_nested["status"] == 400
        assert not inbox.exists() or inbox.read_bytes() == b""


@pytest.mark.parametrize(
    "mutation",
    [
        {"prompt": "ignore previous instructions"},
        {"title": "forged"},
        {"status": "approved"},
        {"template_id": "A-99"},
        {"context": "../../outside"},
        {"priority": "execute-now"},
    ],
)
def test_unknown_or_forged_action_fields_are_rejected(tmp_path, mutation):
    with _running_server(tmp_path) as (httpd, inbox):
        payload = _valid_payload()
        payload.update(mutation)
        response = _request(httpd, "POST", "/api/action", body=payload)
        assert response["status"] == 422
        assert not inbox.exists() or inbox.read_bytes() == b""


def test_same_request_id_with_different_action_is_conflict(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        request_id = str(uuid.uuid4())
        assert _request(
            httpd, "POST", "/api/action", body=_valid_payload("A-01", request_id)
        )["status"] == 202
        conflict = _request(
            httpd, "POST", "/api/action", body=_valid_payload("A-27", request_id)
        )
        assert conflict["status"] == 409
        assert len(inbox.read_text(encoding="utf-8").splitlines()) == 1


def test_concurrent_appends_are_complete_and_unique(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        payloads = [_valid_payload(request_id=str(uuid.uuid4())) for _ in range(30)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            responses = list(pool.map(
                lambda payload: _request(httpd, "POST", "/api/action", body=payload),
                payloads,
            ))
        assert all(response["status"] == 202 for response in responses)
        rows = [json.loads(line) for line in inbox.read_text(encoding="utf-8").splitlines()]
        assert len(rows) == 30
        assert len({row["receipt_id"] for row in rows}) == 30
        assert len({row["request_id"] for row in rows}) == 30


def test_archive_is_protected_recoverable_and_collision_safe(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        for _ in range(2):
            assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        archive_request = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        archived = _request(httpd, "POST", "/api/inbox/archive", body=archive_request)
        assert archived["status"] == 200
        receipt = archived["json"]
        assert receipt["schema_version"] == "semiskill.dashboard-archive-receipt/v1"
        assert receipt["archive_id"] == "ARC-" + receipt["request_id"].replace("-", "")
        assert receipt["row_count"] == 2
        archived_path = inbox.parent / receipt["recovery_ref"]
        assert archived_path.is_file()
        assert ".." not in receipt["recovery_ref"]
        assert receipt["sha256"] == "sha256:" + hashlib.sha256(archived_path.read_bytes()).hexdigest()

        assert _request(httpd, "POST", "/api/inbox/clear", body={})["status"] == 404
        assert _request(httpd, "POST", "/api/run", body={})["status"] == 404


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"host": "evil.example"}, 421),
        ({"origin": None}, 403),
        ({"origin": "https://evil.example"}, 403),
        ({"token": None}, 403),
        ({"token": "wrong"}, 403),
        ({"content_type": "text/plain"}, 415),
    ],
)
def test_archive_authority_failures_leave_queue_unchanged(tmp_path, overrides, expected):
    with _running_server(tmp_path) as (httpd, inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        before = inbox.read_bytes()
        payload = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        response = _request(httpd, "POST", "/api/inbox/archive", body=payload, **overrides)
        assert response["status"] == expected
        assert inbox.read_bytes() == before
        assert not (tmp_path / "archive").exists()


def test_action_and_archive_idempotency_survive_rotation(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        action = _valid_payload()
        queued = _request(httpd, "POST", "/api/action", body=action)["json"]
        archive_request = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        archived = _request(httpd, "POST", "/api/inbox/archive", body=archive_request)["json"]

        replay_action = _request(httpd, "POST", "/api/action", body=action)
        replay_archive = _request(httpd, "POST", "/api/inbox/archive", body=archive_request)
        receipt_lookup = _request(
            httpd, "GET", f"/api/inbox/receipts/{queued['receipt_id']}"
        )

        assert replay_action["status"] == 202 and replay_action["json"] == queued
        assert replay_archive["status"] == 200 and replay_archive["json"] == archived
        assert receipt_lookup["status"] == 200 and receipt_lookup["json"] == queued
        assert not inbox.exists()
        assert len(list((tmp_path / "archive").glob("inbox-*.jsonl"))) == 1
        assert len(list((tmp_path / "archive").glob("inbox-*.receipt.json"))) == 1


def test_archive_receipt_failure_rolls_back_without_losing_rows(tmp_path, monkeypatch):
    with _running_server(tmp_path) as (httpd, inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        original = inbox.read_bytes()
        archive_request = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        real_fsync = server.action_queue.os.fsync
        monkeypatch.setattr(
            server.action_queue.os,
            "fsync",
            lambda _fd: (_ for _ in ()).throw(OSError("receipt fsync failed")),
        )
        failed = _request(httpd, "POST", "/api/inbox/archive", body=archive_request)
        assert failed["status"] == 503
        assert inbox.read_bytes() == original
        assert not list((tmp_path / "archive").glob("inbox-*"))

        monkeypatch.setattr(server.action_queue.os, "fsync", real_fsync)
        recovered = _request(httpd, "POST", "/api/inbox/archive", body=archive_request)
        assert recovered["status"] == 200
        assert recovered["json"]["row_count"] == 1


def test_archive_filesystem_prep_failure_is_structured_503(tmp_path, monkeypatch):
    with _running_server(tmp_path) as (httpd, inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        original = inbox.read_bytes()
        monkeypatch.setattr(
            server.action_queue,
            "_fsync_directory",
            lambda _path: (_ for _ in ()).throw(OSError("directory sync unavailable")),
        )
        response = _request(httpd, "POST", "/api/inbox/archive", body={
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        })
        assert response["status"] == 503
        assert response["json"] == {"error": "queue_unavailable"}
        assert inbox.read_bytes() == original


def test_template_registry_is_frozen_and_drift_fails_closed(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        changed = _model()
        changed["actions"][0]["prompt"] = "Changed after server startup."
        (tmp_path / "model.json").write_text(json.dumps(changed), encoding="utf-8")
        response = _request(httpd, "POST", "/api/action", body=_valid_payload())
        assert response["status"] == 503
        assert not inbox.exists()


def test_template_manifest_pins_registry_before_startup(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(_model()), encoding="utf-8")
    model_path.with_suffix(".sha256").write_text(
        "sha256:" + hashlib.sha256(model_path.read_bytes()).hexdigest() + "\n",
        encoding="ascii",
    )
    changed = _model()
    changed["actions"][0]["prompt"] = "Tampered before startup."
    model_path.write_text(json.dumps(changed), encoding="utf-8")

    queue = server.ActionQueue(inbox_path=tmp_path / "inbox.jsonl", model_path=model_path)
    try:
        with pytest.raises(server.action_queue.QueueUnavailable):
            queue.enqueue(_valid_payload())
        with pytest.raises(server.action_queue.QueueUnavailable):
            queue.public_templates()
    finally:
        queue.close()


def test_browser_listing_never_exposes_server_prompt(tmp_path):
    with _running_server(tmp_path) as (httpd, _inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        listing = _request(httpd, "GET", "/api/inbox")
        assert listing["status"] == 200
        rendered = json.dumps(listing["json"])
        assert "Implement the approver console" not in rendered
        assert '"prompt"' not in rendered


def test_second_queue_owner_fails_closed(tmp_path):
    model_path = tmp_path / "model.json"
    model_path.write_text(json.dumps(_model()), encoding="utf-8")
    model_path.with_suffix(".sha256").write_text(
        "sha256:" + hashlib.sha256(model_path.read_bytes()).hexdigest() + "\n",
        encoding="ascii",
    )
    first = server.ActionQueue(inbox_path=tmp_path / "inbox.jsonl", model_path=model_path)
    try:
        with pytest.raises(server.action_queue.QueueUnavailable):
            server.ActionQueue(inbox_path=tmp_path / "inbox.jsonl", model_path=model_path)
    finally:
        first.close()


def test_corrupt_queue_and_invalid_template_registry_are_unavailable(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        inbox.write_text("not-json\n", encoding="utf-8")
        response = _request(httpd, "GET", "/api/inbox")
        assert response["status"] == 503

    duplicate = _model(actions=[_model()["actions"][0], _model()["actions"][0]])
    with _running_server(tmp_path / "duplicate", model=duplicate) as (httpd, inbox):
        response = _request(httpd, "POST", "/api/action", body=_valid_payload())
        assert response["status"] == 503
        assert not inbox.exists() or inbox.read_bytes() == b""


def test_session_token_is_same_origin_bootstrap_only_and_gets_do_not_mutate(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        session = _request(httpd, "GET", "/api/session")
        listing = _request(httpd, "GET", "/api/inbox")
        assert session["status"] == listing["status"] == 200
        assert session["json"]["csrf_token"] == _TOKEN
        assert _TOKEN not in json.dumps(listing["json"])
        assert not inbox.exists()


def test_dashboard_and_api_are_not_frameable(tmp_path):
    with _running_server(tmp_path) as (httpd, _inbox):
        for path in ("/", "/api/session", "/api/inbox"):
            response = _request(httpd, "GET", path)
            assert response["headers"]["x-frame-options"] == "DENY"
            assert "frame-ancestors 'none'" in response["headers"]["content-security-policy"]
            assert response["headers"]["x-content-type-options"] == "nosniff"


def test_query_mutations_and_handler_command_calls_are_absent(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        response = _request(httpd, "POST", "/api/action?template=A-01", body=_valid_payload())
        assert response["status"] == 404
        archive = _request(
            httpd,
            "POST",
            "/api/inbox/archive?all=true",
            body={
                "schema_version": "semiskill.dashboard-archive/v1",
                "request_id": str(uuid.uuid4()),
            },
        )
        assert archive["status"] == 404
        assert not inbox.exists()

    import inspect

    post_source = inspect.getsource(server.Handler.do_POST)
    for forbidden in ("_sh(", "subprocess", "docker", "pytest", "Popen", "os.system"):
        assert forbidden not in post_source


def test_post_routes_never_reach_state_process_database_or_scoreboard_helpers(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("POST crossed the queue-only authority boundary")

    for name in ("build_state", "_sh", "canonical_snapshot_signals", "_rebuild_snapshot"):
        monkeypatch.setattr(server, name, forbidden)
    with _running_server(tmp_path) as (httpd, _inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        archived = _request(httpd, "POST", "/api/inbox/archive", body={
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        })
        assert archived["status"] == 200


def test_state_projection_also_redacts_prompt_and_registry_hash(tmp_path, monkeypatch):
    monkeypatch.setattr(
        server,
        "build_state",
        lambda reader, _templates: {"inbox": reader()},
    )
    with _running_server(tmp_path) as (httpd, _inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        state = _request(httpd, "GET", "/api/state")
        rendered = json.dumps(state["json"])
        assert state["status"] == 200
        assert '"prompt"' not in rendered
        assert "template_registry_sha256" not in rendered


def test_append_fsync_failure_never_returns_success(tmp_path, monkeypatch):
    with _running_server(tmp_path) as (httpd, inbox):
        monkeypatch.setattr(server.action_queue.os, "fsync", lambda _fd: (_ for _ in ()).throw(OSError("boom")))
        response = _request(httpd, "POST", "/api/action", body=_valid_payload())
        assert response["status"] == 503
        assert not inbox.exists() or inbox.read_bytes() == b""


def test_action_retry_recovers_ambiguous_post_replace_failure(tmp_path, monkeypatch):
    with _running_server(tmp_path) as (httpd, inbox):
        payload = _valid_payload()
        real_replace = server.action_queue._replace_durable

        def committed_then_failed(source, target):
            real_replace(source, target)
            raise OSError("response boundary lost after commit")

        monkeypatch.setattr(server.action_queue, "_replace_durable", committed_then_failed)
        uncertain = _request(httpd, "POST", "/api/action", body=payload)
        monkeypatch.setattr(server.action_queue, "_replace_durable", real_replace)
        replay = _request(httpd, "POST", "/api/action", body=payload)

        assert uncertain["status"] == 503
        assert replay["status"] == 202
        rows = inbox.read_text(encoding="utf-8").splitlines()
        assert len(rows) == 1
        assert json.loads(rows[0])["request_id"] == payload["request_id"]


def test_action_restart_resyncs_rename_before_idempotent_success(tmp_path, monkeypatch):
    payload = _valid_payload()
    real_sync = server.action_queue._fsync_directory
    failed = False

    def fail_first_post_rename_sync(path):
        nonlocal failed
        if not failed:
            failed = True
            raise OSError("directory sync interrupted after rename")
        return real_sync(path)

    with _running_server(tmp_path) as (httpd, _inbox):
        monkeypatch.setattr(server.action_queue, "_fsync_directory", fail_first_post_rename_sync)
        uncertain = _request(httpd, "POST", "/api/action", body=payload)
        assert uncertain["status"] == 503
        monkeypatch.setattr(server.action_queue, "_fsync_directory", real_sync)

    with _running_server(tmp_path) as (httpd, inbox):
        replay = _request(httpd, "POST", "/api/action", body=payload)
        assert replay["status"] == 202
        assert replay["json"]["request_id"] == payload["request_id"]
        assert len(inbox.read_text(encoding="utf-8").splitlines()) == 1


def test_archive_retry_recovers_ambiguous_post_move_failure(tmp_path, monkeypatch):
    with _running_server(tmp_path) as (httpd, _inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        payload = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        real_move = server.action_queue._move_no_replace

        def committed_then_failed(source, target):
            real_move(source, target)
            if target.suffix == ".jsonl":
                raise OSError("response boundary lost after archive move")

        monkeypatch.setattr(server.action_queue, "_move_no_replace", committed_then_failed)
        uncertain = _request(httpd, "POST", "/api/inbox/archive", body=payload)
        monkeypatch.setattr(server.action_queue, "_move_no_replace", real_move)
        replay = _request(httpd, "POST", "/api/inbox/archive", body=payload)

        assert uncertain["status"] == 503
        assert replay["status"] == 200
        assert replay["json"]["request_id"] == payload["request_id"]
        assert replay["json"]["row_count"] == 1


def test_archive_restart_resyncs_data_move_before_idempotent_success(tmp_path, monkeypatch):
    payload = {
        "schema_version": "semiskill.dashboard-archive/v1",
        "request_id": str(uuid.uuid4()),
    }
    real_sync = server.action_queue._fsync_directory
    failed = False

    def fail_when_archive_data_is_visible(path):
        nonlocal failed
        archive_dir = tmp_path / "archive"
        if not failed and archive_dir.exists() and list(archive_dir.glob("inbox-*.jsonl")):
            failed = True
            raise OSError("directory sync interrupted after archive move")
        return real_sync(path)

    with _running_server(tmp_path) as (httpd, _inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
        monkeypatch.setattr(server.action_queue, "_fsync_directory", fail_when_archive_data_is_visible)
        uncertain = _request(httpd, "POST", "/api/inbox/archive", body=payload)
        assert uncertain["status"] == 503
        monkeypatch.setattr(server.action_queue, "_fsync_directory", real_sync)

    with _running_server(tmp_path) as (httpd, inbox):
        replay = _request(httpd, "POST", "/api/inbox/archive", body=payload)
        assert replay["status"] == 200
        assert replay["json"]["request_id"] == payload["request_id"]
        assert replay["json"]["row_count"] == 1
        assert not inbox.exists()


def test_incomplete_archive_intent_recovers_exactly_once_on_restart(tmp_path):
    archive_request_id = str(uuid.uuid4())
    with _running_server(tmp_path) as (httpd, inbox):
        action = _request(httpd, "POST", "/api/action", body=_valid_payload())["json"]
        original = inbox.read_bytes()

    archived_at = datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )
    stamp = datetime.fromisoformat(archived_at.replace("Z", "+00:00")).strftime(
        "%Y%m%dT%H%M%S%fZ"
    )
    archive_id = "ARC-" + archive_request_id.replace("-", "")
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    target = archive_dir / f"inbox-{stamp}-{archive_id.removeprefix('ARC-')}.jsonl"
    receipt = {
        "schema_version": "semiskill.dashboard-archive-receipt/v1",
        "archive_id": archive_id,
        "request_id": archive_request_id,
        "archived_at": archived_at,
        "row_count": 1,
        "sha256": "sha256:" + hashlib.sha256(original).hexdigest(),
        "recovery_ref": target.relative_to(tmp_path).as_posix(),
    }
    target.with_suffix(".receipt.json").write_bytes(_canonical_json(receipt))

    with _running_server(tmp_path) as (httpd, inbox):
        listing = _request(httpd, "GET", "/api/inbox")
        replay = _request(httpd, "POST", "/api/inbox/archive", body={
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": archive_request_id,
        })
        action_lookup = _request(
            httpd, "GET", f"/api/inbox/receipts/{action['receipt_id']}"
        )
        assert listing["status"] == 200 and listing["json"]["inbox"] == []
        assert replay["status"] == 200 and replay["json"] == receipt
        assert action_lookup["status"] == 200 and action_lookup["json"] == action
        assert target.read_bytes() == original and not inbox.exists()


@pytest.mark.parametrize(
    "field",
    ["sha256", "row_count", "recovery_ref", "request_id", "archived_at"],
)
def test_tampered_archive_receipt_blocks_every_queue_surface(tmp_path, field, monkeypatch):
    with _running_server(tmp_path) as (httpd, _inbox):
        action = _request(httpd, "POST", "/api/action", body=_valid_payload())["json"]
        archived = _request(httpd, "POST", "/api/inbox/archive", body={
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        })["json"]

    receipt_path = next((tmp_path / "archive").glob("inbox-*.receipt.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if field == "sha256":
        receipt[field] = "sha256:" + ("0" * 64)
    elif field == "row_count":
        receipt[field] += 1
    elif field == "recovery_ref":
        receipt[field] = "archive/inbox-forged.jsonl"
    elif field == "request_id":
        receipt[field] = str(uuid.uuid4())
    else:
        receipt[field] = "2030-01-01T00:00:00.000000Z"
    receipt_path.write_bytes(_canonical_json(receipt))

    monkeypatch.setattr(
        server,
        "build_state",
        lambda reader, _templates: {"inbox": reader()},
    )
    with _running_server(tmp_path) as (httpd, _inbox):
        responses = [
            _request(httpd, "GET", "/api/inbox"),
            _request(httpd, "GET", "/api/state"),
            _request(httpd, "GET", f"/api/inbox/receipts/{action['receipt_id']}"),
            _request(httpd, "POST", "/api/action", body=_valid_payload()),
            _request(httpd, "POST", "/api/inbox/archive", body={
                "schema_version": "semiskill.dashboard-archive/v1",
                "request_id": archived["request_id"],
            }),
        ]
        assert [response["status"] for response in responses] == [503, 503, 503, 503, 503]


def test_duplicate_persisted_identity_blocks_every_queue_surface(tmp_path, monkeypatch):
    with _running_server(tmp_path) as (httpd, inbox):
        action = _request(httpd, "POST", "/api/action", body=_valid_payload())["json"]
        original = inbox.read_bytes()
    inbox.write_bytes(original + original)

    monkeypatch.setattr(
        server,
        "build_state",
        lambda reader, _templates: {"inbox": reader()},
    )
    with _running_server(tmp_path) as (httpd, _inbox):
        archive_payload = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        assert _request(httpd, "GET", "/api/inbox")["status"] == 503
        assert _request(httpd, "GET", "/api/state")["status"] == 503
        assert _request(
            httpd, "GET", f"/api/inbox/receipts/{action['receipt_id']}"
        )["status"] == 503
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 503
        assert _request(
            httpd, "POST", "/api/inbox/archive", body=archive_payload
        )["status"] == 503


@pytest.mark.parametrize("location", ["active", "archive_receipt"])
def test_deeply_nested_disk_json_fails_closed_everywhere(tmp_path, location, monkeypatch):
    with _running_server(tmp_path) as (_httpd, inbox):
        pass
    if location == "active":
        inbox.write_bytes((b"[" * 5000) + b"0" + (b"]" * 5000) + b"\n")
    else:
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()
        request_id = str(uuid.uuid4())
        stamp = "20300101T000000000000Z"
        archive_id = "ARC-" + request_id.replace("-", "")
        target = archive_dir / f"inbox-{stamp}-{archive_id.removeprefix('ARC-')}.jsonl"
        target.write_bytes(b"")
        target.with_suffix(".receipt.json").write_bytes(
            (b"[" * 5000) + b"0" + (b"]" * 5000)
        )

    monkeypatch.setattr(
        server,
        "build_state",
        lambda reader, _templates: {"inbox": reader()},
    )
    with _running_server(tmp_path) as (httpd, _inbox):
        action = _valid_payload()
        archive = {
            "schema_version": "semiskill.dashboard-archive/v1",
            "request_id": str(uuid.uuid4()),
        }
        statuses = [
            _request(httpd, "GET", "/api/inbox")["status"],
            _request(httpd, "GET", "/api/state")["status"],
            _request(httpd, "GET", "/api/inbox/receipts/ACT-" + ("0" * 32))["status"],
            _request(httpd, "POST", "/api/action", body=action)["status"],
            _request(httpd, "POST", "/api/inbox/archive", body=archive)["status"],
        ]
        assert statuses == [503, 503, 503, 503, 503]


def test_boolean_template_version_is_corrupt_not_integer_one(tmp_path):
    with _running_server(tmp_path) as (httpd, inbox):
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 202
    row = json.loads(inbox.read_text(encoding="utf-8"))
    row["template_version"] = True
    inbox.write_bytes(_canonical_json(row) + b"\n")

    with _running_server(tmp_path) as (httpd, _inbox):
        assert _request(httpd, "GET", "/api/inbox")["status"] == 503
        assert _request(httpd, "POST", "/api/action", body=_valid_payload())["status"] == 503
