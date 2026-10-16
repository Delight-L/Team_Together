"""Analysis2 전체 기간 일괄 실행: feature table 하나로 탐지 결과와 근거 카드를 만듭니다.

전처리 자동 갱신(pipelines/preprocessing/regional_features)이 새 월을 붙인 뒤 이 파일을 실행합니다.
월별 순차 실행은 run_analysis2_sequential.py를 씁니다.

    python run_analysis2.py --input <feature table CSV> --output-dir <결과 폴더>
"""
import argparse
from pathlib import Path

import pandas as pd

from analysis.analysis2 import run_analysis2_pipeline
from analysis.outputs import build_detection_table, build_evidence_card
from common.config import MIN_HISTORY, ROBUST_Z_SCALE, ROBUST_Z_THRESHOLD
from data.ingestion import load_analysis2_input
from data.validation import validate_analysis2_input

BASE_DIR = Path(__file__).resolve().parent
REFERENCE_DIR = BASE_DIR / "data" / "reference"
DETECTION_NAME = "gangnam_analysis2_detection_2022_2025.csv"
EVIDENCE_NAME = "gangnam_analysis2_evidence_card_2022_2025.csv"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, default=REFERENCE_DIR / "gangnam_analysis2_feature_table_2022_2025.csv")
    parser.add_argument("--context", type=Path, default=REFERENCE_DIR / "gangnam_analysis1_final_region_typology_2025H2.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    df = load_analysis2_input(args.input)
    validation = validate_analysis2_input(df)
    if validation["status"] != "PASS":
        raise ValueError(f"Analysis2 input validation failed: {validation}")
    analysis_result = run_analysis2_pipeline(df, pd.read_csv(args.context), MIN_HISTORY, ROBUST_Z_SCALE, ROBUST_Z_THRESHOLD)
    detection_table = build_detection_table(analysis_result)
    evidence_card = build_evidence_card(analysis_result)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    detection_table.to_csv(args.output_dir / DETECTION_NAME, index=False, encoding="utf-8-sig")
    evidence_card.to_csv(args.output_dir / EVIDENCE_NAME, index=False, encoding="utf-8-sig")
    print("===== ANALYSIS 2 =====")
    print("Input validation:", validation["status"])
    print("Feature Table:", df.shape, "/ Detection Table:", detection_table.shape, "/ Evidence Card:", evidence_card.shape)
    print("Signals:", int(detection_table["any_signal"].sum()))
    print("Saved:", args.output_dir)


if __name__ == "__main__":
    main()
