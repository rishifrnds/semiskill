"""Batch orchestrator: mint review-batch contracts from a validated scoreboard snapshot.

    python tools/issue_batch.py --snapshot reports/scoreboard.json --phase review \
        --prompt-version P1-ADVERSARIAL-REVIEW@3 --size 10 --out-dir reports/contracts/<batch-id>/

`tools/collect_wave.py` was written to CONSUME the exact contract documented in
``docs/WORKFLOW.md`` and validated strictly by ``collect_wave.py::load_contract`` /
``semiskill.authoring.review_collection._validate``, but nothing produced one — this is that
producer. It has **no gate authority**: it leases work, it never decides readiness.

What it does, in order:

1. Loads and semantically validates the scoreboard snapshot, then re-verifies it against the
   *current* repository/database state (``_verify_snapshot_freshness``) — a stale or
   source/database-mismatched snapshot leases a payload that may no longer exist and is refused
   before anything else happens.
2. Selects up to ``MAX_BATCH_SIZE`` eligible cells as a pure function of the snapshot's own
   (already role/level/slug-sorted) ``cells`` array — same snapshot in, same batch out.
3. For each selected cell, binds identity *from the snapshot* (``artifacts.skill_version_id``,
   ``payload_hashes``) — never by re-reading ``skills/`` — fetches and re-verifies the exact
   ``skill_version`` artifact via ``payload_fingerprint`` (reused, not reimplemented), and leases it
   through the same append-only actuator ``collect_wave.py`` trusts:
   ``semiskill.authoring.review_collection.issue_review_batch_contract``. A cell that fails any of
   this is refused with a typed reason and the batch continues with the rest.
4. Renders the worker prompt for that lease from ``docs/PROMPT_LIBRARY.md`` with every
   ``{{PLACEHOLDER}}`` resolved, refusing rather than emitting a prompt with anything unresolved.
5. Writes one contract JSON + one prompt text file per issued cell, plus a batch manifest that
   reports every refusal — a batch driver that reports phantom work as real work is the failure
   mode this whole file exists to avoid.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from semiskill.artifacts.schema import ArtifactType  # noqa: E402
from semiskill.artifacts.store import PostgresArtifactStore  # noqa: E402
from semiskill.authoring.gate import (  # noqa: E402
    ADVERSARIAL_REVIEW_PROMPT,
    CALIBRATED_RECHECK_PROMPT,
    CONTENT_REVIEW_KIND,
    REVIEWED,
    UNREVIEWED,
)
from semiskill.authoring.review_collection import (  # noqa: E402
    MAX_BATCH_SIZE,
    BatchRejected,
    ReviewBatchContract,
    ReviewCellContract,
    issue_review_batch_contract,
    review_batch_contract_document,
)
from semiskill.authoring.snapshot import (  # noqa: E402
    SnapshotUnavailable,
    full_input_tree_sha256,
    load_scoreboard_snapshot,
)
from semiskill.capture.intake import payload_fingerprint  # noqa: E402
from semiskill.config import Config  # noqa: E402

PROMPT_LIBRARY_PATH = REPO / "docs" / "PROMPT_LIBRARY.md"
_PLACEHOLDER = re.compile(r"\{\{([^{}]+)\}\}")


class BatchRefused(RuntimeError):
    """The whole run is refused before any contract/prompt file is written."""


def _confined_path(repo_root: Path, raw: object, *, what: str) -> Path:
    """Join a snapshot-supplied path onto `repo_root` and refuse any escape.

    `sources.registry.path` / `sources.skills.root` come from the snapshot document, which is
    untrusted input (CLAUDE.md: treat every submitted artifact as an injection payload) — not a
    value this file may assume is repo-relative. `Path.__truediv__` silently discards `repo_root`
    when the right operand is absolute, and a relative `..`-laden string escapes it once resolved,
    which would otherwise turn this freshness check into an arbitrary local file read / directory
    enumeration. Mirrors the containment check the trusted generator already applies on write
    (semiskill/authoring/snapshot.py, ~line 1383) on the read side too.
    """
    text = str(raw) if raw is not None else ""
    if not text or text.strip() != text:
        raise BatchRefused(f"snapshot {what} path is empty or has surrounding whitespace")
    resolved_root = repo_root.resolve()
    resolved = (repo_root / text).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError:
        raise BatchRefused(f"snapshot {what} path escapes the repository: {text!r}") from None
    return resolved


@dataclass(frozen=True, slots=True)
class Refusal:
    """One typed, reported refusal. The rest of the batch still proceeds."""

    slug: str
    reason: str
    detail: str

    def as_dict(self) -> dict:
        return {"slug": self.slug, "reason": self.reason, "detail": self.detail}


# --------------------------------------------------------------------------------------
# Snapshot freshness (SPEC B requirement 1)
# --------------------------------------------------------------------------------------

def _verify_snapshot_freshness(document: dict, *, repo_root: Path, store) -> None:
    """Refuse a snapshot whose source/database provenance no longer matches reality.

    ``load_scoreboard_snapshot`` already proves the JSON is internally consistent and unmodified
    (it recomputes ``snapshot_id``). This additionally proves it is *current*: the registry file,
    the full skills/ tree, the repository commit, and the connected database must still be the
    ones the snapshot was generated from.
    """
    sources = document.get("sources")
    if not isinstance(sources, dict):
        raise BatchRefused("snapshot has no sources section to verify freshness against")

    registry_source = sources.get("registry") or {}
    registry_path = _confined_path(repo_root, registry_source.get("path"), what="registry")
    try:
        registry_bytes = registry_path.read_bytes()
    except OSError as exc:
        raise BatchRefused(f"cannot read {registry_path} to verify snapshot freshness") from exc
    actual_registry_sha = "sha256:" + sha256(registry_bytes).hexdigest()
    if actual_registry_sha != registry_source.get("sha256"):
        raise BatchRefused(
            "snapshot is source-mismatched: the registry file has changed since the snapshot "
            "was generated"
        )

    skills_source = sources.get("skills") or {}
    skills_root = _confined_path(repo_root, skills_source.get("root"), what="skills")
    try:
        actual_tree_sha = full_input_tree_sha256(skills_root)
    except SnapshotUnavailable as exc:
        raise BatchRefused(f"cannot hash {skills_root} to verify snapshot freshness: {exc}") from exc
    if actual_tree_sha != skills_source.get("full_tree_sha256"):
        raise BatchRefused(
            "snapshot is stale: skills/ has changed on disk since the snapshot was generated"
        )

    repository_source = sources.get("repository") or {}
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, check=True, capture_output=True,
            text=True, encoding="utf-8",
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise BatchRefused("cannot determine the current git HEAD to verify snapshot freshness") from exc
    if head != repository_source.get("commit"):
        raise BatchRefused(
            "snapshot is source-mismatched: the repository HEAD has moved since the snapshot "
            "was generated"
        )

    database_source = sources.get("database") or {}
    identity_reader = getattr(store, "database_identity", None)
    if not callable(identity_reader):
        raise BatchRefused("connected store cannot report a database identity to verify against")
    actual_database = identity_reader(environment=database_source.get("environment"))
    if (
        actual_database.get("identity_sha256") != database_source.get("identity_sha256")
        or actual_database.get("database_name") != database_source.get("database_name")
    ):
        raise BatchRefused(
            "snapshot is database-mismatched: the connected database is not the one the "
            "snapshot was generated from"
        )


# --------------------------------------------------------------------------------------
# Selection — a pure function of the snapshot (SPEC B requirement 2)
# --------------------------------------------------------------------------------------

def _select_cells(document: dict, *, phase: str, size: int) -> list[dict]:
    """Filter the snapshot's own (already role/level/slug-sorted) cells; never reorders them."""
    cells = document.get("cells")
    if not isinstance(cells, list):
        raise BatchRefused("snapshot has no cells array")
    selected: list[dict] = []
    for cell in cells:
        if not isinstance(cell, dict) or cell.get("registry_status") != "active":
            continue
        content = (cell.get("checks") or {}).get("content_review") or {}
        status = content.get("status")
        blockers = cell.get("blockers") or []
        if phase == "review":
            if status != UNREVIEWED or blockers:
                continue
        else:
            if status != REVIEWED:
                continue
            if any(blocker.get("source") != "review" for blocker in blockers):
                continue
        selected.append(cell)
        if len(selected) >= size:
            break
    return selected


