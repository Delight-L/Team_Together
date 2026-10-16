# bomi — 보미 챗봇 코어

`backend`에서 챗봇만 새로 구성한 패키지입니다. 흐름 전체는 [CHAT_FLOW.md](../CHAT_FLOW.md)를 보세요.

```
bomi/
├─ pipeline.py     요청 → 이벤트 스트림 (안전 검사 → 담당 선택 → 에이전트 → done)
├─ routing.py      담당 선택 (고정 규칙 → AI → 키워드 규칙)
├─ regularization.py 규칙·moderate API를 에이전트별 Policy로 적용 (입력·출력 규제)
├─ events.py       프론트엔드와 맺은 이벤트 9종 계약, seal
├─ request.py      ChatRequest·GroupSelection·입력 검증
├─ questions.py    질문 분류 함수와 키워드 목록
├─ phrases.py      고정 문구, AI 담당 선택 지시문
├─ aio.py          동기↔비동기 변환 (asyncio.run을 여기서만 호출)
├─ agents/         region_analysis · welfare · report · guide
├─ adapters/v16.py v16 엔진 어댑터
└─ tests/          이벤트 계약·라우팅·파이프라인·에이전트 테스트
```

## 새 에이전트를 추가하려면

1. `agents/`에 `RegulatedAgent`를 상속한 클래스를 만들고 `id`, `policy`, `answer(request) -> Iterator[Event]`를 정의합니다. 입력 규제는 `respond()`가 해 주고, `done`·`route`는 보내지 않습니다.
2. 한 번에 완성되는 답이면 `self.deliver(Reply(...))`(출력 규제 포함)를 쓰고, 스트리밍이면 `events.token(...)`을 `yield`하며 끝에서 `self.regulator.output_flagged_async`로 검사합니다.
3. `agents/__init__.py`의 `default_agents()`에 등록합니다.
4. `phrases.AGENT_LABELS`와 `ROUTER_PROMPT`에 이름과 설명을 추가하고, 키워드 규칙이 필요하면 `routing.Router.by_rules`에 둡니다.
5. `tests/test_routing.py`에 예시 질문을 추가합니다.

## 규칙

- 담당 선택은 `routing.py`에서만 합니다. 자료 유무 같은 사정은 에이전트 안에서 처리합니다.
- 입력·출력 규제는 `regularization.py`의 `Policy`로 선언합니다. 규칙(정규식·단어)의 정의는 `chatbot/guardrails.py`에 있습니다.
- AI 호출은 `chatbot/welfare/app/llm/client.py`의 `llm`만 쓰고, 동기 코드에서는 `aio.run`/`aio.iterate`를 거칩니다.
- 이벤트 이름·내용을 바꾸면 화면이 깨집니다. `events.py`를 바꾸기 전에 `BomiChat.jsx`를 함께 확인하세요.

## 테스트

```bash
python -m unittest discover -s backend/bomi/tests -t .
```
