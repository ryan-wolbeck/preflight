from __future__ import annotations

from preflight import run


def test_policy_html_renderer_contains_gate(clean_df):
    report = run(clean_df, target="churn", profile="exploratory")
    html = report.to_html()
    assert "<html" in html.lower()
    assert "Preflight Run Report" in html
    assert "Gate" in html
