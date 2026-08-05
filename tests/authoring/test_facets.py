import json
import re
from pathlib import Path

import pytest

from semiskill.authoring import facets

ROOT = Path(__file__).resolve().parents[2]


def test_published_seed_facets_are_all_in_the_vocabulary():
    """The eight already-published DV seeds must remain reachable. If a facet string here ever
    drifts from what was published, those cards fall out of faceted browse silently."""
    fixture = json.loads((ROOT / "tests" / "seed" / "fixtures" / "generated_seeds.json")
                         .read_text(encoding="utf-8"))
    for seed in fixture:
        md = seed["skill_md"]
        for key in ("function", "role", "level"):
            m = re.search(rf"^{key}:\s*(.+)$", md, re.M)
            assert m, f"{seed['slug']} has no {key}"
            value = m.group(1).strip()
            assert facets.is_valid(key, value), f"{seed['slug']} {key}={value!r} not in vocabulary"


def test_levels_cover_both_ladders():
    assert "fresher" in facets.LEVELS and "principal" in facets.LEVELS      # IC
    assert "senior-manager" in facets.LEVELS and "director" in facets.LEVELS  # management
    assert len(set(facets.LEVELS)) == len(facets.LEVELS), "duplicate level"


def test_no_duplicate_roles_or_functions():
    for seq in (facets.ROLES, facets.FUNCTIONS):
        assert len(set(seq)) == len(seq)


def test_vocabulary_is_kebab_case():
    for facet in facets.FACET_KEYS:
        for value in facets.allowed(facet):
            assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", value), f"{facet}={value!r} not kebab"


@pytest.mark.parametrize("facet,value", [
    ("level", "senior"), ("role", "dv-engineer"), ("function", "design-verification"),
])
def test_is_valid_accepts_known(facet, value):
    assert facets.is_valid(facet, value)


@pytest.mark.parametrize("facet,value", [
    ("level", "sr"), ("level", "Senior"), ("role", "dv engineer"), ("function", "dv"), ("level", None),
])
def test_is_valid_rejects_unknown(facet, value):
    assert not facets.is_valid(facet, value)


@pytest.mark.parametrize("facet,typo,expected", [
    ("level", "senio", "senior"),
    ("level", "Senior", "senior"),
    ("role", "dv-enginer", "dv-engineer"),
    ("function", "design-verificatio", "design-verification"),
])
def test_suggest_finds_the_near_miss(facet, typo, expected):
    assert facets.suggest(facet, typo) == expected


def test_suggest_returns_none_when_nothing_is_close():
    assert facets.suggest("level", "zzzz") is None


def test_allowed_rejects_an_unknown_facet_key():
    with pytest.raises(ValueError):
        facets.allowed("seniority")
