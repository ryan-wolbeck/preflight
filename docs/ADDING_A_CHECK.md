# Adding a Check

`preflight` is policy-first. New checks should be native checks that emit `Finding` objects.

## Checklist

1. Add a native check module under `preflight/checks_native/`.
2. Register it in `preflight/engine/registry.py` as `kind="native"`.
3. Add focused unit tests and one policy-impact test.
4. Add/update docs for thresholds and interpretation.

## Worked example

### 1) Implement `preflight/checks_native/outliers_native.py`

```python
from __future__ import annotations

import pandas as pd

from preflight.engine.interfaces import CheckContext
from preflight.model.finding import Domain, Evidence, Finding

name = "outliers"


def run(df: pd.DataFrame, context: CheckContext) -> list[Finding]:
    if df.empty:
        return []

    findings: list[Finding] = []
    numeric = df.select_dtypes(include=["number"])
    for col in numeric.columns:
        series = numeric[col].dropna()
        if len(series) < 20:
            continue
        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_rate = float(((series < lower) | (series > upper)).mean())
        if outlier_rate >= 0.2:
            findings.append(
                Finding(
                    check_id="distributions.outlier_rate",
                    title=f"Column '{col}' has high outlier rate ({outlier_rate:.1%}).",
                    domain=Domain.STAT_ANOMALY,
                    signal_strength="medium",
                    confidence=0.8,
                    affected_columns=[str(col)],
                    evidence=Evidence(
                        metrics={"outlier_rate": outlier_rate},
                        threshold={"warn_if_gte": 0.2},
                    ),
                    recommendations=[
                        "Investigate upstream data generation for spikes.",
                        "Consider robust scaling or capping with documented rationale.",
                    ],
                    suggested_action="Investigate outlier source before training.",
                    docs_url="https://github.com/ryan-wolbeck/preflight/blob/main/docs/checks/distributional-health.md",
                )
            )
    return findings
```

### 2) Register it in `preflight/engine/registry.py`

```python
from preflight.checks_native import outliers_native

RegisteredCheck(name=outliers_native.name, kind="native", run_native=outliers_native.run),
```

### 3) Add tests (`tests/test_outliers_native.py`)

```python
import numpy as np
import pandas as pd

from preflight.api import run


def test_outlier_check_fires_for_extreme_tail():
    rng = np.random.default_rng(1)
    normal = rng.normal(0, 1, 200)
    normal[:50] = normal[:50] * 30
    df = pd.DataFrame({"x": normal})

    report = run(df, profile="ci-balanced")
    ids = {f.check_id for f in report.findings}
    assert "distributions.outlier_rate" in ids
```

### 4) Optional plugin distribution

Expose a native plugin entry point:

```toml
[project.entry-points."preflight.checks"]
my_plugin_check = "my_pkg.preflight_plugin:run"
```

Legacy plugin fallback (compatibility only) is explicit opt-in and disabled by default:

```toml
[project.entry-points."preflight.checks.legacy"]
my_legacy_check = "my_pkg.legacy_plugin:run"
```

This legacy path is only loaded when `PREFLIGHT_ENABLE_LEGACY_PLUGIN_ENTRYPOINTS=1`.

## Design rules for maintainers

- Use constants from `preflight/constants.py` for check names and domains when possible.
- Keep `check_id` stable and descriptive for policy/suppressions.
- Include numeric evidence in `evidence.metrics`.
- Prefer deterministic logic and fixed seeds in tests.

## Legacy note

Legacy `preflight/checks/*` modules remain for compatibility with `check()` and `check_split()`.
Do not add new legacy checks unless explicitly required for backwards compatibility.
