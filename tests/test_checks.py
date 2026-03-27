"""
Pytest suite for all preflight check modules.
Tests are grouped by module and cover edge cases.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from preflight._types import Severity

# ─────────────────────────────────────────────────────────────────────────────
# Completeness
# ─────────────────────────────────────────────────────────────────────────────


class TestCompleteness:
    from preflight.checks import completeness

    def test_no_missing(self, clean_df):
        from preflight.checks import completeness

        results = completeness.run(clean_df)
        severities = {r.check_id: r.severity for r in results}
        assert severities["completeness.overall"] == Severity.PASS

    def test_warn_column(self, missing_df):
        from preflight.checks import completeness

        results = completeness.run(missing_df)
        ids = [r.check_id for r in results]
        assert "completeness.moderate_missing" in ids

    def test_fail_column(self, missing_df):
        from preflight.checks import completeness

        results = completeness.run(missing_df)
        ids = [r.check_id for r in results]
        assert "completeness.high_missing" in ids

    def test_empty_dataframe(self):
        from preflight.checks import completeness

        results = completeness.run(pd.DataFrame())
        assert results[0].check_id == "completeness.empty_dataframe"
        assert results[0].severity == Severity.WARN

    def test_all_missing_column(self):
        from preflight.checks import completeness

        df = pd.DataFrame({"a": [np.nan] * 50, "b": list(range(50))})
        results = completeness.run(df)
        fail = next(r for r in results if r.check_id == "completeness.high_missing")
        assert "a" in fail.details["columns"]

    def test_details_structure(self, missing_df):
        from preflight.checks import completeness

        results = completeness.run(missing_df)
        for r in results:
            d = r.to_dict()
            assert "check_id" in d
            assert "severity" in d
            assert "penalty" in d

    def test_penalty_nonzero_on_fail(self, missing_df):
        from preflight.checks import completeness

        results = completeness.run(missing_df)
        fail_results = [r for r in results if r.severity == Severity.FAIL]
        assert all(r.penalty > 0 for r in fail_results)


# ─────────────────────────────────────────────────────────────────────────────
# Class Balance
# ─────────────────────────────────────────────────────────────────────────────


class TestBalance:
    def test_balanced_binary(self):
        from preflight.checks import balance

        df = pd.DataFrame({"target": [0] * 50 + [1] * 50})
        results = balance.run(df, target="target")
        assert any(r.severity == Severity.PASS for r in results)

    def test_imbalanced_91_9(self):
        from preflight.checks import balance

        df = pd.DataFrame({"target": [0] * 91 + [1] * 9})
        results = balance.run(df, target="target")
        fail = next((r for r in results if r.severity == Severity.FAIL), None)
        assert fail is not None

    def test_no_target(self, clean_df):
        from preflight.checks import balance

        results = balance.run(clean_df, target=None)
        assert len(results) == 1
        assert results[0].severity == Severity.PASS

    def test_continuous_target_skipped(self):
        from preflight.checks import balance

        rng = np.random.default_rng(1)
        df = pd.DataFrame({"target": rng.normal(0, 1, 200)})
        results = balance.run(df, target="target")
        # continuous target → skip balance, return info pass
        assert all(r.severity in (Severity.PASS, Severity.WARN) for r in results)

    def test_multiclass(self):
        from preflight.checks import balance

        df = pd.DataFrame({"target": ["a"] * 80 + ["b"] * 15 + ["c"] * 5})
        results = balance.run(df, target="target")
        severities = [r.severity for r in results]
        assert Severity.WARN in severities or Severity.FAIL in severities

    def test_missing_target_column(self):
        from preflight.checks import balance

        df = pd.DataFrame({"a": [1, 2, 3]})
        results = balance.run(df, target="nonexistent")
        assert results[0].severity == Severity.WARN


# ─────────────────────────────────────────────────────────────────────────────
# Leakage Detection
# ─────────────────────────────────────────────────────────────────────────────


class TestLeakage:
    def test_no_leakage(self, clean_df):
        from preflight.checks import leakage

        results = leakage.run(clean_df, target="churn")
        fail = [r for r in results if r.severity == Severity.FAIL]
        assert len(fail) == 0

    def test_high_correlation_detected(self):
        from preflight.checks import leakage

        rng = np.random.default_rng(7)
        target = rng.integers(0, 2, 200)
        leak = target + rng.normal(0, 0.001, 200)  # near-perfect correlation
        df = pd.DataFrame({"target": target, "leak_col": leak, "noise": rng.normal(0, 1, 200)})
        results = leakage.run(df, target="target")
        fail_ids = [r.check_id for r in results if r.severity == Severity.FAIL]
        assert any("leakage" in fid for fid in fail_ids)

    def test_no_target(self, clean_df):
        from preflight.checks import leakage

        results = leakage.run(clean_df, target=None)
        assert all(r.severity == Severity.PASS for r in results)

    def test_id_like_column_flagged(self):
        from preflight.checks import leakage

        df = pd.DataFrame(
            {
                "user_id": range(100),
                "target": [0] * 50 + [1] * 50,
                "feature": np.random.default_rng(3).normal(0, 1, 100),
            }
        )
        results = leakage.run(df, target="target")
        ids = [r.check_id for r in results]
        assert "leakage.id_like_columns" in ids

    def test_date_column_flagged(self):
        from preflight.checks import leakage

        df = pd.DataFrame(
            {
                "signup_date": pd.date_range("2020-01-01", periods=100),
                "target": [0] * 50 + [1] * 50,
            }
        )
        results = leakage.run(df, target="target")
        ids = [r.check_id for r in results]
        assert "leakage.datetime_columns" in ids

    def test_graceful_on_all_nan(self):
        from preflight.checks import leakage

        df = pd.DataFrame({"all_nan": [np.nan] * 50, "target": [0] * 25 + [1] * 25})
        results = leakage.run(df, target="target")
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────────────────
# Duplicates
# ─────────────────────────────────────────────────────────────────────────────


class TestDuplicates:
    def test_no_duplicates(self, clean_df):
        from preflight.checks import duplicates

        results = duplicates.run(clean_df)
        assert any(
            r.check_id == "duplicates.exact" and r.severity == Severity.PASS for r in results
        )

    def test_exact_duplicates_detected(self):
        from preflight.checks import duplicates

        df = pd.DataFrame({"a": [1, 2, 3, 1, 2], "b": [4, 5, 6, 4, 5]})
        results = duplicates.run(df)
        fail = next(r for r in results if r.check_id == "duplicates.exact")
        assert fail.severity == Severity.FAIL
        assert fail.details["duplicate_rows"] == 2

    def test_near_duplicates(self):
        from preflight.checks import duplicates

        base = {"a": 1.0, "b": 2.0, "c": 3.0}
        rows = [base.copy() for _ in range(20)] + [
            {"a": float(i), "b": float(i), "c": float(i)} for i in range(80)
        ]
        df = pd.DataFrame(rows)
        results = duplicates.run(df)
        near = next((r for r in results if r.check_id == "duplicates.near"), None)
        assert near is not None

    def test_empty_df(self):
        from preflight.checks import duplicates

        results = duplicates.run(pd.DataFrame())
        assert isinstance(results, list)

    def test_single_row(self):
        from preflight.checks import duplicates

        df = pd.DataFrame({"a": [1], "b": [2]})
        results = duplicates.run(df)
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────────────────
# Distributions
# ─────────────────────────────────────────────────────────────────────────────


class TestDistributions:
    def test_clean_df_passes(self, clean_df):
        from preflight.checks import distributions

        results = distributions.run(clean_df)
        fails = [r for r in results if r.severity == Severity.FAIL]
        assert len(fails) == 0

    def test_constant_column_flagged(self):
        from preflight.checks import distributions

        df = pd.DataFrame({"const": [5] * 100, "good": list(range(100))})
        results = distributions.run(df)
        fail = next(r for r in results if r.check_id == "distributions.constant_columns")
        assert "const" in fail.details["columns"]

    def test_near_zero_variance_flagged(self):
        from preflight.checks import distributions

        rng = np.random.default_rng(9)
        df = pd.DataFrame(
            {
                "tiny_var": rng.normal(0, 0.0001, 100),
                "good": rng.normal(0, 1, 100),
            }
        )
        results = distributions.run(df)
        ids = [r.check_id for r in results]
        assert "distributions.low_variance" in ids

    def test_high_cardinality_flagged(self):
        from preflight.checks import distributions

        df = pd.DataFrame({"id_col": [f"user_{i}" for i in range(100)], "y": list(range(100))})
        results = distributions.run(df)
        fail = next((r for r in results if r.check_id == "distributions.high_cardinality"), None)
        assert fail is not None

    def test_scale_disparity_flagged(self):
        from preflight.checks import distributions

        df = pd.DataFrame(
            {
                "tiny": [0.0001] * 100,
                "huge": [1_000_000.0] * 100,
            }
        )
        results = distributions.run(df)
        ids = [r.check_id for r in results]
        assert "distributions.scale_disparity" in ids

    def test_all_object_columns_skipped_gracefully(self):
        from preflight.checks import distributions

        df = pd.DataFrame({"a": ["x"] * 50, "b": ["y"] * 50})
        results = distributions.run(df)
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────────────────
# Correlations
# ─────────────────────────────────────────────────────────────────────────────


class TestCorrelations:
    def test_no_high_correlation(self, clean_df):
        from preflight.checks import correlations

        results = correlations.run(clean_df)
        fails = [r for r in results if r.severity == Severity.FAIL]
        assert len(fails) == 0

    def test_highly_correlated_pair_detected(self):
        from preflight.checks import correlations

        rng = np.random.default_rng(5)
        x = rng.normal(0, 1, 200)
        df = pd.DataFrame({"a": x, "b": x + rng.normal(0, 0.001, 200), "c": rng.normal(0, 1, 200)})
        results = correlations.run(df)
        fail = next((r for r in results if r.severity == Severity.FAIL), None)
        assert fail is not None
        assert len(fail.details["pairs"]) >= 1

    def test_single_numeric_column(self):
        from preflight.checks import correlations

        df = pd.DataFrame({"a": list(range(50))})
        results = correlations.run(df)
        assert isinstance(results, list)

    def test_all_object_columns(self):
        from preflight.checks import correlations

        df = pd.DataFrame({"a": ["x"] * 50, "b": ["y"] * 50})
        results = correlations.run(df)
        assert isinstance(results, list)


# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────


class TestTypes:
    def test_clean_df_no_issues(self, clean_df):
        from preflight.checks import types as types_check

        results = types_check.run(clean_df)
        fails = [r for r in results if r.severity == Severity.FAIL]
        assert len(fails) == 0

    def test_numeric_stored_as_object(self):
        from preflight.checks import types as types_check

        df = pd.DataFrame({"numeric_str": ["1.5", "2.0", "3.1"] * 30, "y": list(range(90))})
        results = types_check.run(df)
        ids = [r.check_id for r in results]
        assert "types.numeric_as_object" in ids

    def test_mixed_types_in_object_column(self):
        from preflight.checks import types as types_check

        df = pd.DataFrame({"mixed": [1, "text", 3.0, None, True] * 20})
        results = types_check.run(df)
        ids = [r.check_id for r in results]
        assert "types.mixed_types" in ids

    def test_empty_df_graceful(self):
        from preflight.checks import types as types_check

        results = types_check.run(pd.DataFrame())
        assert isinstance(results, list)

    def test_all_numeric(self):
        from preflight.checks import types as types_check

        df = pd.DataFrame({"a": [1.0, 2.0], "b": [3, 4]})
        results = types_check.run(df)
        fails = [r for r in results if r.severity == Severity.FAIL]
        assert len(fails) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Integration: top-level check()
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.integration
class TestTopLevelAPI:
    def test_check_returns_report(self, clean_df):
        import preflight

        report = preflight.check(clean_df, target="churn")
        assert report is not None
        assert isinstance(report.score, (int, float))
        assert 0 <= report.score <= 100

    def test_check_no_target(self, clean_df):
        import preflight

        report = preflight.check(clean_df)
        assert report is not None

    def test_report_to_dict(self, clean_df):
        import preflight

        d = preflight.check(clean_df, target="churn").to_dict()
        assert "score" in d
        assert "verdict" in d
        assert "checks" in d

    def test_report_str(self, clean_df):
        import preflight

        s = str(preflight.check(clean_df, target="churn"))
        assert "Readiness Score" in s
        assert "/" in s

    def test_report_to_markdown(self, clean_df):
        import preflight

        md = preflight.check(clean_df, target="churn").to_markdown()
        assert "##" in md or "#" in md

    def test_verdict_values(self, clean_df):
        import preflight

        report = preflight.check(clean_df, target="churn")
        assert report.verdict in ("READY", "CAUTION", "NOT READY")

    def test_check_split(self, clean_df):
        import preflight

        train = clean_df.iloc[:70]
        test = clean_df.iloc[70:]
        report = preflight.check_split(train, test)
        assert report is not None
        assert isinstance(str(report), str)

    def test_report_html_and_repr(self):
        from preflight._types import CheckResult
        from preflight.report import Report

        checks = [
            CheckResult.passed(
                "completeness.overall",
                "Completeness",
                "No missing values detected.",
            ),
            CheckResult.warn(
                "balance.imbalance_warn",
                "Class Balance",
                "Moderate class imbalance.",
                penalty=7.0,
            ),
            CheckResult.fail(
                "leakage.correlation",
                "Leakage Detection",
                "Potential leakage in feature <target_proxy>.",
                penalty=20.0,
            ),
        ]
        report = Report(
            checks=checks,
            score=73.6,
            verdict="CAUTION",
            metadata={"rows": 1234, "cols": 9, "target": 'churn<script>alert("x")</script>'},
        )

        html = report.to_html()
        assert "<!DOCTYPE html>" in html
        assert "Preflight Report" in html
        assert "churn&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;" in html
        assert "Potential leakage in feature &lt;target_proxy&gt;." in html

        rep = repr(report)
        assert "preflight.Report" in rep
        assert "score=73.6/100" in rep
        assert "checks=3" in rep

    def test_save_html_writes_file(self, tmp_path):
        from preflight._types import CheckResult
        from preflight.report import Report

        report = Report(
            checks=[CheckResult.passed("types.ok", "Data Types", "Looks good.")],
            score=95.0,
            verdict="READY",
            metadata={"rows": 10, "cols": 2},
        )

        out = report.save_html(str(tmp_path / "report.html"))
        assert out.endswith("report.html")
        content = (tmp_path / "report.html").read_text(encoding="utf-8")
        assert '<html lang="en">' in content
        assert "Generated by <strong>preflight-data</strong>" in content


@pytest.mark.integration
class TestCoverageBranches:
    def test_check_type_error(self):
        import preflight

        with pytest.raises(TypeError):
            preflight.check([1, 2, 3], target="y")

    def test_check_split_type_error(self):
        import preflight

        with pytest.raises(TypeError):
            preflight.check_split([1, 2], [3, 4])

    def test_check_split_no_numeric_columns(self):
        import preflight

        train = pd.DataFrame({"a": ["x", "y"], "b": ["u", "v"]})
        test = pd.DataFrame({"a": ["p", "q"], "b": ["m", "n"]})
        report = preflight.check_split(train, test)
        d = report.to_dict()
        assert report.verdict == "READY"
        assert d["checks"][0]["check_id"] == "split.no_numeric"

    def test_compute_psi_small_arrays_returns_none(self):
        import preflight

        assert preflight._compute_psi(np.array([1, 2, 3]), np.array([1, 2, 4]), n_bins=10) is None

    def test_check_split_moderate_and_high_drift_branches(self, monkeypatch):
        import preflight

        train = pd.DataFrame({"x": np.arange(100), "y": np.arange(100)})
        test = pd.DataFrame({"x": np.arange(100), "y": np.arange(100)})

        vals = iter([0.15, 0.35])

        def fake_psi(*_args, **_kwargs):
            return next(vals)

        monkeypatch.setattr(preflight, "_compute_psi", fake_psi)
        report = preflight.check_split(train, test, threshold_psi=0.3)
        ids = [c["check_id"] for c in report.to_dict()["checks"]]
        assert "split.moderate_drift" in ids
        assert "split.high_drift" in ids

    def test_check_split_stable_and_none_psi_continue_branch(self, monkeypatch):
        import preflight

        train = pd.DataFrame({"x": np.arange(200), "y": np.arange(200)})
        test = pd.DataFrame({"x": np.arange(200), "y": np.arange(200)})

        vals = iter([None, 0.05])

        def fake_psi(*_args, **_kwargs):
            return next(vals)

        monkeypatch.setattr(preflight, "_compute_psi", fake_psi)
        report = preflight.check_split(train, test, threshold_psi=0.2)
        ids = [c["check_id"] for c in report.to_dict()["checks"]]
        assert "split.stable" in ids

    def test_balance_empty_target_branch(self):
        from preflight.checks import balance

        df = pd.DataFrame({"target": [np.nan, np.nan, np.nan]})
        results = balance.run(df, target="target")
        assert results[0].check_id == "balance.empty_target"

    def test_balance_warn_branch_ratio(self):
        from preflight.checks import balance

        df = pd.DataFrame({"target": [0] * 80 + [1] * 20})
        results = balance.run(df, target="target")
        assert any(
            r.check_id == "balance.imbalanced" and r.severity == Severity.WARN for r in results
        )

    def test_completeness_overall_warn_and_per_column_pass(self):
        from preflight.checks import completeness

        rng = np.random.default_rng(44)
        df = pd.DataFrame({"a": rng.normal(size=100), "b": rng.normal(size=100)})
        # overall missing 10%, per-column 10% (below 20% threshold)
        df.loc[:9, "a"] = np.nan
        results = completeness.run(df)
        ids = [r.check_id for r in results]
        assert "completeness.overall" in ids
        assert "completeness.per_column" in ids
        overall = next(r for r in results if r.check_id == "completeness.overall")
        assert overall.severity == Severity.WARN

    def test_correlations_warn_and_exception_branches(self, monkeypatch):
        from preflight.checks import correlations

        df = pd.DataFrame({"x": np.arange(10), "y": np.arange(10)})

        def warn_corr(self, method="pearson"):
            cols = list(self.columns)
            return pd.DataFrame(
                [[1.0, 0.92], [0.92, 1.0]],
                index=cols,
                columns=cols,
            )

        monkeypatch.setattr(pd.DataFrame, "corr", warn_corr)
        results = correlations.run(df)
        assert any(r.severity == Severity.WARN for r in results)

        def boom(*_args, **_kwargs):
            raise RuntimeError("boom")

        monkeypatch.setattr(pd.DataFrame, "corr", boom)
        results_err = correlations.run(df)
        assert results_err[0].severity == Severity.WARN
        assert "failed" in results_err[0].message

    def test_correlations_nan_pair_skipped(self, monkeypatch):
        from preflight.checks import correlations

        df = pd.DataFrame({"x": np.arange(10), "y": np.arange(10)})

        def nan_corr(self, method="pearson"):
            cols = list(self.columns)
            return pd.DataFrame(
                [[1.0, np.nan], [np.nan, 1.0]],
                index=cols,
                columns=cols,
            )

        monkeypatch.setattr(pd.DataFrame, "corr", nan_corr)
        results = correlations.run(df)
        assert results[0].severity == Severity.PASS

    def test_distributions_empty_and_scale_pass(self):
        from preflight.checks import distributions

        assert distributions.run(pd.DataFrame()) == []

        rng = np.random.default_rng(8)
        df = pd.DataFrame(
            {
                "x": rng.normal(0, 1.0, 200),
                "y": rng.normal(0, 1.2, 200),
            }
        )
        results = distributions.run(df)
        scale = next(r for r in results if r.check_id == "distributions.scale_disparity")
        assert scale.severity == Severity.PASS

    def test_distributions_skip_paths_and_target_exclusion(self):
        from preflight.checks import distributions

        df = pd.DataFrame(
            {
                "target": [0] * 50 + [1] * 50,
                "numeric_single": [1.0] + [np.nan] * 99,
                "obj_empty": [np.nan] * 100,
                "obj_high_card": [f"id_{i}" for i in range(100)],
                "const_nonzero": [7.0] * 100,
                "varying": np.linspace(1, 2, 100),
            }
        )
        results = distributions.run(df, target="target")
        ids = [r.check_id for r in results]
        assert "distributions.high_cardinality" in ids
        assert "distributions.scale_disparity" in ids

    def test_distributions_low_variance_warn_and_object_empty_branch(self):
        from preflight.checks import distributions

        n = 10_000
        mostly_mid = np.full(n, 0.5)
        mostly_mid[0] = 0.0
        mostly_mid[1] = 1.0
        df = pd.DataFrame(
            {
                "near_zero": mostly_mid,
                "normal": np.linspace(0.0, 10.0, n),
                "obj_all_nan": pd.Series([np.nan] * n, dtype=object),
                "obj_unique": pd.Series([f"id_{i}" for i in range(n)], dtype=object),
            }
        )
        results = distributions.run(df)
        low_var = next(r for r in results if r.check_id == "distributions.low_variance")
        assert low_var.severity == Severity.WARN
        high_card = next(r for r in results if r.check_id == "distributions.high_cardinality")
        assert high_card.severity == Severity.WARN

    def test_distributions_skips_object_target_in_high_cardinality_loop(self):
        from preflight.checks import distributions

        df = pd.DataFrame(
            {
                "target": pd.Series([f"class_{i}" for i in range(100)], dtype=object),
                "feature_obj": pd.Series([f"user_{i}" for i in range(100)], dtype=object),
                "num": np.linspace(0.0, 1.0, 100),
            }
        )
        results = distributions.run(df, target="target")
        high_card = next(r for r in results if r.check_id == "distributions.high_cardinality")
        assert "feature_obj" in high_card.details["columns"]
        assert "target" not in high_card.details["columns"]

    def test_duplicates_exact_warn_and_near_fail_and_no_numeric(self):
        from preflight.checks import duplicates

        # exact duplicates warn branch: <1%
        rows = [{"a": float(i), "b": float(i + 1)} for i in range(300)]
        rows.append({"a": 1.0, "b": 2.0})  # one duplicate pair
        df_warn = pd.DataFrame(rows)
        exact_warn = next(r for r in duplicates.run(df_warn) if r.check_id == "duplicates.exact")
        assert exact_warn.severity == Severity.WARN

        # near-duplicate fail branch: many near duplicates
        base = {"a": 1.001, "b": 2.001}
        near_rows = [base.copy() for _ in range(70)] + [
            {"a": float(i), "b": float(i + 10)} for i in range(30)
        ]
        near_fail = next(
            r for r in duplicates.run(pd.DataFrame(near_rows)) if r.check_id == "duplicates.near"
        )
        assert near_fail.severity == Severity.FAIL

        # no numeric columns branch
        no_num = duplicates.run(pd.DataFrame({"x": ["a", "b"], "y": ["c", "d"]}))
        near_pass = next(r for r in no_num if r.check_id == "duplicates.near")
        assert near_pass.severity == Severity.PASS

    def test_leakage_warn_correlation_and_non_id_and_dt_parse_exception(self, monkeypatch):
        from preflight.checks import leakage

        rng = np.random.default_rng(111)
        target = rng.integers(0, 2, 500)
        # roughly warn-level correlation around 0.85-0.95
        weak_noise = rng.normal(0, 0.2, 500)
        maybe_leak = target + weak_noise
        df = pd.DataFrame(
            {
                "target": target,
                "feature": maybe_leak,
                "plain_text": ["alpha"] * 500,
                "dt_like": ["not-a-date"] * 500,
            }
        )
        results = leakage.run(df, target="target")
        corr = next(r for r in results if r.check_id == "leakage.high_correlation")
        assert corr.severity == Severity.WARN

        # ensure non-ID branch can pass when features are not id-like
        non_id = next(r for r in results if r.check_id == "leakage.id_like_columns")
        assert non_id.severity in (Severity.PASS, Severity.WARN)

        def bad_to_datetime(*_args, **_kwargs):
            raise ValueError("bad parse")

        monkeypatch.setattr(pd, "to_datetime", bad_to_datetime)
        results2 = leakage.run(df, target="target")
        dt = next(r for r in results2 if r.check_id == "leakage.datetime_columns")
        assert dt.severity == Severity.PASS

    def test_types_helper_and_no_object_and_clean_object_branches(self):
        from preflight.checks import types as types_check

        assert types_check._looks_numeric(pd.Series([np.nan, np.nan])) is False
        assert types_check._has_mixed_types(pd.Series([1, "x", True])) is True
        assert types_check._has_mixed_types(pd.Series([np.nan, np.nan])) is False
        assert types_check._has_mixed_types(pd.Series(["x", b"y", complex(1, 2)])) is True

        no_obj = types_check.run(pd.DataFrame({"a": [1.0, 2.0], "b": [3, 4]}))
        assert no_obj[0].check_id == "types.no_object_columns"

        clean_obj = types_check.run(pd.DataFrame({"cat": ["a", "b", "a", "b"] * 10}))
        ids = [r.check_id for r in clean_obj]
        assert "types.numeric_as_object" in ids
        assert "types.mixed_types" in ids
        assert all(
            r.severity == Severity.PASS
            for r in clean_obj
            if r.check_id != "types.no_object_columns"
        )

    def test_scorer_caution_branch(self):
        from preflight._types import CheckResult
        from preflight.scorer import compute_score

        score, verdict = compute_score(
            [
                CheckResult.warn("a", "A", "warn", penalty=20.0),
                CheckResult.warn("b", "A", "warn2", penalty=10.0),
            ]
        )
        assert score == 70.0
        assert verdict == "CAUTION"

    def test_report_default_save_and_not_ready_color_branch(self, monkeypatch, tmp_path):
        import os
        from preflight._types import CheckResult
        from preflight.report import Report

        report = Report(
            checks=[CheckResult.fail("x", "X", "fail", penalty=40.0)],
            score=45.0,
            verdict="NOT READY",
            metadata={"rows": 2, "cols": 1},
        )
        html = report.to_html()
        assert "#ef4444" in html

        monkeypatch.chdir(tmp_path)
        out = report.save_html()
        assert out.endswith("preflight_report.html")
        assert os.path.exists(out)

    def test_leakage_helper_importerror_and_exception_paths(self, monkeypatch):
        import builtins
        from preflight.checks import leakage

        s = pd.Series([0.0, 1.0, 0.0, 1.0] * 30)
        t = pd.Series([0.0, 1.0, 0.0, 1.0] * 30)

        real_import = builtins.__import__

        def fake_import(name, *args, **kwargs):
            if name == "scipy.stats":
                raise ImportError("forced")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", fake_import)
        val = leakage._pearson_or_pointbiserial(s, t)
        assert val is not None

        # cover the broad exception guard in helper
        bad = pd.Series([object()] * 200)
        assert leakage._pearson_or_pointbiserial(bad, t) is None

    def test_leakage_helper_constant_and_multiclass_paths(self):
        from preflight.checks import leakage

        x = pd.Series(np.arange(200, dtype=float))
        y_constant = pd.Series([1.0] * 200)
        assert leakage._pearson_or_pointbiserial(x, y_constant) is None

        y_multi = pd.Series(np.arange(200) % 5, dtype=float)
        val = leakage._pearson_or_pointbiserial(x, y_multi)
        assert val is not None

    def test_leakage_id_name_and_unique_object_branches(self):
        from preflight.checks import leakage

        uuid_values = pd.Series([f"u{i}" for i in range(120)], dtype=object)
        df = pd.DataFrame(
            {
                "id": np.arange(120),
                "uuid_text": uuid_values,
                "target": [0, 1] * 60,
            }
        )
        results = leakage.run(df, target="target")
        id_result = next(r for r in results if r.check_id == "leakage.id_like_columns")
        cols = id_result.details["columns"]
        assert "id" in cols
        assert len(cols) >= 1

    def test_leakage_datetime_object_parse_exception_branch(self, monkeypatch):
        from preflight.checks import leakage

        dt_obj = pd.Series(["not-a-date"] * 120, dtype=object)
        df = pd.DataFrame({"target": [0, 1] * 60, "dt_obj": dt_obj})

        def bad_to_datetime(*_args, **_kwargs):
            raise ValueError("forced parser error")

        monkeypatch.setattr(pd, "to_datetime", bad_to_datetime)
        results = leakage.run(df, target="target")
        dt_result = next(r for r in results if r.check_id == "leakage.datetime_columns")
        assert dt_result.severity == Severity.PASS

    def test_leakage_datetime_object_parse_success_branch(self):
        from preflight.checks import leakage

        df = pd.DataFrame(
            {
                "target": [0, 1] * 60,
                "date_text": pd.Series(
                    [f"2024-01-{(i % 28) + 1:02d}" for i in range(120)],
                    dtype=object,
                ),
            }
        )
        results = leakage.run(df, target="target")
        dt_result = next(r for r in results if r.check_id == "leakage.datetime_columns")
        assert dt_result.severity == Severity.WARN
        assert "date_text" in dt_result.details["columns"]
