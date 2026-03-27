from __future__ import annotations

import numpy as np
import pandas as pd

import preflight


def test_run_split_native_returns_split_findings():
    train = pd.DataFrame(
        {
            "x": np.linspace(0.0, 1.0, 500),
            "cat": ["a"] * 500,
        }
    )
    test = pd.DataFrame(
        {
            "x": np.linspace(10.0, 20.0, 500),
            "cat": ["b"] * 500,
        }
    )
    report = preflight.run_split(train, test, profile="ci-strict")
    check_ids = {finding.check_id for finding in report.findings}
    assert "split.numeric_psi" in check_ids
    assert "split.categorical_tvd" in check_ids
