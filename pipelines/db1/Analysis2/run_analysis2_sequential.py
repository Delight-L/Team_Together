from __future__ import annotations

from pathlib import Path

import pandas as pd

from common.config import DATE_COLUMN, AREA_CODE_COLUMN


BASE_DIR = Path(__file__).resolve().parent


def find_month_file(directory: Path, year: int, month: int, keyword: str) -> Path:
    pattern = f"{year}.{month}월*{keyword}*.xlsx"
    matches = sorted(directory.glob(pattern))

    if len(matches) == 0:
        raise FileNotFoundError(f"No raw file found: {directory / pattern}")

    if len(matches) > 1:
        raise ValueError(f"Multiple raw files found for {year}-{month:02d}: {matches}")

    return matches[0]


def validate_current_month(
    history: pd.DataFrame,
    current: pd.DataFrame,
    period: pd.Timestamp,
) -> None:
    from data.monthly_validation import validate_feature_rows

    validate_feature_rows(current, history[AREA_CODE_COLUMN].unique())

    if len(current) != 22:
        raise ValueError(f"Current month must contain 22 dongs, got {len(current)}.")

    if current.shape[1] != 23:
        raise ValueError(f"Current month must contain 23 columns, got {current.shape[1]}.")

    current_dates = (
        pd.to_datetime(
            current[DATE_COLUMN],
            format="mixed",
        )
        .dt.normalize()
        .drop_duplicates()
    )

    if len(current_dates) != 1 or current_dates.iloc[0] != period:
        raise ValueError(f"Current feature month mismatch: expected {period:%Y-%m}")

    history_dates = history[DATE_COLUMN]

    # Idempotency: 이미 처리한 월 재실행 방지
    if (history_dates == period).any():
        raise ValueError(f"{period:%Y-%m} already exists in History. Duplicate processing blocked.")

    if len(history) > 0:
        expected_period = (history_dates.max().to_period("M") + 1).to_timestamp()

        if period != expected_period:
            raise ValueError(
                f"Sequential processing violation: "
                f"History ends at {history_dates.max():%Y-%m}, "
                f"so next month must be {expected_period:%Y-%m}, "
                f"not {period:%Y-%m}."
            )

    duplicate_count = current.duplicated(subset=[DATE_COLUMN, AREA_CODE_COLUMN]).sum()

    if duplicate_count:
        raise ValueError(f"Current month contains {duplicate_count} duplicate keys.")


def main():
    import sys
    from update_worker import main as update_main

    if '--config' not in sys.argv:
        sys.argv += ['--config', str(BASE_DIR.parent / 'config/db1_config.json')]
    update_main()


if __name__ == '__main__':
    main()
