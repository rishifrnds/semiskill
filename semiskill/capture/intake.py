"""L1 Capture — turn a skill submission into an immutable `skill_version` artifact.

The submitted SKILL.md body and any bundled files are UNTRUSTED: they are stored verbatim in the
artifact payload but never executed or interpreted as instructions. The L4/L6 pipeline (Phase C)
scans them, and a human approves, before anything becomes discoverable (ADR-002).
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
import yaml
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind

_FENCE = "---"

MAX_PAYLOAD_DEPTH = 8
MAX_PAYLOAD_FILES = 64
MAX_PAYLOAD_ENTRIES = 128
MAX_PAYLOAD_FILE_BYTES = 1024 * 1024
MAX_PAYLOAD_TOTAL_BYTES = 4 * 1024 * 1024
_READ_CHUNK_BYTES = 64 * 1024

# Canonical identity of the installable skill bytes. Governance metadata, artifact IDs, actors,
# and timestamps are intentionally absent.
PAYLOAD_FINGERPRINT_FIELDS = (
    "slug", "name", "description", "version", "function", "role", "level", "tags",
    "allowed_tools", "skill_md", "body", "files",
)


def payload_fingerprint(payload: dict) -> str:
    """Return a stable SHA-256 fingerprint of the installable skill payload."""
    if not isinstance(payload, dict):
        raise ValueError("skill payload must be an object")
    canonical = {key: payload.get(key) for key in PAYLOAD_FINGERPRINT_FIELDS}
    try:
        encoded = json.dumps(
            canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str,
        ).encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("skill payload contains invalid Unicode") from exc
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class ParsedSkill:
    frontmatter: dict
    body: str


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "skill"


def _meta(fm: dict) -> dict:
    """The `metadata` block, or {} when absent or not a mapping (never fatal — the pipeline, not
    the parser, is what rejects a bad submission)."""
    m = fm.get("metadata")
    return m if isinstance(m, dict) else {}


def _field(fm: dict, key: str):
    """Resolve one taxonomy field per ADR-008: `metadata['semiskill-<k>']` → `metadata['<k>']` →
    top-level `'<k>'`. The last hop keeps the pre-ADR-008 seeds working unchanged."""
    m = _meta(fm)
    for candidate in (m.get(f"semiskill-{key}"), m.get(key), fm.get(key)):
        if candidate is not None:
            return candidate
    return None


def _str_list(value) -> list[str]:
    """A YAML list, or a delimited string. The Agent Skills standard writes `allowed-tools` as a
    space-separated string, and `metadata` values are strings by spec — iterating either as a
    sequence would yield one entry per CHARACTER, which scores every skill 0.0 at stage 1."""
    if value is None:
        return []
    if isinstance(value, str):
        return [t for t in re.split(r"[,\s]+", value.strip()) if t]
    if isinstance(value, (list, tuple)):
        return [str(t) for t in value]
    return []


def _payload_text(value: str, *, label: str) -> str:
    """Keep payload text byte-faithful and reject content PostgreSQL JSON cannot represent."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be UTF-8 text")
    if "\x00" in value:
        raise ValueError(f"NUL bytes are not allowed in {label}")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} contains invalid Unicode") from exc
    return value


