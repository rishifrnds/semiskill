"""ADR-024 Stage 2 — the trusted host adapter.

This is the piece that decides whether a Stage-2 result may exist at all. It projects the exact
payload into scanner-owned staging, invokes a digest-pinned engine, validates the bounded exact-key
report, and binds the result to identity the host computed itself.

Two invariants drive the design:

1. **An unapproved supply chain can never pass.** `Stage2Policy.approved` gates execution, so
   BLK-003 is enforced in code rather than in prose. An unapproved policy does not even run the
   engine.
2. **Every failure is absent evidence, never a pass.** Every refusal path returns the
   `security-audit-skipped` finding, which `pipeline._write_scan` maps to status `not_run` — which
   `snapshot.py` then treats as `REQUIRED_STAGE_BLOCKED`. A broken, hostile, unapproved or merely
   unavailable scan therefore blocks publication instead of quietly scoring 1.000. That fail-open
   gap is exactly what retired the previous runner.

The engine is injected. The host never trusts the container to describe itself: identity comes from
the policy and from hashes the host recomputes, and any provenance-shaped key in the container's
report is refused upstream in `stage2_report`.
"""
from __future__ import annotations

import hashlib
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from semiskill.scanners.base import Finding, ScanStage, ScanResult, result_from
from semiskill.scanners.stage2_report import (
    REPORT_SCHEMA_VERSION,
    Stage2ReportRefused,
    validate_report,
)
from semiskill.scanners.stage2_staging import Stage2Refused, project_payload

SKIPPED_CODE = "security-audit-skipped"     # pipeline._write_scan maps this to a blocking not_run


@dataclass(frozen=True)
class Stage2Policy:
    """Host-bound, approval-gated supply-chain identity.

    None of these values may originate from the container. `approved` is the AppSec/legal promotion
    of one exact immutable chain — an image platform-manifest digest plus a rule pack — and not a
    tag or version label, which is the distinction ADR-024 exists to enforce.
    """

    image_manifest_digest: str
    rule_pack_path: Path
    rule_pack_sha256: str
    adapter_commit: str
    approved: bool = False          # default False: promotion is opt-in, never inherited


class Stage2Adapter:
    stage = ScanStage.SECURITY_AUDIT

    def __init__(self, *, engine: Callable[..., dict], policy: Stage2Policy):
        self._engine = engine
        self._policy = policy

    # The Scanner protocol only carries a ScanResult. The binding record is what an auditor needs,
    # so it is available explicitly rather than smuggled into a finding string.
    def scan(self, submission) -> ScanResult:
        return self.scan_with_binding(submission)[0]

    def scan_with_binding(self, submission) -> tuple[ScanResult, dict]:
        binding = {
            "slug": getattr(submission, "slug", ""),
            "image_manifest_digest": self._policy.image_manifest_digest,
            "rule_pack_sha256": self._policy.rule_pack_sha256,
            "adapter_commit": self._policy.adapter_commit,
            "report_schema_version": REPORT_SCHEMA_VERSION,
            "payload_sha256": _payload_sha256(submission),
            "analyzed_files": (),
            "isolated_files": (),
            "refused": False,
            "refusal": "",
        }

        refusal = self._preflight()
        if refusal:
            return _absent_evidence(refusal, binding)

        staged_root = Path(tempfile.mkdtemp(prefix="semiskill-stage2-"))
        try:
            try:
                staged = project_payload(submission, root=staged_root / "payload")
            except Stage2Refused as exc:
                return _absent_evidence(f"staging refused: {exc}", binding)

            binding["isolated_files"] = staged.isolated

            try:
                report = self._engine(
                    staged_root=staged.root,
                    expected_files=staged.expected_files,
                    policy=self._policy,
                )
            except Exception as exc:            # noqa: BLE001 - any engine failure is absent evidence
                return _absent_evidence(f"engine failed: {type(exc).__name__}: {exc}", binding)

            try:
                validated = validate_report(report, expected_files=staged.expected_files)
            except Stage2ReportRefused as exc:
                return _absent_evidence(f"report refused: {exc}", binding)

            binding["analyzed_files"] = validated.analyzed_files
            return result_from(self.stage, validated.findings), binding
        finally:
            shutil.rmtree(staged_root, ignore_errors=True)

    def _preflight(self) -> str:
        """Return why Stage 2 must not run, or an empty string if the chain is usable."""
        policy = self._policy
        if not policy.approved:
            return (
                "supply chain is not approved: AppSec/legal must promote the exact image manifest "
                "digest and rule pack before Stage 2 can produce credit (BLK-003)"
            )
        if not str(policy.image_manifest_digest).startswith("sha256:"):
            return f"image identity must be an exact digest, got {policy.image_manifest_digest!r}"
        try:
            actual = hashlib.sha256(Path(policy.rule_pack_path).read_bytes()).hexdigest()
        except OSError as exc:
            return f"rule_pack could not be read: {exc}"
        # Recomputed, never taken on trust: a policy that merely restates a hash proves nothing.
        declared = str(policy.rule_pack_sha256).removeprefix("sha256:")
        if actual != declared:
            return f"rule_pack hash mismatch: computed {actual}, policy declares {declared}"
        return ""


def _payload_sha256(submission) -> str:
    from semiskill.capture.intake import payload_fingerprint

    return payload_fingerprint({
        "slug": getattr(submission, "slug", ""),
        "name": getattr(submission, "name", ""),
        "body": getattr(submission, "body", ""),
        "files": dict(getattr(submission, "files", {}) or {}),
        "allowed_tools": list(getattr(submission, "allowed_tools", ()) or ()),
    })


def _absent_evidence(reason: str, binding: dict) -> tuple[ScanResult, dict]:
    """Stage 2 did not happen. Say so loudly; never let it look like a clean scan."""
    binding = {**binding, "refused": True, "refusal": reason}
    # Severity 0.0 keeps the aggregate score honest — the stage contributed no measurement — while
    # the code itself drives the blocking `not_run` status downstream.
    return result_from(ScanStage.SECURITY_AUDIT, [Finding(SKIPPED_CODE, 0.0, reason)]), binding
