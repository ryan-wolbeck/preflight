"""
Report class
============
Wraps a list of CheckResult objects + score into a human-readable and
machine-readable output object.
"""

from __future__ import annotations

from typing import Any

from preflight._types import CheckResult, Severity

SCHEMA_VERSION = "1.1.0"

# ANSI color codes (used only in terminal output)
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_RESET = "\033[0m"
_BOLD = "\033[1m"

_ICONS = {
    Severity.PASS: "✓",
    Severity.WARN: "⚠",
    Severity.FAIL: "✗",
}

_VERDICT_ICONS = {
    "READY": "✓",
    "CAUTION": "⚠",
    "NOT READY": "✗",
}

_VERDICT_COLORS = {
    "READY": _GREEN,
    "CAUTION": _YELLOW,
    "NOT READY": _RED,
}

_SEV_COLORS = {
    Severity.PASS: _GREEN,
    Severity.WARN: _YELLOW,
    Severity.FAIL: _RED,
}


class Report:
    """
    The result of a preflight.check() call.

    Attributes
    ----------
    score   : float — readiness score 0–100
    verdict : str   — "READY" | "CAUTION" | "NOT READY"
    checks  : list[CheckResult]
    """

    def __init__(
        self,
        checks: list[CheckResult],
        score: float,
        verdict: str,
        metadata: dict | None = None,
    ) -> None:
        self.checks = checks
        self.score = round(score, 1)
        self.verdict = verdict
        self.metadata: dict[str, Any] = metadata or {}

    # ── Human-readable terminal output ───────────────────────────────────────

    def __str__(self) -> str:
        lines: list[str] = []
        width = 48

        verdict_color = _VERDICT_COLORS.get(self.verdict, "")
        verdict_icon = _VERDICT_ICONS.get(self.verdict, "")

        lines.append(f"\n{_BOLD}Preflight Report{_RESET}")
        lines.append("─" * width)
        lines.append(
            f"{_BOLD}Readiness Score: {self.score:.0f}/100  "
            f"{verdict_color}{verdict_icon} {self.verdict}{_RESET}"
        )
        lines.append("─" * width)

        # Group by category
        categories: dict[str, list[CheckResult]] = {}
        for r in self.checks:
            categories.setdefault(r.category, []).append(r)

        for cat, cat_results in categories.items():
            lines.append(f"\n{_BOLD}{cat}{_RESET}")
            for r in cat_results:
                color = _SEV_COLORS[r.severity]
                icon = _ICONS[r.severity]
                lines.append(f"  {color}{icon}{_RESET} {r.message}")

        lines.append("\n" + "─" * width)

        # Summary counts
        n_pass = sum(1 for r in self.checks if r.severity == Severity.PASS)
        n_warn = sum(1 for r in self.checks if r.severity == Severity.WARN)
        n_fail = sum(1 for r in self.checks if r.severity == Severity.FAIL)
        lines.append(
            f"{_GREEN}✓ {n_pass} passed{_RESET}  "
            f"{_YELLOW}⚠ {n_warn} warnings{_RESET}  "
            f"{_RED}✗ {n_fail} failed{_RESET}"
        )

        if self.metadata:
            rows = self.metadata.get("rows", "?")
            cols = self.metadata.get("cols", "?")
            rows_fmt = f"{rows:,}" if isinstance(rows, int) else str(rows)
            lines.append(f"\nDataset: {rows_fmt} rows × {cols} columns")
        lines.append("")

        return "\n".join(lines)

    # ── Machine-readable output ───────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "schema_version": SCHEMA_VERSION,
            "score": self.score,
            "verdict": self.verdict,
            "metadata": self.metadata,
            "summary": {
                "passed": sum(1 for r in self.checks if r.severity == Severity.PASS),
                "warnings": sum(1 for r in self.checks if r.severity == Severity.WARN),
                "failures": sum(1 for r in self.checks if r.severity == Severity.FAIL),
            },
            "checks": [r.to_dict() for r in self.checks],
        }

    # ── Markdown output (model cards / READMEs) ───────────────────────────────

    def to_markdown(self) -> str:
        lines: list[str] = []
        md_icons = {
            Severity.PASS: "✅",
            Severity.WARN: "⚠️",
            Severity.FAIL: "❌",
        }
        verdict_md = {"READY": "✅", "CAUTION": "⚠️", "NOT READY": "❌"}

        lines.append("## Preflight Dataset Report\n")

        if self.metadata:
            rows = self.metadata.get("rows", "?")
            rows_fmt = f"{rows:,}" if isinstance(rows, int) else str(rows)
            lines.append(
                f"**Dataset:** {rows_fmt} rows × " f"{self.metadata.get('cols', '?')} columns\n"
            )

        lines.append(
            f"**Readiness Score:** {self.score:.0f} / 100 "
            f"{verdict_md.get(self.verdict, '')} **{self.verdict}**\n"
        )

        # Summary table
        n_pass = sum(1 for r in self.checks if r.severity == Severity.PASS)
        n_warn = sum(1 for r in self.checks if r.severity == Severity.WARN)
        n_fail = sum(1 for r in self.checks if r.severity == Severity.FAIL)
        lines.append("| Status | Count |")
        lines.append("|--------|-------|")
        lines.append(f"| ✅ Passed   | {n_pass} |")
        lines.append(f"| ⚠️ Warnings | {n_warn} |")
        lines.append(f"| ❌ Failed   | {n_fail} |")
        lines.append("")

        # Group by category
        categories: dict[str, list[CheckResult]] = {}
        for r in self.checks:
            categories.setdefault(r.category, []).append(r)

        for cat, cat_results in categories.items():
            lines.append(f"### {cat}\n")
            for r in cat_results:
                icon = md_icons[r.severity]
                lines.append(f"- {icon} {r.message}")
            lines.append("")

        return "\n".join(lines)

    # ── HTML output ──────────────────────────────────────────────────────────

    def to_html(self) -> str:
        """
        Return a self-contained, single-file HTML report with:
        - Animated radial score gauge
        - Per-category accordion cards
        - Colour-coded severity badges
        - Summary stat bar
        - Full details table (expandable)
        - No external dependencies — pure HTML/CSS/JS
        """
        import json
        import html as html_lib

        n_pass = sum(1 for r in self.checks if r.severity == Severity.PASS)
        n_warn = sum(1 for r in self.checks if r.severity == Severity.WARN)
        n_fail = sum(1 for r in self.checks if r.severity == Severity.FAIL)

        score_int = int(round(self.score))
        verdict = self.verdict

        # Verdict palette
        if verdict == "READY":
            verdict_color = "#22c55e"
            verdict_bg = "#f0fdf4"
            verdict_border = "#86efac"
            gauge_color = "#22c55e"
        elif verdict == "CAUTION":
            verdict_color = "#f59e0b"
            verdict_bg = "#fffbeb"
            verdict_border = "#fcd34d"
            gauge_color = "#f59e0b"
        else:
            verdict_color = "#ef4444"
            verdict_bg = "#fef2f2"
            verdict_border = "#fca5a5"
            gauge_color = "#ef4444"

        # Metadata block
        rows = self.metadata.get("rows", "?")
        cols = self.metadata.get("cols", "?")
        target = self.metadata.get("target") or "—"
        rows_fmt = f"{rows:,}" if isinstance(rows, int) else str(rows)
        rows_analyzed = self.metadata.get("rows_analyzed", rows)
        rows_analyzed_fmt = (
            f"{rows_analyzed:,}" if isinstance(rows_analyzed, int) else str(rows_analyzed)
        )
        sampling_applied = bool(self.metadata.get("sampling_applied", False))

        # Build category cards
        categories: dict[str, list[CheckResult]] = {}
        for r in self.checks:
            categories.setdefault(r.category, []).append(r)

        SEV_BADGE = {
            Severity.PASS: ('<span class="badge pass">✓ PASS</span>', "row-pass"),
            Severity.WARN: ('<span class="badge warn">⚠ WARN</span>', "row-warn"),
            Severity.FAIL: ('<span class="badge fail">✗ FAIL</span>', "row-fail"),
        }

        CAT_ICONS = {
            "Completeness": "🗂",
            "Class Balance": "⚖️",
            "Leakage Detection": "🔍",
            "Duplicates": "📋",
            "Distributional Health": "📊",
            "Feature Correlation": "🔗",
            "Data Types": "🏷",
            "Train/Test Drift": "🌊",
        }

        def _cat_status(results: list[CheckResult]) -> tuple[str, str]:
            """Return (css_class, icon) for worst severity in this category."""
            sevs = [r.severity for r in results]
            if Severity.FAIL in sevs:
                return "cat-fail", "✗"
            if Severity.WARN in sevs:
                return "cat-warn", "⚠"
            return "cat-pass", "✓"

        cards_html = ""
        for i, (cat, cat_results) in enumerate(categories.items()):
            css_cls, status_icon = _cat_status(cat_results)
            cat_icon = CAT_ICONS.get(cat, "🔎")
            rows_html = ""
            for r in cat_results:
                badge, row_cls = SEV_BADGE[r.severity]
                msg = html_lib.escape(r.message)
                pen = f"-{r.penalty:.0f}" if r.penalty > 0 else "0"
                conf = (
                    f"{int(round(r.confidence * 100))}%" if isinstance(r.confidence, float) else "—"
                )
                rows_html += f"""
                <tr class="{row_cls}">
                  <td>{badge}</td>
                  <td>{msg}</td>
                  <td>{conf}</td>
                  <td class="penalty">{pen}</td>
                </tr>"""

            cards_html += f"""
        <div class="card {css_cls}">
          <button class="card-header" onclick="toggleCard(this)" aria-expanded="{'true' if i == 0 else 'false'}">
            <span class="cat-icon">{cat_icon}</span>
            <span class="cat-name">{html_lib.escape(cat)}</span>
            <span class="cat-status-icon">{status_icon}</span>
            <span class="chevron">▾</span>
          </button>
          <div class="card-body" {'style="display:block"' if i == 0 else ''}>
            <table class="check-table">
              <thead><tr><th>Status</th><th>Finding</th><th>Confidence</th><th>Penalty</th></tr></thead>
              <tbody>{rows_html}
              </tbody>
            </table>
          </div>
        </div>"""

        # Serialise check data for the JS details table
        checks_json = json.dumps([r.to_dict() for r in self.checks], default=str)

        # SVG gauge — circumference trick
        radius = 80
        circ = 2 * 3.14159 * radius
        dash = circ * score_int / 100
        gap = circ - dash

        html_out = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Preflight Report</title>
