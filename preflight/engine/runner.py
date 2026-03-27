"""
Execution engine for running registered checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import pandas as pd

from preflight.config import PreflightConfig
from preflight.engine.adapters import finding_from_check_result
from preflight.engine.interfaces import CheckContext
from preflight.engine.registry import RegisteredCheck, default_registry
from preflight.model.finding import Domain, Evidence, Finding, Severity


@dataclass(frozen=True)
class RunContext:
    target: str | None
    config: PreflightConfig
    profile_name: str


def prepare_runtime_df(df: pd.DataFrame, config: PreflightConfig) -> pd.DataFrame:
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


def run_registered_checks(
    df: pd.DataFrame,
    context: RunContext,
    registry: list[RegisteredCheck] | None = None,
) -> tuple[list[Finding], pd.DataFrame]:
    checks = registry or default_registry()
    sampled_df = prepare_runtime_df(df, context.config)
    findings: list[Finding] = []
    native_context = CheckContext(
        target=context.target,
        config=context.config,
        profile_name=context.profile_name,
        metadata={
            "rows_total": len(df),
            "rows_analyzed": len(sampled_df),
            "sampling_applied": len(df) != len(sampled_df),
        },
    )

    for registered_check in checks:
        if not context.config.enabled_checks.get(registered_check.name, True):
            continue
        try:
            if registered_check.kind == "legacy":
                if registered_check.run_legacy is None:
                    raise RuntimeError("legacy check missing run_legacy callable")
                results = registered_check.run_legacy(sampled_df, context.target, context.config)
                findings.extend(finding_from_check_result(result) for result in results)
            else:
                if registered_check.run_native is None:
                    raise RuntimeError("native check missing run_native callable")
                findings.extend(registered_check.run_native(sampled_df, native_context))
        except Exception as exc:
            findings.append(
                Finding(
                    check_id=f"{registered_check.name}.execution_error",
                    title=f"Check execution failed: {exc}",
                    domain=Domain.ADVISORY,
                    signal_strength="high",
                    confidence=1.0,
                    evidence=Evidence(
                        metrics={"check": registered_check.name, "source": registered_check.source}
                    ),
                    recommendations=["Inspect stack trace and check input data types."],
                    severity=Severity.ERROR,
                    details={
                        "exception": repr(exc),
                        "check_name": registered_check.name,
                        "check_source": registered_check.source,
                    },
                )
            )

    findings.sort(key=lambda finding: finding.check_id)
    return findings, sampled_df


def extract_dataset_meta(
    df: pd.DataFrame, sampled_df: pd.DataFrame, target: str | None
) -> dict[str, Any]:
    return {
        "rows": len(df),
        "cols": len(df.columns),
        "target": target,
        "rows_analyzed": len(sampled_df),
        "sampling_applied": len(df) != len(sampled_df),
    }
