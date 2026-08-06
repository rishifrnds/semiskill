"""Fail-closed, non-crediting dashboard request queue.

Browser requests select a server-owned template. They never supply executable prose and queue
receipts are deliberately outside the SemiSkill artifact/publication authority chain.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import math
import os
import re
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ACTION_REQUEST_SCHEMA = "semiskill.dashboard-action/v1"
ARCHIVE_REQUEST_SCHEMA = "semiskill.dashboard-archive/v1"
QUEUE_ROW_SCHEMA = "semiskill.dashboard-request/v1"
RECEIPT_SCHEMA = "semiskill.dashboard-receipt/v1"
ARCHIVE_RECEIPT_SCHEMA = "semiskill.dashboard-archive-receipt/v1"
TEMPLATE_SCHEMA = "semiskill.dashboard-template/v1"
DASHBOARD_MODEL_SCHEMA = "semiskill.dashboard-model/v1"

_ACTION_FIELDS = frozenset({
    "schema_version", "request_type", "template_id", "priority", "context", "request_id",
})
_ARCHIVE_FIELDS = frozenset({"schema_version", "request_id"})
_PRIORITIES = frozenset({"low", "normal", "high", "urgent"})
_CONTEXTS = frozenset({
    "overview", "architecture", "pipeline", "features", "quality", "security", "catalog",
    "launch", "growth", "analytics", "queue",
})
_TEMPLATE_ID = re.compile(r"^A-\d{2,4}$")
_ACTION_RECEIPT_ID = re.compile(r"^ACT-[0-9a-f]{32}$")
_ARCHIVE_ID = re.compile(r"^ARC-[0-9a-f]{32}$")
_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_UTC_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$"
)
_ARCHIVE_DATA_NAME = re.compile(
    r"^inbox-(\d{8}T\d{12}Z)-([0-9a-f]{32})\.jsonl$"
)
_MODEL_MANIFEST = re.compile(r"^sha256:[0-9a-f]{64}\r?\n$")
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 20_000

_ROOT_MODEL_FIELDS = frozenset({
    "schema_version", "_comment", "project", "register_authority", "layers",
    "pipeline_stages", "lifecycle", "features", "risks", "deferred_scope",
    "launch_checklist", "gtm", "actions",
})
_REGISTER_AUTHORITY = {
    "features": "curated_non_crediting",
    "risks": "curated_non_crediting",
    "launch_plan": "curated_non_crediting",
    "gtm": "unvalidated_hypotheses",
}
_APPROVED_ACTION_TEMPLATE_SHA256 = {
    "A-01": "sha256:a2c9f9adbf4c23d9bcb4fee35ea5969646bf0dd1e945dd6b6599c38d8bbfd08e",
    "A-02": "sha256:bf9432a59d5915904ae4aa748432ee72ca7cee4bec1143d7e0ed39f86c1ebf4d",
    "A-03": "sha256:ee2fe54892aa357a4cec4a4b7c850103b37dcd14e5fa353fa547b9e0673f4860",
    "A-04": "sha256:acb04e6560c8a8ac2f11237f88145cadc9dea1ec7d99f7e06baf2c88973e55cc",
    "A-05": "sha256:b7366e286a63a3b084c5e943c03f3bf6390b8ae938bc861a8e2dc7fb163dcf5c",
    "A-06": "sha256:9f0c4496c708e2609daf4ca842a7e6e43445b14fc11f1e5eb287342b4b6863fc",
    "A-07": "sha256:d729406024b16c41dbf7f42d85db7f632c9e2adb356c588c0e1e5488ff7dc726",
    "A-08": "sha256:dfe27ad7789ce570357627fe6c88f6ccfc98a6b1f9c9a1a8efca4e81f4121a46",
    "A-09": "sha256:471b7902aecfabd91b1412caa5a12447dc05808df1f0c1830369ce2a2f1c533f",
    "A-10": "sha256:716c75e98f3f56344a14a9bd82e3d3d4cbcd58f0025b7faab2620dfcf4564a31",
    "A-11": "sha256:0913d4070cf9ab065b3255b316e99d60c0d00c0eb16c3da17522d2f0d3942624",
    "A-12": "sha256:0f05c1e3f1e447fa14e28ce5919a5e965c9802d2309c791e9001c421863fff6e",
    "A-13": "sha256:e5fcd34ae1a298226bbd34db23bf672d1f4c6421b5170f7788a9bce3ee1e21db",
    "A-14": "sha256:14bd691bdc5e281efcd5470eca603174737811d40a6c7b1a299d1fcda9162d53",
    "A-15": "sha256:896c43f4bd7a0bef8d8af3153d212a4e0ec86087f7619483f5200359862508b2",
    "A-16": "sha256:6c57aa2ef6d140d51808212bafc57d2bf8cdd748dc732679529097dabd75fe89",
    "A-17": "sha256:f3f8e7b2b9bbe419d7187ed7224be6822a458035e8148a1de6bc64cec6548552",
    "A-18": "sha256:778c849ec464cb3cc7d0ef538d62f38a65237a71858761c2cf1f8624b81f1f87",
    "A-19": "sha256:63e258dfc40caf792a70c67632f1b631c96cd8abe63c6bdb93918b029ab46494",
    "A-20": "sha256:2225996a83ff4b74162ea6c977939618a238e1de10e102d3d50d2ea80faf7c96",
    "A-21": "sha256:8e5f07fef9265b00e9cb1245b68979f0d5b78d8dcdc3de2fab246182fe6ecdfa",
    "A-22": "sha256:53c49dee70c5d11705da3c06772a01956a567487020a1a039747c58eef5f713f",
    "A-23": "sha256:1211c39a25d74427c99b879189902d6dd552139ea97bdd8abd28b348786c16a1",
    "A-24": "sha256:4ce3bf9ab7ede7e137229ab9759786585a01b253513002dd28028c0c3dd429a3",
    "A-25": "sha256:95bee47c85e460dda44885bee2cb074263a14b5fbab780e268eec646c27b63b6",
    "A-26": "sha256:52f353accf771f819d1763d51130e7cdfe07228ac2734a2c50ea071ae14b5bec",
    "A-27": "sha256:bc36251cbd166e339e89745b31e69d53503fff7ae48ff5ee927c151598c06f20",
    "A-28": "sha256:9edd1539b87b1d8eefc1f252510e746ddcfb66ea07554ff93f55f7694050285f",
    "A-29": "sha256:a5964e4519d31a49bcbba038631181377e0d335a2625eef9e58f60a750314c6f",
    "A-30": "sha256:de432f3a0932df5656acd13702254a07494e39335112f5de037ea224893a4ab0",
    "A-31": "sha256:7d7b0a1b4b7b5bf8eff85da0bdd6a70d1582a2f9cdc81a32004e2e644b5ca9b3",
    "A-32": "sha256:19d3162144beab813dccc839524cebe2a06c8736ca364445dd6f25dd24c24ead",
    "A-33": "sha256:0a0df90985c636e1cab3ea9bef7017921a0268d76bb42db5a574e9d43a1e641e",
    "A-34": "sha256:0f2ecca1511f97cbbd1899a2b058749979c5090db8523cc6f55941433112cb5c",
    "A-35": "sha256:e434398b0946f21fe24df0e7864965bb773cea3ca3ea3814145768d3de11074c",
    "A-36": "sha256:b505188bc1693eae92cda3c27b7c2e054d7c4eb34c06f3e6cd25829f1f4a0f0c",
}


class QueueError(RuntimeError):
    status = 503
    code = "queue_unavailable"


class QueueUnavailable(QueueError):
    pass


class QueueConflict(QueueError):
    status = 409
    code = "request_id_conflict"


class QueueValidationError(QueueError):
    status = 422
    code = "invalid_request"


class DuplicateJSONKey(ValueError):
    pass


@dataclass(frozen=True)
class LoadedDashboardModel:
    sha256: str
    model: dict[str, Any]
    templates: dict[str, dict[str, Any]]


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite number: {value}")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKey(key)
        result[key] = value
    return result


def strict_json_loads(text: str) -> Any:
    try:
        value = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except RecursionError as exc:
        raise ValueError("JSON structure exceeds limits") from exc
    stack: list[tuple[Any, int]] = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if depth > _MAX_JSON_DEPTH or nodes > _MAX_JSON_NODES:
            raise ValueError("JSON structure exceeds limits")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
    return value


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _validate_utc_timestamp(value: Any, *, label: str) -> str:
    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        raise QueueUnavailable(f"invalid {label} timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise QueueUnavailable(f"invalid {label} timestamp") from exc
    if parsed.utcoffset() != timedelta(0):
        raise QueueUnavailable(f"invalid {label} timestamp")
    return value


def _plain_text(value: Any, *, field: str, maximum: int) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise QueueUnavailable(f"invalid template {field}")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise QueueUnavailable(f"invalid template {field}")
    return value


def _canonical_uuid(value: Any) -> str:
    if not isinstance(value, str):
        raise QueueValidationError("request_id must be a UUID")
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError) as exc:
        raise QueueValidationError("request_id must be a UUID") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise QueueValidationError("request_id must be a canonical UUIDv4")
    return value


def _templates_from_model(model: dict[str, Any]) -> dict[str, dict[str, Any]]:
    templates: dict[str, dict[str, Any]] = {}
    for source in model["actions"]:
        if not isinstance(source, dict) or set(source) != {"id", "group", "label", "prompt"}:
            raise QueueUnavailable("invalid template registry")
        template_id = source["id"]
        if not isinstance(template_id, str) or not _TEMPLATE_ID.fullmatch(template_id):
            raise QueueUnavailable("invalid template id")
        if template_id in templates:
            raise QueueUnavailable("duplicate template id")
        template = {
            "schema_version": TEMPLATE_SCHEMA,
            "template_id": template_id,
            "template_version": 1,
            "group": _plain_text(source["group"], field="group", maximum=80),
            "title": _plain_text(source["label"], field="label", maximum=300),
            "prompt": _plain_text(source["prompt"], field="prompt", maximum=8_000),
        }
        template["template_sha256"] = _sha256(_canonical_bytes(template))
        templates[template_id] = template
    if not templates:
        raise QueueUnavailable("template registry empty")
    return templates


def _load_model_manifest(path: Path) -> str:
    try:
        raw = path.read_bytes()
        text = raw.decode("ascii", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise QueueUnavailable("template manifest unavailable") from exc
    if not _MODEL_MANIFEST.fullmatch(text):
        raise QueueUnavailable("template manifest invalid")
    return text.rstrip("\r\n")


def _exact_record(value: Any, fields: set[str] | frozenset[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValueError("invalid dashboard model record")
    return value


def _text(value: Any, *, maximum: int = 10_000) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError("invalid dashboard model text")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError("invalid dashboard model text")
    return value


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not value:
        raise ValueError("invalid dashboard model text list")
    for item in value:
        _text(item)
    return value


def _records(
    value: Any,
    fields: set[str] | frozenset[str],
    *,
    id_field: str | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        raise ValueError("invalid dashboard model list")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in value:
        record = _exact_record(item, fields)
        if id_field is not None:
            identifier = _text(record[id_field], maximum=100)
            if identifier in seen:
                raise ValueError("duplicate dashboard model id")
            seen.add(identifier)
        result.append(record)
    return result


def _number(value: Any, *, minimum: float = 0) -> float | int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
    ):
        raise ValueError("invalid dashboard model number")
    return value


def _integer(value: Any, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError("invalid dashboard model integer")
    return value


def _validate_deferred_ref(value: Any, deferred_ids: set[str]) -> None:
    if value is not None and (not isinstance(value, str) or value not in deferred_ids):
        raise ValueError("invalid deferred scope reference")


def _validate_dashboard_model(model: Any) -> None:
    root = _exact_record(model, _ROOT_MODEL_FIELDS)
    if root["schema_version"] != DASHBOARD_MODEL_SCHEMA:
        raise ValueError("unsupported dashboard model schema")
    _text(root["_comment"])

    project = _exact_record(
        root["project"],
        {"name", "tagline", "one_liner", "architecture", "repo", "started", "stage"},
    )
    for value in project.values():
        _text(value)
    if project["stage"] != "local-pre-alpha":
        raise ValueError("invalid project stage")

    if root["register_authority"] != _REGISTER_AUTHORITY:
        raise ValueError("invalid register authority")

    layers = _records(root["layers"], {"id", "name", "modules", "role", "color"}, id_field="id")
    if [item["id"] for item in layers] != [f"L{number}" for number in range(1, 7)]:
        raise ValueError("invalid layer sequence")
    for item in layers:
        for field in ("name", "role"):
            _text(item[field])
        if not isinstance(item["color"], str) or not _HEX_COLOR.fullmatch(item["color"]):
            raise ValueError("invalid layer color")
        _text_list(item["modules"])

    stages = _records(
        root["pipeline_stages"],
        {"n", "id", "name", "module", "kind", "declared_state", "coverage_contract", "detail"},
        id_field="id",
    )
    if [item["n"] for item in stages] != list(range(1, 7)) or any(
        isinstance(item["n"], bool) or not isinstance(item["n"], int) for item in stages
    ):
        raise ValueError("invalid pipeline sequence")
    for item in stages:
        for field in ("name", "module", "coverage_contract", "detail"):
            _text(item[field])
        if item["kind"] not in {"deterministic", "external-skill", "model"}:
            raise ValueError("invalid pipeline kind")
        if item["declared_state"] not in {"source-present", "external-adapter-pending"}:
            raise ValueError("invalid pipeline declared state")

    if root["lifecycle"] != ["submitted", "scanned", "reviewed", "approved", "published"]:
        raise ValueError("invalid lifecycle")

    features = _records(
        root["features"],
        {"id", "layer", "name", "declared_status", "source_ref", "note"},
        id_field="id",
    )
    for item in features:
        for field in ("layer", "name", "source_ref", "note"):
            _text(item[field])
        if item["layer"] not in {*{f"L{number}" for number in range(1, 7)}, "Ops", "Product"}:
            raise ValueError("invalid feature layer")
        if item["declared_status"] not in {"done", "partial", "gap", "by-design-off"}:
            raise ValueError("invalid feature declared status")

    risks = _records(
        root["risks"],
        {"id", "title", "severity_hypothesis", "area", "validation_status", "detail", "mitigation"},
        id_field="id",
    )
    for item in risks:
        for field in ("title", "area", "detail", "mitigation"):
            _text(item[field])
        if item["severity_hypothesis"] not in {"critical", "high", "medium", "low"}:
            raise ValueError("invalid risk hypothesis")
        if item["validation_status"] != "unvalidated":
            raise ValueError("invalid risk validation status")

    deferred = _records(
        root["deferred_scope"],
        {"id", "scope", "status", "credit", "preconditions"},
        id_field="id",
    )
    deferred_ids = {item["id"] for item in deferred}
    for item in deferred:
        _text(item["scope"])
        _text_list(item["preconditions"])
        if item["status"] != "deferred" or item["credit"] != "none":
            raise ValueError("invalid deferred scope authority")

    launch_fields = {"id", "section", "item", "declared_status", "weight", "owner"}
    if not isinstance(root["launch_checklist"], list) or not root["launch_checklist"]:
        raise ValueError("invalid launch checklist")
    launch: list[dict[str, Any]] = []
    launch_ids: set[str] = set()
    for candidate in root["launch_checklist"]:
        if not isinstance(candidate, dict) or set(candidate) not in {
            frozenset(launch_fields),
            frozenset(launch_fields | {"source_ref"}),
        }:
            raise ValueError("invalid launch record")
        identifier = _text(candidate["id"], maximum=100)
        if identifier in launch_ids:
            raise ValueError("duplicate launch id")
        launch_ids.add(identifier)
        launch.append(candidate)
    for item in launch:
        for field in ("section", "item", "owner"):
            _text(item[field])
        if "source_ref" in item:
            _text(item["source_ref"])
        if item["declared_status"] not in {"todo", "partial"}:
            raise ValueError("invalid launch declared status")
        _integer(item["weight"], minimum=1)

    gtm = _exact_record(
        root["gtm"],
        {"authority", "positioning_hypothesis", "icp", "funnels", "channels", "timeline", "assets", "metrics", "pricing"},
    )
    if gtm["authority"] != {
        "kind": "curated_hypothesis",
        "credit": "none",
        "validation_status": "unvalidated",
    }:
        raise ValueError("invalid gtm authority")
    _text(gtm["positioning_hypothesis"])

    icp = _records(
        gtm["icp"],
        {"segment", "priority_hypothesis", "rationale_hypothesis", "entry_experiment", "validation_status", "deferred_scope_id"},
    )
    for item in icp:
        for field in ("segment", "priority_hypothesis", "rationale_hypothesis", "entry_experiment"):
            _text(item[field])
        if item["validation_status"] != "unvalidated":
            raise ValueError("invalid icp validation status")
        _validate_deferred_ref(item["deferred_scope_id"], deferred_ids)

    funnels = _exact_record(
        gtm["funnels"],
        {"horizon", "validation_status", "user", "supply", "advocacy"},
    )
    _text(funnels["horizon"])
    if funnels["validation_status"] != "unvalidated":
        raise ValueError("invalid funnel validation status")
    funnel_fields = {"id", "label", "unit", "target_count", "definition", "instrument", "measurement_status"}
    user_funnel = _records(funnels["user"], funnel_fields, id_field="id")
    supply_funnel = _records(funnels["supply"], funnel_fields, id_field="id")
    advocacy = _exact_record(funnels["advocacy"], funnel_fields)
    if [item["id"] for item in user_funnel] != ["aware", "browsed", "first_reuse", "habitual"]:
        raise ValueError("invalid user funnel")
    if [item["id"] for item in supply_funnel] != ["submitted", "published"]:
        raise ValueError("invalid supply funnel")
    for item in [*user_funnel, *supply_funnel, advocacy]:
        for field in ("id", "label", "definition", "instrument"):
            _text(item[field])
        _integer(item["target_count"])
        if item["measurement_status"] != "unmeasured":
            raise ValueError("invalid funnel measurement")
    if any(item["unit"] != "unique_people" for item in user_funnel):
        raise ValueError("invalid user funnel unit")
    if any(item["unit"] != "skill_versions" for item in supply_funnel):
        raise ValueError("invalid supply funnel unit")
    if advocacy["id"] != "advocate" or advocacy["unit"] != "unique_people":
        raise ValueError("invalid advocacy cohort")
    for cohort in (user_funnel, supply_funnel):
        counts = [item["target_count"] for item in cohort]
        if counts != sorted(counts, reverse=True):
            raise ValueError("invalid funnel target order")
    if supply_funnel[1]["instrument"] != "verified scoreboard publish projection":
        raise ValueError("invalid publication instrument")

    channels = _records(
        gtm["channels"],
        {"name", "type", "effort_hypothesis", "impact_hypothesis", "rationale_hypothesis", "validation_status", "experiment", "evidence_ref", "deferred_scope_id"},
    )
    for item in channels:
        for field in ("name", "type", "effort_hypothesis", "impact_hypothesis", "rationale_hypothesis", "experiment"):
            _text(item[field])
        if item["effort_hypothesis"] not in {"low", "med", "high"}:
            raise ValueError("invalid channel effort hypothesis")
        if item["impact_hypothesis"] not in {"low", "med", "high"}:
            raise ValueError("invalid channel impact hypothesis")
        if item["validation_status"] != "unvalidated" or item["evidence_ref"] is not None:
            raise ValueError("invalid channel evidence")
        _validate_deferred_ref(item["deferred_scope_id"], deferred_ids)

    timeline = _records(gtm["timeline"], {"phase", "start", "days", "track", "items"})
    for item in timeline:
        for field in ("phase", "track"):
            _text(item[field])
        _integer(item["start"])
        _integer(item["days"], minimum=1)
        _text_list(item["items"])

    asset_fields = {
        "id", "name", "type", "declared_status", "validation_status", "availability",
        "source_ref", "channel", "note",
    }
    if not isinstance(gtm["assets"], list) or not gtm["assets"]:
        raise ValueError("invalid asset list")
    assets: list[dict[str, Any]] = []
    asset_ids: set[str] = set()
    for candidate in gtm["assets"]:
        if not isinstance(candidate, dict) or set(candidate) not in {
            frozenset(asset_fields),
            frozenset(asset_fields | {"deferred_scope_id"}),
        }:
            raise ValueError("invalid asset record")
        identifier = _text(candidate["id"], maximum=100)
        if identifier in asset_ids:
            raise ValueError("duplicate asset id")
        asset_ids.add(identifier)
        assets.append(candidate)
    for item in assets:
        for field in ("name", "type", "channel", "note"):
            _text(item[field])
        if item["source_ref"] is not None:
            _text(item["source_ref"])
        if item["declared_status"] not in {"todo", "partial"}:
            raise ValueError("invalid asset declared status")
        if item["declared_status"] == "partial" and item["source_ref"] is None:
            raise ValueError("partial asset source missing")
        if item["validation_status"] != "unvalidated" or item["availability"] != "not_published":
            raise ValueError("invalid asset authority")
        _validate_deferred_ref(item.get("deferred_scope_id"), deferred_ids)

    metrics = _records(
        gtm["metrics"],
        {"id", "name", "target", "measurement", "why", "source_definition"},
        id_field="id",
    )
    for item in metrics:
        for field in ("name", "why", "source_definition"):
            _text(item[field])
        target = _exact_record(item["target"], {"value", "unit", "comparator", "horizon", "status"})
        _number(target["value"])
        for field in ("unit", "horizon"):
            _text(target[field])
        if target["comparator"] not in {"equal", "greater_than_or_equal", "less_than"}:
            raise ValueError("invalid metric comparator")
        if target["status"] != "hypothesis":
            raise ValueError("invalid metric target authority")
        measurement = _exact_record(
            item["measurement"],
            {"status", "value", "observed_at", "evidence_ref", "reason"},
        )
        if measurement != {
            "status": "unmeasured",
            "value": None,
            "observed_at": None,
            "evidence_ref": None,
            "reason": measurement.get("reason"),
        }:
            raise ValueError("invalid metric measurement authority")
        _text(measurement["reason"])

    pricing = _records(
        gtm["pricing"],
        {"tier", "proposed_price", "audience_hypothesis", "includes_hypothesis", "availability", "decision_status", "validation_status", "evidence_ref", "deferred_scope_id"},
    )
    for item in pricing:
        for field in ("tier", "proposed_price", "audience_hypothesis", "includes_hypothesis"):
            _text(item[field])
        if (
            item["availability"] != "not_offered"
            or item["decision_status"] != "not_decided"
            or item["validation_status"] != "unvalidated"
            or item["evidence_ref"] is not None
        ):
            raise ValueError("invalid pricing authority")
        _validate_deferred_ref(item["deferred_scope_id"], deferred_ids)


def load_pinned_model(
    model_path: Path,
    manifest_path: Path | None = None,
    *,
    expected_sha256: str | None = None,
) -> LoadedDashboardModel:
    model_path = Path(model_path)
    manifest_path = Path(manifest_path or model_path.with_suffix(".sha256"))
    try:
        raw = model_path.read_bytes()
    except OSError as exc:
        raise QueueUnavailable("dashboard model unavailable") from exc
    actual_sha256 = _sha256(raw)
    pinned_sha256 = _load_model_manifest(manifest_path)
    if not hmac.compare_digest(pinned_sha256, actual_sha256):
        raise QueueUnavailable("dashboard model integrity mismatch")
    if expected_sha256 is not None and not hmac.compare_digest(expected_sha256, actual_sha256):
        raise QueueUnavailable("dashboard model changed; restart required")
    try:
        model = strict_json_loads(raw.decode("utf-8", errors="strict"))
        _validate_dashboard_model(model)
        templates = _templates_from_model(model)
    except (UnicodeError, TypeError, ValueError, json.JSONDecodeError, QueueUnavailable) as exc:
        raise QueueUnavailable("dashboard model invalid") from exc
    if {
        template_id: template["template_sha256"]
        for template_id, template in templates.items()
    } != _APPROVED_ACTION_TEMPLATE_SHA256:
        raise QueueUnavailable("dashboard model action registry is not approved")
    return LoadedDashboardModel(actual_sha256, model, templates)


def _load_templates(model_path: Path) -> tuple[dict[str, dict[str, Any]], str]:
    loaded = load_pinned_model(model_path)
    return loaded.templates, loaded.sha256


def public_model(loaded: LoadedDashboardModel) -> dict[str, Any]:
    model = copy.deepcopy(loaded.model)
    model["actions"] = [
        {
            "id": template["template_id"],
            "group": template["group"],
            "label": template["title"],
            "description": (
                f"Hash-bound schema-v1 {template['group']} request; the server resolves the "
                "integrity-pinned prompt when queued."
            ),
        }
        for template in loaded.templates.values()
    ]
    return model


def _acquire_lifetime_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (OSError, ImportError) as exc:
        handle.close()
        raise QueueUnavailable("queue already owned by another process") from exc
    return handle


def _release_lifetime_lock(handle) -> None:
    if handle is None or handle.closed:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _fsync_directory(path: Path) -> None:
    """Persist directory entries where the platform exposes directory fsync."""
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(path, flags)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _move_no_replace(source: Path, target: Path) -> None:
    """Move within a volume without replacing an existing target; request write-through on Windows."""
    if target.exists():
        raise FileExistsError(str(target))
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file.restype = ctypes.c_int
        movefile_write_through = 0x00000008
        if not move_file(str(source), str(target), movefile_write_through):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.rename(source, target)
        _fsync_directory(target.parent)
        if source.parent != target.parent:
            _fsync_directory(source.parent)


def _replace_durable(source: Path, target: Path) -> None:
    """Atomically replace a file and request durable directory metadata."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        move_file = kernel32.MoveFileExW
        move_file.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
        move_file.restype = ctypes.c_int
        movefile_replace_existing = 0x00000001
        movefile_write_through = 0x00000008
        if not move_file(
            str(source),
            str(target),
            movefile_replace_existing | movefile_write_through,
        ):
            raise ctypes.WinError(ctypes.get_last_error())
    else:
        os.replace(source, target)
        _fsync_directory(target.parent)
        if source.parent != target.parent:
            _fsync_directory(source.parent)


