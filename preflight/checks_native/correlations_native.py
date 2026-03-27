"""
Native correlation check emitting policy-first findings.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "correlations"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    target = context.target
    cfg = context.config.correlations
    feature_df = df.drop(columns=[target], errors="ignore")
    numeric = feature_df.select_dtypes(include=[np.number])
    if numeric.shape[1] < 2:
        return [
            Finding(
                check_id="correlations.feature_pairs",
                title="Correlation check skipped: fewer than 2 numeric feature columns.",
                domain=Domain.STAT_ANOMALY,
                signal_strength="low",
                confidence=1.0,
                evidence=Evidence(metrics={"numeric_columns": int(numeric.shape[1])}),
                severity=Severity.INFO,
            )
        ]

    corr = numeric.corr(method="pearson").abs()
    fail_pairs: list[dict[str, float | str]] = []
    warn_pairs: list[dict[str, float | str]] = []
    cols = list(corr.columns)
    for i, col_a in enumerate(cols):
        for col_b in cols[i + 1 :]:
            val = corr.loc[col_a, col_b]
            if np.isnan(val):
                continue
            rec = {"col_a": str(col_a), "col_b": str(col_b), "abs_corr": round(float(val), 4)}
            if val >= cfg.fail_threshold:
                fail_pairs.append(rec)
            elif val >= cfg.warn_threshold:
                warn_pairs.append(rec)

    if fail_pairs:
        severity = Severity.ERROR
        signal = "high"
        pairs = fail_pairs
    elif warn_pairs:
        severity = Severity.WARN
        signal = "medium"
        pairs = warn_pairs
    else:
        severity = Severity.INFO
        signal = "low"
        pairs = []

    return [
        Finding(
            check_id="correlations.feature_pairs",
            title=(
                f"{len(pairs)} highly correlated feature pair(s) detected."
                if pairs
                else "No highly correlated feature pairs detected."
            ),
            domain=Domain.STAT_ANOMALY,
            signal_strength=signal,
            confidence=0.85,
            evidence=Evidence(
                metrics={
                    "warn_threshold": cfg.warn_threshold,
                    "fail_threshold": cfg.fail_threshold,
                    "pairs_flagged": len(pairs),
                },
                samples={"pairs": pairs[:20]} if pairs else None,
            ),
            affected_columns=sorted(
                {str(p["col_a"]) for p in pairs} | {str(p["col_b"]) for p in pairs}
            ),
            recommendations=["Remove redundant features or use dimensionality reduction."],
            severity=severity,
        )
    ]
