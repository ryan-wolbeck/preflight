"""
Legacy compatibility API (`check` / `check_split`) and helpers.
"""

from __future__ import annotations

from typing import Optional, cast

import numpy as np
import numpy.typing as npt
import pandas as pd

from preflight._types import CheckResult
from preflight.checks import (
    balance,
    completeness,
    correlations,
    distributions,
    duplicates,
    leakage,
    types as types_check,
)
from preflight.config import PreflightConfig
from preflight.report import Report
from preflight.scorer import compute_score


def check(
    df: pd.DataFrame,
    target: Optional[str] = None,
    config: PreflightConfig | None = None,
) -> Report:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"preflight.check() expects a pandas DataFrame, got {type(df).__name__}")

    cfg = config or PreflightConfig()
    sampled_df = _prepare_runtime_df(df, cfg)

    all_results: list[CheckResult] = []
    if cfg.enabled_checks.get("completeness", True):
        all_results += completeness.run(sampled_df, target=target, config=cfg.completeness)
    if cfg.enabled_checks.get("balance", True):
        all_results += balance.run(sampled_df, target=target, config=cfg.balance)
    if cfg.enabled_checks.get("leakage", True):
        all_results += leakage.run(sampled_df, target=target, config=cfg.leakage)
    if cfg.enabled_checks.get("duplicates", True):
        all_results += duplicates.run(sampled_df, config=cfg.duplicates)
    if cfg.enabled_checks.get("distributions", True):
        all_results += distributions.run(sampled_df, target=target, config=cfg.distributions)
    if cfg.enabled_checks.get("correlations", True):
        all_results += correlations.run(sampled_df, target=target, config=cfg.correlations)
    if cfg.enabled_checks.get("types", True):
        all_results += types_check.run(sampled_df, target=target, config=cfg.types)

    score, verdict = compute_score(all_results, scoring_config=cfg.scoring)
    metadata = {
        "rows": len(df),
        "cols": len(df.columns),
        "target": target,
        "rows_analyzed": len(sampled_df),
        "sampling_applied": len(sampled_df) != len(df),
        "mode": cfg.runtime.mode,
    }
    return Report(checks=all_results, score=score, verdict=verdict, metadata=metadata)


