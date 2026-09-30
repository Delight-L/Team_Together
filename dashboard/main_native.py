r"""고립예방 대시보드 — 수업 코드처럼 위에서 아래로 읽는 Streamlit 앱.

실행: .\.venv\Scripts\python.exe -m streamlit run main.py

[수정할 곳 안내]
1. 데이터 파일·열 이름·색·가중치 → settings.py
2. CSV 읽기·기간 집계·위험도 계산 → data_utils.py
3. 지도·막대·추이 등 시각화 종류 → charts.py
4. 화면 배치·메뉴·입력 위젯 → 이 파일(main.py)

Streamlit은 버튼을 누르거나 값을 바꾸면 이 파일을 다시 실행합니다.
계속 기억해야 하는 값은 st.session_state에 넣습니다.
원본 HTML의 데이터는 시연용입니다. 실제 예측 모델이 아닙니다.
"""

# ============================================================
# 1. 라이브러리 가져오기 / 화면 기본 설정
# ============================================================
from datetime import datetime
import re

import pandas as pd
import streamlit as st

from settings import (
    APP_TITLE, RISK_FILE, PEOPLE_FILE, MAP_FILE, DATA_LABEL,
    FACTORS, DEFAULT_WEIGHTS, LEVEL_COLORS, THRESHOLDS, STATUSES,
    PAGES, DEMO_ACCOUNTS,
)
from data_utils import (
    load_risk_data, load_people, load_boundaries, make_snapshot,
    make_trend, display_snapshot, risk_level,
)
from charts import (
    make_map_chart, make_factor_chart, make_trend_chart,
    make_rank_chart, make_contribution_chart,
)

# layout='wide': 브라우저의 가로 공간을 넓게 씁니다.
st.set_page_config(page_title=APP_TITLE, page_icon=":material/location_city:", layout="wide")


# ============================================================
# 2. 기억할 값(session_state)과 공통 함수
# ============================================================
st.session_state.setdefault("user", None)
st.session_state.setdefault("weights", DEFAULT_WEIGHTS.copy())
st.session_state.setdefault("logs", [])
st.session_state.setdefault("messages", [])


def add_log(kind, detail, success=True, identity=None):
    # 현재 브라우저 세션의 기록만 저장합니다. 새 세션에서는 초기화됩니다.
    # 여러 담당자의 실제 감사 로그는 추후 별도 DB에 저장하세요.
    who = identity or st.session_state.user or {"id": "-", "org": "-"}
    st.session_state.logs.insert(0, {
        "일시": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "계정": who["id"], "소속": who["org"], "구분": kind,
        "내용": detail, "결과": "성공" if success else "실패",
    })
    st.session_state.logs = st.session_state.logs[:500]


def fill_demo(account_id):
    # 버튼의 on_click으로 실행하면 입력 위젯이 그려지기 전에 값을 채웁니다.
    account = DEMO_ACCOUNTS[account_id]
    st.session_state.login_org = account["org"]
    st.session_state.login_id = account_id
    st.session_state.login_password = account["password"]


def logout():
    add_log("접속", "로그아웃")
    # 다른 시연 계정으로 바꿀 때 이전 사용자의 필터·대화를 초기화합니다.
    logs = st.session_state.logs
    st.session_state.clear()
    st.session_state.logs = logs


def delta_text(value):
    if pd.isna(value):
        return "비교 자료 없음"
    return f"{value:+.1f}점"


def describe_region(row):
    return f"{row['district']}: {row['score']:.1f}점({row['level']}), 이전 대비 {delta_text(row['delta'])}. 주요 요인: {row['main_factor']}."


