"""
Leakage Detection checks
=========================
- Columns with suspiciously high correlation to target (>0.95)
- Date/time columns that could implicitly encode the target
- ID-like columns (monotonic integers, unique object columns)
"""

from __future__ import annotations

import re
from typing import Optional

import numpy as np
import pandas as pd

from preflight.config import LeakageConfig
from preflight._types import CheckResult

# Regex patterns that suggest an ID or key column
_ID_PATTERNS = re.compile(r"\b(id|key|uuid|guid|pk|index|row_?num|seq)\b", re.IGNORECASE)


def _pearson_or_pointbiserial(series: pd.Series, target: pd.Series) -> Optional[float]:
    """
    Compute an appropriate correlation between *series* and *target*.
    Returns None if computation is impossible (e.g. all NaN, zero variance).
    """
    try:
        combined = pd.concat([series, target], axis=1).dropna()
        if len(combined) < 10:
            return None

        x = combined.iloc[:, 0].astype(float)
        y = combined.iloc[:, 1].astype(float)

        if x.std() == 0 or y.std() == 0:
            return None

        # Use point-biserial when target is binary, Pearson otherwise
        n_unique_y = y.nunique()
        if n_unique_y == 2:
            try:
                from scipy.stats import pointbiserialr  # type: ignore[import-untyped]

                stat, _ = pointbiserialr(y, x)
            except ImportError:
                # Fall back to Pearson (good approximation for point-biserial)
                stat = float(x.corr(y))
        else:
            stat = float(x.corr(y))

        return abs(stat) if not np.isnan(stat) else None
    except Exception:
        return None


def _temporal_association(dt_series: pd.Series, target: pd.Series) -> Optional[float]:
    """
    Estimate target association strength for a datetime feature.
    Returns absolute Pearson correlation between epoch seconds and target.
    """
    combined = pd.concat([dt_series, target], axis=1).dropna()
    if len(combined) < 20:
        return None
    ts = pd.to_datetime(combined.iloc[:, 0], errors="coerce")
    y = pd.to_numeric(combined.iloc[:, 1], errors="coerce")
    valid = ts.notna() & y.notna()
    if valid.sum() < 20:
        return None
    # Avoid deprecated Series.view() path so CI with -W error remains stable.
    x = ts[valid].astype("int64", copy=False).to_numpy(dtype="float64") / 1e9
    y_valid = y[valid].astype(float)
    if float(np.nanstd(x)) == 0.0 or float(np.nanstd(y_valid)) == 0.0:
        return None
    corr = float(pd.Series(x).corr(pd.Series(y_valid)))
    if np.isnan(corr):
        return None
    return abs(corr)


