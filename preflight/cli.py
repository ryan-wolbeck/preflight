"""
Command line interface for preflight.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal, Optional, cast

import pandas as pd

import preflight
from preflight.api import run as run_api
from preflight.api import run_split as run_split_api
from preflight.compare import compare_reports
from preflight.config import PreflightConfig, RuntimeConfig
from preflight.config_loader import load_config_file
from preflight.engine.registry import discover_entrypoint_plugins
from preflight.model.policy import Policy
from preflight.model.report import RunReport
from preflight.policy import load_policy_file, load_suppressions
from preflight.policy.default_profiles import parse_fail_on, with_fail_on
from preflight.renderers import render_html, render_json, render_markdown, render_text


def _load_table(path: str) -> pd.DataFrame:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(p)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(p)
    raise ValueError(f"Unsupported file format for {path!r}. Use .csv or .parquet")


def _emit(text: str, output: str | None) -> None:
    if output is None:
        print(text)
        return
    Path(output).write_text(text, encoding="utf-8")


def _build_config(
    mode: Optional[Literal["accurate", "fast"]],
    sample_rows: int | None,
    base: PreflightConfig | None = None,
) -> PreflightConfig:
    cfg = base or PreflightConfig()
    runtime = cfg.runtime
    return PreflightConfig(
        runtime=RuntimeConfig(
            mode=mode or runtime.mode,
            sample_rows=sample_rows if sample_rows is not None else runtime.sample_rows,
            random_state=runtime.random_state,
            large_dataset_rows=runtime.large_dataset_rows,
            fast_mode_sample_rows=runtime.fast_mode_sample_rows,
        ),
        completeness=cfg.completeness,
        balance=cfg.balance,
        leakage=cfg.leakage,
        duplicates=cfg.duplicates,
        distributions=cfg.distributions,
        correlations=cfg.correlations,
        types=cfg.types,
        split=cfg.split,
        scoring=cfg.scoring,
        enabled_checks=cfg.enabled_checks,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="preflight",
        description="Dataset readiness checker for machine learning datasets.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run",
        help="Run policy-based readiness checks (recommended).",
    )
    run_parser.add_argument("path", help="Input dataset path (.csv or .parquet)")
    run_parser.add_argument("--target", default=None, help="Target column name")
    run_parser.add_argument(
        "--profile",
        default=None,
        choices=["exploratory", "ci-balanced", "ci-strict"],
        help="Policy profile",
    )
    run_parser.add_argument(
        "--policy-file",
        default=None,
        help="Path to custom policy JSON/YAML. Overrides --profile when provided.",
    )
    run_parser.add_argument(
        "--fail-on",
        default=None,
        help="Comma-separated severities that fail the gate "
        "(info,warn,error,critical). Overrides profile defaults.",
    )
    run_parser.add_argument(
        "--suppressions",
        default=None,
        help="Path to suppressions JSON file.",
    )
    run_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "markdown", "html"],
        help="Output format",
    )
    run_parser.add_argument("--output", default=None, help="Write output to a file")
    run_parser.add_argument(
        "--output-html",
        default=None,
        help="Optional path to always write HTML report output.",
    )
    run_parser.add_argument(
        "--mode",
        default=None,
        choices=["accurate", "fast"],
        help="Runtime mode; fast enables sampling for large datasets",
    )
    run_parser.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Explicit sample size for analysis (overrides default runtime sampling)",
    )
    run_parser.add_argument(
        "--config-file",
        default=None,
        help="Path to JSON/YAML runtime/check configuration file.",
    )

    run_split_parser = subparsers.add_parser(
        "run-split",
        help="Run policy-based split integrity checks on train/test datasets.",
    )
    run_split_parser.add_argument("train_path", help="Train dataset path (.csv or .parquet)")
    run_split_parser.add_argument("test_path", help="Test dataset path (.csv or .parquet)")
    run_split_parser.add_argument(
        "--profile",
        default=None,
        choices=["exploratory", "ci-balanced", "ci-strict"],
        help="Policy profile",
    )
    run_split_parser.add_argument(
        "--policy-file",
        default=None,
        help="Path to custom policy JSON/YAML. Overrides --profile when provided.",
    )
    run_split_parser.add_argument(
        "--fail-on",
        default=None,
        help="Comma-separated severities that fail the gate "
        "(info,warn,error,critical). Overrides profile defaults.",
    )
    run_split_parser.add_argument(
        "--suppressions",
        default=None,
        help="Path to suppressions JSON file.",
    )
    run_split_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "markdown", "html"],
        help="Output format",
    )
    run_split_parser.add_argument("--output", default=None, help="Write output to a file")
    run_split_parser.add_argument(
        "--output-html",
        default=None,
        help="Optional path to always write HTML report output.",
    )
    run_split_parser.add_argument(
        "--mode",
        default=None,
        choices=["accurate", "fast"],
        help="Runtime mode; fast enables sampling for large datasets",
    )
    run_split_parser.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Explicit sample size for analysis (overrides default runtime sampling)",
    )
    run_split_parser.add_argument(
        "--config-file",
        default=None,
        help="Path to JSON/YAML runtime/check configuration file.",
    )

    check_parser = subparsers.add_parser("check", help="Run full readiness checks on one dataset.")
    check_parser.add_argument("path", help="Input dataset path (.csv or .parquet)")
    check_parser.add_argument("--target", default=None, help="Target column name")
    check_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "markdown", "html"],
        help="Output format",
    )
    check_parser.add_argument("--output", default=None, help="Write output to a file")
    check_parser.add_argument(
        "--mode",
        default=None,
        choices=["accurate", "fast"],
        help="Runtime mode; fast enables sampling for large datasets",
    )
    check_parser.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Explicit sample size for analysis (overrides default runtime sampling)",
    )
    check_parser.add_argument(
        "--config-file",
        default=None,
        help="Path to JSON/YAML runtime/check configuration file.",
    )

    split_parser = subparsers.add_parser(
        "check-split", help="Run train/test drift checks between two datasets."
    )
    split_parser.add_argument("train_path", help="Train dataset path (.csv or .parquet)")
    split_parser.add_argument("test_path", help="Test dataset path (.csv or .parquet)")
    split_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json", "markdown", "html"],
        help="Output format",
    )
    split_parser.add_argument("--output", default=None, help="Write output to a file")
    split_parser.add_argument(
        "--mode",
        default=None,
        choices=["accurate", "fast"],
        help="Runtime mode; fast enables sampling for large datasets",
    )
    split_parser.add_argument(
        "--sample-rows",
        type=int,
        default=None,
        help="Explicit sample size for analysis (overrides default runtime sampling)",
    )
    split_parser.add_argument(
        "--config-file",
        default=None,
        help="Path to JSON/YAML runtime/check configuration file.",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Compare current JSON report vs baseline JSON report.",
    )
    compare_parser.add_argument("current", help="Current report JSON path")
    compare_parser.add_argument("baseline", help="Baseline report JSON path")
    compare_parser.add_argument(
        "--max-score-drop",
        type=float,
        default=5.0,
        help="Fail if current score drops by more than this amount.",
    )
    compare_parser.add_argument(
        "--allow-new-critical",
        action="store_true",
        help="Do not fail when new critical findings appear.",
    )
    compare_parser.add_argument(
        "--fail-on-new-error",
        action="store_true",
        help="Fail when new error-level findings appear.",
    )
    compare_parser.add_argument(
        "--fail-on-domain-increase",
        action="append",
        default=[],
        metavar="DOMAIN=COUNT",
        help="Fail if a domain's finding count increases by more than COUNT (repeatable).",
    )
    compare_parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        help="Output format",
    )
    compare_parser.add_argument("--output", default=None, help="Write output to a file")

    suppress_parser = subparsers.add_parser(
        "suppress",
        help="Manage suppression JSON files.",
    )
    suppress_sub = suppress_parser.add_subparsers(dest="suppress_command", required=True)
    suppress_add = suppress_sub.add_parser(
        "add",
        help="Add a suppression item to a JSON suppressions file.",
    )
    suppress_add.add_argument("--file", required=True, help="Suppressions JSON file path")
    suppress_add.add_argument("--check-id", required=True, help="Check ID to suppress")
    suppress_add.add_argument("--column", default=None, help="Optional column scope")
    suppress_add.add_argument("--expires", default=None, help="Optional expiry date (YYYY-MM-DD)")
    suppress_add.add_argument("--reason", required=True, help="Suppression rationale")
    suppress_list = suppress_sub.add_parser(
        "list",
        help="List suppressions from a JSON file.",
    )
    suppress_list.add_argument("--file", required=True, help="Suppressions JSON file path")
    suppress_list.add_argument("--format", default="text", choices=["text", "json"])
    suppress_validate = suppress_sub.add_parser(
        "validate",
        help="Validate suppression JSON and report expired entries.",
    )
    suppress_validate.add_argument("--file", required=True, help="Suppressions JSON file path")
    suppress_validate.add_argument("--fail-on-expired", action="store_true")
    suppress_validate.add_argument("--format", default="text", choices=["text", "json"])

    plugins_parser = subparsers.add_parser(
        "plugins",
        help="Inspect preflight plugin discovery health.",
    )
    plugins_sub = plugins_parser.add_subparsers(dest="plugins_command", required=True)
    plugins_doctor = plugins_sub.add_parser("doctor", help="Run plugin discovery diagnostics.")
    plugins_doctor.add_argument("--format", default="text", choices=["text", "json"])
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    config: PreflightConfig | None = None
    if hasattr(args, "mode") and hasattr(args, "sample_rows"):
        base_cfg = (
            load_config_file(args.config_file) if getattr(args, "config_file", None) else None
        )
        runtime_mode = args.mode
        if runtime_mode not in (None, "accurate", "fast"):
            raise ValueError(f"Unsupported runtime mode: {runtime_mode!r}")
        typed_mode = cast(Optional[Literal["accurate", "fast"]], runtime_mode)
        config = _build_config(mode=typed_mode, sample_rows=args.sample_rows, base=base_cfg)

    if args.command == "compare":
        current = json.loads(Path(args.current).read_text(encoding="utf-8"))
        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        result = compare_reports(
            current,
            baseline,
            max_score_drop=args.max_score_drop,
            fail_on_new_critical=not args.allow_new_critical,
            fail_on_new_error=bool(args.fail_on_new_error),
            domain_increase_thresholds=_parse_domain_thresholds(args.fail_on_domain_increase),
        )
        if args.format == "json":
            payload = json.dumps(result.to_dict(), indent=2)
        else:
            lines = [f"Status: {result.status}"]
            if result.reasons:
                lines.append("Reasons:")
                lines.extend(f"- {reason}" for reason in result.reasons)
            lines.append("Summary:")
            for key, value in result.summary.items():
                lines.append(f"- {key}: {value}")
            payload = "\n".join(lines)
        _emit(payload, args.output)
        return _gate_exit_code(result.status)

    if args.command == "suppress":
        if args.suppress_command == "add":
            return _add_suppression(
                file_path=args.file,
                check_id=args.check_id,
                column=args.column,
                expires=args.expires,
                reason=args.reason,
            )
        if args.suppress_command == "list":
            return _list_suppressions(args.file, output_format=args.format)
        if args.suppress_command == "validate":
            return _validate_suppressions(
                args.file,
                fail_on_expired=bool(args.fail_on_expired),
                output_format=args.format,
            )
        parser.error(f"Unsupported suppress command: {args.suppress_command}")
        return 2

    if args.command == "plugins":
        if args.plugins_command == "doctor":
            return _plugins_doctor(output_format=args.format)
        parser.error(f"Unsupported plugins command: {args.plugins_command}")
        return 2

    if args.command == "run":
        _validate_policy_args(args, parser)
        df = _load_table(args.path)
        suppressions = load_suppressions(args.suppressions)
        policy_obj = load_policy_file(args.policy_file) if args.policy_file else None
        profile_name = args.profile or "exploratory"
        policy = policy_obj if policy_obj is not None else profile_name
        run_report = run_api(
            df,
            target=args.target,
            profile=policy,
            config=config,
            suppressions=suppressions,
        )
        if args.fail_on:
            run_report = _apply_fail_on_override(
                run_report,
                profile_name=run_report.meta.profile,
                fail_on=args.fail_on,
                suppressions=suppressions,
                base_policy=policy_obj,
            )

        if args.format == "json":
            payload = render_json(run_report)
        elif args.format == "markdown":
            payload = render_markdown(run_report)
        elif args.format == "html":
            payload = render_html(run_report)
        else:
            payload = render_text(run_report)
        _emit(payload, args.output)
        if args.output_html:
            Path(args.output_html).write_text(render_html(run_report), encoding="utf-8")
        return _gate_exit_code(run_report.gate.status)

    if args.command == "run-split":
        _validate_policy_args(args, parser)
        train = _load_table(args.train_path)
        test = _load_table(args.test_path)
        suppressions = load_suppressions(args.suppressions)
        policy_obj = load_policy_file(args.policy_file) if args.policy_file else None
        profile_name = args.profile or "exploratory"
        policy = policy_obj if policy_obj is not None else profile_name
        run_report = run_split_api(
            train,
            test,
            profile=policy,
            config=config,
            suppressions=suppressions,
        )
        if args.fail_on:
            run_report = _apply_fail_on_override(
                run_report,
                profile_name=run_report.meta.profile,
                fail_on=args.fail_on,
                suppressions=suppressions,
                base_policy=policy_obj,
            )

        if args.format == "json":
            payload = render_json(run_report)
        elif args.format == "markdown":
            payload = render_markdown(run_report)
        elif args.format == "html":
            payload = render_html(run_report)
        else:
            payload = render_text(run_report)
        _emit(payload, args.output)
        if args.output_html:
            Path(args.output_html).write_text(render_html(run_report), encoding="utf-8")
        return _gate_exit_code(run_report.gate.status)

    if args.command == "check":
        df = _load_table(args.path)
        report = preflight.check(df, target=args.target, config=config)
    elif args.command == "check-split":
        train = _load_table(args.train_path)
        test = _load_table(args.test_path)
        report = preflight.check_split(train, test, config=config)
    else:
        parser.error(f"Unsupported command: {args.command}")
        return 2

    if args.format == "json":
        payload = json.dumps(report.to_dict(), indent=2, default=str)
    elif args.format == "markdown":
        payload = report.to_markdown()
    elif args.format == "html":
        payload = report.to_html()
    else:
        payload = str(report)

    _emit(payload, args.output)
    return 0


def _gate_exit_code(status: str) -> int:
    if status == "FAIL":
        return 2
    return 0


def _apply_fail_on_override(
    run_report: RunReport,
    profile_name: str,
    fail_on: str,
    suppressions: Optional[list[Any]] = None,
    base_policy: Policy | None = None,
) -> RunReport:
    from preflight.policy.default_profiles import choose_profile
    from preflight.policy.evaluator import evaluate

    profile = base_policy if base_policy is not None else choose_profile(profile_name)
    parsed = parse_fail_on(fail_on, profile.fail_on)
    profile = with_fail_on(profile, fail_on=parsed)
    evaluation = evaluate(run_report.findings, profile, suppressions=suppressions)
    return type(run_report)(
        meta=run_report.meta,
        findings=evaluation.findings,
        gate=evaluation.gate,
        score=evaluation.score,
        score_label=run_report.score_label,
    )


def _add_suppression(
    *,
    file_path: str,
    check_id: str,
    column: str | None,
    expires: str | None,
    reason: str,
) -> int:
    path = Path(file_path)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Suppressions file must contain a JSON list.")
    else:
        data = []
    entry: dict[str, str] = {"check_id": check_id, "reason": reason}
    if column:
        entry["column"] = column
    if expires:
        entry["expires"] = expires
    data.append(entry)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Added suppression to {path}: {check_id}")
    return 0


def _list_suppressions(file_path: str, output_format: str = "text") -> int:
    items = load_suppressions(file_path)
    if output_format == "json":
        payload = []
        for item in items:
            payload.append(
                {
                    "check_id": item.check_id,
                    "column": item.column,
                    "expires": item.expires.isoformat() if item.expires else None,
                    "reason": item.reason,
                    "expired": item.is_expired(),
                }
            )
        print(json.dumps(payload, indent=2))
        return 0

    if not items:
        print("No suppressions found.")
        return 0
    print(f"Suppressions ({len(items)}):")
    for item in items:
        expires = item.expires.isoformat() if item.expires else "-"
        expired = " (EXPIRED)" if item.is_expired() else ""
        column = item.column or "*"
        reason = item.reason or "-"
        print(f"- {item.check_id} column={column} expires={expires}{expired} reason={reason}")
    return 0


def _validate_suppressions(
    file_path: str, *, fail_on_expired: bool = False, output_format: str = "text"
) -> int:
    items = load_suppressions(file_path)
    expired = [item for item in items if item.is_expired()]
    summary = {
        "total": len(items),
        "expired": len(expired),
        "status": "FAIL" if (fail_on_expired and expired) else "PASS",
    }
    if output_format == "json":
        print(json.dumps(summary, indent=2))
    else:
        print(f"Suppressions validation: {summary['status']}")
        print(f"- total: {summary['total']}")
        print(f"- expired: {summary['expired']}")
    if fail_on_expired and expired:
        return 2
    return 0


def _parse_domain_thresholds(items: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Invalid --fail-on-domain-increase value: {item!r}")
        domain, threshold = item.split("=", 1)
        domain = domain.strip()
        threshold = threshold.strip()
        if not domain:
            raise ValueError(f"Invalid domain in --fail-on-domain-increase: {item!r}")
        out[domain] = int(threshold)
    return out


def _plugins_doctor(output_format: str = "text") -> int:
    diagnostics = discover_entrypoint_plugins()
    loaded = [item for item in diagnostics if item.get("status") == "loaded"]
    errors = [item for item in diagnostics if item.get("status") != "loaded"]
    if output_format == "json":
        print(
            json.dumps(
                {
                    "status": "FAIL" if errors else "PASS",
                    "loaded": len(loaded),
                    "errors": len(errors),
                    "plugins": [
                        {
                            "name": item.get("name"),
                            "source": item.get("source"),
                            "status": item.get("status"),
                            "kind": item.get("kind"),
                            "error": item.get("error"),
                        }
                        for item in diagnostics
                    ],
                },
                indent=2,
            )
        )
        return 2 if errors else 0

    print(f"Plugin doctor: {'FAIL' if errors else 'PASS'}")
    print(f"- loaded: {len(loaded)}")
    print(f"- errors: {len(errors)}")
    for item in diagnostics:
        status = item.get("status")
        name = item.get("name")
        source = item.get("source")
        if status == "loaded":
            print(f"  - [loaded] {name} ({source})")
        else:
            print(f"  - [error] {name} ({source}): {item.get('error')}")
    return 2 if errors else 0


def _validate_policy_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    profile = getattr(args, "profile", None)
    policy_file = getattr(args, "policy_file", None)
    fail_on = getattr(args, "fail_on", None)

    if profile and policy_file:
        parser.error("Use either --profile or --policy-file, not both.")
    if policy_file and fail_on:
        parser.error("Use --fail-on with --profile only; set fail_on inside the policy file.")
    if fail_on is not None and not str(fail_on).strip():
        parser.error("--fail-on must not be empty.")


if __name__ == "__main__":
    sys.exit(main())