def answer_question(question, rows, selected):
    # 원본처럼 정해진 질문을 분류하는 규칙 기반 챗봇입니다.
    # 나중에 AI 모델을 연결할 때 이 함수의 내용을 교체하면 됩니다.
    text = re.sub(r"\s+", "", question)
    names = rows["district"].tolist()
    exact_names = [name for name in names if name in text]
    matches = exact_names or [name for name in names if re.sub(r"(본|\d+)동$", "", name) in text]
    if matches:
        return "\n\n".join(describe_region(row) for _, row in rows[rows["district"].isin(matches)].head(3).iterrows())
    if any(word in text for word in ["요인", "이유", "원인", "왜"]):
        return describe_region(rows[rows["district"].eq(selected)].iloc[0])
    if any(word in text for word in ["오른", "상승", "증가", "악화"]):
        # 하락한 지역을 '상승 지역'으로 소개하지 않도록 양수만 고릅니다.
        rising = rows[rows["delta"] > 0].nlargest(3, "delta")
        if rising.empty:
            return "현재 비교 가능한 자료에서 상승한 지역이 없습니다."
        return "상승 폭이 큰 지역입니다.\n\n" + "\n\n".join(describe_region(row) for _, row in rising.iterrows())
    if any(word in text for word in ["위험", "순위", "높은", "심각", "우선", "방문", "어디"]):
        return "우선 확인할 지역입니다.\n\n" + "\n\n".join(describe_region(row) for _, row in rows.head(3).iterrows())
    if "로그" in text or "이력" in text:
        return "전체 관리자 계정의 '접속·조회 로그'에서 현재 세션의 기록을 확인할 수 있습니다."
    return "'가장 위험한 동은?', '지난주보다 오른 동은?', '선택한 동 위험 요인은?'처럼 질문해 주세요."


# ============================================================
# 3. 로그인 화면 — st.form으로 입력을 한꺼번에 제출하기
# ============================================================
if st.session_state.user is None:
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        st.title("고립 위험이 커지는 동네를\n먼저 확인합니다")
        st.write("유동인구·소비 변화와 공공데이터를 함께 살펴보는 지자체 담당자용 대시보드입니다.")
        st.info("시연용 화면 · 모든 수치는 샘플 데이터입니다.")
    with right:
        st.subheader("담당자 로그인")
        with st.form("login_form"):
            org = st.selectbox("소속", ["강남구", "춘천시", "전체 관리자"], key="login_org")
            account_id = st.text_input("아이디", key="login_id")
            password = st.text_input("비밀번호", type="password", key="login_password")
            submitted = st.form_submit_button("로그인", type="primary", width="stretch")
        if submitted:
            account = DEMO_ACCOUNTS.get(account_id.strip())
            if account and account["password"] == password and account["org"] == org:
                st.session_state.user = {"id": account_id.strip(), **account}
                add_log("접속", "로그인")
                st.rerun()
            else:
                st.error("소속, 아이디, 비밀번호를 확인해 주세요.")
                add_log("접속", "로그인 실패", False, {"id": account_id, "org": org})
        with st.expander("시연 계정 보기 / 자동 입력", expanded=True):
            for account_id, account in DEMO_ACCOUNTS.items():
                st.button(f"{account['org']} · {account_id}", key=f"demo_{account_id}", on_click=fill_demo, args=(account_id,))
                st.caption(f"비밀번호: {account['password']}")
    # 로그인 전에는 이 아래의 데이터·관리 화면을 실행하지 않습니다.
    st.stop()


# ============================================================
# 4. 데이터 불러오기 — 실제 CSV로 바꿀 때 확인할 부분
# ============================================================
try:
    # 파일 수정 시간을 전달하므로 CSV를 저장한 뒤 재실행하면 새 값이 적용됩니다.
    risk_data = load_risk_data(RISK_FILE, RISK_FILE.stat().st_mtime_ns)
    people_data = load_people(PEOPLE_FILE, PEOPLE_FILE.stat().st_mtime_ns)
    boundaries = load_boundaries(MAP_FILE, MAP_FILE.stat().st_mtime_ns) if MAP_FILE.exists() else {}
except (OSError, ValueError, KeyError) as error:
    st.error(f"자료를 읽지 못했습니다: {error}")
    st.info("data 폴더와 사용안내.md의 CSV 열 설명을 확인해 주세요.")
    st.stop()


# ============================================================
# 5. 왼쪽 메뉴 / 지자체 / 집계 기간 / 행정동 선택
# ============================================================
user = st.session_state.user
with st.sidebar:
    st.title(APP_TITLE)
    st.caption(f"{user['org']} · {user['id']}")
    menus = PAGES + (["접속·조회 로그"] if user["admin"] else [])
    # 수업에서 사용한 radio: 여러 메뉴 중 한 개만 고릅니다.
    page = st.radio("메뉴", menus, key="page")
    st.divider()
    if user["admin"]:
        city = st.selectbox("지자체", sorted(risk_data["city"].unique()), key="city")
    else:
        city = user["org"]
        st.write(f"**조회 지역: {city}**")
    st.button("로그아웃", on_click=logout, icon=":material/logout:")

