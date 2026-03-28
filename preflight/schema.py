"""
JSON schema contract helpers for RunReport payloads.
"""

from __future__ import annotations

from typing import Any

from preflight.model.report import SCHEMA_VERSION

TOP_LEVEL_REQUIRED = {"schema_version", "run", "dataset", "gate", "score", "summary", "findings"}
FINDING_REQUIRED = {
    "check_id",
    "title",
    "domain",
    "signal_strength",
    "severity",
    "suppressed",
    "affected_columns",
    "recommendations",
    "suggested_action",
    "docs_url",
    "tags",
    "details",
    "evidence",
}


def validate_run_report_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["payload must be an object"]

    missing_top = sorted(TOP_LEVEL_REQUIRED - set(payload.keys()))
    if missing_top:
        errors.append(f"missing top-level keys: {', '.join(missing_top)}")

    schema_version = payload.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        errors.append(
            f"unexpected schema_version: {schema_version!r} (expected {SCHEMA_VERSION!r})"
        )

    findings = payload.get("findings")
    if not isinstance(findings, list):
        errors.append("'findings' must be a list")
        return errors

    for idx, finding in enumerate(findings):
        if not isinstance(finding, dict):
            errors.append(f"findings[{idx}] must be an object")
            continue
        missing = sorted(FINDING_REQUIRED - set(finding.keys()))
        if missing:
            errors.append(f"findings[{idx}] missing keys: {', '.join(missing)}")
        evidence = finding.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"findings[{idx}].evidence must be an object")

    return errors
