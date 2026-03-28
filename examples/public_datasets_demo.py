from __future__ import annotations

from sklearn.datasets import load_breast_cancer, load_iris, load_wine
from sklearn.model_selection import train_test_split

import pandas as pd

import preflight


def _as_frame(dataset_loader) -> tuple[pd.DataFrame, str]:
    ds = dataset_loader(as_frame=True)
    df = ds.frame.copy()
    target_name = ds.target.name if ds.target is not None and ds.target.name else "target"
    if target_name not in df.columns:
        df[target_name] = ds.target
    return df, target_name


def run_dataset(name: str, loader) -> None:
    df, target = _as_frame(loader)
    print(f"\n=== {name} ===")
    print(f"shape={df.shape}, target={target!r}")

    report_explore = preflight.run(df, target=target, profile="exploratory")
    report_balanced = preflight.run(df, target=target, profile="ci-balanced")
    print(
        "run exploratory:",
        report_explore.gate.status,
        "score=",
        round(report_explore.score, 1),
    )
    print(
        "run ci-balanced:",
        report_balanced.gate.status,
        "score=",
        round(report_balanced.score, 1),
    )

    train_df, test_df = train_test_split(df, test_size=0.25, random_state=42, stratify=df[target])
    split_report = preflight.run_split(train_df, test_df, profile="ci-balanced")
    print(
        "run_split ci-balanced:", split_report.gate.status, "score=", round(split_report.score, 1)
    )
    print("findings:", len(report_balanced.findings), "split findings:", len(split_report.findings))


def main() -> None:
    run_dataset("Breast Cancer (sklearn/UCI)", load_breast_cancer)
    run_dataset("Wine (sklearn/UCI)", load_wine)
    run_dataset("Iris (sklearn/UCI)", load_iris)


if __name__ == "__main__":
    main()
