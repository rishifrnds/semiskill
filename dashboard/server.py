"""SemiSkill command centre — a local, dependency-free dashboard server.

Serves `index.html` and a live `/api/state` assembled from real signals:
  * repo      — git history, tracked files, module LOC, test inventory
  * runtime   — Docker Postgres reachability and read-API health
  * scoreboard — validated canonical catalog state (never inferred from fixtures or API visibility)
  * plan      — the curated model in `model.json` (features, risks, launch, GTM)
  * inbox     — actions the user has clicked, appended to `inbox.jsonl`

The dashboard's buttons POST to `/api/action`, which appends one JSON line per
request. That file is the feedback channel: Claude reads `dashboard/inbox.jsonl`
and works the queue.

Read-mostly by construction: the only writes are the inbox and run logs, both
under `dashboard/`. `/api/run` executes ONLY commands in `RUNNABLE` — never
caller-supplied strings — and binds to 127.0.0.1.

    python dashboard/server.py            # http://127.0.0.1:8899
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
INBOX = HERE / "inbox.jsonl"
RUNS = HERE / "runs"
MODEL = HERE / "model.json"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from semiskill.authoring.snapshot import (                    # noqa: E402
    SnapshotUnavailable,
    load_progress,
    load_scoreboard_snapshot,
)

PORT = int(os.environ.get("SEMISKILL_DASHBOARD_PORT", "8899"))
API_URL = os.environ.get("SEMISKILL_API", "http://127.0.0.1:8787")

# Whitelisted commands the dashboard may trigger. Nothing else can be run.
RUNNABLE: dict[str, dict] = {
    "tests": {
        "label": "Run the test suite",
        "cmd": [sys.executable, "-m", "pytest", "-q"],
        "note": "Needs the Postgres container up.",
    },
    "db-up": {
        "label": "Start the Postgres container",
        "cmd": ["docker", "compose", "up", "-d", "db"],
        "note": "Requires Docker Desktop running.",
    },
    "api": {
        "label": "Start the read API (background)",
        "cmd": [sys.executable, "-m", "semiskill.api"],
        "note": "Serves the catalog on :8787.",
        "background": True,
    },
    "git-status": {
        "label": "git status",
        "cmd": ["git", "status", "--short", "--branch"],
        "note": "",
    },
}

_run_log: list[dict] = []          # newest last; in-memory ring of run results
_run_lock = threading.Lock()


# ---------------------------------------------------------------- helpers

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sh(args: list[str], timeout: int = 20) -> tuple[int, str]:
    try:
        p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout, encoding="utf-8", errors="replace")
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except FileNotFoundError:
        return 127, f"command not found: {args[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except Exception as e:                                   # noqa: BLE001
        return 1, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------- signals

def repo_signals() -> dict:
    rc, log = _sh(["git", "log", "--format=%h|%aI|%s", "-n", "80"])
    commits = []
    if rc == 0:
        for line in log.splitlines():
            parts = line.split("|", 2)
            if len(parts) == 3:
                sha, iso, subject = parts
                kind = "rotate" if subject.startswith("rotate:") else (
                    "feat" if subject.startswith(("feat:", "fix:")) else "wip")
                phase = ""
                m = re.search(r"\b([A-G]|P0|G)-(\d{3})\b", subject)
                if m:
                    phase = m.group(1)
                commits.append({"sha": sha, "date": iso, "subject": subject,
                                "kind": kind, "phase": phase})

    rc, status = _sh(["git", "status", "--porcelain"])
    dirty = [l for l in status.splitlines() if l.strip()] if rc == 0 else []
    rc, branch = _sh(["git", "rev-parse", "--abbrev-ref", "HEAD"])

    modules, tests = [], []
    for p in sorted((ROOT / "semiskill").rglob("*.py")):
        loc = sum(1 for _ in p.open(encoding="utf-8", errors="replace"))
        if loc:
            modules.append({"path": p.relative_to(ROOT).as_posix(), "loc": loc,
                            "layer": _layer_of(p.relative_to(ROOT).as_posix())})
    test_re = re.compile(r"^\s*(?:async\s+)?def\s+test_", re.M)
    for p in sorted((ROOT / "tests").rglob("test_*.py")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        n = len(test_re.findall(txt))
        if n:
            rel = p.relative_to(ROOT).as_posix()
            tests.append({"path": rel, "count": n, "group": rel.split("/")[1]})

    return {"commits": commits, "branch": branch.strip(), "dirty": len(dirty),
            "dirty_files": dirty[:20], "modules": modules, "tests": tests,
            "total_tests": sum(t["count"] for t in tests),
            "collected_tests": collected_tests(),
            "total_loc": sum(m["loc"] for m in modules)}


_collect_cache = {"n": 0, "at": 0.0}


def collected_tests() -> int:
    """True pytest count (parametrized cases expand past the `def test_` count).

    Collection-only, so it needs no database. Cached for 5 minutes.
    """
    if _collect_cache["n"] and time.time() - _collect_cache["at"] < 300:
        return _collect_cache["n"]
    rc, out = _sh([sys.executable, "-m", "pytest", "--collect-only", "-q"], timeout=90)
    m = re.search(r"(\d+)\s+tests? collected", out)
    if m:
        _collect_cache.update(n=int(m.group(1)), at=time.time())
    return _collect_cache["n"]


_LAYER_MAP = [
    ("semiskill/capture", "L1"), ("semiskill/cli.py", "L1"),
    ("semiskill/artifacts", "L2"), ("semiskill/spine", "L2"),
    ("semiskill/context", "L3"), ("semiskill/api.py", "L3"),
    ("semiskill/governance", "L4"),
    ("semiskill/intelligence", "L5"),
    ("semiskill/scanners", "L6"), ("semiskill/sensor", "L6"),
    ("semiskill/redteam", "L6"),
]


def _layer_of(path: str) -> str:
    for prefix, layer in _LAYER_MAP:
        if path.startswith(prefix):
            return layer
    return "core"


def state_files() -> dict:
    out = {}
    for name in ("STATUS.md", "MEMORY.md", "BLOCKERS.md"):
        p = ROOT / name
        out[name] = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""

    status = out["STATUS.md"]
    memory = out["MEMORY.md"]
    phase = ""
    m = re.search(r"^## Current Phase\s*\n(.+)$", memory, re.M)
    if m:
        phase = m.group(1).strip()
    right_now = ""
    m = re.search(r"^## Right now\s*\n((?:.+\n?)+?)(?:\n##|\Z)", status, re.M)
    if m:
        right_now = m.group(1).strip()
    gaps = re.findall(r"^- (Stage.+|pgvector.+|SharePoint.+|Phase G.+)$", status, re.M)
    steps = re.findall(r"^- \[([^\]]+)\]\s+(\S+)\s+status:\s*(\w+)\s*\n\s+what:\s*(.+)$",
                       memory, re.M)
    # strip HTML comments first — BLOCKERS.md keeps its entry template commented out
    live_blockers = re.sub(r"<!--.*?-->", "", out["BLOCKERS.md"], flags=re.S)
    blockers = [l.strip() for l in live_blockers.splitlines() if l.startswith("## [BLK-")]
    return {"phase": phase, "right_now": right_now, "gaps": gaps,
            "steps": [{"id": a, "ts": b, "status": c, "what": d} for a, b, c, d in steps],
            "blockers": blockers}


def runtime_signals() -> dict:
    """Best-effort liveness probes. Everything degrades to 'down' without raising."""
    out = {"checked_at": _now()}

    rc, _ = _sh(["docker", "info", "--format", "{{.ServerVersion}}"], timeout=8)
    out["docker"] = "up" if rc == 0 else "down"

    db = {"status": "down", "detail": ""}
    try:
        sys.path.insert(0, str(ROOT))
        import psycopg                                        # noqa: PLC0415
        from semiskill.config import Config                   # noqa: PLC0415
        dsn = Config.from_env().database_url
        with psycopg.connect(dsn, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("select count(*) from artifacts")
                total = cur.fetchone()[0]
                cur.execute("select artifact_type, count(*) from artifacts group by 1 order by 2 desc")
                by_type = [{"type": t, "n": n} for t, n in cur.fetchall()]
        db = {"status": "up", "detail": "", "artifacts": total, "by_type": by_type}
    except Exception as e:                                    # noqa: BLE001
        db["detail"] = f"{type(e).__name__}: {str(e)[:160]}"
    out["db"] = db

    api = {"status": "down", "detail": ""}
    try:
        import urllib.request                                  # noqa: PLC0415
        with urllib.request.urlopen(f"{API_URL}/health", timeout=2) as r:
            if r.status == 200:
                api["status"] = "up"
    except Exception as e:                                    # noqa: BLE001
        api["detail"] = f"{type(e).__name__}: {str(e)[:120]}"
    out["api"] = api
    return out


def canonical_snapshot_signals() -> dict:
    """Load canonical catalog state or expose an explicit, non-substituted unavailable state."""
    observed_at = _now()
    scoreboard = {
        "status": "unavailable", "observed_at": observed_at,
        "reason": "not_configured", "snapshot": None,
    }
    progress = {
        "status": "unavailable", "observed_at": observed_at,
        "reason": "scoreboard_unavailable", "snapshot": None,
    }
    scoreboard_path = os.environ.get("SEMISKILL_SCOREBOARD_SNAPSHOT")
    if not scoreboard_path:
        return {"scoreboard": scoreboard, "progress": progress}
    try:
        snapshot = load_scoreboard_snapshot(scoreboard_path)
    except SnapshotUnavailable:
        scoreboard["reason"] = "invalid_or_unavailable"
        return {"scoreboard": scoreboard, "progress": progress}
    environment = os.environ.get("SEMISKILL_ENVIRONMENT", "development")
    if snapshot["sources"]["database"]["environment"] != environment:
        scoreboard["reason"] = "environment_mismatch"
        return {"scoreboard": scoreboard, "progress": progress}

    scoreboard.update(status="available", reason=None, snapshot=snapshot)
    progress["reason"] = "not_configured"
    progress_path = os.environ.get("SEMISKILL_PROGRESS_SNAPSHOT")
    if progress_path:
        try:
            progress_snapshot = load_progress(progress_path, snapshot["snapshot_id"])
        except SnapshotUnavailable:
            progress["reason"] = "invalid_or_unavailable"
        else:
            progress.update(status="available", reason=None, snapshot=progress_snapshot)
    return {"scoreboard": scoreboard, "progress": progress}


def redteam_attacks() -> list[dict]:
    f = ROOT / "tests" / "redteam" / "fixtures" / "generated_attacks.json"
    if not f.exists():
        return []
    return [{"name": a.get("name", ""), "attack_class": a.get("attack_class", ""),
             "technique": a.get("technique", ""), "blocked": True}
            for a in json.loads(f.read_text(encoding="utf-8"))]


def adrs() -> list[dict]:
    p = ROOT / "DECISIONS.md"
    if not p.exists():
        return []
    return [{"id": i, "title": t.strip()} for i, t in
            re.findall(r"^## \[(ADR-\d+)\]\s*(.+)$", p.read_text(encoding="utf-8"), re.M)]


def read_inbox() -> list[dict]:
    if not INBOX.exists():
        return []
    rows = []
    for line in INBOX.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return rows


def build_state() -> dict:
    model = json.loads(MODEL.read_text(encoding="utf-8"))
    canonical = canonical_snapshot_signals()
    return {
        "generated_at": _now(),
        "model": model,
        "repo": repo_signals(),
        "state": state_files(),
        "runtime": runtime_signals(),
        "scoreboard": canonical["scoreboard"],
        "progress": canonical["progress"],
        "attacks": redteam_attacks(),
        "adrs": adrs(),
        "inbox": read_inbox(),
        "runs": list(_run_log[-25:]),
        "runnable": [{"id": k, "label": v["label"], "note": v.get("note", "")}
                     for k, v in RUNNABLE.items()],
    }


# ---------------------------------------------------------------- actions

def append_action(payload: dict) -> dict:
    row = {
        "id": payload.get("action_id") or f"ACT-{uuid.uuid4().hex[:8]}",
        "ts": _now(),
        "kind": str(payload.get("kind", "task"))[:40],
        "title": str(payload.get("title", ""))[:300],
        "prompt": str(payload.get("prompt", ""))[:4000],
        "context": str(payload.get("context", ""))[:300],
        "priority": str(payload.get("priority", "normal"))[:20],
        "status": "queued",
    }
    with INBOX.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def run_command(key: str) -> dict:
    spec = RUNNABLE.get(key)
    if not spec:
        return {"ok": False, "error": "unknown command"}
    RUNS.mkdir(exist_ok=True)
    started = _now()

    if spec.get("background"):
        try:
            subprocess.Popen(spec["cmd"], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            entry = {"id": key, "label": spec["label"], "started": started,
                     "code": 0, "output": "started in background", "ok": True}
        except Exception as e:                                # noqa: BLE001
            entry = {"id": key, "label": spec["label"], "started": started,
                     "code": 1, "output": str(e), "ok": False}
    else:
        code, out = _sh(spec["cmd"], timeout=600)
        entry = {"id": key, "label": spec["label"], "started": started,
                 "finished": _now(), "code": code, "ok": code == 0,
                 "output": out[-6000:]}
        (RUNS / f"{key}-{int(time.time())}.log").write_text(out, encoding="utf-8")

    with _run_lock:
        _run_log.append(entry)
    return entry


# ---------------------------------------------------------------- http

class Handler(BaseHTTPRequestHandler):
    server_version = "SemiSkillCommandCentre/1.0"

    def log_message(self, *a):
        pass

    def _json(self, code: int, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _file(self, path: Path, ctype: str):
        if not path.exists():
            return self._json(404, {"error": "not found"})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        route = urlparse(self.path).path
        if route in ("/", "/index.html"):
            return self._file(HERE / "index.html", "text/html; charset=utf-8")
        if route == "/api/state":
            try:
                return self._json(200, build_state())
            except Exception as e:                            # noqa: BLE001
                return self._json(500, {"error": f"{type(e).__name__}: {e}"})
        if route == "/api/inbox":
            return self._json(200, {"inbox": read_inbox()})
        if route == "/api/runs":
            return self._json(200, {"runs": list(_run_log[-25:])})
        return self._json(404, {"error": "unknown route"})

    def do_POST(self):
        route = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "bad json"})

        if route == "/api/action":
            row = append_action(payload)
            print(f"  [queued] {row['kind']}: {row['title']}")
            return self._json(200, {"ok": True, "action": row})
        if route == "/api/run":
            key = str(payload.get("id", ""))
            print(f"  [run] {key}")
            return self._json(200, run_command(key))
        if route == "/api/inbox/clear":
            if INBOX.exists():
                INBOX.rename(INBOX.with_suffix(f".{int(time.time())}.jsonl"))
            return self._json(200, {"ok": True})
        return self._json(404, {"error": "unknown route"})


def main():
    try:                                    # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:                       # noqa: BLE001
        pass
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print(f"SemiSkill command centre -> {url}")
    print(f"  action queue: {INBOX}")
    print("  (buttons on the dashboard append to that file; Ctrl-C to stop)")
    if "--no-open" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