<style>
  /* ── Reset & base ─────────────────────────────────────────────────── */
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --pass:   #22c55e;
    --warn:   #f59e0b;
    --fail:   #ef4444;
    --bg:     #0f172a;
    --surface:#1e293b;
    --surface2:#253248;
    --border: #334155;
    --text:   #e2e8f0;
    --muted:  #94a3b8;
    --radius: 12px;
    --gauge:  {gauge_color};
  }}
  html {{ scroll-behavior: smooth; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter",
                 Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 2rem 1rem 4rem;
  }}
  a {{ color: var(--gauge); text-decoration: none; }}

  /* ── Layout ──────────────────────────────────────────────────────── */
  .container {{ max-width: 860px; margin: 0 auto; }}

  /* ── Header ──────────────────────────────────────────────────────── */
  .header {{
    display: flex; align-items: center; gap: 0.75rem;
    margin-bottom: 2rem;
  }}
  .header h1 {{ font-size: 1.5rem; font-weight: 700; letter-spacing: -0.02em; }}
  .header-sub {{ color: var(--muted); font-size: 0.875rem; margin-top: 0.15rem; }}
  .logo {{ font-size: 2rem; }}
  .timestamp {{ color: var(--muted); font-size: 0.8rem; margin-left: auto; }}

  /* ── Hero strip ──────────────────────────────────────────────────── */
  .hero {{
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 2rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
    margin-bottom: 1.5rem;
    align-items: center;
  }}
  @media (max-width: 520px) {{
    .hero {{ grid-template-columns: 1fr; text-align: center; }}
    .gauge-wrap {{ justify-content: center; }}
  }}

  /* ── Gauge ───────────────────────────────────────────────────────── */
  .gauge-wrap {{ display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }}
  /* Rotate SVG so arc starts at 12 o'clock — text is a separate div overlay, unaffected */
  .gauge-svg {{ display: block; transform: rotate(-90deg); }}
  /* Track = full circle in verdict colour at low opacity (shows the "deficit") */
  .gauge-track {{ fill: none; stroke: {gauge_color}33; stroke-width: 12; }}
  /* Fill = the earned portion in full verdict colour */
  .gauge-fill  {{
    fill: none; stroke: {gauge_color}; stroke-width: 12;
    stroke-linecap: butt;
    stroke-dasharray: 0 {circ:.1f};
    transition: stroke-dasharray 1.2s cubic-bezier(.4,0,.2,1);
  }}

  .verdict-pill {{
    display: inline-flex; align-items: center; gap: 0.4rem;
    background: {verdict_bg}22;
    color: {verdict_color};
    border: 1px solid {verdict_color}44;
    border-radius: 999px;
    padding: 0.3rem 1rem;
    font-size: 0.9rem;
    font-weight: 700;
    letter-spacing: 0.04em;
  }}

  /* ── Hero right panel ────────────────────────────────────────────── */
  .hero-right h2 {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 0.5rem; }}
  .meta-grid {{
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 0.6rem 1.5rem;
    margin-bottom: 1.25rem;
  }}
  .meta-item {{ display: flex; flex-direction: column; }}
  .meta-label {{ font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.06em; }}
  .meta-value {{ font-size: 0.95rem; font-weight: 600; }}

  /* ── Summary bar ─────────────────────────────────────────────────── */
  .summary-bar {{
    display: flex; gap: 1rem; flex-wrap: wrap;
  }}
  .stat {{
    display: flex; align-items: center; gap: 0.4rem;
    background: var(--surface2);
    border-radius: 8px;
    padding: 0.45rem 0.9rem;
    font-size: 0.875rem;
    font-weight: 600;
    border: 1px solid var(--border);
  }}
  .stat.s-pass {{ color: var(--pass); border-color: var(--pass)33; }}
  .stat.s-warn {{ color: var(--warn); border-color: var(--warn)33; }}
  .stat.s-fail {{ color: var(--fail); border-color: var(--fail)33; }}
  .stat-num {{ font-size: 1.2rem; font-weight: 800; }}

  /* ── Cards ───────────────────────────────────────────────────────── */
  .section-title {{
    font-size: 0.75rem; font-weight: 700; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em;
    margin: 1.75rem 0 0.75rem;
  }}
  .cards {{ display: flex; flex-direction: column; gap: 0.6rem; }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    transition: box-shadow 0.2s;
  }}
  .card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.35); }}
  .card.cat-fail {{ border-left: 3px solid var(--fail); }}
  .card.cat-warn {{ border-left: 3px solid var(--warn); }}
  .card.cat-pass {{ border-left: 3px solid var(--pass); }}

  .card-header {{
    width: 100%; background: none; border: none; cursor: pointer;
    display: flex; align-items: center; gap: 0.65rem;
    padding: 0.85rem 1rem;
    color: var(--text);
    font-size: 0.95rem; font-weight: 600;
    text-align: left;
  }}
  .card-header:hover {{ background: var(--surface2); }}
  .cat-icon {{ font-size: 1.1rem; }}
  .cat-name {{ flex: 1; }}
  .cat-status-icon {{ font-size: 0.9rem; }}
  .cat-fail .cat-status-icon {{ color: var(--fail); }}
  .cat-warn .cat-status-icon {{ color: var(--warn); }}
  .cat-pass .cat-status-icon {{ color: var(--pass); }}
  .chevron {{
    color: var(--muted); font-size: 0.8rem;
    transition: transform 0.25s;
  }}
  .card-header[aria-expanded="true"] .chevron {{ transform: rotate(180deg); }}

  .card-body {{ display: none; border-top: 1px solid var(--border); }}

  /* ── Check table ─────────────────────────────────────────────────── */
  .check-table {{ width: 100%; border-collapse: collapse; font-size: 0.875rem; }}
  .check-table thead th {{
    background: var(--surface2);
    padding: 0.5rem 1rem;
    text-align: left;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    color: var(--muted);
    font-weight: 600;
    border-bottom: 1px solid var(--border);
  }}
  .check-table tbody tr {{
    border-bottom: 1px solid var(--border);
    transition: background 0.15s;
  }}
  .check-table tbody tr:last-child {{ border-bottom: none; }}
  .check-table tbody tr:hover {{ background: var(--surface2); }}
  .check-table td {{ padding: 0.65rem 1rem; vertical-align: top; }}
  .check-table .penalty {{ text-align: right; color: var(--muted); font-variant-numeric: tabular-nums; white-space: nowrap; }}
  .row-fail .penalty {{ color: var(--fail); }}
  .row-warn .penalty {{ color: var(--warn); }}

  /* ── Badges ──────────────────────────────────────────────────────── */
  .badge {{
    display: inline-block; padding: 0.2rem 0.55rem;
    border-radius: 6px; font-size: 0.72rem; font-weight: 700;
    letter-spacing: 0.05em; white-space: nowrap;
  }}
  .badge.pass {{ background: var(--pass)22; color: var(--pass); border: 1px solid var(--pass)44; }}
  .badge.warn {{ background: var(--warn)22; color: var(--warn); border: 1px solid var(--warn)44; }}
  .badge.fail {{ background: var(--fail)22; color: var(--fail); border: 1px solid var(--fail)44; }}

  /* ── Details table ───────────────────────────────────────────────── */
  .details-section {{ margin-top: 2.5rem; }}
  .details-toggle {{
    background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); border-radius: 8px; padding: 0.55rem 1.1rem;
    cursor: pointer; font-size: 0.875rem; font-weight: 600;
    margin-bottom: 0.75rem;
  }}
  .details-toggle:hover {{ background: var(--surface); }}
  #details-table {{ display: none; }}
  .dt {{ width: 100%; border-collapse: collapse; font-size: 0.8rem; }}
  .dt th {{
    background: var(--surface2); padding: 0.5rem 0.75rem;
    text-align: left; font-size: 0.68rem; text-transform: uppercase;
    letter-spacing: 0.07em; color: var(--muted);
    border-bottom: 1px solid var(--border); position: sticky; top: 0;
  }}
  .dt td {{
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--border);
    vertical-align: top;
    max-width: 320px;
    word-break: break-word;
  }}
  .dt tr:hover td {{ background: var(--surface2); }}
  .dt .mono {{ font-family: ui-monospace, "Fira Code", monospace; color: var(--muted); font-size: 0.75rem; }}

  /* ── Progress bars ───────────────────────────────────────────────── */
  .score-bar {{
    display: flex; align-items: center; gap: 0.75rem;
    margin-top: 1rem;
  }}
  .bar-track {{
    flex: 1; height: 8px; background: var(--border); border-radius: 999px; overflow: hidden;
  }}
  .bar-fill {{
    height: 100%; background: {gauge_color}; border-radius: 999px;
    width: 0%; transition: width 1.2s cubic-bezier(.4,0,.2,1);
  }}
  .bar-pct {{ font-size: 0.85rem; color: var(--muted); font-variant-numeric: tabular-nums; min-width: 3.5rem; text-align: right; }}

  /* ── Footer ──────────────────────────────────────────────────────── */
  .footer {{
    margin-top: 3rem; padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    color: var(--muted); font-size: 0.78rem;
    display: flex; justify-content: space-between; flex-wrap: wrap; gap: 0.5rem;
  }}
