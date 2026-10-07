"""파트 1. 자주 바꾸는 설정을 한곳에 모았습니다."""

from pathlib import Path

# __file__은 이 파일의 위치입니다. 다른 폴더에서 실행해도 데이터를 찾습니다.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
APP_TITLE = "복지탐정 AI"

# 데이터 교체: 아래 경로를 바꾸거나, data 폴더의 CSV 내용을 교체하세요.
RISK_FILE = DATA_DIR / "risk_factors.csv"
GROUP_FILE = DATA_DIR / "group_signals.json"
MAP_FILE = BASE_DIR.parents[1] / "shared" / "data" / "map_boundaries.json"

# 왼쪽은 CSV 열 이름, 오른쪽은 화면에 표시할 이름입니다.
# 모든 요인은 '값이 클수록 위험'인 0~100 점수로 준비합니다.
FACTORS = {
    "flow": "유동인구 감소",
    "card": "카드 결제 감소",
    "single": "1인 가구 비율",
    "elder": "고령 인구 비율",
    "welfare": "복지 연계 공백",
}
DEFAULT_WEIGHTS = {"flow": 25, "card": 25, "single": 20, "elder": 15, "welfare": 15}
FACTOR_COLORS = ["#2563EB", "#60A5FA", "#10B981", "#F59E0B", "#1E293B"]

# 위험도 42 미만: 양호 / 42 이상: 주의 / 52 이상: 위험 / 60 이상: 심각
THRESHOLDS = [42, 52, 60]

# 대시보드 시연 계정입니다. 실제 인증용 계정 저장소가 아닙니다.
# 실제 서비스 전환 시 로그인 함수와 계정 관리를 인증 서비스로 교체하세요.
from shared.accounts import DEMO_ACCOUNTS

"""파트 2. CSV·지도 데이터 불러오기 및 유효성 검사.

화면과 업무에서 공유하는 설정·자료 검사·근거 선택 함수를 모았습니다.
CSV 한 행은 '하루 / 지자체 / 행정동 / 5개 위험 요인'입니다.
"""

import json

import numpy as np
import pandas as pd
import streamlit as st




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

"""Public workflow facade used by dialogs and reports."""
from agents.service_matching import match_services
from chatbot.service import explain_question

def selected_evidence(request, db_data):
    if request.get("city") != "강남구":
        return []
    return [r for r in db_data.get("assessment", []) if r["기준연월"] == request["month"] and r["행정동명"] == request.get("district")]
