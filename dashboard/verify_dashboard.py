"""보관한 Streamlit 기본 위젯 버전(main_native.py)의 동작 검사 도구."""

import os
from pathlib import Path
import tempfile
import sys

import pandas as pd
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard.settings import RISK_FILE, DEFAULT_WEIGHTS, FACTORS
from dashboard.data_utils import load_risk_data
from dashboard.legacy_data import PAGES, make_snapshot, calculate_scores, risk_level

os.chdir(Path(__file__).resolve().parent)


def healthy(app):
    assert not app.exception, [error.message for error in app.exception]


def login(account):
    app = AppTest.from_file("main_native.py", default_timeout=30).run()
    app.button(key=f"demo_{account}").click().run()
    app.button[0].click().run()
    healthy(app)
    assert app.session_state.user["id"] == account
    return app


# 1. 계산 검증: 경계 점수, 가중 평균, 월평균, 비교 자료 누락.
data = load_risk_data(RISK_FILE, RISK_FILE.stat().st_mtime_ns)
city = data[data.city.eq("강남구")]
assert [risk_level(v) for v in [41.9, 42, 51.9, 52, 59.9, 60]] == [
    "양호",
    "주의",
    "주의",
    "위험",
    "위험",
    "심각",
]
snapshot = make_snapshot(city, "일", "2026-09-20", DEFAULT_WEIGHTS)
raw = city[city.date.eq(pd.Timestamp("2026-09-20"))].set_index("district")
for _, row in snapshot.iterrows():
    expected = (
        sum(
            raw.loc[row.district, key] * weight
            for key, weight in DEFAULT_WEIGHTS.items()
        )
        / 100
    )
    assert abs(row.score - expected) < 1e-10
monthly = make_snapshot(city, "월", "2026-09", DEFAULT_WEIGHTS)
sample = monthly.iloc[0]
observed = city[
    city.district.eq(sample.district) & city.date.dt.strftime("%Y-%m").eq("2026-09")
]
expected_month = (
    sum(observed[key].mean() * weight for key, weight in DEFAULT_WEIGHTS.items()) / 100
)
assert abs(sample.score - expected_month) < 1e-10
assert make_snapshot(city, "일", "2025-08-01", DEFAULT_WEIGHTS).delta.isna().all()
try:
    calculate_scores(raw.reset_index(), {key: 0 for key in FACTORS})
    raise AssertionError("0 가중치가 거부되지 않았습니다.")
except ValueError:
    pass

# 잘못 교체한 CSV가 조용히 잘못된 위험도를 만들지 않는지 확인합니다.
with tempfile.TemporaryDirectory() as temp:
    invalid = data.head(1).copy()
    invalid["flow"] = 101
    path = Path(temp) / "invalid.csv"
    invalid.to_csv(path, index=False)
    try:
        load_risk_data(path, path.stat().st_mtime_ns)
        raise AssertionError("범위를 벗어난 점수가 거부되지 않았습니다.")
    except ValueError:
        pass

# 2. 잘못된 로그인은 진입을 허용하지 않습니다.
bad = AppTest.from_file("main_native.py", default_timeout=30).run()
bad.text_input(key="login_id").set_value("admin")
bad.text_input(key="login_password").set_value("wrong")
bad.button[0].click().run()
healthy(bad)
assert bad.error and bad.session_state.user is None

# 3. 관리자: 7개 화면, 두 지역, 월별 보기, 그래프 종류 전환.
app = login("admin")
for page in PAGES + ["접속·조회 로그"]:
    app.radio(key="page").set_value(page).run()
    healthy(app)
app.radio(key="page").set_value("종합 현황").run()
for name in ["강남구", "춘천시"]:
    app.selectbox(key="city").set_value(name).run()
    healthy(app)
    for chart_type in ["꺾은선", "영역", "막대"]:
        app.selectbox(key="trend_kind").set_value(chart_type).run()
        healthy(app)
    app.selectbox(key="factor_kind").set_value("레이더").run()
    healthy(app)
app.segmented_control(key="mode").set_value("월").run()
healthy(app)
assert app.selectbox(key="month_춘천시").value == "2026-09"

# 4. 가중치의 저장, 화면 이동 후 유지, 0 합계 거부, 초기화.
app.radio(key="page").set_value("위험도 기준").run()
app.slider(key="weight_flow_0").set_value(40)
next(button for button in app.button if button.label == "가중치 적용").click().run()
healthy(app)
assert app.session_state.weights["flow"] == 40
app.radio(key="page").set_value("동별 분석").run()
app.radio(key="page").set_value("위험도 기준").run()
assert app.session_state.weights["flow"] == 40
for slider in app.slider:
    slider.set_value(0)
next(button for button in app.button if button.label == "가중치 적용").click().run()
healthy(app)
assert app.error and app.session_state.weights["flow"] == 40
app.button(key="reset_weights").click().run()
healthy(app)
assert app.session_state.weights == DEFAULT_WEIGHTS

# 5. 챗봇 응답, 대상자 필터, 소속별 접근, 로그아웃.
app.toggle(key="show_chat").set_value(True).run()
app.button(key="question_0").click().run()
healthy(app)
assert len(app.session_state.messages) == 2
assert "춘천시" in app.session_state.messages[-1]["content"]
app.radio(key="page").set_value("대상자 관리").run()
app.selectbox(key="people_status").set_value("상담 완료").run()
healthy(app)
if app.dataframe:
    assert app.dataframe[0].value["조치 상태"].eq("상담 완료").all()

for account, city_name in [("gangnam01", "강남구"), ("chuncheon01", "춘천시")]:
    scoped = login(account)
    assert "접속·조회 로그" not in scoped.radio(key="page").options
    assert not any(widget.key == "city" for widget in scoped.selectbox)
    scoped.radio(key="page").set_value("대상자 관리").run()
    healthy(scoped)
    assert len(scoped.dataframe[0].value) == 32
    next(button for button in scoped.button if button.label == "로그아웃").click().run()
    healthy(scoped)
    assert scoped.session_state.user is None

print(
    "PASS: calculations, data validation, login, 7 menus, 2 cities, periods, charts, weights, chat, people filters, logout"
)
