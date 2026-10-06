# 입력 가드레일 적용 안내

모델: `omni-moderation-latest` / API: `client.moderations.create`.

1. 압축을 풀고 프로젝트 폴더에서 `pip install -r requirements.txt`를 실행합니다.
2. 프로젝트 루트 `.env`에 `OPENAI_API_KEY=실제키`를 추가합니다. 기존 Gemini 키는 그대로 유지합니다. 키를 채팅으로 보내지 마세요.
3. 기존 실행 명령으로 챗봇을 시작합니다.

질문 → 기존 입력 규칙(개인 명단·비밀정보·길이·연도) → OpenAI Moderation → 목적 해석 → 데이터 조회와 Gemini 답변 → 기존 수치·근거 검증.

한국어 원문을 그대로 검사합니다. 영어 데이터셋 다운로드나 별도 모델 학습은 필요하지 않습니다. Gemini 답변에 Moderation API를 호출하지 않습니다. Moderation은 유해 콘텐츠 검사이며 업무 범위·권한·프롬프트 공격을 모두 해결하지 않으므로 기존 검사를 유지합니다.

`flagged=True`이면 일반 답변 생성을 중단합니다. 자해 관련 분류에는 안전 안내를 제공합니다. 키 누락·연결 오류·10초 타임아웃·잘못된 응답도 일반 답변을 중단하고 검사 실패 안내를 표시합니다. 질문, API 키, API 오류 원문은 로그에 남기지 않습니다. 검사 시 사용자 질문은 OpenAI API로 전송됩니다.

변경 파일: chatbot_agent/content_moderation.py, chatbot_agent/orchestrator.py, requirements.txt, .env.example, .gitignore. 기존 guardrails.py와 answer_validator.py는 유지합니다.

검증: 모의 API를 사용한 통과·차단·자해 안내·키 누락·오류·후속 단계 차단 테스트. 실제 OpenAI API 호출과 한국어 분류 정확도 평가는 API 키 없이 검증하지 않았습니다. 키 설정 후 실제 한국어 질문으로 확인해야 합니다.

공식 문서: https://developers.openai.com/api/docs/guides/moderation?api-mode=responses
