"""
Check registry for the policy-first runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points
import os
from typing import Any, Callable, Literal, Optional

import pandas as pd

from preflight._types import CheckResult
from preflight.checks_native import (
    balance_name,
    balance_run,
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
from preflight.config import PreflightConfig
from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Finding

NATIVE_PLUGIN_GROUP = "preflight.checks"
LEGACY_PLUGIN_GROUP = "preflight.checks.legacy"

CheckCallable = Callable[[pd.DataFrame, Optional[str], PreflightConfig], list[CheckResult]]
NativeCheckCallable = Callable[[pd.DataFrame, CheckContext], list[Finding]]


@dataclass(frozen=True)
class RegisteredCheck:
    name: str
    kind: Literal["legacy", "native"]
    run_legacy: Optional[CheckCallable] = None
    run_native: Optional[NativeCheckCallable] = None
    source: str = "builtin"


def default_registry() -> list[RegisteredCheck]:
    checks: list[RegisteredCheck] = [
        RegisteredCheck(balance_name, kind="native", run_native=balance_run),
        RegisteredCheck(completeness_name, kind="native", run_native=completeness_run),
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
    diagnostics = discover_entrypoint_plugins(group=group, plugin_mode="native")
    if _legacy_plugin_fallback_enabled():
        diagnostics.extend(
            discover_entrypoint_plugins(group=LEGACY_PLUGIN_GROUP, plugin_mode="legacy")
        )
    out: list[RegisteredCheck] = []
    for item in diagnostics:
        if item.get("status") != "loaded":
            continue
        check = item.get("check")
        if isinstance(check, RegisteredCheck):
            out.append(check)
    return out


def discover_entrypoint_plugins(
    group: str = NATIVE_PLUGIN_GROUP,
    *,
    plugin_mode: Literal["native", "legacy"] = "native",
) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    try:
        eps = entry_points()
        group_entries: list[EntryPoint]
        if hasattr(eps, "select"):
            group_entries = list(eps.select(group=group))
        else:
            get_method = getattr(eps, "get", None)
            group_entries = list(get_method(group, [])) if callable(get_method) else []
    except Exception:
        return diagnostics

    for ep in group_entries:
        try:
            loaded = ep.load()
            if isinstance(loaded, RegisteredCheck):
                if loaded.kind == "legacy" and plugin_mode != "legacy":
                    diagnostics.append(
                        {
                            "name": ep.name,
                            "source": ep.value,
                            "status": "error",
                            "error": (
                                "Legacy plugin entry points are disabled in the native plugin "
                                "group. Use preflight.checks.legacy and set "
                                "PREFLIGHT_ENABLE_LEGACY_PLUGIN_ENTRYPOINTS=1."
                            ),
                        }
                    )
                    continue
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
                if plugin_mode == "legacy":
                    plugin_check = RegisteredCheck(
                        name=ep.name,
                        kind="legacy",
                        run_legacy=loaded,  # plugin contract: callable(df, target, cfg) -> list[CheckResult]
                        source=ep.value,
                    )
                    kind = "legacy"
                else:
                    plugin_check = RegisteredCheck(
                        name=ep.name,
                        kind="native",
                        run_native=loaded,  # plugin contract: callable(df, context) -> list[Finding]
                        source=ep.value,
                    )
                    kind = "native"
                diagnostics.append(
                    {
                        "name": ep.name,
                        "source": ep.value,
                        "status": "loaded",
                        "kind": kind,
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


def _legacy_plugin_fallback_enabled() -> bool:
    token = os.getenv("PREFLIGHT_ENABLE_LEGACY_PLUGIN_ENTRYPOINTS", "").strip().lower()
    return token in {"1", "true", "yes", "on"}
