"""공식 문서에서 정리한 2025년 계획사업을 검토 후보로 제공한다."""
import json
from pathlib import Path

import streamlit as st


POLICY_FILE = Path(__file__).resolve().parents[1] / "data" / "gangnam_policy_plans_2025.json"

# 동·월 집계로 확인할 수 있는 범위만 연결한다. 연령·소득·개인 상태가
# 필요한 사업은 이 단계에서 자동 후보로 만들지 않는다.
MATCHABLE = {
    "세곡동행": {"dong": "세곡동", "months": (5, 12), "signal": "소통·외출"},
    "스마트 안부확인": {"dong": None, "months": (1, 12), "signal": "소통"},
    "동별 사회관계망 형성사업": {"dong": None, "months": (2, 12), "signal": "소통"},
}


@st.cache_data(show_spinner=False)
def load_policy_plans(path: str, modified_ns: int) -> list[dict]:
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {item["사업명"] for item in source}
    if not MATCHABLE.keys() <= names:
        raise ValueError("2025년 계획사업 정리표에 연결 대상 사업이 없습니다.")
    result = []
    for item in source:
        if item["사업명"] not in MATCHABLE:
            continue
        rule = MATCHABLE[item["사업명"]]
        result.append({
            "name": item["사업명"], "target": item["대상"],
            "agency": item["기관"], "support": item["지원내용"],
            "check": item["확인절차"], "sourceFile": item["출처파일"],
            "sourcePage": item["PDF페이지"], "planPeriod": item["계획기간"],
            "status": item["상태"], "dong": rule["dong"],
            "fromMonth": rule["months"][0], "throughMonth": rule["months"][1],
            "signal": rule["signal"],
        })
    return result