# --------------------------------------------------------------------------------------
# Per-cell identity binding + refusal (SPEC B requirements 3 and 6)
# --------------------------------------------------------------------------------------

def _cell_checks(cell: dict) -> dict:
    """Rebuild the four REQUIRED_CHECKS booleans from the snapshot's own recorded evidence."""
    checks = cell.get("checks") or {}
    lint = checks.get("lint") or {}
    consistency = checks.get("consistency") or {}
    security = checks.get("security") or {}
    hashes = cell.get("payload_hashes") or {}
    artifacts = cell.get("artifacts") or {}
    return {
        "strict_lint": {
            "passed": bool((cell.get("stage_flags") or {}).get("strict_lint_pass")),
            "evidence": (
                f"lint:{lint.get('status')} predicted={lint.get('predicted_verdict')} "
                f"errors={lint.get('errors')} warnings={lint.get('warnings')} "
                f"advisories={lint.get('advisories')}"
            ),
        },
        "consistency": {
            "passed": consistency.get("status") == "passed",
            "evidence": (
                f"consistency:{consistency.get('status')} errors={consistency.get('errors')} "
                f"warnings={consistency.get('warnings')}"
            ),
        },
        "source_hash": {
            "passed": bool(hashes.get("source")) and hashes.get("source") == hashes.get("skill_version"),
            "evidence": f"source={hashes.get('source')} skill_version={hashes.get('skill_version')}",
        },
        "artifact_reconciliation": {
            "passed": (
                security.get("status") == "passed"
                and artifacts.get("skill_version_id") is not None
                and artifacts.get("automated_review_id") is not None
            ),
            "evidence": (
                f"security:{security.get('status')} "
                f"automated_review={artifacts.get('automated_review_id')} "
                f"scans={len(artifacts.get('scan_artifact_ids') or [])}"
            ),
        },
    }


