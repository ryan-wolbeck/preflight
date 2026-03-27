"""Shared fixtures for the preflight test suite."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def clean_df() -> pd.DataFrame:
    """100-row DataFrame with no issues."""
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "age": rng.integers(18, 80, size=100).astype(float),
            "income": rng.normal(50_000, 15_000, size=100),
            "score": rng.uniform(0, 1, size=100),
            "churn": rng.integers(0, 2, size=100),
        }
    )


@pytest.fixture
def missing_df() -> pd.DataFrame:
    """DataFrame with controlled missing-value patterns."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "ok_col": rng.normal(0, 1, 100),  # 0 % missing
            "warn_col": rng.normal(0, 1, 100),  # ~25 % missing
            "fail_col": rng.normal(0, 1, 100),  # ~60 % missing
        }
    )
    warn_idx = rng.choice(100, size=25, replace=False)
    fail_idx = rng.choice(100, size=60, replace=False)
    df.loc[warn_idx, "warn_col"] = np.nan
    df.loc[fail_idx, "fail_col"] = np.nan
    return df
