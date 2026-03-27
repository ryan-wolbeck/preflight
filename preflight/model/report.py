"""
Run report model used by the new policy-first API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from preflight.model.finding import Domain, Finding
from preflight.model.policy import GateDecision, PolicyEvaluation

SCHEMA_VERSION = "2.0.0"


@dataclass(frozen=True)
class RunMeta:
    profile: str
    rows_total: int
    columns_total: int
    rows_analyzed: int
    sampling_applied: bool
    target: str | None
    run_id: str = field(default_factory=lambda: str(uuid4()))
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


@dataclass(frozen=True)
class RunReport:
    meta: RunMeta
    findings: list[Finding]
    gate: GateDecision
    score: float
    score_label: str = "heuristic"

    @property
    def summary(self) -> dict[str, Any]:
        sev_counts = PolicyEvaluation.severity_counts(self.findings)
        domain_counts: dict[str, int] = {d.value: 0 for d in Domain}
        suppressed_count = 0
        for finding in self.findings:
            domain_counts[finding.domain.value] = domain_counts.get(finding.domain.value, 0) + 1
            if finding.suppressed:
                suppressed_count += 1
        return {
            "severity_counts": sev_counts,
            "domain_counts": domain_counts,
            "suppressed_findings": suppressed_count,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "run": {
                "id": self.meta.run_id,
                "timestamp_utc": self.meta.timestamp_utc,
                "profile": self.meta.profile,
                "sampling": {
                    "applied": self.meta.sampling_applied,
                    "rows_analyzed": self.meta.rows_analyzed,
                    "rows_total": self.meta.rows_total,
                },
            },
            "dataset": {
                "rows": self.meta.rows_total,
                "columns": self.meta.columns_total,
                "target": self.meta.target,
            },
            "gate": {
                "status": self.gate.status,
                "reasons": self.gate.reasons,
            },
            "score": {
                "enabled": True,
                "value": round(self.score, 1),
                "label": self.score_label,
                "profile": self.meta.profile,
            },
            "summary": self.summary,
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json(self, indent: int = 2) -> str:
        import json

        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_markdown(self) -> str:
        from preflight.renderers.markdown import render

        return render(self)

    def to_text(self) -> str:
        from preflight.renderers.text import render

        return render(self)

    def to_html(self) -> str:
        from preflight.renderers.html import render

        return render(self)
