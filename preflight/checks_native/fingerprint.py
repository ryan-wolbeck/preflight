"""
Native policy-first check: dataset fingerprint advisory.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding, Severity

name = "dataset_fingerprint"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    cols = [str(col) for col in df.columns]
    dtypes = [str(df[col].dtype) for col in df.columns]
    payload = "|".join(cols) + "||" + "|".join(dtypes)
    fingerprint = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return [
        Finding(
            check_id="dataset.fingerprint",
            title="Dataset fingerprint computed.",
            domain=Domain.ADVISORY,
            signal_strength="low",
            confidence=1.0,
            evidence=Evidence(
                metrics={
                    "rows": int(len(df)),
                    "cols": int(len(df.columns)),
                    "fingerprint_prefix": fingerprint,
                }
            ),
            recommendations=["Track this fingerprint across runs to detect schema-level changes."],
            severity=Severity.INFO,
            details={"profile": context.profile_name},
        )
    ]
