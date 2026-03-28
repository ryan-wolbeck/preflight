from __future__ import annotations

import json

import pytest

from preflight.model.finding import Domain, Evidence, Finding, Severity
from preflight.policy.loader import load_policy_file


def test_load_policy_file_json(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "name": "custom",
                "fail_on": ["critical"],
                "score_weights": {"info": 0, "warn": 1, "error": 5, "critical": 10},
                "rules": [
                    {
                        "id": "critical-target-risk",
                        "severity": "critical",
                        "match": {"domain": "target_risk", "signal_strength_in": ["high"]},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    policy = load_policy_file(str(path))
    finding = Finding(
        check_id="x",
        title="x",
        domain=Domain.TARGET_RISK,
        signal_strength="high",
        evidence=Evidence(),
        severity=Severity.INFO,
    )
    assert policy.name == "custom"
    assert len(policy.rules) == 1
    assert policy.rules[0].when(finding) is True


def test_load_policy_file_requires_complete_score_weights(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "name": "custom",
                "fail_on": ["critical"],
                "score_weights": {"info": 0, "warn": 1},
                "rules": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="missing severity keys"):
        load_policy_file(str(path))


def test_load_policy_file_rejects_all_zero_score_weights(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps(
            {
                "name": "custom",
                "fail_on": ["critical"],
                "score_weights": {"info": 0, "warn": 0, "error": 0, "critical": 0},
                "rules": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="non-zero weight"):
        load_policy_file(str(path))
