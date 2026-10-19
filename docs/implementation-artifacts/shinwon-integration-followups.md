# shinwon 챗봇 병합 후속 수정 항목

2026-10-19, main 2b34991 + shinwon 5fdf730 병합. 사용자는 아래 알려진 문제를 후속 보완하는 조건으로 우선 반영을 승인했다.

- 질문 분류: `외로움 해소 지원사업 추천해 줘`가 복지사업 검색 대신 서울서베이 설명으로 간다. `다른 지표`, `탐지월` 같은 단어만으로 고정 설명을 선택하지 않도록 질문 목적과 이전 대화를 확인할 것.
- 전체 사례: `탐지가 9건인데 왜 이것만 나와?`는 동 제한만 해제하고 현재 연령을 유지한다. main의 동×연령 사례 목록과 조회 범위를 맞출 것.
- 전월 탐지: 여러 동의 결과를 받아도 최신 한 행만 설명한다. 여러 동을 명시한 질문에는 동별 결과를 유지할 것.
- 설문 분류: `no_support3_and_lonely_outside`가 일반 도움 관계 분류에 먼저 걸린다. 복합 지표 일치 검사를 먼저 할 것.

충돌 해결: answer_generator.py와 query_service.py에서 shinwon의 자동 연령 설명/부가 조회 제거 의도를 적용하고 나머지 main 변경은 유지했다. 명시적인 연령별 조회는 유지한다. BomiChat에는 문단 구분만 합쳐 main의 대화 유지·대화 기준 표시·사업 이동 기능을 보존했다.

검증: group_workspace_regression.py와 기존 로컬 test_context_period_matching.py 합계 13개 통과, 변경 Python 파일 구문 검사 통과, Vite production build 통과, git diff --check 통과. 실제 배포 UI/API, 외부 AI 및 공유 DB의 운영 동작은 이번 병합 검증에 포함하지 않았다.