def _payload_files(files: dict[str, str] | None) -> dict[str, str]:
    """Validate the leased relative file scope even for non-filesystem capture callers."""
    if files is None:
        return {}
    if not isinstance(files, dict):
        raise ValueError("payload files must be a path-to-text object")
    if len(files) + 1 > MAX_PAYLOAD_FILES:
        raise ValueError(f"skill payload exceeds the {MAX_PAYLOAD_FILES}-file limit")
    validated: dict[str, str] = {}
    seen_casefold: set[str] = set()
    for raw_path, value in files.items():
        if not isinstance(raw_path, str) or not raw_path or "\x00" in raw_path:
            raise ValueError("payload file paths must be non-empty text")
        try:
            raw_path.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError("payload file paths contain invalid Unicode") from exc
        path = PurePosixPath(raw_path)
        canonical = path.as_posix()
        if (
            raw_path != canonical
            or path.is_absolute()
            or "\\" in raw_path
            or ":" in raw_path
            or any(part in {"", ".", ".."} for part in path.parts)
        ):
            raise ValueError(f"payload file path escapes or aliases its leased scope: {raw_path!r}")
        folded = canonical.casefold()
        if folded in seen_casefold:
            raise ValueError(f"payload file paths collide case-insensitively: {raw_path!r}")
        seen_casefold.add(folded)
        if path.name.casefold() == "review.json":
            raise ValueError(f"governance metadata must not be embedded in a skill payload: {raw_path}")
        if canonical.casefold() == "skill.md":
            raise ValueError("SKILL.md must be supplied through the canonical skill_md field")
        validated[canonical] = _payload_text(value, label=f"payload file {canonical!r}")
    return validated


def _validate_payload_budget(skill_md: str, files: dict[str, str]) -> None:
    """Apply one deterministic resource contract to filesystem and direct capture paths."""
    if len(files) + 1 > MAX_PAYLOAD_FILES:
        raise ValueError(f"skill payload exceeds the {MAX_PAYLOAD_FILES}-file limit")
    entry_names: dict[str, tuple[str, str]] = {"skill.md": ("SKILL.md", "file")}
    total = 0
    for path, value in [("SKILL.md", skill_md), *files.items()]:
        parts = PurePosixPath(path).parts
        if len(parts) > MAX_PAYLOAD_DEPTH:
            raise ValueError(f"skill payload exceeds the depth limit at {path}")
        for depth in range(1, len(parts)):
            directory = PurePosixPath(*parts[:depth]).as_posix()
            entry = (directory, "directory")
            existing = entry_names.setdefault(directory.casefold(), entry)
            if existing != entry:
                raise ValueError("skill payload paths collide case-insensitively")
        entry = (path, "file")
        existing = entry_names.setdefault(path.casefold(), entry)
        if existing != entry:
            raise ValueError("skill payload paths collide case-insensitively")
        if len(entry_names) > MAX_PAYLOAD_ENTRIES:
            raise ValueError(f"skill payload exceeds the {MAX_PAYLOAD_ENTRIES}-entry limit")
        size = len(value.encode("utf-8"))
        if size > MAX_PAYLOAD_FILE_BYTES:
            raise ValueError(f"skill payload file exceeds the byte limit: {path}")
        total += size
        if total > MAX_PAYLOAD_TOTAL_BYTES:
            raise ValueError("skill payload exceeds the total byte limit")


def parse_skill_md(text: str) -> ParsedSkill:
    """Split a SKILL.md into YAML frontmatter (a mapping) + the untrusted body."""
    if not text.startswith(_FENCE):
        raise ValueError("SKILL.md must start with a '---' YAML frontmatter fence")
    rest = text[len(_FENCE):]
    end = rest.find("\n" + _FENCE)
    if end == -1:
        raise ValueError("SKILL.md frontmatter is not closed with '---'")
    fm_text = rest[:end]
    body = rest[end + len("\n" + _FENCE):].lstrip("\n")
    fm = yaml.safe_load(fm_text) or {}          # safe_load: never construct arbitrary objects
    if not isinstance(fm, dict):
        raise ValueError("SKILL.md frontmatter must be a YAML mapping")
    return ParsedSkill(frontmatter=fm, body=body)