def _unlink_durable(path: Path) -> None:
    path.unlink()
    _fsync_directory(path.parent)


def _write_atomic_no_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _move_no_replace(temp, path)
        _fsync_directory(path.parent)
    except OSError:
        try:
            if temp.exists():
                _unlink_durable(temp)
        except OSError:
            pass
        raise


def _write_atomic_replace(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp.open("xb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        _replace_durable(temp, path)
        _fsync_directory(path.parent)
    except OSError:
        try:
            if temp.exists():
                _unlink_durable(temp)
        except OSError:
            pass
        raise


class ActionQueue:
    """Serialize a template-derived JSONL queue and own its cross-process writer lease."""

    def __init__(self, *, inbox_path: Path, model_path: Path, manifest_path: Path | None = None):
        self.inbox_path = Path(inbox_path)
        self.model_path = Path(model_path)
        self.manifest_path = Path(manifest_path or self.model_path.with_suffix(".sha256"))
        self.archive_dir = self.inbox_path.parent / "archive"
        self._thread_lock = threading.RLock()
        self._process_lock = _acquire_lifetime_lock(self.inbox_path.with_suffix(".lock"))
        self._closed = False
        self._history_error: QueueUnavailable | None = None
        self._durability_uncertain = False
        try:
            loaded = load_pinned_model(self.model_path, self.manifest_path)
            self._templates = loaded.templates
            self._template_registry_sha256 = loaded.sha256
            self._template_error = None
        except QueueUnavailable as exc:
            self._templates = {}
            self._template_registry_sha256 = None
            self._template_error = exc
        try:
            self._remove_abandoned_inbox_temps()
            self._recover_archive_transactions()
            self._validated_history()
        except QueueUnavailable as exc:
            self._history_error = exc
        if self._history_error is None:
            try:
                self._sync_authoritative_state()
            except QueueUnavailable:
                self._durability_uncertain = True

    def close(self) -> None:
        with self._thread_lock:
            if not self._closed:
                _release_lifetime_lock(self._process_lock)
                self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise QueueUnavailable("queue closed")

    def _ensure_history_available(self) -> None:
        if self._history_error is not None:
            raise QueueUnavailable("queue history unavailable") from self._history_error
        if self._durability_uncertain:
            self._remove_abandoned_inbox_temps()
            self._recover_archive_transactions()
            self._sync_authoritative_state()
            self._durability_uncertain = False

    def _current_model(self) -> LoadedDashboardModel:
        if self._template_error is not None:
            raise QueueUnavailable("template registry unavailable") from self._template_error
        return load_pinned_model(
            self.model_path,
            self.manifest_path,
            expected_sha256=self._template_registry_sha256,
        )

    @staticmethod
    def _rows_from_path(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            raw = path.read_bytes()
            if raw and (not raw.endswith(b"\n") or b"\r" in raw):
                raise QueueUnavailable("queue corrupt")
            lines = raw.decode("utf-8", errors="strict").splitlines()
        except (OSError, UnicodeError) as exc:
            raise QueueUnavailable("queue unreadable") from exc
        rows: list[dict[str, Any]] = []
        for line in lines:
            if not line:
                raise QueueUnavailable("queue corrupt")
            try:
                row = strict_json_loads(line)
            except (ValueError, json.JSONDecodeError) as exc:
                raise QueueUnavailable("queue corrupt") from exc
            if not isinstance(row, dict):
                raise QueueUnavailable("queue corrupt")
            rows.append(row)
        return rows

    def _raw_rows(self) -> list[dict[str, Any]]:
        return self._rows_from_path(self.inbox_path)

    def _remove_abandoned_inbox_temps(self) -> None:
        for path in self.inbox_path.parent.glob(f".{self.inbox_path.name}.*.tmp"):
            if path.is_file():
                try:
                    _unlink_durable(path)
                except OSError as exc:
                    raise QueueUnavailable("queue recovery failed") from exc

    def _sync_authoritative_state(self) -> None:
        """Make every visible authoritative file durable before availability or replay."""
        paths: list[Path] = []
        if self.inbox_path.exists():
            paths.append(self.inbox_path)
        if self.archive_dir.exists():
            paths.extend(sorted(self.archive_dir.glob("inbox-*.jsonl")))
            paths.extend(sorted(self.archive_dir.glob("inbox-*.receipt.json")))
        try:
            for path in paths:
                with path.open("r+b") as handle:
                    os.fsync(handle.fileno())
            if self.archive_dir.exists():
                _fsync_directory(self.archive_dir)
            _fsync_directory(self.inbox_path.parent)
        except OSError as exc:
            raise QueueUnavailable("queue durability unavailable") from exc

    @staticmethod
    def _archive_target_for_receipt(receipt_path: Path) -> Path:
        return receipt_path.with_suffix("").with_suffix(".jsonl")

    def _load_archive_receipt(self, receipt_path: Path) -> tuple[dict[str, Any], Path]:
        required = {
            "schema_version", "archive_id", "request_id", "archived_at", "row_count",
            "sha256", "recovery_ref",
        }
        try:
            raw = receipt_path.read_bytes()
            receipt = strict_json_loads(raw.decode("utf-8", errors="strict"))
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            raise QueueUnavailable("archive receipt corrupt") from exc
        if (
            not isinstance(receipt, dict)
            or set(receipt) != required
            or receipt.get("schema_version") != ARCHIVE_RECEIPT_SCHEMA
            or raw != _canonical_bytes(receipt)
        ):
            raise QueueUnavailable("archive receipt corrupt")
        archive_id = receipt.get("archive_id")
        if not isinstance(archive_id, str) or not _ARCHIVE_ID.fullmatch(archive_id):
            raise QueueUnavailable("archive receipt corrupt")
        try:
            request_id = _canonical_uuid(receipt.get("request_id"))
        except QueueValidationError as exc:
            raise QueueUnavailable("archive receipt corrupt") from exc
        archived_at = _validate_utc_timestamp(receipt.get("archived_at"), label="archive")
        if archive_id.removeprefix("ARC-") != request_id.replace("-", ""):
            raise QueueUnavailable("archive receipt identity mismatch")
        if (
            not isinstance(receipt.get("row_count"), int)
            or isinstance(receipt.get("row_count"), bool)
            or receipt["row_count"] < 0
        ):
            raise QueueUnavailable("archive receipt corrupt")
        if not isinstance(receipt.get("sha256"), str) or not _SHA256.fullmatch(receipt["sha256"]):
            raise QueueUnavailable("archive receipt corrupt")

        target = self._archive_target_for_receipt(receipt_path)
        match = _ARCHIVE_DATA_NAME.fullmatch(target.name)
        if match is None or match.group(2) != archive_id.removeprefix("ARC-"):
            raise QueueUnavailable("archive receipt filename mismatch")
        try:
            filename_time = datetime.strptime(match.group(1), "%Y%m%dT%H%M%S%fZ")
            receipt_time = datetime.fromisoformat(archived_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise QueueUnavailable("archive receipt filename mismatch") from exc
        if filename_time != receipt_time.replace(tzinfo=None):
            raise QueueUnavailable("archive receipt timestamp mismatch")
        expected_ref = target.relative_to(self.inbox_path.parent).as_posix()
        if receipt.get("recovery_ref") != expected_ref:
            raise QueueUnavailable("archive receipt recovery reference mismatch")
        return receipt, target

    def _remove_abandoned_temps(self) -> None:
        if not self.archive_dir.exists():
            return
        for path in self.archive_dir.glob(".inbox-*.tmp"):
            if path.is_file():
                try:
                    _unlink_durable(path)
                except OSError as exc:
                    raise QueueUnavailable("archive recovery failed") from exc

    def _recover_archive_transactions(self) -> None:
        """Complete a durable archive intent left between sidecar commit and journal move."""
        self._remove_abandoned_temps()
        if not self.archive_dir.exists():
            return
        data_paths = set(self.archive_dir.glob("inbox-*.jsonl"))
        receipt_paths = sorted(self.archive_dir.glob("inbox-*.receipt.json"))
        paired_data = {self._archive_target_for_receipt(path) for path in receipt_paths}
        if data_paths - paired_data:
            raise QueueUnavailable("archive receipt missing")

        pending: list[tuple[dict[str, Any], Path]] = []
        for receipt_path in receipt_paths:
            receipt, target = self._load_archive_receipt(receipt_path)
            if not target.exists():
                pending.append((receipt, target))
        if len(pending) > 1:
            raise QueueUnavailable("multiple incomplete archive transactions")
        if not pending:
            return

        receipt, target = pending[0]
        try:
            raw = self.inbox_path.read_bytes() if self.inbox_path.exists() else b""
            rows = self._rows_from_path(self.inbox_path)
        except OSError as exc:
            raise QueueUnavailable("archive recovery failed") from exc
        if len(rows) != receipt["row_count"] or _sha256(raw) != receipt["sha256"]:
            raise QueueUnavailable("archive recovery source mismatch")
        try:
            if self.inbox_path.exists():
                _move_no_replace(self.inbox_path, target)
            else:
                _write_atomic_no_replace(target, b"")
            _fsync_directory(self.archive_dir)
            _fsync_directory(self.inbox_path.parent)
        except OSError as exc:
            raise QueueUnavailable("archive recovery failed") from exc

    def _archive_receipts(self) -> list[dict[str, Any]]:
        receipts: list[dict[str, Any]] = []
        if not self.archive_dir.exists():
            return receipts
        data_paths = sorted(self.archive_dir.glob("inbox-*.jsonl"))
        receipt_paths = sorted(self.archive_dir.glob("inbox-*.receipt.json"))
        expected_data = {self._archive_target_for_receipt(path) for path in receipt_paths}
        if expected_data != set(data_paths):
            raise QueueUnavailable("archive receipt missing")
        seen_archive_ids: set[str] = set()
        seen_request_ids: set[str] = set()
        seen_recovery_refs: set[str] = set()
        for path in receipt_paths:
            receipt, target = self._load_archive_receipt(path)
            try:
                raw = target.read_bytes()
            except OSError as exc:
                raise QueueUnavailable("archive data unreadable") from exc
            rows = self._rows_from_path(target)
            if receipt["row_count"] != len(rows) or receipt["sha256"] != _sha256(raw):
                raise QueueUnavailable("archive receipt does not match data")
            if (
                receipt["archive_id"] in seen_archive_ids
                or receipt["request_id"] in seen_request_ids
                or receipt["recovery_ref"] in seen_recovery_refs
            ):
                raise QueueUnavailable("duplicate archive receipt identity")
            seen_archive_ids.add(receipt["archive_id"])
            seen_request_ids.add(receipt["request_id"])
            seen_recovery_refs.add(receipt["recovery_ref"])
            receipts.append(receipt)
        return receipts

    def _validated_history(
        self,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        """Validate every row/sidecar and enforce one global identity namespace."""
        self._ensure_history_available()
        receipts = self._archive_receipts()
        historical: list[dict[str, Any]] = []
        if self.archive_dir.exists():
            for path in sorted(self.archive_dir.glob("inbox-*.jsonl")):
                historical.extend(self._rows_from_path(path))
        active = self._raw_rows()
        historical.extend(active)

        public_active: list[dict[str, Any]] = []
        active_start = len(historical) - len(active)
        seen_receipt_ids: set[str] = set()
        seen_request_ids: set[str] = {receipt["request_id"] for receipt in receipts}
        for index, row in enumerate(historical):
            public = self._public_row(row)
            receipt_id = public["receipt_id"]
            request_id = public["request_id"]
            if receipt_id in seen_receipt_ids:
                raise QueueUnavailable("duplicate queue receipt identity")
            seen_receipt_ids.add(receipt_id)
            if request_id is not None:
                if request_id in seen_request_ids:
                    raise QueueUnavailable("duplicate queue request identity")
                seen_request_ids.add(request_id)
            if index >= active_start:
                public_active.append(public)
        return receipts, historical, active, public_active

    @staticmethod
    def _public_row(row: dict[str, Any]) -> dict[str, Any]:
        if row.get("schema_version") != QUEUE_ROW_SCHEMA:
            digest = _sha256(_canonical_bytes(row))
            return {
                "schema_version": "semiskill.dashboard-quarantined-request/v1",
                "receipt_id": "LEGACY-" + digest.removeprefix("sha256:")[:16],
                "request_id": None,
                "accepted_at": None,
                "request_type": "untrusted_legacy",
                "template_id": None,
                "group": "Untrusted",
                "title": "Legacy request quarantined",
                "priority": None,
                "context": None,
                "status": "quarantined",
                "credit": "none",
            }
        required = {
            "schema_version", "receipt_id", "request_id", "accepted_at", "request_type",
            "template_id", "template_version", "template_sha256", "template_registry_sha256",
            "action_sha256", "priority", "context", "group", "title", "prompt", "status", "credit",
        }
        if set(row) != required or row.get("status") != "queued" or row.get("credit") != "none":
            raise QueueUnavailable("queue corrupt")
        if not isinstance(row.get("receipt_id"), str) or not _ACTION_RECEIPT_ID.fullmatch(
            row["receipt_id"]
        ):
            raise QueueUnavailable("queue corrupt")
        try:
            request_id = _canonical_uuid(row.get("request_id"))
            _validate_utc_timestamp(row.get("accepted_at"), label="queue")
        except (QueueValidationError, QueueUnavailable) as exc:
            raise QueueUnavailable("queue corrupt") from exc
        if row["receipt_id"].removeprefix("ACT-") != request_id.replace("-", ""):
            raise QueueUnavailable("queue identity mismatch")
        if (
            row.get("request_type") != "prepared"
            or not isinstance(row.get("template_version"), int)
            or isinstance(row.get("template_version"), bool)
            or row.get("template_version") != 1
        ):
            raise QueueUnavailable("queue corrupt")
        if not isinstance(row.get("template_id"), str) or not _TEMPLATE_ID.fullmatch(row["template_id"]):
            raise QueueUnavailable("queue corrupt")
        if row.get("priority") not in _PRIORITIES or row.get("context") not in _CONTEXTS:
            raise QueueUnavailable("queue corrupt")
        template = {
            "schema_version": TEMPLATE_SCHEMA,
            "template_id": row["template_id"],
            "template_version": 1,
            "group": _plain_text(row.get("group"), field="group", maximum=80),
            "title": _plain_text(row.get("title"), field="title", maximum=300),
            "prompt": _plain_text(row.get("prompt"), field="prompt", maximum=8_000),
        }
        if row.get("template_sha256") != _sha256(_canonical_bytes(template)):
            raise QueueUnavailable("queue corrupt")
        if not isinstance(row.get("template_registry_sha256"), str) or not _SHA256.fullmatch(
            row["template_registry_sha256"]
        ):
            raise QueueUnavailable("queue corrupt")
        action_basis = {
            "schema_version": ACTION_REQUEST_SCHEMA,
            "request_id": row["request_id"],
            "request_type": "prepared",
            "template_id": row["template_id"],
            "template_version": 1,
            "template_sha256": row["template_sha256"],
            "template_registry_sha256": row["template_registry_sha256"],
            "priority": row["priority"],
            "context": row["context"],
        }
        if row.get("action_sha256") != _sha256(_canonical_bytes(action_basis)):
            raise QueueUnavailable("queue corrupt")
        return {
            key: value for key, value in row.items()
            if key not in {"prompt", "template_registry_sha256"}
        }

    def read(self) -> list[dict[str, Any]]:
        with self._thread_lock:
            self._ensure_open()
            self._current_model()
            _receipts, _historical, _active, public_active = self._validated_history()
            return public_active

    def public_templates(self) -> list[dict[str, Any]]:
        with self._thread_lock:
            self._ensure_open()
            loaded = self._current_model()
            return [
                {
                    "id": template["template_id"],
                    "group": template["group"],
                    "label": template["title"],
                    "description": (
                        f"Hash-bound schema-v1 {template['group']} request; the server resolves "
                        "the integrity-pinned prompt when queued."
                    ),
                }
                for template in loaded.templates.values()
            ]

    def public_model(self) -> dict[str, Any]:
        with self._thread_lock:
            self._ensure_open()
            return public_model(self._current_model())

    def state_inputs(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Load one pinned model snapshot and the queue view under the same process lock."""
        with self._thread_lock:
            self._ensure_open()
            loaded = self._current_model()
            _receipts, _historical, _active, public_active = self._validated_history()
            return public_model(loaded), public_active

    @staticmethod
    def _receipt(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "schema_version": RECEIPT_SCHEMA,
            "receipt_id": row["receipt_id"],
            "request_id": row["request_id"],
            "status": row["status"],
            "accepted_at": row["accepted_at"],
            "request_type": row["request_type"],
            "template_id": row["template_id"],
            "action_sha256": row["action_sha256"],
        }

    def _append_durable(self, row: dict[str, Any]) -> None:
        self.inbox_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            prior = self.inbox_path.read_bytes() if self.inbox_path.exists() else b""
            _write_atomic_replace(self.inbox_path, prior + _canonical_bytes(row) + b"\n")
        except OSError as exc:
            self._durability_uncertain = True
            raise QueueUnavailable("queue write failed") from exc

    def enqueue(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) != _ACTION_FIELDS:
            raise QueueValidationError("action fields do not match schema")
        if payload.get("schema_version") != ACTION_REQUEST_SCHEMA:
            raise QueueValidationError("unsupported action schema")
        if payload.get("request_type") != "prepared":
            raise QueueValidationError("unsupported request type")
        request_id = _canonical_uuid(payload.get("request_id"))
        priority = payload.get("priority")
        context = payload.get("context")
        if priority not in _PRIORITIES or context not in _CONTEXTS:
            raise QueueValidationError("invalid priority or context")

        with self._thread_lock:
            self._ensure_open()
            loaded = self._current_model()
            registry_sha256 = loaded.sha256
            template = loaded.templates.get(payload.get("template_id"))
            if template is None:
                raise QueueValidationError("unknown template")
            receipts, historical, _active, _public_active = self._validated_history()
            for archived in receipts:
                if archived.get("request_id") == request_id:
                    raise QueueConflict("request id already used for archive")
            for existing in historical:
                if existing.get("schema_version") != QUEUE_ROW_SCHEMA:
                    continue
                if existing.get("request_id") == request_id:
                    if existing.get("template_registry_sha256") != registry_sha256:
                        raise QueueUnavailable("request template registry changed")
                    if (
                        existing.get("template_id") != payload.get("template_id")
                        or existing.get("priority") != priority
                        or existing.get("context") != context
                    ):
                        raise QueueConflict("request id already used for another action")
                    return self._receipt(self._public_row(existing))
            action_basis = {
                "schema_version": ACTION_REQUEST_SCHEMA,
                "request_id": request_id,
                "request_type": "prepared",
                "template_id": template["template_id"],
                "template_version": template["template_version"],
                "template_sha256": template["template_sha256"],
                "template_registry_sha256": registry_sha256,
                "priority": priority,
                "context": context,
            }
            action_sha256 = _sha256(_canonical_bytes(action_basis))

            row = {
                "schema_version": QUEUE_ROW_SCHEMA,
                "receipt_id": "ACT-" + request_id.replace("-", ""),
                "request_id": request_id,
                "accepted_at": _utc_now(),
                "request_type": "prepared",
                "template_id": template["template_id"],
                "template_version": template["template_version"],
                "template_sha256": template["template_sha256"],
                "template_registry_sha256": registry_sha256,
                "action_sha256": action_sha256,
                "priority": priority,
                "context": context,
                "group": template["group"],
                "title": template["title"],
                "prompt": template["prompt"],
                "status": "queued",
                "credit": "none",
            }
            self._append_durable(row)
            return self._receipt(row)

    def archive(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict) or set(payload) != _ARCHIVE_FIELDS:
            raise QueueValidationError("archive fields do not match schema")
        if payload.get("schema_version") != ARCHIVE_REQUEST_SCHEMA:
            raise QueueValidationError("unsupported archive schema")
        request_id = _canonical_uuid(payload.get("request_id"))
        with self._thread_lock:
            self._ensure_open()
            self._current_model()
            receipts, historical, rows, _public_active = self._validated_history()
            for receipt in receipts:
                if receipt.get("request_id") == request_id:
                    return dict(receipt)
            for row in historical:
                if row.get("schema_version") == QUEUE_ROW_SCHEMA and row.get("request_id") == request_id:
                    raise QueueConflict("request id already used for action")
            archived_at = _utc_now()
            archive_id = "ARC-" + request_id.replace("-", "")
            stamp = datetime.fromisoformat(archived_at.replace("Z", "+00:00")).strftime(
                "%Y%m%dT%H%M%S%fZ"
            )
            name = f"inbox-{stamp}-{archive_id.removeprefix('ARC-')}.jsonl"
            target = self.archive_dir / name
            receipt_path = target.with_suffix(".receipt.json")
            try:
                raw = self.inbox_path.read_bytes() if self.inbox_path.exists() else b""
                self.archive_dir.mkdir(parents=True, exist_ok=True)
                _fsync_directory(self.inbox_path.parent)
                receipt = {
                    "schema_version": ARCHIVE_RECEIPT_SCHEMA,
                    "archive_id": archive_id,
                    "request_id": request_id,
                    "archived_at": archived_at,
                    "row_count": len(rows),
                    "sha256": _sha256(raw),
                    "recovery_ref": target.relative_to(self.inbox_path.parent).as_posix(),
                }
                _write_atomic_no_replace(receipt_path, _canonical_bytes(receipt))
                if self.inbox_path.exists():
                    _move_no_replace(self.inbox_path, target)
                else:
                    _write_atomic_no_replace(target, b"")
                _fsync_directory(self.archive_dir)
                _fsync_directory(self.inbox_path.parent)
            except OSError as exc:
                self._durability_uncertain = True
                if receipt_path.exists() and not target.exists() and self.inbox_path.exists():
                    try:
                        _unlink_durable(receipt_path)
                    except OSError as rollback_exc:
                        raise QueueUnavailable("queue archive failed") from rollback_exc
                raise QueueUnavailable("queue archive failed") from exc
            # Reconcile the completed transaction before returning its authoritative receipt.
            self._archive_receipts()
            return receipt

    def receipt(self, receipt_id: str) -> dict[str, Any] | None:
        if not isinstance(receipt_id, str) or not _ACTION_RECEIPT_ID.fullmatch(receipt_id):
            return None
        with self._thread_lock:
            self._ensure_open()
            self._current_model()
            _receipts, historical, _active, _public_active = self._validated_history()
            for row in historical:
                if row.get("schema_version") == QUEUE_ROW_SCHEMA and row.get("receipt_id") == receipt_id:
                    return self._receipt(self._public_row(row))
        return None
