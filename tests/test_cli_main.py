from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from preflight.cli import main


def _write_csv(path: Path, df: pd.DataFrame) -> None:
    df.to_csv(path, index=False)


def test_cli_run_json_and_output_html(tmp_path):
    data = pd.DataFrame({"a": [1, 2, 3, 4], "target": [0, 1, 0, 1]})
    csv_path = tmp_path / "data.csv"
    out_json = tmp_path / "run.json"
    out_html = tmp_path / "run.html"
    _write_csv(csv_path, data)

    rc = main(
        [
            "run",
            str(csv_path),
            "--target",
            "target",
            "--format",
            "json",
            "--output",
            str(out_json),
            "--output-html",
            str(out_html),
        ]
    )
    assert rc in (0, 2)
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "2.0.0"
    assert out_html.exists()
    assert "<html" in out_html.read_text(encoding="utf-8").lower()


def test_cli_run_split_markdown(tmp_path):
    train = pd.DataFrame({"x": [1, 2, 3, 4, 5], "cat": ["a", "a", "b", "b", "c"]})
    test = pd.DataFrame({"x": [1, 2, 3, 4, 6], "cat": ["a", "b", "b", "c", "c"]})
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    out_md = tmp_path / "run_split.md"
    _write_csv(train_path, train)
    _write_csv(test_path, test)

    rc = main(
        [
            "run-split",
            str(train_path),
            str(test_path),
            "--format",
            "markdown",
            "--output",
            str(out_md),
        ]
    )
    assert rc in (0, 2)
    text = out_md.read_text(encoding="utf-8")
    assert "Preflight Run Report" in text
    assert "Findings" in text


def test_cli_legacy_check_and_check_split(tmp_path):
    df = pd.DataFrame({"a": [1, 2, 3, 4], "target": [0, 1, 0, 1]})
    csv_path = tmp_path / "data.csv"
    train_path = tmp_path / "train.csv"
    test_path = tmp_path / "test.csv"
    out_check = tmp_path / "check.json"
    out_split = tmp_path / "check_split.md"
    _write_csv(csv_path, df)
    _write_csv(train_path, df.iloc[:2])
    _write_csv(test_path, df.iloc[2:])

    rc_check = main(
        [
            "check",
            str(csv_path),
            "--target",
            "target",
            "--format",
            "json",
            "--output",
            str(out_check),
        ]
    )
    assert rc_check == 0
    payload = json.loads(out_check.read_text(encoding="utf-8"))
    assert "schema_version" in payload

    rc_split = main(
        [
            "check-split",
            str(train_path),
            str(test_path),
            "--format",
            "markdown",
            "--output",
            str(out_split),
        ]
    )
    assert rc_split == 0
    assert "Preflight Dataset Report" in out_split.read_text(encoding="utf-8")


def test_cli_compare_text_and_json(tmp_path):
    baseline = {
        "score": {"value": 90},
        "summary": {
            "severity_counts": {"critical": 0, "error": 0},
            "domain_counts": {"target_risk": 1},
        },
    }
    current = {
        "score": {"value": 85},
        "summary": {
            "severity_counts": {"critical": 0, "error": 1},
            "domain_counts": {"target_risk": 4},
        },
    }
    base_path = tmp_path / "baseline.json"
    cur_path = tmp_path / "current.json"
    out_path = tmp_path / "compare.json"
    base_path.write_text(json.dumps(baseline), encoding="utf-8")
    cur_path.write_text(json.dumps(current), encoding="utf-8")

    rc = main(
        [
            "compare",
            str(cur_path),
            str(base_path),
            "--fail-on-new-error",
            "--fail-on-domain-increase",
            "target_risk=2",
            "--format",
            "json",
            "--output",
            str(out_path),
        ]
    )
    assert rc == 2
    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert payload["summary"]["new_error"] == 1


def test_cli_suppress_add_list_validate(tmp_path):
    sup = tmp_path / "sup.json"
    rc_add = main(
        [
            "suppress",
            "add",
            "--file",
            str(sup),
            "--check-id",
            "leakage.high_correlation",
            "--reason",
            "known waiver",
            "--expires",
            "2099-01-01",
        ]
    )
    assert rc_add == 0

    rc_list = main(
        [
            "suppress",
            "list",
            "--file",
            str(sup),
            "--format",
            "json",
        ]
    )
    assert rc_list == 0

    rc_validate = main(
        [
            "suppress",
            "validate",
            "--file",
            str(sup),
            "--fail-on-expired",
            "--format",
            "json",
        ]
    )
    assert rc_validate == 0


def test_cli_plugins_doctor_error_branch(monkeypatch):
    monkeypatch.setattr(
        "preflight.cli.discover_entrypoint_plugins",
        lambda: [
            {"name": "x", "source": "pkg:x", "status": "error", "error": "boom"},
            {"name": "y", "source": "pkg:y", "status": "loaded", "kind": "native"},
        ],
    )
    rc = main(["plugins", "doctor", "--format", "json"])
    assert rc == 2