def build_skill_version(*, skill_md: str, actor: str,
                        source_system: SourceSystem = SourceSystem.CLI,
                        actor_kind: ActorKind = ActorKind.HUMAN,
                        permissions_label: str = "team",
                        files: dict[str, str] | None = None) -> Artifact:
    """Build a `skill_version` artifact from a SKILL.md submission. Body/files kept UNTRUSTED."""
    skill_md = _payload_text(skill_md, label="SKILL.md")
    payload_files = _payload_files(files)
    _validate_payload_budget(skill_md, payload_files)
    parsed = parse_skill_md(skill_md)
    fm = parsed.frontmatter
    name = fm.get("name")
    if not name:
        raise ValueError("SKILL.md frontmatter must include a 'name'")
    version = _field(fm, "version")
    title = _field(fm, "title")                  # ADR-008: human title rides in metadata…
    payload = {
        "slug": _field(fm, "slug") or _slugify(str(name)),   # …`name` is the kebab identifier
        "name": str(title if title is not None else name),
        "description": str(fm.get("description", "")),
        "version": str(version if version is not None else "0.1.0"),
        "function": _field(fm, "function"),
        "role": _field(fm, "role"),
        "level": _field(fm, "level"),
        "owner": _field(fm, "owner") or actor,
        "tags": _str_list(_field(fm, "tags")),
        "allowed_tools": _str_list(fm.get("allowed-tools") or fm.get("allowed_tools")),
        "skill_md": skill_md,  # exact canonical source text
        "body": _payload_text(parsed.body, label="SKILL.md body"),
        "files": payload_files,
    }
    payload["payload_sha256"] = payload_fingerprint(payload)
    art = Artifact.new(artifact_type=ArtifactType.SKILL_VERSION, source_system=source_system,
                       actor=actor, actor_kind=actor_kind, payload=payload)
    if permissions_label != art.permissions_label:
        art = replace(art, permissions_label=permissions_label)
    return art


def _is_link_or_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    is_junction = getattr(path, "is_junction", lambda: False)
    return path.is_symlink() or is_junction() or bool(attributes & reparse_flag)


def _payload_entries(root_path: Path) -> list[Path]:
    """Bounded enumeration without following a link or accepting a special filesystem node."""
    entries: list[Path] = []
    entry_count = 0
    file_count = 0

    def visit(directory: Path, depth: int) -> None:
        nonlocal entry_count, file_count
        children: list[Path] = []
        try:
            for child in directory.iterdir():
                entry_count += 1
                if entry_count > MAX_PAYLOAD_ENTRIES:
                    raise ValueError(
                        f"skill payload exceeds the {MAX_PAYLOAD_ENTRIES}-entry limit"
                    )
                children.append(child)
        except OSError as exc:
            raise ValueError(f"skill payload directory is unreadable: {directory}") from exc
        children.sort(key=lambda entry: (entry.name.casefold(), entry.name))
        folded_names: set[str] = set()
        for entry in children:
            child_depth = depth + 1
            if child_depth > MAX_PAYLOAD_DEPTH:
                raise ValueError(f"skill payload exceeds the depth limit at {entry}")
            folded = entry.name.casefold()
            if folded in folded_names:
                raise ValueError(
                    f"skill payload paths collide case-insensitively in {directory}"
                )
            folded_names.add(folded)
            try:
                metadata = entry.lstat()
            except OSError as exc:
                raise ValueError(f"skill payload path is unreadable: {entry}") from exc
            if _is_link_or_reparse(entry):
                raise ValueError(f"links/reparse points are forbidden in skill payloads: {entry}")
            if stat.S_ISDIR(metadata.st_mode):
                visit(entry, child_depth)
            elif stat.S_ISREG(metadata.st_mode):
                file_count += 1
                if file_count > MAX_PAYLOAD_FILES:
                    raise ValueError(
                        f"skill payload exceeds the {MAX_PAYLOAD_FILES}-file limit"
                    )
                entries.append(entry)
            else:
                raise ValueError(f"special filesystem nodes are forbidden in skill payloads: {entry}")

    visit(root_path, 0)
    return entries


