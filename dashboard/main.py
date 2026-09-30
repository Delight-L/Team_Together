r"""원본 HTML 디자인을 사용하는 Streamlit 앱.

실행: .\.venv\Scripts\python.exe -m streamlit run main.py

수정 위치
  데이터: data/*.csv / settings.py / data_utils.py
  색·여백·배치: ui/style.css / ui/layout.html
  그래프 종류: ui/charts.js, ui/dashboard.js의 mapSVG·detailHTML·viewAnalysis
  메뉴·화면·클릭: ui/dashboard.js

Streamlit 기본 위젯 학습 코드는 main_native.py에 보관했습니다.
현재 앱은 원본 화면을 유지하기 위해 Custom Component v2를 사용합니다.
"""

# ============================================================
# 1. 라이브러리와 설정 가져오기
# ============================================================
import streamlit as st
from settings import (
    APP_TITLE, RISK_FILE, PEOPLE_FILE, MAP_FILE, FACTORS,
    DEFAULT_WEIGHTS, FACTOR_COLORS, THRESHOLDS, STATUSES, DEMO_ACCOUNTS,
)
from data_utils import load_risk_data, load_people, load_boundaries
from design_ui import render_dashboard


# ============================================================
# 2. 화면 설정 — 원본처럼 전체 너비·높이 사용
# ============================================================
st.set_page_config(page_title="고립예방 에이전트 · 지자체 대시보드", layout="wide", initial_sidebar_state="collapsed")

# 화면 내부는 ui/style.css가 담당합니다. 여기서는 Streamlit 바깥 여백만 제거합니다.
st.html("""
<style>
[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stStatusWidget"] {display:none!important;}
[data-testid="stAppViewContainer"] {padding:0!important;}
.stMainBlockContainer {padding:0!important;max-width:none!important;}
[data-testid="stMainBlockContainer"] {padding:0!important;max-width:none!important;}
[data-testid="stVerticalBlock"] {gap:0!important;}
[data-testid="stMain"] {overflow:hidden;}
</style>
""")


# ============================================================
# 3. CSV 읽기 — 기존 파일을 교체하면 화면 데이터도 변경
# ============================================================
try:
    risk_data = load_risk_data(RISK_FILE, RISK_FILE.stat().st_mtime_ns)
    people_data = load_people(PEOPLE_FILE, PEOPLE_FILE.stat().st_mtime_ns)
    geometry = load_boundaries(MAP_FILE, MAP_FILE.stat().st_mtime_ns)
except (OSError, ValueError, KeyError) as error:
    st.error(f"자료를 읽지 못했습니다: {error}")
    st.info("data 폴더와 사용안내.md의 열 설명을 확인해 주세요.")
    st.stop()


# ============================================================
# 4. 날짜 범위 / 지도 자료 준비
# ============================================================
start_date = risk_data["date"].min().strftime("%Y-%m-%d")
end_date = risk_data["date"].max().strftime("%Y-%m-%d")
months = sorted(risk_data["date"].dt.strftime("%Y-%m").unique().tolist())
cities = risk_data["city"].unique().tolist()
missing_cities = [city for city in cities if city not in geometry]
if missing_cities:
    st.error("지도 경계 자료가 없는 지자체: " + ", ".join(missing_cities))
    st.stop()
geometry = {city: geometry[city] for city in cities}


# ============================================================
# 5. 날짜별 요인 → 화면 자료로 변환
# ============================================================
# 화면에서 가중치를 바꿀 때 이 원자료로 새로운 위험도를 계산합니다.
risk_rows = risk_data[["date", "city", "district", *FACTORS]].copy()
risk_rows["date"] = risk_rows["date"].dt.strftime("%Y-%m-%d")
risk_records = risk_rows.values.tolist()


# ============================================================
# 6. 대상자 목록 → 원본의 관리 화면에 연결
# ============================================================
people_by_city = {}
for city in cities:
    group = people_data[people_data["city"].eq(city)].sort_values("risk_score", ascending=False)
    people_by_city[city] = [
        {
            "name": row["name"], "age": row["age"], "u": row["district"],
            "s": float(row["risk_score"]), "why": str(row["reason"]).split(" / "),
            "st": row["status"], "last": row["last_contact"],
        }
        for _, row in group.iterrows()
    ]


# ============================================================
# 7. 기본 가중치 / 요인 이름 / 시연 계정
# ============================================================
accounts = [
    {
        "id": account_id, "pw": account["password"], "org": account["org"],
        "name": "전체 관리자" if account["admin"] else f"{account['org']} 복지정책과 담당자",
        "admin": account["admin"],
    }
    for account_id, account in DEMO_ACCOUNTS.items()
]
payload = {
    "title": APP_TITLE, "geometry": geometry, "riskRows": risk_records,
    "people": people_by_city, "startDate": start_date, "endDate": end_date,
    "months": months, "factorNames": list(FACTORS.values()),
    "factorShortNames": ["유동인구", "카드 결제", "1인 가구", "고령 인구", "복지 연계"],
    "factorColors": FACTOR_COLORS,
    "weights": [DEFAULT_WEIGHTS[key] for key in FACTORS],
    "thresholds": THRESHOLDS, "statuses": STATUSES, "accounts": accounts,
}


# ============================================================
# 8. 원본 디자인 표시
# ============================================================
# layout.html: 로그인·메뉴·챗봇 뼈대 / style.css: 색·간격·카드 배치
# dashboard.js: 화면 생성·지도 클릭 / charts.js: 추이 그래프
# data.js: 날짜 조회·월평균·위험 점수 계산
render_dashboard(payload)
