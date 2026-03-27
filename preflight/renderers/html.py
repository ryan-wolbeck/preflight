"""
Simple HTML renderer for policy-first RunReport.
"""

from __future__ import annotations

import html

from preflight.model.report import RunReport


def render(report: RunReport) -> str:
    rows = []
    for finding in report.findings:
        sev = html.escape(finding.severity.value)
        check_id = html.escape(finding.check_id)
        domain = html.escape(finding.domain.value)
        title = html.escape(finding.title)
        conf = "n/a" if finding.confidence is None else f"{finding.confidence:.2f}"
        suppressed = "yes" if finding.suppressed else "no"
        rows.append(
            "<tr>"
            f"<td>{sev}</td><td>{check_id}</td><td>{domain}</td>"
            f"<td>{title}</td><td>{conf}</td><td>{suppressed}</td>"
            "</tr>"
        )
    table_rows = "\n".join(rows)
    reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in report.gate.reasons)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Preflight Run Report</title>
  <style>
    body {{ font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px; color: #111; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 13px; }}
    th {{ background: #f5f5f5; }}
    .meta {{ margin-bottom: 12px; }}
    .gate-pass {{ color: #0a7f2e; }}
    .gate-fail {{ color: #b00020; }}
  </style>
</head>
<body>
  <h1>Preflight Run Report</h1>
  <div class="meta">
    <div><strong>Profile:</strong> {html.escape(report.meta.profile)}</div>
    <div><strong>Gate:</strong> <span class="{'gate-fail' if report.gate.status == 'FAIL' else 'gate-pass'}">{html.escape(report.gate.status)}</span></div>
    <div><strong>Score (heuristic):</strong> {report.score:.1f}/100</div>
    <div><strong>Rows analyzed:</strong> {report.meta.rows_analyzed:,} / {report.meta.rows_total:,}</div>
  </div>
  <h2>Gate Reasons</h2>
  <ul>{reasons}</ul>
  <h2>Findings</h2>
  <table>
    <thead>
      <tr><th>Severity</th><th>Check ID</th><th>Domain</th><th>Title</th><th>Confidence</th><th>Suppressed</th></tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</body>
</html>"""
