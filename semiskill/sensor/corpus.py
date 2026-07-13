"""Client for the held-out injection corpus.

Seeding runs as the OWNER (a restricted-cleared path outside the pipeline). Probing runs under the
restricted `semiskill_pipeline` role, which cannot read the corpus — it can only invoke the SECURITY
DEFINER probe, which returns counts + failing class names, never the patterns. This is the seam that
lets the pipeline be tested against the corpus without ever being able to read it.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable
import psycopg


@dataclass(frozen=True)
class ProbeResult:
    passed: int
    total: int
    failing_classes: tuple[str, ...]


def seed_corpus(dsn: str, probes: Iterable[tuple[str, str]]) -> None:
    """Insert (probe_class, pattern) rows as the owner. NEVER called by pipeline code."""
    with psycopg.connect(dsn) as conn:
        for cls, pattern in probes:
            conn.execute("INSERT INTO injection_corpus (probe_class, pattern) VALUES (%s, %s)",
                         (cls, pattern))
        conn.commit()


def probe_skill(dsn: str, text: str) -> ProbeResult:
    """Run the held-out corpus against untrusted text under the restricted pipeline role."""
    with psycopg.connect(dsn) as conn:
        conn.execute("SET LOCAL ROLE semiskill_pipeline")
        row = conn.execute(
            "SELECT passed, total, failing_classes FROM probe_skill_against_corpus(%s)", (text,)
        ).fetchone()
        conn.rollback()
    passed, total, failing = row
    return ProbeResult(passed=int(passed), total=int(total), failing_classes=tuple(failing or []))
