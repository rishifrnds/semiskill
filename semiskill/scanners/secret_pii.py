"""Stage 4 — secret / PII scan (deterministic, 100% of submissions).

Detects embedded credentials, tokens, private keys, internal URLs/IPs, and PII in the untrusted
submission. A live-looking credential is a hard_fail (a published skill must never ship secrets).
"""
from __future__ import annotations
import re
from semiskill.scanners.base import ScanStage, Finding, ScanResult, SkillSubmission, result_from

# (code, pattern, severity). Severity >= 0.9 => hard_fail.
_PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), 0.95),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), 0.95),
    ("github-token", re.compile(r"\bghp_[A-Za-z0-9]{36}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b"), 0.95),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"), 0.95),
    ("credential-assignment",
     re.compile(r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|pwd)\b\s*[:=]\s*"
                r"['\"]?[A-Za-z0-9_\-]{16,}"), 0.9),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]+\.eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"), 0.7),
    ("internal-url", re.compile(r"https?://[A-Za-z0-9.\-]+\.(?:internal|corp|local|intranet)\b"), 0.5),
    ("private-ip",
     re.compile(r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))\.\d{1,3}\.\d{1,3}\b"), 0.4),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), 0.85),
    ("credit-card", re.compile(r"\b\d{4}[- ]\d{4}[- ]\d{4}[- ]\d{4}\b"), 0.6),
]


class SecretPiiScanner:
    stage = ScanStage.SECRET_PII

    def scan(self, s: SkillSubmission) -> ScanResult:
        blob = "\n".join(s.texts())
        findings = [Finding(code, sev, "detected in submission")
                    for code, rx, sev in _PATTERNS if rx.search(blob)]
        return result_from(self.stage, findings)
