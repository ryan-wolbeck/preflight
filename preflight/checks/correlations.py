"""
Feature Correlation checks
===========================
- Flag pairs of numeric features with absolute Pearson correlation > 0.95
  (likely redundant features that may harm some models)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from preflight.config import CorrelationsConfig
from preflight._types import CheckResult


def run(
    df: pd.DataFrame, target: Optional[str] = None, config: CorrelationsConfig | None = None
) -> list[CheckResult]:
    cfg = config or CorrelationsConfig()
    results: list[CheckResult] = []

    feature_cols = [c for c in df.columns if c != target]
    numeric_df = df[feature_cols].select_dtypes(include=[np.number])

    if numeric_df.shape[1] < 2:
        results.append(
            CheckResult.passed(
                "correlations.feature_pairs",
                "Feature Correlation",
                "Fewer than 2 numeric feature columns — correlation check skipped.",
                confidence=1.0,
            )
        )
        return results

    try:
        corr_matrix = numeric_df.corr(method="pearson").abs()
    except Exception as exc:
        results.append(
            CheckResult.warn(
                "correlations.feature_pairs",
                "Feature Correlation",
                f"Correlation matrix computation failed: {exc}",
                confidence=0.2,
                penalty=0.0,
            )
        )
        return results

    fail_pairs: list[dict] = []
    warn_pairs: list[dict] = []

    cols = list(corr_matrix.columns)
    for i, col_a in enumerate(cols):
        for col_b in cols[i + 1 :]:
            val = corr_matrix.loc[col_a, col_b]
            if np.isnan(val):
                continue
            if val >= cfg.fail_threshold:
                fail_pairs.append(
                    {"col_a": col_a, "col_b": col_b, "correlation": round(float(val), 4)}
                )
            elif val >= cfg.warn_threshold:
                warn_pairs.append(
                    {"col_a": col_a, "col_b": col_b, "correlation": round(float(val), 4)}
                )

    if fail_pairs:
        pair_strs = ", ".join(
            f"`{p['col_a']}`↔`{p['col_b']}` ({p['correlation']:.2f})"
            for p in fail_pairs[: cfg.max_pairs_in_message]
        )
        suffix = (
            f" (+{len(fail_pairs)-cfg.max_pairs_in_message} more)"
            if len(fail_pairs) > cfg.max_pairs_in_message
            else ""
        )
        results.append(
            CheckResult.fail(
                "correlations.feature_pairs",
                "Feature Correlation",
                f"{len(fail_pairs)} highly correlated feature pair(s) (r≥{cfg.fail_threshold:.2f}): "
                f"{pair_strs}{suffix}.",
                details={"pairs": fail_pairs},
                confidence=min(1.0, 0.7 + min(0.3, len(fail_pairs) / 20.0)),
                penalty=cfg.fail_penalty_per_pair * min(len(fail_pairs), cfg.fail_penalty_pair_cap),
            )
        )
    elif warn_pairs:
        pair_strs = ", ".join(
            f"`{p['col_a']}`↔`{p['col_b']}` ({p['correlation']:.2f})"
            for p in warn_pairs[: cfg.max_pairs_in_message]
        )
        results.append(
            CheckResult.warn(
                "correlations.feature_pairs",
                "Feature Correlation",
                f"{len(warn_pairs)} moderately correlated feature pair(s) "
                f"(r≥{cfg.warn_threshold:.2f}): {pair_strs}.",
                details={"pairs": warn_pairs},
                confidence=min(0.9, 0.55 + min(0.3, len(warn_pairs) / 20.0)),
                penalty=cfg.warn_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "correlations.feature_pairs",
                "Feature Correlation",
                "No highly correlated feature pairs detected.",
                confidence=0.85,
            )
        )

    return results