def run(
    df: pd.DataFrame, target: Optional[str] = None, config: LeakageConfig | None = None
) -> list[CheckResult]:
    cfg = config or LeakageConfig()
    results: list[CheckResult] = []

    if target is None or target not in df.columns:
        results.append(
            CheckResult.passed(
                "leakage.skipped",
                "Leakage Detection",
                "No target column specified — leakage detection skipped.",
                confidence=1.0,
            )
        )
        return results

    target_series = df[target]
    feature_cols = [c for c in df.columns if c != target]

    # ── 1. High-correlation leakage ──────────────────────────────────────────
    high_corr_fail: dict[str, float] = {}
    high_corr_warn: dict[str, float] = {}

    numeric_features = df[feature_cols].select_dtypes(include=[np.number])

    for col in numeric_features.columns:
        corr = _pearson_or_pointbiserial(df[col], target_series)
        if corr is None:
            continue
        if corr >= cfg.corr_fail_threshold:
            high_corr_fail[col] = round(corr, 4)
        elif corr >= cfg.corr_warn_threshold:
            high_corr_warn[col] = round(corr, 4)

    if high_corr_fail:
        col_list = ", ".join(f"`{c}` (r={v})" for c, v in high_corr_fail.items())
        results.append(
            CheckResult.fail(
                "leakage.high_correlation",
                "Leakage Detection",
                f"Potential target leakage — suspiciously high correlation: {col_list}.",
                details={"columns": high_corr_fail},
                confidence=0.95,
                penalty=cfg.corr_fail_penalty,
            )
        )
    elif high_corr_warn:
        col_list = ", ".join(f"`{c}` (r={v})" for c, v in high_corr_warn.items())
        results.append(
            CheckResult.warn(
                "leakage.high_correlation",
                "Leakage Detection",
                f"Columns with high (but not conclusive) correlation to target: {col_list}.",
                details={"columns": high_corr_warn},
                confidence=0.75,
                penalty=cfg.corr_warn_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "leakage.high_correlation",
                "Leakage Detection",
                "No features with suspiciously high correlation to target.",
                confidence=0.85,
            )
        )

    # ── 2. ID-like columns ───────────────────────────────────────────────────
    id_cols: list[str] = []
    for col in feature_cols:
        series = df[col]
        col_lower = col.lower()

        # Name-based pattern match
        if _ID_PATTERNS.search(col_lower):
            id_cols.append(col)
            continue

        # Numeric column that is strictly monotonic → likely a row index
        if pd.api.types.is_numeric_dtype(series):
            non_null = series.dropna()
            if (
                len(non_null) > 1
                and (
                    bool(non_null.is_monotonic_increasing) or bool(non_null.is_monotonic_decreasing)
                )
                and non_null.nunique() == len(non_null)
            ):
                id_cols.append(col)
                continue

        # Object column where every value is unique
        if series.dtype == object:
            if series.nunique() == len(series.dropna()) and len(series.dropna()) > 10:
                id_cols.append(col)

    if id_cols:
        results.append(
            CheckResult.warn(
                "leakage.id_like_columns",
                "Leakage Detection",
                f"{len(id_cols)} ID-like column(s) detected that may leak row identity: "
                + ", ".join(f"`{c}`" for c in id_cols),
                details={"columns": id_cols},
                confidence=0.8,
                penalty=cfg.id_like_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "leakage.id_like_columns",
                "Leakage Detection",
                "No ID-like columns detected.",
                confidence=0.75,
            )
        )

    # ── 3. Datetime columns ──────────────────────────────────────────────────
    dt_cols: list[str] = []
    for col in feature_cols:
        series = df[col]
        if pd.api.types.is_datetime64_any_dtype(series):
            dt_cols.append(col)
        elif series.dtype == object:
            # Try to parse a sample
            sample = series.dropna().head(20)
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
                if parsed.notna().mean() > 0.8:
                    dt_cols.append(col)
            except Exception:
                pass

    if dt_cols:
        results.append(
            CheckResult.warn(
                "leakage.datetime_columns",
                "Leakage Detection",
                f"{len(dt_cols)} datetime column(s) may implicitly encode the target: "
                + ", ".join(f"`{c}`" for c in dt_cols)
                + ". Consider extracting features or excluding from training.",
                details={"columns": dt_cols},
                confidence=0.8,
                penalty=cfg.datetime_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "leakage.datetime_columns",
                "Leakage Detection",
                "No raw datetime columns detected.",
                confidence=0.85,
            )
        )

    # ── 4. Temporal leakage risk (datetime correlation to target) ───────────
    temporal_fail: dict[str, float] = {}
    temporal_warn: dict[str, float] = {}
    if dt_cols:
        for col in dt_cols:
            assoc = _temporal_association(df[col], target_series)
            if assoc is None:
                continue
            if assoc >= cfg.temporal_fail_threshold:
                temporal_fail[col] = round(assoc, 4)
            elif assoc >= cfg.temporal_warn_threshold:
                temporal_warn[col] = round(assoc, 4)

    if temporal_fail:
        col_list = ", ".join(f"`{c}` (|r|={v})" for c, v in temporal_fail.items())
        results.append(
            CheckResult.fail(
                "leakage.temporal_signal",
                "Leakage Detection",
                f"Strong temporal association with target detected: {col_list}.",
                details={"columns": temporal_fail},
                confidence=0.9,
                penalty=cfg.temporal_fail_penalty,
            )
        )
    elif temporal_warn:
        col_list = ", ".join(f"`{c}` (|r|={v})" for c, v in temporal_warn.items())
        results.append(
            CheckResult.warn(
                "leakage.temporal_signal",
                "Leakage Detection",
                f"Moderate temporal association with target detected: {col_list}.",
                details={"columns": temporal_warn},
                confidence=0.75,
                penalty=cfg.temporal_warn_penalty,
            )
        )
    elif dt_cols:
        results.append(
            CheckResult.passed(
                "leakage.temporal_signal",
                "Leakage Detection",
                "Datetime columns present but no strong temporal association with target detected.",
                confidence=0.75,
            )
        )

    return results
