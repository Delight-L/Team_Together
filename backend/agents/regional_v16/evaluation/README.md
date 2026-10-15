# v16 답변 평가 실행기

팀투게더 메인 프로젝트의 지역 변화 분석 챗봇을 평가합니다. 현재 데이터셋은 B01~B32의 32개이며 경로별 8개입니다. 한 사례에는 여러 대화·화면 선택 단계가 있을 수 있습니다.

## 이전 결과 정정

2026-10-14의 64개 실행은 선행 대화와 화면 선택 단계를 버린 실행기에서 생성됐습니다. 당시 정답률과 유사도 평균은 챗봇 최종 성능으로 사용하지 않습니다. 기존 결과와 사용자 리뷰는 비교 자료로 보존합니다. 해시만 변경한 가져오기도 근거 검증이 아니었으며 `import_dataset.py`는 사용 중지했습니다.

## 실행

```powershell
cd "C:\Users\user\Desktop\together project\Team_Together\Team_Together-main"
.venv\Scripts\python.exe agents\regional_analysis\chatbot_v16\evaluation\prepare_dataset32.py
.venv\Scripts\python.exe agents\regional_analysis\chatbot_v16\evaluation\validate_dataset.py agents\regional_analysis\chatbot_v16\evaluation\datasets\v16_questions_32.jsonl
.venv\Scripts\python.exe agents\regional_analysis\chatbot_v16\evaluation\run_eval.py agents\regional_analysis\chatbot_v16\evaluation\datasets\v16_questions_32.jsonl --output-dir agents\regional_analysis\chatbot_v16\evaluation\results
```

준비 도구는 별도 원본 폴더의 데이터셋·스냅샷을 읽고 메인 DB와 비교합니다. 준비 이후에는 검증된 32개 파일로 평가합니다. 메인 DB가 변경되면 답안 근거를 다시 확인해야 합니다.

## 평가 조건과 범위

- 사례마다 문맥을 초기화하고 `steps`를 순서대로 실행합니다.
- 후속 질문에는 실제 선행 답변을 전달하며, 모범답안을 대화 기록으로 넣지 않습니다.
- 화면 선택은 동·기준월·연령을 전달하여 자동 설명을 실행합니다.
- 마지막 `score_target` 응답을 채점하고 선행 단계도 기록합니다.
- 기본 모드는 외부 AI 호출 없는 DB/규칙 기반 평가입니다. AI를 사용하는 서비스 설정의 성능과 같다고 주장하지 않습니다.
- 서비스 및 대시보드 구성요소를 통한 내부 평가입니다. 브라우저 클릭, 메인 `/api/chat` HTTP 연결, 캐시·revision까지 검증한 UI 종단간 테스트가 아닙니다.

BLEU·ROUGE는 표현 유사도입니다. 정답은 질문 의도, 조건, 사실·수치, 과도한 단정 여부로 판단합니다. 질문에 요구되지 않은 부가 정보 누락만으로 오답 처리하지 않습니다. 에이전트 판정과 사용자의 휴먼 리뷰를 구분합니다. DB 검증 상세는 `DATASET32_DB_AUDIT.md`와 `.json`을 참조하세요.