def _payload_entries_posix(root_fd: int) -> list[PurePosixPath]:
    """Enumerate relative to one held root descriptor, never through a replaceable root path."""
    entries: list[PurePosixPath] = []
    entry_count = 0
    file_count = 0
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flag = getattr(os, "O_DIRECTORY", 0)

    def visit(directory_fd: int, prefix: PurePosixPath, depth: int) -> None:
        nonlocal entry_count, file_count
        try:
            with os.scandir(directory_fd) as iterator:
                children = list(iterator)
        except OSError as exc:
            raise ValueError(
                f"skill payload directory is unreadable: {prefix.as_posix() or '.'}"
            ) from exc
        entry_count += len(children)
        if entry_count > MAX_PAYLOAD_ENTRIES:
            raise ValueError(f"skill payload exceeds the {MAX_PAYLOAD_ENTRIES}-entry limit")
        children.sort(key=lambda entry: (entry.name.casefold(), entry.name))
        folded_names: set[str] = set()
        for entry in children:
            child_depth = depth + 1
            relative = prefix / entry.name
            if child_depth > MAX_PAYLOAD_DEPTH:
                raise ValueError(f"skill payload exceeds the depth limit at {relative}")
            folded = entry.name.casefold()
            if folded in folded_names:
                raise ValueError(
                    f"skill payload paths collide case-insensitively in {prefix.as_posix() or '.'}"
                )
            folded_names.add(folded)
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValueError(f"skill payload path is unreadable: {relative}") from exc
            if entry.is_symlink():
                raise ValueError(
                    f"links/reparse points are forbidden in skill payloads: {relative}"
                )
            if stat.S_ISDIR(metadata.st_mode):
                try:
                    child_fd = os.open(
                        entry.name,
                        os.O_RDONLY | directory_flag | nofollow | getattr(os, "O_CLOEXEC", 0),
                        dir_fd=directory_fd,
                    )
                except OSError as exc:
                    raise ValueError(
                        f"skill payload directory changed while being read: {relative}"
                    ) from exc
                try:
                    if not stat.S_ISDIR(os.fstat(child_fd).st_mode):
                        raise ValueError(
                            f"skill payload directory changed while being read: {relative}"
                        )
                    visit(child_fd, relative, child_depth)
                finally:
                    os.close(child_fd)
            elif stat.S_ISREG(metadata.st_mode):
                file_count += 1
                if file_count > MAX_PAYLOAD_FILES:
                    raise ValueError(f"skill payload exceeds the {MAX_PAYLOAD_FILES}-file limit")
                entries.append(relative)
            else:
                raise ValueError(f"special filesystem nodes are forbidden in skill payloads: {relative}")

    visit(root_fd, PurePosixPath(), 0)
    return entries


@contextmanager
def _posix_root_session(path: Path):
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory_flag or os.open not in os.supports_dir_fd:
        raise ValueError("secure no-follow payload reads are unavailable on this platform")
    descriptor = None
    try:
        descriptor = os.open(
            str(path),
            os.O_RDONLY | directory_flag | nofollow | getattr(os, "O_CLOEXEC", 0),
        )
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError(f"skill payload root is not a directory: {path}")
        yield descriptor
    except OSError as exc:
        raise ValueError(f"skill path is unreadable or changed: {path}") from exc
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass


