from __future__ import annotations

import preflight
from preflight.schema import validate_run_report_payload


def test_run_report_payload_matches_schema_contract(clean_df):
    report = preflight.run(clean_df, target="churn", profile="exploratory")
    payload = report.to_dict()
    errors = validate_run_report_payload(payload)
    assert errors == []


def test_schema_validator_flags_missing_fields(clean_df):
    payload = preflight.run(clean_df, target="churn", profile="exploratory").to_dict()
    first_finding = payload["findings"][0]
    first_finding.pop("evidence")
    first_finding.pop("suggested_action")
    errors = validate_run_report_payload(payload)
    assert any("findings[0] missing keys" in err for err in errors)
