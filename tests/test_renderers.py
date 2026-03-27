from __future__ import annotations

import json

from preflight import run
from preflight.renderers import render_json, render_markdown, render_text


def test_policy_renderers(clean_df):
    report = run(clean_df, target="churn", profile="exploratory")

    text = render_text(report)
    assert "Preflight Run Report" in text
    assert "Findings" in text

    md = render_markdown(report)
    assert "## Preflight Run Report" in md
    assert "| Severity | Check | Domain | Title |" in md

    js = render_json(report)
    payload = json.loads(js)
    assert payload["schema_version"] == "2.0.0"
