from pathlib import Path

import numpy as np
import pandas as pd

from data.ingestion import load_analysis2_input
from data.validation import validate_analysis2_input
from analysis.analysis2 import run_analysis2_pipeline
from analysis.outputs import (
    build_detection_table,
    build_evidence_card,
)
from common.config import (
    MIN_HISTORY,
    ROBUST_Z_SCALE,
    ROBUST_Z_THRESHOLD,
)


BASE_DIR = Path(__file__).resolve().parents[1]

INPUT_PATH = (
    BASE_DIR / "data/reference/gangnam_analysis2_feature_table_2022_2025.csv"
)

CONTEXT_PATH = (
    BASE_DIR
    / "data/reference"
    / "gangnam_analysis1_final_region_typology_2025H2.csv"
)

DETECTION_REFERENCE_PATH = (
    BASE_DIR
    / "data/reference"
    / "gangnam_analysis2_detection_2022_2025.csv"
)

EVIDENCE_REFERENCE_PATH = (
    BASE_DIR
    / "data/reference"
    / "gangnam_analysis2_evidence_card_2022_2025.csv"
)


def compare_with_reference(actual, reference):
    """
    실제 생성 결과와 Reference를 비교한다.

    - shape 및 컬럼 순서는 정확히 일치해야 한다.
    - 숫자형 컬럼은 부동소수점 오차를 허용한다.
    - 나머지 컬럼은 정확히 일치해야 한다.
    """
    assert actual.shape == reference.shape
    assert actual.columns.tolist() == reference.columns.tolist()

    numeric_columns = reference.select_dtypes(
        include=np.number
    ).columns
    for column in numeric_columns:
        np.testing.assert_allclose(actual[column],reference[column],atol=2e-12,rtol=1e-13,equal_nan=True,err_msg=column)

    other_columns = [
        col
        for col in reference.columns
        if col not in numeric_columns
    ]

    for col in other_columns:
    # 날짜 컬럼은 Timestamp / CSV 문자열 표현 차이를 제거한 뒤 비교
        if col in {"date", "previous_signal_date"}:
            actual_values = (
                pd.to_datetime(actual[col], errors="coerce")
                .dt.strftime("%Y-%m-%d")
                .fillna("<NA>")
            )

            reference_values = (
                pd.to_datetime(reference[col], errors="coerce")
                .dt.strftime("%Y-%m-%d")
                .fillna("<NA>")
            )

        else:
            actual_values = (
                actual[col]
                .fillna("<NA>")
                .astype(str)
            )

            reference_values = (
                reference[col]
                .fillna("<NA>")
                .astype(str)
            )

        assert actual_values.equals(
            reference_values
        ), f"Non-numeric mismatch: {col}"


def test_analysis2_reproduction():
    # 1. Feature Table
    df = load_analysis2_input(INPUT_PATH)

    validation = validate_analysis2_input(df)

    assert validation["status"] == "PASS"
    assert df.shape == (1056, 23)

    # 2. Analysis1 Context
    context_df = pd.read_csv(CONTEXT_PATH)

    # 3. Analysis2 전체 파이프라인
    analysis_result = run_analysis2_pipeline(
        df,
        context_df,
        MIN_HISTORY,
        ROBUST_Z_SCALE,
        ROBUST_Z_THRESHOLD,
    )

    assert analysis_result.shape == (1056, 64)

    # 4. Detection Table
    detection = build_detection_table(
        analysis_result
    )

    detection_reference = pd.read_csv(
        DETECTION_REFERENCE_PATH
    )

    compare_with_reference(
        detection,
        detection_reference,
    )

    assert int(detection["any_signal"].sum()) == 35
    assert int(detection["communication_signal"].sum()) == 10
    assert int(detection["mobility_signal"].sum()) == 26
    assert int(detection["combined_signal"].sum()) == 1

    # 5. Evidence Card
    evidence = build_evidence_card(
        analysis_result
    )

    evidence_reference = pd.read_csv(
        EVIDENCE_REFERENCE_PATH
    )

    compare_with_reference(
        evidence,
        evidence_reference,
    )

    assert evidence.shape == (35, 29)
    assert (evidence["signal_status"] == "New").sum() == 30
    assert (evidence["signal_status"] == "Continuing").sum() == 5
    assert evidence["consecutive_signal"].sum() == 5
