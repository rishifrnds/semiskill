import subprocess

import pytest

from semiskill.governance.identity import (
    AuthenticatedHuman,
    IdentityRefused,
    entra_identity,
    identity_from_authentication,
    local_os_identity,
)


def test_windows_local_identity_comes_from_whoami_sid_not_environment(monkeypatch):
    monkeypatch.setenv("USERNAME", "forged-env-user")

    def runner(*_args, **_kwargs):
        return subprocess.CompletedProcess([], 0, '"RISHI_PC\\rishi","S-1-5-21-real"\n', "")

    identity = local_os_identity(system="Windows", runner=runner)
    assert identity.actor == "RISHI_PC\\rishi"
    assert identity.subject == "S-1-5-21-real" and identity.provider == "local_os"


def test_production_without_entra_adapter_fails_closed():
    with pytest.raises(IdentityRefused, match="not configured"):
        entra_identity(assertion="signed", verifier=None,
                       expected_issuer="issuer", expected_tenant="tenant")


def test_wrong_entra_tenant_or_issuer_is_rejected():
    class Verifier:
        def verify(self, _assertion):
            return {"iss": "wrong", "tid": "wrong", "oid": "object", "name": "Alice"}

    with pytest.raises(IdentityRefused, match="issuer or tenant"):
        entra_identity(assertion="signed", verifier=Verifier(),
                       expected_issuer="issuer", expected_tenant="tenant")


def test_verified_entra_identity_keeps_only_nonsecret_allowlisted_context():
    class Verifier:
        def verify(self, _assertion):
            return {"iss": "issuer", "tid": "tenant", "oid": "object", "name": "Alice",
                    "amr": ["mfa"], "access_token": "must-not-survive"}

    identity = entra_identity(assertion="signed-secret", verifier=Verifier(),
                              expected_issuer="issuer", expected_tenant="tenant")
    assert identity.provider == "entra_oidc" and identity.subject == "object"
    assert "access_token" not in identity.auth_context and identity.auth_context["amr"] == ["mfa"]


@pytest.mark.parametrize("field", ["issuer", "tenant"])
def test_entra_policy_must_be_configured_before_verifier_runs(field):
    called = False

    class Verifier:
        def verify(self, _assertion):
            nonlocal called
            called = True
            return {}

    kwargs = {"expected_issuer": "issuer", "expected_tenant": "tenant"}
    kwargs[f"expected_{field}"] = ""
    with pytest.raises(IdentityRefused, match="not configured"):
        entra_identity(assertion="signed", verifier=Verifier(), **kwargs)
    assert called is False


def test_entra_identity_subject_must_match_object_id():
    with pytest.raises(IdentityRefused, match="object ID"):
        AuthenticatedHuman(
            actor="Alice",
            subject="different-object",
            provider="entra_oidc",
            auth_context={"issuer": "issuer", "tenant_id": "tenant", "object_id": "object"},
        )


def test_persisted_authentication_binds_actor_and_production_tenant():
    authentication = {
        "provider": "entra_oidc",
        "actor": "Alice",
        "subject": "object",
        "context": {"issuer": "issuer", "tenant_id": "tenant", "object_id": "object"},
    }
    identity = identity_from_authentication(
        authentication,
        artifact_actor="Alice",
        environment="production",
        expected_entra_issuer="issuer",
        expected_entra_tenant="tenant",
    )
    assert identity.subject == "object"
    with pytest.raises(IdentityRefused, match="tenant"):
        identity_from_authentication(
            authentication,
            artifact_actor="Alice",
            environment="production",
            expected_entra_issuer="issuer",
            expected_entra_tenant="other-tenant",
        )


@pytest.mark.parametrize("provider", [None, [], {}, 7, True])
def test_malformed_persisted_provider_is_normalized_to_identity_refusal(provider):
    with pytest.raises(IdentityRefused, match="unsupported identity provider"):
        identity_from_authentication(
            {
                "provider": provider,
                "actor": "Alice",
                "subject": "object",
                "context": {"issuer": "issuer", "tenant_id": "tenant", "object_id": "object"},
            },
            artifact_actor="Alice",
            environment="development",
        )


@pytest.mark.parametrize("context", [None, [], "claims", 1, True])
def test_malformed_persisted_context_is_normalized_to_identity_refusal(context):
    with pytest.raises(IdentityRefused, match="context must be an object"):
        identity_from_authentication(
            {
                "provider": "entra_oidc",
                "actor": "Alice",
                "subject": "object",
                "context": context,
            },
            artifact_actor="Alice",
            environment="development",
        )


@pytest.mark.parametrize("environment", [None, [], {}, 7, True])
def test_malformed_persisted_environment_is_normalized_to_identity_refusal(environment):
    with pytest.raises(IdentityRefused, match="unknown identity environment"):
        identity_from_authentication(
            {
                "provider": "local_os",
                "actor": "Alice",
                "subject": "uid:42",
                "context": {"account": "Alice", "uid": 42},
            },
            artifact_actor="Alice",
            environment=environment,
        )
