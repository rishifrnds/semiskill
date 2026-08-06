"""L4/L6 orchestrator — run a submitted skill through the deterministic scanners in order.

Each stage appends a scan_run (or, for the injection stage, an injection_test) artifact carrying its
safety_score + hard_fail + findings. A hard-fail short-circuits: no later stage runs, no aggregate
review is written, and the skill can never advance to publish. Otherwise the worst-stage safety score
drives a suggest-only aggregate `review` verdict (approve / request-changes / reject) — which a human
must still sign off before the publish actuator makes anything discoverable (ADR-002).

Stages 1/2/3/4 are always represented. Stage 5 is either a supplied calibrated judge result or an
explicit ``not_sampled`` artifact; a skipped judge is never rendered as a pass. Stage 6 is the
aggregate review and is emitted even for a deterministic hard failure, preserving a complete trail.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore
from semiskill.scanners.base import ScanStage, Finding, ScanResult, SkillSubmission
from semiskill.scanners.static_structure import StaticStructureScanner
from semiskill.scanners.injection_probe import InjectionProbeScanner
from semiskill.scanners.secret_pii import SecretPiiScanner
from semiskill.scanners.security_audit import SecurityAuditScanner, ToolUnavailable

APPROVE_THRESHOLD = 0.8
REJECT_THRESHOLD = 0.5


@dataclass(frozen=True)
class PipelineResult:
    skill_version_id: object
    scan_artifacts: list[Artifact] = field(default_factory=list)
    review: Artifact | None = None
    verdict: str = "reject"                 # approve | request-changes | reject
    blocked_at: ScanStage | None = None


def _unconfigured_security_audit(_submission):
    # Never let a routine pipeline call `npx` (which can fetch from the network). Production injects
    # a pinned, egress-sandboxed adapter; without it stage 2 is explicit `not_run` evidence.
    raise ToolUnavailable("security-audit adapter is not configured")


def _build_scanners(dsn: str, security_audit_runner=None, judge_risk_scanner=None):
    scanners = [
        StaticStructureScanner(),
        SecurityAuditScanner(security_audit_runner or _unconfigured_security_audit),
        InjectionProbeScanner(dsn),
        SecretPiiScanner(),
    ]
    if judge_risk_scanner is not None:
        scanners.append(judge_risk_scanner)
    return scanners


def _scan_type(stage: ScanStage) -> ArtifactType:
    return ArtifactType.INJECTION_TEST if stage == ScanStage.INJECTION else ArtifactType.SCAN_RUN


def _write_scan(store: ArtifactStore, sv: Artifact, r: ScanResult, label: str) -> Artifact:
    codes = {finding.code for finding in r.findings}
    if "security-audit-skipped" in codes:
        status = "not_run"
    elif "judge-not-sampled" in codes or "judge-skipped" in codes:
        status = "not_sampled"
    else:
        status = "failed" if r.hard_fail else "passed"
    art = Artifact.new(
        artifact_type=_scan_type(r.stage), source_system=SourceSystem.CLI,
        actor="pipeline", actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=[sv.artifact_id],
        payload={"stage": int(r.stage), "status": status,
                 "sampled": status not in {"not_run", "not_sampled"},
                 "safety_score": r.safety_score, "hard_fail": r.hard_fail,
                 "findings": [{"code": f.code, "severity": f.severity,
                               "detail": f.detail} for f in r.findings]})
    art = replace(art, permissions_label=label).with_eval_score(r.safety_score)
    return store.append(art)


def _write_review(store: ArtifactStore, sv: Artifact, scans: list[Artifact], verdict: str,
                  aggregate: float, label: str, judge_required: bool) -> Artifact:
    art = Artifact.new(
        artifact_type=ArtifactType.REVIEW, source_system=SourceSystem.CLI,
        actor="l5-controller", actor_kind=ActorKind.AGENT,
        input_refs=[sv.artifact_id, *[a.artifact_id for a in scans]],
        payload={"review_kind": "security_aggregate", "schema_version": 1, "stage": 6,
                 "verdict": verdict, "aggregate_safety": aggregate,
                 "judge_required": judge_required,
                 "scan_artifact_ids": [str(a.artifact_id) for a in scans]})
    art = replace(art, permissions_label=label).with_eval_score(aggregate)
    return store.append(art)


def run_pipeline(*, store: ArtifactStore, dsn: str, skill_version_id,
                 security_audit_runner=None, judge_risk_scanner=None,
                 judge_required: bool = True) -> PipelineResult:
    sv = store.get(skill_version_id)
    if sv is None or sv.artifact_type is not ArtifactType.SKILL_VERSION:
        raise ValueError("skill_version not found")
    label = sv.permissions_label
    submission = SkillSubmission.from_payload(sv.payload)

    scans: list[Artifact] = []
    for scanner in _build_scanners(dsn, security_audit_runner, judge_risk_scanner):
        result = scanner.scan(submission)
        scans.append(_write_scan(store, sv, result, label))

    if judge_risk_scanner is None:
        not_sampled = ScanResult(
            stage=ScanStage.JUDGE_RISK,
            safety_score=1.0,
            findings=(Finding("judge-not-sampled", 0.0, "no calibrated judge selected"),),
        )
        scans.append(_write_scan(store, sv, not_sampled, label))

    measured = [
        artifact.eval_score for artifact in scans
        if artifact.payload.get("status") not in {"not_run", "not_sampled"}
    ]
    aggregate = min(measured, default=1.0)
    hard_failed = [artifact for artifact in scans if artifact.payload.get("hard_fail")]
    verdict = (
        "reject" if hard_failed else
        "approve" if aggregate >= APPROVE_THRESHOLD else
        "reject" if aggregate < REJECT_THRESHOLD else
        "request-changes"
    )
    review = _write_review(store, sv, scans, verdict, aggregate, label, judge_required)
    return PipelineResult(skill_version_id=skill_version_id, scan_artifacts=scans,
                          review=review, verdict=verdict,
                          blocked_at=(ScanStage(hard_failed[0].payload["stage"])
                                      if hard_failed else None))
