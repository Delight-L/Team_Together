from __future__ import annotations
from typing import Iterable
import numpy as np
import pandas as pd


class DataValidationError(ValueError):
    pass


def validate_table(
    df: pd.DataFrame,
    required_columns: Iterable[str],
    *,
    area_key: str | None = None,
    expected_areas: int | None = None,
    unique_area: bool = False,
    non_numeric_columns: Iterable[str] = (),
) -> dict:
    required = list(required_columns)
    missing = [c for c in required if c not in df.columns]
    errors: list[str] = []
    warnings: list[str] = []

    if missing:
        errors.append(f"Missing required columns: {missing}")
        return {
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
        }

    if df.empty:
        errors.append("Input table is empty.")

    if df[required].isna().any().any():
        cols = df[required].columns[
            df[required].isna().any()
        ].tolist()
        errors.append(
            f"Missing values found in required columns: {cols}"
        )

    # 식별자 등 숫자형 검사가 필요하지 않은 컬럼 제외
    non_numeric_set = set(non_numeric_columns)

    if area_key:
        non_numeric_set.add(area_key)

    # 실제 분석에 사용되는 숫자형 컬럼
    numeric_cols = [
        c for c in required
        if c not in non_numeric_set
    ]

    if numeric_cols:
        non_numeric = [
            c for c in numeric_cols
            if not pd.api.types.is_numeric_dtype(df[c])
        ]

        if non_numeric:
            errors.append(
                f"Non-numeric analysis columns: {non_numeric}"
            )
        else:
            arr = df[numeric_cols].to_numpy(dtype=float)

            if not np.isfinite(arr).all():
                errors.append(
                    "Infinite values found in analysis columns."
                )

    # 행정동 식별자 검증
    if area_key:
        if df[area_key].isna().any():
            errors.append(f"Missing area key: {area_key}")

        if unique_area and df[area_key].duplicated().any():
            errors.append(
                f"Duplicate area keys found in {area_key}."
            )

        if (
            expected_areas is not None
            and df[area_key].nunique() != expected_areas
        ):
            errors.append(
                f"Expected {expected_areas} areas, "
                f"found {df[area_key].nunique()}."
            )

    status = (
        "FAIL"
        if errors
        else ("WARNING" if warnings else "PASS")
    )

    return {
        "status": status,
        "errors": errors,
        "warnings": warnings,
    }


def require_pass(report: dict) -> None:
    if report.get("status") == "FAIL":
        raise DataValidationError("; ".join(report.get("errors", [])))
