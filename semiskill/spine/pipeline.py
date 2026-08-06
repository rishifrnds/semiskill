"""L4/L6 orchestrator — run a submitted skill through the deterministic scanners in order.

Each stage appends a scan_run (or, for the injection stage, an injection_test) artifact carrying its
safety_score + hard_fail + findings. A hard-fail short-circuits: no later stage runs, no aggregate
review is written, and the skill can never advance to publish. Otherwise the worst-stage safety score
drives a suggest-only aggregate `review` verdict (approve / request-changes / reject) — which a human
must still sign off before the publish actuator makes anything discoverable (ADR-002).

v1 wires the deterministic stages (static structure, injection corpus, secret/PII). Stage 2
(security-audit) and stage 5 (LLM judge) are added later and slot into `_build_scanners`.
"""
from __future__ import annotations
from dataclasses import dataclass, field, replace
from semiskill.artifacts.schema import Artifact, ArtifactType, SourceSystem, ActorKind
from semiskill.artifacts.store import ArtifactStore
from semiskill.scanners.base import ScanStage, ScanResult, SkillSubmission
from semiskill.scanners.static_structure import StaticStructureScanner
from semiskill.scanners.injection_probe import InjectionProbeScanner
from semiskill.scanners.secret_pii import SecretPiiScanner
from semiskill.scanners.security_audit import SecurityAuditScanner

APPROVE_THRESHOLD = 0.8
REJECT_THRESHOLD = 0.5


@dataclass(frozen=True)
class PipelineResult:
    skill_version_id: object
    scan_artifacts: list[Artifact] = field(default_factory=list)
    review: Artifact | None = None
    verdict: str = "reject"                 # approve | request-changes | reject
    blocked_at: ScanStage | None = None


def _build_scanners(dsn: str, security_audit_runner=None):
    # Stage 2 (security-audit) is opt-in: it needs the egress sandbox + local security CLI, so the
    # default pipeline is deterministic-only (stages 1/3/4). Pass a runner to enable stage 2 in order.
    scanners = [StaticStructureScanner()]
    if security_audit_runner is not None:
        scanners.append(SecurityAuditScanner(security_audit_runner))
    scanners += [InjectionProbeScanner(dsn), SecretPiiScanner()]
    return scanners


def _scan_type(stage: ScanStage) -> ArtifactType:
    return ArtifactType.INJECTION_TEST if stage == ScanStage.INJECTION else ArtifactType.SCAN_RUN


def _write_scan(store: ArtifactStore, sv: Artifact, r: ScanResult, label: str) -> Artifact:
    art = Artifact.new(
        artifact_type=_scan_type(r.stage), source_system=SourceSystem.CLI,
        actor="pipeline", actor_kind=ActorKind.SERVICE_ACCOUNT, input_refs=[sv.artifact_id],
        payload={"stage": int(r.stage), "safety_score": r.safety_score, "hard_fail": r.hard_fail,
                 "findings": [{"code": f.code, "severity": f.severity} for f in r.findings]})
    art = replace(art, permissions_label=label).with_eval_score(r.safety_score)
    return store.append(art)


def _write_review(store: ArtifactStore, sv: Artifact, scans: list[Artifact], verdict: str,
                  aggregate: float, label: str) -> Artifact:
    art = Artifact.new(
        artifact_type=ArtifactType.REVIEW, source_system=SourceSystem.CLI,
        actor="l5-controller", actor_kind=ActorKind.AGENT,
        input_refs=[sv.artifact_id, *[a.artifact_id for a in scans]],
        payload={"review_kind": "security_aggregate", "schema_version": 1,
                 "verdict": verdict, "aggregate_safety": aggregate})
    art = replace(art, permissions_label=label).with_eval_score(aggregate)
    return store.append(art)


def run_pipeline(*, store: ArtifactStore, dsn: str, skill_version_id,
                 security_audit_runner=None) -> PipelineResult:
    sv = store.get(skill_version_id)
    if sv is None or sv.artifact_type is not ArtifactType.SKILL_VERSION:
        raise ValueError("skill_version not found")
    label = sv.permissions_label
    submission = SkillSubmission.from_payload(sv.payload)

    scans: list[Artifact] = []
    for scanner in _build_scanners(dsn, security_audit_runner):
        result = scanner.scan(submission)
        scans.append(_write_scan(store, sv, result, label))
        if result.hard_fail:
            return PipelineResult(skill_version_id=skill_version_id, scan_artifacts=scans,
                                  review=None, verdict="reject", blocked_at=result.stage)

    aggregate = min((a.eval_score for a in scans), default=1.0)
    verdict = ("approve" if aggregate >= APPROVE_THRESHOLD
               else "reject" if aggregate < REJECT_THRESHOLD
               else "request-changes")
    review = _write_review(store, sv, scans, verdict, aggregate, label)
    return PipelineResult(skill_version_id=skill_version_id, scan_artifacts=scans,
                          review=review, verdict=verdict, blocked_at=None)