def _lease_cell(store, cell: dict, *, phase: str):
    """Bind and verify one cell's identity against the store. Returns a Refusal, never raises."""
    slug = cell.get("slug")
    raw_id = (cell.get("artifacts") or {}).get("skill_version_id")
    if not raw_id:
        return Refusal(slug, "MISSING_SKILL_VERSION_ID", "snapshot cell has no artifacts.skill_version_id")
    try:
        skill_version_id = uuid.UUID(raw_id)
    except (ValueError, AttributeError, TypeError):
        return Refusal(slug, "INVALID_SKILL_VERSION_ID", str(raw_id))

    artifact = store.get(skill_version_id)
    if artifact is None or artifact.artifact_type is not ArtifactType.SKILL_VERSION:
        return Refusal(slug, "SKILL_VERSION_NOT_FOUND", str(raw_id))
    if not isinstance(artifact.payload, dict) or artifact.payload.get("slug") != slug:
        return Refusal(slug, "SLUG_MISMATCH", f"artifact slug={artifact.payload.get('slug')!r}")

    actual_hash = payload_fingerprint(artifact.payload)
    expected_hash = (cell.get("payload_hashes") or {}).get("skill_version")
    if not expected_hash or expected_hash != actual_hash:
        return Refusal(slug, "HASH_MISMATCH", f"snapshot={expected_hash} actual={actual_hash}")

    for facet in ("role", "level"):
        if artifact.payload.get(facet) != cell.get(facet):
            return Refusal(
                slug, "FACET_MISMATCH",
                f"{facet}: snapshot={cell.get(facet)!r} artifact={artifact.payload.get(facet)!r}",
            )

    checks = _cell_checks(cell)
    if not all(check["passed"] for check in checks.values()):
        failed = sorted(name for name, check in checks.items() if not check["passed"])
        return Refusal(slug, "CHECKS_NOT_PASSED", "failed checks: " + ", ".join(failed))

    token = uuid.uuid4().hex[:10]

    if phase == "review":
        prior_review_ref = None
        lineage_id = str(uuid.uuid4())
        attempt = 1
        run_id = f"review:{slug}:{token}"
        reviewer_identity = f"reviewer:{slug}:{token}"
        fixer_identity = "not-applicable:pre-fix"
    elif phase == "recheck":
        raw_prior = (cell.get("artifacts") or {}).get("content_review_id")
        if not raw_prior:
            return Refusal(slug, "MISSING_PRIOR_REVIEW", "snapshot cell has no artifacts.content_review_id")
        try:
            prior_id = uuid.UUID(raw_prior)
        except (ValueError, AttributeError, TypeError):
            return Refusal(slug, "INVALID_PRIOR_REVIEW_ID", str(raw_prior))
        prior = store.get(prior_id)
        if (
            prior is None
            or prior.artifact_type is not ArtifactType.REVIEW
            or not isinstance(prior.payload, dict)
            or prior.payload.get("review_kind") != CONTENT_REVIEW_KIND
            or prior.payload.get("slug") != slug
        ):
            return Refusal(slug, "PRIOR_REVIEW_NOT_FOUND", str(raw_prior))
        prior_attempt = prior.payload.get("attempt")
        prior_lineage = prior.payload.get("lineage_id")
        if type(prior_attempt) is not int or prior_attempt < 1 or not isinstance(prior_lineage, str):
            return Refusal(slug, "PRIOR_REVIEW_MALFORMED", "prior review attempt/lineage_id is invalid")
        attempt = prior_attempt + 1
        prior_review_ref = prior.artifact_id
        lineage_id = prior_lineage
        run_id = f"recheck:{slug}:{token}"
        reviewer_identity = f"reviewer:{slug}:{token}"
        fixer_identity = f"fixer:{slug}:{token}"
    else:
        return Refusal(slug, "UNKNOWN_PHASE", str(phase))

    cell_contract = ReviewCellContract(
        skill_version=artifact,
        reviewer_identity=reviewer_identity,
        fixer_identity=fixer_identity,
        checks=checks,
        lineage_id=lineage_id,
        prior_review_ref=prior_review_ref,
    )
    meta = {
        "run_id": run_id,
        "attempt": attempt,
        "role": artifact.payload.get("role"),
        "level": artifact.payload.get("level"),
        "version": artifact.payload.get("version"),
        "payload_sha256": actual_hash,
        "checks": checks,
    }
    return cell_contract, meta


