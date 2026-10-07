r"""사회적 고립 위험도를 살펴보는 Streamlit 대시보드.

실행: 프로젝트 최상위에서 python -m streamlit run main.py

수정 위치
  데이터: data/*.csv / common.py
  색·여백·배치: ui/style.css / ui/layout.html
  그래프 종류: ui/charts.js, ui/dashboard.js의 mapSVG·detailHTML·viewAnalysis
  메뉴·화면·클릭: ui/dashboard.js

화면은 Streamlit Custom Component v2로 구성합니다.
"""

# ============================================================
# 1. 라이브러리와 설정 가져오기
# ============================================================
import streamlit as st
from legacy.streamlit_dashboard.common import (
    APP_TITLE,
    RISK_FILE,
    MAP_FILE,
    FACTORS,
    GROUP_FILE,
    DEFAULT_WEIGHTS,
    FACTOR_COLORS,
    THRESHOLDS,
    DEMO_ACCOUNTS,
)
from legacy.streamlit_dashboard.common import load_risk_data, load_boundaries
from legacy.streamlit_dashboard.design_ui import render_dashboard


def render_app():
    """최상위 진입점에서 호출하는 대시보드 화면."""
    st.set_page_config(
        page_title="복지탐정 AI · 분석·사업 검토·보고",
        #page_title="복지탐정 AI · 지역 복지 미션",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

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

    try:
        risk_data = load_risk_data(RISK_FILE, RISK_FILE.stat().st_mtime_ns)
        group_data = load_boundaries(GROUP_FILE, GROUP_FILE.stat().st_mtime_ns)
        geometry = load_boundaries(MAP_FILE, MAP_FILE.stat().st_mtime_ns)
    except (OSError, ValueError, KeyError) as error:
        st.error(f"자료를 읽지 못했습니다: {error}")
        st.info("data 폴더와 README.md의 열 설명을 확인해 주세요.")
        st.stop()

    start_date = risk_data["date"].min().strftime("%Y-%m-%d")
    end_date = risk_data["date"].max().strftime("%Y-%m-%d")
    months = sorted(risk_data["date"].dt.strftime("%Y-%m").unique().tolist())
    cities = risk_data["city"].unique().tolist()
    missing_cities = []
    for city in cities:
        if city not in geometry:
            missing_cities.append(city)
    if missing_cities:
        st.error("지도 경계 자료가 없는 지자체: " + ", ".join(missing_cities))
        st.stop()
    selected_geometry = {}
    for city in cities:
        selected_geometry[city] = geometry[city]
    geometry = selected_geometry

    # 화면에서 가중치를 바꿀 때 이 원자료로 새로운 위험도를 계산합니다.
    risk_rows = risk_data[["date", "city", "district", *FACTORS]].copy()
    risk_rows["date"] = risk_rows["date"].dt.strftime("%Y-%m-%d")
    risk_records = risk_rows.values.tolist()


    accounts = []
    for account_id, account in DEMO_ACCOUNTS.items():
        if account["admin"]:
            display_name = "전체 관리자"
        else:
            display_name = f"{account['org']} 복지정책과 담당자"
        accounts.append(
            {
                "id": account_id,
                "pw": account["password"],
                "org": account["org"],
                "name": display_name,
                "admin": account["admin"],
            }
        )

    factor_weights = []
    for key in FACTORS:
        factor_weights.append(DEFAULT_WEIGHTS[key])
    payload = {
        "title": APP_TITLE,
        "geometry": geometry,
        "riskRows": risk_records,
        "groupSignals": group_data,
        "startDate": start_date,
        "endDate": end_date,
        "months": months,
        "factorNames": list(FACTORS.values()),
        "factorShortNames": [
            "유동인구",
            "카드 결제",
            "1인 가구",
            "고령 인구",
            "복지 연계",
        ],
        "factorColors": FACTOR_COLORS,
        "weights": factor_weights,
        "thresholds": THRESHOLDS,
        "accounts": accounts,
    }

    # layout.html: 로그인·메뉴·챗봇 뼈대 / style.css: 색·간격·카드 배치
    # dashboard.js: 화면 생성·지도 클릭 / charts.js: 추이 그래프
    # data.js: 날짜 조회·월평균·위험 점수 계산
    from db.analysis_repository import load_analysis2_data
    from legacy.streamlit_dashboard.dialogs import handle_request

    try:
        db_data = load_analysis2_data()
    except (OSError, ValueError) as error:
        st.error(f"version11 분석 결과를 읽지 못했습니다: {error}")
        st.info("루트에서 python main.py --analysis --no-download를 실행해 결과 CSV를 생성하세요.")
        st.stop()
    from db.mission_store import load_all
    payload["missions"] = load_all()
    payload["db1"] = db_data
    payload["notice"] = st.session_state.get("operation_notice", "")
    result = render_dashboard(payload)
    next_report = st.session_state.pop("next_workflow_report", None)
    handle_request(next_report | {"action": "report"} if next_report else result.get("request"), db_data)
