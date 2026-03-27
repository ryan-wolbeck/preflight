"""
Configuration models for preflight checks and scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class RuntimeConfig:
    mode: Literal["accurate", "fast"] = "accurate"
    sample_rows: int | None = None
    random_state: int = 42
    large_dataset_rows: int = 250_000
    fast_mode_sample_rows: int = 50_000


@dataclass(frozen=True)
class CompletenessConfig:
    warn_threshold: float = 0.20
    fail_threshold: float = 0.50
    overall_warn_penalty: float = 5.0
    overall_fail_penalty: float = 15.0
    per_column_warn_penalty: float = 5.0
    per_column_fail_penalty: float = 10.0
    empty_dataframe_penalty: float = 20.0


@dataclass(frozen=True)
class BalanceConfig:
    categorical_threshold: int = 20
    warn_ratio: float = 4.0
    fail_ratio: float = 9.0
    warn_penalty: float = 7.0
    fail_penalty: float = 15.0


@dataclass(frozen=True)
class LeakageConfig:
    corr_warn_threshold: float = 0.85
    corr_fail_threshold: float = 0.95
    corr_warn_penalty: float = 8.0
    corr_fail_penalty: float = 20.0
    id_like_penalty: float = 8.0
    datetime_penalty: float = 8.0
    temporal_warn_threshold: float = 0.70
    temporal_fail_threshold: float = 0.85
    temporal_warn_penalty: float = 6.0
    temporal_fail_penalty: float = 12.0


@dataclass(frozen=True)
class DuplicatesConfig:
    near_dup_warn_pct: float = 0.01
    near_dup_fail_pct: float = 0.05
    exact_warn_penalty: float = 5.0
    exact_fail_penalty: float = 10.0
    near_warn_penalty: float = 5.0
    near_fail_penalty: float = 10.0


@dataclass(frozen=True)
class DistributionsConfig:
    low_var_threshold: float = 0.01
    high_card_threshold: float = 0.95
    scale_order_threshold: float = 4.0
    constant_penalty_per_column: float = 5.0
    low_variance_penalty: float = 5.0
    high_card_penalty: float = 5.0
    scale_disparity_penalty: float = 5.0


@dataclass(frozen=True)
class CorrelationsConfig:
    warn_threshold: float = 0.90
    fail_threshold: float = 0.95
    warn_penalty: float = 3.0
    fail_penalty_per_pair: float = 5.0
    fail_penalty_pair_cap: int = 4
    max_pairs_in_message: int = 5


@dataclass(frozen=True)
class TypesConfig:
    numeric_sample_size: int = 200
    numeric_parse_threshold: float = 0.90
    numeric_as_object_penalty: float = 5.0
    mixed_types_penalty: float = 8.0


@dataclass(frozen=True)
class SplitConfig:
    psi_warn_threshold: float = 0.1
    psi_fail_threshold: float = 0.2
    psi_warn_penalty: float = 5.0
    psi_fail_penalty: float = 15.0
    drift_penalty_col_cap: int = 3
    categorical_tvd_warn_threshold: float = 0.1
    categorical_tvd_fail_threshold: float = 0.2
    categorical_warn_penalty: float = 4.0
    categorical_fail_penalty: float = 10.0
    missingness_warn_delta: float = 0.1
    missingness_fail_delta: float = 0.2
    missingness_warn_penalty: float = 4.0
    missingness_fail_penalty: float = 10.0


@dataclass(frozen=True)
class ScoringConfig:
    ready_threshold: float = 85.0
    caution_threshold: float = 60.0


@dataclass(frozen=True)
class PreflightConfig:
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)
    completeness: CompletenessConfig = field(default_factory=CompletenessConfig)
    balance: BalanceConfig = field(default_factory=BalanceConfig)
    leakage: LeakageConfig = field(default_factory=LeakageConfig)
    duplicates: DuplicatesConfig = field(default_factory=DuplicatesConfig)
    distributions: DistributionsConfig = field(default_factory=DistributionsConfig)
    correlations: CorrelationsConfig = field(default_factory=CorrelationsConfig)
    types: TypesConfig = field(default_factory=TypesConfig)
    split: SplitConfig = field(default_factory=SplitConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    enabled_checks: dict[str, bool] = field(
        default_factory=lambda: {
            "completeness": True,
            "balance": True,
            "leakage": True,
            "duplicates": True,
            "distributions": True,
            "correlations": True,
            "types": True,
        }
    )
