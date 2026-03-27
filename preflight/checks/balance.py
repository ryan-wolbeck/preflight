"""
Class Balance checks
====================
- Majority/minority class ratio for categorical targets
- Flags if any class ratio exceeds 90/10
- Skips gracefully for continuous (regression) targets
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from preflight.config import BalanceConfig
from preflight._types import CheckResult


def run(
    df: pd.DataFrame, target: Optional[str] = None, config: BalanceConfig | None = None
) -> list[CheckResult]:
    cfg = config or BalanceConfig()
    results: list[CheckResult] = []

    if target is None:
        results.append(
            CheckResult.passed(
                "balance.no_target",
                "Class Balance",
                "No target column specified — class balance check skipped.",
                confidence=1.0,
            )
        )
        return results

    if target not in df.columns:
        results.append(
            CheckResult.warn(
                "balance.missing_target",
                "Class Balance",
                f"Target column `{target}` not found in DataFrame.",
                confidence=1.0,
                penalty=5.0,
            )
        )
        return results

    series = df[target].dropna()
    if len(series) == 0:
        results.append(
            CheckResult.warn(
                "balance.empty_target",
                "Class Balance",
                f"Target column `{target}` contains only missing values.",
                confidence=1.0,
                penalty=10.0,
            )
        )
        return results

    n_unique = series.nunique()

    # Determine if this looks like a classification target
    is_numeric_continuous = (
        pd.api.types.is_numeric_dtype(series) and n_unique > cfg.categorical_threshold
    )

    if is_numeric_continuous:
        results.append(
            CheckResult.passed(
                "balance.continuous_target",
                "Class Balance",
                f"Target `{target}` appears continuous ({n_unique} unique values) — "
                "class balance check not applicable.",
                confidence=0.95,
            )
        )
        return results

    # ── Categorical target: compute class distribution ───────────────────────
    counts = series.value_counts()
    total = len(series)
    majority_count = int(counts.iloc[0])
    minority_count = int(counts.iloc[-1])
    majority_class = counts.index[0]
    minority_class = counts.index[-1]

    majority_pct = majority_count / total
    minority_pct = minority_count / total
    ratio = majority_count / minority_count if minority_count > 0 else float("inf")

    distribution = {str(k): round(v / total, 4) for k, v in counts.items()}

    if ratio >= cfg.fail_ratio:
        results.append(
            CheckResult.fail(
                "balance.imbalanced",
                "Class Balance",
                (
                    f"Severe class imbalance: {majority_pct:.0%}/{minority_pct:.0%} split "
                    f"(`{majority_class}` vs `{minority_class}`). "
                    "Consider resampling, class weights, or stratified splitting."
                ),
                details={
                    "majority_class": str(majority_class),
                    "minority_class": str(minority_class),
                    "ratio": round(ratio, 2),
                    "distribution": distribution,
                },
                confidence=min(1.0, 0.65 + min(1.0, ratio / 20.0)),
                penalty=cfg.fail_penalty,
            )
        )
    elif ratio >= cfg.warn_ratio:
        results.append(
            CheckResult.warn(
                "balance.imbalanced",
                "Class Balance",
                (
                    f"Moderate class imbalance: {majority_pct:.0%}/{minority_pct:.0%} split "
                    f"(`{majority_class}` vs `{minority_class}`)."
                ),
                details={
                    "majority_class": str(majority_class),
                    "minority_class": str(minority_class),
                    "ratio": round(ratio, 2),
                    "distribution": distribution,
                },
                confidence=min(0.9, 0.5 + min(1.0, ratio / 20.0)),
                penalty=cfg.warn_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "balance.balanced",
                "Class Balance",
                f"Class distribution is acceptably balanced (ratio {ratio:.1f}:1).",
                details={"ratio": round(ratio, 2), "distribution": distribution},
                confidence=0.9,
            )
        )

    return results
