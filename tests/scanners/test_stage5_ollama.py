import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from semiskill.scanners.stage5_ollama import (
    OllamaJudge,
    Stage5Policy,
    Stage5Refused,
    _is_loopback_only,
)

DIGEST = "sha256:" + "a" * 64
MODEL = "qwen3-coder:30b"


# --------------------------------------------------------------------------------------
# A real local HTTP server standing in for Ollama — no live daemon needed. Each test
# registers exactly the routes it needs; anything else 404s.
# --------------------------------------------------------------------------------------

class _FakeOllama:
    def __init__(self, host="127.0.0.1"):
        self.routes = {}       # (method, path) -> callable(body: bytes) -> (status, headers, body)
        self.calls = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a, **k):
                pass

            def _handle(self, method):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                outer.calls.append((method, self.path))
                fn = outer.routes.get((method, self.path))
                if fn is None:
                    self.send_response(404)
                    self.end_headers()
                    return
                status, headers, response_body = fn(body)
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response_body)

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.server = HTTPServer((host, 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


@pytest.fixture
def fake_ollama():
    server = _FakeOllama()
    yield server
    server.close()


def _tags_route(*, name=MODEL, digest=DIGEST, count=1):
    models = [{"name": name, "digest": digest} for _ in range(count)]

    def _respond(_body):
        return 200, {"Content-Type": "application/json"}, json.dumps({"models": models}).encode()
    return _respond


def _generate_route(*, score=0.9, extra_key=False, status=200, raw_text=None):
    def _respond(_body):
        if raw_text is not None:
            text = raw_text
        elif extra_key:
            text = json.dumps({"safety_score": score, "extra": "x"})
        else:
            text = json.dumps({"safety_score": score})
        return status, {"Content-Type": "application/json"}, json.dumps({"response": text}).encode()
    return _respond


def _policy(fake_ollama, **overrides) -> Stage5Policy:
    base = dict(host="127.0.0.1", port=fake_ollama.port, model=MODEL, model_digest=DIGEST,
                approved=True, timeout_seconds=5.0)
    base.update(overrides)
    return Stage5Policy(**base)


# --------------------------------------------------------------------------------------
# _is_loopback_only — deterministic via a monkeypatched "LAN IP" (still in 127.0.0.0/8, so
# it's a real, connectable address, but distinct from the literal 127.0.0.1 the checker
# special-cases). A server bound only to 127.0.0.1 never accepts a connection addressed to
# a different loopback alias; a wildcard-bound server accepts one on any local address.
# --------------------------------------------------------------------------------------

def test_is_loopback_only_true_for_a_loopback_bound_server(monkeypatch, fake_ollama):
    monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.2")
    assert _is_loopback_only("127.0.0.1", fake_ollama.port) is True


def test_is_loopback_only_false_for_a_wildcard_bound_server(monkeypatch):
    wildcard = _FakeOllama(host="0.0.0.0")
    try:
        monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.2")
        assert _is_loopback_only("127.0.0.1", wildcard.port) is False
    finally:
        wildcard.close()


def test_is_loopback_only_true_when_lan_ip_cannot_be_determined(monkeypatch, fake_ollama):
    def _raise(_name):
        raise OSError("no network")
    monkeypatch.setattr(socket, "gethostbyname", _raise)
    assert _is_loopback_only("127.0.0.1", fake_ollama.port) is True


def test_is_loopback_only_false_for_a_non_loopback_host():
    assert _is_loopback_only("10.0.0.5", 11434) is False


# --------------------------------------------------------------------------------------
# Preflight — BLK-004 (approved) and the loopback contract are enforced in code, before any
# network call, mirroring Stage-2's "an unapproved chain never invokes the engine" pattern.
# --------------------------------------------------------------------------------------

def test_unapproved_policy_never_calls_the_network(fake_ollama):
    policy = _policy(fake_ollama, approved=False)
    with pytest.raises(Stage5Refused, match="not approved"):
        OllamaJudge(policy).score(candidate="x", rubric="r")
    assert fake_ollama.calls == []


def test_non_loopback_host_is_refused_before_any_call(fake_ollama):
    policy = _policy(fake_ollama, host="10.0.0.5")
    with pytest.raises(Stage5Refused, match="loopback"):
        OllamaJudge(policy).score(candidate="x", rubric="r")
    assert fake_ollama.calls == []


def test_daemon_reachable_on_lan_is_refused(monkeypatch):
    wildcard = _FakeOllama(host="0.0.0.0")
    try:
        monkeypatch.setattr(socket, "gethostbyname", lambda _name: "127.0.0.2")
        policy = _policy(wildcard)
        with pytest.raises(Stage5Refused, match="non-loopback"):
            OllamaJudge(policy).score(candidate="x", rubric="r")
        assert ("GET", "/api/tags") not in wildcard.calls
        assert ("POST", "/api/generate") not in wildcard.calls
    finally:
        wildcard.close()


def test_missing_model_digest_is_refused_before_any_call(fake_ollama):
    policy = _policy(fake_ollama, model_digest="")
    with pytest.raises(Stage5Refused, match="sha256"):
        OllamaJudge(policy).score(candidate="x", rubric="r")
    assert fake_ollama.calls == []


def test_oversized_candidate_is_refused_before_any_call(fake_ollama):
    policy = _policy(fake_ollama, max_candidate_bytes=10)
    with pytest.raises(Stage5Refused, match="bounded size"):
        OllamaJudge(policy).score(candidate="x" * 100, rubric="r")
    assert fake_ollama.calls == []


# --------------------------------------------------------------------------------------
# Model-digest pinning — the model's own claimed identity is never trusted; a mismatch or
# an ambiguous/missing model entry refuses before /api/generate is ever called.
# --------------------------------------------------------------------------------------

def test_model_digest_mismatch_is_refused_before_generate(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route(digest="sha256:" + "b" * 64)
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route()
    with pytest.raises(Stage5Refused, match="digest mismatch"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")
    assert ("POST", "/api/generate") not in fake_ollama.calls


def test_model_not_installed_is_refused_before_generate(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route(name="a-different-model")
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route()
    with pytest.raises(Stage5Refused, match="expected exactly 1"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")
    assert ("POST", "/api/generate") not in fake_ollama.calls


def test_duplicate_model_entries_are_refused_before_generate(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route(count=2)
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route()
    with pytest.raises(Stage5Refused, match="expected exactly 1"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")
    assert ("POST", "/api/generate") not in fake_ollama.calls


# --------------------------------------------------------------------------------------
# The generate call itself — every failure mode is absent evidence, never a fabricated pass.
# --------------------------------------------------------------------------------------

def test_successful_score_round_trip(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route(score=0.73)
    score = OllamaJudge(_policy(fake_ollama)).score(candidate="a skill body", rubric="rate it")
    assert score == 0.73
    assert fake_ollama.calls == [("GET", "/api/tags"), ("POST", "/api/generate")]


def test_non_200_status_is_refused(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route(status=500)
    with pytest.raises(Stage5Refused, match="status"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")


def test_redirect_is_not_followed(fake_ollama):
    def _redirect(_body):
        return 302, {"Location": "http://evil.example/steal"}, b""
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _redirect
    with pytest.raises(Stage5Refused, match="status"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")


def test_oversized_response_is_refused(fake_ollama):
    def _huge(_body):
        text = json.dumps({"safety_score": 0.5})
        payload = json.dumps({"response": text, "padding": "z" * 5000}).encode()
        return 200, {"Content-Type": "application/json"}, payload
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _huge
    policy = _policy(fake_ollama, max_response_bytes=100)
    with pytest.raises(Stage5Refused, match="bounded size"):
        OllamaJudge(policy).score(candidate="x", rubric="r")


def test_malformed_json_response_is_refused(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route(raw_text="not json at all")
    with pytest.raises(Stage5Refused, match="valid JSON"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")


def test_missing_response_field_is_refused(fake_ollama):
    def _no_field(_body):
        return 200, {"Content-Type": "application/json"}, json.dumps({"nope": True}).encode()
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _no_field
    with pytest.raises(Stage5Refused, match="no text field"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")


def test_unexpected_keys_in_score_json_are_refused(fake_ollama):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route(extra_key=True)
    with pytest.raises(Stage5Refused, match="unexpected shape"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")


@pytest.mark.parametrize("bad_score", [-0.1, 1.1, "0.5", True, None])
def test_out_of_range_or_malformed_score_is_refused(fake_ollama, bad_score):
    fake_ollama.routes[("GET", "/api/tags")] = _tags_route()
    fake_ollama.routes[("POST", "/api/generate")] = _generate_route(
        raw_text=json.dumps({"safety_score": bad_score})
    )
    with pytest.raises(Stage5Refused, match="malformed"):
        OllamaJudge(_policy(fake_ollama)).score(candidate="x", rubric="r")


def test_connection_refused_is_a_transport_refusal_not_a_crash():
    policy = Stage5Policy(host="127.0.0.1", port=1, model=MODEL, model_digest=DIGEST,
                          approved=True, timeout_seconds=1.0)
    with pytest.raises(Stage5Refused, match="transport error"):
        OllamaJudge(policy).score(candidate="x", rubric="r")