# 화면에 표시하기 전에 소속 지자체의 행만 가져옵니다.
city_data = risk_data[risk_data["city"].eq(city)]
if city_data.empty:
    st.info("선택한 지자체의 자료가 없습니다.")
    st.stop()

with st.sidebar:
    mode = st.segmented_control("집계 단위", ["일", "월"], default="일", key="mode") or "일"
    if mode == "일":
        available_dates = sorted(city_data["date"].dt.date.unique(), reverse=True)
        period = st.selectbox("기준일", available_dates, key=f"date_{city}")
        comparison_label = "7일 전"
    else:
        months = sorted(city_data["date"].dt.strftime("%Y-%m").unique(), reverse=True)
        period = st.selectbox("기준월", months, key=f"month_{city}")
        comparison_label = "전월"

weights = st.session_state.weights
rows = make_snapshot(city_data, mode, period, weights)
if rows.empty:
    st.info("선택한 기간에 자료가 없습니다.")
    st.stop()
with st.sidebar:
    # 기본 선택은 위험도가 가장 높은 지역입니다.
    selected = st.selectbox("상세 조회 행정동", rows["district"].tolist(), key=f"district_{city}")
    show_chat = st.toggle("고립예방 에이전트 열기", key="show_chat")

# 같은 화면의 단순 재실행마다 로그가 중복되지 않게 조회 조건을 비교합니다.
context = (user["id"], page, city, mode, str(period), selected)
if st.session_state.get("last_context") != context:
    add_log("조회", f"{page} · {city} · {mode} · {period} · {selected}")
    st.session_state.last_context = context

st.title(page)
st.caption(f"{city} · {mode} 단위 · {period} · {DATA_LABEL}")
if mode == "월":
    month_dates = city_data[city_data["date"].dt.strftime("%Y-%m").eq(str(period))]["date"]
    st.caption(f"집계에 포함된 날짜: {month_dates.min():%Y-%m-%d} ~ {month_dates.max():%Y-%m-%d} · 관측된 날짜의 평균")


# ============================================================
# 6. 종합 현황 — 단계별 요약 → 지도/상세 → 추이/순위
# ============================================================
if page == "종합 현황":
    # st.metric: 큰 숫자 카드. st.container(horizontal=True): 가로 배치.
    with st.container(horizontal=True):
        for level in reversed(LEVEL_COLORS):
            st.metric(level, f"{rows['level'].eq(level).sum()}곳", border=True)

    band = st.selectbox("위험 단계 필터 · 지도 강조 및 순위", ["전체", *LEVEL_COLORS], key="band")
    filtered = rows if band == "전체" else rows[rows["level"].eq(band)]
    map_column, detail_column = st.columns([1.6, 1], gap="medium")
    with map_column, st.container(border=True):
        st.subheader(f"{city} 행정동별 고립 위험도")
        if city in boundaries:
            zoom = st.checkbox("도심 확대", key=f"zoom_{city}") if city == "춘천시" else False
            # 그림 종류를 바꾸려면 charts.py의 make_map_chart()를 수정합니다.
            fig = make_map_chart(rows, boundaries[city], selected, band, zoom)
            st.plotly_chart(fig, key="risk_map", config={"scrollZoom": False})
            missing = set(rows["district"]) - {unit["n"] for unit in boundaries[city]["units"]}
            if missing:
                st.warning("지도 경계가 없는 지역: " + ", ".join(sorted(missing)))
            st.caption("원본 HTML의 단순화된 행정동 경계 · 색은 위험 단계 · 상세 지역은 왼쪽에서 선택하세요.")
        else:
            st.info("이 지역의 지도 경계가 없어 순위 그래프로 표시합니다.")
            st.plotly_chart(make_rank_chart(filtered), key="map_fallback")
    with detail_column, st.container(border=True):
        row = rows[rows["district"].eq(selected)].iloc[0]
        st.subheader(selected)
        st.write(f"**{row['level']}**")
        st.metric("고립 위험도", f"{row['score']:.1f} / 100", delta=None if pd.isna(row["delta"]) else f"{row['delta']:+.1f}점", delta_color="inverse")
        st.caption(f"{comparison_label} 대비 {delta_text(row['delta'])}")
        factor_kind = st.selectbox("요인 그래프 종류", ["가로 막대", "레이더"], key="factor_kind")
        st.plotly_chart(make_factor_chart(row, weights, factor_kind), key="factor_chart")
        st.info(f"가중 기여가 가장 큰 요인: {row['main_factor']}")

    trend_column, rank_column = st.columns([1.3, 1])
    with trend_column, st.container(border=True):
        st.subheader("위험도 추이")
        trend_kind = st.selectbox("추이 그래프 종류", ["꺾은선", "영역", "막대"], key="trend_kind")
        trend = make_trend(city_data, mode, period, selected, weights)
        st.plotly_chart(make_trend_chart(trend, trend_kind), key="trend_chart")
        st.caption("일: 최근 30일 · 월: 선택한 월까지 최대 12개월 · 지역 평균은 행정동별 점수의 단순 평균")
    with rank_column, st.container(border=True):
        st.subheader("우선 확인 순위")
        if filtered.empty:
            st.info("해당 단계의 지역이 없습니다.")
        else:
            st.plotly_chart(make_rank_chart(filtered), key="rank_chart")
            st.dataframe(display_snapshot(filtered.head(8)), hide_index=True)


