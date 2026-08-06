import subprocess

import pytest

from semiskill.governance.identity import (
    IdentityRefused,
    entra_identity,
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
