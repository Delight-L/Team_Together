# 복지이음 챗봇 코드 읽기 안내

> 과거 구조의 기록입니다. 현재 실행·파일 경로는 [폴더 구성](../folder-organization.md)과 [백엔드 안내](../../backend/README.md)를 따릅니다.

학교 특강의 `chat_test` 코드와 현재 복지 챗봇은 기본 흐름이 비슷합니다. 현재 코드에는 복지자료 검색, API 키 없이 답변하는 기능, 팀 웹페이지 연결 기능이 추가되어 있습니다.

## 전체 흐름

```text
사용자가 질문 입력
       ↓
관련 복지사업 자료 검색
       ↓
검색 자료 + 답변 규칙 + 대화 내용을 AI에 전달
       ↓
답변을 조금씩 화면에 표시
```

API 키가 없으면 검색한 자료를 정해진 문장 형식으로 안내합니다.

## 먼저 읽을 핵심 파일

### 1. 특강 orchestrator.py

경로: `C:\Users\user\Desktop\chat_test\backend\app\agent\orchestrator.py`

- `build_messages()`: 챗봇의 역할을 정하는 system 메시지와 사용자 대화를 합칩니다.
- `handle_chat()`: API 키를 확인하고 AI의 답변을 받아 전달합니다.

AI에게 무엇을 보낼지 준비하고, 돌아온 답변을 전달하는 담당자라고 생각하면 됩니다.

### 2. 현재 복지 챗봇 orchestrator.py

경로: `chatbot/welfare/app/agent/orchestrator.py`

| 코드 | 역할 |
|---|---|
| `SYSTEM` | 복지이음의 역할과 답변 규칙. 자료에 없는 자격·금액 등을 지어내지 않도록 안내 |
| `search_question()` | “그 사업 신청은?” 같은 후속 질문에 앞선 질문의 맥락을 붙임 |
| `handle_chat()`의 `search(...)` | 질문에 맞는 복지자료 검색 |
| `if not settings.openai_api_key` | API 키가 없으면 자료 안내문으로 답변 |
| `messages = ...` | 답변 규칙·검색 자료·대화 이력을 합침 |
| `llm.stream(messages)` | AI 답변을 조금씩 받아 전달 |

특강에서는 **역할 설명 + 대화**를 보냈다면, 현재는 **역할 설명 + 검색한 복지자료 + 대화**를 보냅니다.

### 3. resources.py

경로: `chatbot/welfare/app/agent/resources.py`

- `load_resources()`: JSON 자료에서 사업명, 지원 내용, 대상, 기관, 출처를 읽습니다.
- `search()`: 질문의 단어와 관련 표현을 자료와 비교해 점수를 매기고 최대 5개를 고릅니다.
- `local_answer()`: API 키가 없을 때 검색 결과를 안내 문장으로 만듭니다.

예를 들어 “혼자 사는 어르신 돌봄 지원 알려줘”라는 질문에는 `어르신`, `노인`, `고령`, `돌봄` 같은 관련 표현도 활용합니다. 현재 검색은 단어 매칭 방식입니다.

자료 파일:

- `chatbot/welfare/data/policy_candidates.json`: 복지사업 후보 자료
- `chatbot/welfare/data/gangnam_policy_plans_2025.json`: 강남구 정책 자료

### 4. openai_client.py

경로: `chatbot/welfare/app/llm/openai_client.py`

```python
stream = await client.chat.completions.create(
    model=settings.openai_model,
    messages=messages,
    stream=True,
)
```

“설정된 모델에게 준비한 메시지를 보내고 답변을 조금씩 받겠다”는 뜻입니다. `yield text`는 받은 답변 조각을 다음 처리 단계에 넘깁니다.

## 나머지 파일 따라 읽기

예시 질문은 **“병원 동행 지원이 있나요?”**로 생각하면 됩니다.

### 5. config.py — 설정표

경로: `chatbot/welfare/app/config.py`

```python
openai_api_key: str = ""
openai_model: str = "gpt-4o-mini"
```

- `openai_api_key`: AI 서비스를 호출할 때 사용하는 키
- `openai_model`: 답변을 만들 모델 이름
- `""`: 별도 설정이 없으면 키가 비어 있다는 뜻

`env_file=... / ".env"`는 프로젝트 루트의 `.env`에서 설정을 읽겠다는 의미입니다. `.env`에 값을 설정하면 위 기본값 대신 사용합니다.

`orchestrator.py`의 `if not settings.openai_api_key:`에서 키 유무를 확인합니다. 키가 없으면 자료 검색 안내로 답하고, 키가 있으면 AI에게 답변을 요청합니다.

