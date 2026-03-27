"""
Baseline comparison utilities for run report JSON artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CompareResult:
    status: str
    reasons: list[str]
    summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "reasons": self.reasons,
            "summary": self.summary,
        }


def compare_reports(
    current: dict[str, Any],
    baseline: dict[str, Any],
    *,
    max_score_drop: float = 5.0,
    fail_on_new_critical: bool = True,
    fail_on_new_error: bool = False,
    domain_increase_thresholds: dict[str, int] | None = None,
) -> CompareResult:
    reasons: list[str] = []
    status = "PASS"

    curr_score = _extract_score(current)
    base_score = _extract_score(baseline)
    if curr_score is not None and base_score is not None:
        drop = base_score - curr_score
        if drop > max_score_drop:
            reasons.append(
                f"Heuristic score dropped by {drop:.1f} (baseline={base_score:.1f}, current={curr_score:.1f})."
            )
            status = "FAIL"
    else:
        drop = None

    curr_crit = _count_severity(current, "critical")
    base_crit = _count_severity(baseline, "critical")
    new_critical = max(0, curr_crit - base_crit)
    if fail_on_new_critical and new_critical > 0:
        reasons.append(
            f"{new_critical} new critical finding(s) compared to baseline "
            f"(baseline={base_crit}, current={curr_crit})."
        )
        status = "FAIL"

    curr_error = _count_severity(current, "error")
    base_error = _count_severity(baseline, "error")
    new_error = max(0, curr_error - base_error)
    if fail_on_new_error and new_error > 0:
        reasons.append(
            f"{new_error} new error finding(s) compared to baseline "
            f"(baseline={base_error}, current={curr_error})."
        )
        status = "FAIL"

    domain_deltas = _domain_deltas(current, baseline)
    for domain, threshold in (domain_increase_thresholds or {}).items():
        delta = domain_deltas.get(domain, 0)
        if delta > threshold:
            reasons.append(
                f"Domain '{domain}' increased by {delta} finding(s), threshold={threshold}."
            )
            status = "FAIL"

    summary = {
        "baseline_score": base_score,
        "current_score": curr_score,
        "score_drop": drop,
        "baseline_critical": base_crit,
        "current_critical": curr_crit,
        "new_critical": new_critical,
        "baseline_error": base_error,
        "current_error": curr_error,
        "new_error": new_error,
        "domain_deltas": domain_deltas,
    }
    return CompareResult(status=status, reasons=reasons, summary=summary)


def _extract_score(payload: dict[str, Any]) -> float | None:
    score = payload.get("score")
    if isinstance(score, dict):
        value = score.get("value")
        if isinstance(value, (float, int)):
            return float(value)
    elif isinstance(score, (float, int)):
        return float(score)
    return None


def _count_severity(payload: dict[str, Any], severity: str) -> int:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        sev = summary.get("severity_counts")
        if isinstance(sev, dict):
            value = sev.get(severity)
            if isinstance(value, int):
                return value
    findings = payload.get("findings")
    if isinstance(findings, list):
        return sum(
            1
            for finding in findings
            if isinstance(finding, dict) and finding.get("severity") == severity
        )
    return 0


def _domain_deltas(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, int]:
    curr = _domain_counts(current)
    base = _domain_counts(baseline)
    out: dict[str, int] = {}
    for domain in set(curr) | set(base):
        out[domain] = curr.get(domain, 0) - base.get(domain, 0)
    return out


def _domain_counts(payload: dict[str, Any]) -> dict[str, int]:
    summary = payload.get("summary")
    if isinstance(summary, dict):
        domain_counts = summary.get("domain_counts")
        if isinstance(domain_counts, dict):
            out: dict[str, int] = {}
            for key, value in domain_counts.items():
                if isinstance(key, str) and isinstance(value, int):
                    out[key] = value
            return out
    findings = payload.get("findings")
    counts: dict[str, int] = {}
    if isinstance(findings, list):
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            domain = finding.get("domain")
            if isinstance(domain, str):
                counts[domain] = counts.get(domain, 0) + 1
    return counts
