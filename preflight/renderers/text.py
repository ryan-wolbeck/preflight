"""
Text renderer for RunReport.
"""

from __future__ import annotations

from preflight.model.finding import Severity
from preflight.model.report import RunReport


def render(report: RunReport) -> str:
    lines: list[str] = []
    lines.append("Preflight Run Report")
    lines.append("─" * 56)
    lines.append(f"Gate: {report.gate.status}")
    lines.append(f"Heuristic Score: {report.score:.1f}/100")
    lines.append(f"Profile: {report.meta.profile}")
    lines.append(
        f"Dataset: {report.meta.rows_analyzed:,}/{report.meta.rows_total:,} rows analyzed "
        f"across {report.meta.columns_total} columns"
    )
    if report.meta.target:
        lines.append(f"Target: {report.meta.target}")

    counts = report.summary["severity_counts"]
    lines.append(
        "Summary: "
        f"{counts[Severity.INFO.value]} info, "
        f"{counts[Severity.WARN.value]} warn, "
        f"{counts[Severity.ERROR.value]} error, "
        f"{counts[Severity.CRITICAL.value]} critical"
    )

    if report.gate.reasons:
        lines.append("")
        lines.append("Gate reasons:")
        for reason in report.gate.reasons:
            lines.append(f"- {reason}")

    lines.append("")
    lines.append("Findings:")
    for finding in report.findings:
        sev = finding.severity.value.upper()
        confidence = "n/a" if finding.confidence is None else f"{finding.confidence:.2f}"
        lines.append(f"- [{sev}] {finding.check_id}: {finding.title} (confidence={confidence})")
    return "\n".join(lines)
