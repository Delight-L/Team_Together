# WELFIND React 실행 안내

이 브랜치는 React + Vite 화면과 Python HTTP API를 사용합니다. Python 전처리·Analysis2·챗봇·사업 매칭·SQLite 업무 기록은 기존 모듈을 재사용합니다. 서버는 로컬 시연용이며 `127.0.0.1`에만 바인딩합니다.

## 폴더 구분

- `frontend/`: 현재 React 화면과 Vite 개발 서버
- `webapp/`: React용 Python HTTP API
- `shared/`: React와 기존 화면이 함께 사용하는 시연 계정, 보고서 생성, 지도 경계 데이터. Streamlit을 가져오지 않습니다.
- `legacy/streamlit_dashboard/`: 기존 Streamlit 화면, 전용 데이터, 컴포넌트, 검증 도구
- `db/`, `agents/`, `chatbot/`, `preprocessing/`: 기존 업무 저장·분석·AI·전처리 기능

현재 화면을 수정할 때는 `frontend/`와 `webapp/`를 확인하세요. 기존 Streamlit 비교 실행은 루트에서 `python main.py --streamlit`입니다. 공용 지도 파일은 `shared/data/map_boundaries.json`, 보고서 생성은 `shared/report.py`, 시연 계정은 `shared/accounts.py`입니다.

## 최초 설치