# --------------------------------------------------------------------------------------
# Worker prompt rendering (SPEC B requirement 5)
# --------------------------------------------------------------------------------------

def _load_prompt_sections(path: Path) -> dict[str, str]:
    """Split docs/PROMPT_LIBRARY.md into sections keyed by the first token of each ``## `` heading."""
    text = path.read_text(encoding="utf-8")
    sections: dict[str, str] = {}
    key: str | None = None
    lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if key is not None:
                sections[key] = "\n".join(lines).strip("\n")
            heading = line[3:].strip()
            key = heading.split()[0] if heading else None
            lines = []
        elif key is not None:
            lines.append(line)
    if key is not None:
        sections[key] = "\n".join(lines).strip("\n")
    return sections


def _extract_code_block(section_text: str) -> str:
    lines = section_text.splitlines()
    start = end = None
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            if start is None:
                start = index + 1
            else:
                end = index
                break
    if start is None or end is None:
        raise BatchRefused("prompt library section has no fenced prompt block")
    return "\n".join(lines[start:end])


def render_worker_prompt(prompt_version: str, context: dict[str, str]) -> str:
    """Render one worker prompt from docs/PROMPT_LIBRARY.md with every placeholder resolved.

    An unresolved ``{{...}}`` — an unknown prompt version, an unknown embedded boundary section,
    or a context value the caller did not supply — is a refused run, never a partially-filled
    prompt (docs/PROMPT_LIBRARY.md: "an unresolved placeholder is a refused run").
    """
    sections = _load_prompt_sections(PROMPT_LIBRARY_PATH)
    if prompt_version not in sections:
        raise BatchRefused(f"prompt library has no section for {prompt_version!r}")
    body = _extract_code_block(sections[prompt_version])

    for match in list(_PLACEHOLDER.finditer(body)):
        token = match.group(1)
        if token.startswith("P0-BOUNDARY@"):
            if token not in sections:
                raise BatchRefused(f"prompt library is missing referenced section {token!r}")
            boundary = _extract_code_block(sections[token])
            body = body.replace("{{" + token + "}}", boundary)

    def _substitute(match: "re.Match[str]") -> str:
        token = match.group(1)
        if token not in context:
            raise BatchRefused(f"unresolved prompt placeholder: {{{{{token}}}}}")
        return context[token]

    rendered = _PLACEHOLDER.sub(_substitute, body)
    unresolved = _PLACEHOLDER.findall(rendered)
    if unresolved:
        raise BatchRefused(f"unresolved prompt placeholders after substitution: {unresolved}")
    return rendered


