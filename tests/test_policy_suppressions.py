from __future__ import annotations

import json

import numpy as np
import pandas as pd

import preflight
from preflight.config import PreflightConfig
from preflight.policy import load_suppressions


def test_suppression_can_prevent_ci_fail(tmp_path):
    rng = np.random.default_rng(7)
    target = rng.integers(0, 2, 500)
    leak = target + rng.normal(0, 0.001, 500)
    df = pd.DataFrame({"target": target, "leak_col": leak, "noise": rng.normal(0, 1, 500)})

    sup_path = tmp_path / "suppressions.json"
    sup_path.write_text(
        json.dumps(
            [
                {
                    "check_id": "leakage.high_correlation",
                    "reason": "temporary waiver for migration",
                    "expires": "2099-01-01",
                }
            ]
        ),
        encoding="utf-8",
    )
    suppressions = load_suppressions(str(sup_path))
    cfg = PreflightConfig(enabled_checks={"duplicates": False})
    report = preflight.run(
        df, target="target", profile="ci-strict", suppressions=suppressions, config=cfg
    )
    assert report.gate.status == "PASS"
    assert any(f.suppressed for f in report.findings if f.check_id == "leakage.high_correlation")


def test_expired_suppression_is_ignored(tmp_path):
    rng = np.random.default_rng(8)
    target = rng.integers(0, 2, 500)
    leak = target + rng.normal(0, 0.001, 500)
    df = pd.DataFrame({"target": target, "leak_col": leak})

    sup_path = tmp_path / "suppressions.json"
    sup_path.write_text(
        json.dumps(
            [
                {
                    "check_id": "leakage.high_correlation",
                    "reason": "old waiver",
                    "expires": "2000-01-01",
                }
            ]
        ),
        encoding="utf-8",
    )
    suppressions = load_suppressions(str(sup_path))
    report = preflight.run(df, target="target", profile="ci-strict", suppressions=suppressions)
    assert report.gate.status == "FAIL"
