import json
import threading
import urllib.error
import urllib.request
import pytest
from pathlib import Path
from semiskill.api import serve
from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.capture.intake import build_skill_version
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
