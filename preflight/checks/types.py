"""
Data Type Sanity checks
========================
- Object columns whose values look entirely numeric (should be cast)
- Object columns with mixed Python types (str + int + float etc.)
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from preflight.config import TypesConfig
from preflight._types import CheckResult


def _looks_numeric(series: pd.Series, config: TypesConfig | None = None) -> bool:
    """Return True if the majority of non-null values can be parsed as floats."""
    cfg = config or TypesConfig()
    sample = series.dropna().head(cfg.numeric_sample_size)
    if len(sample) == 0:
        return False
    parsed = pd.to_numeric(sample, errors="coerce")
    return bool(parsed.notna().mean() >= cfg.numeric_parse_threshold)


def _has_mixed_types(series: pd.Series, config: TypesConfig | None = None) -> bool:
    """Return True if the column contains more than one Python primitive type."""
    cfg = config or TypesConfig()
    sample = series.dropna().head(cfg.numeric_sample_size)
    if len(sample) == 0:
        return False
    types_seen = set(type(v).__name__ for v in sample)
    # Filter out subclasses that are expected to co-exist (e.g. int/float)
    numeric_types = {"int", "float", "int64", "float64", "numpy.int64", "numpy.float64"}
    non_numeric = types_seen - numeric_types
    numeric_present = types_seen & numeric_types
    # Mixed = has both numeric AND non-numeric, or has 3+ distinct base types
    if non_numeric and numeric_present:
        return True
    if len(types_seen) >= 3:
        return True
    return False


def run(
    df: pd.DataFrame, target: Optional[str] = None, config: TypesConfig | None = None
) -> list[CheckResult]:
    cfg = config or TypesConfig()
    results: list[CheckResult] = []

    if df.empty:
        return results

    # Include pandas "string" dtype explicitly for forward compatibility.
    object_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    if not object_cols:
        results.append(
            CheckResult.passed(
                "types.no_object_columns",
                "Data Types",
                "No object-typed columns found — all columns have explicit dtypes.",
                confidence=1.0,
            )
        )
        return results

    # ── 1. Numeric values stored as object ───────────────────────────────────
    numeric_as_object: list[str] = []
    for col in object_cols:
        if _looks_numeric(df[col], cfg):
            numeric_as_object.append(col)

    if numeric_as_object:
        results.append(
            CheckResult.warn(
                "types.numeric_as_object",
                "Data Types",
                f"{len(numeric_as_object)} column(s) typed as object but appear numeric: "
                + ", ".join(f"`{c}`" for c in numeric_as_object)
                + ". Consider casting with pd.to_numeric().",
                details={"columns": numeric_as_object},
                confidence=0.85,
                penalty=cfg.numeric_as_object_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "types.numeric_as_object",
                "Data Types",
                "No object columns appear to be numeric.",
                confidence=0.8,
            )
        )

    # ── 2. Mixed types in object column ─────────────────────────────────────
    mixed_type_cols: list[str] = []
    for col in object_cols:
        if col in numeric_as_object:
            continue  # already flagged
        if _has_mixed_types(df[col], cfg):
            mixed_type_cols.append(col)

    if mixed_type_cols:
        results.append(
            CheckResult.warn(
                "types.mixed_types",
                "Data Types",
                f"{len(mixed_type_cols)} column(s) contain mixed Python types: "
                + ", ".join(f"`{c}`" for c in mixed_type_cols)
                + ". This often indicates data pipeline issues.",
                details={"columns": mixed_type_cols},
                confidence=0.8,
                penalty=cfg.mixed_types_penalty,
            )
        )
    else:
        results.append(
            CheckResult.passed(
                "types.mixed_types",
                "Data Types",
                "No mixed-type object columns detected.",
                confidence=0.85,
            )
        )

    return results
