"""
Native type-sanity check emitting policy-first findings.
"""

from __future__ import annotations

import pandas as pd

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "types"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    cfg = context.config.types
    object_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
    if not object_cols:
        return [
            Finding(
                check_id="types.sanity",
                title="No object/string columns found.",
                domain=Domain.SCHEMA_CONTRACT,
                signal_strength="low",
                confidence=1.0,
                evidence=Evidence(metrics={"object_columns": 0}),
                severity=Severity.INFO,
            )
        ]

    numeric_as_object: list[str] = []
    mixed_types: list[str] = []

    for col in object_cols:
        sample = df[col].dropna().head(cfg.numeric_sample_size)
        if len(sample) == 0:
            continue
        parsed = pd.to_numeric(sample, errors="coerce")
        if float(parsed.notna().mean()) >= cfg.numeric_parse_threshold:
            numeric_as_object.append(str(col))
            continue
        type_count = len({type(v).__name__ for v in sample})
        if type_count >= 3:
            mixed_types.append(str(col))

    if numeric_as_object:
        severity = Severity.WARN
        signal = "medium"
    elif mixed_types:
        severity = Severity.WARN
        signal = "medium"
    else:
        severity = Severity.INFO
        signal = "low"

    return [
        Finding(
            check_id="types.sanity",
            title=(
                f"Detected {len(numeric_as_object)} numeric-as-object and "
                f"{len(mixed_types)} mixed-type column(s)."
                if (numeric_as_object or mixed_types)
                else "No major object/string type issues detected."
            ),
            domain=Domain.SCHEMA_CONTRACT,
            signal_strength=signal,
            confidence=0.85,
            evidence=Evidence(
                metrics={
                    "object_columns": len(object_cols),
                    "numeric_as_object": len(numeric_as_object),
                    "mixed_types": len(mixed_types),
                },
                samples={
                    "numeric_as_object_columns": numeric_as_object[:20],
                    "mixed_type_columns": mixed_types[:20],
                },
            ),
            affected_columns=sorted(set(numeric_as_object + mixed_types)),
            recommendations=[
                "Cast numeric-like columns to numeric dtype.",
                "Normalize mixed-type columns upstream in ETL.",
            ],
            severity=severity,
        )
    ]