def _prompt_context(*, slug, skill_version_id, payload_sha256, role, level, version,
                     batch_id, run_id, attempt, reviewer_identity, fixer_identity,
                     prior_review_ref, checks) -> dict[str, str]:
    return {
        "SLUG": slug,
        "SKILL_VERSION_ID": str(skill_version_id),
        "PAYLOAD_SHA256": payload_sha256,
        "ROLE": role or "",
        "LEVEL": level or "",
        "VERSION": version or "",
        "BATCH_ID": batch_id,
        "RUN_ID": run_id,
        "ATTEMPT": str(attempt),
        "READ_SCOPE": f"skills/{slug}/ (leased payload only; skills/_shared/ canonical files if referenced)",
        "WRITE_SCOPE_OR_NONE": "none (P1/P5 are read-only)",
        "TOOL_ALLOWLIST": "Read, Grep, Glob",
        "REPO": REPO.as_posix(),
        "REVIEWER_IDENTITY": reviewer_identity,
        "FRESH_REVIEWER_IDENTITY": reviewer_identity,
        "FIXER_IDENTITY": fixer_identity,
        "PRIOR_REVIEW_REF_OR_NULL": (
            "null" if prior_review_ref is None else json.dumps(str(prior_review_ref))
        ),
        "DETERMINISTIC_CHECK_EVIDENCE": json.dumps(checks, sort_keys=True),
    }


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------

