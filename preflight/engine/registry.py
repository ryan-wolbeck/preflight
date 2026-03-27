"""
Check registry for the policy-first runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
from typing import Any, Callable, Literal

import pandas as pd

from preflight._types import CheckResult
from preflight.checks_native import (
    completeness_name,
    completeness_run,
    correlations_name,
    correlations_run,
    distributions_name,
    distributions_run,
    duplicates_name,
    duplicates_run,
    fingerprint_name,
    fingerprint_run,
    leakage_name,
    leakage_run,
    types_name,
    types_run,
)
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
from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Finding

CheckCallable = Callable[[pd.DataFrame, str | None, PreflightConfig], list[CheckResult]]
NativeCheckCallable = Callable[[pd.DataFrame, CheckContext], list[Finding]]


@dataclass(frozen=True)
class RegisteredCheck:
    name: str
    kind: Literal["legacy", "native"]
    run_legacy: CheckCallable | None = None
    run_native: NativeCheckCallable | None = None
    source: str = "builtin"


def _run_completeness(
    df: pd.DataFrame, target: str | None, cfg: PreflightConfig
) -> list[CheckResult]:
    return completeness.run(df, target=target, config=cfg.completeness)


def _run_balance(df: pd.DataFrame, target: str | None, cfg: PreflightConfig) -> list[CheckResult]:
    return balance.run(df, target=target, config=cfg.balance)


def _run_leakage(df: pd.DataFrame, target: str | None, cfg: PreflightConfig) -> list[CheckResult]:
    return leakage.run(df, target=target, config=cfg.leakage)


def _run_duplicates(
    df: pd.DataFrame, target: str | None, cfg: PreflightConfig
) -> list[CheckResult]:
    del target
    return duplicates.run(df, config=cfg.duplicates)


def _run_distributions(
    df: pd.DataFrame, target: str | None, cfg: PreflightConfig
) -> list[CheckResult]:
    return distributions.run(df, target=target, config=cfg.distributions)


def _run_correlations(
    df: pd.DataFrame, target: str | None, cfg: PreflightConfig
) -> list[CheckResult]:
    return correlations.run(df, target=target, config=cfg.correlations)


def _run_types(df: pd.DataFrame, target: str | None, cfg: PreflightConfig) -> list[CheckResult]:
    return types_check.run(df, target=target, config=cfg.types)


def default_registry() -> list[RegisteredCheck]:
    checks: list[RegisteredCheck] = [
        RegisteredCheck(completeness_name, kind="native", run_native=completeness_run),
        RegisteredCheck("balance", kind="legacy", run_legacy=_run_balance),
        RegisteredCheck(leakage_name, kind="native", run_native=leakage_run),
        RegisteredCheck(duplicates_name, kind="native", run_native=duplicates_run),
        RegisteredCheck(distributions_name, kind="native", run_native=distributions_run),
        RegisteredCheck(correlations_name, kind="native", run_native=correlations_run),
        RegisteredCheck(types_name, kind="native", run_native=types_run),
        RegisteredCheck(fingerprint_name, kind="native", run_native=fingerprint_run),
    ]
    checks.extend(load_entrypoint_checks())
    return checks


def load_entrypoint_checks(group: str = "preflight.checks") -> list[RegisteredCheck]:
    diagnostics = discover_entrypoint_plugins(group=group)
    out: list[RegisteredCheck] = []
    for item in diagnostics:
        if item.get("status") != "loaded":
            continue
        check = item.get("check")
        if isinstance(check, RegisteredCheck):
            out.append(check)
    return out


def discover_entrypoint_plugins(group: str = "preflight.checks") -> list[dict[str, Any]]:
    discovered: list[RegisteredCheck] = []
    diagnostics: list[dict[str, Any]] = []
    try:
        eps = entry_points()
        group_entries: list[EntryPoint]
        if hasattr(eps, "select"):
            group_entries = list(eps.select(group=group))
        else:
            group_entries = list(eps.get(group, []))  # type: ignore[union-attr]
    except Exception:
        return diagnostics

    for ep in group_entries:
        try:
            loaded = ep.load()
            if isinstance(loaded, RegisteredCheck):
                diagnostics.append(
                    {
                        "name": ep.name,
                        "source": ep.value,
                        "status": "loaded",
                        "kind": loaded.kind,
                        "check": loaded,
                    }
                )
                continue
            if callable(loaded):
                plugin_check = RegisteredCheck(
                    name=ep.name,
                    kind="native",
                    run_native=loaded,  # plugin contract: callable(df, context) -> list[Finding]
                    source=ep.value,
                )
                diagnostics.append(
                    {
                        "name": ep.name,
                        "source": ep.value,
                        "status": "loaded",
                        "kind": "native",
                        "check": plugin_check,
                    }
                )
                continue
            diagnostics.append(
                {
                    "name": ep.name,
                    "source": ep.value,
                    "status": "error",
                    "error": "Entry point did not return a RegisteredCheck or callable",
                }
            )
        except Exception:
            diagnostics.append(
                {
                    "name": ep.name,
                    "source": ep.value,
                    "status": "error",
                    "error": "Failed to load entry point",
                }
            )
    return diagnostics
