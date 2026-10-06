# 지역 변화 신호 챗봇 version11 개선판

실행:

```bash
python chatbot_agent/main.py
```

세 가지 업무 목적과 예시 질문은 실행 직후 한 번만 표시됩니다. 이후에는 `추가 질문>` 입력창만 반복됩니다. 분석 계산 과정은 사용자가 분석 과정이나 선정 근거를 물었을 때만 답변에 포함됩니다.

처리 구조는 다음 파일로 나뉩니다.

1. `guardrails.py`: 빈 입력·기간·개인 정보 요청 등 입력 검사
2. `intent_parser.py`, `menu.py`: API가 없을 때의 최소 목적·조건 해석
   - `llm_intent_resolver.py`: 자연어 질문을 목적·행정동·기간·신호 조건의 조회 계획으로 해석합니다. `하반기` 같은 기간 표현도 LLM이 실제 데이터 기간을 보고 YYYY-MM 범위로 바꿉니다.
   - `conversation_memory.py`, `query_planner.py`: 직전 조회의 대상·기간·신호를 보존하고, 생략된 후속 질문을 보완한 뒤 실제 데이터 범위를 검증합니다.
3. `repository.py`, `query_service.py`: 정확한 CSV 조회
   - `explanation_guide.md`, `explanation_retriever.py`: 신호 수치의 쉬운 설명 기준을 검색하는 설명 전용 RAG
   - `knowledge_retriever.py`, `answer_generator.py`: 분석 방법·설명 기준과 실제 조회 수치를 결합해 답변 생성
4. `answer_validator.py`: 근거를 넘는 해석과 과도한 표현 검토
5. `orchestrator.py`: 네 단계를 순서대로 연결

숫자·집계·신호 판정은 Python이 처리합니다. Gemini API 키가 설정되면 LLM이 자연어의 의도와 대화 맥락을 읽어 조회 계획을 만들고, 조회 결과를 쉬운 말로 다시 표현합니다. 키가 없으면 최소 규칙 기반 템플릿 답변으로 동작합니다.

API 키는 `chatbot_agent/api_key.txt`에 한 줄로 넣을 수 있습니다. 파일 이름이 실제로 `api_key.txt`인지 확인하세요. Windows에서 확장자 숨김을 켠 경우 `api_key.txt.txt`로 저장되지 않도록 주의합니다.

주요 데이터는 `Analysis2/outputs`와 Analysis1 최종 지역유형 파일입니다. 동별 전체 집계는 CSV 전체를 코드로 조회하므로 파일 일부 행만 LLM에 전달하는 기존 방식의 누락 문제를 줄였습니다.