def run_issue_batch(
    *,
    store,
    document: dict,
    phase: str,
    prompt_version: str,
    size: int,
    out_dir: Path,
    batch_id: str | None = None,
    issuer_identity: str = "orchestrator:issue_batch@1",
    verify_freshness: bool = True,
    repo_root: Path = REPO,
) -> dict:
    """Issue up to ``size`` review-batch contracts and write a contract+prompt file for each.

    Pure with respect to selection; the only side effects are the append-only contract actuator
    (one durable GATE_DECISION artifact per issued cell) and the files written under ``out_dir``.
    """
    if phase not in {"review", "recheck"}:
        raise BatchRefused(f"unknown phase: {phase!r}")
    if phase == "review" and not ADVERSARIAL_REVIEW_PROMPT.fullmatch(prompt_version):
        raise BatchRefused(
            "--phase review requires a calibrated P1-ADVERSARIAL-REVIEW@N prompt version"
        )
    if phase == "recheck" and not CALIBRATED_RECHECK_PROMPT.fullmatch(prompt_version):
        raise BatchRefused(
            "--phase recheck requires a calibrated P5-RECHECK-CALIBRATED@N prompt version"
        )
    if type(size) is not int or not 1 <= size <= MAX_BATCH_SIZE:
        raise BatchRefused(f"--size must be an integer between 1 and {MAX_BATCH_SIZE}")

    if verify_freshness:
        _verify_snapshot_freshness(document, repo_root=repo_root, store=store)

    identity_reader = getattr(store, "review_coordinator_authentication_context", None)
    authentication_context = (
        identity_reader() if callable(identity_reader)
        else {"provider": "test", "subject_sha256": "sha256:" + "0" * 64}
    )

    batch_id = batch_id or (
        f"{phase}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"
    )
    eligible = _select_cells(document, phase=phase, size=size)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    issued: list[dict] = []
    refusals: list[Refusal] = []
    for cell in eligible:
        slug = cell["slug"]
        leased = _lease_cell(store, cell, phase=phase)
        if isinstance(leased, Refusal):
            refusals.append(leased)
            continue
        cell_contract, meta = leased

        prompt_context = _prompt_context(
            slug=slug, skill_version_id=cell_contract.skill_version.artifact_id,
            payload_sha256=meta["payload_sha256"], role=meta["role"], level=meta["level"],
            version=meta["version"], batch_id=batch_id, run_id=meta["run_id"],
            attempt=meta["attempt"], reviewer_identity=cell_contract.reviewer_identity,
            fixer_identity=cell_contract.fixer_identity,
            prior_review_ref=cell_contract.prior_review_ref, checks=meta["checks"],
        )
        try:
            prompt_text = render_worker_prompt(prompt_version, prompt_context)
        except BatchRefused as exc:
            refusals.append(Refusal(slug, "PROMPT_RENDER_FAILED", str(exc)))
            continue

        contract = ReviewBatchContract(
            batch_id=batch_id, run_id=meta["run_id"], phase=phase, prompt_version=prompt_version,
            attempt=meta["attempt"], cells={slug: cell_contract}, issuer_identity=issuer_identity,
            authentication_context=authentication_context,
        )
        try:
            issued_contract = issue_review_batch_contract(store=store, contract=contract)
        except BatchRejected as exc:
            refusals.append(Refusal(slug, "CONTRACT_REJECTED", str(exc)))
            continue

        contract_document = review_batch_contract_document(issued_contract)
        contract_path = out_dir / f"{slug}.contract.json"
        prompt_path = out_dir / f"{slug}.prompt.txt"
        contract_path.write_text(
            json.dumps(contract_document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        prompt_path.write_text(prompt_text, encoding="utf-8")
        issued.append({
            "slug": slug,
            "contract_artifact_id": contract_document["contract_artifact_id"],
            "contract_path": str(contract_path),
            "prompt_path": str(prompt_path),
            "run_id": meta["run_id"],
            "attempt": meta["attempt"],
        })

    manifest = {
        "batch_id": batch_id, "phase": phase, "prompt_version": prompt_version,
        "snapshot_id": document.get("snapshot_id"), "requested_size": size,
        "eligible_considered": len(eligible), "issued": len(issued), "refused": len(refusals),
        "issued_cells": issued, "refusals": [refusal.as_dict() for refusal in refusals],
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", help="artifact database; defaults to DATABASE_URL")
    parser.add_argument("--snapshot", type=Path, required=True,
                        help="validated scoreboard snapshot JSON (semiskill scoreboard --snapshot-out)")
    parser.add_argument("--phase", required=True, choices=["review", "recheck"])
    parser.add_argument("--prompt-version", required=True,
                        help="e.g. P1-ADVERSARIAL-REVIEW@3 or P5-RECHECK-CALIBRATED@3")
    parser.add_argument("--size", type=int, default=MAX_BATCH_SIZE,
                        help=f"at most {MAX_BATCH_SIZE} skills per batch")
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--batch-id", help="defaults to a generated phase+timestamp id")
    parser.add_argument("--issuer-identity", default="orchestrator:issue_batch@1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    document = load_scoreboard_snapshot(args.snapshot)
    dsn = args.dsn or os.environ.get("DATABASE_URL") or Config.from_env().database_url
    store = PostgresArtifactStore(dsn)
    manifest = run_issue_batch(
        store=store, document=document, phase=args.phase, prompt_version=args.prompt_version,
        size=args.size, out_dir=args.out_dir, batch_id=args.batch_id,
        issuer_identity=args.issuer_identity,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (BatchRefused, BatchRejected, SnapshotUnavailable) as exc:
        print(f"BATCH REFUSED: {exc}", file=sys.stderr)
        raise SystemExit(2)
