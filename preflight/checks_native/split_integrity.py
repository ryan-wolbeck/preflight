"""
Native split-integrity checks for policy-first run_split.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from preflight.config import PreflightConfig
from preflight.model.finding import Domain, Evidence, Finding, Severity


def run_split_checks(
    train_df: pd.DataFrame, test_df: pd.DataFrame, config: PreflightConfig
) -> list[Finding]:
    findings: list[Finding] = []
    split_cfg = config.split

    common_cols = [c for c in train_df.columns if c in test_df.columns]
    numeric_cols = train_df[common_cols].select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = (
        train_df[common_cols]
        .select_dtypes(include=["object", "string", "category"])
        .columns.tolist()
    )

    # Numeric PSI drift
    high_psi: list[dict[str, float | str]] = []
    moderate_psi: list[dict[str, float | str]] = []
    for col in numeric_cols:
        psi = _compute_psi(train_df[col].dropna().to_numpy(), test_df[col].dropna().to_numpy())
        if psi is None:
            continue
        rec = {"column": col, "psi": round(psi, 4)}
        if psi >= split_cfg.psi_fail_threshold:
            high_psi.append(rec)
        elif psi >= split_cfg.psi_warn_threshold:
            moderate_psi.append(rec)

    if high_psi:
        findings.append(
            Finding(
                check_id="split.numeric_psi",
                title=f"{len(high_psi)} numeric column(s) show major PSI drift.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="high",
                confidence=0.9,
                evidence=Evidence(
                    metrics={"count": len(high_psi)},
                    threshold={"metric": "psi", "op": ">=", "value": split_cfg.psi_fail_threshold},
                    samples={"columns": high_psi},
                ),
                affected_columns=[str(item["column"]) for item in high_psi],
                recommendations=[
                    "Review split strategy and data generation windows.",
                    "Add drift guardrails in pipeline CI.",
                ],
                severity=Severity.ERROR,
            )
        )
    elif moderate_psi:
        findings.append(
            Finding(
                check_id="split.numeric_psi",
                title=f"{len(moderate_psi)} numeric column(s) show moderate PSI drift.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="medium",
                confidence=0.75,
                evidence=Evidence(
                    metrics={"count": len(moderate_psi)},
                    threshold={"metric": "psi", "op": ">=", "value": split_cfg.psi_warn_threshold},
                    samples={"columns": moderate_psi},
                ),
                affected_columns=[str(item["column"]) for item in moderate_psi],
                recommendations=["Investigate feature distribution shifts between train and test."],
                severity=Severity.WARN,
            )
        )
    else:
        findings.append(
            Finding(
                check_id="split.numeric_psi",
                title="No material numeric PSI drift detected.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="low",
                confidence=0.85,
                evidence=Evidence(metrics={"columns_checked": len(numeric_cols)}),
                severity=Severity.INFO,
            )
        )

    # Categorical TVD drift
    high_tvd: list[dict[str, float | str]] = []
    moderate_tvd: list[dict[str, float | str]] = []
    for col in categorical_cols:
        tvd = _compute_categorical_tvd(train_df[col], test_df[col])
        if tvd is None:
            continue
        rec = {"column": col, "tvd": round(tvd, 4)}
        if tvd >= split_cfg.categorical_tvd_fail_threshold:
            high_tvd.append(rec)
        elif tvd >= split_cfg.categorical_tvd_warn_threshold:
            moderate_tvd.append(rec)

    if high_tvd:
        findings.append(
            Finding(
                check_id="split.categorical_tvd",
                title=f"{len(high_tvd)} categorical column(s) show major TVD drift.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="high",
                confidence=0.85,
                evidence=Evidence(
                    metrics={"count": len(high_tvd)},
                    threshold={
                        "metric": "tvd",
                        "op": ">=",
                        "value": split_cfg.categorical_tvd_fail_threshold,
                    },
                    samples={"columns": high_tvd},
                ),
                affected_columns=[str(item["column"]) for item in high_tvd],
                recommendations=["Audit categorical value generation and train/test sampling."],
                severity=Severity.ERROR,
            )
        )
    elif moderate_tvd:
        findings.append(
            Finding(
                check_id="split.categorical_tvd",
                title=f"{len(moderate_tvd)} categorical column(s) show moderate TVD drift.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="medium",
                confidence=0.75,
                evidence=Evidence(
                    metrics={"count": len(moderate_tvd)},
                    threshold={
                        "metric": "tvd",
                        "op": ">=",
                        "value": split_cfg.categorical_tvd_warn_threshold,
                    },
                    samples={"columns": moderate_tvd},
                ),
                affected_columns=[str(item["column"]) for item in moderate_tvd],
                recommendations=["Consider stratified splitting for key categorical features."],
                severity=Severity.WARN,
            )
        )
    elif categorical_cols:
        findings.append(
            Finding(
                check_id="split.categorical_tvd",
                title="No material categorical TVD drift detected.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="low",
                confidence=0.8,
                evidence=Evidence(metrics={"columns_checked": len(categorical_cols)}),
                severity=Severity.INFO,
            )
        )

    # Missingness drift
    high_missing: list[dict[str, float | str]] = []
    moderate_missing: list[dict[str, float | str]] = []
    for col in common_cols:
        miss_train = float(train_df[col].isna().mean())
        miss_test = float(test_df[col].isna().mean())
        delta = abs(miss_test - miss_train)
        rec = {
            "column": col,
            "train_missing_rate": round(miss_train, 4),
            "test_missing_rate": round(miss_test, 4),
            "delta": round(delta, 4),
        }
        if delta >= split_cfg.missingness_fail_delta:
            high_missing.append(rec)
        elif delta >= split_cfg.missingness_warn_delta:
            moderate_missing.append(rec)

    if high_missing:
        findings.append(
            Finding(
                check_id="split.missingness_delta",
                title=f"{len(high_missing)} column(s) show major missingness drift.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="high",
                confidence=0.9,
                evidence=Evidence(
                    metrics={"count": len(high_missing)},
                    threshold={
                        "metric": "missingness_delta",
                        "op": ">=",
                        "value": split_cfg.missingness_fail_delta,
                    },
                    samples={"columns": high_missing[:20]},
                ),
                affected_columns=[str(item["column"]) for item in high_missing],
                recommendations=["Check ingestion changes causing missingness skew."],
                severity=Severity.ERROR,
            )
        )
    elif moderate_missing:
        findings.append(
            Finding(
                check_id="split.missingness_delta",
                title=f"{len(moderate_missing)} column(s) show moderate missingness drift.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="medium",
                confidence=0.75,
                evidence=Evidence(
                    metrics={"count": len(moderate_missing)},
                    threshold={
                        "metric": "missingness_delta",
                        "op": ">=",
                        "value": split_cfg.missingness_warn_delta,
                    },
                    samples={"columns": moderate_missing[:20]},
                ),
                affected_columns=[str(item["column"]) for item in moderate_missing],
                recommendations=["Monitor missingness rates over time per split."],
                severity=Severity.WARN,
            )
        )
    else:
        findings.append(
            Finding(
                check_id="split.missingness_delta",
                title="No material missingness drift detected.",
                domain=Domain.SPLIT_INTEGRITY,
                signal_strength="low",
                confidence=0.85,
                evidence=Evidence(metrics={"columns_checked": len(common_cols)}),
                severity=Severity.INFO,
            )
        )

    return findings


def _compute_psi(expected: np.ndarray, actual: np.ndarray, n_bins: int = 10) -> float | None:
    if len(expected) < n_bins or len(actual) < n_bins:
        return None
    lower = min(float(expected.min()), float(actual.min()))
    upper = max(float(expected.max()), float(actual.max()))
    if lower == upper:
        return 0.0
    bins = np.linspace(lower, upper, n_bins + 1)

    def _pct(values: np.ndarray) -> np.ndarray:
        counts, _ = np.histogram(values, bins=bins)
        pct = counts / max(1, len(values))
        return np.where(pct == 0, 1e-4, pct).astype(float)

    p = _pct(expected)
    q = _pct(actual)
    return float(np.sum((q - p) * np.log(q / p)))


def _compute_categorical_tvd(train_col: pd.Series, test_col: pd.Series) -> float | None:
    train = train_col.fillna("__MISSING__").astype(str)
    test = test_col.fillna("__MISSING__").astype(str)
    if len(train) == 0 or len(test) == 0:
        return None
    train_dist = train.value_counts(normalize=True)
    test_dist = test.value_counts(normalize=True)
    all_vals = train_dist.index.union(test_dist.index)
    p = train_dist.reindex(all_vals, fill_value=0.0).astype(float).to_numpy()
    q = test_dist.reindex(all_vals, fill_value=0.0).astype(float).to_numpy()
    return 0.5 * float(np.abs(p - q).sum())
