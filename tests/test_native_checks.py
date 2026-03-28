from __future__ import annotations

import numpy as np
import pandas as pd

import preflight


def test_run_includes_native_completeness_and_leakage():
    rng = np.random.default_rng(3)
    target = rng.integers(0, 2, 300)
    leak = target + rng.normal(0, 0.001, 300)
    df = pd.DataFrame(
        {
            "target": target,
            "leak_col": leak,
            "feature": rng.normal(0, 1, 300),
            "nullable": [None] * 40 + list(range(260)),
        }
    )
    report = preflight.run(df, target="target", profile="exploratory")
    ids = {finding.check_id for finding in report.findings}
    assert "completeness.missingness" in ids
    assert "leakage.high_correlation" in ids


def test_run_includes_native_duplicates_and_distributions():
    df = pd.DataFrame(
        {
            "a": [1, 1, 2, 3, 4, 4],
            "b": ["x", "x", "y", "z", "w", "w"],
            "target": [0, 0, 1, 1, 0, 0],
        }
    )
    report = preflight.run(df, target="target", profile="exploratory")
    ids = {finding.check_id for finding in report.findings}
    assert "duplicates.exact" in ids
    assert "distributions.health" in ids


def test_run_uses_native_balance_check_no_legacy_adapter_fields():
    df = pd.DataFrame(
        {
            "target": [0] * 91 + [1] * 9,
            "feature": list(range(100)),
        }
    )
    report = preflight.run(df, target="target", profile="exploratory")
    balance = next(
        finding for finding in report.findings if finding.check_id == "balance.class_imbalance"
    )
    assert balance.severity.value in {"warn", "error"}
    assert not (balance.details and "legacy_category" in balance.details)


def test_run_balance_single_class_target_is_flagged():
    df = pd.DataFrame({"target": [0] * 100, "feature": list(range(100))})
    report = preflight.run(df, target="target", profile="exploratory")
    finding = next(f for f in report.findings if f.check_id == "balance.single_class_target")
    assert finding.severity.value == "error"
