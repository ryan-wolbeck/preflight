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


def test_schema_validator_flags_invalid_nested_values(clean_df):
    payload = preflight.run(clean_df, target="churn", profile="exploratory").to_dict()
    payload["gate"]["status"] = "UNKNOWN"
    payload["gate"]["reasons"] = ["", "ok"]
    payload["score"]["value"] = float("inf")
    payload["run"] = "bad"
    payload["dataset"] = "bad"
    payload["summary"] = "bad"
    payload["findings"][0]["severity"] = "not-a-severity"
    payload["findings"][0]["domain"] = "not-a-domain"
    payload["findings"][0]["signal_strength"] = "extreme"
    payload["findings"][0]["evidence"]["metrics"] = []
    errors = validate_run_report_payload(payload)
    assert any("gate.status" in err for err in errors)
    assert any("gate.reasons entries" in err for err in errors)
    assert any("score.value" in err for err in errors)
    assert any("'run' must be an object" in err for err in errors)
    assert any("'dataset' must be an object" in err for err in errors)
    assert any("'summary' must be an object" in err for err in errors)
    assert any(".severity" in err for err in errors)
    assert any(".domain" in err for err in errors)
    assert any(".signal_strength" in err for err in errors)
    assert any(".evidence.metrics" in err for err in errors)
