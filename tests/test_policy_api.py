from __future__ import annotations

import numpy as np
import pandas as pd

import preflight


def test_run_returns_policy_report(clean_df):
    report = preflight.run(clean_df, target="churn", profile="exploratory")
    payload = report.to_dict()
    assert payload["schema_version"] == "2.0.0"
    assert payload["gate"]["status"] in {"PASS", "FAIL"}
    assert isinstance(payload["findings"], list)


def test_run_ci_strict_can_fail_on_target_risk():
    rng = np.random.default_rng(7)
    target = rng.integers(0, 2, 500)
    leak = target + rng.normal(0, 0.001, 500)
    df = pd.DataFrame({"target": target, "leak_col": leak, "noise": rng.normal(0, 1, 500)})
    report = preflight.run(df, target="target", profile="ci-strict")
    assert report.gate.status == "FAIL"


def test_run_split_returns_policy_report(clean_df):
    train = clean_df.iloc[:70]
    test = clean_df.iloc[70:]
    report = preflight.run_split(train, test, profile="exploratory")
    payload = report.to_dict()
    assert payload["schema_version"] == "2.0.0"
    assert payload["dataset"]["rows"] == len(train) + len(test)
