"""
Legacy compatibility namespace.

This module contains the legacy report/scoring surface used by
`preflight.check()` and `preflight.check_split()`.
"""

from preflight._types import CheckResult, Severity
from preflight.legacy.api import check, check_split
from preflight.report import Report
from preflight.scorer import compute_score

__all__ = [
    "check",
    "check_split",
    "CheckResult",
    "Severity",
    "Report",
    "compute_score",
]
