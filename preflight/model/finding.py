"""
Core finding/evidence domain objects for policy-based readiness evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Domain(str, Enum):
    DATA_QUALITY = "data_quality"
    TARGET_RISK = "target_risk"
    SPLIT_INTEGRITY = "split_integrity"
    SCHEMA_CONTRACT = "schema_contract"
    STAT_ANOMALY = "stat_anomaly"
    ADVISORY = "advisory"


class Severity(str, Enum):
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass(frozen=True)
class Evidence:
    metrics: dict[str, float | int | str | bool] = field(default_factory=dict)
    threshold: dict[str, Any] | None = None
    samples: dict[str, Any] | None = None


@dataclass(frozen=True)
class Finding:
    check_id: str
    title: str
    domain: Domain
    signal_strength: str = "medium"
    confidence: float | None = None
    evidence: Evidence = field(default_factory=Evidence)
    affected_columns: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    suggested_action: str | None = None
    docs_url: str | None = None
    tags: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    # Set by policy evaluation stage.
    severity: Severity = Severity.INFO
    suppressed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "domain": self.domain.value,
            "signal_strength": self.signal_strength,
            "confidence": self.confidence,
            "severity": self.severity.value,
            "suppressed": self.suppressed,
            "affected_columns": self.affected_columns,
            "recommendations": self.recommendations,
            "suggested_action": self.suggested_action,
            "docs_url": self.docs_url,
            "tags": self.tags,
            "details": self.details,
            "evidence": {
                "metrics": self.evidence.metrics,
                "threshold": self.evidence.threshold,
                "samples": self.evidence.samples,
            },
        }
