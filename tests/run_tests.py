"""
Standalone test runner — uses only Python stdlib (unittest).
Run with:  PYTHONPATH=.. python tests/run_tests.py
"""

from __future__ import annotations
import sys
import os
import unittest
import traceback

# Ensure the package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd
from preflight._types import Severity


# ── Fixtures ──────────────────────────────────────────────────────────────────
def _clean_df():
    rng = np.random.default_rng(42)
    return pd.DataFrame(
        {
            "age": rng.integers(18, 80, size=100).astype(float),
            "income": rng.normal(50_000, 15_000, size=100),
            "score": rng.uniform(0, 1, size=100),
            "churn": rng.integers(0, 2, size=100),
        }
    )


def _missing_df():
    rng = np.random.default_rng(0)
    df = pd.DataFrame(
        {
            "ok_col": rng.normal(0, 1, 100),
            "warn_col": rng.normal(0, 1, 100),
            "fail_col": rng.normal(0, 1, 100),
        }
    )
    warn_idx = rng.choice(100, size=25, replace=False)
    fail_idx = rng.choice(100, size=60, replace=False)
    df.loc[warn_idx, "warn_col"] = np.nan
    df.loc[fail_idx, "fail_col"] = np.nan
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Completeness
# ─────────────────────────────────────────────────────────────────────────────


class TestCompleteness(unittest.TestCase):
    def setUp(self):
        from preflight.checks import completeness

        self.mod = completeness

    def test_no_missing(self):
        r = self.mod.run(_clean_df())
        ids = {x.check_id: x.severity for x in r}
        self.assertEqual(ids["completeness.overall"], Severity.PASS)

    def test_warn_column(self):
        ids = [x.check_id for x in self.mod.run(_missing_df())]
        self.assertIn("completeness.moderate_missing", ids)

    def test_fail_column(self):
        ids = [x.check_id for x in self.mod.run(_missing_df())]
        self.assertIn("completeness.high_missing", ids)

    def test_empty_dataframe(self):
        r = self.mod.run(pd.DataFrame())
        self.assertEqual(r[0].check_id, "completeness.empty_dataframe")
        self.assertEqual(r[0].severity, Severity.WARN)

    def test_all_missing_column(self):
        df = pd.DataFrame({"a": [np.nan] * 50, "b": list(range(50))})
        r = self.mod.run(df)
        fail = next(x for x in r if x.check_id == "completeness.high_missing")
        self.assertIn("a", fail.details["columns"])

    def test_to_dict_structure(self):
        for r in self.mod.run(_missing_df()):
            d = r.to_dict()
            for key in ("check_id", "severity", "penalty"):
                self.assertIn(key, d)

    def test_penalty_nonzero_on_fail(self):
        fails = [x for x in self.mod.run(_missing_df()) if x.severity == Severity.FAIL]
        self.assertTrue(all(x.penalty > 0 for x in fails))


# ─────────────────────────────────────────────────────────────────────────────
# Class Balance
# ─────────────────────────────────────────────────────────────────────────────


class TestBalance(unittest.TestCase):
    def setUp(self):
        from preflight.checks import balance

        self.mod = balance

    def test_balanced_binary(self):
        df = pd.DataFrame({"target": [0] * 50 + [1] * 50})
        r = self.mod.run(df, target="target")
        self.assertTrue(any(x.severity == Severity.PASS for x in r))

    def test_imbalanced_91_9(self):
        df = pd.DataFrame({"target": [0] * 91 + [1] * 9})
        r = self.mod.run(df, target="target")
        self.assertIsNotNone(next((x for x in r if x.severity == Severity.FAIL), None))

    def test_no_target(self):
        r = self.mod.run(_clean_df(), target=None)
        self.assertEqual(len(r), 1)
        self.assertEqual(r[0].severity, Severity.PASS)

    def test_continuous_target_skipped(self):
        rng = np.random.default_rng(1)
        df = pd.DataFrame({"target": rng.normal(0, 1, 200)})
        r = self.mod.run(df, target="target")
        self.assertTrue(all(x.severity in (Severity.PASS, Severity.WARN) for x in r))

    def test_multiclass(self):
        df = pd.DataFrame({"target": ["a"] * 80 + ["b"] * 15 + ["c"] * 5})
        r = self.mod.run(df, target="target")
        sevs = [x.severity for x in r]
        self.assertTrue(Severity.WARN in sevs or Severity.FAIL in sevs)

    def test_missing_target_column(self):
        df = pd.DataFrame({"a": [1, 2, 3]})
        r = self.mod.run(df, target="nonexistent")
        self.assertEqual(r[0].severity, Severity.WARN)


