import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

_MIGRATION_LOCK = 0x53454D49534B494C
_MIGRATION_NAME = re.compile(r"^[0-9]{4}_[a-z0-9_]+\.sql$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PLAN_SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_LEGACY_MANIFEST = Path(__file__).with_name("legacy_migration_manifest.json")

_FORWARD_PLAN_SCHEMA = "migration-forward-plan/v1"
_FORWARD_EVIDENCE_SCHEMA = "migration-forward-execution/v1"
_FORWARD_AUDIT_NAMESPACE = uuid.UUID("e79d5d73-8b2a-5a8a-8c9d-6b25c86cb77b")
_MIGRATION_AUTHORITY_SCHEMAS = frozenset({
    "migration-checksum-adoption/v1",
    _FORWARD_EVIDENCE_SCHEMA,
})
_ADOPTION_SCHEMA_ATTESTATION_KEYS = frozenset({
    "approval_index_exact",
    "artifact_enum_security_exact",
    "artifact_enums_exact",
    "artifact_triggers_exact",
    "artifacts_columns_exact",
    "artifacts_constraints_exact",
    "artifacts_owned_by_migrator",
    "authority_column_acls_absent",
    "authority_index_inventories_exact",
    "authority_relations_have_no_inheritance",
    "foundation_role_separation",
    "foundation_roles_hardened",
    "function_definitions_exact",
    "function_security_exact",
    "governed_functions_pinned",
    "held_out_seed_exact",
    "held_out_tables_exact",
    "migration_tracker_has_no_triggers",
    "pending_0011_boundary_clean",
    "public_function_inventory_exact",
    "public_schema_shadow_surface_absent",
    "relation_security_exact",
    "schema_and_default_acl_exact",
    "tracker_contract_exact",
})
_STORED_ADOPTION_0015_ATTESTATION_KEYS = frozenset({
    "authority_triggers_exact",
    "capability_memberships_exact",
    "capability_roles_hardened",
    "critical_projection_index_exact",
    "direct_table_boundary_exact",
    "function_boundary_exact",
    "projection_and_policy_start_empty",
    "public_schema_create_revoked",
    "required_functions_present",
    "required_relations_present",
    "security_definer_paths_hardened",
})
_CHECKPOINT_0015_ATTESTATION_KEYS = _STORED_ADOPTION_0015_ATTESTATION_KEYS | {
    "held_out_seed_exact",
    "judge_gold_set_empty",
    "registry_rows_exact",
    "schema_inventory_exact",
}
_CHECKPOINT_0015_SCHEMA_SHA256 = (
    "7220c78682898c6f0edad2859576eb59a217593fec086b6ac3dfd09c752b3d8a"
)
_CHECKPOINT_0015_CORPUS_SHA256 = (
    "a14f815966f9610fa9efe5122cdde8340c1f47701d7ec48cc98baff8aed328bf"
)
_CHECKPOINT_0023_SCHEMA_SHA256 = (
    "45ca37a423b6a77db9a281cc37dce8141935e8524178ffefe7573cd431aeba58"
)
_CHECKPOINT_REGISTRY_SHA256 = (
    "982793b0616bdd86ff6c47f8f5afecde352b2216490c35731593bf4d1b5128b3"
)
_BASELINE_INJECTION_ROWS = frozenset({
    ("exfiltration", "exfiltrat", "restricted"),
    (
        "exfiltration",
        r"send\s+.{0,60}(secret|token|password|credential|api[_-]?key).{0,60}(to|https?://)",
        "restricted",
    ),
    ("injection", r"disregard\s+(the\s+)?(above|previous|system)", "restricted"),
    (
        "injection",
        r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
        "restricted",
    ),
    ("injection", r"you\s+are\s+now\s+(a|an|the)\s", "restricted"),
    ("scope-violation", "echoleak", "restricted"),
    (
        "scope-violation",
        r"(read|access|leak)\s+.{0,60}(other\s+users|another\s+context|cross[- ]context)",
        "restricted",
    ),
    ("tool-abuse", r"execute\s+arbitrary\s+(code|commands)", "restricted"),
    (
        "tool-abuse",
        r"run\s+the\s+following\s+(shell|command|bash|script)",
        "restricted",
    ),
})
_POST_MIGRATION_ATTESTATION_KEYS = frozenset({
    "authority_triggers_exact",
    "capability_memberships_exact",
    "capability_roles_hardened",
    "critical_projection_index_exact",
    "direct_table_boundary_exact",
    "function_boundary_exact",
    "held_out_baseline_intact",
    "projection_and_policy_start_empty",
    "public_schema_create_revoked",
    "review_root_index_exact",
    "registry_rows_exact",
    "required_functions_present",
    "required_relations_present",
    "security_definer_paths_hardened",
    "schema_inventory_exact",
})
_POST_MIGRATION_STABLE_ATTESTATION_KEYS = (
    _POST_MIGRATION_ATTESTATION_KEYS - {"projection_and_policy_start_empty"}
)
_FORWARD_POLICIES = {
    (
        "0015_projection_truncate_hardening.sql",
        "0023_review_unbound_parameter_binding.sql",
    ): {
        "policy_id": "migration/0015-to-0023@1",
        "pre_attestation_policy_id": "schema/0015@1",
        "post_attestation_policy_id": "schema/0023@1",
    },
}

_TRACKER = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    sha256 text
);
ALTER TABLE public.schema_migrations ADD COLUMN IF NOT EXISTS sha256 text;
"""

class MigrationAdoptionRefused(RuntimeError):
    """Legacy migration history was not safe to attest or changed after review."""


def _resolve_migration_source(repo_root: str | Path) -> tuple[Path, str]:
    root = Path(repo_root).resolve()
    canonical_root = Path(__file__).resolve().parents[2]
    expected_module = root / "semiskill" / "artifacts" / "migrate.py"
    expected_manifest = root / "semiskill" / "artifacts" / "legacy_migration_manifest.json"
    directory = root / "semiskill" / "artifacts" / "migrations"
    try:
        if (root != canonical_root
                or not expected_module.samefile(Path(__file__).resolve())
                or not expected_manifest.samefile(_LEGACY_MANIFEST.resolve())):
            raise MigrationAdoptionRefused(
                "running adoption code is not sourced from the reviewed repository"
            )
        git_env = {
            key: value for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        top_level = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True,
            text=True, check=True, timeout=10, env=git_env,
        ).stdout.strip()
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
            text=True, check=True, timeout=10, env=git_env,
        ).stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain=v1"], capture_output=True,
            text=True, check=True, timeout=10, env=git_env,
        ).stdout
    except MigrationAdoptionRefused:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise MigrationAdoptionRefused("source repository identity could not be established") from exc
    if Path(top_level).resolve() != root or not _COMMIT.fullmatch(head) or dirty:
        raise MigrationAdoptionRefused(
            "migration adoption requires one clean exact source commit"
        )
    try:
        tracked_output = subprocess.run(
            ["git", "-C", str(root), "ls-tree", "-r", "--name-only", "HEAD", "--",
             "semiskill/artifacts/migrations"],
            capture_output=True, text=True, check=True, timeout=10, env=git_env,
        ).stdout
        tracked_migrations = sorted(
            line.strip() for line in tracked_output.splitlines() if line.strip().endswith(".sql")
        )
        actual_migrations = sorted(
            f"semiskill/artifacts/migrations/{path.name}"
            for path in directory.iterdir() if path.name.lower().endswith(".sql")
        )
        if tracked_migrations != actual_migrations:
            raise MigrationAdoptionRefused(
                "migration directory does not exactly match the committed source tree"
            )
        bound_paths = [
            "semiskill/artifacts/migrate.py",
            "semiskill/artifacts/legacy_migration_manifest.json",
            "semiskill/cli.py",
            "semiskill/governance/identity.py",
            *tracked_migrations,
        ]
        for relative in bound_paths:
            _safe_read_bytes(root / Path(relative), max_bytes=2_000_000)
            committed_oid = subprocess.run(
                ["git", "-C", str(root), "rev-parse", f"HEAD:{relative}"],
                capture_output=True, text=True, check=True, timeout=10, env=git_env,
            ).stdout.strip()
            working_oid = subprocess.run(
                ["git", "-C", str(root), "hash-object", f"--path={relative}", relative],
                capture_output=True, text=True, check=True, timeout=10, env=git_env,
            ).stdout.strip()
            if committed_oid != working_oid:
                raise MigrationAdoptionRefused(
                    "migration source bytes do not equal the recorded commit"
                )
    except MigrationAdoptionRefused:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise MigrationAdoptionRefused(
            "committed migration source could not be attested"
        ) from exc
    # The secure manifest reader performs the final directory/link checks.
    return directory, head


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _is_reparse(path: Path) -> bool:
    info = os.lstat(path)
    attributes = getattr(info, "st_file_attributes", 0)
    return bool(attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))


def _safe_read_bytes(path: Path, *, max_bytes: int) -> bytes:
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise MigrationAdoptionRefused(f"trusted file is unavailable: {path.name}") from exc
    if (not stat.S_ISREG(before.st_mode) or path.is_symlink() or _is_reparse(path)
            or before.st_size > max_bytes):
        raise MigrationAdoptionRefused(f"trusted file is not a bounded regular file: {path.name}")
    try:
        raw = path.read_bytes()
        after = os.lstat(path)
    except OSError as exc:
        raise MigrationAdoptionRefused(f"trusted file could not be read: {path.name}") from exc
    witness_before = (
        before.st_dev, before.st_ino, before.st_mode, before.st_size, before.st_mtime_ns,
        getattr(before, "st_file_attributes", 0),
    )
    witness_after = (
        after.st_dev, after.st_ino, after.st_mode, after.st_size, after.st_mtime_ns,
        getattr(after, "st_file_attributes", 0),
    )
    if witness_before != witness_after or len(raw) != before.st_size:
        raise MigrationAdoptionRefused(f"trusted file changed while being read: {path.name}")
    return raw


def _repository_manifest(directory: Path) -> list[dict[str, str | int]]:
    try:
        root_info = os.lstat(directory)
    except OSError as exc:
        raise MigrationAdoptionRefused("migration directory is unavailable") from exc
    if not stat.S_ISDIR(root_info.st_mode) or directory.is_symlink() or _is_reparse(directory):
        raise MigrationAdoptionRefused("migration directory must be a real local directory")
    candidates = sorted(
        (path for path in directory.iterdir() if path.name.lower().endswith(".sql")),
        key=lambda path: path.name,
    )
    if not candidates:
        raise MigrationAdoptionRefused("migration repository is empty")
    if len(candidates) > 128:
        raise MigrationAdoptionRefused("migration repository exceeds the bounded file count")
    lowered: set[str] = set()
    manifest: list[dict[str, str]] = []
    for path in candidates:
        if not _MIGRATION_NAME.fullmatch(path.name):
            raise MigrationAdoptionRefused(f"noncanonical migration filename: {path.name}")
        folded = path.name.casefold()
        if folded in lowered:
            raise MigrationAdoptionRefused("case-colliding migration filenames")
        lowered.add(folded)
        raw = _safe_read_bytes(path, max_bytes=2_000_000)
        manifest.append({
            "filename": path.name,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        })
    return manifest


def _assert_repository_matches_commit(
    directory: Path,
    source_commit: str,
    repository: list[dict[str, str | int]],
) -> None:
    """Rebind the just-read manifest to Git after collection, closing the resolve/read race."""
    canonical_directory = Path(__file__).resolve().parent / "migrations"
    if directory.resolve() != canonical_directory:
        # Disposable integration databases inject an isolated byte-for-byte migration directory.
        # Public callers cannot choose this path: _resolve_migration_source requires canonical root.
        return
    root = Path(__file__).resolve().parents[2]
    git_env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True,
            text=True, check=True, timeout=10, env=git_env,
        ).stdout.strip()
        if head != source_commit:
            raise MigrationAdoptionRefused("source commit changed during manifest collection")
        committed_names = sorted(
            line.strip().rsplit("/", 1)[-1]
            for line in subprocess.run(
                ["git", "-C", str(root), "ls-tree", "-r", "--name-only",
                 source_commit, "--", "semiskill/artifacts/migrations"],
                capture_output=True, text=True, check=True, timeout=10, env=git_env,
            ).stdout.splitlines()
            if line.strip().endswith(".sql")
        )
        collected_names = sorted(str(item["filename"]) for item in repository)
        if collected_names != committed_names:
            raise MigrationAdoptionRefused(
                "collected migration set does not equal the recorded commit"
            )
        for item in repository:
            relative = f"semiskill/artifacts/migrations/{item['filename']}"
            working = _safe_read_bytes(directory / str(item["filename"]), max_bytes=2_000_000)
            committed_oid = subprocess.run(
                ["git", "-C", str(root), "rev-parse", f"{source_commit}:{relative}"],
                capture_output=True, text=True, check=True, timeout=10, env=git_env,
            ).stdout.strip()
            working_oid = subprocess.run(
                ["git", "-C", str(root), "hash-object", f"--path={relative}", relative],
                capture_output=True, text=True, check=True, timeout=10, env=git_env,
            ).stdout.strip()
            if (len(working) != item["bytes"]
                    or hashlib.sha256(working).hexdigest() != item["sha256"]
                    or committed_oid != working_oid):
                raise MigrationAdoptionRefused(
                    "collected migration manifest does not equal the recorded commit"
                )
    except MigrationAdoptionRefused:
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        raise MigrationAdoptionRefused(
            "collected migration manifest could not be rebound to source"
        ) from exc


def _assert_trusted_manifest_matches_commit(
    directory: Path,
    source_commit: str,
    trusted_digest: str,
) -> None:
    """Bind the in-memory legacy contract to the same commit after its working-tree read."""
    canonical_directory = Path(__file__).resolve().parent / "migrations"
    if directory.resolve() != canonical_directory:
        return
    root = Path(__file__).resolve().parents[2]
    git_env = {
        key: value for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    try:
        raw = subprocess.run(
            ["git", "-C", str(root), "cat-file", "blob",
             f"{source_commit}:semiskill/artifacts/legacy_migration_manifest.json"],
            capture_output=True, check=True, timeout=10, env=git_env,
        ).stdout
        committed = json.loads(raw)
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        raise MigrationAdoptionRefused(
            "committed legacy trust contract could not be read"
        ) from exc
    committed_digest = "sha256:" + hashlib.sha256(_canonical_bytes(committed)).hexdigest()
    if committed_digest != trusted_digest:
        raise MigrationAdoptionRefused(
            "legacy trust contract does not equal the recorded commit"
        )


def _trusted_legacy_manifest(repository: list[dict]) -> tuple[dict, str]:
    try:
        raw = _safe_read_bytes(_LEGACY_MANIFEST, max_bytes=100_000)
        trusted = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise MigrationAdoptionRefused("trusted legacy migration manifest is unavailable") from exc
    expected_keys = {
        "schema_version", "historical_limit", "injection_corpus_sha256",
        "artifacts_columns_sha256", "artifacts_constraints_sha256",
        "approval_index_sha256", "artifact_triggers_sha256",
        "function_security_sha256", "public_function_inventory_sha256",
        "relation_security_sha256", "tracker_columns_sha256",
        "tracker_constraints_sha256", "artifacts_index_inventory_sha256",
        "tracker_index_inventory_sha256", "public_schema_acl_sha256",
        "default_acl_sha256", "held_out_table_sha256",
        "function_definition_sha256", "known_orphaned_test_fixtures", "migrations",
    }
    if not isinstance(trusted, dict) or set(trusted) != expected_keys:
        raise MigrationAdoptionRefused("trusted legacy migration manifest has unknown fields")
    if trusted.get("schema_version") != "migration-checksum-adoption/v1":
        raise MigrationAdoptionRefused("trusted legacy migration manifest has the wrong schema")
    rows = trusted.get("migrations")
    if not isinstance(rows, list) or len(rows) != 10:
        raise MigrationAdoptionRefused("trusted legacy migration manifest is empty")
    expected = []
    for row in rows:
        if not isinstance(row, dict) or not _MIGRATION_NAME.fullmatch(str(row.get("filename", ""))):
            raise MigrationAdoptionRefused("trusted legacy migration manifest has a bad filename")
        if not _SHA256.fullmatch(str(row.get("sha256", ""))):
            raise MigrationAdoptionRefused("trusted legacy migration manifest has a bad checksum")
        expected.append({"filename": row["filename"], "sha256": row["sha256"]})
    repository_hashes = [
        {"filename": row["filename"], "sha256": row["sha256"]}
        for row in repository[:len(expected)]
    ]
    if len({row["filename"] for row in expected}) != len(expected) or expected != repository_hashes:
        raise MigrationAdoptionRefused(
            "repository bytes do not match the trusted legacy migration manifest"
        )
    if not isinstance(trusted.get("historical_limit"), str) or not trusted["historical_limit"]:
        raise MigrationAdoptionRefused("trusted historical limitation is malformed")
    digest = "sha256:" + hashlib.sha256(_canonical_bytes(trusted)).hexdigest()
    return trusted, digest


def _database_identity(conn) -> dict[str, str]:
    database, address, port, version, session_user, current_user, owner = conn.execute(
        "SELECT current_database(),coalesce(inet_server_addr()::text,'local'),"
        "coalesce(inet_server_port(),0)::text,current_setting('server_version_num'),"
        "session_user,current_user,(SELECT pg_get_userbyid(datdba) FROM pg_database "
        "WHERE datname=current_database())"
    ).fetchone()
    if session_user != current_user or session_user != owner:
        raise MigrationAdoptionRefused(
            "legacy adoption requires the database-owner migration session"
        )
    expected_migrator = os.environ.get("SEMISKILL_MIGRATOR_ROLE")
    if not expected_migrator or session_user != expected_migrator:
        raise MigrationAdoptionRefused(
            "database session is not the explicitly configured migration identity"
        )
    safe = {
        "engine": "postgresql",
        "database_name": database,
        "server_version_num": version,
        "session_user_sha256": "sha256:" + hashlib.sha256(
            session_user.encode("utf-8")
        ).hexdigest(),
    }
    private_identity = {**safe, "server_address": address, "server_port": port}
    safe["identity_sha256"] = "sha256:" + hashlib.sha256(
        _canonical_bytes(private_identity)
    ).hexdigest()
    return safe


def _validate_database_environment(identity: dict, environment: str) -> None:
    database = identity.get("database_name")
    if not isinstance(database, str) or not database:
        raise MigrationAdoptionRefused("database identity is incomplete")
    is_test = database.lower().endswith("_test")
    production_name = os.environ.get("SEMISKILL_PRODUCTION_DATABASE_NAME")
    development_name = os.environ.get("SEMISKILL_DEVELOPMENT_DATABASE_NAME")
    if environment == "test" and not is_test:
        raise MigrationAdoptionRefused("test adoption requires an isolated *_test database")
    if environment == "development" and (
        is_test or not development_name or not production_name
        or development_name == production_name
        or database != development_name or database == production_name
    ):
        raise MigrationAdoptionRefused("development database identity is inconsistent")
    if environment == "production":
        if (not production_name or not development_name
                or production_name == development_name
                or database != production_name or is_test):
            raise MigrationAdoptionRefused(
                "production database identity is not explicitly configured"
            )
    if environment not in {"development", "test", "production"}:
        raise MigrationAdoptionRefused("a known migration environment is required")


def _schema_attestations(conn, *, trusted: dict) -> dict[str, bool]:
    columns = [list(row) for row in conn.execute(
        "SELECT column_name,udt_name,is_nullable,column_default,numeric_precision,numeric_scale "
        "FROM information_schema.columns WHERE table_schema='public' AND table_name='artifacts' "
        "ORDER BY ordinal_position"
    )]
    constraints = [list(row) for row in conn.execute(
        "SELECT conname,contype,pg_get_constraintdef(oid,true) FROM pg_constraint "
        "WHERE conrelid='public.artifacts'::regclass ORDER BY conname"
    )]
    enums = {
        name: [row[0] for row in conn.execute(
            "SELECT enumlabel FROM pg_enum JOIN pg_type ON pg_type.oid=enumtypid "
            "JOIN pg_namespace n ON n.oid=pg_type.typnamespace "
            "WHERE n.nspname='public' AND typname=%s ORDER BY enumsortorder", (name,),
        )]
        for name in ("artifact_type", "source_system", "actor_kind")
    }
    enum_security = [tuple(row) for row in conn.execute(
        "SELECT typname,pg_get_userbyid(typowner)=session_user,"
        "coalesce(array_to_string(typacl,','),'') FROM pg_type t "
        "JOIN pg_namespace n ON n.oid=t.typnamespace WHERE n.nspname='public' "
        "AND typname IN ('artifact_type','source_system','actor_kind') ORDER BY typname"
    )]
    expected_function_hashes = trusted.get("function_definition_sha256")
    definitions: dict[str, str | None] = {}
    governed: dict[str, tuple[bool, list[str]]] = {}
    if isinstance(expected_function_hashes, dict):
        for signature in expected_function_hashes:
            row = conn.execute(
                "SELECT pg_get_functiondef(p.oid),p.prosecdef,p.proconfig "
                "FROM pg_proc p WHERE p.oid=to_regprocedure(%s)",
                (f"public.{signature}",),
            ).fetchone()
            definitions[signature] = hashlib.sha256(row[0].encode("utf-8")).hexdigest() if row else None
            if row:
                governed[signature] = (row[1], row[2] or [])
    trigger_bindings = [list(row) for row in conn.execute(
        "SELECT t.tgname,t.tgtype,t.tgenabled,pg_get_triggerdef(t.oid,true),"
        "n.nspname,p.proname,pg_get_function_identity_arguments(p.oid) "
        "FROM pg_trigger t JOIN pg_proc p ON p.oid=t.tgfoid "
        "JOIN pg_namespace n ON n.oid=p.pronamespace WHERE NOT t.tgisinternal "
        "AND t.tgrelid='public.artifacts'::regclass ORDER BY t.tgname"
    )]
    public_function_inventory = [row[0] for row in conn.execute(
        "SELECT p.oid::regprocedure::text FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY 1"
    )]
    function_security = [list(row) for row in conn.execute(
        "SELECT p.oid::regprocedure::text,pg_get_userbyid(p.proowner),p.prosecdef,p.proconfig,"
        "coalesce(array_to_string(p.proacl,','),'') FROM pg_proc p JOIN pg_namespace n "
        "ON n.oid=p.pronamespace WHERE n.nspname='public' ORDER BY 1"
    )]
    index_row = conn.execute(
        "SELECT x.indexdef,i.indisunique,i.indisvalid,i.indisready,i.indislive,"
        "t.oid='public.artifacts'::regclass FROM pg_indexes x "
        "JOIN pg_class c ON c.relname=x.indexname JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_index i ON i.indexrelid=c.oid JOIN pg_class t ON t.oid=i.indrelid "
        "WHERE x.schemaname='public' AND n.nspname='public' "
        "AND x.indexname='one_approval_correction_per_head'"
    ).fetchone()
    foundation_roles = [tuple(row) for row in conn.execute(
        "SELECT rolname,rolinherit,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
        "rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname IN "
        "('semiskill_app','semiskill_submitter','semiskill_pipeline') ORDER BY rolname"
    )]
    held_schemas = {}
    for table in ("injection_corpus", "judge_gold_set"):
        held_columns = [list(row) for row in conn.execute(
            "SELECT column_name,udt_name,is_nullable,column_default "
            "FROM information_schema.columns WHERE table_schema='public' AND table_name=%s "
            "ORDER BY ordinal_position", (table,),
        )]
        held_constraints = [list(row) for row in conn.execute(
            "SELECT conname,contype,pg_get_constraintdef(oid,true) FROM pg_constraint "
            "WHERE conrelid=to_regclass(%s) ORDER BY conname", (f"public.{table}",),
        )]
        indexes = [row[0] for row in conn.execute(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND tablename=%s "
            "ORDER BY indexname", (table,),
        )]
        triggers = [list(row) for row in conn.execute(
            "SELECT t.tgname,pg_get_triggerdef(t.oid,true),n.nspname,p.proname,"
            "pg_get_function_identity_arguments(p.oid) FROM pg_trigger t "
            "JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE NOT t.tgisinternal AND t.tgrelid=to_regclass(%s) ORDER BY t.tgname",
            (f"public.{table}",),
        )]
        held_schemas[table] = hashlib.sha256(_canonical_bytes({
            "columns": held_columns,
            "constraints": held_constraints,
            "indexes": indexes,
            "triggers": triggers,
        })).hexdigest()
    corpus_rows = [list(row) for row in conn.execute(
        "SELECT probe_class,pattern FROM public.injection_corpus ORDER BY probe_class,pattern"
    )]
    relation_security = [list(row) for row in conn.execute(
        "SELECT c.relname,c.relkind,c.relpersistence,c.relispartition,"
        "coalesce(t.spcname,''),pg_get_userbyid(c.relowner),c.relrowsecurity,"
        "c.relforcerowsecurity,coalesce(array_to_string(c.relacl,','),'') "
        "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_tablespace t ON t.oid=c.reltablespace "
        "WHERE n.nspname='public' AND c.relname=ANY("
        "ARRAY['artifacts','injection_corpus','judge_gold_set','schema_migrations']) "
        "ORDER BY c.relname"
    )]
    tracker_columns = [list(row) for row in conn.execute(
        "SELECT column_name,udt_name,is_nullable,column_default "
        "FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='schema_migrations' ORDER BY ordinal_position"
    )]
    tracker_constraints = [list(row) for row in conn.execute(
        "SELECT conname,contype,pg_get_constraintdef(oid,true) FROM pg_constraint "
        "WHERE conrelid='public.schema_migrations'::regclass ORDER BY conname"
    )]
    index_inventory = {}
    for table in ("artifacts", "schema_migrations"):
        index_inventory[table] = [list(row) for row in conn.execute(
            "SELECT x.indexname,x.indexdef,i.indisunique,i.indisprimary,i.indisvalid,"
            "i.indisready,i.indislive,i.indkey::text,"
            "coalesce(pg_get_expr(i.indexprs,i.indrelid),''),"
            "coalesce(pg_get_expr(i.indpred,i.indrelid),'') FROM pg_indexes x "
            "JOIN pg_class ci ON ci.relname=x.indexname "
            "JOIN pg_namespace ni ON ni.oid=ci.relnamespace "
            "JOIN pg_index i ON i.indexrelid=ci.oid WHERE x.schemaname='public' "
            "AND ni.nspname='public' AND x.tablename=%s ORDER BY x.indexname",
            (table,),
        )]
    public_schema_acl = list(conn.execute(
        "SELECT pg_get_userbyid(nspowner),coalesce(array_to_string(nspacl,','),'') "
        "FROM pg_namespace WHERE nspname='public'"
    ).fetchone())
    default_acl = [list(row) for row in conn.execute(
        "SELECT d.defaclrole::regrole::text,coalesce(n.nspname,''),d.defaclobjtype,"
        "array_to_string(d.defaclacl,',') FROM pg_default_acl d LEFT JOIN pg_namespace n "
        "ON n.oid=d.defaclnamespace ORDER BY 1,2,3"
    )]
    column_acls = [list(row) for row in conn.execute(
        "SELECT c.relname,a.attname,array_to_string(a.attacl,',') FROM pg_attribute a "
        "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname=ANY("
        "ARRAY['artifacts','injection_corpus','judge_gold_set','schema_migrations']) "
        "AND a.attnum>0 AND NOT a.attisdropped AND a.attacl IS NOT NULL "
        "ORDER BY c.relname,a.attnum"
    )]
    foundation_role_names = {
        "semiskill_app", "semiskill_submitter", "semiskill_pipeline",
    }
    pending_roles = {
        "semiskill_approval_actuator", "semiskill_review_coordinator",
        "semiskill_acl_reader", "semiskill_export_reader",
        "semiskill_export_label_public", "semiskill_export_label_team",
        "semiskill_export_label_need_to_know", "semiskill_export_label_regulated",
    }
    present_pending_roles = [tuple(row) for row in conn.execute(
        "SELECT rolname,rolinherit,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
        "rolreplication,rolbypassrls "
        "FROM pg_roles WHERE rolname=ANY(%s) ORDER BY rolname", (list(pending_roles),),
    )]
    pending_roles_safe = all(
        row[1:] == (False, False, False, False, False, False, False)
                             for row in present_pending_roles)
    capability_roles = foundation_role_names | pending_roles
    capability_memberships = [tuple(row) for row in conn.execute(
        "SELECT granted.rolname,member.rolname,m.admin_option FROM pg_auth_members m "
        "JOIN pg_roles granted ON granted.oid=m.roleid "
        "JOIN pg_roles member ON member.oid=m.member "
        "WHERE granted.rolname=ANY(%s) OR member.rolname=ANY(%s) "
        "ORDER BY granted.rolname,member.rolname",
        (list(capability_roles), list(capability_roles)),
    )]
    session_user = conn.execute("SELECT session_user").fetchone()[0]
    capability_memberships_safe = all(
        granted in capability_roles and member == session_user and not admin_option
        for granted, member, admin_option in capability_memberships
    )
    pending_objects = (
        "publication_trust_policy", "publication_skill_registry", "verified_publication_events",
        "verified_review_contracts", "verified_review_contract_cells",
        "one_verified_correction_per_head", "content_review_v2_one_root_per_slug",
    )
    pending_functions = (
        "activate_verified_publication(uuid)", "verified_active_publication_heads_v1()",
        "export_scoped_publication_bundle_v2(text)",
        "append_verified_review_contract(uuid,source_system,text,actor_kind,timestamp with time zone,"
        "timestamp with time zone,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,jsonb)",
        "review_contract_authentication_valid_v1(uuid)",
        "review_contract_matches_v1(uuid,uuid,uuid)",
    )
    table_owner_is_session = conn.execute(
        "SELECT pg_get_userbyid(relowner)=session_user FROM pg_class "
        "WHERE oid='public.artifacts'::regclass"
    ).fetchone() == (True,)
    no_tracker_triggers = conn.execute(
        "SELECT count(*)=0 FROM pg_trigger WHERE NOT tgisinternal "
        "AND tgrelid='public.schema_migrations'::regclass"
    ).fetchone() == (True,)
    role_separation = conn.execute(
        "SELECT "
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE']) p "
        "WHERE has_table_privilege('semiskill_app','public.artifacts',p)),"
        "has_table_privilege('semiskill_submitter','public.artifacts','INSERT'),"
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p "
        "WHERE has_table_privilege('semiskill_submitter','public.artifacts',p)),"
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p "
        "WHERE has_table_privilege('semiskill_pipeline','public.injection_corpus',p)),"
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p "
        "WHERE has_table_privilege('semiskill_pipeline','public.judge_gold_set',p))"
    ).fetchone() == (True, True, True, True, True)
    expected_held = trusted.get("held_out_table_sha256")
    return {
        "artifacts_columns_exact": hashlib.sha256(_canonical_bytes(columns)).hexdigest()
        == trusted.get("artifacts_columns_sha256"),
        "artifacts_constraints_exact": hashlib.sha256(_canonical_bytes(constraints)).hexdigest()
        == trusted.get("artifacts_constraints_sha256"),
        "artifact_enums_exact": enums == {
            "artifact_type": [
                "skill_version", "scan_run", "injection_test", "review", "approval",
                "comment", "rating", "reuse_event", "gate_decision", "sensor_reading",
                "gold_set", "cost_ledger",
            ],
            "source_system": ["github", "sharepoint", "cli", "web"],
            "actor_kind": ["human", "service-account", "agent"],
        },
        "artifact_enum_security_exact": enum_security == [
            ("actor_kind", True, ""),
            ("artifact_type", True, ""),
            ("source_system", True, ""),
        ],
        "function_definitions_exact": definitions == expected_function_hashes,
        "governed_functions_pinned": all(
            signature in governed and governed[signature][0]
            and "search_path=pg_catalog, public" in governed[signature][1]
            for signature in (
                "artifact_get(uuid,text[])",
                "catalog_search(text,text[],text,text,text,integer)",
                "lineage(uuid,text[],integer)", "reuse_events_for_skill(uuid,text[])",
                "probe_skill_against_corpus(text)", "skill_scan_report(uuid,text[])",
            )
        ),
        "artifact_triggers_exact": hashlib.sha256(
            _canonical_bytes(trigger_bindings)
        ).hexdigest() == trusted.get("artifact_triggers_sha256"),
        "public_function_inventory_exact": hashlib.sha256(
            _canonical_bytes(public_function_inventory)
        ).hexdigest() == trusted.get("public_function_inventory_sha256"),
        "function_security_exact": hashlib.sha256(
            _canonical_bytes(function_security)
        ).hexdigest() == trusted.get("function_security_sha256"),
        "relation_security_exact": hashlib.sha256(
            _canonical_bytes(relation_security)
        ).hexdigest() == trusted.get("relation_security_sha256"),
        "tracker_contract_exact": (
            hashlib.sha256(_canonical_bytes(tracker_columns)).hexdigest()
            in trusted.get("tracker_columns_sha256", [])
            and hashlib.sha256(_canonical_bytes(tracker_constraints)).hexdigest()
            == trusted.get("tracker_constraints_sha256")
            and conn.execute(
                "SELECT count(*)=0 FROM pg_policy WHERE polrelid=ANY(ARRAY["
                "'public.artifacts'::regclass,'public.injection_corpus'::regclass,"
                "'public.judge_gold_set'::regclass,'public.schema_migrations'::regclass])"
            ).fetchone() == (True,)
            and conn.execute(
                "SELECT count(*)=0 FROM pg_rewrite r WHERE r.ev_class=ANY(ARRAY["
                "'public.artifacts'::regclass,'public.injection_corpus'::regclass,"
                "'public.judge_gold_set'::regclass,'public.schema_migrations'::regclass]) "
                "AND r.rulename<>'_RETURN'"
            ).fetchone() == (True,)
        ),
        "authority_index_inventories_exact": (
            hashlib.sha256(_canonical_bytes(index_inventory["artifacts"])).hexdigest()
            == trusted.get("artifacts_index_inventory_sha256")
            and hashlib.sha256(
                _canonical_bytes(index_inventory["schema_migrations"])
            ).hexdigest() == trusted.get("tracker_index_inventory_sha256")
        ),
        "schema_and_default_acl_exact": (
            hashlib.sha256(_canonical_bytes(public_schema_acl)).hexdigest()
            == trusted.get("public_schema_acl_sha256")
            and hashlib.sha256(_canonical_bytes(default_acl)).hexdigest()
            == trusted.get("default_acl_sha256")
        ),
        "authority_column_acls_absent": column_acls == [],
        "authority_relations_have_no_inheritance": conn.execute(
            "SELECT NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhparent=ANY(ARRAY["
            "'public.artifacts'::regclass,'public.injection_corpus'::regclass,"
            "'public.judge_gold_set'::regclass,'public.schema_migrations'::regclass]) "
            "OR i.inhrelid=ANY(ARRAY['public.artifacts'::regclass,"
            "'public.injection_corpus'::regclass,'public.judge_gold_set'::regclass,"
            "'public.schema_migrations'::regclass])) AND NOT EXISTS (SELECT 1 FROM pg_class c "
            "WHERE c.oid=ANY(ARRAY['public.artifacts'::regclass,"
            "'public.injection_corpus'::regclass,'public.judge_gold_set'::regclass,"
            "'public.schema_migrations'::regclass]) AND c.relhassubclass)"
        ).fetchone() == (True,),
        "public_schema_shadow_surface_absent": (
            conn.execute(
                "SELECT NOT has_schema_privilege('public','public','CREATE') "
                "AND NOT EXISTS (SELECT 1 FROM pg_operator o JOIN pg_namespace n "
                "ON n.oid=o.oprnamespace WHERE n.nspname='public') "
                "AND NOT EXISTS (SELECT 1 FROM pg_type u JOIN pg_namespace un "
                "ON un.oid=u.typnamespace JOIN pg_type b ON b.typname=u.typname "
                "JOIN pg_namespace bn ON bn.oid=b.typnamespace "
                "WHERE un.nspname='public' AND bn.nspname='pg_catalog') "
                "AND NOT EXISTS (SELECT 1 FROM pg_class u JOIN pg_namespace un "
                "ON un.oid=u.relnamespace JOIN pg_class b ON b.relname=u.relname "
                "JOIN pg_namespace bn ON bn.oid=b.relnamespace "
                "WHERE un.nspname='public' AND bn.nspname='pg_catalog')"
            ).fetchone() == (True,)
        ),
        "approval_index_exact": bool(index_row) and hashlib.sha256(
            index_row[0].encode("utf-8")
        ).hexdigest() == trusted.get("approval_index_sha256")
        and index_row[1:] == (True, True, True, True, True),
        "foundation_roles_hardened": foundation_roles == [
            ("semiskill_app", False, False, False, False, False, False, False),
            ("semiskill_pipeline", False, False, False, False, False, False, False),
            ("semiskill_submitter", False, False, False, False, False, False, False),
        ],
        "foundation_role_separation": role_separation,
        "artifacts_owned_by_migrator": table_owner_is_session,
        "migration_tracker_has_no_triggers": no_tracker_triggers,
        "held_out_tables_exact": isinstance(expected_held, dict) and held_schemas == expected_held,
        "held_out_seed_exact": len(corpus_rows) == 9 and hashlib.sha256(
            _canonical_bytes(corpus_rows)
        ).hexdigest() == trusted.get("injection_corpus_sha256"),
        "pending_0011_boundary_clean": (
            pending_roles_safe
            and capability_memberships_safe
            and not any(conn.execute(
                "SELECT to_regclass(%s)", (f"public.{name}",)
            ).fetchone()[0] for name in pending_objects)
            and not any(conn.execute(
                "SELECT to_regprocedure(%s)", (f"public.{signature}",)
            ).fetchone()[0] for signature in pending_functions)
        ),
    }


def _attest_checkpoint_0015(conn) -> dict[str, bool]:
    """Verify the frozen schema/0015@1 trust boundary before the reviewed forward step."""
    capability_roles = [
        "semiskill_acl_reader", "semiskill_app", "semiskill_approval_actuator",
        "semiskill_export_label_need_to_know", "semiskill_export_label_public",
        "semiskill_export_label_regulated", "semiskill_export_label_team",
        "semiskill_export_reader", "semiskill_pipeline", "semiskill_submitter",
    ]
    role_rows = [tuple(row) for row in conn.execute(
        "SELECT rolname,rolinherit,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
        "rolreplication,rolbypassrls FROM pg_roles WHERE rolname=ANY(%s) ORDER BY rolname",
        (capability_roles,),
    )]
    expected_role_rows = [
        (name, False, False, False, False, False, False, False)
        for name in capability_roles
    ]
    session_user = conn.execute("SELECT session_user").fetchone()[0]
    memberships = [tuple(row) for row in conn.execute(
        "SELECT granted.rolname,member.rolname,m.admin_option FROM pg_auth_members m "
        "JOIN pg_roles granted ON granted.oid=m.roleid "
        "JOIN pg_roles member ON member.oid=m.member "
        "WHERE granted.rolname=ANY(%s) OR member.rolname=ANY(%s) "
        "ORDER BY granted.rolname,member.rolname",
        (capability_roles, capability_roles),
    )]
    expected_memberships = [
        (name, session_user, False)
        for name in ("semiskill_app", "semiskill_pipeline", "semiskill_submitter")
    ]
    triggers = [list(row) for row in conn.execute(
        "SELECT c.relname,t.tgname,t.tgtype,t.tgenabled,pg_get_triggerdef(t.oid,true),"
        "n.nspname,p.proname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE NOT t.tgisinternal AND c.relname IN "
        "('artifacts','verified_publication_events') ORDER BY c.relname,t.tgname"
    )]
    index_row = conn.execute(
        "SELECT x.indexdef,i.indisunique,i.indisvalid,i.indisready,i.indislive,"
        "t.oid='public.verified_publication_events'::regclass FROM pg_indexes x "
        "JOIN pg_class c ON c.relname=x.indexname JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_index i ON i.indexrelid=c.oid JOIN pg_class t ON t.oid=i.indrelid "
        "WHERE x.schemaname='public' AND n.nspname='public' "
        "AND x.indexname='one_verified_correction_per_head'"
    ).fetchone()
    required_relations = conn.execute(
        "SELECT count(*)=3 FROM unnest(ARRAY['publication_trust_policy',"
        "'publication_skill_registry','verified_publication_events']) name "
        "WHERE to_regclass('public.'||name) IS NOT NULL"
    ).fetchone() == (True,)
    required_functions = all(conn.execute(
        "SELECT to_regprocedure(%s) IS NOT NULL", (f"public.{signature}",)
    ).fetchone() == (True,) for signature in (
        "activate_verified_publication(uuid)",
        "verified_active_publication_heads_v1()",
        "publication_registry_entry_v1(text)",
        "content_review_ready_v1(uuid,uuid)",
        "approval_v1_projection_valid(uuid)",
        "export_scoped_publication_bundle_v1(text)",
    ))
    direct_table_boundary = conn.execute(
        "SELECT "
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['semiskill_app','semiskill_pipeline',"
        "'semiskill_approval_actuator','semiskill_acl_reader','semiskill_export_reader']) r "
        "CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p WHERE has_table_privilege(r,'public.artifacts',p)),"
        "has_table_privilege('semiskill_submitter','public.artifacts','INSERT'),"
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p WHERE has_table_privilege("
        "'semiskill_submitter','public.artifacts',p)),"
        "NOT EXISTS (SELECT 1 FROM unnest(%s::text[]) r CROSS JOIN "
        "unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p "
        "WHERE has_table_privilege(r,'public.verified_publication_events',p))",
        (capability_roles,),
    ).fetchone() == (True, True, True, True)
    function_boundary = conn.execute(
        "SELECT "
        "has_function_privilege('semiskill_approval_actuator',"
        "'public.activate_verified_publication(uuid)','EXECUTE'),"
        "NOT has_function_privilege('semiskill_app',"
        "'public.activate_verified_publication(uuid)','EXECUTE'),"
        "has_function_privilege('semiskill_export_reader',"
        "'public.export_scoped_publication_bundle_v1(text)','EXECUTE'),"
        "NOT has_function_privilege('semiskill_app',"
        "'public.export_scoped_publication_bundle_v1(text)','EXECUTE')"
    ).fetchone() == (True, True, True, True)
    return {
        "required_relations_present": required_relations,
        "required_functions_present": required_functions,
        "critical_projection_index_exact": bool(index_row) and hashlib.sha256(
            index_row[0].encode("utf-8")
        ).hexdigest() == "a3aa3ebb5bb1d27e10cd055bb918f49820067330b63bbd6c26f229f567d9e4b3"
        and index_row[1:] == (True, True, True, True, True),
        "authority_triggers_exact": hashlib.sha256(
            _canonical_bytes(triggers)
        ).hexdigest() == "c02a3ec826208f6f45e9e9f66b07234573bcefdacfdba5b38f067174c0ff960c",
        "capability_roles_hardened": role_rows == expected_role_rows,
        "capability_memberships_exact": memberships == expected_memberships,
        "security_definer_paths_hardened": conn.execute(
            "SELECT count(*)>0 AND bool_and(coalesce("
            "'search_path=pg_catalog, public, pg_temp'=ANY(proconfig),false)) "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public' AND p.prosecdef"
        ).fetchone() == (True,),
        "direct_table_boundary_exact": direct_table_boundary,
        "function_boundary_exact": function_boundary,
        "projection_and_policy_start_empty": conn.execute(
            "SELECT (SELECT count(*) FROM public.verified_publication_events)=0 "
            "AND (SELECT count(*) FROM public.publication_trust_policy)=0"
        ).fetchone() == (True,),
        "public_schema_create_revoked": conn.execute(
            "SELECT NOT has_schema_privilege('public','public','CREATE')"
        ).fetchone() == (True,),
    }


def _canonical_rows(rows) -> list[list]:
    values = [list(row) for row in rows]
    return sorted(values, key=_canonical_bytes)


def _governed_schema_inventory_sha256(conn) -> str:
    """Hash the complete governed public-schema structure and authority metadata."""
    inventory = {
        "relations": _canonical_rows(conn.execute(
            "SELECT c.relname,c.relkind,c.relpersistence,"
            "pg_get_userbyid(c.relowner),"
            "coalesce(array_to_string(c.relacl,','),''),c.relrowsecurity,c.relforcerowsecurity,"
            "c.relispartition,c.relhasrules,c.relreplident,"
            "coalesce(array_to_string(c.reloptions,','),'') "
            "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' ORDER BY c.relname,c.relkind"
        )),
        "columns": _canonical_rows(conn.execute(
            "SELECT c.relname,row_number() OVER (PARTITION BY c.oid ORDER BY a.attnum),"
            "a.attname,format_type(a.atttypid,a.atttypmod),"
            "a.attnotnull,coalesce(pg_get_expr(d.adbin,d.adrelid),''),a.attidentity,"
            "a.attgenerated,coalesce(array_to_string(a.attacl,','),''),"
            "CASE WHEN a.attcollation=0 THEN '' ELSE a.attcollation::regcollation::text END,"
            "a.attstorage,a.attcompression FROM pg_attribute a "
            "JOIN pg_class c ON c.oid=a.attrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum "
            "WHERE n.nspname='public' AND a.attnum>0 AND NOT a.attisdropped "
            "AND c.relkind IN ('r','p','v','m','f') ORDER BY c.relname,a.attnum"
        )),
        "constraints": _canonical_rows(conn.execute(
            "SELECT c.relname,k.conname,k.contype,k.condeferrable,k.condeferred,k.convalidated,"
            "pg_get_constraintdef(k.oid,true) FROM pg_constraint k "
            "JOIN pg_class c ON c.oid=k.conrelid "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' ORDER BY c.relname,k.conname"
        )),
        "indexes": _canonical_rows(conn.execute(
            "SELECT t.relname,i.relname,pg_get_indexdef(x.indexrelid),x.indisunique,"
            "x.indisprimary,x.indisexclusion,x.indimmediate,x.indisvalid,x.indisready,"
            "x.indislive,x.indkey::text FROM pg_index x "
            "JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_class t ON t.oid=x.indrelid "
            "JOIN pg_namespace n ON n.oid=t.relnamespace WHERE n.nspname='public' "
            "ORDER BY t.relname,i.relname"
        )),
        "triggers": _canonical_rows(conn.execute(
            "SELECT c.relname,t.tgname,t.tgtype,t.tgenabled,pg_get_triggerdef(t.oid,true),"
            "p.oid::regprocedure::text FROM pg_trigger t "
            "JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
            "JOIN pg_proc p ON p.oid=t.tgfoid WHERE n.nspname='public' "
            "AND NOT t.tgisinternal ORDER BY c.relname,t.tgname"
        )),
        "rules": _canonical_rows(conn.execute(
            "SELECT c.relname,r.rulename,r.ev_type,r.ev_enabled,r.is_instead,"
            "pg_get_ruledef(r.oid,true) FROM pg_rewrite r "
            "JOIN pg_class c ON c.oid=r.ev_class "
            "JOIN pg_namespace n ON n.oid=c.relnamespace "
            "WHERE n.nspname='public' ORDER BY c.relname,r.rulename"
        )),
        "functions": _canonical_rows(conn.execute(
            "SELECT p.oid::regprocedure::text,pg_get_functiondef(p.oid),"
            "pg_get_userbyid(p.proowner),l.lanname,p.prokind,p.provolatile,"
            "p.proisstrict,p.prosecdef,p.proleakproof,p.proparallel,"
            "coalesce(array_to_string(p.proconfig,','),''),"
            "coalesce(array_to_string(p.proacl,','),'') FROM pg_proc p "
            "JOIN pg_namespace n ON n.oid=p.pronamespace "
            "JOIN pg_language l ON l.oid=p.prolang WHERE n.nspname='public' "
            "ORDER BY p.oid::regprocedure::text"
        )),
        "types": _canonical_rows(conn.execute(
            "SELECT t.typname,t.typtype,t.typcategory,pg_get_userbyid(t.typowner),"
            "coalesce(array_to_string(t.typacl,','),''),t.typnotnull,"
            "coalesce(t.typbasetype::regtype::text,''),coalesce(t.typdefault,'') "
            "FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='public' ORDER BY t.typname"
        )),
        "enums": _canonical_rows(conn.execute(
            "SELECT t.typname,e.enumsortorder,e.enumlabel FROM pg_enum e "
            "JOIN pg_type t ON t.oid=e.enumtypid JOIN pg_namespace n ON n.oid=t.typnamespace "
            "WHERE n.nspname='public' ORDER BY t.typname,e.enumsortorder"
        )),
        "schema_acl": _canonical_rows(conn.execute(
            "SELECT n.nspname,pg_get_userbyid(n.nspowner),"
            "coalesce(array_to_string(n.nspacl,','),'') FROM pg_namespace n "
            "WHERE n.nspname='public'"
        )),
        "default_acl": _canonical_rows(conn.execute(
            "SELECT d.defaclobjtype,coalesce(n.nspname,''),"
            "pg_get_userbyid(d.defaclrole),"
            "coalesce(array_to_string(d.defaclacl,','),'') FROM pg_default_acl d "
            "LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace "
            "ORDER BY pg_get_userbyid(d.defaclrole),d.defaclobjtype,coalesce(n.nspname,'')"
        )),
        "policies": _canonical_rows(conn.execute(
            "SELECT schemaname,tablename,policyname,permissive,roles,cmd,qual,with_check "
            "FROM pg_policies WHERE schemaname='public' ORDER BY tablename,policyname"
        )),
        "operators": _canonical_rows(conn.execute(
            "SELECT o.oid::regoperator::text,pg_get_userbyid(o.oprowner) "
            "FROM pg_operator o JOIN pg_namespace n ON n.oid=o.oprnamespace "
            "WHERE n.nspname='public' ORDER BY o.oid::regoperator::text"
        )),
    }
    return hashlib.sha256(_canonical_bytes(inventory)).hexdigest()


def _registry_rows_sha256(conn) -> str:
    rows = _canonical_rows(conn.execute(
        "SELECT slug,role,level,permissions_label,active,judge_required,registry_sha256 "
        "FROM public.publication_skill_registry ORDER BY slug"
    ))
    return hashlib.sha256(_canonical_bytes(rows)).hexdigest()


def _held_out_seed_sha256(conn) -> tuple[int, str]:
    rows = _canonical_rows(conn.execute(
        "SELECT probe_class,pattern,permissions_label FROM public.injection_corpus "
        "ORDER BY probe_class,pattern,permissions_label"
    ))
    return len(rows), hashlib.sha256(_canonical_bytes(rows)).hexdigest()


def _held_out_baseline_intact(conn) -> bool:
    rows = {
        tuple(row) for row in conn.execute(
            "SELECT probe_class,pattern,permissions_label FROM public.injection_corpus"
        )
    }
    return _BASELINE_INJECTION_ROWS <= rows


def _attest_checkpoint_0015_exact(conn) -> dict[str, bool]:
    results = _attest_checkpoint_0015(conn)
    corpus_count, corpus_sha256 = _held_out_seed_sha256(conn)
    return {
        **results,
        "schema_inventory_exact": (
            _governed_schema_inventory_sha256(conn)
            == _CHECKPOINT_0015_SCHEMA_SHA256
        ),
        "held_out_seed_exact": (
            corpus_count == 9 and corpus_sha256 == _CHECKPOINT_0015_CORPUS_SHA256
        ),
        "judge_gold_set_empty": conn.execute(
            "SELECT count(*)=0 FROM public.judge_gold_set"
        ).fetchone() == (True,),
        "registry_rows_exact": (
            _registry_rows_sha256(conn) == _CHECKPOINT_REGISTRY_SHA256
        ),
    }


def _post_migration_attestations(conn) -> dict[str, bool]:
    """Verify the exact trust boundary created by the reviewed pending suffix."""
    capability_roles = [
        "semiskill_acl_reader", "semiskill_app", "semiskill_approval_actuator",
        "semiskill_export_label_need_to_know", "semiskill_export_label_public",
        "semiskill_export_label_regulated", "semiskill_export_label_team",
        "semiskill_export_reader", "semiskill_pipeline", "semiskill_review_coordinator",
        "semiskill_submitter",
    ]
    role_rows = [tuple(row) for row in conn.execute(
        "SELECT rolname,rolinherit,rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,"
        "rolreplication,rolbypassrls FROM pg_roles WHERE rolname=ANY(%s) ORDER BY rolname",
        (capability_roles,),
    )]
    expected_role_rows = [
        (name, False, False, False, False, False, False, False)
        for name in capability_roles
    ]
    session_user = conn.execute("SELECT session_user").fetchone()[0]
    memberships = [tuple(row) for row in conn.execute(
        "SELECT granted.rolname,member.rolname,m.admin_option FROM pg_auth_members m "
        "JOIN pg_roles granted ON granted.oid=m.roleid "
        "JOIN pg_roles member ON member.oid=m.member "
        "WHERE granted.rolname=ANY(%s) OR member.rolname=ANY(%s) "
        "ORDER BY granted.rolname,member.rolname",
        (capability_roles, capability_roles),
    )]
    expected_memberships = [
        (name, session_user, False)
        for name in ("semiskill_app", "semiskill_pipeline", "semiskill_submitter")
    ]
    triggers = [list(row) for row in conn.execute(
        "SELECT c.relname,t.tgname,t.tgtype,t.tgenabled,pg_get_triggerdef(t.oid,true),"
        "n.nspname,p.proname FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
        "JOIN pg_proc p ON p.oid=t.tgfoid JOIN pg_namespace n ON n.oid=p.pronamespace "
        "WHERE NOT t.tgisinternal AND c.relname IN "
        "('artifacts','verified_publication_events','verified_review_contracts',"
        "'verified_review_contract_cells') ORDER BY c.relname,t.tgname"
    )]
    index_row = conn.execute(
        "SELECT x.indexdef,i.indisunique,i.indisvalid,i.indisready,i.indislive,"
        "t.oid='public.verified_publication_events'::regclass FROM pg_indexes x "
        "JOIN pg_class c ON c.relname=x.indexname JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_index i ON i.indexrelid=c.oid JOIN pg_class t ON t.oid=i.indrelid "
        "WHERE x.schemaname='public' AND n.nspname='public' "
        "AND x.indexname='one_verified_correction_per_head'"
    ).fetchone()
    review_root_index = conn.execute(
        "SELECT x.indexdef,i.indisunique,i.indisvalid,i.indisready,i.indislive,"
        "t.oid='public.artifacts'::regclass FROM pg_indexes x "
        "JOIN pg_class c ON c.relname=x.indexname JOIN pg_namespace n ON n.oid=c.relnamespace "
        "JOIN pg_index i ON i.indexrelid=c.oid JOIN pg_class t ON t.oid=i.indrelid "
        "WHERE x.schemaname='public' AND n.nspname='public' "
        "AND x.indexname='content_review_v2_one_root_per_slug'"
    ).fetchone()
    required_relations = conn.execute(
        "SELECT count(*)=5 FROM unnest(ARRAY['publication_trust_policy',"
        "'publication_skill_registry','verified_publication_events',"
        "'verified_review_contracts','verified_review_contract_cells']) name "
        "WHERE to_regclass('public.'||name) IS NOT NULL"
    ).fetchone() == (True,)
    required_functions = all(conn.execute(
        "SELECT to_regprocedure(%s) IS NOT NULL", (f"public.{signature}",)
    ).fetchone() == (True,) for signature in (
        "activate_verified_publication(uuid)",
        "verified_active_publication_heads_v1()",
        "publication_registry_entry_v1(text)",
        "content_review_ready_v1(uuid,uuid)",
        "content_review_publication_safe_v1(uuid)",
        "review_contract_authentication_valid_v1(uuid)",
        "review_contract_matches_v1(uuid,uuid,uuid)",
        "review_contract_verified_v1(uuid,text)",
        "append_verified_review_contract(uuid,source_system,text,actor_kind,timestamp with time zone,"
        "timestamp with time zone,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,jsonb)",
        "approval_v1_projection_valid(uuid)",
        "export_scoped_publication_bundle_v2(text)",
    ))
    direct_table_boundary = conn.execute(
        "SELECT "
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['semiskill_app','semiskill_pipeline',"
        "'semiskill_approval_actuator','semiskill_review_coordinator',"
        "'semiskill_acl_reader','semiskill_export_reader']) r "
        "CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p WHERE has_table_privilege(r,'public.artifacts',p)),"
        "has_table_privilege('semiskill_submitter','public.artifacts','INSERT'),"
        "NOT EXISTS (SELECT 1 FROM unnest(ARRAY['SELECT','UPDATE','DELETE','TRUNCATE',"
        "'REFERENCES','TRIGGER']) p WHERE has_table_privilege("
        "'semiskill_submitter','public.artifacts',p)),"
        "NOT EXISTS (SELECT 1 FROM unnest(%s::text[]) r CROSS JOIN "
        "unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p "
        "WHERE has_table_privilege(r,'public.verified_publication_events',p)),"
        "NOT EXISTS (SELECT 1 FROM unnest(%s::text[]) r CROSS JOIN "
        "unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER']) p "
        "CROSS JOIN unnest(ARRAY['public.verified_review_contracts',"
        "'public.verified_review_contract_cells']) relation "
        "WHERE has_table_privilege(r,relation,p))",
        (capability_roles, capability_roles),
    ).fetchone() == (True, True, True, True, True)
    function_boundary = conn.execute(
        "SELECT "
        "has_function_privilege('semiskill_approval_actuator',"
        "'public.activate_verified_publication(uuid)','EXECUTE'),"
        "NOT has_function_privilege('semiskill_app',"
        "'public.activate_verified_publication(uuid)','EXECUTE'),"
        "has_function_privilege('semiskill_export_reader',"
        "'public.export_scoped_publication_bundle_v2(text)','EXECUTE'),"
        "NOT has_function_privilege('semiskill_app',"
        "'public.export_scoped_publication_bundle_v2(text)','EXECUTE'),"
        "has_function_privilege('semiskill_review_coordinator',"
        "'public.append_verified_review_contract(uuid,source_system,text,actor_kind,timestamp with "
        "time zone,timestamp with time zone,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,"
        "jsonb)','EXECUTE'),"
        "NOT has_function_privilege('semiskill_app',"
        "'public.append_verified_review_contract(uuid,source_system,text,actor_kind,timestamp with "
        "time zone,timestamp with time zone,uuid[],uuid[],text,text,text,numeric,jsonb,numeric,uuid,"
        "jsonb)','EXECUTE'),"
        "NOT has_function_privilege('semiskill_review_coordinator',"
        "'public.append_verified_review_contract_v2_unbound(uuid,source_system,text,actor_kind,"
        "timestamp with time zone,timestamp with time zone,uuid[],uuid[],text,text,text,numeric,"
        "jsonb,numeric,uuid,jsonb)','EXECUTE')"
    ).fetchone() == (True, True, True, True, True, True, True)
    return {
        "required_relations_present": required_relations,
        "required_functions_present": required_functions,
        "critical_projection_index_exact": bool(index_row) and hashlib.sha256(
            index_row[0].encode("utf-8")
        ).hexdigest() == "a3aa3ebb5bb1d27e10cd055bb918f49820067330b63bbd6c26f229f567d9e4b3"
        and index_row[1:] == (True, True, True, True, True),
        "authority_triggers_exact": hashlib.sha256(
            _canonical_bytes(triggers)
        ).hexdigest() == "974c05ade72e1690f77510a6ae2de34c0e8b7df8df7fe68a91117992568ad5f0",
        "review_root_index_exact": bool(review_root_index) and hashlib.sha256(
            review_root_index[0].encode("utf-8")
        ).hexdigest() == "ab4b6a5560b1f5a2ed942e91420146b404d3f22b45231069ab3f32940ebf691b"
        and review_root_index[1:] == (True, True, True, True, True),
        "registry_rows_exact": (
            _registry_rows_sha256(conn) == _CHECKPOINT_REGISTRY_SHA256
        ),
        "capability_roles_hardened": role_rows == expected_role_rows,
        "capability_memberships_exact": memberships == expected_memberships,
        "security_definer_paths_hardened": conn.execute(
            "SELECT count(*)>0 AND bool_and(coalesce("
            "'search_path=pg_catalog, public, pg_temp'=ANY(proconfig),false)) "
            "FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace "
            "WHERE n.nspname='public' AND p.prosecdef"
        ).fetchone() == (True,),
        "direct_table_boundary_exact": direct_table_boundary,
        "function_boundary_exact": function_boundary,
        "held_out_baseline_intact": _held_out_baseline_intact(conn),
        "projection_and_policy_start_empty": conn.execute(
            "SELECT (SELECT count(*) FROM public.verified_publication_events)=0 "
            "AND (SELECT count(*) FROM public.publication_trust_policy)=0 "
            "AND (SELECT count(*) FROM public.verified_review_contracts)=0 "
            "AND (SELECT count(*) FROM public.verified_review_contract_cells)=0"
        ).fetchone() == (True,),
        "schema_inventory_exact": (
            _governed_schema_inventory_sha256(conn)
            == _CHECKPOINT_0023_SCHEMA_SHA256
        ),
        "public_schema_create_revoked": conn.execute(
            "SELECT NOT has_schema_privilege('public','public','CREATE')"
        ).fetchone() == (True,),
    }


def _plan_with_connection(
    conn,
    directory: Path,
    *,
    expected_database: str,
    environment: str,
    source_commit: str,
    remove_orphaned_test_fixtures: tuple[str, ...] = (),
) -> dict:
    if not isinstance(expected_database, str) or not expected_database.strip():
        raise MigrationAdoptionRefused("expected database identity is required")
    if not isinstance(source_commit, str) or not _COMMIT.fullmatch(source_commit):
        raise MigrationAdoptionRefused("a clean exact source commit is required")
    identity = _database_identity(conn)
    _validate_database_environment(identity, environment)
    if identity["database_name"] != expected_database:
        raise MigrationAdoptionRefused("actual database identity does not match expectation")
    if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None:
        raise MigrationAdoptionRefused("legacy migration tracker does not exist")
    columns = set(row[0] for row in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='schema_migrations'"
    ))
    if not {"filename", "applied_at"} <= columns:
        raise MigrationAdoptionRefused("legacy migration tracker has an unknown schema")
    if columns not in ({"filename", "applied_at"}, {"filename", "applied_at", "sha256"}):
        raise MigrationAdoptionRefused("legacy migration tracker has unexpected columns")
    select_checksum = "sha256" if "sha256" in columns else "NULL::text AS sha256"
    tracked = [
        {"filename": filename, "sha256": checksum, "applied_at": applied_at.isoformat()}
        for filename, checksum, applied_at in conn.execute(
            f"SELECT filename,{select_checksum},applied_at "
            "FROM public.schema_migrations ORDER BY filename"
        )
    ]
    repository = _repository_manifest(directory)
    _assert_repository_matches_commit(directory, source_commit, repository)
    trusted, trusted_digest = _trusted_legacy_manifest(repository)
    _assert_trusted_manifest_matches_commit(directory, source_commit, trusted_digest)
    if (not isinstance(remove_orphaned_test_fixtures, tuple)
            or any(not isinstance(name, str) or not _MIGRATION_NAME.fullmatch(name)
                   for name in remove_orphaned_test_fixtures)
            or len(set(remove_orphaned_test_fixtures)) != len(remove_orphaned_test_fixtures)):
        raise MigrationAdoptionRefused("orphaned test-fixture removal list is malformed")
    removable = sorted(remove_orphaned_test_fixtures)
    known_fixtures = trusted.get("known_orphaned_test_fixtures")
    if not isinstance(known_fixtures, dict) or any(name not in known_fixtures for name in removable):
        raise MigrationAdoptionRefused("unknown tracker history cannot be removed or acknowledged")
    tracked_names = [row["filename"] for row in tracked]
    repository_names = [row["filename"] for row in repository]
    trusted_names_ordered = [row["filename"] for row in trusted["migrations"]]
    official_names = [name for name in tracked_names if name in trusted_names_ordered]
    unmanaged = [name for name in tracked_names if name not in repository_names]
    unexpected_tracked = [
        name for name in tracked_names
        if name not in trusted_names_ordered and name not in removable
    ]
    if (official_names != trusted_names_ordered or unmanaged != removable
            or unexpected_tracked):
        raise MigrationAdoptionRefused(
            "tracked migrations are not the exact trusted legacy set"
        )
    tracked_by_name = {row["filename"]: row for row in tracked}
    orphaned_relations_to_drop: list[str] = []
    for filename in removable:
        fixture = known_fixtures[filename]
        relation = fixture.get("relation") if isinstance(fixture, dict) else None
        if (tracked_by_name[filename]["sha256"] is not None
                or relation != "public.mig_probe"):
            raise MigrationAdoptionRefused(
                f"untracked fixture is not a provably orphaned NULL record: {filename}"
            )
        if conn.execute("SELECT to_regclass(%s)", (relation,)).fetchone()[0] is not None:
            columns = [list(row) for row in conn.execute(
                "SELECT column_name,udt_name,is_nullable,column_default "
                "FROM information_schema.columns WHERE table_schema='public' "
                "AND table_name='mig_probe' ORDER BY ordinal_position"
            )]
            constraints = [list(row) for row in conn.execute(
                "SELECT conname,contype,pg_get_constraintdef(oid,true) FROM pg_constraint "
                "WHERE conrelid='public.mig_probe'::regclass ORDER BY conname"
            )]
            relation_contract = conn.execute(
                "SELECT c.relkind,c.relpersistence,NOT c.relispartition,"
                "c.reltablespace=0,pg_get_userbyid(c.relowner)=session_user,c.relacl IS NULL,"
                "NOT c.relrowsecurity,NOT c.relforcerowsecurity,"
                "NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid=c.oid OR i.inhparent=c.oid),"
                "NOT EXISTS (SELECT 1 FROM pg_index i WHERE i.indrelid=c.oid),"
                "NOT EXISTS (SELECT 1 FROM pg_rewrite r WHERE r.ev_class=c.oid "
                "AND r.rulename<>'_RETURN') FROM pg_class c "
                "WHERE c.oid='public.mig_probe'::regclass"
            ).fetchone()
            trigger_free = conn.execute(
                "SELECT count(*)=0 FROM pg_trigger WHERE NOT tgisinternal "
                "AND tgrelid='public.mig_probe'::regclass"
            ).fetchone() == (True,)
            empty = conn.execute("SELECT count(*)=0 FROM public.mig_probe").fetchone() == (True,)
            if (
                hashlib.sha256(_canonical_bytes(columns)).hexdigest()
                != fixture.get("columns_sha256")
                or hashlib.sha256(_canonical_bytes(constraints)).hexdigest()
                != fixture.get("constraints_sha256")
                or relation_contract != (
                    "r", "p", True, True, True, True, True, True, True, True, True,
                )
                or not trigger_free
                or not empty
            ):
                raise MigrationAdoptionRefused(
                    f"untracked fixture relation is not the exact empty test probe: {filename}"
                )
            orphaned_relations_to_drop.append(relation)
    repository_by_name = {row["filename"]: row["sha256"] for row in repository}
    trusted_names = set(trusted_names_ordered)
    null_rows: list[str] = []
    for row in tracked:
        checksum = row["sha256"]
        if row["filename"] in unmanaged:
            continue
        if checksum is None:
            if row["filename"] not in trusted_names:
                raise MigrationAdoptionRefused(
                    f"legacy NULL checksum is outside the trusted manifest: {row['filename']}"
                )
            null_rows.append(row["filename"])
        elif not isinstance(checksum, str) or not _SHA256.fullmatch(checksum):
            raise MigrationAdoptionRefused(
                f"tracked migration has a malformed checksum: {row['filename']}"
            )
        elif checksum != repository_by_name[row["filename"]]:
            raise MigrationAdoptionRefused(
                f"tracked migration checksum differs from repository: {row['filename']}"
            )
    if not null_rows:
        raise MigrationAdoptionRefused("no legacy NULL checksums require adoption")
    corpus_sha256 = trusted.get("injection_corpus_sha256")
    if not isinstance(corpus_sha256, str) or not _SHA256.fullmatch(corpus_sha256):
        raise MigrationAdoptionRefused("trusted corpus attestation is malformed")
    attestations = _schema_attestations(conn, trusted=trusted)
    failed = [name for name, passed in attestations.items() if not passed]
    if failed:
        raise MigrationAdoptionRefused(
            "post-0010 schema attestation failed: " + ", ".join(failed)
        )
    document = {
        "schema_version": "migration-checksum-adoption-plan/v1",
        "database": identity,
        "environment": environment,
        "source_commit": source_commit,
        "tracked_prefix": trusted_names_ordered,
        "tracked_manifest": tracked,
        "repository_manifest": repository,
        "trusted_manifest_sha256": trusted_digest,
        "orphaned_test_fixtures_to_remove": removable,
        "orphaned_relations_to_drop": orphaned_relations_to_drop,
        "legacy_null_filenames": null_rows,
        "legacy_null_count": len(null_rows),
        "pending_filenames": repository_names[len(trusted_names_ordered):],
        "schema_attestations": attestations,
        "historical_limit": trusted["historical_limit"],
    }
    document["plan_sha256"] = "sha256:" + hashlib.sha256(_canonical_bytes(document)).hexdigest()
    return document


def plan_legacy_migration_checksums(
    dsn: str,
    repo_root: str | Path,
    *,
    expected_database: str,
    environment: str,
    remove_orphaned_test_fixtures: tuple[str, ...] = (),
) -> dict:
    """Build a deterministic, read-only plan for human review; never alter the tracker."""
    directory, source_commit = _resolve_migration_source(repo_root)
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        conn.execute("SET LOCAL search_path = pg_catalog, public")
        return _plan_with_connection(
            conn,
            Path(directory),
            expected_database=expected_database,
            environment=environment,
            source_commit=source_commit,
            remove_orphaned_test_fixtures=remove_orphaned_test_fixtures,
        )


def adopt_legacy_migration_checksums(
    dsn: str,
    repo_root: str | Path,
    *,
    expected_database: str,
    expected_plan_sha256: str,
    remove_orphaned_test_fixtures: tuple[str, ...] = (),
    identity,
    environment: str,
    reason: str,
) -> dict:
    """Adopt a reviewed legacy prefix and append immutable evidence in one transaction."""
    from semiskill.governance.identity import AuthenticatedHuman, validate_identity_policy

    if not isinstance(identity, AuthenticatedHuman):
        raise MigrationAdoptionRefused("authenticated operator identity is required")
    try:
        validate_identity_policy(identity, environment=environment)
    except Exception as exc:
        raise MigrationAdoptionRefused("operator identity is not allowed for this environment") from exc
    if (not isinstance(reason, str) or len(reason.strip()) < 20 or len(reason) > 1000
            or any(ord(char) < 32 or ord(char) == 127 for char in reason)):
        raise MigrationAdoptionRefused("a substantive, printable adoption reason is required")
    if any(
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 512
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        for value in (identity.actor, identity.subject)
    ):
        raise MigrationAdoptionRefused("operator identity fields are malformed")
    if not isinstance(expected_plan_sha256, str) or not _PLAN_SHA256.fullmatch(
        expected_plan_sha256
    ):
        raise MigrationAdoptionRefused("a reviewed adoption plan digest is required")

    directory, source_commit = _resolve_migration_source(repo_root)
    with psycopg.connect(dsn) as conn:
        conn.execute("SET LOCAL search_path = pg_catalog, public")
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
        conn.execute("LOCK TABLE public.schema_migrations IN ACCESS EXCLUSIVE MODE")
        plan = _plan_with_connection(
            conn,
            Path(directory),
            expected_database=expected_database,
            environment=environment,
            source_commit=source_commit,
            remove_orphaned_test_fixtures=remove_orphaned_test_fixtures,
        )
        for relation in plan["orphaned_relations_to_drop"]:
            schema, name = relation.split(".", 1)
            conn.execute(
                sql.SQL("LOCK TABLE {}.{} IN ACCESS EXCLUSIVE MODE").format(
                    sql.Identifier(schema), sql.Identifier(name),
                )
            )
        if plan["orphaned_relations_to_drop"]:
            locked_plan = _plan_with_connection(
                conn,
                Path(directory),
                expected_database=expected_database,
                environment=environment,
                source_commit=source_commit,
                remove_orphaned_test_fixtures=remove_orphaned_test_fixtures,
            )
            if locked_plan["plan_sha256"] != plan["plan_sha256"]:
                raise MigrationAdoptionRefused(
                    "orphaned fixture relation changed before the adoption lock"
                )
            plan = locked_plan
        if plan["plan_sha256"] != expected_plan_sha256:
            raise MigrationAdoptionRefused("migration adoption plan changed after review")
        conn.execute("ALTER TABLE public.schema_migrations ADD COLUMN IF NOT EXISTS sha256 text")
        repository = {row["filename"]: row["sha256"] for row in plan["repository_manifest"]}
        for relation in plan["orphaned_relations_to_drop"]:
            schema, name = relation.split(".", 1)
            conn.execute(
                sql.SQL("DROP TABLE {}.{}").format(
                    sql.Identifier(schema), sql.Identifier(name),
                )
            )
        for filename in plan["orphaned_test_fixtures_to_remove"]:
            cursor = conn.execute(
                "DELETE FROM public.schema_migrations WHERE filename=%s AND sha256 IS NULL",
                (filename,),
            )
            if cursor.rowcount != 1:
                raise MigrationAdoptionRefused(
                    f"orphaned test fixture changed during adoption: {filename}"
                )
        for filename in plan["legacy_null_filenames"]:
            cursor = conn.execute(
                "UPDATE public.schema_migrations SET sha256=%s "
                "WHERE filename=%s AND sha256 IS NULL",
                (repository[filename], filename),
            )
            if cursor.rowcount != 1:
                raise MigrationAdoptionRefused(
                    f"migration tracker changed during adoption: {filename}"
                )
        manifest_by_name = {row["filename"]: row for row in plan["repository_manifest"]}
        for filename in plan["pending_filenames"]:
            raw = _safe_read_bytes(Path(directory) / filename, max_bytes=2_000_000)
            expected = manifest_by_name[filename]
            if (len(raw) != expected["bytes"]
                    or hashlib.sha256(raw).hexdigest() != expected["sha256"]):
                raise MigrationAdoptionRefused(
                    f"pending migration bytes changed after review: {filename}"
                )
            try:
                statement = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MigrationAdoptionRefused(
                    f"pending migration is not UTF-8: {filename}"
                ) from exc
            # With pg_catalog omitted it is searched implicitly first, while current_schema stays
            # public for unqualified CREATE statements. Explicit pg_temp last blocks temp shadows.
            conn.execute("SET LOCAL search_path = public, pg_temp")
            conn.execute(statement)
            conn.execute("SET LOCAL search_path = pg_catalog, public")
            conn.execute(
                "INSERT INTO public.schema_migrations(filename,sha256) VALUES(%s,%s)",
                (filename, expected["sha256"]),
            )
        final_tracker = [tuple(row) for row in conn.execute(
            "SELECT filename,sha256 FROM public.schema_migrations ORDER BY filename"
        )]
        expected_tracker = [
            (row["filename"], row["sha256"]) for row in plan["repository_manifest"]
        ]
        if final_tracker != expected_tracker:
            raise MigrationAdoptionRefused(
                "final migration tracker does not equal the reviewed repository manifest"
            )
        post_attestations = _post_migration_attestations(conn)
        failed_post = [name for name, passed in post_attestations.items() if not passed]
        if failed_post:
            raise MigrationAdoptionRefused(
                "post-migration trust attestation failed: " + ", ".join(failed_post)
            )
        subject_sha256 = "sha256:" + hashlib.sha256(identity.subject.encode("utf-8")).hexdigest()
        adoption_id = uuid.uuid4()
        evidence = {
            "schema_version": "migration-checksum-adoption/v1",
            "adoption_id": str(adoption_id),
            "decision": "adopt_and_apply",
            "environment": environment,
            "reason": reason.strip(),
            "source_commit": source_commit,
            "plan_sha256": plan["plan_sha256"],
            "database": plan["database"],
            "tracked_manifest": plan["tracked_manifest"],
            "repository_manifest": plan["repository_manifest"],
            "trusted_manifest_sha256": plan["trusted_manifest_sha256"],
            "schema_attestations": plan["schema_attestations"],
            "post_migration_attestations": post_attestations,
            "historical_limit": plan["historical_limit"],
            "operator_authentication": {
                "provider": identity.provider,
                "subject_sha256": subject_sha256,
            },
            "adopted_filenames": plan["legacy_null_filenames"],
            "removed_orphaned_test_fixtures": plan["orphaned_test_fixtures_to_remove"],
            "removed_orphaned_relations": plan["orphaned_relations_to_drop"],
            "applied_filenames": plan["pending_filenames"],
            "final_tracker": [
                {"filename": filename, "sha256": checksum}
                for filename, checksum in final_tracker
            ],
        }
        row = conn.execute(
            "INSERT INTO public.artifacts ("
            "artifact_id,artifact_type,source_system,actor,actor_kind,timestamp_start,"
            "timestamp_end,input_refs,output_refs,permissions_label,objective_tag,"
            "ground_truth_ref,eval_score,rollback_ref,cost_usd,corrects_ref,payload"
            ") VALUES ("
            "%s,'gate_decision','cli',%s,'human',clock_timestamp(),clock_timestamp(),"
            "'{}'::uuid[],'{}'::uuid[],'need-to-know','compliance',%s,NULL,%s,NULL,NULL,%s"
            ") RETURNING timestamp_start",
            (
                adoption_id,
                identity.actor,
                plan["plan_sha256"],
                Jsonb({
                    "supported": False,
                    "reason": "historical checksum adoption is an irreversible attestation",
                }),
                Jsonb(evidence),
            ),
        ).fetchone()
        conn.commit()
    return {
        "adoption_id": str(adoption_id),
        "adopted_at": row[0].isoformat(),
        "plan_sha256": plan["plan_sha256"],
        "database_identity_sha256": plan["database"]["identity_sha256"],
        "adopted_filenames": list(plan["legacy_null_filenames"]),
        "removed_orphaned_test_fixtures": list(plan["orphaned_test_fixtures_to_remove"]),
        "removed_orphaned_relations": list(plan["orphaned_relations_to_drop"]),
        "applied_filenames": list(plan["pending_filenames"]),
    }


def _migration_operator_claim(identity, *, environment: str, reason: str) -> dict[str, str]:
    """Return the non-secret human claim that is bound into a forward plan digest."""
    from semiskill.governance.identity import AuthenticatedHuman, validate_identity_policy

    if not isinstance(identity, AuthenticatedHuman):
        raise MigrationAdoptionRefused("authenticated operator identity is required")
    try:
        validate_identity_policy(identity, environment=environment)
    except Exception as exc:
        raise MigrationAdoptionRefused(
            "operator identity is not allowed for this environment"
        ) from exc
    if (
        not isinstance(reason, str)
        or len(reason.strip()) < 20
        or len(reason) > 1000
        or any(ord(char) < 32 or ord(char) == 127 for char in reason)
    ):
        raise MigrationAdoptionRefused(
            "a substantive, printable forward-migration reason is required"
        )
    if any(
        not isinstance(value, str)
        or not value.strip()
        or len(value) > 512
        or any(ord(char) < 32 or ord(char) == 127 for char in value)
        for value in (identity.actor, identity.subject)
    ):
        raise MigrationAdoptionRefused("operator identity fields are malformed")
    return {
        "actor": identity.actor,
        "provider": identity.provider,
        "subject_sha256": "sha256:" + hashlib.sha256(
            identity.subject.encode("utf-8")
        ).hexdigest(),
    }


def _tracked_migration_manifest(conn) -> list[dict[str, str]]:
    if conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0] is None:
        raise MigrationAdoptionRefused("migration tracker does not exist")
    columns = set(row[0] for row in conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='schema_migrations'"
    ))
    if columns != {"filename", "applied_at", "sha256"}:
        raise MigrationAdoptionRefused("migration tracker does not have the adopted schema")
    rows = [
        {"filename": filename, "sha256": checksum, "applied_at": applied_at.isoformat()}
        for filename, checksum, applied_at in conn.execute(
            "SELECT filename,sha256,applied_at FROM public.schema_migrations ORDER BY filename"
        )
    ]
    if not rows:
        raise MigrationAdoptionRefused("migration tracker is empty")
    for row in rows:
        if (
            not _MIGRATION_NAME.fullmatch(str(row["filename"]))
            or not isinstance(row["sha256"], str)
            or not _SHA256.fullmatch(row["sha256"])
            or not isinstance(row["applied_at"], str)
            or not row["applied_at"]
        ):
            raise MigrationAdoptionRefused(
                "migration tracker contains an untrusted checksummed row"
            )
    return rows


def _final_tracker(manifest: list[dict]) -> list[dict[str, str]]:
    return [
        {"filename": str(row["filename"]), "sha256": str(row["sha256"])}
        for row in manifest
    ]


def _validate_exact_tracker_prefix(
    tracked: list[dict[str, str]], repository: list[dict],
) -> tuple[dict[str, str], list[dict]]:
    tracked_final = _final_tracker(tracked)
    repository_final = _final_tracker(repository)
    if len(tracked_final) >= len(repository_final):
        raise MigrationAdoptionRefused(
            "forward migration requires one reviewed pending repository suffix"
        )
    if tracked_final != repository_final[:len(tracked_final)]:
        raise MigrationAdoptionRefused(
            "migration tracker is not an exact checksummed repository prefix"
        )
    endpoint = (tracked_final[-1]["filename"], repository_final[-1]["filename"])
    policy = _FORWARD_POLICIES.get(endpoint)
    if policy is None:
        raise MigrationAdoptionRefused(
            "migration tracker and repository do not match a reviewed forward policy"
        )
    pending = repository[len(tracked):]
    if not pending:
        raise MigrationAdoptionRefused("reviewed forward migration has no pending files")
    return dict(policy), pending


def _manifest_matches_final(value: object, expected: list[dict[str, str]]) -> bool:
    if not isinstance(value, list) or len(value) != len(expected):
        return False
    projected = []
    for row in value:
        if (
            not isinstance(row, dict)
            or set(row) != {"filename", "sha256", "bytes"}
            or type(row.get("bytes")) is not int
            or row["bytes"] < 0
        ):
            return False
        projected.append({"filename": row.get("filename"), "sha256": row.get("sha256")})
    return projected == expected


def _resolve_prior_migration_audit(
    conn,
    *,
    tracker_final: list[dict[str, str]],
    database: dict[str, str],
    environment: str,
    trusted_legacy: dict,
    trusted_legacy_sha256: str,
) -> dict[str, str]:
    rows = conn.execute(
        "SELECT artifact_id,source_system::text,actor,actor_kind::text,timestamp_start,"
        "timestamp_end,input_refs,output_refs,permissions_label,objective_tag,ground_truth_ref,"
        "eval_score,rollback_ref,cost_usd,corrects_ref,payload "
        "FROM public.artifacts WHERE artifact_type='gate_decision' "
        "AND payload->>'schema_version'='migration-checksum-adoption/v1' "
        "ORDER BY timestamp_start,artifact_id"
    ).fetchall()
    candidates = [
        row for row in rows
        if isinstance(row[15], dict) and row[15].get("final_tracker") == tracker_final
    ]
    if len(candidates) != 1:
        raise MigrationAdoptionRefused(
            "current migration checkpoint requires one exact prior authority artifact"
        )
    (
        artifact_id, source_system, actor, actor_kind, timestamp_start, timestamp_end,
        input_refs, output_refs, permissions_label, objective_tag, ground_truth_ref,
        eval_score, rollback_ref, cost_usd, corrects_ref, payload,
    ) = candidates[0]
    plan_sha256 = payload.get("plan_sha256")
    post = payload.get("post_migration_attestations")
    operator = payload.get("operator_authentication")
    repository_names = [row["filename"] for row in tracker_final]
    schema_attestations = payload.get("schema_attestations")
    repository_manifest = payload.get("repository_manifest")
    tracked_manifest = payload.get("tracked_manifest")
    adopted_filenames = payload.get("adopted_filenames")
    applied_filenames = payload.get("applied_filenames")
    removed_fixtures = payload.get("removed_orphaned_test_fixtures")
    removed_relations = payload.get("removed_orphaned_relations")
    trusted_rows = trusted_legacy.get("migrations")
    trusted_names = [row.get("filename") for row in trusted_rows] if isinstance(
        trusted_rows, list
    ) else []
    tracked_valid = isinstance(tracked_manifest, list) and bool(tracked_manifest)
    if tracked_valid:
        tracked_names = []
        for row in tracked_manifest:
            if (
                not isinstance(row, dict)
                or set(row) != {"filename", "sha256", "applied_at"}
                or not isinstance(row.get("filename"), str)
                or _MIGRATION_NAME.fullmatch(row["filename"]) is None
                or (
                    row.get("sha256") is not None
                    and (
                        not isinstance(row["sha256"], str)
                        or _SHA256.fullmatch(row["sha256"]) is None
                    )
                )
                or not isinstance(row.get("applied_at"), str)
                or not row["applied_at"].strip()
            ):
                tracked_valid = False
                break
            tracked_names.append(row["filename"])
        tracked_valid = (
            tracked_valid
            and tracked_names == sorted(tracked_names)
            and len(tracked_names) == len(set(tracked_names))
            and isinstance(removed_fixtures, list)
            and tracked_names == sorted(trusted_names + removed_fixtures)
            and adopted_filenames == [
                row["filename"] for row in tracked_manifest
                if row["filename"] in trusted_names and row["sha256"] is None
            ]
        )
    adoption_plan_valid = False
    if (
        tracked_valid
        and isinstance(repository_manifest, list)
        and isinstance(adopted_filenames, list)
        and isinstance(applied_filenames, list)
        and isinstance(schema_attestations, dict)
        and isinstance(removed_relations, list)
    ):
        reconstructed_plan = {
            "schema_version": "migration-checksum-adoption-plan/v1",
            "database": payload.get("database"),
            "environment": payload.get("environment"),
            "source_commit": payload.get("source_commit"),
            "tracked_prefix": trusted_names,
            "tracked_manifest": tracked_manifest,
            "repository_manifest": repository_manifest,
            "trusted_manifest_sha256": payload.get("trusted_manifest_sha256"),
            "orphaned_test_fixtures_to_remove": removed_fixtures,
            "orphaned_relations_to_drop": removed_relations,
            "legacy_null_filenames": adopted_filenames,
            "legacy_null_count": len(adopted_filenames),
            "pending_filenames": applied_filenames,
            "schema_attestations": schema_attestations,
            "historical_limit": payload.get("historical_limit"),
        }
        adoption_plan_valid = plan_sha256 == "sha256:" + hashlib.sha256(
            _canonical_bytes(reconstructed_plan)
        ).hexdigest()
    valid = (
        source_system == "cli"
        and isinstance(actor, str) and bool(actor.strip())
        and actor_kind == "human"
        and timestamp_end is not None and timestamp_end >= timestamp_start
        and list(input_refs or []) == []
        and list(output_refs or []) == []
        and permissions_label == "need-to-know"
        and objective_tag == "compliance"
        and isinstance(plan_sha256, str) and _PLAN_SHA256.fullmatch(plan_sha256) is not None
        and ground_truth_ref == plan_sha256
        and eval_score is None
        and cost_usd is None
        and corrects_ref is None
        and isinstance(rollback_ref, dict)
        and set(rollback_ref) == {"supported", "reason"}
        and rollback_ref.get("supported") is False
        and isinstance(rollback_ref.get("reason"), str)
        and bool(rollback_ref["reason"].strip())
        and payload.get("database") == database
        and payload.get("environment") == environment
        and isinstance(payload.get("source_commit"), str)
        and _COMMIT.fullmatch(payload["source_commit"]) is not None
        and isinstance(payload.get("reason"), str)
        and bool(payload["reason"].strip())
        and isinstance(post, dict)
        and set(post) == _STORED_ADOPTION_0015_ATTESTATION_KEYS
        and all(value is True for value in post.values())
        and isinstance(schema_attestations, dict)
        and set(schema_attestations) == _ADOPTION_SCHEMA_ATTESTATION_KEYS
        and all(value is True for value in schema_attestations.values())
        and isinstance(operator, dict)
        and set(operator) == {"provider", "subject_sha256"}
        and operator.get("provider") in {"local_os", "entra_oidc"}
        and isinstance(operator.get("subject_sha256"), str)
        and _PLAN_SHA256.fullmatch(operator["subject_sha256"]) is not None
        and _manifest_matches_final(repository_manifest, tracker_final)
        and set(payload) == {
            "adopted_filenames", "adoption_id", "applied_filenames", "database",
            "decision", "environment", "final_tracker", "historical_limit",
            "operator_authentication", "plan_sha256", "post_migration_attestations",
            "reason", "removed_orphaned_relations", "removed_orphaned_test_fixtures",
            "repository_manifest", "schema_attestations", "schema_version",
            "source_commit", "tracked_manifest", "trusted_manifest_sha256",
        }
        and payload.get("schema_version") == "migration-checksum-adoption/v1"
        and payload.get("decision") == "adopt_and_apply"
        and payload.get("adoption_id") == str(artifact_id)
        and payload.get("historical_limit") == trusted_legacy.get("historical_limit")
        and payload.get("trusted_manifest_sha256") == trusted_legacy_sha256
        and tracked_valid
        and isinstance(adopted_filenames, list)
        and isinstance(applied_filenames, list)
        and adopted_filenames + applied_filenames == repository_names
        and (
            (
                payload.get("removed_orphaned_relations") == []
                and payload.get("removed_orphaned_test_fixtures") == []
            )
            or (
                payload.get("removed_orphaned_relations") == ["public.mig_probe"]
                and payload.get("removed_orphaned_test_fixtures") == ["9001_probe.sql"]
            )
        )
        and adoption_plan_valid
    )
    if not valid:
        raise MigrationAdoptionRefused("prior migration authority artifact is malformed or detached")
    return {
        "artifact_id": str(artifact_id),
        "schema_version": "migration-checksum-adoption/v1",
        "plan_sha256": plan_sha256,
        "payload_sha256": "sha256:" + hashlib.sha256(_canonical_bytes(payload)).hexdigest(),
    }


def _build_forward_plan_with_connection(
    conn,
    directory: Path,
    *,
    expected_database: str,
    environment: str,
    source_commit: str,
    operator_claim: dict[str, str],
    reason: str,
) -> dict:
    if not isinstance(expected_database, str) or not expected_database.strip():
        raise MigrationAdoptionRefused("expected database identity is required")
    if not isinstance(source_commit, str) or _COMMIT.fullmatch(source_commit) is None:
        raise MigrationAdoptionRefused("a clean exact source commit is required")
    database = _database_identity(conn)
    _validate_database_environment(database, environment)
    if database["database_name"] != expected_database:
        raise MigrationAdoptionRefused("actual database identity does not match expectation")
    tracked = _tracked_migration_manifest(conn)
    repository = _repository_manifest(directory)
    _assert_repository_matches_commit(directory, source_commit, repository)
    trusted_legacy, trusted_legacy_sha256 = _trusted_legacy_manifest(repository)
    _assert_trusted_manifest_matches_commit(
        directory, source_commit, trusted_legacy_sha256,
    )
    policy, pending = _validate_exact_tracker_prefix(tracked, repository)
    tracker_final = _final_tracker(tracked)
    prior = _resolve_prior_migration_audit(
        conn,
        tracker_final=tracker_final,
        database=database,
        environment=environment,
        trusted_legacy=trusted_legacy,
        trusted_legacy_sha256=trusted_legacy_sha256,
    )
    pre_results = _attest_checkpoint_0015_exact(conn)
    if set(pre_results) != _CHECKPOINT_0015_ATTESTATION_KEYS or not all(
        value is True for value in pre_results.values()
    ):
        failed = sorted(name for name, passed in pre_results.items() if passed is not True)
        raise MigrationAdoptionRefused(
            "schema/0015@1 pre-migration attestation failed: " + ", ".join(failed)
        )
    document = {
        "schema_version": _FORWARD_PLAN_SCHEMA,
        "action": "apply_reviewed_forward_migration",
        "policy_id": policy["policy_id"],
        "source_commit": source_commit,
        "environment": environment,
        "database": database,
        "migrator": {
            "session_user_sha256": database["session_user_sha256"],
            "explicit_role_bound": True,
        },
        "operator_authentication": operator_claim,
        "reason": reason.strip(),
        "prior_audit": prior,
        "tracker_manifest": tracked,
        "repository_manifest": repository,
        "pending_manifest": pending,
        "from_filename": tracked[-1]["filename"],
        "to_filename": repository[-1]["filename"],
        "pre_attestation": {
            "policy_id": policy["pre_attestation_policy_id"],
            "results": pre_results,
        },
        "post_attestation_contract": {
            "policy_id": policy["post_attestation_policy_id"],
            "required_keys": sorted(_POST_MIGRATION_ATTESTATION_KEYS),
            "expected_all_true": True,
        },
    }
    document["plan_sha256"] = "sha256:" + hashlib.sha256(
        _canonical_bytes(document)
    ).hexdigest()
    return document


def plan_forward_migrations(
    dsn: str,
    repo_root: str | Path,
    *,
    expected_database: str,
    environment: str,
    identity,
    reason: str,
) -> dict:
    """Build a reason- and operator-bound read-only plan for one reviewed checkpoint."""
    operator_claim = _migration_operator_claim(
        identity, environment=environment, reason=reason,
    )
    directory, source_commit = _resolve_migration_source(repo_root)
    with psycopg.connect(dsn) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='15s'")
        conn.execute("SET LOCAL lock_timeout='3s'")
        conn.execute("SET LOCAL search_path = pg_catalog, public")
        return _build_forward_plan_with_connection(
            conn,
            Path(directory),
            expected_database=expected_database,
            environment=environment,
            source_commit=source_commit,
            operator_claim=operator_claim,
            reason=reason,
        )


def _validate_forward_plan_document(plan: object, expected_plan_sha256: str) -> dict:
    expected_keys = {
        "schema_version", "action", "policy_id", "source_commit", "environment",
        "database", "migrator", "operator_authentication", "reason", "prior_audit",
        "tracker_manifest", "repository_manifest", "pending_manifest", "from_filename",
        "to_filename", "pre_attestation", "post_attestation_contract", "plan_sha256",
    }
    if not isinstance(plan, dict) or set(plan) != expected_keys:
        raise MigrationAdoptionRefused("forward migration plan has an unknown schema")
    database = plan.get("database")
    migrator = plan.get("migrator")
    operator = plan.get("operator_authentication")
    prior = plan.get("prior_audit")
    tracker = plan.get("tracker_manifest")
    repository = plan.get("repository_manifest")
    pending = plan.get("pending_manifest")
    pre = plan.get("pre_attestation")
    post = plan.get("post_attestation_contract")
    from_filename = plan.get("from_filename")
    to_filename = plan.get("to_filename")
    endpoint = (from_filename, to_filename)
    policy = _FORWARD_POLICIES.get(endpoint) if all(
        isinstance(value, str) for value in endpoint
    ) else None

    def _printable(value: object, *, minimum: int = 1, maximum: int = 1000) -> bool:
        return (
            isinstance(value, str)
            and minimum <= len(value) <= maximum
            and value == value.strip()
            and all(ord(char) >= 32 and ord(char) != 127 for char in value)
        )

    def _canonical_uuid(value: object) -> bool:
        if not isinstance(value, str):
            return False
        try:
            return str(uuid.UUID(value)) == value
        except ValueError:
            return False

    def _repository_manifest_valid(value: object) -> bool:
        if not isinstance(value, list) or not value:
            return False
        names = []
        for row in value:
            if (
                not isinstance(row, dict)
                or set(row) != {"filename", "sha256", "bytes"}
                or not isinstance(row.get("filename"), str)
                or _MIGRATION_NAME.fullmatch(row["filename"]) is None
                or not isinstance(row.get("sha256"), str)
                or _SHA256.fullmatch(row["sha256"]) is None
                or type(row.get("bytes")) is not int
                or not 0 < row["bytes"] <= 2_000_000
            ):
                return False
            names.append(row["filename"])
        return names == sorted(names) and len(names) == len(set(names))

    def _tracker_manifest_valid(value: object) -> bool:
        if not isinstance(value, list) or not value:
            return False
        names = []
        for row in value:
            if (
                not isinstance(row, dict)
                or set(row) != {"filename", "sha256", "applied_at"}
                or not isinstance(row.get("filename"), str)
                or _MIGRATION_NAME.fullmatch(row["filename"]) is None
                or not isinstance(row.get("sha256"), str)
                or _SHA256.fullmatch(row["sha256"]) is None
                or not _printable(row.get("applied_at"), maximum=128)
            ):
                return False
            names.append(row["filename"])
        return names == sorted(names) and len(names) == len(set(names))

    nested_valid = (
        policy is not None
        and plan.get("policy_id") == policy["policy_id"]
        and isinstance(plan.get("source_commit"), str)
        and _COMMIT.fullmatch(plan["source_commit"]) is not None
        and plan.get("environment") in {"development", "test", "production"}
        and isinstance(database, dict)
        and set(database) == {
            "engine", "database_name", "server_version_num", "session_user_sha256",
            "identity_sha256",
        }
        and database.get("engine") == "postgresql"
        and _printable(database.get("database_name"), maximum=128)
        and isinstance(database.get("server_version_num"), str)
        and database["server_version_num"].isdigit()
        and isinstance(database.get("session_user_sha256"), str)
        and _PLAN_SHA256.fullmatch(database["session_user_sha256"]) is not None
        and isinstance(database.get("identity_sha256"), str)
        and _PLAN_SHA256.fullmatch(database["identity_sha256"]) is not None
        and isinstance(migrator, dict)
        and set(migrator) == {"session_user_sha256", "explicit_role_bound"}
        and migrator.get("session_user_sha256") == database.get("session_user_sha256")
        and migrator.get("explicit_role_bound") is True
        and isinstance(operator, dict)
        and set(operator) == {"actor", "provider", "subject_sha256"}
        and _printable(operator.get("actor"), maximum=512)
        and operator.get("provider") in {"local_os", "entra_oidc"}
        and isinstance(operator.get("subject_sha256"), str)
        and _PLAN_SHA256.fullmatch(operator["subject_sha256"]) is not None
        and _printable(plan.get("reason"), minimum=20, maximum=1000)
        and isinstance(prior, dict)
        and set(prior) == {"artifact_id", "schema_version", "plan_sha256", "payload_sha256"}
        and _canonical_uuid(prior.get("artifact_id"))
        and prior.get("schema_version") == "migration-checksum-adoption/v1"
        and isinstance(prior.get("plan_sha256"), str)
        and _PLAN_SHA256.fullmatch(prior["plan_sha256"]) is not None
        and isinstance(prior.get("payload_sha256"), str)
        and _PLAN_SHA256.fullmatch(prior["payload_sha256"]) is not None
        and _repository_manifest_valid(repository)
        and _repository_manifest_valid(pending)
        and _tracker_manifest_valid(tracker)
        and len(tracker) < len(repository)
        and _final_tracker(tracker) == _final_tracker(repository)[:len(tracker)]
        and pending == repository[len(tracker):]
        and tracker[-1]["filename"] == endpoint[0]
        and repository[-1]["filename"] == endpoint[1]
        and isinstance(pre, dict)
        and set(pre) == {"policy_id", "results"}
        and pre.get("policy_id") == policy["pre_attestation_policy_id"]
        and isinstance(pre.get("results"), dict)
        and set(pre["results"]) == _CHECKPOINT_0015_ATTESTATION_KEYS
        and all(value is True for value in pre["results"].values())
        and isinstance(post, dict)
        and set(post) == {"policy_id", "required_keys", "expected_all_true"}
        and post.get("policy_id") == policy["post_attestation_policy_id"]
        and post.get("required_keys") == sorted(_POST_MIGRATION_ATTESTATION_KEYS)
        and post.get("expected_all_true") is True
    )
    if (
        plan.get("schema_version") != _FORWARD_PLAN_SCHEMA
        or plan.get("action") != "apply_reviewed_forward_migration"
        or not nested_valid
        or not isinstance(expected_plan_sha256, str)
        or _PLAN_SHA256.fullmatch(expected_plan_sha256) is None
        or plan.get("plan_sha256") != expected_plan_sha256
    ):
        raise MigrationAdoptionRefused("reviewed forward migration plan identity is invalid")
    unsigned = {key: value for key, value in plan.items() if key != "plan_sha256"}
    digest = "sha256:" + hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()
    if digest != expected_plan_sha256:
        raise MigrationAdoptionRefused("forward migration plan digest does not match its bytes")
    try:
        return json.loads(json.dumps(
            plan, ensure_ascii=False, sort_keys=True, allow_nan=False,
        ))
    except (TypeError, ValueError) as exc:
        raise MigrationAdoptionRefused("forward migration plan is not canonical JSON") from exc


def load_forward_migration_plan(path: str | Path) -> dict:
    """Read one bounded regular plan file; semantic validation occurs at execution."""
    def _object_without_duplicates(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate object key")
            value[key] = item
        return value

    def _reject_non_finite(value):
        raise ValueError(f"non-finite number {value}")

    try:
        raw = _safe_read_bytes(Path(path), max_bytes=2_000_000).decode("utf-8")
        document = json.loads(
            raw,
            object_pairs_hook=_object_without_duplicates,
            parse_constant=_reject_non_finite,
        )
    except (OSError, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise MigrationAdoptionRefused("forward migration plan file is unavailable") from exc
    if not isinstance(document, dict):
        raise MigrationAdoptionRefused("forward migration plan file must contain an object")
    plan_sha256 = document.get("plan_sha256")
    if not isinstance(plan_sha256, str):
        raise MigrationAdoptionRefused("forward migration plan file has no digest")
    return _validate_forward_plan_document(document, plan_sha256)


def write_forward_migration_plan(path: str | Path, plan: dict) -> Path:
    """Publish reviewed plan bytes atomically without replacing a different existing file."""
    if not isinstance(plan, dict) or not isinstance(plan.get("plan_sha256"), str):
        raise MigrationAdoptionRefused("forward migration plan is malformed")
    _validate_forward_plan_document(plan, plan["plan_sha256"])
    raw = json.dumps(
        plan, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False,
    ).encode("utf-8") + b"\n"
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if _safe_read_bytes(target, max_bytes=2_000_000) == raw:
            return target
        raise MigrationAdoptionRefused("forward migration plan output already exists with other bytes")
    handle = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, target)
        except FileExistsError:
            if _safe_read_bytes(target, max_bytes=2_000_000) != raw:
                raise MigrationAdoptionRefused(
                    "forward migration plan output raced with different bytes"
                )
        return target
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _forward_audit_id(database_identity_sha256: str, plan_sha256: str) -> uuid.UUID:
    return uuid.uuid5(_FORWARD_AUDIT_NAMESPACE, f"{database_identity_sha256}|{plan_sha256}")


def _post_attestations_are_stable(results: object) -> bool:
    return (
        isinstance(results, dict)
        and set(results) == _POST_MIGRATION_ATTESTATION_KEYS
        and all(
            results.get(name) is True
            for name in _POST_MIGRATION_STABLE_ATTESTATION_KEYS
        )
        and type(results.get("projection_and_policy_start_empty")) is bool
    )


def _assert_forward_audit_slot_empty(conn, plan: dict) -> None:
    """Reserve one deterministic lineage slot before any reviewed DDL is applied."""
    migration_id = _forward_audit_id(
        plan["database"]["identity_sha256"], plan["plan_sha256"],
    )
    collisions = conn.execute(
        "SELECT artifact_id,artifact_type::text,payload->>'schema_version',"
        "payload->>'plan_sha256' FROM public.artifacts WHERE artifact_id=%s OR "
        "(artifact_type='gate_decision' AND payload->>'schema_version'=%s "
        "AND payload->>'plan_sha256'=%s) ORDER BY artifact_id",
        (migration_id, _FORWARD_EVIDENCE_SCHEMA, plan["plan_sha256"]),
    ).fetchall()
    if collisions:
        raise MigrationAdoptionRefused(
            "forward migration audit slot is already occupied or ambiguous"
        )


def _forward_evidence_payload(
    plan: dict,
    *,
    migration_id: uuid.UUID,
    post_attestations: dict[str, bool],
    final_tracker: list[dict[str, str]],
) -> dict:
    return {
        "schema_version": _FORWARD_EVIDENCE_SCHEMA,
        "migration_id": str(migration_id),
        "decision": "apply_reviewed_forward_migration",
        "policy_id": plan["policy_id"],
        "environment": plan["environment"],
        "reason": plan["reason"],
        "source_commit": plan["source_commit"],
        "plan_sha256": plan["plan_sha256"],
        "database": plan["database"],
        "operator_authentication": plan["operator_authentication"],
        "prior_audit": plan["prior_audit"],
        "tracker_before": plan["tracker_manifest"],
        "repository_manifest": plan["repository_manifest"],
        "pending_manifest": plan["pending_manifest"],
        "pre_migration_attestation": plan["pre_attestation"],
        "post_migration_attestations": post_attestations,
        "applied_filenames": [row["filename"] for row in plan["pending_manifest"]],
        "final_tracker": final_tracker,
    }


def _resolve_forward_retry(
    conn,
    *,
    plan: dict,
    final_tracker: list[dict[str, str]],
) -> dict | None:
    migration_id = _forward_audit_id(
        plan["database"]["identity_sha256"], plan["plan_sha256"],
    )
    matching_ids = [row[0] for row in conn.execute(
        "SELECT artifact_id FROM public.artifacts WHERE artifact_type='gate_decision' "
        "AND payload->>'schema_version'=%s AND payload->>'plan_sha256'=%s "
        "ORDER BY artifact_id",
        (_FORWARD_EVIDENCE_SCHEMA, plan["plan_sha256"]),
    )]
    if not matching_ids:
        return None
    if matching_ids != [migration_id]:
        raise MigrationAdoptionRefused("forward migration audit lineage is ambiguous")
    row = conn.execute(
        "SELECT source_system::text,actor,actor_kind::text,timestamp_start,timestamp_end,"
        "input_refs,output_refs,permissions_label,objective_tag,ground_truth_ref,eval_score,"
        "rollback_ref,cost_usd,corrects_ref,payload FROM public.artifacts WHERE artifact_id=%s",
        (migration_id,),
    ).fetchone()
    stored_post = row[14].get("post_migration_attestations") if row else None
    expected_payload = _forward_evidence_payload(
        plan,
        migration_id=migration_id,
        post_attestations=stored_post,
        final_tracker=final_tracker,
    )
    expected_prior = uuid.UUID(plan["prior_audit"]["artifact_id"])
    if (
        row is None
        or row[0] != "cli"
        or row[1] != plan["operator_authentication"]["actor"]
        or row[2] != "human"
        or row[4] is None
        or row[4] < row[3]
        or list(row[5] or []) != [expected_prior]
        or list(row[6] or []) != []
        or row[7] != "need-to-know"
        or row[8] != "compliance"
        or row[9] != plan["plan_sha256"]
        or row[10] is not None
        or row[11] != {
            "supported": False,
            "reason": "forward schema migrations are irreversible attestations",
        }
        or row[12] is not None
        or row[13] is not None
        or not isinstance(stored_post, dict)
        or set(stored_post) != _POST_MIGRATION_ATTESTATION_KEYS
        or not all(value is True for value in stored_post.values())
        or row[14] != expected_payload
    ):
        raise MigrationAdoptionRefused("existing forward migration audit conflicts with the plan")
    return {
        "migration_id": str(migration_id),
        "migrated_at": row[3].isoformat(),
        "plan_sha256": plan["plan_sha256"],
        "database_identity_sha256": plan["database"]["identity_sha256"],
        "applied_filenames": [row["filename"] for row in plan["pending_manifest"]],
        "semantic_retry": True,
    }


def execute_forward_migrations(
    dsn: str,
    repo_root: str | Path,
    *,
    plan: dict,
    expected_plan_sha256: str,
    expected_database: str,
    environment: str,
    identity,
    reason: str,
) -> dict:
    """Apply one reviewed forward policy and its chained audit in a single transaction."""
    reviewed_plan = _validate_forward_plan_document(plan, expected_plan_sha256)
    operator_claim = _migration_operator_claim(
        identity, environment=environment, reason=reason,
    )
    if (
        reviewed_plan["operator_authentication"] != operator_claim
        or reviewed_plan["reason"] != reason.strip()
        or reviewed_plan["environment"] != environment
        or reviewed_plan["database"].get("database_name") != expected_database
    ):
        raise MigrationAdoptionRefused(
            "operator, reason, environment, or database differs from the reviewed plan"
        )
    directory, source_commit = _resolve_migration_source(repo_root)
    if source_commit != reviewed_plan["source_commit"]:
        raise MigrationAdoptionRefused("source commit differs from the reviewed plan")

    with psycopg.connect(dsn) as conn:
        conn.execute("SET LOCAL statement_timeout='120s'")
        conn.execute("SET LOCAL lock_timeout='10s'")
        conn.execute("SET LOCAL search_path = pg_catalog, public")
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
        conn.execute("LOCK TABLE public.schema_migrations IN ACCESS EXCLUSIVE MODE")
        conn.execute("LOCK TABLE public.artifacts IN SHARE MODE")
        conn.execute(
            "LOCK TABLE public.publication_skill_registry,public.injection_corpus "
            "IN SHARE MODE"
        )

        database = _database_identity(conn)
        _validate_database_environment(database, environment)
        if database != reviewed_plan["database"] or database["database_name"] != expected_database:
            raise MigrationAdoptionRefused("database identity differs from the reviewed plan")
        repository = _repository_manifest(Path(directory))
        _assert_repository_matches_commit(Path(directory), source_commit, repository)
        trusted_legacy, trusted_legacy_sha256 = _trusted_legacy_manifest(repository)
        _assert_trusted_manifest_matches_commit(
            Path(directory), source_commit, trusted_legacy_sha256,
        )
        tracked = _tracked_migration_manifest(conn)
        repository_final = _final_tracker(repository)
        tracked_final = _final_tracker(tracked)

        if tracked_final == repository_final:
            retry_prior = _resolve_prior_migration_audit(
                conn,
                tracker_final=_final_tracker(reviewed_plan["tracker_manifest"]),
                database=database,
                environment=environment,
                trusted_legacy=trusted_legacy,
                trusted_legacy_sha256=trusted_legacy_sha256,
            )
            if retry_prior != reviewed_plan["prior_audit"]:
                raise MigrationAdoptionRefused(
                    "completed forward migration is detached from its prior authority artifact"
                )
            post_attestations = _post_migration_attestations(conn)
            if not _post_attestations_are_stable(post_attestations):
                raise MigrationAdoptionRefused(
                    "completed forward migration no longer passes its post-attestation"
                )
            retry = _resolve_forward_retry(
                conn,
                plan=reviewed_plan,
                final_tracker=tracked_final,
            )
            if retry is None:
                raise MigrationAdoptionRefused(
                    "final tracker exists without the exact reviewed forward audit"
                )
            conn.commit()
            return retry

        locked_plan = _build_forward_plan_with_connection(
            conn,
            Path(directory),
            expected_database=expected_database,
            environment=environment,
            source_commit=source_commit,
            operator_claim=operator_claim,
            reason=reason,
        )
        if locked_plan != reviewed_plan:
            raise MigrationAdoptionRefused("forward migration plan changed after human review")
        _assert_forward_audit_slot_empty(conn, reviewed_plan)

        transaction_id = conn.execute("SELECT txid_current()").fetchone()[0]
        for expected in reviewed_plan["pending_manifest"]:
            filename = expected["filename"]
            raw = _safe_read_bytes(Path(directory) / filename, max_bytes=2_000_000)
            if (
                len(raw) != expected["bytes"]
                or hashlib.sha256(raw).hexdigest() != expected["sha256"]
            ):
                raise MigrationAdoptionRefused(
                    f"pending migration bytes changed after review: {filename}"
                )
            try:
                statement = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise MigrationAdoptionRefused(
                    f"pending migration is not UTF-8: {filename}"
                ) from exc
            conn.execute("SET LOCAL search_path = public, pg_temp")
            conn.execute(statement)
            conn.execute("SET LOCAL search_path = pg_catalog, public")
            if conn.execute("SELECT txid_current()").fetchone()[0] != transaction_id:
                raise MigrationAdoptionRefused(
                    f"pending migration escaped the reviewed transaction: {filename}"
                )
            conn.execute(
                "INSERT INTO public.schema_migrations(filename,sha256) VALUES(%s,%s)",
                (filename, expected["sha256"]),
            )

        final_tracker = _final_tracker(_tracked_migration_manifest(conn))
        if final_tracker != repository_final:
            raise MigrationAdoptionRefused(
                "final migration tracker does not equal the reviewed repository manifest"
            )
        post_attestations = _post_migration_attestations(conn)
        if set(post_attestations) != _POST_MIGRATION_ATTESTATION_KEYS or not all(
            value is True for value in post_attestations.values()
        ):
            failed = sorted(
                name for name, passed in post_attestations.items() if passed is not True
            )
            raise MigrationAdoptionRefused(
                "schema/0023@1 post-migration attestation failed: " + ", ".join(failed)
            )
        rebound_directory, rebound_commit = _resolve_migration_source(repo_root)
        rebound_repository = _repository_manifest(Path(rebound_directory))
        _assert_repository_matches_commit(
            Path(rebound_directory), rebound_commit, rebound_repository,
        )
        if (
            rebound_commit != source_commit
            or rebound_repository != reviewed_plan["repository_manifest"]
        ):
            raise MigrationAdoptionRefused(
                "migration source changed before the audit artifact was committed"
            )

        migration_id = _forward_audit_id(
            database["identity_sha256"], reviewed_plan["plan_sha256"],
        )
        evidence = _forward_evidence_payload(
            reviewed_plan,
            migration_id=migration_id,
            post_attestations=post_attestations,
            final_tracker=final_tracker,
        )
        migrated_at = conn.execute(
            "INSERT INTO public.artifacts ("
            "artifact_id,artifact_type,source_system,actor,actor_kind,timestamp_start,"
            "timestamp_end,input_refs,output_refs,permissions_label,objective_tag,"
            "ground_truth_ref,eval_score,rollback_ref,cost_usd,corrects_ref,payload"
            ") VALUES ("
            "%s,'gate_decision','cli',%s,'human',clock_timestamp(),clock_timestamp(),"
            "%s::uuid[],'{}'::uuid[],'need-to-know','compliance',%s,NULL,%s,NULL,NULL,%s"
            ") RETURNING timestamp_start",
            (
                migration_id,
                operator_claim["actor"],
                [uuid.UUID(reviewed_plan["prior_audit"]["artifact_id"])],
                reviewed_plan["plan_sha256"],
                Jsonb({
                    "supported": False,
                    "reason": "forward schema migrations are irreversible attestations",
                }),
                Jsonb(evidence),
            ),
        ).fetchone()[0]
        conn.commit()
    return {
        "migration_id": str(migration_id),
        "migrated_at": migrated_at.isoformat(),
        "plan_sha256": reviewed_plan["plan_sha256"],
        "database_identity_sha256": database["identity_sha256"],
        "applied_filenames": [row["filename"] for row in reviewed_plan["pending_manifest"]],
        "semantic_retry": False,
    }


def apply_migrations(
    dsn: str,
    directory: str | Path,
    *,
    allow_partial_test_directory: bool = False,
) -> list[str]:
    """Bootstrap an isolated *_test database; non-test migration uses the audited actuator."""
    directory = Path(directory)
    applied: list[str] = []
    with psycopg.connect(dsn) as conn:
        conn.execute("SET LOCAL search_path = pg_catalog, public")
        database = conn.execute("SELECT current_database()").fetchone()[0]
        if not database.lower().endswith("_test"):
            raise RuntimeError(
                "generic migration bootstrap is restricted to isolated *_test databases"
            )
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_MIGRATION_LOCK,))
        conn.execute(_TRACKER)
        conn.execute("LOCK TABLE public.schema_migrations IN ACCESS EXCLUSIVE MODE")
        if allow_partial_test_directory and not database.lower().endswith("_test"):
            raise RuntimeError("partial migration directories are permitted only in *_test databases")
        manifest = _repository_manifest(directory)
        repository_names = {row["filename"] for row in manifest}
        done = dict(conn.execute(
            "SELECT filename,sha256 FROM public.schema_migrations"
        ))
        if not allow_partial_test_directory:
            unknown = sorted(set(done) - repository_names)
            nulls = sorted(filename for filename, checksum in done.items() if checksum is None)
            if unknown or nulls:
                raise RuntimeError(
                    "migration tracker contains unknown or untrusted history; audited repair is required"
                )
            repository_order = [row["filename"] for row in manifest]
            tracked_order = sorted(done)
            if tracked_order != repository_order[:len(tracked_order)]:
                raise RuntimeError(
                    "migration tracker is not an exact ordered repository prefix"
                )
        for item in manifest:
            path = directory / item["filename"]
            raw = _safe_read_bytes(path, max_bytes=2_000_000)
            checksum = hashlib.sha256(raw).hexdigest()
            if checksum != item["sha256"] or len(raw) != item["bytes"]:
                raise RuntimeError(f"migration changed while being applied: {item['filename']}")
            if item["filename"] in done:
                recorded = done[item["filename"]]
                if recorded is not None and recorded != checksum:
                    raise RuntimeError(
                        f"applied migration checksum differs from repository: {item['filename']}"
                    )
                if recorded is None:
                    raise RuntimeError(
                        "applied migration has no trustworthy checksum; audited adoption is required: "
                        f"{item['filename']}"
                    )
                continue
            try:
                statement = raw.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise RuntimeError(f"migration is not UTF-8: {item['filename']}") from exc
            conn.execute("SET LOCAL search_path = public, pg_temp")
            conn.execute(statement)
            conn.execute("SET LOCAL search_path = pg_catalog, public")
            conn.execute(
                "INSERT INTO public.schema_migrations (filename, sha256) VALUES (%s, %s)",
                (item["filename"], checksum),
            )
            applied.append(item["filename"])
        conn.commit()
    return applied