# ============================================================
# 7. 동별 분석 — 요인별 기여도와 상세 표
# ============================================================
elif page == "동별 분석":
    st.subheader("동별 위험 요인 분해")
    st.plotly_chart(make_contribution_chart(rows, weights), key="contribution_chart")
    st.caption("각 색은 가중치를 반영한 기여 점수입니다. 다섯 색을 합하면 위험도가 됩니다.")
    st.dataframe(display_snapshot(rows), hide_index=True)
    with st.expander("요인 원점수 확인"):
        st.dataframe(rows[["district", *FACTORS]].rename(columns={"district": "행정동", **FACTORS}).round(2), hide_index=True)
    # utf-8-sig: 엑셀로 한글 CSV를 열 때 글자가 깨지지 않도록 BOM을 넣습니다.
    st.download_button("분석 결과 CSV 다운로드", display_snapshot(rows).to_csv(index=False).encode("utf-8-sig"), file_name=f"{city}_{period}_분석.csv", mime="text/csv")


# ============================================================
# 8. 대상자 관리 — 행정동·조치 상태로 필터링
# ============================================================
elif page == "대상자 관리":
    st.caption("가상의 대상자 목록 · 개인 위험도는 별도 샘플 값이며 지역 가중치와 연동되지 않습니다.")
    people = people_data[people_data["city"].eq(city)].copy()
    col1, col2 = st.columns(2)
    with col1:
        status_filter = st.selectbox("조치 상태", ["전체", *STATUSES], key="people_status")
    with col2:
        unit_filter = st.selectbox("대상자 행정동", ["전체", *sorted(people["district"].unique())], key=f"people_district_{city}")
    if status_filter != "전체":
        people = people[people["status"].eq(status_filter)]
    if unit_filter != "전체":
        people = people[people["district"].eq(unit_filter)]
    st.write(f"검색 결과 **{len(people)}명**")
    if people.empty:
        st.info("조건에 맞는 대상자가 없습니다.")
    else:
        labels = {"name": "대상자", "age": "연령대", "district": "행정동", "risk_score": "개인 위험도", "reason": "주요 사유", "status": "조치 상태", "last_contact": "최근 접촉"}
        st.dataframe(people.sort_values("risk_score", ascending=False)[list(labels)].rename(columns=labels).round(1), hide_index=True)


# ============================================================
# 9. 조치 현황 — 상태별 카드 목록
# ============================================================
elif page == "조치 현황":
    st.caption("시연용 목록 · 담당자 배정 및 방문 결과 저장은 추후 연결할 부분입니다.")
    people = people_data[people_data["city"].eq(city)]
    for column, status in zip(st.columns(4), STATUSES):
        with column:
            group = people[people["status"].eq(status)]
            st.subheader(f"{status} · {len(group)}명")
            if group.empty:
                st.caption("대상자 없음")
            for _, person in group.iterrows():
                with st.container(border=True):
                    st.write(f"**{person['name']} · {person['age']}**")
                    st.caption(f"{person['district']} · {risk_level(person['risk_score'])}")
                    st.write(person["reason"])


