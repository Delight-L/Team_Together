from pathlib import Path

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


BASE_DIR = Path(__file__).resolve().parent

INPUT_PATH = (
    BASE_DIR / "gangnam_analysis2_feature_table_2022_2025.csv"
)

CONTEXT_PATH = (
    BASE_DIR
    / "reference"
    / "gangnam_analysis1_final_region_typology_2025H2.csv"
)


OUTPUT_DIR = BASE_DIR / "outputs"

DETECTION_OUTPUT_PATH = (
    OUTPUT_DIR / "gangnam_analysis2_detection_2022_2025.csv"
)

EVIDENCE_OUTPUT_PATH = (
    OUTPUT_DIR / "gangnam_analysis2_evidence_card_2022_2025.csv"
)


def main():
    # 1. Analysis2 Feature Table 로드
    df = load_analysis2_input(INPUT_PATH)

    # 2. 입력 데이터 검증
    validation = validate_analysis2_input(df)

    if validation["status"] != "PASS":
        raise ValueError(
            f"Analysis2 input validation failed: {validation}"
        )

    # 3. Analysis1 Context 로드
    context_df = pd.read_csv(CONTEXT_PATH)

    # 4. Analysis2 전체 분석 실행
    analysis_result = run_analysis2_pipeline(
        df,
        context_df,
        MIN_HISTORY,
        ROBUST_Z_SCALE,
        ROBUST_Z_THRESHOLD,
    )

    # 5. 최종 산출물 생성
    detection_table = build_detection_table(analysis_result)
    evidence_card = build_evidence_card(analysis_result)

        # 6. 최종 산출물 저장
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    detection_table.to_csv(
        DETECTION_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    evidence_card.to_csv(
        EVIDENCE_OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    # 7. 실행 결과 확인
    print("===== ANALYSIS 2 =====")
    print("Input validation:", validation["status"])
    print("Feature Table:", df.shape)
    print("Analysis Result:", analysis_result.shape)
    print("Detection Table:", detection_table.shape)
    print("Evidence Card:", evidence_card.shape)
    print("Signals:", int(detection_table["any_signal"].sum()))
    print("Detection saved:", DETECTION_OUTPUT_PATH)
    print("Evidence saved:", EVIDENCE_OUTPUT_PATH)


if __name__ == "__main__":
    main()