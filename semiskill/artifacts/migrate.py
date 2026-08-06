from pathlib import Path
import hashlib
import psycopg

_TRACKER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now(),
    sha256 text
);
ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS sha256 text;
"""


def apply_migrations(dsn: str, directory: str | Path) -> list[str]:
    """Apply every *.sql in `directory` in filename order, once. Returns newly applied."""
    directory = Path(directory)
    applied: list[str] = []
    with psycopg.connect(dsn) as conn:
        conn.execute(_TRACKER)
        done = dict(conn.execute("SELECT filename, sha256 FROM schema_migrations"))
        for path in sorted(directory.glob("*.sql")):
            raw = path.read_bytes()
            checksum = hashlib.sha256(raw).hexdigest()
            if path.name in done:
                recorded = done[path.name]
                if recorded is not None and recorded != checksum:
                    raise RuntimeError(
                        f"applied migration checksum differs from repository: {path.name}"
                    )
                if recorded is None:
                    raise RuntimeError(
                        "applied migration has no trustworthy checksum; audited adoption is required: "
                        f"{path.name}"
                    )
                continue
            conn.execute(raw.decode("utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (filename, sha256) VALUES (%s, %s)",
                (path.name, checksum),
            )
            applied.append(path.name)
        conn.commit()
    return applied