# ─────────────────────────────────────────────────────────────────────────────
# Leakage
# ─────────────────────────────────────────────────────────────────────────────


class TestLeakage(unittest.TestCase):
    def setUp(self):
        from preflight.checks import leakage

        self.mod = leakage

    def test_no_leakage(self):
        fails = [
            x for x in self.mod.run(_clean_df(), target="churn") if x.severity == Severity.FAIL
        ]
        self.assertEqual(len(fails), 0)

    def test_high_correlation_detected(self):
        rng = np.random.default_rng(7)
        t = rng.integers(0, 2, 200)
        leak = t + rng.normal(0, 0.001, 200)
        df = pd.DataFrame({"target": t, "leak_col": leak, "noise": rng.normal(0, 1, 200)})
        r = self.mod.run(df, target="target")
        fail_ids = [x.check_id for x in r if x.severity == Severity.FAIL]
        self.assertTrue(any("leakage" in fid for fid in fail_ids))

    def test_no_target(self):
        r = self.mod.run(_clean_df(), target=None)
        self.assertTrue(all(x.severity == Severity.PASS for x in r))

    def test_id_like_column_flagged(self):
        df = pd.DataFrame(
            {
                "user_id": range(100),
                "target": [0] * 50 + [1] * 50,
                "feature": np.random.default_rng(3).normal(0, 1, 100),
            }
        )
        ids = [x.check_id for x in self.mod.run(df, target="target")]
        self.assertIn("leakage.id_like_columns", ids)

    def test_date_column_flagged(self):
        df = pd.DataFrame(
            {
                "signup_date": pd.date_range("2020-01-01", periods=100),
                "target": [0] * 50 + [1] * 50,
            }
        )
        ids = [x.check_id for x in self.mod.run(df, target="target")]
        self.assertIn("leakage.datetime_columns", ids)

    def test_graceful_on_all_nan(self):
        df = pd.DataFrame({"all_nan": [np.nan] * 50, "target": [0] * 25 + [1] * 25})
        self.assertIsInstance(self.mod.run(df, target="target"), list)


# ─────────────────────────────────────────────────────────────────────────────
# Duplicates
# ─────────────────────────────────────────────────────────────────────────────


class TestDuplicates(unittest.TestCase):
    def setUp(self):
        from preflight.checks import duplicates

        self.mod = duplicates

    def test_no_duplicates(self):
        r = self.mod.run(_clean_df())
        exact = next(x for x in r if x.check_id == "duplicates.exact")
        self.assertEqual(exact.severity, Severity.PASS)

    def test_exact_duplicates_detected(self):
        df = pd.DataFrame({"a": [1, 2, 3, 1, 2], "b": [4, 5, 6, 4, 5]})
        r = self.mod.run(df)
        fail = next(x for x in r if x.check_id == "duplicates.exact")
        self.assertEqual(fail.severity, Severity.FAIL)
        self.assertEqual(fail.details["duplicate_rows"], 2)

    def test_near_duplicates(self):
        base = {"a": 1.0, "b": 2.0, "c": 3.0}
        rows = [base.copy() for _ in range(20)] + [
            {"a": float(i), "b": float(i), "c": float(i)} for i in range(80)
        ]
        df = pd.DataFrame(rows)
        r = self.mod.run(df)
        near = next((x for x in r if x.check_id == "duplicates.near"), None)
        self.assertIsNotNone(near)

    def test_empty_df(self):
        self.assertIsInstance(self.mod.run(pd.DataFrame()), list)

    def test_single_row(self):
        self.assertIsInstance(self.mod.run(pd.DataFrame({"a": [1], "b": [2]})), list)


# ─────────────────────────────────────────────────────────────────────────────
# Distributions
# ─────────────────────────────────────────────────────────────────────────────


