"""
Distributional Health checks
=============================
- Constant columns (zero variance)
- Near-zero variance columns (variance < 0.01 after normalisation)
- High-cardinality categorical columns (unique > 95% of rows)
- Scale disparity across numeric features (range differs by >4 orders of magnitude)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from preflight.config import DistributionsConfig
from preflight._types import CheckResult


def run(
    df: pd.DataFrame, target: Optional[str] = None, config: DistributionsConfig | None = None
) -> list[CheckResult]:
    cfg = config or DistributionsConfig()
    results: list[CheckResult] = []

    if df.empty:
        return results

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    # Include pandas "string" dtype explicitly for forward compatibility.
    object_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()
    n_rows = len(df)

    # ── 1. Constant columns ──────────────────────────────────────────────────
    constant_cols: list[str] = []
    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0 or series.nunique() == 1:
            constant_cols.append(col)

    if constant_cols:
        results.append(
            CheckResult.fail(
                "distributions.constant_columns",
                "Distributional Health",
                f"{len(constant_cols)} constant column(s) detected (zero variance): "
                + ", ".join(f"`{c}`" for c in constant_cols),
                details={"columns": constant_cols},
                confidence=1.0,
                penalty=cfg.constant_penalty_per_column * len(constant_cols),
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "distributions.constant_columns",
                "Distributional Health",
                "No constant columns detected.",
                confidence=0.9,
            )
        )

    # ── 2. Near-zero variance (numeric only) ─────────────────────────────────
    low_var_cols: dict[str, float] = {}
    for col in numeric_cols:
        if col in constant_cols:
            continue
        series = df[col].dropna()
        col_range = series.max() - series.min()
        # Coefficient of variation proxy: std / (max-min)
        norm_var = float(series.std() / col_range) if col_range != 0 else 0.0
        if norm_var < cfg.low_var_threshold:
            low_var_cols[col] = round(norm_var, 6)

    if low_var_cols:
        results.append(
            CheckResult.warn(
                "distributions.low_variance",
                "Distributional Health",
                f"{len(low_var_cols)} near-zero variance column(s): "
                + ", ".join(f"`{c}`" for c in low_var_cols),
                details={"columns": low_var_cols},
                confidence=0.8,
                penalty=cfg.low_variance_penalty,
            )
        )
    elif numeric_cols:
        results.append(
            CheckResult.passed(
                "distributions.low_variance",
                "Distributional Health",
                "All numeric columns have sufficient variance.",
                confidence=0.85,
            )
        )

    # ── 3. High-cardinality categorical columns ──────────────────────────────
    high_card_cols: dict[str, float] = {}
    for col in object_cols:
        if col == target:
            continue
        series = df[col].dropna()
        if len(series) == 0:
            continue
        ratio = series.nunique() / n_rows
        if ratio > cfg.high_card_threshold:
            high_card_cols[col] = round(ratio, 4)

    if high_card_cols:
        results.append(
            CheckResult.warn(
                "distributions.high_cardinality",
                "Distributional Health",
                f"{len(high_card_cols)} high-cardinality categorical column(s) (unique values > "
                f"{cfg.high_card_threshold:.0%} of rows — may be ID-like): "
                + ", ".join(f"`{c}` ({v:.0%})" for c, v in high_card_cols.items()),
                details={"columns": high_card_cols},
                confidence=0.85,
                penalty=cfg.high_card_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "distributions.high_cardinality",
                "Distributional Health",
                "No high-cardinality categorical columns detected.",
                confidence=0.8,
            )
        )

    # ── 4. Scale disparity ───────────────────────────────────────────────────
    if len(numeric_cols) >= 2:
        ranges: dict[str, float] = {}
        for col in numeric_cols:
            if col == target:
                continue
            series = df[col].dropna()
            if len(series) == 0:
                continue
            col_range = float(abs(series.max() - series.min()))
            # For constant columns, use the absolute value as the representative scale
            if col_range == 0:
                abs_val = float(abs(series.iloc[0])) if len(series) > 0 else 0.0
                if abs_val > 0:
                    ranges[col] = abs_val
            else:
                ranges[col] = col_range

        if len(ranges) >= 2:
            log_ranges = {c: np.log10(v) for c, v in ranges.items() if v > 0}
            if log_ranges:
                max_log = max(log_ranges.values())
                min_log = min(log_ranges.values())
                spread = max_log - min_log

                if spread >= cfg.scale_order_threshold:
                    max_col = max(log_ranges, key=log_ranges.get)  # type: ignore[arg-type]
                    min_col = min(log_ranges, key=log_ranges.get)  # type: ignore[arg-type]
                    results.append(
                        CheckResult.warn(
                            "distributions.scale_disparity",
                            "Distributional Health",
                            (
                                f"Feature value ranges span {spread:.1f} orders of magnitude "
                                f"(`{min_col}` range={ranges[min_col]:.2g} vs "
                                f"`{max_col}` range={ranges[max_col]:.2g}). "
                                "Consider scaling for distance-based models."
                            ),
                            details={
                                "log10_spread": round(spread, 2),
                                "max_range_col": max_col,
                                "min_range_col": min_col,
                            },
                            confidence=min(1.0, 0.65 + spread / 12.0),
                            penalty=cfg.scale_disparity_penalty,
                        )
                    )
                else:
                    results.append(
                        CheckResult.passed(
                            "distributions.scale_disparity",
                            "Distributional Health",
                            f"Feature scales are within {spread:.1f} orders of magnitude — acceptable.",
                            details={"log10_spread": round(spread, 2)},
                            confidence=0.8,
                        )
                    )

    return results
