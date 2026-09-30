# 사회적 고립 위험 설명 챗봇 (시연용)

위험분석 에이전트와 자원연결 에이전트가 아직 없는 상태에서도 실행할 수 있는 Streamlit 챗봇입니다. Gemini를 연결하면 자유 문장 질문을 이해해 가상 분석결과를 자연어로 설명합니다.

## 1. Gemini API 키 설정

`.env.example` 파일을 복사해 파일 이름을 `.env`로 바꾼 뒤, 발급받은 키를 넣습니다.

```text
GEMINI_API_KEY=여기에_발급받은_API_키
```

`.env` 파일은 절대 GitHub에 올리지 마세요.

## 실행

```bash
cd social_isolation_chatbot
pip install -r requirements.txt
streamlit run app.py
```

브라우저가 열리면 다음 질문을 해 보세요.

- `논현1동은 왜 후보야?`
- `역삼1동 분석 결과를 보여줘`
- `Robust Z-score 2.5는 무슨 뜻이야?`
- `상대 변화량은 왜 봐야 해?`

## 나중에 실제 에이전트와 연결하는 곳

`chat_service.py`의 `get_risk_result(region)`은 현재 `mock_data.json`을 읽습니다.
위험분석 에이전트가 완성되면 이 함수 안을 해당 API 호출로 교체하면 됩니다.

Gemini는 `chat_service.py`의 `answer_with_gemini()`에서 사용하며, 모델명은 `gemini-3.7-flash`입니다. LLM은 질문 이해와 문장 작성만 담당하고, 수치 근거는 JSON/API 결과에서만 가져오도록 제한했습니다.

## 지역명 오타 보정

`논형돈 1동`처럼 한두 글자가 틀린 입력은 유사한 지역명을 찾아 `논현1동`으로 보정합니다. 다만 여러 지역이 비슷해 확신할 수 없는 경우에는 자동으로 바꾸지 않아 잘못된 지역 분석을 막습니다.

자원연결 기능은 `get_resources(region)` 같은 함수를 추가해 자원연결 에이전트 API와 연결하면 됩니다.

## 주의

이 챗봇은 ‘사회적 고립 확정’이 아니라, 활동 변화의 이례성을 설명하고 추가 확인이 필요한 지역 후보임을 안내하도록 작성했습니다.
