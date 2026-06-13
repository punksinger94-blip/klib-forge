from __future__ import annotations

import re

from .models import TrustFinding

INJECTION_PATTERNS = (
    (
        "high",
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|forget)\b.{0,60}\b(previous|prior|system|developer)"
            r"\b.{0,40}\b(instruction|prompt|message)s?\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "Source attempts to override higher-priority instructions.",
    ),
    (
        "high",
        "secret_exfiltration",
        re.compile(
            r"\b(api[_ -]?key|password|secret|token|credential)s?\b.{0,60}"
            r"\b(print|send|reveal|return|upload|exfiltrate)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "Source requests disclosure or transfer of secrets.",
    ),
    (
        "medium",
        "role_impersonation",
        re.compile(r"\b(system|developer|assistant)\s*:\s*", re.IGNORECASE),
        "Source contains text that imitates a chat role.",
    ),
    (
        "medium",
        "tool_instruction",
        re.compile(
            r"\b(run|execute|open|download|install|delete)\b.{0,50}"
            r"\b(command|powershell|shell|terminal|file|url)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "Source contains executable or tool-oriented instructions.",
    ),
)


def scan_prompt_injection(text: str) -> list[TrustFinding]:
    findings: list[TrustFinding] = []
    for severity, category, pattern, message in INJECTION_PATTERNS:
        for match in pattern.finditer(text):
            excerpt = " ".join(match.group(0).split())[:240]
            findings.append(
                TrustFinding(
                    severity=severity,
                    category=category,
                    message=message,
                    excerpt=excerpt,
                )
            )
            if len(findings) >= 20:
                return findings
    return findings


def trust_risk_score(findings: list[TrustFinding]) -> int:
    weights = {"low": 5, "medium": 20, "high": 45}
    return min(sum(weights[finding.severity] for finding in findings), 100)
