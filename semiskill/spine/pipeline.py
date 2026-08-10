"""L4/L6 orchestrator — run a submitted skill through the deterministic scanners in order.

Scanner stages 1–5 are always represented by scan_run artifacts (or injection_test for stage 3)
carrying safety_score + hard_fail + findings. Available scanner adapters run; unavailable external
stages emit explicit not_run/not_sampled evidence. Stage 6 always appends the aggregate review so the
trail is complete. Any hard-fail forces that review to reject; otherwise the worst measured score
drives a suggest-only verdict (approve / request-changes / reject). A human must still sign off before
the publication actuator makes anything discoverable (ADR-011).

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
from semiskill.scanners.stage2_adapter import Stage2Adapter, Stage2Policy
from semiskill.scanners.stage2_engine import docker_semgrep_engine
from semiskill.scanners.judge_risk import JudgeRiskScanner
from semiskill.scanners.stage5_ollama import OllamaJudge, Stage5Policy

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


def _build_scanners(dsn: str, security_audit_runner=None, judge_risk_scanner=None,
                    stage2_policy: Stage2Policy | None = None):
    # ADR-024/ADR-030: Stage2Adapter is the accepted Stage-2 authority; the old npx-based
    # SecurityAuditScanner is retired (HANDOFF.md) but stays as the pre-ADR-024 fallback when no
    # stage2_policy is supplied, so existing callers that don't yet pass one keep today's
    # behavior exactly (both paths currently produce `not_run` either way, since Stage2Policy.
    # approved defaults to False pending BLK-003). Callers should migrate to stage2_policy.
    if stage2_policy is not None:
        stage2 = Stage2Adapter(engine=docker_semgrep_engine, policy=stage2_policy)
    else:
        stage2 = SecurityAuditScanner(security_audit_runner or _unconfigured_security_audit)
    scanners = [
        StaticStructureScanner(),
        stage2,
        InjectionProbeScanner(dsn),
        SecretPiiScanner(),
    ]
    if judge_risk_scanner is not None:
        scanners.append(judge_risk_scanner)
    return scanners


def _effective_judge_scanner(store, judge_risk_scanner, stage5_policy: Stage5Policy | None):
    """An explicit `judge_risk_scanner` always wins (tests inject a `FakeJudge` this way); a
    `stage5_policy` constructs the real `OllamaJudge`-backed scanner, mirroring `stage2_policy`'s
    host-decides-construction pattern rather than making every caller wire up `JudgeRiskScanner`
    (rubric, model-family bookkeeping, calibration params) by hand."""
    if judge_risk_scanner is not None:
        return judge_risk_scanner
    if stage5_policy is None:
        return None
    return JudgeRiskScanner(
        store=store, judge=OllamaJudge(stage5_policy),
        judge_model_family=f"ollama:{stage5_policy.model}",
    )


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
                 judge_required: bool = True,
                 stage2_policy: Stage2Policy | None = None,
                 stage5_policy: Stage5Policy | None = None) -> PipelineResult:
    sv = store.get(skill_version_id)
    if sv is None or sv.artifact_type is not ArtifactType.SKILL_VERSION:
        raise ValueError("skill_version not found")
    label = sv.permissions_label
    submission = SkillSubmission.from_payload(sv.payload)

    judge_risk_scanner = _effective_judge_scanner(store, judge_risk_scanner, stage5_policy)

    scans: list[Artifact] = []
    for scanner in _build_scanners(dsn, security_audit_runner, judge_risk_scanner, stage2_policy):
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
