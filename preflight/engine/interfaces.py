"""
Interfaces for native policy-first checks.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd

from preflight.config import PreflightConfig
from preflight.model.finding import Finding


@dataclass(frozen=True)
class CheckContext:
    target: str | None
    config: PreflightConfig
    profile_name: str
    metadata: dict[str, Any]


class NativeCheck(Protocol):
    name: str

    def run(self, df: pd.DataFrame, context: CheckContext) -> list[Finding]: ...
