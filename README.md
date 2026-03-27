# preflight ✈️

[![CI](https://github.com/preflight-ml/preflight/actions/workflows/ci.yml/badge.svg)](https://github.com/preflight-ml/preflight/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://pypi.org/project/preflight-data/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

**Dataset readiness checker for machine learning.**
Run a pre-flight checklist on any pandas DataFrame before you train a model.

```python
import preflight

report = preflight.check(df, target="churn")
print(report)
```

```
Preflight Report
────────────────────────────────────────────────
Readiness Score: 74/100  ⚠ CAUTION

Completeness
  ✓ No missing values detected across all columns.

Class Balance
  ⚠ Moderate class imbalance: 82%/18% split (`0` vs `1`).

Leakage Detection
  ✗ Potential target leakage — suspiciously high correlation: `signup_date` (r=0.97).
  ⚠ 1 ID-like column(s) detected: `user_id`.

Duplicates
  ✓ No exact duplicate rows.
  ✓ No near-duplicate rows.

Distributional Health
  ✓ No constant columns.
  ⚠ Feature value ranges span 4.2 orders of magnitude.

Feature Correlation
  ✓ No highly correlated feature pairs.

Data Types
  ✓ No object columns appear to be numeric.
  ✓ No mixed-type object columns.

────────────────────────────────────────────────
✓ 7 passed  ⚠ 3 warnings  ✗ 1 failed
```

---

## Installation

```bash
# From PyPI (once published)
pip install preflight-data

# From source
git clone https://github.com/preflight-ml/preflight
cd preflight
make install-dev
```

### Conda environment

```bash
make env                   # creates 'preflight' conda env
conda activate preflight
make test                  # run full test suite
```

---

## API

### `preflight.check(df, target=None) → Report`

Run all checks on a DataFrame.

| Parameter | Type | Description |
|-----------|------|-------------|
| `df` | `pd.DataFrame` | Dataset to analyse |
| `target` | `str \| None` | Name of the label/target column |

```python
report = preflight.check(df, target="price")

report.score          # float  0–100
report.verdict        # "READY" | "CAUTION" | "NOT READY"
str(report)           # terminal-friendly summary
report.to_dict()      # machine-readable dict
report.to_markdown()  # markdown for model cards / READMEs

# configurable runtime (fast mode + sampling)
from preflight import PreflightConfig
cfg = PreflightConfig()
report = preflight.check(df, target="price", config=cfg)
```

### `preflight.run(df, target=None, profile="exploratory") → RunReport`

Policy-first API with explicit gate semantics.

```python
import preflight

run_report = preflight.run(df, target="price", profile="ci-strict")
run_report.gate.status     # PASS | FAIL
run_report.to_dict()       # schema v2 machine output
```

### `preflight.check_split(X_train, X_test) → Report`

Detect distribution drift between train and test splits:
- numeric drift via Population Stability Index (PSI)
- categorical drift via total variation distance (TVD)
- missingness drift via absolute missing-rate delta

```python
split_report = preflight.check_split(X_train, X_test)
print(split_report)
```

### JSON schema stability

`report.to_dict()` includes a `schema_version` field so downstream CI/pipeline parsing can version-lock safely.

---

## CLI

```bash
# policy-first commands (recommended)
preflight run data.csv --target churn --profile ci-strict --format json
preflight run data.csv --target churn --policy-file policy.json --format json
preflight run data.csv --target churn --config-file config.json --format json
preflight run data.csv --target churn --format markdown --output-html report.html
preflight run-split train.csv test.csv --profile exploratory --format markdown
preflight run data.csv --target churn --profile ci-strict --suppressions suppressions.json
preflight compare current.json baseline.json --max-score-drop 3 --fail-on-new-error --fail-on-domain-increase target_risk=1
preflight suppress add --file suppressions.json --check-id leakage.high_correlation --reason "known safe"
preflight suppress list --file suppressions.json
preflight suppress validate --file suppressions.json --fail-on-expired
preflight plugins doctor --format json

# full dataset readiness check
preflight check data.csv --target churn --format json --output preflight.json

# train/test drift check
preflight check-split train.csv test.csv --format markdown

# fast mode sampling
preflight check data.csv --target churn --mode fast --sample-rows 50000
```

### Suppressions

Policy runs can load suppressions from JSON:

```json
[
  {
    "check_id": "leakage.high_correlation",
    "column": "signup_date",
    "expires": "2026-12-31",
    "reason": "feature excluded from model; tracked in migration plan"
  }
]
```

---

## Checks

| Category | Check | Penalty |
|----------|-------|---------|
| **Completeness** | Overall missing rate | 5–15 pts |
| | Per-column missing (>20% warn, >50% fail) | 5–30 pts |
| **Class Balance** | Majority/minority ratio (>4:1 warn, >9:1 fail) | 7–15 pts |
| **Leakage Detection** | Correlation to target (>0.85 warn, >0.95 fail) | 8–20 pts |
| | ID-like columns | 8 pts |
| | Datetime columns | 8 pts |
| | Temporal leakage signal from datetime columns | 6–12 pts |
| **Duplicates** | Exact duplicate rows | 5–10 pts |
| | Near-duplicate rows | 5–10 pts |
| **Distributional Health** | Constant columns | 5 pts each |
| | Near-zero variance | 5 pts |
| | High-cardinality categoricals (>95% unique) | 5 pts |
| | Scale disparity (>4 orders of magnitude) | 5 pts |
| **Feature Correlation** | Feature pairs with r>0.90 | 3–20 pts |
| **Data Types** | Numeric stored as object | 5 pts |
| | Mixed types in object column | 8 pts |

### Scoring

```
Score = 100 − Σ(penalties)    clamped to [0, 100]

≥ 85  → READY
60–84 → CAUTION
< 60  → NOT READY
```

---

## Development

```bash
git clone https://github.com/preflight-ml/preflight
cd preflight

# Conda setup
make env
conda activate preflight

# Install in editable mode with dev deps
make install-dev

# Run tests
make test          # pytest + coverage
make test-fast     # pytest only
make test-stdlib   # stdlib unittest runner (no pytest needed)

# Lint
make lint

# Build
make build
```

### Project structure

```
preflight/
├── __init__.py          # check() and check_split() entry points
├── _types.py            # CheckResult dataclass, Severity enum
├── scorer.py            # penalty → score → verdict
├── report.py            # Report class (__str__, to_dict, to_markdown)
└── checks/
    ├── completeness.py
    ├── balance.py
    ├── leakage.py
    ├── duplicates.py
    ├── distributions.py
    ├── correlations.py
    └── types.py
tests/
├── conftest.py          # shared fixtures
├── test_checks.py       # pytest-style tests
└── run_tests.py         # stdlib unittest runner
```

### Adding a check

1. Create `preflight/checks/my_check.py` with a `run(df, **kwargs) -> list[CheckResult]` function.
2. Import and call it in `preflight/__init__.py` inside `check()`.
3. Add tests to `tests/test_checks.py` and `tests/run_tests.py`.

---

## Requirements

- Python ≥ 3.9
- pandas ≥ 1.3
- numpy ≥ 1.21
- scipy ≥ 1.7 *(optional extra: `pip install preflight-data[stats]`)*
- scikit-learn ≥ 1.0 *(optional extra: `pip install preflight-data[ml]`)*

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
