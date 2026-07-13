from __future__ import annotations
from typing import Iterable


def resolve_allowed_labels(principal: Iterable[str]) -> tuple[str, ...]:
    """The single place that decides which permission labels a caller may see. For now `principal`
    IS the caller's iterable of labels; this normalizes them (dedup, ordered tuple) and is the one
    seam to extend when a real principal->labels mapping (roles/groups/identity) arrives. Every L3
    retrieval and provenance path resolves through here so they cannot drift. Fails closed on an
    empty clearance."""
    labels = tuple(sorted(set(principal)))
    if not labels:
        raise ValueError("principal resolves to no permission labels")
    return labels
