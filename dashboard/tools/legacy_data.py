"""보관한 main_native.py 전용 계산입니다. 현재 화면은 ui/data.js를 씁니다.

구형 화면의 동작을 보존하기 위해 계산·표시 설정을 이 파일에 모았습니다.
"""

import pandas as pd
import streamlit as st

from dashboard.common import require_columns, check_numbers
from dashboard.common import BASE_DIR, FACTORS, THRESHOLDS

PEOPLE_FILE = BASE_DIR / "data" / "people.csv"
DATA_LABEL = "시연용 샘플 데이터"
LEVEL_COLORS = {
    "양호": "#4E9A76",
    "주의": "#C68B2C",
    "위험": "#DB7840",
    "심각": "#B5527A",
}
STATUSES = ["미배정", "방문 예정", "상담 완료", "모니터링"]
PAGES = [
    "종합 현황",
    "동별 분석",
    "대상자 관리",
    "조치 현황",
    "데이터 연계",
    "위험도 기준",
]


@st.cache_data(show_spinner=False, max_entries=4)
def load_people(path, modified_time):
    """구형 시연 화면의 가상 대상자 CSV를 읽고 검사합니다."""
    data = pd.read_csv(path, encoding="utf-8-sig")
    columns = [
        "person_id",
        "city",
        "name",
        "age",
        "district",
        "risk_score",
        "reason",
        "status",
        "last_contact",
    ]
    require_columns(data, columns, "시연 대상자 CSV")
    check_numbers(data, ["risk_score"], "시연 대상자 CSV")
    if data["person_id"].duplicated().any():
        raise ValueError("person_id는 중복될 수 없습니다.")
    if not data["status"].isin(STATUSES).all():
        raise ValueError("status는 설정된 조치 상태 중 하나여야 합니다.")
    return data


def risk_level(score):
    """점수를 4개 단계 이름으로 바꿉니다."""
    if score < THRESHOLDS[0]:
        return "양호"
    if score < THRESHOLDS[1]:
        return "주의"
    if score < THRESHOLDS[2]:
        return "위험"
    return "심각"


def calculate_scores(data, weights):
    """5개 요인의 가중 평균과 기여가 가장 큰 요인을 계산합니다."""
    total_weight = sum(weights.values())
    if total_weight <= 0:
        raise ValueError("가중치 합계는 0보다 커야 합니다.")
    result = data.copy()
    contributions = pd.DataFrame(index=result.index)
    for column in FACTORS:
        contributions[column] = result[column] * weights[column] / total_weight
    result["score"] = contributions.sum(axis=1)
    result["level"] = result["score"].map(risk_level)
    result["main_factor"] = contributions.idxmax(axis=1).map(FACTORS)
    return result


def period_factors(data, mode, period):
    """일별 원자료 또는 관측된 날짜의 월평균을 동별로 반환합니다."""
    if mode == "일":
        selected = data["date"] == pd.Timestamp(period)
        return data.loc[selected, ["district", *FACTORS]].copy()
    selected = data["date"].dt.strftime("%Y-%m") == str(period)
    monthly_data = data.loc[selected, ["district", *FACTORS]]
    return monthly_data.groupby("district", as_index=False).mean()


def make_snapshot(data, mode, period, weights):
    """선택 기간의 점수와 일:7일 전 / 월:전월 대비 차이를 계산합니다."""
    current = calculate_scores(period_factors(data, mode, period), weights)
    if mode == "일":
        previous_period = pd.Timestamp(period) - pd.Timedelta(days=7)
    else:
        previous_period = str(pd.Period(str(period), freq="M") - 1)
    previous = calculate_scores(period_factors(data, mode, previous_period), weights)
    previous = previous[["district", "score"]].rename(
        columns={"score": "previous_score"}
    )
    result = current.merge(previous, on="district", how="left", validate="one_to_one")
    result["delta"] = result["score"] - result["previous_score"]
    return result.sort_values("score", ascending=False).reset_index(drop=True)


def make_trend(data, mode, period, district, weights):
    """선택 동과 전체 동 평균의 시계열 표를 만듭니다."""
    if mode == "일":
        end_date = pd.Timestamp(period)
        start_date = end_date - pd.Timedelta(days=29)
        selected = data["date"].between(start_date, end_date)
        period_data = data.loc[selected].copy()
        period_data["period"] = period_data["date"].dt.strftime("%Y-%m-%d")
    else:
        period_data = data.copy()
        period_data["period"] = period_data["date"].dt.strftime("%Y-%m")
        available = sorted(
            period_data.loc[period_data["period"] <= str(period), "period"].unique()
        )
        period_data = period_data[period_data["period"].isin(available[-12:])]
    grouped = period_data.groupby(["period", "district"], as_index=False)[
        list(FACTORS)
    ].mean()
    scored = calculate_scores(grouped, weights)
    average = scored.groupby("period")["score"].mean().rename("지역 평균")
    selected_scores = (
        scored[scored["district"] == district]
        .set_index("period")["score"]
        .rename(district)
    )
    return pd.concat([average, selected_scores], axis=1).reset_index()


def display_snapshot(rows):
    """내부 열 이름을 화면용 한글로 바꿉니다."""
    labels = {
        "district": "행정동",
        "score": "위험도",
        "level": "단계",
        "delta": "이전 대비",
        "main_factor": "주요 요인",
    }
    return rows[list(labels)].rename(columns=labels).round(1)
