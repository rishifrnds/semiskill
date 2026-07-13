from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.secret_pii import SecretPiiScanner

SC = SecretPiiScanner()


def _sub(body="# Clean skill\nNo secrets here.", files=None):
    return SkillSubmission(slug="dv/x", name="X", body=body, files=files or {}, allowed_tools=())


def _codes(r):
    return {f.code for f in r.findings}


def test_benign_is_clean():
    r = SC.scan(_sub())
    assert r.safety_score == 1.0 and r.hard_fail is False


def test_aws_key_hardfails():
    r = SC.scan(_sub(body="key = AKIAIOSFODNN7EXAMPLE"))
    assert r.hard_fail is True and "aws-access-key" in _codes(r)


def test_private_key_hardfails():
    r = SC.scan(_sub(files={"id_rsa": "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n"}))
    assert r.hard_fail is True and "private-key" in _codes(r)


def test_credential_assignment_hardfails():
    r = SC.scan(_sub(body='password = "hunter2superlongsecret"'))
    assert r.hard_fail is True and "credential-assignment" in _codes(r)


def test_github_token_hardfails():
    r = SC.scan(_sub(body="ghp_" + "a" * 36))
    assert r.hard_fail is True and "github-token" in _codes(r)


def test_internal_url_soft_flag():
    r = SC.scan(_sub(body="see https://wiki.corp.internal/page"))
    assert "internal-url" in _codes(r) and r.hard_fail is False


def test_ssn_flagged():
    r = SC.scan(_sub(body="employee ssn 123-45-6789"))
    assert "ssn" in _codes(r)
