import streamlit as st

from chat_service import answer_question, get_example_questions, is_gemini_configured


st.set_page_config(page_title="사회적 고립 위험 설명 챗봇", page_icon="💬", layout="centered")

st.title("사회적 고립 위험 설명 챗봇")
st.caption("Gemini 기반 시연용 버전 · 현재는 가상 분석결과를 설명합니다.")

if is_gemini_configured():
    st.success("Gemini 자유 질문 모드가 연결되었습니다.", icon="✨")
else:
    st.info("`.env`에 Gemini API 키를 넣으면 자유 질문 모드가 켜집니다. 현재는 기본 안내 모드입니다.")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "안녕하세요. 지역 활동 변화와 Robust Z-score 기준을 설명해 드립니다.\n\n"
                "예: ‘논현1동은 왜 후보야?’, ‘Robust Z-score 2.5는 무슨 뜻이야?’"
            ),
        }
    ]

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

st.subheader("추천 질문")
question_columns = st.columns(2)
for index, question in enumerate(get_example_questions()):
    if question_columns[index % 2].button(question, key=f"example_{index}"):
        st.session_state.pending_question = question

prompt = st.chat_input("지역명 또는 궁금한 기준을 입력하세요")
question = st.session_state.pop("pending_question", None) or prompt

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    history = st.session_state.messages[-8:-1]
    reply = answer_question(question, history)
    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)

with st.expander("현재 시연 버전의 범위"):
    st.markdown(
        "- 가상 지역 분석결과를 근거로 변화율·상대 변화량·Robust Z-score를 설명합니다.\n"
        "- 실제 위험 분석, 최신 데이터 조회, 자원 추천 기능은 아직 연결되지 않았습니다.\n"
        "- 이후 `chat_service.py`의 `get_risk_result()`만 실제 위험분석 API 호출로 바꾸면 됩니다."
    )
