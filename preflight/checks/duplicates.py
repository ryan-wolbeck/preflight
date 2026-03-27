"""
Duplicate Detection checks
===========================
- Exact duplicate rows
- Near-duplicate rows (hash-based bucket approach, configurable threshold)
"""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from preflight.config import DuplicatesConfig
from preflight._types import CheckResult


def _row_hash(row: pd.Series, precision: int = 2) -> str:
    """
    Produce a coarse hash for a row by rounding floats to *precision* decimal
    places.  This groups near-identical numeric rows into the same bucket.
    """
    parts = []
    for val in row:
        if isinstance(val, float):
            parts.append(f"{round(val, precision)}")
        else:
            parts.append(str(val))
    key = "|".join(parts).encode()
    return hashlib.md5(key, usedforsecurity=False).hexdigest()[:8]


def run(
    df: pd.DataFrame,
    near_dup_precision: int = 2,
    config: DuplicatesConfig | None = None,
) -> list[CheckResult]:
    cfg = config or DuplicatesConfig()
    results: list[CheckResult] = []

    if df.empty or len(df) < 2:
        results.append(
            CheckResult.passed(
                "duplicates.exact",
                "Duplicates",
                "DataFrame has fewer than 2 rows — duplicate check skipped.",
                confidence=1.0,
            )
        )
        return results

    # ── 1. Exact duplicates ──────────────────────────────────────────────────
    n_exact = int(df.duplicated().sum())
    pct_exact = n_exact / len(df)

    if n_exact == 0:
        results.append(
            CheckResult.passed(
                "duplicates.exact",
                "Duplicates",
                "No exact duplicate rows found.",
                details={"duplicate_rows": 0},
                confidence=0.95,
            )
        )
    elif pct_exact < 0.01:
        results.append(
            CheckResult.warn(
                "duplicates.exact",
                "Duplicates",
                f"{n_exact} exact duplicate row(s) detected ({pct_exact:.1%} of data).",
                details={"duplicate_rows": n_exact, "duplicate_pct": round(pct_exact, 4)},
                confidence=min(0.95, 0.5 + pct_exact * 10),
                penalty=cfg.exact_warn_penalty,
            )
        )
    else:
        results.append(
            CheckResult.fail(
                "duplicates.exact",
                "Duplicates",
                f"{n_exact} exact duplicate row(s) detected ({pct_exact:.1%} of data).",
                details={"duplicate_rows": n_exact, "duplicate_pct": round(pct_exact, 4)},
                confidence=min(1.0, 0.7 + pct_exact * 6),
                penalty=cfg.exact_fail_penalty,
            )
        )

    # ── 2. Near-duplicate rows ───────────────────────────────────────────────
    # Only operate on numeric + bool columns for hashing efficiency
    numeric_df = df.select_dtypes(include=[np.number, bool])

    if numeric_df.empty or len(numeric_df.columns) == 0:
        results.append(
            CheckResult.passed(
                "duplicates.near",
                "Duplicates",
                "No numeric columns available for near-duplicate detection.",
                confidence=1.0,
            )
        )
        return results

    try:
        hashes = numeric_df.apply(lambda row: _row_hash(row, precision=near_dup_precision), axis=1)
        hash_counts = hashes.value_counts()
        # Rows that share a hash with at least one other row
        duplicated_hashes = hash_counts[hash_counts >= 2]
        near_dup_rows = int(duplicated_hashes.sum()) - len(
            duplicated_hashes
        )  # subtract one 'original' per bucket
        near_dup_pct = near_dup_rows / len(df)

        if near_dup_pct == 0:
            results.append(
                CheckResult.passed(
                    "duplicates.near",
                    "Duplicates",
                    "No near-duplicate rows detected.",
                    details={"near_duplicate_rows": 0},
                    confidence=0.85,
                )
            )
        elif near_dup_pct < cfg.near_dup_fail_pct:
            results.append(
                CheckResult.warn(
                    "duplicates.near",
                    "Duplicates",
                    f"{near_dup_rows} near-duplicate row(s) detected ({near_dup_pct:.1%} of data).",
                    details={
                        "near_duplicate_rows": near_dup_rows,
                        "near_duplicate_pct": round(near_dup_pct, 4),
                    },
                    confidence=min(0.9, 0.5 + near_dup_pct * 5),
                    penalty=cfg.near_warn_penalty,
                )
            )
        else:
            results.append(
                CheckResult.fail(
                    "duplicates.near",
                    "Duplicates",
                    f"{near_dup_rows} near-duplicate row(s) detected ({near_dup_pct:.1%} of data).",
                    details={
                        "near_duplicate_rows": near_dup_rows,
                        "near_duplicate_pct": round(near_dup_pct, 4),
                    },
                    confidence=min(1.0, 0.7 + near_dup_pct * 2),
                    penalty=cfg.near_fail_penalty,
                )
            )
    except Exception as exc:  # pragma: no cover
        results.append(
            CheckResult.warn(
                "duplicates.near",
                "Duplicates",
                f"Near-duplicate detection failed: {exc}",
                confidence=0.2,
                penalty=0.0,
            )
        )

    return results
