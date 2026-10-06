"""동·월별 2025년 결과보고 실적만 대시보드 검증 자료로 읽는다."""
import json
from pathlib import Path

import streamlit as st


VALIDATION_FILE = Path(__file__).resolve().parents[1] / "data" / "validation_actuals_2025.json"
ACTUAL_FIELDS = (
    "surveyTarget", "surveyCompleted", "newlyFound", "highRisk", "midRisk",
    "lowRisk", "contactAttempts", "counseling", "visits", "supportNeeded",
    "serviceLinked", "followUp",
)


@st.cache_data(show_spinner=False)
def load_validation_rows(path: str, modified_ns: int) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    records = data.get("records", [])
    seen = set()
    for row in records:
        key = (row["month"], row["dongCode"])
        if key in seen or not row["month"].startswith("2025-"):
            raise ValueError("검증 실적의 월·행정동 키가 중복되었거나 2025년이 아닙니다.")
        seen.add(key)
        if not all(row.get(field) is None or isinstance(row[field], int) and row[field] >= 0 for field in ACTUAL_FIELDS):
            raise ValueError(f"검증 실적은 음수가 아닌 정수 또는 빈값이어야 합니다: {key}")
        if not all(row.get(field) for field in ("documentNumber", "period", "unit", "dedupRule")):
            raise ValueError(f"검증 실적의 출처·기간·단위·중복 처리 기준이 없습니다: {key}")
    return {"records": records, "source": data.get("source", ""), "asOf": data.get("asOf", "")}
