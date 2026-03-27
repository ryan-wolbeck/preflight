"""
Completeness checks
===================
- Overall missing-value rate
- Per-column missing rate, flagged at >20 % (WARN) and >50 % (FAIL)
"""

from __future__ import annotations

from typing import Optional

import pandas as pd

from preflight.config import CompletenessConfig
from preflight._types import CheckResult


def run(
    df: pd.DataFrame,
    target: Optional[str] = None,
    config: CompletenessConfig | None = None,
) -> list[CheckResult]:
    """Return a list of CheckResult objects for completeness checks."""
    cfg = config or CompletenessConfig()
    results: list[CheckResult] = []

    if df.empty:
        results.append(
            CheckResult.warn(
                "completeness.empty_dataframe",
                "Completeness",
                "DataFrame is empty — no rows to analyse.",
                confidence=1.0,
                penalty=cfg.empty_dataframe_penalty,
            )
        )
        return results

    # ── 1. Overall missing rate ──────────────────────────────────────────────
    total_cells = df.size
    total_missing = int(df.isna().sum().sum())
    overall_rate = total_missing / total_cells if total_cells > 0 else 0.0

    if total_missing == 0:
        results.append(
            CheckResult.passed(
                "completeness.overall",
                "Completeness",
                "No missing values detected across all columns.",
                details={"missing_cells": 0, "missing_rate": 0.0},
                confidence=1.0,
            )
        )
    elif overall_rate <= cfg.warn_threshold:
        results.append(
            CheckResult.warn(
                "completeness.overall",
                "Completeness",
                f"Overall missing-value rate: {overall_rate:.1%} ({total_missing:,} cells).",
                details={"missing_cells": total_missing, "missing_rate": round(overall_rate, 4)},
                confidence=min(1.0, 0.4 + overall_rate),
                penalty=cfg.overall_warn_penalty,
            )
        )
    else:
        results.append(
            CheckResult.fail(
                "completeness.overall",
                "Completeness",
                f"High overall missing-value rate: {overall_rate:.1%} ({total_missing:,} cells).",
                details={"missing_cells": total_missing, "missing_rate": round(overall_rate, 4)},
                confidence=min(1.0, 0.7 + overall_rate / 2.0),
                penalty=cfg.overall_fail_penalty,
            )
        )

    # ── 2. Per-column missing rates ──────────────────────────────────────────
    col_missing = df.isna().mean()
    warn_cols: dict[str, float] = {}
    fail_cols: dict[str, float] = {}

    for col, rate in col_missing.items():
        if rate >= cfg.fail_threshold:
            fail_cols[col] = round(float(rate), 4)
        elif rate >= cfg.warn_threshold:
            warn_cols[col] = round(float(rate), 4)

    if fail_cols:
        col_list = ", ".join(
            f"`{c}` ({r:.0%})" for c, r in sorted(fail_cols.items(), key=lambda x: -x[1])
        )
        results.append(
            CheckResult.fail(
                "completeness.high_missing",
                "Completeness",
                f"{len(fail_cols)} column(s) exceed {cfg.fail_threshold:.0%} missing: {col_list}.",
                details={"columns": fail_cols},
                confidence=0.95,
                penalty=cfg.per_column_fail_penalty * min(len(fail_cols), 3),
            )
        )

    if warn_cols:
        col_list = ", ".join(
            f"`{c}` ({r:.0%})" for c, r in sorted(warn_cols.items(), key=lambda x: -x[1])
        )
        results.append(
            CheckResult.warn(
                "completeness.moderate_missing",
                "Completeness",
                f"{len(warn_cols)} column(s) between {cfg.warn_threshold:.0%}–"
                f"{cfg.fail_threshold:.0%} missing: {col_list}.",
                details={"columns": warn_cols},
                confidence=0.75,
                penalty=cfg.per_column_warn_penalty * min(len(warn_cols), 3),
            )
        )

    if not fail_cols and not warn_cols and total_missing == 0:
        pass  # already reported PASS above
    elif not fail_cols and not warn_cols:
        results.append(
            CheckResult.passed(
                "completeness.per_column",
                "Completeness",
                f"All individual columns are below the {cfg.warn_threshold:.0%} missing threshold.",
                details={"max_missing_rate": round(float(col_missing.max()), 4)},
                confidence=0.9,
            )
        )

    return results
