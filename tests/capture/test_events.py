import uuid
import pytest
from semiskill.artifacts.schema import ArtifactType
from semiskill.capture.events import build_comment, build_rating, build_reuse_event

SV = uuid.uuid4()


def test_comment_references_skill_version():
    c = build_comment(skill_version_id=SV, actor="alice", body="nice skill")
    assert c.artifact_type is ArtifactType.COMMENT
    assert c.input_refs == [SV]
    assert c.payload["body"] == "nice skill"


def test_comment_reply_links_parent():
    parent = uuid.uuid4()
    c = build_comment(skill_version_id=SV, actor="bob", body="agreed", parent_id=parent)
    assert c.input_refs == [SV, parent]
    assert c.payload["parent_id"] == str(parent)


@pytest.mark.parametrize("stars", [1, 3, 5])
def test_rating_valid(stars):
    r = build_rating(skill_version_id=SV, actor="carol", stars=stars)
    assert r.artifact_type is ArtifactType.RATING
    assert r.input_refs == [SV] and r.payload["stars"] == stars


@pytest.mark.parametrize("stars", [0, 6, -1])
def test_rating_out_of_range_rejected(stars):
    with pytest.raises(ValueError):
        build_rating(skill_version_id=SV, actor="carol", stars=stars)


def test_reuse_event():
    e = build_reuse_event(skill_version_id=SV, actor="dave", method="copy-command")
    assert e.artifact_type is ArtifactType.REUSE_EVENT
    assert e.input_refs == [SV] and e.payload["method"] == "copy-command"


def test_permissions_label_applied():
    c = build_comment(skill_version_id=SV, actor="a", body="x", permissions_label="need-to-know")
    assert c.permissions_label == "need-to-know"