</style>
</head>
<body>
<div class="container">

  <!-- Header -->
  <div class="header">
    <span class="logo">✈️</span>
    <div>
      <h1>Preflight Report</h1>
      <div class="header-sub">Dataset readiness analysis for machine learning</div>
    </div>
    <span class="timestamp" id="ts"></span>
  </div>

  <!-- Hero -->
  <div class="hero">
    <div class="gauge-wrap">
      <div style="position:relative;width:190px;height:190px;">
        <svg class="gauge-svg" width="190" height="190" viewBox="0 0 190 190">
          <circle class="gauge-track" cx="95" cy="95" r="{radius}"/>
          <circle class="gauge-fill" id="gauge-fill" cx="95" cy="95" r="{radius}"/>
        </svg>
        <div style="position:absolute;inset:0;display:flex;flex-direction:column;
                    align-items:center;justify-content:center;gap:0.1rem;">
          <span style="font-size:2.4rem;font-weight:800;color:var(--text);line-height:1;">{score_int}</span>
          <span style="font-size:0.8rem;color:var(--muted);font-weight:500;">/100</span>
        </div>
      </div>
      <div class="verdict-pill">{verdict}</div>
    </div>
    <div class="hero-right">
      <h2>Dataset Summary</h2>
      <div class="meta-grid">
        <div class="meta-item"><span class="meta-label">Rows</span><span class="meta-value">{rows_fmt}</span></div>
        <div class="meta-item"><span class="meta-label">Columns</span><span class="meta-value">{cols}</span></div>
        <div class="meta-item"><span class="meta-label">Target</span><span class="meta-value">{html_lib.escape(str(target))}</span></div>
        <div class="meta-item"><span class="meta-label">Checks run</span><span class="meta-value">{len(self.checks)}</span></div>
        <div class="meta-item"><span class="meta-label">Rows analyzed</span><span class="meta-value">{rows_analyzed_fmt}</span></div>
        <div class="meta-item"><span class="meta-label">Sampling</span><span class="meta-value">{'Yes' if sampling_applied else 'No'}</span></div>
      </div>
      <div class="summary-bar">
        <div class="stat s-pass"><span class="stat-num">{n_pass}</span> passed</div>
        <div class="stat s-warn"><span class="stat-num">{n_warn}</span> warnings</div>
        <div class="stat s-fail"><span class="stat-num">{n_fail}</span> failed</div>
      </div>
      <div class="score-bar">
        <div class="bar-track"><div class="bar-fill" id="bar-fill"></div></div>
        <span class="bar-pct">{score_int}/100</span>
      </div>
    </div>
  </div>

  <!-- Category cards -->
  <div class="section-title">Check Results by Category</div>
  <div class="cards">
    {cards_html}
  </div>

  <!-- Full details table -->
  <div class="details-section">
    <button class="details-toggle" onclick="toggleDetails()">▾ Show all check details</button>
    <div id="details-table">
      <table class="dt">
        <thead>
          <tr>
            <th>Category</th><th>Check ID</th><th>Status</th><th>Confidence</th><th>Message</th><th>Penalty</th>
          </tr>
        </thead>
        <tbody id="dt-body"></tbody>
      </table>
    </div>
  </div>

  <div class="footer">
    <span>Generated by <strong>preflight-data</strong></span>
    <span id="ft-ts"></span>
  </div>
