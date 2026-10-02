"""파트 2. CSV·지도 데이터 불러오기 및 유효성 검사.

화면을 바꾸지 않고 자료만 바꾸려면 이 파일과 settings.py를 수정하세요.
CSV 한 행은 '하루 / 지자체 / 행정동 / 5개 위험 요인'입니다.
"""

import json

import numpy as np
import pandas as pd
import streamlit as st

from dashboard.settings import FACTORS


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
def load_boundaries(path, modified_time):
    # 행정동의 SVG 지도 경계입니다. 실제 위도·경도 데이터가 아닙니다.
    return json.loads(path.read_text(encoding="utf-8"))
