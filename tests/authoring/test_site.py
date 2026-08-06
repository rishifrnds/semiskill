"""Site generator tests.

Three properties matter more than the rest: the site is built only from what published, it contains
no fabricated metric, and it works from a plain folder with no network.
"""
import json
import re
from pathlib import Path

import pytest

from semiskill.artifacts.migrate import apply_migrations
from semiskill.artifacts.store import PostgresArtifactStore
from semiskill.authoring.site import build_site
from tests.support import public_export_scope, publish_wave_sources

MIG = Path("semiskill/artifacts/migrations")
BODY = ("# Title\n\nA procedure with enough substance to be a skill.\n\n"
        "## Fill this in for our team\n\n| Slot | What |\n|---|---|\n"
        "| where | [[FILL: where our logs land]] |\n\n"
        "## Procedure\n\n1. Use **Grep** to locate the marker, then read a bounded window.\n\n"
        "```\nsignature : phase|kind|where|what\n```\n\n"
        "## Gotchas\n\nThe loudest line is rarely the first failure.\n\n"
        "## Human verification\n\nA wrong answer names a cascade line as the cause.\n"
        + "Filler prose to keep this a realistic length. " * 10)


def skill_md(name, *, body=BODY, tools="Read Grep Glob", role="dv-engineer", level="senior"):
    return (f"---\nname: {name}\ndescription: Does {name}. Use when you need {name}.\n"
            f"allowed-tools: {tools}\nmetadata:\n  semiskill-title: Title of {name}\n"
            f"  semiskill-function: design-verification\n  semiskill-role: {role}\n"
            f"  semiskill-level: {level}\n  semiskill-version: 1.0.0\n"
            f"  semiskill-owner: dv-guild\n  semiskill-tags: alpha, beta\n---\n{body}")


@pytest.fixture
def pg_store(pg_dsn):
    apply_migrations(pg_dsn, MIG)
    return PostgresArtifactStore(pg_dsn)


@pytest.fixture
def site(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    for name, role, level in (("dv-alpha", "dv-engineer", "senior"),
                              ("dv-beta", "dv-infra-engineer", "junior"),
                              ("dv-gamma", "dv-engineer", "junior")):
        d = root / name
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(skill_md(name, role=role, level=level), encoding="utf-8")
    fixtures = publish_wave_sources(pg_store, root)
    return build_site(
        store=pg_store, out_dir=tmp_path / "site",
        scope=public_export_scope(pg_store, fixtures, generated_at="2026-08-05T00:00:00Z"),
    )


def read(res, rel):
    return (res.root / rel).read_text(encoding="utf-8")


# ── shape ─────────────────────────────────────────────────────────────────────

def test_every_expected_page_is_written(site):
    for rel in ("index.html", "matrix.html", "install.html", "assets/site.css",
                "catalog.md", "catalog.csv",
                "skills/dv-alpha.html", "skills/dv-beta.html",
                "roles/dv-engineer.html", "roles/dv-infra-engineer.html"):
        assert (site.root / rel).exists(), f"missing {rel}"


def test_index_lists_every_published_skill_with_a_link(site):
    idx = read(site, "index.html")
    for slug in ("dv-alpha", "dv-beta", "dv-gamma"):
        assert f'href="skills/{slug}.html"' in idx


def test_skill_page_has_the_install_block_and_the_real_scan_report(site):
    page = read(site, "skills/dv-alpha.html")
    assert "Copy install prompt" in page
    assert ".cursor/skills/dv-alpha/SKILL.md" in page
    assert "stage 1" in page and "stage 3" in page and "stage 4" in page
    assert "1.000" in page and "approve" in page


def test_skill_page_renders_the_body_as_html_not_a_blob(site):
    page = read(site, "skills/dv-alpha.html")
    assert "<h2>Title</h2>" in page                       # heading demoted by the renderer
    assert "<table>" in page and "<pre><code>" in page
    assert 'class="fill"' in page                         # the [[FILL:]] slot is surfaced


def test_related_skills_link_within_the_same_role(site):
    page = read(site, "skills/dv-alpha.html")
    assert "More in dv-engineer" in page
    assert 'href="dv-gamma.html"' in page                 # same role
    assert 'href="dv-beta.html"' not in page              # different role


def test_matrix_cells_link_to_skills(site):
    m = read(site, "matrix.html")
    assert 'href="skills/dv-alpha.html"' in m
    assert 'class="off"' in m                             # an empty cell exists and is marked


def test_role_page_lists_only_that_role(site):
    page = read(site, "roles/dv-infra-engineer.html")
    assert "dv-beta" in page and "dv-alpha" not in page


# ── the properties that matter ────────────────────────────────────────────────

def test_an_unpublished_skill_never_reaches_the_site(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    allowed = root / "dv-ok"
    allowed.mkdir(parents=True)
    (allowed / "SKILL.md").write_text(skill_md("dv-ok"), encoding="utf-8")
    fixtures = publish_wave_sources(pg_store, root)
    blocked = root / "dv-blocked"
    blocked.mkdir()
    (blocked / "SKILL.md").write_text(skill_md("dv-blocked", tools="Read Bash"), encoding="utf-8")

    res = build_site(
        store=pg_store, out_dir=tmp_path / "site",
        scope=public_export_scope(pg_store, fixtures),
    )
    assert {e.slug for e in res.entries} == {"dv-ok"}
    assert not (res.root / "skills" / "dv-blocked.html").exists()
    assert "dv-blocked" not in (res.root / "index.html").read_text(encoding="utf-8")


# `ui/catalog-demo.html` shipped "1.3k installs · ★ 4.8" and an invented approver. We have no
# install telemetry at all, so any adoption-shaped number here would be fabricated.
_FABRICATED = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:k|m)?\s+(?:installs?|downloads?|stars?|users?)"
    r"|★|⭐|rating|trending|most[- ]installed", re.I)


