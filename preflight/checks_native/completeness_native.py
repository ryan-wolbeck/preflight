"""
Native completeness check emitting policy-first findings.
"""

from __future__ import annotations

import pandas as pd

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "completeness"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    cfg = context.config.completeness
    if df.empty:
        return [
            Finding(
                check_id="completeness.empty_dataframe",
                title="DataFrame is empty — no rows to analyze.",
                domain=Domain.DATA_QUALITY,
                signal_strength="high",
                confidence=1.0,
                evidence=Evidence(metrics={"rows": 0}),
                recommendations=["Confirm extraction query and upstream filters."],
                severity=Severity.ERROR,
            )
        ]

    total_cells = max(1, int(df.size))
    missing_cells = int(df.isna().sum().sum())
    missing_rate = float(missing_cells / total_cells)
    col_missing = df.isna().mean()

    fail_cols = [str(col) for col, rate in col_missing.items() if float(rate) >= cfg.fail_threshold]
    warn_cols = [
        str(col)
        for col, rate in col_missing.items()
        if cfg.warn_threshold <= float(rate) < cfg.fail_threshold
    ]

    if missing_rate >= cfg.fail_threshold or fail_cols:
        severity = Severity.ERROR
        signal = "high"
    elif missing_rate >= cfg.warn_threshold or warn_cols:
        severity = Severity.WARN
        signal = "medium"
    else:
        severity = Severity.INFO
        signal = "low"

    findings = [
        Finding(
            check_id="completeness.missingness",
            title=(
                f"Overall missingness is {missing_rate:.1%} "
                f"({missing_cells:,} cells missing across dataset)."
            ),
            domain=Domain.DATA_QUALITY,
            signal_strength=signal,
            confidence=0.95,
            evidence=Evidence(
                metrics={
                    "missing_rate": round(missing_rate, 6),
                    "missing_cells": missing_cells,
                    "warn_threshold": cfg.warn_threshold,
                    "fail_threshold": cfg.fail_threshold,
                },
                samples={"warn_columns": warn_cols[:20], "fail_columns": fail_cols[:20]},
            ),
            affected_columns=sorted(set(warn_cols + fail_cols)),
            recommendations=[
                "Inspect missingness by source system and ingestion step.",
                "Impute/drop columns using model-appropriate strategy.",
            ],
            severity=severity,
        )
    ]
    return findings