def check_split(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    threshold_psi: float = 0.2,
    config: PreflightConfig | None = None,
) -> Report:
    if not isinstance(X_train, pd.DataFrame) or not isinstance(X_test, pd.DataFrame):
        raise TypeError("check_split() requires two pandas DataFrames.")

    cfg = config or PreflightConfig()
    train_df = _prepare_runtime_df(X_train, cfg)
    test_df = _prepare_runtime_df(X_test, cfg)
    results: list[CheckResult] = []
    effective_fail_threshold = (
        threshold_psi if threshold_psi != 0.2 else cfg.split.psi_fail_threshold
    )

    common_cols = [c for c in train_df.columns if c in test_df.columns]
    numeric_cols = train_df[common_cols].select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = (
        train_df[common_cols]
        .select_dtypes(include=["object", "string", "category"])
        .columns.tolist()
    )

    if not numeric_cols:
        results.append(
            CheckResult.passed(
                "split.no_numeric",
                "Train/Test Drift",
                "No numeric columns in common — drift check skipped.",
                confidence=1.0,
            )
        )
        return Report(
            results,
            score=100.0,
            verdict="READY",
            metadata={
                "train_rows": len(X_train),
                "test_rows": len(X_test),
                "sampling_applied_train": len(train_df) != len(X_train),
                "sampling_applied_test": len(test_df) != len(X_test),
                "rows_analyzed_train": len(train_df),
                "rows_analyzed_test": len(test_df),
            },
        )

    high_drift: list[dict[str, float | str]] = []
    moderate_drift: list[dict[str, float | str]] = []
    for col in numeric_cols:
        psi = _compute_psi(train_df[col].dropna().values, test_df[col].dropna().values)
        if psi is None:
            continue
        record: dict[str, float | str] = {"column": str(col), "psi": round(psi, 4)}
        if psi >= effective_fail_threshold:
            high_drift.append(record)
        elif psi >= cfg.split.psi_warn_threshold:
            moderate_drift.append(record)

    if high_drift:
        col_list = ", ".join(f"`{d['column']}` (PSI={d['psi']})" for d in high_drift)
        results.append(
            CheckResult.fail(
                "split.high_drift",
                "Train/Test Drift",
                f"{len(high_drift)} column(s) show major distribution shift: {col_list}.",
                details={"columns": high_drift},
                confidence=0.9,
                penalty=cfg.split.psi_fail_penalty
                * min(len(high_drift), cfg.split.drift_penalty_col_cap),
            )
        )
    if moderate_drift:
        col_list = ", ".join(f"`{d['column']}` (PSI={d['psi']})" for d in moderate_drift)
        results.append(
            CheckResult.warn(
                "split.moderate_drift",
                "Train/Test Drift",
                f"{len(moderate_drift)} column(s) show moderate distribution shift: {col_list}.",
                details={"columns": moderate_drift},
                confidence=0.75,
                penalty=cfg.split.psi_warn_penalty
                * min(len(moderate_drift), cfg.split.drift_penalty_col_cap),
            )
        )

    high_cat_drift: list[dict[str, float | str]] = []
    moderate_cat_drift: list[dict[str, float | str]] = []
    for col in categorical_cols:
        tvd = _compute_categorical_tvd(train_df[col], test_df[col])
        if tvd is None:
            continue
        rec: dict[str, float | str] = {"column": str(col), "tvd": round(tvd, 4)}
        if tvd >= cfg.split.categorical_tvd_fail_threshold:
            high_cat_drift.append(rec)
        elif tvd >= cfg.split.categorical_tvd_warn_threshold:
            moderate_cat_drift.append(rec)

    if high_cat_drift:
        col_list = ", ".join(f"`{d['column']}` (TVD={d['tvd']})" for d in high_cat_drift)
        results.append(
            CheckResult.fail(
                "split.categorical_drift",
                "Train/Test Drift",
                f"{len(high_cat_drift)} categorical column(s) show major drift: {col_list}.",
                details={"columns": high_cat_drift},
                confidence=0.85,
                penalty=cfg.split.categorical_fail_penalty,
            )
        )
    elif moderate_cat_drift:
        col_list = ", ".join(f"`{d['column']}` (TVD={d['tvd']})" for d in moderate_cat_drift)
        results.append(
            CheckResult.warn(
                "split.categorical_drift",
                "Train/Test Drift",
                f"{len(moderate_cat_drift)} categorical column(s) show moderate drift: {col_list}.",
                details={"columns": moderate_cat_drift},
                confidence=0.7,
                penalty=cfg.split.categorical_warn_penalty,
            )
        )
    elif categorical_cols:
        results.append(
            CheckResult.passed(
                "split.categorical_drift",
                "Train/Test Drift",
                "No material categorical drift detected in shared categorical columns.",
                confidence=0.75,
            )
        )

    missingness_fail: list[dict[str, float | str]] = []
    missingness_warn: list[dict[str, float | str]] = []
    for col in common_cols:
        miss_train = float(train_df[col].isna().mean())
        miss_test = float(test_df[col].isna().mean())
        delta = abs(miss_test - miss_train)
        missing_rec: dict[str, float | str] = {
            "column": str(col),
            "train_missing_rate": round(miss_train, 4),
            "test_missing_rate": round(miss_test, 4),
            "delta": round(delta, 4),
        }
        if delta >= cfg.split.missingness_fail_delta:
            missingness_fail.append(missing_rec)
        elif delta >= cfg.split.missingness_warn_delta:
            missingness_warn.append(missing_rec)

    if missingness_fail:
        col_list = ", ".join(f"`{d['column']}` (Δ={d['delta']})" for d in missingness_fail[:5])
        results.append(
            CheckResult.fail(
                "split.missingness_drift",
                "Train/Test Drift",
                f"{len(missingness_fail)} column(s) have major missingness drift: {col_list}.",
                details={"columns": missingness_fail},
                confidence=0.9,
                penalty=cfg.split.missingness_fail_penalty,
            )
        )
    elif missingness_warn:
        col_list = ", ".join(f"`{d['column']}` (Δ={d['delta']})" for d in missingness_warn[:5])
        results.append(
            CheckResult.warn(
                "split.missingness_drift",
                "Train/Test Drift",
                f"{len(missingness_warn)} column(s) have moderate missingness drift: {col_list}.",
                details={"columns": missingness_warn},
                confidence=0.75,
                penalty=cfg.split.missingness_warn_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "split.missingness_drift",
                "Train/Test Drift",
                "No material missingness drift detected.",
                confidence=0.85,
            )
        )

    if not high_drift and not moderate_drift:
        results.append(
            CheckResult.passed(
                "split.stable",
                "Train/Test Drift",
                f"All {len(numeric_cols)} numeric columns have stable distributions "
                f"(PSI < {cfg.split.psi_warn_threshold:.2f}).",
                confidence=0.8,
            )
        )

    score, verdict = compute_score(results, scoring_config=cfg.scoring)
    return Report(
        checks=results,
        score=score,
        verdict=verdict,
        metadata={
            "train_rows": len(X_train),
            "test_rows": len(X_test),
            "sampling_applied_train": len(train_df) != len(X_train),
            "sampling_applied_test": len(test_df) != len(X_test),
            "rows_analyzed_train": len(train_df),
            "rows_analyzed_test": len(test_df),
            "columns_checked": len(numeric_cols),
            "categorical_columns_checked": len(categorical_cols),
        },
    )