def test_no_page_carries_a_fabricated_metric(site):
    for page in site.pages:
        if page.endswith((".html", ".md")):
            hit = _FABRICATED.search(read(site, page))
            assert not hit, f"{page} carries a fabricated metric: {hit.group(0)!r}"


def test_pages_are_self_contained_with_no_network(site):
    for page in site.pages:
        if not page.endswith(".html"):
            continue
        text = read(site, page)
        assert "http://" not in text and "https://" not in text, f"{page} reaches the network"
        assert "fetch(" not in text and "cdn" not in text.lower()


def test_links_are_relative_so_the_folder_can_move(site):
    """It will be zipped, emailed, and opened from a download folder — absolute paths break all three."""
    for page in site.pages:
        if not page.endswith(".html"):
            continue
        for href in re.findall(r'(?:href|src)="([^"]+)"', read(site, page)):
            assert not href.startswith(("/", "file://", "http")), f"{page} -> {href}"


def test_every_internal_link_resolves(site):
    for page in site.pages:
        if not page.endswith(".html"):
            continue
        base = (site.root / page).parent
        for href in re.findall(r'href="([^"#?]+)"', read(site, page)):
            assert (base / href).resolve().exists(), f"{page} -> {href} is a dead link"


def test_a_hostile_body_stays_inert_on_its_page(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-hostile"
    d.mkdir(parents=True)
    # No URL in the body: a bare http link scores 0.3 at stage 1, so the skill would never publish
    # and there would be no page to attack. The hostile content has to be the markup itself.
    nasty = BODY + ('\nA body with </script><script>window.pwned=1</script> and '
                    '<img src=x onerror=alert(1)> and [a link](evil.html).\n')
    (d / "SKILL.md").write_text(skill_md("dv-hostile", body=nasty), encoding="utf-8")
    fixtures = publish_wave_sources(pg_store, root)

    res = build_site(
        store=pg_store, out_dir=tmp_path / "site",
        scope=public_export_scope(pg_store, fixtures),
    )
    page = (res.root / "skills" / "dv-hostile.html").read_text(encoding="utf-8")
    # The page owns exactly two script blocks. The body cannot add or close one: `</` is neutralised
    # inside the JSON, and the rendered section escapes every tag.
    assert page.count("</script>") == 2
    rendered = page.split('<section class="rendered">')[1].split("</section>")[0]
    assert "<img" not in rendered and "<script" not in rendered
    assert "&lt;script&gt;" in rendered and "&lt;img" in rendered
    assert "evil.html" in rendered and 'href="evil.html"' not in rendered
    # the embedded JSON block cannot be terminated by the body
    payload = page.split('id="skill-data" type="application/json">')[1].split("</script>")[0]
    assert "</" not in payload
    assert json.loads(payload.replace("<\\/", "</"))["skill_md"]


def test_generation_is_deterministic(pg_store, pg_dsn, tmp_path):
    root = tmp_path / "skills"
    d = root / "dv-a"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(skill_md("dv-a"), encoding="utf-8")
    fixtures = publish_wave_sources(pg_store, root)

    scope = public_export_scope(pg_store, fixtures)
    a = build_site(store=pg_store, out_dir=tmp_path / "s1", scope=scope)
    b = build_site(store=pg_store, out_dir=tmp_path / "s2", scope=scope)
    assert a.pages == b.pages
    for page in a.pages:
        assert (a.root / page).read_text(encoding="utf-8") == (b.root / page).read_text(encoding="utf-8")


def test_site_states_the_limits_of_the_badge(site):
    idx = read(site, "index.html")
    assert "not a runtime guarantee" in idx and "does not enforce" in idx
