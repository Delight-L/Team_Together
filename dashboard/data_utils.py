"""파트 2. 데이터 불러오기 → 검사 → 기간 집계 → 위험도 계산.

화면을 바꾸지 않고 자료만 바꾸려면 이 파일과 settings.py를 수정하세요.
CSV 한 행은 '하루 / 지자체 / 행정동 / 5개 위험 요인'입니다.
"""
import json

import numpy as np
import pandas as pd
import streamlit as st

from settings import FACTORS, THRESHOLDS, STATUSES


def require_columns(df, columns, label):
    # 필요한 열이 없으면 어떤 열을 추가해야 하는지 알려줍니다.
    missing = set(columns) - set(df.columns)
    if missing:
        raise ValueError(f"{label}: 필요한 열이 없습니다: {', '.join(sorted(missing))}")
    if df.empty:
        raise ValueError(f"{label}: 데이터가 비어 있습니다.")


def check_numbers(df, columns, label):
    # 문자, 빈칸, 무한대, 0~100 밖의 점수를 조용히 계산하지 않도록 검사합니다.
    for column in columns:
        df[column] = pd.to_numeric(df[column], errors="raise")
        if not (np.isfinite(df[column]) & df[column].between(0, 100)).all():
            raise ValueError(f"{label}: {column}은 빈칸 없이 0~100 숫자로 입력하세요.")


@st.cache_data(show_spinner=False, max_entries=4)
def load_risk_data(path, modified_time):
    # cache_data: 같은 파일을 버튼 클릭 때마다 다시 읽지 않도록 결과를 기억합니다.
    # modified_time: CSV를 저장하면 수정 시간이 달라져 새 자료를 다시 읽습니다.
    df = pd.read_csv(path, encoding="utf-8-sig")
    require_columns(df, ["date", "city", "district", *FACTORS], "위험 요인 CSV")
    if df[["date", "city", "district"]].isna().any().any():
        raise ValueError("날짜, 지자체, 행정동은 비워 둘 수 없습니다.")
    for column in ["city", "district"]:
        df[column] = df[column].astype(str).str.strip()
        if df[column].eq("").any():
            raise ValueError(f"{column}에 빈 이름이 있습니다.")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise")
    if df.duplicated(["date", "city", "district"]).any():
        raise ValueError("같은 날짜·지자체·행정동은 한 행만 입력하세요.")
    check_numbers(df, FACTORS, "위험 요인 CSV")
    return df.sort_values(["date", "city", "district"]).reset_index(drop=True)


@st.cache_data(show_spinner=False, max_entries=4)
def load_people(path, modified_time):
    df = pd.read_csv(path, encoding="utf-8-sig")
    columns = ["person_id", "city", "name", "age", "district", "risk_score", "reason", "status", "last_contact"]
    require_columns(df, columns, "대상자 CSV")
    if df[columns].isna().any().any() or df["person_id"].duplicated().any():
        raise ValueError("대상자 자료에는 빈칸이나 중복 person_id가 없어야 합니다.")
    check_numbers(df, ["risk_score"], "대상자 CSV")
    if not df["status"].isin(STATUSES).all():
        raise ValueError(f"status는 {', '.join(STATUSES)} 중 하나여야 합니다.")
    df["last_contact"] = pd.to_datetime(df["last_contact"], errors="raise").dt.strftime("%Y-%m-%d")
    return df


@st.cache_data(show_spinner=False, max_entries=4)
def load_boundaries(path, modified_time):
    # 원본 HTML에서 꺼낸 SVG 지도 경계입니다. 실제 위도·경도 데이터가 아닙니다.
    return json.loads(path.read_text(encoding="utf-8"))


def risk_level(score):
    if score < THRESHOLDS[0]:
        return "양호"
    if score < THRESHOLDS[1]:
        return "주의"
    if score < THRESHOLDS[2]:
        return "위험"
    return "심각"


def calculate_scores(df, weights):
    # 가중 평균 = (요인1×가중치1 + ... + 요인5×가중치5) / 가중치 합계
    # 예: 25,25,20,15,15의 합은 100이지만 다른 합계여도 계산할 수 있습니다.
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("가중치 중 하나 이상은 0보다 커야 합니다.")
    result = df.copy()
    result["score"] = sum(result[key] * weights[key] for key in FACTORS) / total
    result["level"] = result["score"].map(risk_level)
    return result


def period_data(df, mode, period):
    if mode == "일":
        return df.loc[df["date"].eq(pd.Timestamp(period)), ["district", *FACTORS]].copy()
    # 월별 집계: 해당 월에 존재하는 일별 점수의 평균을 구합니다.
    # 2026년 9월 샘플은 20일까지 있으므로 1~20일의 평균입니다.
    monthly = df[df["date"].dt.strftime("%Y-%m").eq(str(period))]
    return monthly.groupby("district", as_index=False)[list(FACTORS)].mean()


def make_snapshot(df, mode, period, weights):
    current = calculate_scores(period_data(df, mode, period), weights)
    if mode == "일":
        previous_period = pd.Timestamp(period) - pd.Timedelta(days=7)
    else:
        previous_period = str(pd.Period(str(period), freq="M") - 1)
    previous = calculate_scores(period_data(df, mode, previous_period), weights)
    # 이전 값이 없으면 NaN으로 남깁니다. 0점으로 채우면 거짓 상승이 생깁니다.
    current = current.merge(previous[["district", "score"]].rename(columns={"score": "previous"}), on="district", how="left")
    current["delta"] = current["score"] - current["previous"]
    current["main_factor"] = current.apply(lambda row: FACTORS[max(FACTORS, key=lambda key: row[key] * weights[key])], axis=1)
    return current.sort_values("score", ascending=False).reset_index(drop=True)


def make_trend(df, mode, period, district, weights):
    if mode == "일":
        end = pd.Timestamp(period)
        view = df[df["date"].between(end - pd.Timedelta(days=29), end)].copy()
        scores = calculate_scores(view, weights)
        scores["period"] = scores["date"]
    else:
        end = pd.Period(str(period), freq="M")
        view = df.copy()
        view["period"] = view["date"].dt.to_period("M")
        view = view[view["period"].between(end - 11, end)]
        scores = calculate_scores(view.groupby(["period", "district"], as_index=False)[list(FACTORS)].mean(), weights)
        scores["period"] = scores["period"].dt.to_timestamp()
    average = scores.groupby("period", as_index=False)["score"].mean().rename(columns={"score": "지역 평균"})
    selected = scores[scores["district"].eq(district)][["period", "score"]].rename(columns={"score": district})
    # 없는 날짜를 가짜 점수로 보간하지 않습니다.
    return average.merge(selected, on="period", how="left")


def display_snapshot(df):
    columns = {"district": "행정동", "level": "위험 단계", "score": "위험도", "delta": "이전 대비", "main_factor": "주요 요인"}
    return df[list(columns)].rename(columns=columns).round(2)
