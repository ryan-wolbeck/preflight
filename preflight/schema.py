"""
JSON schema contract helpers for RunReport payloads.
"""

from __future__ import annotations

from typing import Any

from preflight.model.finding import Domain, Severity
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
ALLOWED_GATE_STATUS = {"PASS", "FAIL"}
ALLOWED_SIGNAL_STRENGTH = {"low", "medium", "high"}
ALLOWED_SEVERITY = {item.value for item in Severity}
ALLOWED_DOMAIN = {item.value for item in Domain}


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

    gate = payload.get("gate")
    if not isinstance(gate, dict):
        errors.append("'gate' must be an object")
    else:
        status = gate.get("status")
        if status not in ALLOWED_GATE_STATUS:
            errors.append(f"gate.status must be one of {sorted(ALLOWED_GATE_STATUS)}")
        reasons = gate.get("reasons")
        if not isinstance(reasons, list) or not all(isinstance(item, str) for item in reasons):
            errors.append("gate.reasons must be a list[str]")

    score = payload.get("score")
    if not isinstance(score, dict):
        errors.append("'score' must be an object")
    else:
        if not isinstance(score.get("enabled"), bool):
            errors.append("score.enabled must be boolean")
        if not isinstance(score.get("value"), (int, float)):
            errors.append("score.value must be numeric")
        if not isinstance(score.get("label"), str):
            errors.append("score.label must be string")
        if not isinstance(score.get("profile"), str):
            errors.append("score.profile must be string")

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
        severity = finding.get("severity")
        if severity not in ALLOWED_SEVERITY:
            errors.append(f"findings[{idx}].severity must be one of {sorted(ALLOWED_SEVERITY)}")
        domain = finding.get("domain")
        if domain not in ALLOWED_DOMAIN:
            errors.append(f"findings[{idx}].domain must be one of {sorted(ALLOWED_DOMAIN)}")
        signal_strength = finding.get("signal_strength")
        if signal_strength not in ALLOWED_SIGNAL_STRENGTH:
            errors.append(
                f"findings[{idx}].signal_strength must be one of {sorted(ALLOWED_SIGNAL_STRENGTH)}"
            )
        evidence = finding.get("evidence")
        if not isinstance(evidence, dict):
            errors.append(f"findings[{idx}].evidence must be an object")
        else:
            if not isinstance(evidence.get("metrics"), dict):
                errors.append(f"findings[{idx}].evidence.metrics must be an object")

    return errors
