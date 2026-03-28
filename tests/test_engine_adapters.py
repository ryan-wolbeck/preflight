from __future__ import annotations

from preflight._types import CheckResult, Severity as LegacySeverity
from preflight.engine.adapters import (
    _extract_affected_columns,
    _recommendations_for,
    domain_from_category,
    finding_from_check_result,
)
from preflight.model.finding import Domain, Severity


def test_extract_affected_columns_variants():
    assert _extract_affected_columns({"columns": {"a": 1, "b": 2}}) == ["a", "b"]
    assert _extract_affected_columns({"columns": [{"column": "x"}, "y"]}) == ["x", "y"]
    assert _extract_affected_columns({"columns": ("c1", "c2")}) == ["c1", "c2"]
    assert sorted(_extract_affected_columns({"columns": {"s1", "s2"}})) == ["s1", "s2"]
    assert _extract_affected_columns({}) == []


def test_finding_from_check_result_includes_explainability_fields():
    result = CheckResult(
        check_id="leakage.high_correlation",
        category="Leakage Detection",
        severity=LegacySeverity.WARN,
        message="Potential leakage",
        details={"columns": {"leak": 0.97}},
        penalty=5.0,
    )
    finding = finding_from_check_result(result)
    assert finding.domain == Domain.TARGET_RISK
    assert finding.severity == Severity.WARN
    payload = finding.to_dict()
    assert payload["suggested_action"] is not None
    assert payload["docs_url"] is not None


def test_domain_and_recommendation_defaults():
    assert domain_from_category("unknown-category") == Domain.ADVISORY
    result = CheckResult(
        check_id="custom.check",
        category="Custom",
        severity=LegacySeverity.PASS,
        message="ok",
    )
    recs = _recommendations_for(result)
    assert len(recs) == 1
