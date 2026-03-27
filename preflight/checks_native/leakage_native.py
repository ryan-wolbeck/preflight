"""
Native leakage check with evidence-rich findings.
"""

from __future__ import annotations

import pandas as pd
import numpy as np

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "leakage"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    target = context.target
    cfg = context.config.leakage
    if target is None or target not in df.columns:
        return [
            Finding(
                check_id="leakage.skipped",
                title="Leakage checks skipped because no valid target was provided.",
                domain=Domain.TARGET_RISK,
                signal_strength="low",
                confidence=1.0,
                evidence=Evidence(
                    metrics={"target_present": bool(target in df.columns) if target else False}
                ),
                recommendations=["Provide target column name for target-aware leakage checks."],
                severity=Severity.INFO,
            )
        ]

    target_series = pd.to_numeric(df[target], errors="coerce")
    numeric = df.drop(columns=[target], errors="ignore").select_dtypes(include=[np.number])
    flagged_fail: list[dict[str, float | str]] = []
    flagged_warn: list[dict[str, float | str]] = []
    for col in numeric.columns:
        aligned = pd.concat(
            [pd.to_numeric(df[col], errors="coerce"), target_series], axis=1
        ).dropna()
        if len(aligned) < 20:
            continue
        corr = float(abs(aligned.iloc[:, 0].corr(aligned.iloc[:, 1])))
        if np.isnan(corr):
            continue
        rec: dict[str, float | str] = {"column": str(col), "abs_corr": float(round(corr, 4))}
        if corr >= cfg.corr_fail_threshold:
            flagged_fail.append(rec)
        elif corr >= cfg.corr_warn_threshold:
            flagged_warn.append(rec)

    if flagged_fail:
        severity = Severity.CRITICAL
        signal = "high"
        flagged = flagged_fail
    elif flagged_warn:
        severity = Severity.WARN
        signal = "medium"
        flagged = flagged_warn
    else:
        severity = Severity.INFO
        signal = "low"
        flagged = []

    return [
        Finding(
            check_id="leakage.high_correlation",
            title=(
                "Potential target leakage detected via feature-target correlation."
                if flagged
                else "No strong feature-target leakage signal detected."
            ),
            domain=Domain.TARGET_RISK,
            signal_strength=signal,
            confidence=0.9 if flagged else 0.8,
            evidence=Evidence(
                metrics={
                    "features_checked": int(numeric.shape[1]),
                    "warn_threshold": cfg.corr_warn_threshold,
                    "fail_threshold": cfg.corr_fail_threshold,
                    "flagged_count": len(flagged),
                },
                samples={"columns": flagged[:20]} if flagged else None,
            ),
            affected_columns=[str(item["column"]) for item in flagged],
            recommendations=[
                "Exclude leakage-prone columns from model features.",
                "Rebuild features using leakage-safe cutoffs.",
            ],
            severity=severity,
        )
    ]
