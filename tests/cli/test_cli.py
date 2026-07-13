import io
import pytest
from semiskill.artifacts.schema import Artifact, ArtifactType
from semiskill.cli import main

SKILL_MD = """---
name: STA Timing Closure
slug: pd/sta-closure
version: 0.3.0
function: physical-design
role: sta-engineer
level: senior
---
Body.
"""


class FakeStore:
    def __init__(self):
        self.rows: list[Artifact] = []

    def append(self, a: Artifact) -> Artifact:
        self.rows.append(a)
        return a

    def get(self, aid):
        return next((r for r in self.rows if r.artifact_id == aid), None)

    def by_type(self, t: ArtifactType):
        return [r for r in self.rows if r.artifact_type == t]


@pytest.fixture
def skill_dir(tmp_path):
    (tmp_path / "SKILL.md").write_text(SKILL_MD, encoding="utf-8")
    return tmp_path


def test_submit_appends_skill_version(skill_dir):
    store, out = FakeStore(), io.StringIO()
    rc = main(["submit", str(skill_dir), "--actor", "rishi", "--label", "need-to-know"],
              store=store, out=out)
    assert rc == 0
    assert len(store.rows) == 1
    art = store.rows[0]
    assert art.artifact_type is ArtifactType.SKILL_VERSION
    assert art.payload["slug"] == "pd/sta-closure"
    assert art.permissions_label == "need-to-know"
    assert "submitted pd/sta-closure" in out.getvalue()
    assert "state=submitted" in out.getvalue()


def test_list_shows_submitted(skill_dir):
    store, out = FakeStore(), io.StringIO()
    main(["submit", str(skill_dir)], store=store, out=io.StringIO())
    main(["list"], store=store, out=out)
    assert "pd/sta-closure" in out.getvalue()


def test_list_empty():
    out = io.StringIO()
    main(["list"], store=FakeStore(), out=out)
    assert "no skills submitted yet" in out.getvalue()


def test_invalid_label_rejected(skill_dir):
    with pytest.raises(SystemExit):  # argparse rejects bad choice
        main(["submit", str(skill_dir), "--label", "top-secret"], store=FakeStore(), out=io.StringIO())
