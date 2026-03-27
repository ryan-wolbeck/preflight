"""
Policy-first public API.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from preflight.checks_native import run_split_checks
from preflight.config import PreflightConfig
from preflight.engine.runner import (
    RunContext,
    extract_dataset_meta,
    prepare_runtime_df,
    run_registered_checks,
)
from preflight.model.policy import Policy
from preflight.model.report import RunMeta, RunReport
from preflight.policy import Suppression, choose_profile, evaluate


def run(
    df: pd.DataFrame,
    *,
    target: str | None = None,
    profile: str | Policy = "exploratory",
    config: PreflightConfig | None = None,
    suppressions: list[Suppression] | None = None,
) -> RunReport:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"preflight.run() expects a pandas DataFrame, got {type(df).__name__}")

    cfg = config or PreflightConfig()
    selected_policy = _resolve_policy(profile)
    ctx = RunContext(target=target, config=cfg, profile_name=selected_policy.name)
    findings, sampled_df = run_registered_checks(df, ctx)
    evaluation = evaluate(findings, selected_policy, suppressions=suppressions)
    meta_dict = extract_dataset_meta(df, sampled_df, target)
    meta = RunMeta(
        profile=selected_policy.name,
        rows_total=meta_dict["rows"],
        columns_total=meta_dict["cols"],
        rows_analyzed=meta_dict["rows_analyzed"],
        sampling_applied=meta_dict["sampling_applied"],
        target=target,
    )
    return RunReport(
        meta=meta,
        findings=evaluation.findings,
        gate=evaluation.gate,
        score=evaluation.score,
    )


def run_split(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    *,
    profile: str | Policy = "exploratory",
    config: PreflightConfig | None = None,
    suppressions: list[Suppression] | None = None,
) -> RunReport:
    if not isinstance(X_train, pd.DataFrame) or not isinstance(X_test, pd.DataFrame):
        raise TypeError("preflight.run_split() requires two pandas DataFrames.")

    cfg = config or PreflightConfig()
    selected_policy = _resolve_policy(profile)
    sampled_train = prepare_runtime_df(X_train, cfg)
    sampled_test = prepare_runtime_df(X_test, cfg)
    findings = run_split_checks(sampled_train, sampled_test, cfg)
    evaluation = evaluate(findings, selected_policy, suppressions=suppressions)
    meta = RunMeta(
        profile=selected_policy.name,
        rows_total=len(X_train) + len(X_test),
        columns_total=len(X_train.columns.intersection(X_test.columns)),
        rows_analyzed=len(sampled_train) + len(sampled_test),
        sampling_applied=len(sampled_train) != len(X_train) or len(sampled_test) != len(X_test),
        target=None,
    )
    return RunReport(
        meta=meta,
        findings=evaluation.findings,
        gate=evaluation.gate,
        score=evaluation.score,
    )


def _resolve_policy(profile: str | Policy) -> Policy:
    if isinstance(profile, Policy):
        return profile
    return choose_profile(profile)


def run_to_dict(
    df: pd.DataFrame,
    *,
    target: str | None = None,
    profile: str | Policy = "exploratory",
    config: PreflightConfig | None = None,
    suppressions: list[Suppression] | None = None,
) -> dict[str, Any]:
    return run(
        df, target=target, profile=profile, config=config, suppressions=suppressions
    ).to_dict()
