# data/validation.py

"""
DB1 Analysis2 input validation

Analysis2 Feature Table이 분석 가능한 구조인지 검증한다.
"""

import numpy as np
import pandas as pd

from common.config import (
    EXPECTED_AREAS,
    EXPECTED_MONTHS,
    EXPECTED_ROWS,
    DATE_COLUMN,
    AREA_CODE_COLUMN,
    AREA_NAME_COLUMN,
    DETECTION_CORE_COLUMNS,
    MOBILITY_EVIDENCE_COLUMNS,
    QC_COLUMNS,
    INTEREST_VALIDATION_COLUMNS,
    STRUCTURAL_ISSUE_COLUMN,
    WEATHER_COLUMNS,
    CALENDAR_COLUMNS,
)


REQUIRED_COLUMNS = [
    DATE_COLUMN,
    AREA_CODE_COLUMN,
    AREA_NAME_COLUMN,
    *DETECTION_CORE_COLUMNS,
    *MOBILITY_EVIDENCE_COLUMNS,
    *QC_COLUMNS,
    *INTEREST_VALIDATION_COLUMNS,
    *WEATHER_COLUMNS,
    *CALENDAR_COLUMNS,
    STRUCTURAL_ISSUE_COLUMN,
]


NUMERIC_COLUMNS = [
    *DETECTION_CORE_COLUMNS,
    *MOBILITY_EVIDENCE_COLUMNS,
    *QC_COLUMNS,
    *INTEREST_VALIDATION_COLUMNS,
    *WEATHER_COLUMNS,
    *CALENDAR_COLUMNS,
]


def validate_analysis2_input(df: pd.DataFrame) -> dict:
    """
    Analysis2 Feature Table의 구조와 데이터 품질을 검증한다.

    Returns
    -------
    dict
        검증 결과
    """

    errors = []
    warnings = []

    # --------------------------------------------------
    # 1. 필수 컬럼
    # --------------------------------------------------

    missing_columns = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing_columns:
        errors.append(
            f"필수 컬럼 누락: {missing_columns}"
        )

        return {
            "status": "FAIL",
            "errors": errors,
            "warnings": warnings,
        }

    # 원본 DataFrame을 변경하지 않기 위해 복사
    data = df.copy()

    # --------------------------------------------------
    # 2. date 변환
    # --------------------------------------------------

    data[DATE_COLUMN] = pd.to_datetime(
        data[DATE_COLUMN],
        errors="coerce"
    )

    invalid_dates = int(
        data[DATE_COLUMN].isna().sum()
    )

    if invalid_dates > 0:
        errors.append(
            f"날짜 변환 실패: {invalid_dates}건"
        )

    # --------------------------------------------------
    # 3. 기본 크기
    # --------------------------------------------------

    n_rows = len(data)
    n_areas = data[AREA_CODE_COLUMN].nunique()
    n_months = data[DATE_COLUMN].nunique()

    if n_rows != EXPECTED_ROWS:
        errors.append(
            f"행 수 불일치: expected={EXPECTED_ROWS}, actual={n_rows}"
        )

    if n_areas != EXPECTED_AREAS:
        errors.append(
            f"행정동 수 불일치: expected={EXPECTED_AREAS}, actual={n_areas}"
        )

    if n_months != EXPECTED_MONTHS:
        errors.append(
            f"월 수 불일치: expected={EXPECTED_MONTHS}, actual={n_months}"
        )

    # --------------------------------------------------
    # 4. Key 중복
    # --------------------------------------------------

    duplicate_keys = int(
        data.duplicated(
            subset=[DATE_COLUMN, AREA_CODE_COLUMN]
        ).sum()
    )

    if duplicate_keys > 0:
        errors.append(
            f"date × 행정동코드 중복: {duplicate_keys}건"
        )

    # --------------------------------------------------
    # 5. 결측
    # --------------------------------------------------

    missing_total = int(
        data[REQUIRED_COLUMNS].isna().sum().sum()
    )

    if missing_total > 0:
        errors.append(
            f"필수 데이터 결측: {missing_total}건"
        )

    # --------------------------------------------------
    # 6. 숫자형 컬럼
    # --------------------------------------------------

    non_numeric_columns = [
        col for col in NUMERIC_COLUMNS
        if not pd.api.types.is_numeric_dtype(data[col])
    ]

    if non_numeric_columns:
        errors.append(
            f"숫자형이 아닌 분석 컬럼: {non_numeric_columns}"
        )

    # --------------------------------------------------
    # 7. 무한값
    # --------------------------------------------------

    if not non_numeric_columns:

        infinite_count = int(
            np.isinf(
                data[NUMERIC_COLUMNS].to_numpy(dtype=float)
            ).sum()
        )

    else:
        infinite_count = 0

    if infinite_count > 0:
        errors.append(
            f"무한값 발견: {infinite_count}건"
        )

    # --------------------------------------------------
    # 8. 월별 22개 행정동 확인
    # --------------------------------------------------

    rows_per_month = (
        data.groupby(DATE_COLUMN)[AREA_CODE_COLUMN]
        .nunique()
    )

    invalid_months = rows_per_month[
        rows_per_month != EXPECTED_AREAS
    ]

    if len(invalid_months) > 0:
        errors.append(
            f"22개 행정동이 아닌 월: {len(invalid_months)}개"
        )

    # --------------------------------------------------
    # 9. 행정동별 48개월 확인
    # --------------------------------------------------

    months_per_area = (
        data.groupby(AREA_CODE_COLUMN)[DATE_COLUMN]
        .nunique()
    )

    invalid_areas = months_per_area[
        months_per_area != EXPECTED_MONTHS
    ]

    if len(invalid_areas) > 0:
        errors.append(
            f"48개월이 아닌 행정동: {len(invalid_areas)}개"
        )

    # --------------------------------------------------
    # 최종 상태
    # --------------------------------------------------

    status = "PASS" if not errors else "FAIL"

    return {
        "status": status,
        "n_rows": n_rows,
        "n_areas": n_areas,
        "n_months": n_months,
        "duplicate_keys": duplicate_keys,
        "missing_total": missing_total,
        "infinite_count": infinite_count,
        "errors": errors,
        "warnings": warnings,
    }