"""
JSON payload helper for RunReport.
"""

from __future__ import annotations

import json

from preflight.model.report import RunReport


def render(report: RunReport, indent: int = 2) -> str:
    return json.dumps(report.to_dict(), indent=indent, default=str)
