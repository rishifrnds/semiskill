"""Enumerated facet vocabulary for authored skills.

Facet matching in `catalog_search` (migration 0005) is exact string equality on
`payload->>'function'|'role'|'level'` — case-sensitive, with no validation anywhere. A single typo
(`level: sr`) therefore produces a card that is published, costs a full pipeline run, and appears
under no facet at all. Nothing fails; the skill is simply invisible. This module is the missing
check, enforced by the linter before submission.

Vocabulary source: `specs/ROLE_TAXONOMY.md` §1a (IC ladder), §1b (management ladder) and §2 (Design
& Verification roles), extended with the roles that actually dominate headcount at an EDA-and-IP
company rather than a fabless SoC house — IP verification, VIP development, DV infrastructure and
applications engineering.
"""
from __future__ import annotations

# ── levels ────────────────────────────────────────────────────────────────────
# ROLE_TAXONOMY §1a — IC / technical track, in ladder order.
IC_LEVELS: tuple[str, ...] = (
    "fresher", "junior", "intermediate", "senior", "staff", "senior-staff",
    "principal", "distinguished", "fellow", "architect",
)

# ROLE_TAXONOMY §1b — management / leadership track, in ladder order.
MANAGEMENT_LEVELS: tuple[str, ...] = (
    "lead", "manager", "senior-manager", "director", "senior-director", "vp", "evp", "exec", "board",
)

LEVELS: tuple[str, ...] = IC_LEVELS + MANAGEMENT_LEVELS

# ── functions ─────────────────────────────────────────────────────────────────
# ROLE_TAXONOMY §2–§18. Only `design-verification` is seeded so far; the rest are declared so a
# later wave cannot invent a near-miss spelling of an existing function.
FUNCTIONS: tuple[str, ...] = (
    "design-verification", "physical-design", "analog-mixed-signal", "cad-eda",
    "silicon-validation", "test", "process-fab", "packaging", "reliability-quality",
    "firmware-software", "product", "program", "sales", "marketing", "finance", "hr",
    "payroll", "operations", "it-security", "legal-ip", "executive", "cross-cutting",
)

# ── roles ─────────────────────────────────────────────────────────────────────
# The six already present in the published catalog. Changing any of these strings orphans a
# published skill's facet, so they are frozen.
PUBLISHED_DV_ROLES: tuple[str, ...] = (
    "rtl-designer", "dv-engineer", "soc-architect", "dft-engineer",
    "low-power-engineer", "formal-verification",
)

# Roles the Phase H research found dominate verification headcount at an EDA+IP company.
EXTENDED_DV_ROLES: tuple[str, ...] = (
    "ip-dv-engineer",                  # verifies the company's own sellable IP — largest population
    "vip-engineer",                    # builds the Verification IP that customers buy
    "dv-infra-engineer",               # build, filelists, regression and coverage infrastructure
    "soc-dv-engineer",                 # subsystem / SoC integration verification
    "verification-lead",               # plans, tracks and signs off across blocks
    "applications-engineer",           # deploys methodology to customers; owns escalations
    "emulation-engineer",              # ZeBu / HAPS bring-up and acceleration
    "ams-verification-engineer",       # mixed-signal / real-number modelling
    "static-signoff-engineer",         # lint, CDC/RDC, static sign-off
    "safety-verification-engineer",    # ISO 26262 fault campaigns
    "security-verification-engineer",  # security properties and negative testing
    # Added by the I-001 top-up design (specs/skill_registry.json), which planned five cells each
    # for these three and so made them reachable facets. They are deliberately NOT folded into
    # `ip-dv-engineer`: a memory-IP engineer's failure modes (refresh, timing checks, DFI) and a
    # processor-IP engineer's (ISA step-compare, traps, WARL) share almost no vocabulary, and
    # collapsing them is what produced the facet drift the scoreboard caught.
    "memory-ip-dv-engineer",           # DRAM/SRAM controller and PHY IP verification
    "processor-ip-dv-engineer",        # CPU/DSP core verification — ISA, traps, memory ordering
    "eda-product-validation-engineer", # validates the EDA tools themselves against their own specs
)

DV_ROLES: tuple[str, ...] = PUBLISHED_DV_ROLES + EXTENDED_DV_ROLES
ROLES: tuple[str, ...] = DV_ROLES

# Where a facet value may be written (ADR-008 resolution order).
FACET_KEYS: tuple[str, ...] = ("function", "role", "level")

_VOCAB: dict[str, tuple[str, ...]] = {"function": FUNCTIONS, "role": ROLES, "level": LEVELS}


def allowed(facet: str) -> tuple[str, ...]:
    """The permitted values for one facet key."""
    try:
        return _VOCAB[facet]
    except KeyError:
        raise ValueError(f"unknown facet {facet!r}; expected one of {FACET_KEYS}") from None


def is_valid(facet: str, value) -> bool:
    return isinstance(value, str) and value in _VOCAB.get(facet, ())


def suggest(facet: str, value) -> str | None:
    """Nearest permitted value for a typo, or None. Deliberately conservative — a wrong suggestion
    is worse than none, so it only matches on prefix, containment, or a single-character edit."""
    if not isinstance(value, str) or not value:
        return None
    v = value.strip().lower()
    options = _VOCAB.get(facet, ())
    for o in options:
        if o == v:
            return o
    for o in options:
        if o.startswith(v) or v.startswith(o) or v in o or o in v:
            return o
    for o in options:                       # one substitution / insertion / deletion apart
        if abs(len(o) - len(v)) <= 1 and sum(a != b for a, b in zip(o, v)) <= 1:
            return o
    return None
