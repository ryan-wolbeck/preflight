from __future__ import annotations

from preflight.compare import compare_reports


def test_compare_fails_on_large_score_drop():
    baseline = {
        "score": {"value": 90.0},
        "summary": {"severity_counts": {"critical": 0}},
    }
    current = {
        "score": {"value": 70.0},
        "summary": {"severity_counts": {"critical": 0}},
    }
    result = compare_reports(current, baseline, max_score_drop=5.0)
    assert result.status == "FAIL"
    assert any("score dropped" in reason.lower() for reason in result.reasons)


def test_compare_fails_on_new_critical():
    baseline = {"score": {"value": 88.0}, "summary": {"severity_counts": {"critical": 0}}}
    current = {"score": {"value": 88.0}, "summary": {"severity_counts": {"critical": 2}}}
    result = compare_reports(current, baseline, max_score_drop=20.0, fail_on_new_critical=True)
    assert result.status == "FAIL"
    assert any("new critical" in reason.lower() for reason in result.reasons)


def test_compare_fails_on_new_error_when_enabled():
    baseline = {"summary": {"severity_counts": {"error": 0, "critical": 0}}}
    current = {"summary": {"severity_counts": {"error": 2, "critical": 0}}}
    result = compare_reports(current, baseline, fail_on_new_critical=False, fail_on_new_error=True)
    assert result.status == "FAIL"
    assert any("new error" in reason.lower() for reason in result.reasons)


def test_compare_domain_increase_threshold():
    baseline = {
        "summary": {"domain_counts": {"target_risk": 1}, "severity_counts": {"critical": 0}}
    }
    current = {"summary": {"domain_counts": {"target_risk": 4}, "severity_counts": {"critical": 0}}}
    result = compare_reports(
        current,
        baseline,
        fail_on_new_critical=False,
        domain_increase_thresholds={"target_risk": 2},
    )
    assert result.status == "FAIL"
    assert any("domain 'target_risk'" in reason.lower() for reason in result.reasons)
