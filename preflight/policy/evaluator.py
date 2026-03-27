"""
Policy evaluator for findings -> severities, gate decision, and score.
"""

from __future__ import annotations

from dataclasses import replace

from preflight.model.finding import Finding, Severity
from preflight.model.policy import GateDecision, Policy, PolicyEvaluation
from preflight.policy.suppressions import Suppression
from preflight.policy.default_profiles import rule_applies, severity_order_for_gate


def evaluate(
    findings: list[Finding],
    policy: Policy,
    suppressions: list[Suppression] | None = None,
) -> PolicyEvaluation:
    resolved: list[Finding] = [apply_policy(finding, policy) for finding in findings]
    effective_suppressions = [s for s in (suppressions or []) if not s.is_expired()]
    resolved = [apply_suppressions(finding, effective_suppressions) for finding in resolved]
    unsuppressed = [finding for finding in resolved if not finding.suppressed]
    score = heuristic_score(unsuppressed, policy)
    gate = build_gate(unsuppressed, policy)
    return PolicyEvaluation(findings=resolved, gate=gate, score=score)


def apply_policy(finding: Finding, policy: Policy) -> Finding:
    resolved_severity = finding.severity
    for rule in policy.rules:
        if rule_applies(rule, finding):
            resolved_severity = max_severity(resolved_severity, rule.severity)
    return replace(finding, severity=resolved_severity)


def max_severity(a: Severity, b: Severity) -> Severity:
    order = {
        Severity.INFO: 0,
        Severity.WARN: 1,
        Severity.ERROR: 2,
        Severity.CRITICAL: 3,
    }
    return a if order[a] >= order[b] else b


def heuristic_score(findings: list[Finding], policy: Policy) -> float:
    penalty = sum(policy.score_weights.get(finding.severity, 0.0) for finding in findings)
    return max(0.0, min(100.0, 100.0 - penalty))


def build_gate(findings: list[Finding], policy: Policy) -> GateDecision:
    reasons: list[str] = []
    should_fail = False
    for severity in severity_order_for_gate():
        if severity not in policy.fail_on:
            continue
        count = sum(1 for finding in findings if finding.severity == severity)
        if count > 0:
            reasons.append(f"{count} {severity.value} finding(s) exceeded policy fail threshold")
            should_fail = True
    return GateDecision(status="FAIL" if should_fail else "PASS", reasons=reasons)


def apply_suppressions(finding: Finding, suppressions: list[Suppression]) -> Finding:
    for suppression in suppressions:
        if suppression.matches(finding):
            return replace(
                finding,
                suppressed=True,
                details={
                    **finding.details,
                    "suppression_reason": suppression.reason,
                    "suppression_expires": (
                        suppression.expires.isoformat() if suppression.expires else None
                    ),
                },
            )
    return finding
