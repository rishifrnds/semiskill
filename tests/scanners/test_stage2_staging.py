"""ADR-024 Stage 2 — host-side staging projection and hostile-config containment.

Every byte of a submission is untrusted payload. The trusted host, not the container, decides what
reaches the scanner and what the expected coverage set is. These tests are the adversarial half of
that contract: a payload must not be able to escape the staging root, silence the scanner, or make
the host's idea of "every file" disagree with what is actually on disk.
"""
from pathlib import Path

import pytest

from semiskill.scanners.base import SkillSubmission
from semiskill.scanners.stage2_staging import (
    ISOLATED_CONFIG_NAMES,
    Stage2Refused,
    project_payload,
)


def _submission(files=None, body="# Title\n\nA procedure.\n"):
    return SkillSubmission(
        slug="dv-example", name="dv-example", body=body, files=dict(files or {}),
    )


def test_skill_md_is_always_projected_and_always_expected(tmp_path):
    """The Markdown body governs agent behaviour; missing it is the old runner's core defect."""
    staged = project_payload(_submission(), root=tmp_path / "stage")

    assert "SKILL.md" in staged.expected_files
    assert (staged.root / "SKILL.md").read_text(encoding="utf-8").startswith("# Title")


def test_expected_files_match_what_is_actually_on_disk_exactly(tmp_path):
    staged = project_payload(
        _submission({"refs/a.txt": "a", "refs/nested/b.txt": "b"}), root=tmp_path / "stage",
    )

    on_disk = sorted(
        p.relative_to(staged.root).as_posix()
        for p in staged.root.rglob("*") if p.is_file()
    )
    assert list(staged.expected_files) == on_disk
    assert set(staged.expected_files) == {"SKILL.md", "refs/a.txt", "refs/nested/b.txt"}


@pytest.mark.parametrize("hostile", [
    "/etc/passwd",                  # absolute POSIX
    "C:/Windows/system32/x.txt",    # absolute Windows
    "C:\\Windows\\system32\\x.txt",
    "../escape.txt",                # parent traversal
    "refs/../../escape.txt",        # traversal after a valid segment
    "refs/./../../escape.txt",
    "..\\escape.txt",               # backslash traversal
    "refs\\..\\..\\escape.txt",
    "",                             # empty
    ".",
    "..",
    "refs/",                        # directory, not a file
    "a\x00b.txt",                   # NUL injection
])
def test_paths_that_could_escape_the_staging_root_are_refused(tmp_path, hostile):
    with pytest.raises(Stage2Refused):
        project_payload(_submission({hostile: "payload"}), root=tmp_path / "stage")


def test_a_refused_payload_leaves_nothing_written_outside_the_root(tmp_path):
    outside = tmp_path / "escape.txt"
    with pytest.raises(Stage2Refused):
        project_payload(_submission({"../escape.txt": "owned"}), root=tmp_path / "stage")
    assert not outside.exists()


@pytest.mark.parametrize("name", sorted(ISOLATED_CONFIG_NAMES))
def test_payload_controlled_scanner_config_is_isolated_not_scanned(tmp_path, name):
    """A payload that ships its own ignore/config file could silence the scanner about itself."""
    staged = project_payload(_submission({name: "*"}), root=tmp_path / "stage")

    assert name in staged.isolated
    assert name not in staged.expected_files
    assert not (staged.root / name).exists()


def test_isolated_config_in_a_subdirectory_is_also_contained(tmp_path):
    staged = project_payload(_submission({"refs/.semgrepignore": "*"}), root=tmp_path / "stage")

    assert "refs/.semgrepignore" in staged.isolated
    assert "refs/.semgrepignore" not in staged.expected_files
    assert not (staged.root / "refs" / ".semgrepignore").exists()


def test_isolation_is_recorded_rather_than_silently_dropped(tmp_path):
    """Silent containment is indistinguishable from a coverage hole in the audit trail."""
    staged = project_payload(
        _submission({".semgrepignore": "*", "refs/a.txt": "a"}), root=tmp_path / "stage",
    )

    assert staged.isolated == (".semgrepignore",)
    assert "refs/a.txt" in staged.expected_files


def test_projection_refuses_a_non_empty_existing_root(tmp_path):
    """Staging is scanner-owned. Reusing a dirty root would scan someone else's bytes."""
    root = tmp_path / "stage"
    root.mkdir(parents=True)
    (root / "leftover.txt").write_text("stale", encoding="utf-8")

    with pytest.raises(Stage2Refused):
        project_payload(_submission(), root=root)


def test_duplicate_paths_differing_only_by_separator_are_refused(tmp_path):
    with pytest.raises(Stage2Refused):
        project_payload(
            _submission({"refs/a.txt": "a", "refs\\a.txt": "b"}), root=tmp_path / "stage",
        )


def test_expected_files_are_sorted_so_coverage_comparison_is_deterministic(tmp_path):
    staged = project_payload(
        _submission({"z.txt": "z", "a.txt": "a", "m/b.txt": "b"}), root=tmp_path / "stage",
    )

    assert list(staged.expected_files) == sorted(staged.expected_files)


def test_non_string_file_content_is_refused(tmp_path):
    with pytest.raises(Stage2Refused):
        project_payload(_submission({"a.txt": 42}), root=tmp_path / "stage")
