import uuid
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.schema import Artifact, ArtifactType, ActorKind, SourceSystem
from semiskill.artifacts.store import PostgresArtifactStore, ScopedPublicationBundle
from semiskill.authoring.export_scope import (
    ExportPublicationRef,
    ExportRefused,
    ExportScope,
    load_scoped_publications,
    make_export_scope,
)
from semiskill.authoring.snapshot import finalize_scoreboard
from semiskill.capture.intake import build_skill_version
from semiskill.context.acl import ResolvedPrincipal, resolve_local_public_principal
from tests.authoring.test_snapshot import _body
from tests.support import TEST_IDENTITY, public_export_scope, publish_test_skill

MIG = Path("semiskill/artifacts/migrations")


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


def _skill(slug: str, label: str):
    return build_skill_version(
        skill_md=(f"---\nname: {slug}\nslug: {slug}\nversion: 1.0.0\n"
                  "function: dv\n---\nA bounded test procedure."),
        actor="test-author",
        permissions_label=label,
    )


def _empty_snapshot(*, environment="test", dirty=False):
    body = _body()
    body["sources"]["repository"].update({
        "commit": "test-commit", "dirty": dirty,
        "tree_sha256": "sha256:" + "2" * 64,
    })
    body["sources"]["skills"] = {
        "root": "skills", "tree_sha256": "sha256:" + "2" * 64,
        "full_tree_sha256": "sha256:" + "4" * 64,
    }
    body["sources"]["database"]["environment"] = environment
    body["sources"]["database"]["database_name"] = (
        "semiskill" if environment != "test" else "semiskill_test"
    )
    if environment == "production":
        body["sources"]["database"]["database_name"] = "semiskill_prod"
    return finalize_scoreboard(body, generated_at="2026-08-06T00:00:00Z")


class _ScopeStore:
    def __init__(self, snapshot):
        self.database = snapshot["sources"]["database"]

    def database_identity(self, *, environment):
        assert environment == self.database["environment"]
        return dict(self.database)

    def export_database_identity(self, *, environment):
        return {"identity_sha256": "sha256:" + "4" * 64, "permission_label": "public"}


def test_scope_requires_resolved_principal_and_exact_clearance(pg_store):
    with pytest.raises(ValueError, match="resolved principal"):
        ExportScope(
            principal={"subject": "forged", "labels": ["regulated"]},
            permission_label="regulated",
            generated_at="2026-08-06T00:00:00Z",
            scoreboard_snapshot_id="sha256:" + "1" * 64,
            scoreboard_generated_at="2026-08-06T00:00:00Z",
            source_commit="test-commit",
            source_skills_root="skills",
            source_tree_sha256="sha256:" + "2" * 64,
            database_environment="test",
            database_name="semiskill_test",
            database_identity_sha256="sha256:" + "3" * 64,
            export_reader_identity_sha256="sha256:" + "4" * 64,
            publications=(),
        )
    with pytest.raises(ValueError, match="trusted resolver"):
        ExportScope(
            principal=ResolvedPrincipal("forged", "entra_oidc", ("regulated",)),
            permission_label="regulated",
            generated_at="2026-08-06T00:00:00Z",
            scoreboard_snapshot_id="sha256:" + "1" * 64,
            scoreboard_generated_at="2026-08-06T00:00:00Z",
            source_commit="test-commit",
            source_skills_root="skills",
            source_tree_sha256="sha256:" + "2" * 64,
            database_environment="production",
            database_name="semiskill_prod",
            database_identity_sha256="sha256:" + "3" * 64,
            export_reader_identity_sha256="sha256:" + "4" * 64,
            publications=(),
        )
    with pytest.raises(ValueError, match="exceeds"):
        ExportScope(
            principal=resolve_local_public_principal(TEST_IDENTITY),
            permission_label="team",
            generated_at="2026-08-06T00:00:00Z",
            scoreboard_snapshot_id="sha256:" + "1" * 64,
            scoreboard_generated_at="2026-08-06T00:00:00Z",
            source_commit="test-commit",
            source_skills_root="skills",
            source_tree_sha256="sha256:" + "2" * 64,
            database_environment="test",
            database_name="semiskill_test",
            database_identity_sha256="sha256:" + "3" * 64,
            export_reader_identity_sha256="sha256:" + "4" * 64,
            publications=(),
        )


def test_scope_id_is_deterministic_and_stamp_does_not_disclose_other_labels(pg_store):
    scope = public_export_scope(pg_store, [])
    same = public_export_scope(pg_store, [])
    assert scope.scope_id == same.scope_id
    stamp = scope.safe_dict()
    assert stamp["scope_id"] == scope.scope_id
    assert stamp["principal"]["provider"] == "local_os"
    assert stamp["principal"]["principal_ref"].startswith("sha256:")
    assert TEST_IDENTITY.subject not in str(stamp)
    assert "labels" not in str(stamp) and "auth_context" not in str(stamp)


