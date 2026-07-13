"""L6 sensor: turn a measured eval into a queryable error-signal artifact. Ported from
aios/sensor/reading.py.

A sensor_reading carries the measured value (eval_score) + the error signal (setpoint - measured) +
provenance to what it measured (input_refs) and to external truth (ground_truth_ref). Deterministic
sensors pass a real external referent; the SELF_MEASURING sentinel flags a reading with no external
truth (e.g. an LLM judge). Held-out integrity: records the MEASURED VALUE, never the check source.
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass, replace
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore

SELF_MEASURING = "self_measuring"
_RESERVED_KEYS = frozenset({"target", "error_signal", "ground_truth_kind"})


@dataclass(frozen=True)
class Setpoint:
    objective_tag: str
    target: float


def error_signal(setpoint: Setpoint, measured: float) -> float:
    """setpoint - measured (signed, 3 dp). Positive => under target => correction needed."""
    return round(setpoint.target - measured, 3)


def record_sensor_reading(store: ArtifactStore, *, scored_ref: uuid.UUID, setpoint: Setpoint,
                          measured: float, ground_truth_ref: str, permissions_label: str = "team",
                          detail: dict | None = None) -> Artifact:
    """Append a SENSOR_READING. FAIL-CLOSED: raises if ground_truth_ref is blank — a reading must
    declare a real external referent or the SELF_MEASURING sentinel. `detail` extends the payload but
    may not override the sensor's canonical keys."""
    if not isinstance(ground_truth_ref, str) or not ground_truth_ref.strip():
        raise ValueError("ground_truth_ref must be a non-blank external referent or SELF_MEASURING")
    if detail and (_RESERVED_KEYS & detail.keys()):
        raise ValueError(f"detail may not override reserved keys: {sorted(_RESERVED_KEYS & detail.keys())}")
    kind = "self_measuring" if ground_truth_ref == SELF_MEASURING else "external"
    art = Artifact.new(
        artifact_type=ArtifactType.SENSOR_READING, source_system=SourceSystem.CLI,
        actor="sensor", actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=[scored_ref],
        payload={"target": setpoint.target, "error_signal": error_signal(setpoint, measured),
                 "ground_truth_kind": kind, **(detail or {})})
    art = replace(art, permissions_label=permissions_label, objective_tag=setpoint.objective_tag,
                  ground_truth_ref=ground_truth_ref).with_eval_score(measured)
    return store.append(art)
