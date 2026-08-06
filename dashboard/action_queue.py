"""Fail-closed, non-crediting dashboard request queue.

Browser requests select a server-owned template. They never supply executable prose and queue
receipts are deliberately outside the SemiSkill artifact/publication authority chain.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ACTION_REQUEST_SCHEMA = "semiskill.dashboard-action/v1"
ARCHIVE_REQUEST_SCHEMA = "semiskill.dashboard-archive/v1"
QUEUE_ROW_SCHEMA = "semiskill.dashboard-request/v1"
RECEIPT_SCHEMA = "semiskill.dashboard-receipt/v1"
ARCHIVE_RECEIPT_SCHEMA = "semiskill.dashboard-archive-receipt/v1"
TEMPLATE_SCHEMA = "semiskill.dashboard-template/v1"

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
_MAX_JSON_DEPTH = 64
_MAX_JSON_NODES = 20_000


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


def _load_templates(model_path: Path) -> tuple[dict[str, dict[str, Any]], str]:
    try:
        raw = model_path.read_bytes()
        model = strict_json_loads(raw.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise QueueUnavailable("template registry unavailable") from exc
    if not isinstance(model, dict) or not isinstance(model.get("actions"), list):
        raise QueueUnavailable("template registry unavailable")

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
    return templates, _sha256(raw)


def _load_model_manifest(path: Path) -> str:
    try:
        raw = path.read_bytes()
        text = raw.decode("ascii", errors="strict")
    except (OSError, UnicodeError) as exc:
        raise QueueUnavailable("template manifest unavailable") from exc
    if not _MODEL_MANIFEST.fullmatch(text):
        raise QueueUnavailable("template manifest invalid")
    return text.rstrip("\r\n")


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
            self._templates, self._template_registry_sha256 = _load_templates(self.model_path)
            if _load_model_manifest(self.manifest_path) != self._template_registry_sha256:
                raise QueueUnavailable("template manifest mismatch")
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
            _receipts, _historical, _active, public_active = self._validated_history()
            return public_active

    def public_templates(self) -> list[dict[str, Any]]:
        with self._thread_lock:
            self._ensure_open()
            if self._template_error is not None:
                raise QueueUnavailable("template registry unavailable") from self._template_error
            _current_templates, current_registry_sha256 = _load_templates(self.model_path)
            if _load_model_manifest(self.manifest_path) != current_registry_sha256:
                raise QueueUnavailable("template manifest mismatch")
            if current_registry_sha256 != self._template_registry_sha256:
                raise QueueUnavailable("template registry changed; restart required")
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
                for template in self._templates.values()
            ]

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
            receipts, historical, _active, _public_active = self._validated_history()
            for archived in receipts:
                if archived.get("request_id") == request_id:
                    raise QueueConflict("request id already used for archive")
            for existing in historical:
                if existing.get("schema_version") != QUEUE_ROW_SCHEMA:
                    continue
                if existing.get("request_id") == request_id:
                    if (
                        existing.get("template_id") != payload.get("template_id")
                        or existing.get("priority") != priority
                        or existing.get("context") != context
                    ):
                        raise QueueConflict("request id already used for another action")
                    return self._receipt(self._public_row(existing))

            if self._template_error is not None:
                raise QueueUnavailable("template registry unavailable") from self._template_error
            _current_templates, current_registry_sha256 = _load_templates(self.model_path)
            if _load_model_manifest(self.manifest_path) != current_registry_sha256:
                raise QueueUnavailable("template manifest mismatch")
            if current_registry_sha256 != self._template_registry_sha256:
                raise QueueUnavailable("template registry changed; restart required")
            registry_sha256 = self._template_registry_sha256
            template = self._templates.get(payload.get("template_id"))
            if template is None:
                raise QueueValidationError("unknown template")
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
            _receipts, historical, _active, _public_active = self._validated_history()
            for row in historical:
                if row.get("schema_version") == QUEUE_ROW_SCHEMA and row.get("receipt_id") == receipt_id:
                    return self._receipt(self._public_row(row))
        return None