@contextmanager
def _windows_root_session(path: Path):
    """Hold a no-delete-share root handle so the leased Windows path cannot be replaced."""
    import ctypes
    from ctypes import wintypes

    file_read_attributes = 0x0080
    share_read_write = 0x00000001 | 0x00000002
    open_existing = 3
    open_reparse = 0x00200000
    backup_semantics = 0x02000000
    attr_directory = 0x00000010
    attr_reparse = 0x00000400
    file_attribute_tag_info = 9
    invalid_handle = ctypes.c_void_p(-1).value

    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]

    class FileInformation(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("CreationTime", wintypes.FILETIME),
            ("LastAccessTime", wintypes.FILETIME),
            ("LastWriteTime", wintypes.FILETIME),
            ("VolumeSerialNumber", wintypes.DWORD),
            ("FileSizeHigh", wintypes.DWORD),
            ("FileSizeLow", wintypes.DWORD),
            ("NumberOfLinks", wintypes.DWORD),
            ("FileIndexHigh", wintypes.DWORD),
            ("FileIndexLow", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(FileInformation),
    ]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL

    handle = kernel.CreateFileW(
        str(path), file_read_attributes, share_read_write, None, open_existing,
        open_reparse | backup_semantics, None,
    )
    if handle == invalid_handle:
        raise ValueError(f"skill path is unreadable or changed: {path}")
    try:
        info = AttributeTagInfo()
        if not kernel.GetFileInformationByHandleEx(
            handle, file_attribute_tag_info, ctypes.byref(info), ctypes.sizeof(info),
        ):
            raise ValueError(f"skill path is unreadable or changed: {path}")
        if not info.FileAttributes & attr_directory or info.FileAttributes & attr_reparse:
            raise ValueError(f"skill path must be a regular non-link directory: {path}")
        identity = FileInformation()
        if not kernel.GetFileInformationByHandle(handle, ctypes.byref(identity)):
            raise ValueError(f"skill path is unreadable or changed: {path}")
        yield (
            identity.VolumeSerialNumber,
            (identity.FileIndexHigh << 32) | identity.FileIndexLow,
        )
    finally:
        kernel.CloseHandle(handle)


def _read_fd_bytes(fd: int, label: str) -> bytes:
    metadata = os.fstat(fd)
    if not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"skill payload path must be a regular file: {label}")
    if metadata.st_size > MAX_PAYLOAD_FILE_BYTES:
        raise ValueError(f"skill payload file exceeds the byte limit: {label}")
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = os.read(fd, _READ_CHUNK_BYTES)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_PAYLOAD_FILE_BYTES:
            raise ValueError(f"skill payload file exceeds the byte limit: {label}")
        chunks.append(chunk)
    return b"".join(chunks)


def _read_posix_payload(root_fd: int, relative: PurePosixPath) -> bytes:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flag = getattr(os, "O_DIRECTORY", 0)
    if not nofollow or not directory_flag or os.open not in os.supports_dir_fd:
        raise ValueError("secure no-follow payload reads are unavailable on this platform")
    descriptors: list[int] = []
    try:
        descriptor = os.dup(root_fd)
        descriptors.append(descriptor)
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError("skill payload root changed while being read")
        for component in relative.parts[:-1]:
            descriptor = os.open(
                component,
                os.O_RDONLY | directory_flag | nofollow | getattr(os, "O_CLOEXEC", 0),
                dir_fd=descriptor,
            )
            descriptors.append(descriptor)
            if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
                raise ValueError(f"skill payload directory changed while being read: {relative}")
        file_descriptor = os.open(
            relative.parts[-1],
            os.O_RDONLY | nofollow | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_CLOEXEC", 0),
            dir_fd=descriptor,
        )
        descriptors.append(file_descriptor)
        return _read_fd_bytes(file_descriptor, relative.as_posix())
    except OSError as exc:
        raise ValueError(f"skill payload path changed or is unreadable: {relative}") from exc
    finally:
        for descriptor in reversed(descriptors):
            try:
                os.close(descriptor)
            except OSError:
                pass


