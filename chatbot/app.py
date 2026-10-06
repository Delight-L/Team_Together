"""Standalone WELFIND assistant: menus are local; only submitted AI questions call Gemini."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from chatbot.service import explain_question
from db.analysis_repository import load_analysis2_data

st.set_page_config(page_title="복지탐정 AI", layout="centered")
st.title("무엇을 도와드릴까요?")
st.caption("메뉴 선택과 저장된 분석 결과 확인은 AI 토큰을 사용하지 않습니다.")
topics = {
    "지역 변화": "지역과 기준월을 선택하면 저장된 분석 근거를 확인할 수 있습니다.",
    "분석 기준": "Robust Z는 과거 변화와의 차이를 나타냅니다. 후보 없음과 이력 부족을 구분해 확인하세요.",
    "복지사업 연결": "대시보드에서 분석 근거를 확인하고 사업 대상과 모집 조건을 검토하세요.",
    "검토 보고서": "대시보드에서 사업 검토를 저장한 뒤 보고서를 생성하세요.",
}
topic = st.segmented_control("궁금한 주제", list(topics), key="topic")
if topic:
    st.info(topics[topic])
data = load_analysis2_data()
months = sorted({row["기준연월"] for row in data["assessment"]})
month = st.selectbox("기준월", months, index=len(months)-1)
regions = sorted({row["행정동명"] for row in data["assessment"] if row["기준연월"] == month})
region = st.selectbox("지역", regions)
evidence = [row for row in data["assessment"] if row["기준연월"] == month and row["행정동명"] == region]
with st.expander("저장된 분석 근거 · AI 호출 없음"):
    st.dataframe(evidence, hide_index=True)
enabled = st.toggle("AI 에이전트 사용", value=False, key="agent_enabled")
st.caption("AI를 켜고 질문을 보내면 토큰이 사용될 수 있습니다. 연결 설정이 없으면 기본 근거 안내를 제공합니다.")
st.session_state.setdefault("messages", [])
for item in st.session_state.messages:
    with st.chat_message(item["role"]):
        st.markdown(item["content"])
question = st.chat_input("선택 지역의 분석 근거를 질문하세요")
if question:
    reply, mode = explain_question(question,evidence,st.session_state.messages[-8:],allow_agent=enabled)
    st.session_state.messages.extend([{"role":"user","content":question},{"role":"assistant","content":reply + "\n\n" + mode}])
    st.rerun()
