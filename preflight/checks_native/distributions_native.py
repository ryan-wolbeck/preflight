"""
Native distributional-health checks emitting policy-first findings.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "distributions"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    cfg = context.config.distributions
    if df.empty:
        return [
            Finding(
                check_id="distributions.skipped",
                title="Distribution checks skipped because dataset is empty.",
                domain=Domain.STAT_ANOMALY,
                signal_strength="low",
                confidence=1.0,
                evidence=Evidence(metrics={"rows": 0}),
                severity=Severity.INFO,
            )
        ]

    constant_cols: list[str] = []
    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0 or series.nunique() == 1:
            constant_cols.append(str(col))

    object_cols = df.select_dtypes(include=["object", "string", "category"]).columns.tolist()
    high_card_cols: list[str] = []
    n_rows = len(df)
    for col in object_cols:
        ratio = float(df[col].dropna().nunique() / max(1, n_rows))
        if ratio > cfg.high_card_threshold:
            high_card_cols.append(str(col))

    if constant_cols:
        severity = Severity.ERROR
        signal = "high"
    elif high_card_cols:
        severity = Severity.WARN
        signal = "medium"
    else:
        severity = Severity.INFO
        signal = "low"

    return [
        Finding(
            check_id="distributions.health",
            title=(
                f"{len(constant_cols)} constant column(s) and {len(high_card_cols)} high-cardinality "
                "categorical column(s) detected."
                if (constant_cols or high_card_cols)
                else "No major distributional health issues detected."
            ),
            domain=Domain.STAT_ANOMALY,
            signal_strength=signal,
            confidence=0.85,
            evidence=Evidence(
                metrics={
                    "constant_columns": len(constant_cols),
                    "high_cardinality_columns": len(high_card_cols),
                    "high_card_threshold": cfg.high_card_threshold,
                    "rows": int(n_rows),
                },
                samples={
                    "constant_columns": constant_cols[:20],
                    "high_cardinality_columns": high_card_cols[:20],
                },
            ),
            affected_columns=sorted(set(constant_cols + high_card_cols)),
            recommendations=[
                "Drop or re-engineer constant and quasi-identifier columns.",
                "Review feature semantics for high-cardinality fields.",
            ],
            severity=severity,
        )
    ]