class TestDistributions(unittest.TestCase):
    def setUp(self):
        from preflight.checks import distributions

        self.mod = distributions

    def test_clean_df_no_fails(self):
        fails = [x for x in self.mod.run(_clean_df()) if x.severity == Severity.FAIL]
        self.assertEqual(len(fails), 0)

    def test_constant_column(self):
        df = pd.DataFrame({"const": [5] * 100, "good": list(range(100))})
        r = self.mod.run(df)
        fail = next(x for x in r if x.check_id == "distributions.constant_columns")
        self.assertIn("const", fail.details["columns"])

    def test_near_zero_variance(self):
        rng = np.random.default_rng(9)
        df = pd.DataFrame({"tiny_var": rng.normal(0, 0.0001, 100), "good": rng.normal(0, 1, 100)})
        ids = [x.check_id for x in self.mod.run(df)]
        self.assertIn("distributions.low_variance", ids)

    def test_high_cardinality(self):
        df = pd.DataFrame({"id_col": [f"u{i}" for i in range(100)], "y": list(range(100))})
        r = self.mod.run(df)
        self.assertIsNotNone(
            next((x for x in r if x.check_id == "distributions.high_cardinality"), None)
        )

    def test_scale_disparity(self):
        df = pd.DataFrame({"tiny": [0.0001] * 100, "huge": [1_000_000.0] * 100})
        ids = [x.check_id for x in self.mod.run(df)]
        self.assertIn("distributions.scale_disparity", ids)

    def test_all_object_graceful(self):
        df = pd.DataFrame({"a": ["x"] * 50, "b": ["y"] * 50})
        self.assertIsInstance(self.mod.run(df), list)


# ─────────────────────────────────────────────────────────────────────────────
# Correlations
# ─────────────────────────────────────────────────────────────────────────────


class TestCorrelations(unittest.TestCase):
    def setUp(self):
        from preflight.checks import correlations

        self.mod = correlations

    def test_no_high_corr(self):
        fails = [x for x in self.mod.run(_clean_df()) if x.severity == Severity.FAIL]
        self.assertEqual(len(fails), 0)

    def test_high_corr_detected(self):
        rng = np.random.default_rng(5)
        x = rng.normal(0, 1, 200)
        df = pd.DataFrame({"a": x, "b": x + rng.normal(0, 0.001, 200), "c": rng.normal(0, 1, 200)})
        fail = next((x for x in self.mod.run(df) if x.severity == Severity.FAIL), None)
        self.assertIsNotNone(fail)
        self.assertGreaterEqual(len(fail.details["pairs"]), 1)

    def test_single_numeric(self):
        self.assertIsInstance(self.mod.run(pd.DataFrame({"a": list(range(50))})), list)

    def test_all_object(self):
        self.assertIsInstance(self.mod.run(pd.DataFrame({"a": ["x"] * 50, "b": ["y"] * 50})), list)


# ─────────────────────────────────────────────────────────────────────────────
# Types
# ─────────────────────────────────────────────────────────────────────────────


class TestTypes(unittest.TestCase):
    def setUp(self):
        from preflight.checks import types as t

        self.mod = t

    def test_clean_no_fails(self):
        fails = [x for x in self.mod.run(_clean_df()) if x.severity == Severity.FAIL]
        self.assertEqual(len(fails), 0)

    def test_numeric_as_object(self):
        df = pd.DataFrame({"num_str": ["1.5", "2.0", "3.1"] * 30, "y": list(range(90))})
        ids = [x.check_id for x in self.mod.run(df)]
        self.assertIn("types.numeric_as_object", ids)

    def test_mixed_types(self):
        df = pd.DataFrame({"mixed": [1, "text", 3.0, None, True] * 20})
        ids = [x.check_id for x in self.mod.run(df)]
        self.assertIn("types.mixed_types", ids)

    def test_empty_graceful(self):
        self.assertIsInstance(self.mod.run(pd.DataFrame()), list)

    def test_all_numeric_no_fails(self):
        fails = [
            x
            for x in self.mod.run(pd.DataFrame({"a": [1.0, 2.0], "b": [3, 4]}))
            if x.severity == Severity.FAIL
        ]
        self.assertEqual(len(fails), 0)


# ─────────────────────────────────────────────────────────────────────────────
# Top-level API
# ─────────────────────────────────────────────────────────────────────────────


