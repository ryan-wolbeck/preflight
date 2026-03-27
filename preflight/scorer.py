"""
Scoring engine
==============
Aggregates CheckResult penalties into a 0–100 readiness score and
assigns a verdict: READY / CAUTION / NOT READY.
"""

from __future__ import annotations

from preflight.config import ScoringConfig
from preflight._types import CheckResult


def compute_score(
    results: list[CheckResult], scoring_config: ScoringConfig | None = None
) -> tuple[float, str]:
    """
    Subtract penalties from 100 and clamp to [0, 100].

    Returns
    -------
    score   : float in [0, 100]
    verdict : "READY" | "CAUTION" | "NOT READY"
    """
    total_penalty = sum(r.penalty for r in results)
    score = max(0.0, min(100.0, 100.0 - total_penalty))
    cfg = scoring_config or ScoringConfig()

    if score >= cfg.ready_threshold:
        verdict = "READY"
    elif score >= cfg.caution_threshold:
        verdict = "CAUTION"
    else:
        verdict = "NOT READY"

    return score, verdict