### 6. schemas.py — 입력 형식 검사

경로: `chatbot/welfare/app/schemas.py`

메시지 한 개의 기본 형태:

```json
{
  "role": "user",
  "content": "병원 동행 지원이 있나요?"
}
```

`ChatMessage`는 메시지 한 개의 형식을 정합니다.

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=6000)
```

보낸 사람은 사용자 또는 챗봇이어야 하고, 내용은 1~6,000자의 문자열이어야 한다는 뜻입니다. 공백뿐인 메시지도 검사합니다.

`ChatRequest`는 메시지 여러 개를 묶습니다.

```python
messages: list[ChatMessage] = Field(min_length=1, max_length=40)
```

이전 대화를 함께 보내야 “그 사업 신청은 어떻게 해?” 같은 후속 질문을 이해할 수 있습니다. 마지막 메시지가 사용자 질문인지도 확인합니다.

`model_validator`, `field_validator`는 입력값에 추가 검사 규칙을 붙이는 기능입니다.

### 7. welfare/service.py — 웹서버와 챗봇 연결

경로: `chatbot/welfare/service.py`

| 함수 | 역할 |
|---|---|
| `validate_messages()` | schemas.py의 규칙으로 대화 검사 |
| `stream_reply()` | 챗봇이 만드는 답변 조각을 하나씩 전달 |
| `complete_reply()` | 답변 조각을 합쳐 완성된 결과로 반환 |

```python
request = ChatRequest.model_validate({"messages": messages})
```

받은 대화가 `ChatRequest` 규칙에 맞는지 검사합니다.

```python
events = handle_chat(history, context)
```

핵심 함수 `handle_chat()`을 호출합니다. `history`는 대화 이력이고, `context`는 선택 지역과 기준월 같은 정보입니다.

`asyncio.Runner()`는 일반 웹서버 코드에서 비동기 챗봇을 실행하기 위한 연결 장치입니다. 처음에는 세부 동작보다 역할만 이해해도 됩니다.

`complete_reply()`의 다음 코드는 답변 조각을 이어 붙입니다.

```python
result["answer"] += payload["text"]
```

```text
"병원" + " 동행" + " 지원을 안내할게요."
→ "병원 동행 지원을 안내할게요."
```

### 8. webapp/server.py — 질문을 받는 창구

경로: `webapp/server.py`

파일이 길므로 `if route == '/api/chat':`를 검색해서 읽습니다.

```python
if body.get("stream") is True:
    messages = validate_messages(body.get("messages"))
    return self.chat_stream(messages, public_context)
```

1. 화면이 답변을 조금씩 받겠다고 요청했는지 확인합니다.
2. 대화 형식을 검사합니다.
3. 대화와 선택 지역 정보를 챗봇 처리 쪽으로 전달합니다.

`/api/chat`은 파일 경로가 아니라 챗봇 요청을 받는 서버 주소입니다.

서버는 로그인과 지역 접근 권한도 확인합니다. 현재 팀 서버의 POST 처리에서는 챗봇 요청 전에 `dashboard_data()`를 읽으므로, 분석 데이터 로딩 문제도 챗봇 요청에 영향을 줄 수 있습니다.

### 9. frontend/src/api.js — 화면의 통신 담당

경로: `frontend/src/api.js`

`streamWelfareChat()`을 중심으로 읽습니다.

```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({ ...context, messages, stream: true }),
});
```

선택 지역 정보와 대화 목록을 서버에 보내고 답변을 조금씩 받겠다는 뜻입니다. 위 예시는 설명을 위해 실제 코드의 일부 옵션을 생략했습니다.

- `fetch`: 서버에 요청 보내기
- `POST`: 데이터를 서버로 전달하는 요청 방식
- `JSON.stringify`: JavaScript 데이터를 전송할 문자열로 바꾸기
- `await`: 응답 기다리기

`reader.read()`는 도착한 데이터를 조금씩 읽습니다. `TextDecoder`는 받은 바이트를 문자열로 바꾸고, 버퍼에 모아 이벤트 경계에서 나눠 처리합니다.

| 이벤트 | 의미 |
|---|---|
| `sources` | 참고한 복지자료 |
| `token` | 답변 텍스트 조각 |
| `replace` | 기존 답변을 다른 안내문으로 교체 |
| `error` | 오류 안내 |
| `done` | 응답 완료 |

이벤트와 데이터를 전달하는 형식을 SSE라고 부릅니다. 답변 조각에 종류표를 붙여 보내는 방식이라고 생각하면 됩니다.

### 10. components.jsx — 대화 화면

경로: `frontend/src/components.jsx`의 `ChatPanel`

```javascript
const [messages, setMessages] = useState([]);
const [input, setInput] = useState('');
const [busy, setBusy] = useState(false);
const [error, setError] = useState('');
```

| 값 | 의미 |
|---|---|
| `messages` | 화면에 표시할 대화 |
| `input` | 입력창에 쓰고 있는 질문 |
| `busy` | 답변을 받는 중인지 여부 |
| `error` | 표시할 오류 문구 |

`useState`는 화면이 기억하는 값입니다. `setMessages` 같은 함수로 값을 바꾸면 화면도 갱신됩니다.

`send()`는 질문 전송 시 실행됩니다.

```javascript
const next = [...history, { role: 'user', text: question }];
```

기존 대화에 새 질문을 추가합니다.

```javascript
setMessages([...next, { role: 'assistant', text: '', sources: [] }]);
```

빈 챗봇 말풍선을 먼저 만듭니다. 이후 답변 조각이 오면 다음 코드로 이어 붙입니다.

```javascript
if (event === 'token')
  update(m => ({ ...m, text: m.text + payload.text }));
