"""
Native class-balance check emitting policy-first findings.
"""

from __future__ import annotations

import pandas as pd

from preflight.constants import CheckName
from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = CheckName.BALANCE.value


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    target = context.target
    cfg = context.config.balance

    if target is None:
        return [
            Finding(
                check_id="balance.skipped",
                title="Class-balance check skipped because no target was provided.",
                domain=Domain.DATA_QUALITY,
                signal_strength="low",
                confidence=1.0,
                evidence=Evidence(metrics={"target_provided": False}),
                recommendations=[
                    "Provide target column name for target-aware class-balance checks."
                ],
                severity=Severity.INFO,
            )
        ]

    if target not in df.columns:
        return [
            Finding(
                check_id="balance.missing_target",
                title=f"Target column '{target}' was not found in the dataset.",
                domain=Domain.DATA_QUALITY,
                signal_strength="medium",
                confidence=1.0,
                evidence=Evidence(metrics={"target_provided": True, "target_present": False}),
                recommendations=["Fix target column name or update ingestion schema mapping."],
                severity=Severity.WARN,
            )
        ]

    series = df[target].dropna()
    if len(series) == 0:
        return [
            Finding(
                check_id="balance.empty_target",
                title=f"Target column '{target}' contains only missing values.",
                domain=Domain.DATA_QUALITY,
                signal_strength="medium",
                confidence=1.0,
                evidence=Evidence(metrics={"target_present": True, "nonnull_rows": 0}),
                recommendations=["Populate target labels before training and QA checks."],
                severity=Severity.WARN,
            )
        ]

    n_unique = int(series.nunique())
    is_numeric_continuous = (
        pd.api.types.is_numeric_dtype(series) and n_unique > cfg.categorical_threshold
    )
    if is_numeric_continuous:
        return [
            Finding(
                check_id="balance.continuous_target",
                title=(
                    f"Target '{target}' appears continuous ({n_unique} unique values); "
                    "class-balance check not applicable."
                ),
                domain=Domain.DATA_QUALITY,
                signal_strength="low",
                confidence=0.95,
                evidence=Evidence(
                    metrics={
                        "target_unique_values": n_unique,
                        "categorical_threshold": cfg.categorical_threshold,
                    }
                ),
                recommendations=["Use regression-specific label diagnostics for this target."],
                severity=Severity.INFO,
            )
        ]

    if n_unique == 1:
        only_class = str(series.iloc[0])
        return [
            Finding(
                check_id="balance.single_class_target",
                title=f"Target '{target}' contains only one class ('{only_class}').",
                domain=Domain.DATA_QUALITY,
                signal_strength="high",
                confidence=1.0,
                evidence=Evidence(metrics={"target_unique_values": 1}),
                recommendations=[
                    "Collect additional labeled examples for the missing class before training.",
                    "Verify target generation logic and class mapping.",
                ],
                severity=Severity.ERROR,
            )
        ]

    counts = series.value_counts()
    total = int(len(series))
    majority_count = int(counts.iloc[0])
    minority_count = int(counts.iloc[-1])
    ratio = majority_count / minority_count if minority_count > 0 else float("inf")
    distribution = {str(k): round(float(v / total), 4) for k, v in counts.items()}

    if ratio >= cfg.fail_ratio:
        severity = Severity.ERROR
        signal = "high"
        title = "Severe class imbalance detected."
    elif ratio >= cfg.warn_ratio:
        severity = Severity.WARN
        signal = "medium"
        title = "Moderate class imbalance detected."
    else:
        severity = Severity.INFO
        signal = "low"
        title = "Class distribution is within configured tolerance."

    return [
        Finding(
            check_id="balance.class_imbalance",
            title=title,
            domain=Domain.DATA_QUALITY,
            signal_strength=signal,
            confidence=0.9 if severity != Severity.INFO else 0.85,
            evidence=Evidence(
                metrics={
                    "majority_minority_ratio": round(float(ratio), 4),
                    "warn_ratio": cfg.warn_ratio,
                    "fail_ratio": cfg.fail_ratio,
                    "target_unique_values": n_unique,
                },
                samples={"distribution": distribution},
            ),
            recommendations=[
                "Use class weights, resampling, or stratified splitting as needed.",
                "Monitor class priors between training and production datasets.",
            ],
            severity=severity,
        )
    ]
