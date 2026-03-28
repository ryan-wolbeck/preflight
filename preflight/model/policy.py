"""
Policy models for mapping findings to severities and gate outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
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

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("policy.name must not be empty")
        if not self.fail_on:
            raise ValueError("policy.fail_on must include at least one severity")

        rule_ids: set[str] = set()
        for rule in self.rules:
            if not rule.id.strip():
                raise ValueError("policy rule id must not be empty")
            if rule.id in rule_ids:
                raise ValueError(f"duplicate policy rule id: {rule.id!r}")
            rule_ids.add(rule.id)

        missing = [severity for severity in Severity if severity not in self.score_weights]
        if missing:
            values = ", ".join(severity.value for severity in missing)
            raise ValueError(f"policy.score_weights missing severity keys: {values}")
        for severity, weight in self.score_weights.items():
            if not math.isfinite(weight):
                raise ValueError(f"policy.score_weights[{severity.value!r}] must be finite")
            if weight < 0:
                raise ValueError(f"policy.score_weights[{severity.value!r}] must be >= 0")
        if all(weight == 0.0 for weight in self.score_weights.values()):
            raise ValueError("policy.score_weights must include at least one non-zero weight")


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