```

이것이 답변이 타이핑하듯 나타나는 화면 동작입니다.

화면에서는 본문 이름을 `text`로 사용하고, 서버에 보낼 때는 `content`로 바꿉니다.

```javascript
next.map(m => ({ role: m.role, content: m.text }))
```

같은 메시지 내용이지만 화면 내부 형식과 서버 요청 형식의 이름이 다릅니다.

`stop()`은 진행 중인 요청을 중지합니다. 지역·기준월 등 맥락이 바뀌면 기존 요청을 중지하고 대화를 초기화합니다.

### 11. App.jsx — 챗봇을 페이지에 배치

경로: `frontend/src/App.jsx`

챗봇을 열고 닫거나 크게 표시하는 상태를 관리합니다. 선택한 지역과 기준월을 `ChatPanel`에 전달하고, 다른 화면에서 만들어진 질문 초안도 연결합니다.

처음에는 `ChatPanel`을 사용하는 부분과 `expandChat()`, `collapseChat()`, `closeChat()`를 찾아보면 됩니다.

### 12. main.py 두 종류 구분하기

현재 팀 웹페이지 실행 흐름:

```text
프로젝트 루트 main.py → webapp/server.py
```

`chatbot/welfare/app/main.py`는 특강과 비슷한 FastAPI 챗봇 서버를 별도로 실행하는 진입점입니다. 현재 팀 화면을 이해할 때는 `webapp/server.py`를 따라가면 됩니다.

파일 이름이 `main.py`라고 해서 모두 같은 실행 과정에 참여하는 것은 아닙니다.

### 13. chatbot/orchestrator.py — 기존 호출 연결

경로: `chatbot/orchestrator.py`

복지 챗봇의 핵심 파일인 `chatbot/welfare/app/agent/orchestrator.py`와 구분해야 합니다.

- `topic_reply()`: 정해진 주제 질문을 연결합니다.
- `free_reply()`: 질문과 대화 이력을 정리해 `complete_reply()`에 전달합니다.
- 보고서 초안 요청은 `agents/report_writer.py`로 연결합니다.

현재 `ChatPanel`의 스트리밍 요청은 서버에서 `welfare/service.py`로 연결됩니다. 이 파일의 함수는 기존 JSON 응답 방식과 호환되는 경로를 담당합니다.

## 질문 한 개를 따라가는 읽기 순서

```text
components.jsx의 ChatPanel.send()
       ↓
api.js의 streamWelfareChat()
       ↓
webapp/server.py의 /api/chat 처리
       ↓
welfare/service.py의 stream_reply()
       ↓
agent/orchestrator.py의 handle_chat()
       ├─ resources.py: 복지자료 검색
       └─ openai_client.py: AI 답변 요청
       ↓
답변 이벤트가 역방향으로 전달되어 말풍선 갱신
```

처음에는 모든 문법을 이해하려고 하기보다, 각 함수가 무엇을 받아서 어디로 넘기는지 따라가세요. “질문 입력 → 자료 검색 → 답변 생성 → 화면 표시”가 연결되면 파일들이 나뉜 이유도 이해하기 쉬워집니다.

## 추가 참고 파일

- `chatbot/welfare/README.md`: 복지 챗봇 실행 안내
- `chatbot/welfare/requirements.txt`: 필요한 Python 패키지
- `chatbot/tests/test_chat_test2.py`: 챗봇 검증 코드
- `docs/복지이음_교체_안내.md`: 팀 프로젝트 연결과 설정 안내
