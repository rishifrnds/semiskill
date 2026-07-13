"""Stage 1 — static structure scan (deterministic, 100% of submissions).

Parses the untrusted submission's declared tools + file tree and flags structural red flags:
dangerous/unlisted tools, executable & binary payloads, shell scripts, dynamic-exec / obfuscation,
outbound network references, and oversized blobs. Never executes anything — pure pattern analysis.
"""
from __future__ import annotations
import re
from semiskill.scanners.base import ScanStage, Finding, ScanResult, SkillSubmission, result_from
from semiskill.governance.policy import tool_risk

_EXEC_BINARY_EXT = (".exe", ".dll", ".so", ".dylib", ".bin", ".o", ".a", ".msi")
_SHELL_EXT = (".sh", ".bash", ".bat", ".cmd", ".ps1", ".psm1")
_DYNAMIC_EXEC = re.compile(
    r"\beval\s*\(|\bexec\s*\(|\bos\.system\s*\(|\bsubprocess\.|__import__\s*\(|"
    r"\batob\s*\(|base64\.b64decode|String\.fromCharCode|\bFunction\s*\(",
    re.IGNORECASE)
_NETWORK = re.compile(
    r"https?://|\bcurl\s|\bwget\s|\brequests\.(get|post)|\burllib|\bfetch\s*\(|\bsocket\.|\bnc\s+-",
    re.IGNORECASE)
_B64_BLOB = re.compile(r"[A-Za-z0-9+/]{200,}={0,2}")
_BINARY_PLACEHOLDER = re.compile(r"^<binary:\d+bytes>$")
_OVERSIZE = 50_000


class StaticStructureScanner:
    stage = ScanStage.STATIC_STRUCTURE

    def scan(self, s: SkillSubmission) -> ScanResult:
        findings: list[Finding] = []

        for t in s.allowed_tools:
            risk = tool_risk(t)
            if risk >= 0.9:
                findings.append(Finding("dangerous-tool", risk, f"skill declares tool {t!r}"))
            elif risk > 0:
                findings.append(Finding("unlisted-tool", risk, f"skill declares tool {t!r}"))

        for rel, content in s.files.items():
            low = rel.lower()
            if low.endswith(_EXEC_BINARY_EXT):
                findings.append(Finding("binary-executable", 0.95, rel))
            elif _BINARY_PLACEHOLDER.match(content.strip()):
                findings.append(Finding("binary-blob", 0.6, rel))
            elif low.endswith(_SHELL_EXT) or content.lstrip().startswith("#!"):
                findings.append(Finding("shell-script", 0.6, rel))

        for text in s.texts():
            if _DYNAMIC_EXEC.search(text):
                findings.append(Finding("dynamic-exec", 0.85, "eval/exec/subprocess/base64-decode pattern"))
            if _B64_BLOB.search(text):
                findings.append(Finding("obfuscated-blob", 0.6, "long base64 blob"))
            if _NETWORK.search(text):
                findings.append(Finding("network-call", 0.3, "outbound network reference"))
            if len(text) > _OVERSIZE:
                findings.append(Finding("oversized", 0.2, f"{len(text)} chars"))

        return result_from(self.stage, findings)
