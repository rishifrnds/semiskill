"""Canonical scoreboard/progress documents and fail-closed persistence.

The scoreboard is authoritative deterministic JSON. Worker progress is a separate ephemeral
document that references one scoreboard snapshot and can never alter its counts.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path

SCOREBOARD_SCHEMA = "semiskill.scoreboard/v1"
PROGRESS_SCHEMA = "semiskill.progress/v1"


class SnapshotUnavailable(RuntimeError):
    """The configured snapshot source is absent, malformed, or internally inconsistent."""


def _canonical_bytes(document: dict) -> bytes:
    body = deepcopy(document)
    body.pop("snapshot_id", None)
    body.pop("generated_at", None)
    return json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def finalize_scoreboard(body: dict, *, generated_at: str) -> dict:
    """Stamp schema/time and derive an ID unaffected by observation time or mapping order."""
    if not isinstance(body, dict):
        raise ValueError("scoreboard body must be an object")
    document = deepcopy(body)
    document["schema_version"] = SCOREBOARD_SCHEMA
    document["generated_at"] = generated_at
    document["snapshot_id"] = "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()
    _validate_scoreboard(document)
    return document


def _validate_scoreboard(document: object) -> dict:
    if not isinstance(document, dict):
        raise SnapshotUnavailable("scoreboard snapshot must be a JSON object")
    if document.get("schema_version") != SCOREBOARD_SCHEMA:
        raise SnapshotUnavailable("unsupported scoreboard snapshot schema")
    for key, expected in (
        ("snapshot_id", str), ("generated_at", str), ("scope", dict), ("sources", dict),
        ("registry", dict), ("funnel", dict), ("roles", list), ("cells", list),
        ("anomalies", dict), ("release_gate", dict),
    ):
        if not isinstance(document.get(key), expected):
            raise SnapshotUnavailable(f"scoreboard snapshot field {key!r} is missing or invalid")
    expected_id = "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()
    if document["snapshot_id"] != expected_id:
        raise SnapshotUnavailable("scoreboard snapshot_id does not match its canonical content")
    return document


def write_json_atomic(path: str | Path, document: dict) -> Path:
    """Write one complete UTF-8 JSON document or leave the prior file intact."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=target.parent,
        prefix=f".{target.name}.", suffix=".tmp", delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(document, handle, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


def load_scoreboard_snapshot(path: str | Path) -> dict:
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable(f"scoreboard snapshot unavailable: {target}") from exc
    return _validate_scoreboard(document)


def load_progress(path: str | Path, snapshot_id: str) -> dict:
    target = Path(path)
    try:
        document = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotUnavailable(f"progress snapshot unavailable: {target}") from exc
    if not isinstance(document, dict) or document.get("schema_version") != PROGRESS_SCHEMA:
        raise SnapshotUnavailable("unsupported progress snapshot schema")
    if document.get("scoreboard_snapshot_id") != snapshot_id:
        raise SnapshotUnavailable("progress scoreboard_snapshot_id does not match the scoreboard")
    if not isinstance(document.get("generated_at"), str) or not isinstance(document.get("workers"), list):
        raise SnapshotUnavailable("progress snapshot fields are missing or invalid")
    return document