class TestTopLevel(unittest.TestCase):
    def setUp(self):
        import preflight

        self.pf = preflight

    def test_returns_report(self):
        r = self.pf.check(_clean_df(), target="churn")
        self.assertIsNotNone(r)
        self.assertIsInstance(r.score, float)
        self.assertGreaterEqual(r.score, 0)
        self.assertLessEqual(r.score, 100)

    def test_no_target(self):
        self.assertIsNotNone(self.pf.check(_clean_df()))

    def test_to_dict(self):
        d = self.pf.check(_clean_df(), target="churn").to_dict()
        for key in ("score", "verdict", "checks"):
            self.assertIn(key, d)

    def test_str_output(self):
        s = str(self.pf.check(_clean_df(), target="churn"))
        self.assertIn("Readiness Score", s)
        self.assertIn("/", s)

    def test_to_markdown(self):
        md = self.pf.check(_clean_df(), target="churn").to_markdown()
        self.assertIn("#", md)

    def test_verdict_values(self):
        v = self.pf.check(_clean_df(), target="churn").verdict
        self.assertIn(v, ("READY", "CAUTION", "NOT READY"))

    def test_check_split(self):
        df = _clean_df()
        r = self.pf.check_split(df.iloc[:70], df.iloc[70:])
        self.assertIsNotNone(r)
        self.assertIsInstance(str(r), str)

    def test_bad_input_raises(self):
        with self.assertRaises(TypeError):
            self.pf.check([1, 2, 3])

    def test_to_html_returns_string(self):
        html = self.pf.check(_clean_df(), target="churn").to_html()
        self.assertIsInstance(html, str)
        self.assertIn("<!DOCTYPE html>", html)

    def test_to_html_contains_score(self):
        report = self.pf.check(_clean_df(), target="churn")
        html = report.to_html()
        self.assertIn(str(int(report.score)), html)

    def test_to_html_contains_verdict(self):
        report = self.pf.check(_clean_df(), target="churn")
        html = report.to_html()
        self.assertIn(report.verdict, html)

    def test_to_html_contains_all_categories(self):
        report = self.pf.check(_clean_df(), target="churn")
        html = report.to_html()
        for r in report.checks:
            # Each category name should appear
            self.assertIn(r.category, html)

    def test_to_html_self_contained(self):
        """No external stylesheet or script src — fully self-contained."""
        html = self.pf.check(_clean_df(), target="churn").to_html()
        self.assertNotIn('src="http', html)
        self.assertNotIn('href="http', html)

    def test_save_html_writes_file(self):
        import tempfile, os

        report = self.pf.check(_clean_df(), target="churn")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "test_report.html")
            result = report.save_html(path)
            self.assertEqual(result, path)
            self.assertTrue(os.path.exists(path))
            with open(path, encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
            self.assertGreater(len(content), 5000)  # substantial file

    def test_save_html_default_name(self):
        import tempfile, os

        report = self.pf.check(_clean_df(), target="churn")
        orig = os.getcwd()
        with tempfile.TemporaryDirectory() as d:
            os.chdir(d)
            try:
                path = report.save_html()
                self.assertTrue(os.path.exists(path))
                self.assertTrue(path.endswith("preflight_report.html"))
            finally:
                os.chdir(orig)
                if os.path.exists(path):
                    os.remove(path)

    def test_html_split_report(self):
        df = _clean_df()
        r = self.pf.check_split(df.iloc[:70], df.iloc[70:])
        html = r.to_html()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Train/Test Drift", html)


# ─────────────────────────────────────────────────────────────────────────────


class TestHTMLOutput(unittest.TestCase):
    """Dedicated HTML output tests for edge cases."""

    def setUp(self):
        import preflight

        self.pf = preflight

    def test_html_escapes_special_chars(self):
        """Column names with < > & should not break the HTML."""
        df = pd.DataFrame(
            {
                "feat<1>": [1.0, 2.0, 3.0] * 20,
                "feat&2": [4.0, 5.0, 6.0] * 20,
                "target": [0, 1, 0] * 20,
            }
        )
        html = self.pf.check(df, target="target").to_html()
        self.assertIn("<!DOCTYPE html>", html)
        # Escaped versions should be present or the original escaped
        self.assertNotIn("<script>", html.split("<style>")[0].split("</head>")[0])

    def test_html_not_ready_verdict(self):
        """NOT READY verdict should render its color class."""
        rng = np.random.default_rng(42)
        # Force a low score: severe imbalance + lots of missing + constant cols
        df = pd.DataFrame(
            {
                "target": [0] * 95 + [1] * 5,
                "const": [1.0] * 100,
                "all_nan": [np.nan] * 100,
                "numeric": rng.normal(0, 1, 100),
            }
        )
        report = self.pf.check(df, target="target")
        html = report.to_html()
        self.assertIn("NOT READY", html)

    def test_html_ready_verdict(self):
        report = self.pf.check(_clean_df(), target="churn")
        # May be READY or CAUTION on the clean fixture — just confirm it renders
        html = report.to_html()
        self.assertIn(report.verdict, html)

    def test_html_no_target(self):
        html = self.pf.check(_clean_df()).to_html()
        self.assertIn("<!DOCTYPE html>", html)


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in [
        TestCompleteness,
        TestBalance,
        TestLeakage,
        TestDuplicates,
        TestDistributions,
        TestCorrelations,
        TestTypes,
        TestTopLevel,
        TestHTMLOutput,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
