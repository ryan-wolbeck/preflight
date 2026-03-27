"""
Default policy profiles shipped with preflight.
"""

from __future__ import annotations

from preflight.model.finding import Domain, Finding, Severity
from preflight.model.policy import Policy, Rule


def exploratory() -> Policy:
    return Policy(
        name="exploratory",
        rules=[
            Rule(
                id="target-risk-high",
                when=lambda finding: finding.domain == Domain.TARGET_RISK
                and finding.signal_strength == "high",
                severity=Severity.ERROR,
                description="High target-risk findings are elevated in exploratory profile.",
            ),
        ],
        fail_on={Severity.CRITICAL},
    )


def ci_strict() -> Policy:
    return Policy(
        name="ci-strict",
        rules=[
            Rule(
                id="target-risk-blocker",
                when=lambda finding: finding.domain == Domain.TARGET_RISK
                and finding.signal_strength in {"medium", "high"},
                severity=Severity.CRITICAL,
                description="Any medium/high target-risk finding is a CI blocker.",
            ),
            Rule(
                id="split-integrity-error",
                when=lambda finding: finding.domain == Domain.SPLIT_INTEGRITY
                and finding.signal_strength == "high",
                severity=Severity.ERROR,
                description="High split-integrity findings block strict CI.",
            ),
            Rule(
                id="schema-contract-error",
                when=lambda finding: finding.domain == Domain.SCHEMA_CONTRACT
                and finding.signal_strength == "high",
                severity=Severity.ERROR,
                description="Schema contract high-risk issues block strict CI.",
            ),
        ],
        fail_on={Severity.ERROR, Severity.CRITICAL},
    )


def with_fail_on(policy: Policy, fail_on: set[Severity]) -> Policy:
    return Policy(
        name=policy.name,
        rules=policy.rules,
        fail_on=fail_on,
        score_weights=policy.score_weights,
    )


def parse_fail_on(value: str | None, default: set[Severity]) -> set[Severity]:
    if value is None:
        return default
    tokens = [token.strip().lower() for token in value.split(",") if token.strip()]
    allowed = {severity.value: severity for severity in Severity}
    parsed: set[Severity] = set()
    for token in tokens:
        if token not in allowed:
            raise ValueError(f"Unsupported severity in --fail-on: {token!r}")
        parsed.add(allowed[token])
    return parsed


def severity_order_for_gate() -> list[Severity]:
    return [Severity.CRITICAL, Severity.ERROR, Severity.WARN, Severity.INFO]


def choose_profile(profile_name: str) -> Policy:
    if profile_name == "exploratory":
        return exploratory()
    if profile_name == "ci-strict":
        return ci_strict()
    raise ValueError(f"Unknown profile: {profile_name}")


def rule_applies(rule: Rule, finding: Finding) -> bool:
    return bool(rule.when(finding))