def _read_windows_payload(
    root: Path,
    relative: PurePosixPath,
    expected_root_identity: tuple[int, int] | None = None,
) -> bytes:
    """Open and read the final Windows file handle without following a reparse point."""
    import ctypes
    import ntpath
    from ctypes import wintypes

    generic_read = 0x80000000
    file_read_attributes = 0x0080
    share_all = 0x00000001 | 0x00000002 | 0x00000004
    open_existing = 3
    open_reparse = 0x00200000
    backup_semantics = 0x02000000
    attr_directory = 0x00000010
    attr_reparse = 0x00000400
    file_type_disk = 0x0001
    file_attribute_tag_info = 9
    invalid_handle = ctypes.c_void_p(-1).value

    class AttributeTagInfo(ctypes.Structure):
        _fields_ = [("FileAttributes", wintypes.DWORD), ("ReparseTag", wintypes.DWORD)]

    class FileInformation(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("CreationTime", wintypes.FILETIME),
            ("LastAccessTime", wintypes.FILETIME),
            ("LastWriteTime", wintypes.FILETIME),
            ("VolumeSerialNumber", wintypes.DWORD),
            ("FileSizeHigh", wintypes.DWORD),
            ("FileSizeLow", wintypes.DWORD),
            ("NumberOfLinks", wintypes.DWORD),
            ("FileIndexHigh", wintypes.DWORD),
            ("FileIndexLow", wintypes.DWORD),
        ]

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
        wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
    ]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.GetFileInformationByHandleEx.argtypes = [
        wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD,
    ]
    kernel.GetFileInformationByHandleEx.restype = wintypes.BOOL
    kernel.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(FileInformation),
    ]
    kernel.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel.GetFileType.argtypes = [wintypes.HANDLE]
    kernel.GetFileType.restype = wintypes.DWORD
    kernel.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD,
    ]
    kernel.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel.GetFileSizeEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_longlong)]
    kernel.GetFileSizeEx.restype = wintypes.BOOL
    kernel.ReadFile.argtypes = [
        wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID,
    ]
    kernel.ReadFile.restype = wintypes.BOOL

    def close(handle) -> None:
        if handle not in (None, invalid_handle):
            kernel.CloseHandle(handle)

    def open_handle(path: Path, *, directory: bool):
        handle = kernel.CreateFileW(
            str(path), file_read_attributes if directory else generic_read, share_all, None,
            open_existing, open_reparse | backup_semantics, None,
        )
        if handle == invalid_handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            info = AttributeTagInfo()
            if not kernel.GetFileInformationByHandleEx(
                handle, file_attribute_tag_info, ctypes.byref(info), ctypes.sizeof(info),
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            is_directory = bool(info.FileAttributes & attr_directory)
            if info.FileAttributes & attr_reparse or is_directory is not directory:
                raise ValueError(f"skill payload path is a link or has the wrong type: {path}")
            if not directory and kernel.GetFileType(handle) != file_type_disk:
                raise ValueError(f"skill payload path is not a disk file: {path}")
            return handle
        except Exception:
            close(handle)
            raise

    def final_path(handle) -> str:
        needed = kernel.GetFinalPathNameByHandleW(handle, None, 0, 0)
        if not needed:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_unicode_buffer(needed + 1)
        copied = kernel.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not copied or copied >= len(buffer):
            raise ctypes.WinError(ctypes.get_last_error())
        value = buffer.value
        if value.startswith("\\\\?\\UNC\\"):
            value = "\\\\" + value[8:]
        elif value.startswith("\\\\?\\"):
            value = value[4:]
        return ntpath.normcase(ntpath.normpath(value))

    root_handle = file_handle = None
    try:
        root_handle = open_handle(root, directory=True)
        root_identity = FileInformation()
        if not kernel.GetFileInformationByHandle(root_handle, ctypes.byref(root_identity)):
            raise ctypes.WinError(ctypes.get_last_error())
        observed_root_identity = (
            root_identity.VolumeSerialNumber,
            (root_identity.FileIndexHigh << 32) | root_identity.FileIndexLow,
        )
        if expected_root_identity is not None and observed_root_identity != expected_root_identity:
            raise ValueError("skill payload root was replaced while being read")
        root_final = final_path(root_handle)
        expected = ntpath.normcase(ntpath.normpath(ntpath.join(root_final, *relative.parts)))
        target = root.joinpath(*relative.parts)
        file_handle = open_handle(target, directory=False)
        if final_path(file_handle) != expected:
            raise ValueError(f"skill payload path escapes or aliases its leased scope: {relative}")
        size = ctypes.c_longlong()
        if not kernel.GetFileSizeEx(file_handle, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        if size.value < 0 or size.value > MAX_PAYLOAD_FILE_BYTES:
            raise ValueError(f"skill payload file exceeds the byte limit: {relative}")
        chunks: list[bytes] = []
        total = 0
        while True:
            buffer = ctypes.create_string_buffer(_READ_CHUNK_BYTES)
            read = wintypes.DWORD()
            if not kernel.ReadFile(
                file_handle, buffer, _READ_CHUNK_BYTES, ctypes.byref(read), None,
            ):
                raise ctypes.WinError(ctypes.get_last_error())
            if read.value == 0:
                break
            total += read.value
            if total > MAX_PAYLOAD_FILE_BYTES:
                raise ValueError(f"skill payload file exceeds the byte limit: {relative}")
            chunks.append(buffer.raw[:read.value])
        return b"".join(chunks)
    except OSError as exc:
        raise ValueError(f"skill payload path changed or is unreadable: {relative}") from exc
    finally:
        close(file_handle)
        close(root_handle)


def _read_utf8_payload(
    root: Path | int,
    relative: PurePosixPath,
    windows_root_identity: tuple[int, int] | None = None,
) -> str:
    raw = (
        _read_windows_payload(root, relative, windows_root_identity)
        if os.name == "nt"
        else _read_posix_payload(root, relative)
    )
    try:
        value = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"binary payload files are not supported: {relative}") from exc
    if "\x00" in value:
        raise ValueError(f"NUL bytes are not allowed in skill payload files: {relative}")
    return value


def load_skill_dir(path: str | Path) -> tuple[str, dict[str, str]]:
    """Read one fully-contained, UTF-8-only skill payload without following links/reparse points."""
    p = Path(path)

    def read_session(
        root: Path | int,
        relative_paths: list[PurePosixPath],
        windows_root_identity: tuple[int, int] | None = None,
    ):
        names = {relative.as_posix() for relative in relative_paths}
        if "SKILL.md" not in names:
            raise ValueError(f"no SKILL.md found in {p}")
        embedded_reviews = [
            relative for relative in relative_paths if relative.name.casefold() == "review.json"
        ]
        if embedded_reviews:
            raise ValueError(
                "governance metadata must not be embedded in a skill payload: "
                f"{embedded_reviews[0]}"
            )
        skill_md = _read_utf8_payload(
            root, PurePosixPath("SKILL.md"), windows_root_identity,
        )
        files: dict[str, str] = {}
        total = len(skill_md.encode("utf-8"))
        for rel in sorted((name for name in names if name != "SKILL.md"),
                          key=lambda name: (name.casefold(), name)):
            value = _read_utf8_payload(root, PurePosixPath(rel), windows_root_identity)
            total += len(value.encode("utf-8"))
            if total > MAX_PAYLOAD_TOTAL_BYTES:
                raise ValueError("skill payload exceeds the total byte limit")
            files[rel] = value
        _validate_payload_budget(skill_md, files)
        return skill_md, files

    if os.name == "nt":
        with _windows_root_session(p) as root_identity:
            if _is_link_or_reparse(p) or not p.is_dir():
                raise ValueError(f"skill path must be a regular non-link directory: {p}")
            try:
                root = p.resolve(strict=True)
            except OSError as exc:
                raise ValueError(f"skill path is unreadable: {p}") from exc
            entries = _payload_entries(p)
            relatives = [PurePosixPath(entry.relative_to(p).as_posix()) for entry in entries]
            return read_session(root, relatives, root_identity)

    with _posix_root_session(p) as root_fd:
        return read_session(root_fd, _payload_entries_posix(root_fd))
