from __future__ import annotations

import numpy as np
import pandas as pd

import preflight
from preflight.model.finding import Domain, Finding, Severity
from preflight.model.policy import Rule
from preflight.policy.default_profiles import (
    choose_profile,
    parse_fail_on,
    rule_applies,
    severity_order_for_gate,
)


def test_choose_profile_ci_balanced_available():
    policy = choose_profile("ci-balanced")
    assert policy.name == "ci-balanced"
    assert Severity.ERROR in policy.fail_on


def test_ci_balanced_fails_on_medium_target_risk():
    rng = np.random.default_rng(7)
    target = rng.integers(0, 2, 500)
    leak = target + rng.normal(0, 0.01, 500)
    df = pd.DataFrame({"target": target, "leak_col": leak, "noise": rng.normal(0, 1, 500)})
    report = preflight.run(df, target="target", profile="ci-balanced")
    assert report.gate.status == "FAIL"


def test_default_profile_helpers():
    parsed = parse_fail_on("warn,error", default={Severity.CRITICAL})
    assert parsed == {Severity.WARN, Severity.ERROR}
    ordered = severity_order_for_gate()
    assert ordered == [Severity.CRITICAL, Severity.ERROR, Severity.WARN, Severity.INFO]


def test_rule_applies_helper():
    rule = Rule(
        id="target-risk-test",
        when=lambda finding: finding.domain == Domain.TARGET_RISK,
        severity=Severity.ERROR,
    )
    finding = Finding(
        check_id="x",
        title="t",
        domain=Domain.TARGET_RISK,
    )
    assert rule_applies(rule, finding) is True
