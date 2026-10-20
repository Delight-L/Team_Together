# WELFIND · 사회적 고립 위험신호 탐지 AI Agent

> **2026 빅콘테스트 · AI데이터 활용 분야 | SeSAC 08 최종프로젝트 | TEAM_TOGETHER | 이환희, 박신원, 조형우, 최도인**
>
> 지역과 인구집단의 행동 변화를 분석하고, 담당자가 근거 확인 → 복지사업 검토 → 보고서 작성으로 이어갈 수 있도록 돕는 웹 서비스입니다.

https://wel-find-ai.onrender.com/

통신·소비·공공자료에서 지역 단위의 변화를 찾고, 대시보드와 보미 챗봇으로 분석 근거와 지원자원을 확인합니다. 현재 분석·서비스 연동의 중심은 **강남구 22개 행정동**입니다. 다른 지역의 화면·지도 제공 여부와 실제 분석자료 보유 범위는 구분합니다.

**개인의 고립 여부나 복지사업 자격을 판정하지 않습니다.** 집계자료의 위험신호는 현장 확인과 지원 검토를 위한 후보이며, 최종 판단은 담당자가 합니다. 기관 연락과 지원 승인은 자동으로 수행하지 않습니다.

[설치·실행](#실행-방법) · [주요 기능](#주요-기능과-업무-흐름) · [데이터 구성](#데이터와-분석-기준) · [개발 안내](docs/development-guide.md) · [전체 문서](docs/README.md) · [Render 배포](deploy/render.md)

## 주요 기능과 업무 흐름

```text
종합 현황·지역 현황에서 변화 확인
    → 분석 확인 저장 → 근거 검토 완료
    → 사업 매칭 검토 → 보고서 작성·저장
```

화면을 조회하거나 메뉴를 이동하는 것만으로 검토가 완료되지는 않습니다. 담당자가 근거와 검토 내용을 확인하고 명시적으로 저장합니다.

| 화면 | 주요 기능 |
|---|---|
| 종합 현황 | 월별 변화 요약과 연령·성별 관찰 그룹 확인 |
| 지역 현황 | 동별 판정 표·지도에서 지역 선택과 근거 확인 |
| 지역 분석 | 지표별 상세 근거·추이, 기간·지역 비교, 분석 확인과 근거 검토 |
| 사업 매칭 검토 | 복지사업 후보 조회, 조건·기관 확인, 검토 기록 저장 |
| 보고서 작성 | 분석 지표·사업 선택, 초안 편집, 미리보기, Word 저장·다운로드와 저장 이력 조회 |
| 보미에게 질문 | 화면 맥락을 바탕으로 분석 설명·복지사업 검색·보고서 초안·업무 안내 |
| 관리자 메뉴 | 데이터 검사·반영·활동 이력, 외부 AI 사용 설정 |

보고서는 사업 검토 기록 없이도 분석·현황만으로 작성할 수 있습니다. 보미의 대화 기반 초안과 최종 보고서 저장 절차는 [보고서 작성 안내](docs/report-guide.md)를 참고하세요.

## 시스템 아키텍처

![자료에서 담당자 검토까지 이어지는 WELFIND 시스템 아키텍처](docs/architecture/system_architecture.png)

[고해상도 PNG](docs/architecture/system_architecture.png) · [편집 가능한 SVG](docs/architecture/system_architecture.svg) · [그림 안내](docs/README.md#architecture)

- **분석 파이프라인**이 통계·ML로 수치와 변화 신호를 만듭니다.
- **PostgreSQL**이 분석 작업, 서비스 자료, 복지자료, 업무 기록을 스키마별로 관리합니다.
- **React 화면과 Python API**가 조회·검토·저장을 연결합니다.
- **보미**가 자료를 검색하고 근거를 설명합니다. 외부 AI는 선택 기능이며 기본 꺼짐입니다.

## 데이터와 분석 기준

### DB1 · 지역·인구집단 분석

기본 분석 단위는 **지역 × 연령집단 × 시간**이며, 자료에 따라 성별을 함께 구분합니다. 통신 유동인구·통화·문자·이동 자료와 카드 소비, 인구·가구·설문 등 공공자료를 사용합니다. 자료별 공간 단위와 관찰 기간이 다르므로 같은 단위의 자료처럼 해석하지 않습니다.

| 분석 | 방법 | 활용 |
|---|---|---|
| Analysis1 · 지역 유형 | `StandardScaler → PCA → KMeans`, 고정 모델 `analysis1_2025H2_elder_v2` | 동별 지역 배경과 유형 비교 |
| Analysis2 · 변화 탐지 | 동별 월 변화에서 강남구 공통 변화를 뺀 잔차를 과거 중앙값·MAD로 표준화하는 robust z | 평소와 다른 감소 신호, 신규·연속·변화 후보 확인 |
| Analysis3 · 소비 맥락 | 소비영역별 과거 동일 분기·전월 대비 기술 통계 | 이동·통신 변화의 보조 맥락 |

지역 유형의 배경 지표인 **독거노인 비율**은 2025년 연간 독거노인 수를 같은 해 4분기 65세 이상 등록인구로 나눈 값입니다. 월별 고립률이나 개인의 고립 여부를 뜻하지 않으며, 공개 시점이 확인되지 않은 사후 배경자료입니다.

위험신호 수치와 점수는 Python 분석으로 계산합니다. LLM이 위험점수를 산출하지 않으며, 고립 여부의 정답(label)을 이용한 지도학습 예측이나 딥러닝 모델은 사용하지 않습니다. 상세 입력·모델·검증 기준은 [DB1 분석 안내](pipelines/db1/README.md)를 참고하세요.

### DB2 · 복지사업·지원자원

| 자료 | 기본 조회 위치 | 활용 |
|---|---|---|
| 공공 API로 수집한 지자체 복지사업 | PostgreSQL `db2.local_welfare_services` 등 | 사업 매칭 검토 |
| 팀 정리 복지사업·강남구 정책 자료 | PostgreSQL `db2.chatbot_policy_*` | 보미 복지사업 안내 |

`backend/chatbot/welfare/data/*.json`은 팀 자료의 적재 원본과 명시적인 오프라인 검증용입니다. 보미의 기본 복지자료 조회는 공유 DB2를 사용합니다. 수집·적재 방법은 [DB2 정기 수집](docs/DB2_지자체복지_정기수집.md)과 [복지사업 검색 안내](backend/README.md#welfare)를 참고하세요.

### 저장소와 화면 자료

| 영역 | 저장소·자료 | 역할 |
|---|---|---|
| 분석·전처리 작업 | PostgreSQL `db1_pipeline` | 원자료 전처리와 분석 작업 |
| 서비스 분석 | PostgreSQL `db1`, 지역 분석 게시 뷰 `db1_v16` | 동별 탐지·지역 유형·집단별 집계·게시된 지역 분석 근거 |
| 지역 배경·소비·설문 | `data/processed/region_insights.json`, `survey_dashboard.json` 등 | 화면의 보조 맥락 |
| 업무·보고서·설정 | PostgreSQL `work` | 검토 기록·보고서 파일과 버전·관리자 AI 설정 |
| 과거 자료 보존 | PostgreSQL `db1_regional_archive` | 이전 작업 자료·원문·해시 보존 |

분석·전처리·서비스의 DB 저장소는 PostgreSQL입니다. 원천 CSV·XLSX와 모델 파일은 별도로 필요합니다. **분석 실행과 서비스 반영·활성화는 별도 단계**이며, 분석만 실행한다고 화면 자료가 자동으로 바뀌지 않습니다.

대시보드 분석자료는 `WELFIND_DATA_SOURCE=auto`이면 DB 우선·실패 시 전달 CSV, `db`이면 DB만, `csv`이면 전달 CSV를 읽습니다. 이 설정은 업무 저장과 복지자료까지 오프라인으로 전환하지 않습니다. 게시된 지역 분석 자료가 없으면 보미는 대시보드와 같은 DB1 조회 경로와 전달 CSV를 활용합니다.

스키마 경계·원자료 갱신·검사·반영·복원은 [데이터 운영 안내](docs/data-operations.md)에서 관리합니다.

## 보미 챗봇

보미는 모든 메뉴에서 같은 채팅으로 질문을 받습니다. `backend/bomi`의 담당 선택기가 질문과 화면 맥락(지역·기준월·그룹)에 맞는 에이전트를 고릅니다.

```text
질문 + 화면 맥락
    → 입력 검사·개인정보 마스킹
    → 담당 선택: 고정 규칙 → AI(사용 시) → 키워드 규칙
    → 담당별 자료 조회·답변·출력 검사
    → 출처와 근거를 포함한 답변
```

| 담당 | 하는 일 |
|---|---|
| 지역 분석 | 동·연령·성별 그룹의 변화 근거, 탐지 기준, 화면 판정 용어 설명 |
| 복지사업 | DB2에서 관련 사업·대상·이용 조건·담당 기관 검색 |
| 보고서 작성 | 대화 또는 저장된 분석·사업 검토를 바탕으로 담당자 검토 전 초안 작성 |
| 보미 안내 | 검토 의견·현장 확인·보고서 작성 등 업무 방법 안내 |

외부 AI를 끄면 자료 검색과 규칙 기반 근거 안내로 동작합니다. 켜려면 관리자가 제공사와 키를 설정하고 사용을 허용한 뒤, 사용자가 보미의 AI 스위치를 켭니다. OpenAI·Anthropic Claude·Google Gemini를 지원하며, 보고서의 AI 문장은 기초 초안과 대조하고 근거에 맞지 않으면 기초 초안을 사용합니다.

[보미 사용·설정 안내](backend/README.md#bomi) · [보미 구조](docs/bomi-architecture.md) · [보고서 근거 대조](docs/report-guide.md)

<a id="13-실행-방법"></a>

## 실행 방법

### 준비

- **Python 3.12** 권장(Docker 실행 환경 기준), **Node.js 22.12 이상**, npm
- PostgreSQL 접속 정보와 필요한 분석·복지자료가 준비된 DB
- 업무 저장을 사용할 계정에는 `work` 스키마 쓰기 권한 필요
- 원천 ZIP·XLSX 등 대용량 분석 원자료는 별도 준비

아래 명령은 **프로젝트 루트의 PowerShell**에서 실행합니다. 기존 `.venv`와 `.env`가 있으면 생성·복사 단계는 건너뛰세요.

### 처음 설치

```powershell
python -m venv .venv
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
```

`.env`에 관리자가 전달한 `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_SSLMODE`를 입력합니다. `.env`와 실제 API 키는 Git에 올리지 않습니다. 가상환경을 활성화하지 않아도 위처럼 Python 실행 파일을 직접 지정할 수 있습니다.

`npm ci`는 잠금 파일의 버전으로 설치합니다. 의존성을 추가·변경할 때는 `npm install <패키지>`를 사용하고 `package-lock.json`도 함께 반영합니다.

### 실행과 로그인

```powershell
.\.venv\Scripts\python.exe main.py
```

브라우저에서 [로컬 서비스](http://127.0.0.1:8503)를 엽니다.

| 시연 계정 | 비밀번호 | 역할 |
|---|---|---|
| `gangnam01` | `demo1234` | 강남구 담당자 |
| `admin` | `admin1234` | 관리자 |

코드에 정의된 시연용 계정이며 실제 운영 인증 체계는 아닙니다. 처음 로그인하면 사용 안내가 열리고, 오른쪽 위 `?` 버튼으로 다시 볼 수 있습니다.

### 화면 개발

Python 서버를 실행한 상태에서 **별도 터미널**을 엽니다.

```powershell
cd frontend
npm run dev
```

[개발 화면](http://127.0.0.1:5173)에서 확인합니다. Vite가 `/api` 요청을 Python 서버의 8503 포트로 전달합니다. 8503 주소는 마지막 빌드 결과를 보여 주므로 화면 수정 후 `npm run build`를 다시 해야 반영됩니다.

### 선택 설정

| 환경변수 | 용도 |
|---|---|
| `WELFIND_DATA_SOURCE` | 대시보드 분석자료: `auto`(기본), `db`, `csv` |
| `WELFIND_WELFARE_SOURCE` | 보미 복지자료: `db`(기본), `json`(오프라인 검증용) |
| `DB1_PIPELINE_SCHEMA` | 분석·전처리 작업 스키마, 기본 `db1_pipeline` |
| `TEAM_TOGETHER_DATA_ROOT` | 별도로 준비한 원자료 기준 폴더 |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` | 외부 AI 사용 시 선택한 제공사의 키 |
| `DB2_WELFARE_API_KEY` | DB2 공공 API 수집 키 |

전체 설정은 [.env.example](.env.example), 클라우드 DB 접속은 [DB 구축 안내](docs/오라클_클라우드_DB_구축.md), Docker·Render 실행은 [배포 안내](deploy/render.md)를 참고하세요.

## 기술 스택

| 영역 | 사용 기술 |
|---|---|
| 화면·지도 | React, Vite, MapLibre GL JS |
| HTTP API | Python 표준 `http.server` / `ThreadingHTTPServer` |
| 분석·ML | pandas, NumPy, scikit-learn, joblib |
| DB | PostgreSQL, SQLAlchemy, psycopg2 |
| 보미·외부 AI | Python 규칙·담당 선택, OpenAI·Anthropic·Google GenAI SDK(선택) |
| 보고서 | python-docx |
| 배포 | Docker 다단계 빌드, Render |

## 폴더와 상세 문서

```text
main.py                  웹 서비스·전처리·분석 공통 실행점
frontend/                화면·컴포넌트·지도·스타일
backend/
  api/                   HTTP API·로그인·업무·관리자 요청
  bomi/                  챗봇 흐름·담당 선택·에이전트
  chatbot/               공용 AI 설정·가드레일·복지사업 검색
  agents/                지역 분석 엔진·보고서 작성·사업 매칭
  db/                    PostgreSQL 연결·조회·저장
  services/, resources/  공통 서비스·Word 생성·지도·보고서 서식
pipelines/               DB1 분석·공통 전처리·DB2 수집
assets/brand/            로고·보미 캐릭터·브랜드 원본
data/                    공통 원자료·가공 자료
scripts/                 검사·이관·수집·운영 도구
docs/                    현재 안내·아키텍처·과거 기록(history/)
deploy/                  배포 안내
```

| 목적 | 문서 |
|---|---|
| 처음 코드 읽기·수정 | [개발 안내](docs/development-guide.md) |
| 화면·지도 출처 | [프런트엔드 안내](frontend/README.md) · [디자인 규칙](docs/design-rules.md) |
| API·보미·에이전트 | [백엔드 안내](backend/README.md) |
| 원자료 전처리·분석 | [파이프라인 안내](pipelines/README.md) · [DB1 상세](pipelines/db1/README.md) |
| DB 검사·반영·게시·복원 | [데이터 운영 안내](docs/data-operations.md) |
| 보고서 근거·저장·서식 | [보고서 작성 안내](docs/report-guide.md) |
| 복지자료 정기 수집 | [DB2 수집 안내](docs/DB2_지자체복지_정기수집.md) |
| 전체 문서·과거 변경 기록 | [문서 목차](docs/README.md) |

## 수정 후 확인

프로젝트 루트에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts/audit_repository.py
cd frontend
npm run build
cd ..
git diff --check
```

테스트 파일은 Git 추적에서 제외되어 새 checkout에는 포함되지 않습니다. 별도 보관한 로컬 테스트의 실행 방법은 각 영역 README를 참고하세요. 정적 검사와 빌드 외에도 변경한 기능의 실제 API·DB·브라우저 동작을 확인해야 합니다.

분석 재계산·DB 게시·공공 API 수집은 자료를 변경하는 작업입니다. 실행 명령과 입력 조건은 위 상세 문서를 확인하세요. `python main.py --analysis --no-download`는 전달본 검사이며 원자료를 재계산하는 명령이 아닙니다.
