"""2024–2025 원본 재집계에서 동별 전년 동월 변화 화면 자료를 만든다."""
import json
from pathlib import Path
from statistics import median

import streamlit as st


METRICS = Path(__file__).with_name("data") / "two_year_dong_metrics.json"
FIELDS = ("low_comm", "low_weekday", "low_holiday", "low_both", "contacts", "weekday_moves", "holiday_moves")


@st.cache_data(show_spinner=False)
def load_detection_rows(path: str, modified_ns: int) -> dict:
    rows = json.loads(Path(path).read_text(encoding="utf-8"))["rows"]
    if len(rows) != 528 or len({(r["month"], str(r["dong_code"])) for r in rows}) != 528:
        raise ValueError("전년 동월 집계는 24개월 × 22개 동이어야 합니다.")
    if any(r.get(k) is None for r in rows for k in FIELDS):
        raise ValueError("탐지 지표에 누락값이 있습니다.")
    by_key = {(r["month"], str(r["dong_code"])): r for r in rows}
    comparable = []
    for row in rows:
        if not row["month"].startswith("2025-") or row["dong"] == "개포3동":
            continue
        previous = by_key[("2024-" + row["month"][-2:], str(row["dong_code"]))]
        delta = {key: row[key] - previous[key] for key in FIELDS}
        comparable.append((row, previous, delta))
    threshold = median(abs(delta["low_both"]) for _, _, delta in comparable)
    result = []
    for row, previous, delta in comparable:
        comm = delta["low_comm"] > 0 and delta["contacts"] < 0
        outing = delta["low_weekday"] > 0 and delta["low_holiday"] > 0 and delta["weekday_moves"] < 0 and delta["holiday_moves"] < 0
        joint = delta["low_both"] > 0
        stage = "우선 검토" if comm and outing and joint and delta["low_both"] >= threshold else "전년 동월 변화" if comm and outing and joint else "조건 미충족"
        result.append({
            "month": row["month"], "dongCode": str(row["dong_code"]), "dong": row["dong"], "stage": stage,
            "joint2024": previous["low_both"], "joint2025": row["low_both"],
            "deltas": delta, "comm": comm, "outing": outing, "joint": joint,
        })
    return {"source": "2024–2025 행정동단위 통신정보·관심집단수 원본 48개 재집계", "threshold": threshold, "rows": result}