def _compute_psi(
    expected: npt.NDArray[np.float64],
    actual: npt.NDArray[np.float64],
    n_bins: int = 10,
) -> Optional[float]:
    if len(expected) < n_bins or len(actual) < n_bins:
        return None
    breakpoints = np.linspace(
        min(expected.min(), actual.min()), max(expected.max(), actual.max()), n_bins + 1
    )

    def _pct(arr: npt.NDArray[np.float64]) -> npt.NDArray[np.float64]:
        counts, _ = np.histogram(arr, bins=breakpoints)
        pct = counts / len(arr)
        pct = np.where(pct == 0, 1e-4, pct)
        return pct.astype(np.float64)

    exp_pct = _pct(expected)
    act_pct = _pct(actual)
    return float(np.sum((act_pct - exp_pct) * np.log(act_pct / exp_pct)))


def _compute_categorical_tvd(train_col: pd.Series, test_col: pd.Series) -> Optional[float]:
    train = train_col.fillna("__MISSING__").astype(str)
    test = test_col.fillna("__MISSING__").astype(str)
    if len(train) == 0 or len(test) == 0:
        return None
    train_dist = train.value_counts(normalize=True)
    test_dist = test.value_counts(normalize=True)
    all_cats = train_dist.index.union(test_dist.index)
    p = np.asarray(
        train_dist.reindex(all_cats, fill_value=0.0).astype(float).to_numpy(), dtype=float
    )
    q = np.asarray(
        test_dist.reindex(all_cats, fill_value=0.0).astype(float).to_numpy(), dtype=float
    )
    return 0.5 * float(np.abs(p - q).sum())


def _prepare_runtime_df(df: pd.DataFrame, config: PreflightConfig) -> pd.DataFrame:
    runtime = config.runtime
    if len(df) == 0:
        return df

    sample_rows = runtime.sample_rows
    if sample_rows is None:
        if runtime.mode == "fast":
            sample_rows = runtime.fast_mode_sample_rows
        elif len(df) > runtime.large_dataset_rows:
            sample_rows = runtime.fast_mode_sample_rows

    if sample_rows is None or sample_rows >= len(df):
        return df
    sampled = df.sample(n=sample_rows, random_state=runtime.random_state)
    return cast(pd.DataFrame, sampled)
