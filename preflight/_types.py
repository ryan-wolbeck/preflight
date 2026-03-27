"""
Shared types used across the preflight package.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    """
    Represents the outcome of a single check.

    Attributes
    ----------
    check_id:   machine-readable identifier, e.g. "completeness.high_missing"
    category:   human-readable group, e.g. "Completeness"
    severity:   PASS / WARN / FAIL
    message:    one-line human-readable description
    details:    optional structured data (dict / list) for to_dict() output
    confidence: confidence score [0,1] for this check signal
    penalty:    0–100 points subtracted from the readiness score
    """

    check_id: str
    category: str
    severity: Severity
    message: str
    details: Any = field(default=None)
    confidence: float | None = field(default=None)
    penalty: float = field(default=0.0)

    # ------------------------------------------------------------------
    # Convenience constructors
    # ------------------------------------------------------------------
    @classmethod
    def passed(
        cls,
        check_id: str,
        category: str,
        message: str,
        details: Any = None,
        confidence: float | None = None,
    ) -> "CheckResult":
        return cls(check_id, category, Severity.PASS, message, details, confidence, 0.0)

    @classmethod
    def warn(
        cls,
        check_id: str,
        category: str,
        message: str,
        details: Any = None,
        confidence: float | None = None,
        penalty: float = 5.0,
    ) -> "CheckResult":
        return cls(check_id, category, Severity.WARN, message, details, confidence, penalty)

    @classmethod
    def fail(
        cls,
        check_id: str,
        category: str,
        message: str,
        details: Any = None,
        confidence: float | None = None,
        penalty: float = 15.0,
    ) -> "CheckResult":
        return cls(check_id, category, Severity.FAIL, message, details, confidence, penalty)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "confidence": self.confidence,
            "penalty": self.penalty,
        }
