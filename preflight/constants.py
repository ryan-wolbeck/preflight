"""
Shared check/category identifiers used across adapters, config, and registry.
"""

from __future__ import annotations

from enum import Enum

from preflight.model.finding import Domain


class CheckName(str, Enum):
    COMPLETENESS = "completeness"
    BALANCE = "balance"
    LEAKAGE = "leakage"
    DUPLICATES = "duplicates"
    DISTRIBUTIONS = "distributions"
    CORRELATIONS = "correlations"
    TYPES = "types"
    FINGERPRINT = "fingerprint"


class LegacyCategory(str, Enum):
    COMPLETENESS = "Completeness"
    CLASS_BALANCE = "Class Balance"
    LEAKAGE_DETECTION = "Leakage Detection"
    DUPLICATES = "Duplicates"
    DISTRIBUTIONAL_HEALTH = "Distributional Health"
    FEATURE_CORRELATION = "Feature Correlation"
    DATA_TYPES = "Data Types"
    TRAIN_TEST_DRIFT = "Train/Test Drift"


CATEGORY_TO_DOMAIN: dict[str, Domain] = {
    LegacyCategory.COMPLETENESS.value: Domain.DATA_QUALITY,
    LegacyCategory.CLASS_BALANCE.value: Domain.DATA_QUALITY,
    LegacyCategory.LEAKAGE_DETECTION.value: Domain.TARGET_RISK,
    LegacyCategory.DUPLICATES.value: Domain.DATA_QUALITY,
    LegacyCategory.DISTRIBUTIONAL_HEALTH.value: Domain.STAT_ANOMALY,
    LegacyCategory.FEATURE_CORRELATION.value: Domain.STAT_ANOMALY,
    LegacyCategory.DATA_TYPES.value: Domain.SCHEMA_CONTRACT,
    LegacyCategory.TRAIN_TEST_DRIFT.value: Domain.SPLIT_INTEGRITY,
}


KNOWN_CHECK_NAMES: set[str] = {item.value for item in CheckName}
