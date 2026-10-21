# 개발 안내

화면에서 한 가지 행동을 고른 뒤 실행 시작점 → API → 보미 → DB 조회 순서로 따라갑니다.
설치와 첫 실행은 [프로젝트 README](../README.md#13-실행-방법), 분석·게시 절차는
[데이터 운영 안내](data-operations.md)를 참고하세요.

## 폴더 구성

화면은 `frontend/`, 웹 서비스는 `backend/`, 데이터 준비·분석은 `pipelines/`에서 작업합니다.

```text
Team_Together/
├─ frontend/                 React 화면
├─ backend/
│  ├─ api/                   HTTP API·로그인·관리자·업무·대화 요청
│  ├─ bomi/                  챗봇 흐름·담당 선택·안전 검사·에이전트
│  ├─ chatbot/               공용 AI 설정·가드레일·AI 연결
│  │  └─ welfare/app/dialogue/  복지사업 검색·근거 표현
│  ├─ agents/                보고서 작성·사업 매칭
│  │  └─ regional_analysis/       지역 변화 엔진·계산·평가 기록
│  ├─ db/                    공유 DB 연결·조회·저장
│  ├─ services/              계정·Word 보고서 생성
│  └─ resources/             지도 자료·보고서 서식
├─ pipelines/
│  ├─ db1/                   Analysis1·2·3·맥락 분석·검증·모델
│  ├─ preprocessing/         공통 전처리·재현 코드
│  ├─ regional_analysis/     --analysis 실행점(DB1 파이프라인 호출)
│  ├─ risk_analysis/         별도 위험변화 분석 도구
│  └─ welfare/               DB2 복지사업 수집
├─ data/                     공통 원자료·가공 자료
├─ assets/brand/             로고·캐릭터·브랜드 원본
│  └─ source/                화면에서 직접 쓰지 않는 CI·브랜드 보드·가이드 원본
├─ docs/                     팀 문서·아키텍처·외부 참고자료·과거 안내(history/)
├─ scripts/                  실행·이관·정기 수집 도구
├─ deploy/                   배포 설정
├─ runtime/                  로컬 실행 로그
└─ main.py                   공통 실행 시작점
```

## 처음 읽을 파일

| 순서 | 파일 | 먼저 확인할 내용 |
|---|---|---|
| 1 | [main.py](../main.py) | 실행 옵션에 따라 웹 서버 또는 분석 도구를 고르는 부분 |
| 2 | [API 서버](../backend/api/server.py) | 요청 경로를 어느 처리 함수로 보내는지 |
| 3 | [채팅 요청](../backend/api/routes_chat.py) | 화면에서 보낸 질문·선택 지역·기간을 받는 부분 |
| 4 | [보미 파이프라인](../backend/bomi/pipeline.py) | 입력 검사 → 담당 선택 → 답변 → 종료 흐름 |
| 5 | [지역 분석 담당](../backend/bomi/agents/region_analysis.py) | 지역 분석을 어떤 조건에서 실행하는지 |
| 6 | [지역 분석 연결](../backend/bomi/adapters/regional_analysis.py) | 질문과 화면 정보를 지역 분석 엔진에 전달하는 부분 |
| 7 | [저장소 계약](../backend/agents/regional_analysis/chatbot_agent/db1_repository.py) | DB 조회 함수가 무엇을 받고 무엇을 돌려주는지 |
| 8 | [공통 DB 조회](../backend/agents/regional_analysis/chatbot_agent/repository.py) | SQL 결과를 표로 바꾸고 지역·기간·신호로 거르는 부분 |

게시된 지역 분석 자료 유무에 따라 실제 조회 구현은 `pg_repository.py` 또는
`dashboard_repository.py`로 이어집니다. 모든 질문이 공통 DB 조회 파일을 거치는 것은 아닙니다.
분석 수식을 공부할 때는 [DB1 안내](../pipelines/db1/README.md)를 별도로 읽습니다.

## 공통 DB 조회 파일을 읽는 방법

1. `connection()`: `with` 블록에 DB 연결을 제공합니다. 중간에 오류가 나도 조회 중첩 횟수를 되돌립니다.
2. `_cached()`: 같은 공개본에서 같은 자료를 요청하면 이전 결과를 재사용합니다.
3. `_load_frame()`: DB의 JSON을 pandas 표(`DataFrame`)로 바꿉니다.
4. `activity()`: 동과 기간으로 자료를 선택합니다.
5. `signals()` / `age_signal_cases()`: 신호가 확인된 행만 남깁니다. 미확인은 신호로 세지 않습니다.
6. `supplements()`: 소비·날씨·설문 같은 보조 맥락을 모으고 자료의 기간 차이를 표시합니다.

`_`로 시작하는 이름은 이 파일 내부에서 쓰는 보조 함수·값이라는 관례입니다.
`DataFrame.loc[조건]`은 조건에 맞는 행을 고르고, `.copy()`는 원본을 바꾸지 않도록 복사합니다.
`yield`는 값을 하나씩 전달하며, `with`는 블록 종료 시 정리 작업도 실행하게 합니다.
`RLock`과 `contextmanager`는 연결 수명·동시 요청 처리를 위해 필요하므로 역할을 이해한 뒤 수정합니다.

## 화면 코드를 읽는 순서

| 순서 | 파일 | 확인할 흐름 |
|---|---|---|
| 1 | [main.jsx](../frontend/src/main.jsx) | React 화면 시작과 공용 CSS 연결 |
| 2 | [App.jsx](../frontend/src/App.jsx) | 로그인·메뉴·지역 선택 상태, 사업 검토·보고서 화면 연결 |
| 3 | [api.js](../frontend/src/api.js) | 서버 조회·저장, 보미 답변 스트림 받기 |
| 4 | [linkedSelection.mjs](../frontend/src/linkedSelection.mjs) | 지역·연령 선택 유지, 선택한 그룹의 탐지 시점 찾기 |
| 5 | [useDraft.js](../frontend/src/useDraft.js) · [draftStore.mjs](../frontend/src/draftStore.mjs) | 메뉴를 옮겨도 입력 중인 초안 보관 |
| 6 | [experienceLogic.mjs](../frontend/src/experienceLogic.mjs) | 보고서 수치·출처·검토 전 문구 점검 |

`props`는 부모가 전달하는 값·함수입니다. `useState`는 화면에서 바뀌는 값을 관리하고,
`useEffect`는 조회·이벤트 등록 같은 작업을 실행합니다. 이벤트를 등록한 effect는 반환한 함수에서 해제합니다.
`.mjs`는 화면을 직접 그리지 않는 JavaScript 계산·선택 함수, `.jsx`는 JSX 화면 코드를 포함하는 파일입니다.
`map`은 각 값을 바꿔 새 목록을 만들고, `filter`는 조건에 맞는 값만 남기며,
`find`는 처음 맞는 값 하나를 찾습니다. `?.`는 앞의 값이 없으면 조회를 멈춥니다.

## 분석 코드를 읽는 순서

분석 실행은 웹 요청과 분리되어 있습니다. 먼저 [DB1 실행기](../pipelines/db1/run_db1.py)에서
어느 분석을 부르는지 확인하고, 해당 분석의 전처리 → 계산 → 저장 순서로 읽습니다.
지역 유형의 기준 모델은 [baseline.py](../pipelines/db1/Analysis1/analysis/baseline.py),
새 기간의 비교는 [change_detector.py](../pipelines/db1/Analysis1/analysis/change_detector.py)입니다.

- `feature_frame`: 분석에 넣을 특성을 열로 정리한 표입니다.
- `balanced_frame` / `balanced_features`: 영역별 가중치를 적용한 표입니다.
- `clusters`: 각 동의 지역 유형 결과입니다.
- `bundle`: 표준화·PCA·군집 모델과 기준 자료를 함께 보관한 묶음입니다.

PCA는 여러 관련 열을 적은 수의 축으로 요약합니다. 새 기간을 비교할 때는 저장된 기준 모델로
변환하고 분류합니다. 기준 모델을 다시 학습하는 작업과 새 기간에 같은 모델을 적용하는 작업을 구분합니다.
`df`는 pandas 표를 뜻하는 관례이고, `row`는 그중 한 행입니다. 정렬·열 순서·결측값 처리는 계산 결과에 영향을 줍니다.

## 가독성 기준

- 한 줄에 여러 문장을 `;`로 연결하지 않습니다.
- 조건문·예외 처리의 실행문은 다음 줄에 씁니다.
- `frame`, `row`, `quarter`처럼 값의 역할이 보이는 이름을 씁니다.
- 한 표현식에 조회·필터·정렬을 모두 넣기보다 중간 결과를 이름으로 설명합니다.
- 함수 설명에는 역할, 중요한 입력·출력, 자료 해석의 주의점을 적습니다.
- 주석은 문법을 그대로 읽어 주기보다 처리 이유와 데이터 경계를 설명합니다.
- 계산 기준·SQL 조건·정렬·결측값 처리·기존 함수 호출 규약은 별도 기능 변경 없이 유지합니다.
- 클래스를 없애거나 파일을 쪼개는 일은 호출부와 공유 상태를 확인한 뒤 결정합니다.

## 실행과 수정 후 확인

Python 환경과 루트 `.env`를 준비한 뒤 프로젝트 루트에서 실행합니다.

```powershell
cd frontend
npm ci
npm run build
cd ..
python main.py
```

별도 터미널에서 정적 검사를 실행합니다.

```powershell
python scripts/audit_repository.py
git diff --check
```

원자료 전처리는 `python main.py --preprocess-analysis1 --raw-dir pipelines/preprocessing/regional_types/raw_data`입니다.
분석·수집 명령은 DB나 산출물을 변경할 수 있으므로 [데이터 운영 안내](data-operations.md)와
[DB2 수집 안내](DB2_지자체복지_정기수집.md)에서 읽기·쓰기 범위를 확인합니다.
정적 검사와 빌드만으로 실제 DB 결과·챗봇 답변·브라우저 동작 전체를 보증하지 않습니다.
변경한 함수의 기존 테스트나 변경 전후 결과 비교를 함께 수행합니다.
Git 제외인 로컬 테스트는 별도로 보관한 환경에서만 사용할 수 있습니다.

## 파일과 설정 보존 기준

- 루트 `.env`, `.venv/`, `frontend/node_modules/`를 사용합니다. 비밀번호와 API 키는 문서에 복사하지 않습니다.
- `backend/db/`는 공유 DB 조회·저장 코드, `pipelines/db1/`은 분석 결과를 만드는 코드입니다.
- 분석 원자료·모델·출처·라이선스·평가·검증 결과는 사용 목적을 확인하고 보존합니다.
- 실제 브랜드 이미지는 `assets/brand/`, 보관 원본은 `assets/brand/source/`에 둡니다.
- `.tmp/`에는 DB 덤프·백업·설정·복구 기록이 있으므로 폴더 전체를 삭제하지 않습니다.
- 관리자 AI 설정은 PostgreSQL `work.app_settings`에 저장합니다.
- `TEAM_TOGETHER_DATA_ROOT`는 저장소와 같은 자료 배치를 가진 기준 폴더입니다.
- 파일 제거 전 화면·서버·실행 도구·문서의 참조와 독립 실행 진입점을 확인합니다.

과거 폴더 이동·가독성 비교·로컬 압축본 위치는 [코드 정리 기록](history/repository-cleanup-2026-10-19.md),
지역 분석 엔진의 이름 변경은 [2026-10-20 기록](history/repository-cleanup-2026-10-20.md)을 참고하세요.
전체 소스의 문장 배치·변수명 정리와 최종 비교 결과는 [2026-10-21 기록](history/repository-cleanup-2026-10-21.md)에 있습니다.

## 문서 관리

README는 프로젝트 진입점과 주요 작업 영역에 둡니다. 현재 기능 설명은 주제별 문서 한 곳에 모으고
나머지 문서에서는 링크로 연결합니다. 날짜별 변경·검증 수치는 `docs/history/`에 보존합니다.
분석별 상세 문서·원자료 출처·평가 결과는 해당 분석 폴더에서 유지합니다.
문서 목차는 [문서 안내](README.md)에서 관리합니다.
