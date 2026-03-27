"""
Policy models for mapping findings to severities and gate outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable

from preflight.model.finding import Finding, Severity

FindingPredicate = Callable[[Finding], bool]


@dataclass(frozen=True)
class Rule:
    id: str
    when: FindingPredicate
    severity: Severity
    description: str = ""


@dataclass(frozen=True)
class Policy:
    name: str
    rules: list[Rule] = field(default_factory=list)
    fail_on: set[Severity] = field(default_factory=lambda: {Severity.ERROR, Severity.CRITICAL})
    score_weights: dict[Severity, float] = field(
        default_factory=lambda: {
            Severity.INFO: 0.0,
            Severity.WARN: 2.0,
            Severity.ERROR: 6.0,
            Severity.CRITICAL: 12.0,
        }
    )


@dataclass(frozen=True)
class GateDecision:
    status: str
    reasons: list[str]


@dataclass(frozen=True)
class PolicyEvaluation:
    findings: list[Finding]
    gate: GateDecision
    score: float

    @staticmethod
    def severity_counts(findings: Iterable[Finding]) -> dict[str, int]:
        counts = {s.value: 0 for s in Severity}
        for finding in findings:
            counts[finding.severity.value] += 1
        return counts