프로젝트 루트에서 Python 가상환경을 준비한 후:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
cd frontend
pnpm install --frozen-lockfile
pnpm run build
cd ..
.venv/Scripts/python.exe main.py
```

Node.js 22.12 이상을 권장합니다. 의존성 설치는 pnpm으로 통일합니다. pnpm으로 설치된 `node_modules`에서 `npm install`을 실행하면 `workspace:*` 오류가 발생할 수 있습니다. pnpm lockfile을 포함하며 esbuild의 설치 스크립트만 허용합니다. pnpm이 없다면 `npm install -g pnpm`으로 먼저 설치하세요.

브라우저에서 http://127.0.0.1:8503 을 엽니다. 강남구 시연 계정은 `gangnam01 / demo1234`, 관리자는 `admin / admin1234`입니다. 춘천시는 실제 Analysis2 자료 미연결 상태를 표시합니다. 시연 계정은 실제 서비스 인증이 아닙니다.

## 반드시 전달할 데이터

CSV는 Git에서 제외됩니다. 새 PC에는 아래 데이터를 같은 경로로 별도 전달하세요.

- `agents/regional_analysis/Analysis2/outputs/gangnam_analysis2_detection_2022_2025.csv` — 화면·챗봇에 직접 필요한 분석 결과
- `agents/regional_analysis/Analysis2/outputs/`의 나머지 분석 결과 CSV
- `preprocessing/regional_features/outputs/`의 기준 feature table과 결과 CSV
- `agents/regional_analysis/Analysis2/gangnam_analysis2_feature_table_2022_2025.csv`

원본 재생성이 필요하면 기존과 같이 `python main.py --preprocess --full`, `python main.py --analysis --no-download`를 실행합니다. 원본 ZIP/XLSX와 reference 자료가 필요합니다. 화면 실행 시 자동 전처리하거나 다운로드하지 않습니다.

## 개발 실행

터미널 1: 프로젝트 루트에서 `.venv/Scripts/python.exe main.py`

터미널 2: `frontend`에서 `pnpm run dev`

http://127.0.0.1:5173 에서 화면을 개발합니다. Vite가 API와 브랜드 이미지를 Python 서버(8503)로 전달합니다. 빌드 후에는 Python 서버 하나가 화면과 API를 함께 제공합니다. 프런트엔드 변경 후 빌드를 다시 실행하세요.

## 화면과 동작

- 종합 현황: 지도 대신 조사 파일 형태의 브리핑을 표시합니다. 상단 후보 집계, 선택 지역의 변화율·최근 6개월 실제 지표값 그래프, 오른쪽 지역별 파일 목록으로 구성합니다. PC 화면은 남는 높이에 맞춰 중앙 스크롤 없이 배치하고, 좁은 화면에서는 내용을 읽을 수 있도록 본문 스크롤을 허용합니다.
- 조사 파일은 후보를 우선해 7곳씩 표시하며 페이지 버튼으로 모든 지역을 볼 수 있습니다. 2024-04의 신규 6곳·연속 1곳은 첫 페이지에 모두 표시합니다. 월을 바꾸면 목록은 첫 페이지로 돌아가며, 지역 선택 상자로 고르면 해당 지역이 있는 페이지를 표시합니다.
- 그래프는 Analysis2 CSV의 원자료를 사용하며 단위(명/회)를 함께 표시합니다. 원자료 열이 없는 이전 업로드는 전월 변화율(%) 그래프로 전환하고, 누락 월은 선을 연결하지 않습니다. 시안의 예시 수치·지역 상태를 실제 데이터로 대체합니다.
- 지역 현황은 전체 동 검색·상태 필터·정렬과 지도 중심으로 구성합니다. 종합 현황의 ‘전체 근거 살펴보기’는 기존 지역 분석 화면으로 이동합니다.
- 지역 상세: 동 클릭 시 지도 내부 옆에 REGION INSIGHT가 열립니다. 선택 지역은 챗봇과 공유합니다. 로고를 클릭하면 메뉴를 접고 펼치며, 접힌 상태에는 보미 얼굴이 표시됩니다.
- 챗봇: chat_test2/backend/app의 코드 파일을 chatbot/welfare/app으로 가져와 원본 handle_chat을 사용합니다. 팀 채팅 패널에서 복지사업 검색, 출처 펼치기, 새 대화, 응답 중지를 제공합니다. 지도/분석과 선택 지역을 공유하며 지역·월 변경 시 이전 요청을 취소하고 대화를 초기화합니다. 기준월은 분석 기준이며 사업 운영 시점이나 자료 연도와 다릅니다.
- 보미 캐릭터: 평소에는 정지 이미지, 답변 처리 중에는 동작 GIF를 표시합니다. 사용자 OS의 동작 줄이기 설정을 따릅니다. 복지이음은 OpenAI 모드에서 실제 토큰 스트리밍을 사용합니다.
- 브리핑의 ‘AI에게 질문하기’는 선택 지역·기준월·실제 지표를 담은 질문을 챗봇 입력창에 준비합니다. 사용자가 전송해야 AI를 호출합니다.
- 업무: 분석 확인 저장 → 근거 검토 완료 → 실제 DB2 사업 조회·검토 기록 → Word 초안 생성·다운로드 확인 → 최종 저장. 기존 SQLite의 단계 검증을 재사용합니다.
- 업무 현황: 담당자의 저장된 지역·월별 업무를 다시 열어 진행합니다. 챗봇 안의 진행 영역은 제거하고 독립 메뉴로 제공합니다.
- 관리자 데이터: CSV/XLSX 검사·미리보기·DB1 반영, DB1 활동 이력 조회를 연결했습니다. DB1 반영은 화면에 사용하는 저장소 CSV를 자동 교체하지 않습니다.
- 복지이음은 루트 `.env`의 `OPENAI_API_KEY`, `OPENAI_MODEL`을 사용합니다. 키가 없으면 예시 질문과 자유 질문 모두 로컬 JSON 자료를 검색해 안내합니다. 키가 있으면 검색 자료와 대화를 OpenAI에 보내 스트리밍 답변을 생성합니다. AI 실패 시 자료 안내로 전환합니다. 현재 운영·자격·모집은 담당 기관 확인이 필요합니다. 복지이음은 DB2를 직접 조회하지 않으며 기존 사업 검토 메뉴의 DB2 연결은 별도로 유지합니다. [복지이음 설정 안내](docs/복지이음_교체_안내.md)를 확인하세요.

## 전환 범위

기존 기본 메뉴의 React 메인 화면·지역 분석·업무 현황·사업 검토·보고서·챗봇·관리자 데이터 반영·DB1 활동 이력을 연결했습니다. 별도 도구의 전년 동월 현장 대응 화면은 기본 메뉴와 별개이며 이 React 화면에 포함하지 않습니다. 비교용 기존 Streamlit 화면은 `python main.py --streamlit`로 실행할 수 있습니다. 원본 Streamlit 브랜치는 변경하지 않습니다.

기존 업무 저장 DB는 `db/runtime/mission_records.sqlite3`이며 Git에서 제외합니다. 새 PC에서 개인 업무 기록이 필요하면 별도 전달하세요. React 챗봇 대화는 화면 세션 안에서만 유지되며 업무 질의 기록으로 자동 저장하지 않습니다.

공유 상태 설계는 [React 공식 문서](https://react.dev/learn/sharing-state-between-components)를 따릅니다.

팀원이 수정할 위치와 오류 확인 순서는 [React 팀원 수정 가이드](docs/React_팀원_수정_가이드.md)에 정리했습니다. 핵심 파일에 한국어 설명 주석을 넣었습니다.

## 검증

```powershell
cd frontend
node --test tests/briefing.test.mjs tests/check-map-data.mjs tests/mission-map.test.mjs
pnpm run build
cd ..
.venv/Scripts/python.exe -m unittest discover -s webapp/tests -v
```

API 검사는 실제 분석 CSV를 읽고 임시 SQLite DB에서 로그인·지역 접근·복지이음 JSON/SSE 응답·업무 순서·Word 초안과 최종 저장을 검사합니다. DB2 경계는 테스트 사업으로 대체하며 실제 DB 쓰기와 외부 AI 호출은 하지 않습니다.

