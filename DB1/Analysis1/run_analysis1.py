from __future__ import annotations
import argparse
import json
from pathlib import Path

from analysis.analysis1 import run_analysis1
from data.ingestion import read_table


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run DB1 Analysis 1 regional-context pipeline."
    )
    parser.add_argument("--input", required=True, help="One-row-per-dong feature source CSV/XLSX/Parquet")
    parser.add_argument("--mapping", required=True, help="JSON defining raw columns for four PCA blocks")
    parser.add_argument("--profile", help="Optional one-row-per-dong raw profile table")
    parser.add_argument("--period", default=None)
    parser.add_argument("--version", default=None)
    parser.add_argument("--output", default="data/results/analysis1")
    args = parser.parse_args()

    base_df = read_table(args.input)
    profile_df = read_table(args.profile) if args.profile else None
    pca_columns = json.loads(Path(args.mapping).read_text(encoding="utf-8"))

    result = run_analysis1(
        base_df,
        pca_columns=pca_columns,
        raw_profile_df=profile_df,
        data_period=args.period,
        data_version=args.version,
        output_dir=args.output,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.status in {"PASS", "WARNING"} else 1)


if __name__ == "__main__":
    main()
