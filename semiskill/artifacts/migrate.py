from pathlib import Path
import psycopg

_TRACKER = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    filename text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
"""


def apply_migrations(dsn: str, directory: str | Path) -> list[str]:
    """Apply every *.sql in `directory` in filename order, once. Returns newly applied."""
    directory = Path(directory)
    applied: list[str] = []
    with psycopg.connect(dsn) as conn:
        conn.execute(_TRACKER)
        done = {r[0] for r in conn.execute("SELECT filename FROM schema_migrations")}
        for path in sorted(directory.glob("*.sql")):
            if path.name in done:
                continue
            conn.execute(path.read_text())
            conn.execute(
                "INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,)
            )
            applied.append(path.name)
        conn.commit()
    return applied
