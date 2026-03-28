from __future__ import annotations

import json

import pytest

from preflight.cli import (
    _add_suppression,
    _list_suppressions,
    _parse_domain_thresholds,
    _plugins_doctor,
    _validate_suppressions,
)


def test_add_suppression_creates_and_appends(tmp_path):
    path = tmp_path / "suppressions.json"
    rc = _add_suppression(
        file_path=str(path),
        check_id="leakage.high_correlation",
        column="signup_date",
        expires="2099-01-01",
        reason="known safe due to feature exclusion",
    )
    assert rc == 0
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert data[0]["check_id"] == "leakage.high_correlation"
    assert data[0]["column"] == "signup_date"
    assert data[0]["expires"] == "2099-01-01"


def test_list_and_validate_suppressions(tmp_path):
    path = tmp_path / "suppressions.json"
    path.write_text(
        json.dumps(
            [
                {
                    "check_id": "leakage.high_correlation",
                    "reason": "ok",
                    "expires": "2099-01-01",
                }
            ]
        ),
        encoding="utf-8",
    )
    assert _list_suppressions(str(path), output_format="json") == 0
    assert _validate_suppressions(str(path), output_format="json", fail_on_expired=True) == 0


def test_parse_domain_thresholds():
    out = _parse_domain_thresholds(["target_risk=2", "data_quality=5"])
    assert out["target_risk"] == 2
    assert out["data_quality"] == 5


def test_parse_domain_thresholds_invalid_input():
    with pytest.raises(ValueError):
        _parse_domain_thresholds(["bad-value"])
    with pytest.raises(ValueError):
        _parse_domain_thresholds(["target_risk=2=extra"])
    with pytest.raises(ValueError):
        _parse_domain_thresholds(["target_risk=-1"])


def test_plugins_doctor_pass(monkeypatch):
    monkeypatch.setattr("preflight.cli.discover_entrypoint_plugins", lambda: [])
    assert _plugins_doctor(output_format="json") == 0
