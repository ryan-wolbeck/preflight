"""
Adapters from legacy CheckResult objects into policy-first Finding objects.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from preflight._types import CheckResult, Severity as LegacySeverity
from preflight.constants import CATEGORY_TO_DOMAIN
from preflight.model.finding import Domain, Evidence, Finding, Severity


def domain_from_category(category: str) -> Domain:
    return CATEGORY_TO_DOMAIN.get(category, Domain.ADVISORY)


def _signal_strength_from_legacy(result: CheckResult) -> str:
    if result.severity == LegacySeverity.FAIL:
        return "high"
    if result.severity == LegacySeverity.WARN:
        return "medium"
    return "low"


def _severity_from_legacy(result: CheckResult) -> Severity:
    if result.severity == LegacySeverity.FAIL:
        return Severity.ERROR
    if result.severity == LegacySeverity.WARN:
        return Severity.WARN
    return Severity.INFO


def _extract_affected_columns(details: Any) -> list[str]:
    if isinstance(details, dict):
        cols = details.get("columns")
        if isinstance(cols, dict):
            return [str(c) for c in cols.keys()]
        if isinstance(cols, (list, tuple, set)):
            out: list[str] = []
            for item in cols:
                if isinstance(item, str):
                    out.append(item)
                elif isinstance(item, dict) and "column" in item:
                    out.append(str(item["column"]))
            return out
    return []


def _recommendations_for(result: CheckResult) -> list[str]:
    if isinstance(result.details, dict):
        raw = result.details.get("recommendations")
        if isinstance(raw, list):
            recommendations = [str(item) for item in raw if str(item).strip()]
            if recommendations:
                return recommendations
    cid = result.check_id
    if cid.startswith("completeness.") or cid.startswith("split.missingness"):
        return [
            "Investigate missingness mechanism",
            "Impute or drop problematic columns with rationale",
        ]
    if cid.startswith("leakage."):
        return [
            "Remove leakage-prone features from training",
            "Rebuild features with leakage-safe time/group cutoffs",
        ]
    if cid.startswith("duplicates."):
        return [
            "Deduplicate training data before split",
            "Track duplicate source in ingestion pipeline",
        ]
    if cid.startswith("split."):
        return [
            "Review split strategy and sampling",
            "Add drift monitoring to data refresh pipeline",
        ]
    return ["Review this finding and document expected behavior or remediation."]


def _docs_url_for(result: CheckResult) -> str:
    category_slug = result.category.lower().replace("/", "-").replace(" ", "-")
    return f"https://github.com/preflight-ml/preflight/blob/main/docs/checks/{category_slug}.md"


def finding_from_check_result(result: CheckResult) -> Finding:
    metrics: dict[str, float | int | str | bool] = {}
    if isinstance(result.details, dict):
        for key, value in result.details.items():
            if isinstance(value, (int, float, str, bool)):
                metrics[key] = value
    recommendations = _recommendations_for(result)
    suggested_action: str | None = recommendations[0] if recommendations else None
    if isinstance(result.details, dict):
        raw_action = result.details.get("suggested_action")
        if isinstance(raw_action, str) and raw_action.strip():
            suggested_action = raw_action

    finding = Finding(
        check_id=result.check_id,
        title=result.message,
        domain=domain_from_category(result.category),
        signal_strength=_signal_strength_from_legacy(result),
        confidence=result.confidence,
        evidence=Evidence(
            metrics=metrics, samples=result.details if isinstance(result.details, dict) else None
        ),
        affected_columns=_extract_affected_columns(result.details),
        recommendations=recommendations,
        suggested_action=suggested_action,
        docs_url=_docs_url_for(result),
        details={"legacy_category": result.category, "legacy_penalty": result.penalty},
        severity=_severity_from_legacy(result),
    )
    # Preserve immutable data model guarantees for future policy remapping.
    return replace(finding)