def test_make_scope_rejects_dirty_or_repository_mismatched_snapshot(monkeypatch):
    principal = resolve_local_public_principal(TEST_IDENTITY)
    monkeypatch.setattr(
        "semiskill.authoring.export_scope._repository_identity",
        lambda _root: ("test-commit", False),
    )
    dirty = _empty_snapshot(dirty=True)
    with pytest.raises(ExportRefused, match="clean source"):
        make_export_scope(
            principal=principal, permission_label="public",
            scoreboard=dirty,
            generated_at="2026-08-06T01:00:00Z", repo_root=".", store=_ScopeStore(dirty),
        )
    monkeypatch.setattr(
        "semiskill.authoring.export_scope._repository_identity",
        lambda _root: ("different", False),
    )
    clean = _empty_snapshot()
    with pytest.raises(ExportRefused, match="no longer matches"):
        make_export_scope(
            principal=principal, permission_label="public",
            scoreboard=clean, generated_at="2026-08-06T01:00:00Z",
            repo_root=".", store=_ScopeStore(clean),
        )


def test_make_scope_recomputes_the_skills_tree(monkeypatch):
    snapshot = _empty_snapshot()
    monkeypatch.setattr(
        "semiskill.authoring.export_scope._repository_identity",
        lambda _root: ("test-commit", False),
    )
    monkeypatch.setattr(
        "semiskill.authoring.export_scope._skills_tree_sha256",
        lambda _root: "sha256:" + "9" * 64,
    )
    with pytest.raises(ExportRefused, match="source tree no longer matches"):
        make_export_scope(
            principal=resolve_local_public_principal(TEST_IDENTITY),
            permission_label="public", scoreboard=snapshot,
            generated_at="2026-08-06T01:00:00Z", repo_root=".",
            store=_ScopeStore(snapshot),
        )


def test_production_scope_requires_entra(monkeypatch):
    monkeypatch.setenv("SEMISKILL_PRODUCTION_DATABASE_NAME", "semiskill_prod")
    monkeypatch.setattr(
        "semiskill.authoring.export_scope._repository_identity",
        lambda _root: ("test-commit", False),
    )
    snapshot = _empty_snapshot(environment="production")
    with pytest.raises(ExportRefused, match="Entra"):
        make_export_scope(
            principal=resolve_local_public_principal(TEST_IDENTITY),
            permission_label="public", scoreboard=snapshot,
            generated_at="2026-08-06T01:00:00Z", repo_root=".",
            store=_ScopeStore(snapshot),
        )


@pytest.mark.integration
def test_scoped_reader_never_returns_another_labels_payload(pg_store):
    public_fixture = publish_test_skill(pg_store, pg_store.append(_skill("dv-public", "public")))
    publish_test_skill(pg_store, pg_store.append(_skill("dv-secret", "regulated")))
    scope = public_export_scope(pg_store, [public_fixture])

    bundle = pg_store.scoped_publication_bundle("public")
    assert {head.slug for head in bundle.heads} == {"dv-public"}
    assert {row.permissions_label for row in bundle.artifacts} == {"public"}
    assert "dv-secret" not in str([row.payload for row in bundle.artifacts])

    loaded = load_scoped_publications(pg_store, scope)
    assert [row.reference.slug for row in loaded] == ["dv-public"]


@pytest.mark.integration
def test_stale_snapshot_head_is_refused(pg_store):
    first = publish_test_skill(pg_store, pg_store.append(_skill("dv-one", "public")))
    scope = public_export_scope(pg_store, [first])
    publish_test_skill(pg_store, pg_store.append(_skill("dv-two", "public")))
    with pytest.raises(ExportRefused, match="no longer match"):
        load_scoped_publications(pg_store, scope)


def test_publication_ref_rejects_mixed_label_and_malformed_hash():
    common = dict(
        slug="dv-one",
        skill_version_id=uuid.uuid4(), approval_id=uuid.uuid4(),
        automated_review_id=uuid.uuid4(), content_review_id=uuid.uuid4(),
        scan_artifact_ids=(uuid.uuid4(),), permissions_label="public",
    )
    with pytest.raises(ValueError, match="payload hash"):
        ExportPublicationRef(payload_sha256="not-a-hash", **common)


def test_duplicate_or_unrelated_bundle_artifacts_are_refused(pg_store):
    scope = public_export_scope(pg_store, [])
    extra = Artifact.new(
        artifact_type=ArtifactType.SKILL_VERSION,
        source_system=SourceSystem.CLI, actor="unrelated", actor_kind=ActorKind.AGENT,
        payload={"slug": "unrelated"},
    )

    class BadStore:
        def database_identity(self, *, environment):
            return pg_store.database_identity(environment=environment)

        def export_database_identity(self, *, environment):
            return pg_store.export_database_identity(environment=environment)

        def scoped_publication_bundle(self, _label):
            return ScopedPublicationBundle(heads=(), artifacts=(extra, extra))

    with pytest.raises(ExportRefused, match="duplicate artifact IDs"):
        load_scoped_publications(BadStore(), scope)