</div>

<script>
  // ── Timestamps ──────────────────────────────────────────────────────────
  const now = new Date();
  const fmt = now.toLocaleString(undefined, {{dateStyle:'medium', timeStyle:'short'}});
  document.getElementById('ts').textContent = fmt;
  document.getElementById('ft-ts').textContent = fmt;

  // ── Animate gauge & bar on load ──────────────────────────────────────────
  window.addEventListener('load', () => {{
    const circ  = {circ:.1f};
    const score = {score_int};
    const fill  = circ * score / 100;
    const gap   = circ - fill;
    const gfill = document.getElementById('gauge-fill');
    if (gfill) gfill.setAttribute('stroke-dasharray', fill.toFixed(1) + ' ' + gap.toFixed(1));
    const bar = document.getElementById('bar-fill');
    if (bar) bar.style.width = score + '%';
  }});

  // ── Card accordion ───────────────────────────────────────────────────────
  function toggleCard(btn) {{
    const body = btn.nextElementSibling;
    const open = btn.getAttribute('aria-expanded') === 'true';
    btn.setAttribute('aria-expanded', !open);
    body.style.display = open ? 'none' : 'block';
  }}

  // ── Details table ────────────────────────────────────────────────────────
  const CHECKS = {checks_json};
  const SEV_CLASS = {{ pass: 'pass', warn: 'warn', fail: 'fail' }};

  function buildDetailsTable() {{
    const tbody = document.getElementById('dt-body');
    if (tbody.children.length) return;
    CHECKS.forEach(c => {{
      const tr = document.createElement('tr');
      const sev = c.severity;
      const badge = `<span class="badge ${{SEV_CLASS[sev] || ''}}">` +
        (sev === 'pass' ? '✓' : sev === 'warn' ? '⚠' : '✗') +
        ` ${{sev.toUpperCase()}}</span>`;
      const pen = c.penalty > 0 ? `-${{c.penalty}}` : '0';
      const conf = typeof c.confidence === 'number' ? `${{Math.round(c.confidence * 100)}}%` : '—';
      tr.innerHTML = `
        <td>${{c.category}}</td>
        <td class="mono">${{c.check_id}}</td>
        <td>${{badge}}</td>
        <td>${{conf}}</td>
        <td>${{c.message}}</td>
        <td style="text-align:right;color:var(--${{sev === 'fail' ? 'fail' : sev === 'warn' ? 'warn' : 'muted'}})">${{pen}}</td>`;
      tbody.appendChild(tr);
    }});
  }}

  function toggleDetails() {{
    const el = document.getElementById('details-table');
    const btn = event.currentTarget;
    if (el.style.display === 'block') {{
      el.style.display = 'none';
      btn.textContent = '▾ Show all check details';
    }} else {{
      buildDetailsTable();
      el.style.display = 'block';
      btn.textContent = '▴ Hide check details';
    }}
  }}
</script>
</body>
</html>"""
        return html_out

    def save_html(self, path: str | None = None) -> str:
        """
        Write the HTML report to *path*.

        Parameters
        ----------
        path : file path to write to (default: "preflight_report.html")

        Returns
        -------
        The absolute path of the written file.
        """
        import os

        if path is None:
            path = "preflight_report.html"
        path = os.path.abspath(path)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self.to_html())
        return path

    def __repr__(self) -> str:
        return (
            f"<preflight.Report score={self.score}/100 "
            f"verdict={self.verdict!r} checks={len(self.checks)}>"
        )
