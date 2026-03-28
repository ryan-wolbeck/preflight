"""
preflight — dataset readiness checker for machine learning.

Quick start
-----------
    import preflight

    run_report = preflight.run(df, target="churn", profile="ci-balanced")
    print(run_report)       # terminal summary + policy gate
    run_report.to_dict()    # machine-readable

    # Split integrity check
    split_run_report = preflight.run_split(X_train, X_test, profile="ci-balanced")
    print(split_run_report)

Legacy API:
    report = preflight.check(df, target="churn")
    split_report = preflight.check_split(X_train, X_test)
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import Optional

import pandas as pd

from preflight.config import PreflightConfig
from preflight._types import CheckResult, Severity
from preflight.legacy import api as legacy_api
from preflight.model import Policy, RunReport
from preflight.report import Report

try:
    __version__ = version("preflight-data")
except PackageNotFoundError:  # pragma: no cover - local editable/uninstalled edge case
    __version__ = "0+unknown"
__all__ = [
    "run",
    "run_split",
    "check",
    "check_split",
    "Report",
    "RunReport",
    "Policy",
    "CheckResult",
    "Severity",
    "PreflightConfig",
]


from preflight.api import run, run_split  # noqa: E402

_compute_psi = legacy_api._compute_psi


def check(
    df: pd.DataFrame,
    target: Optional[str] = None,
    config: PreflightConfig | None = None,
) -> Report:
    return legacy_api.check(df=df, target=target, config=config)


def check_split(
    X_train: pd.DataFrame,
    X_test: pd.DataFrame,
    threshold_psi: float = 0.2,
    config: PreflightConfig | None = None,
) -> Report:
    # Keep monkeypatch compatibility for tests and downstream users that patch
    # `preflight._compute_psi` directly.
    legacy_api._compute_psi = _compute_psi
    return legacy_api.check_split(
        X_train=X_train,
        X_test=X_test,
        threshold_psi=threshold_psi,
        config=config,
    )
