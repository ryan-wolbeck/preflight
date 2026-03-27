"""
Markdown renderer for RunReport.
"""

from __future__ import annotations

from preflight.model.report import RunReport


def render(report: RunReport) -> str:
    lines: list[str] = []
    lines.append("## Preflight Run Report")
    lines.append("")
    lines.append(f"- **Gate:** `{report.gate.status}`")
    lines.append(f"- **Heuristic score:** `{report.score:.1f}/100`")
    lines.append(f"- **Profile:** `{report.meta.profile}`")
    lines.append(
        f"- **Rows analyzed:** `{report.meta.rows_analyzed:,}` / `{report.meta.rows_total:,}`"
    )
    lines.append(f"- **Columns:** `{report.meta.columns_total}`")
    if report.meta.target:
        lines.append(f"- **Target:** `{report.meta.target}`")
    lines.append("")
    lines.append("### Findings")
    lines.append("")
    lines.append("| Severity | Check | Domain | Title |")
    lines.append("|---|---|---|---|")
    for finding in report.findings:
        lines.append(
            f"| `{finding.severity.value}` | `{finding.check_id}` | `{finding.domain.value}` | "
            f"{finding.title} |"
        )
    return "\n".join(lines)
