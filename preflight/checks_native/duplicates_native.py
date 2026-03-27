"""
Native duplicate checks emitting policy-first findings.
"""

from __future__ import annotations

import pandas as pd

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "duplicates"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    del context
    if len(df) < 2:
        return [
            Finding(
                check_id="duplicates.exact",
                title="Duplicate checks skipped for fewer than 2 rows.",
                domain=Domain.DATA_QUALITY,
                signal_strength="low",
                confidence=1.0,
                evidence=Evidence(metrics={"rows": int(len(df))}),
                severity=Severity.INFO,
            )
        ]

    exact_dupes = int(df.duplicated().sum())
    rate = exact_dupes / max(1, len(df))
    if rate >= 0.01:
        severity = Severity.ERROR
        signal = "high"
    elif exact_dupes > 0:
        severity = Severity.WARN
        signal = "medium"
    else:
        severity = Severity.INFO
        signal = "low"

    return [
        Finding(
            check_id="duplicates.exact",
            title=(
                f"{exact_dupes} exact duplicate row(s) detected ({rate:.1%})."
                if exact_dupes
                else "No exact duplicate rows detected."
            ),
            domain=Domain.DATA_QUALITY,
            signal_strength=signal,
            confidence=0.95,
            evidence=Evidence(
                metrics={"duplicate_rows": exact_dupes, "duplicate_rate": round(rate, 6)}
            ),
            recommendations=[
                "Deduplicate rows prior to model training.",
                "Trace duplicate source in data ingestion pipeline.",
            ],
            severity=severity,
        )
    ]
