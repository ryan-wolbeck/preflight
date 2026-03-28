# Leakage Detection

Checks for leakage risk signals such as strong feature-target correlation.

- Warn/fail thresholds are configurable in `leakage.*`
- Focus is heuristic risk detection, not proof of leakage
- Typical remediation: remove/rebuild suspect features with leakage-safe cutoffs