# ============================================================
# 10. 데이터 연계 — 어떤 자료를 연결할지 정리
# ============================================================
elif page == "데이터 연계":
    sources = pd.DataFrame({
        "데이터": ["이동전화 유동인구", "카드 결제", "주민등록 인구·세대", "주민등록 인구·세대", "복지 서비스 이용 현황"],
        "반영 지표": list(FACTORS.values()),
        "산출 내용": ["활동량 감소 점수", "소비 활동 감소 점수", "1인 가구 비율", "고령 인구 비율", "서비스 미연계 비율"],
        "현재 상태": [DATA_LABEL] * len(FACTORS),
    })
    st.dataframe(sources, hide_index=True)
    st.metric("현재 지역의 일별 자료", f"{len(city_data):,}행")
    st.caption(f"수록 기간: {city_data['date'].min():%Y-%m-%d} ~ {city_data['date'].max():%Y-%m-%d}")
    with st.expander("최근 원자료 확인"):
        st.dataframe(city_data.tail(50).rename(columns={"date": "날짜", "city": "지자체", "district": "행정동", **FACTORS}), hide_index=True)


# ============================================================
# 11. 위험도 기준 — 가중치 변경 / 기본값 복원
# ============================================================
elif page == "위험도 기준":
    st.write("위험도는 5개 요인 점수의 가중 평균입니다. 적용하면 지도·분석·추이·챗봇에 반영됩니다.")
    # form: 슬라이더를 여러 번 바꿔도 '적용'을 눌렀을 때 한 번만 반영합니다.
    # epoch: 초기화 시 폼 위젯을 새로 만들어 예전 슬라이더 값도 함께 지웁니다.
    epoch = st.session_state.get("weight_form_epoch", 0)
    with st.form(f"weight_form_{epoch}"):
        new_weights = {}
        for key, label in FACTORS.items():
            new_weights[key] = st.slider(label, 0, 40, int(weights[key]), key=f"weight_{key}_{epoch}")
        applied = st.form_submit_button("가중치 적용", type="primary")
    if applied:
        if sum(new_weights.values()) == 0:
            st.error("적어도 한 요인의 가중치는 1 이상으로 설정하세요. 기존 값은 유지됩니다.")
        else:
            st.session_state.weights = new_weights
            add_log("설정", f"가중치 변경: {new_weights}")
            st.rerun()
    if st.button("기본값으로 복원", key="reset_weights"):
        st.session_state.weights = DEFAULT_WEIGHTS.copy()
        st.session_state.weight_form_epoch = epoch + 1
        add_log("설정", "가중치 기본값 복원")
        st.rerun()
    total = sum(weights.values())
    st.write("현재 적용 비중: " + " · ".join(f"{FACTORS[key]} {value/total:.0%}" for key, value in weights.items()))
    st.info(f"양호: {THRESHOLDS[0]} 미만 / 주의: {THRESHOLDS[0]} 이상 {THRESHOLDS[1]} 미만 / 위험: {THRESHOLDS[1]} 이상 {THRESHOLDS[2]} 미만 / 심각: {THRESHOLDS[2]} 이상")


# ============================================================
# 12. 접속·조회 로그 — 시연 관리자 전용
# ============================================================
elif page == "접속·조회 로그" and user["admin"]:
    st.caption("현재 브라우저 세션에서 발생한 최근 500건 · 다른 사용자의 접속 기록과 공유되지 않습니다.")
    log_type = st.selectbox("로그 종류", ["전체", "접속", "조회", "질의", "설정"], key="log_type")
    logs = pd.DataFrame(st.session_state.logs)
    if not logs.empty:
        if log_type != "전체":
            logs = logs[logs["구분"].eq(log_type)]
        st.dataframe(logs, hide_index=True)


# ============================================================
# 13. 고립예방 에이전트 — 선택 지역/기간을 반영한 질의
# ============================================================
if show_chat:
    st.divider()
    st.subheader("고립예방 에이전트")
    st.caption(f"시연용 규칙 기반 응답 · 현재 질문 기준: {city} / {period} / {selected}")
    # 도시·기간이 달라져도 과거 답변을 오해하지 않도록 각 질문의 기준을 기록합니다.
    quick_question = None
    with st.container(horizontal=True):
        for index, question in enumerate(["가장 위험한 동은?", "오른 동은?", "선택한 동 위험 요인은?"]):
            if st.button(question, key=f"question_{index}"):
                quick_question = question
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    question = st.chat_input("예: 역삼동 상태 알려줘", key="chat_question") or quick_question
    if question:
        response = answer_question(question, rows, selected)
        response = f"**{city} · {period} · {comparison_label} 대비**\n\n{response}"
        st.session_state.messages.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": response},
        ])
        st.session_state.messages = st.session_state.messages[-40:]
        add_log("질의", f"{city} · {period} · {question}")
        st.rerun()
