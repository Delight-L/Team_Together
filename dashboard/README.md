# Team Together · 고립예방 대시보드

지자체별 사회적 고립 위험도를 살펴보는 Streamlit 시연용 대시보드입니다.
로그인, 지역별 지도·상세 카드, 위험도 추이·순위, 집단별 대응·서비스 추천과 챗봇을 제공합니다.
화면은 Streamlit Custom Component v2로 구성하며, Python이 CSV 데이터를 읽어 전달합니다.
`dashboard/isolation-dashboard_260921.html`의 디자인(로그인 화면, 왼쪽 메뉴, 지도·상세 카드, 아래 추이·순위, 오른쪽 챗봇, 색상·글꼴·간격·반응형 배치)을 Streamlit Custom Component v2로 옮겼고, 화면 데이터는 Python이 CSV를 읽어 전달합니다.

## 실행하기

### 1. 준비

Python 3.10 이상을 준비한 뒤 저장소를 내려받고 가상환경을 만듭니다.
가상환경은 저장소에 포함되지 않으므로 각 컴퓨터에서 처음 한 번 만들어야 합니다.

```bash
git clone --branch docoup3 --single-branch https://github.com/Delight-L/Team_Together.git
cd Team_Together
cd Team_Together/dashboard
python -m venv .venv
```

### 2. 설치 및 실행

Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run main.py
```

macOS / Linux:

```bash
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python -m streamlit run main.py
```

브라우저에서 `http://localhost:8501`을 엽니다.

Windows에서는 `.\.venv\Scripts\python.exe main.py`로도 실행할 수 있습니다.
기존 전처리 CSV 준비·확인은 `python main.py --preprocess`로 실행합니다.
현재 화면은 `dashboard/data/`의 CSV를 사용하며, `data/processed/` 자료의 위험 요인 변환·연결은 별도 작업입니다.

- Windows에서는 최초 설치 후 `dashboard/run_dashboard.bat`를 더블클릭해 실행할 수도 있습니다.
- 실행 창은 앱을 사용하는 동안 열어 두고, 종료할 때는 실행 창에서 `Ctrl+C`를 누릅니다.
- `ui/`의 화면 파일을 수정한 뒤에는 앱을 종료하고 다시 실행하세요.
- CSV 수정은 파일의 수정 시간을 기준으로 다시 읽으므로 브라우저를 새로고침하면 반영됩니다.

## 시연 계정

로그인 화면의 시연 계정 버튼을 누르고 로그인 버튼을 누르면 됩니다.

| 소속 | 아이디 | 비밀번호 |
|---|---|---|
| 강남구 | gangnam01 | demo1234 |
| 춘천시 | chuncheon01 | demo1234 |
| 전체 관리자 | admin | admin1234 |

모든 계정·집단별 집계·위험 점수는 시연용입니다. 로그인은 실제 서비스 인증 기능이 아닙니다.

## 구성

설치 의존성은 최상위 `requirements.txt`, Streamlit 설정은 최상위 `.streamlit/config.toml`에서 관리합니다.

실행 진입점은 프로젝트 최상위의 `main.py`입니다. 이 파일에서 `dashboard/main.py`의 `render_app()`을 호출합니다. 대시보드 Python 파일은 화면 구성(`dashboard/main.py`), 설정(`settings.py`), 데이터 읽기(`data_utils.py`), 화면 연결(`design_ui.py`)의 네 역할로 나눕니다.
일·월 집계와 위험도 계산은 `ui/data.js`, 그래프는 `ui/charts.js`에서 처리합니다.

| 변경 내용 | 파일 |
|---|---|
| 대시보드 화면 구성 / 데이터 연결 | `dashboard/main.py` — 파트 1~8 |
| CSV 경로 / 요인 이름 / 기본 가중치 / 기준 점수 | `dashboard/settings.py` |
| CSV·지도 데이터 읽기 / 유효성 검사 | `dashboard/data_utils.py` |
| 날짜별 지역 위험 요인 | `dashboard/data/risk_factors.csv` |
| 지역·성별·연령대 월별 집계 | `dashboard/data/group_signals.json` |
| 집단별 변화율·서비스 추천·조치 현황 | `dashboard/ui/responses.js` |
모든 계정·대상자·위험 점수는 시연용입니다. 로그인은 실제 서비스 인증 기능이 아닙니다.

## 구성

| 변경 내용 | 파일 |
|---|---|
| Python 실행 흐름 / 데이터 연결 | `dashboard/main.py` — 파트 1~8 |
| CSV 경로 / 요인 이름 / 기본 가중치 / 기준 점수 | `dashboard/settings.py` |
| CSV 검사 / 일·월 집계 / Python 위험도 계산 | `dashboard/data_utils.py` |
| 날짜별 지역 위험 요인 | `dashboard/data/risk_factors.csv` |
| 대상자 목록 | `dashboard/data/people.csv` |
| 행정동 지도 경계 | `dashboard/data/map_boundaries.json` |
| 색상 / 글꼴 / 너비 / 간격 / 카드 배치 | `dashboard/ui/style.css` |
| 로그인 / 앱 뼈대 / 챗봇 입력 폼 | `dashboard/ui/layout.html` |
| 추이 그래프 종류와 축·선·막대 | `dashboard/ui/charts.js` |
| 지도 / 요인 막대 / 요인 기여도 / 메뉴 / 각 화면 | `dashboard/ui/dashboard.js` |
| 화면의 날짜 조회 / 월평균 / 위험도 계산 | `dashboard/ui/data.js` |
| 화면을 Streamlit에 등록·표시하는 부분 | `dashboard/design_ui.py` |

- 화면 디자인과 동작은 **`ui/` 폴더**에서 수정하세요.
- 실행과 데이터 변경 위치에는 파트별 한국어 주석이 달려 있습니다. 새 데이터와 시각화 변경 방법은 아래 항목을 참고하세요.
- 원본 디자인 버전을 고칠 때는 **`ui/` 폴더**를 수정하세요.
- 수업에서 배운 Streamlit 기본 위젯으로 작성한 이전 버전은 `main_native.py`에 보관했고, 그 버전의 Plotly 그래프 코드는 `charts.py`에 있습니다. `charts.py`를 고치면 보관한 기본 위젯 버전에만 적용됩니다.
- `prepare_design.py`와 `export_html_data.cjs`는 최초 분리·추출에 사용한 도구입니다. 다시 실행하면 수정한 화면 파일 또는 CSV를 덮어쓸 수 있으므로 일상적인 편집 때는 사용하지 마세요.
- 실행과 데이터 변경 위치에는 파트별 한국어 주석이 달려 있습니다. 새 데이터를 추가하거나 시각화를 바꾸는 방법은 [대시보드 사용안내](dashboard/사용안내.md)를 참고하세요.

## 데이터 교체

### 위험 요인: `data/risk_factors.csv`

같은 열 이름으로 교체하세요.

| 열 | 뜻 | 예시 |
|---|---|---|
| date | 날짜, YYYY-MM-DD | 2026-09-20 |
| city | 지자체 | 강남구 |
| district | 행정동 | 역삼1동 |
| flow | 유동인구 감소 위험 점수 | 55.3 |
| card | 카드 결제 감소 위험 점수 | 48.1 |
| single | 1인 가구 비율/점수 | 62.0 |
| elder | 고령 인구 비율/점수 | 30.0 |
| welfare | 복지 연계 공백 점수 | 41.0 |

- 한 행은 하루·지자체·행정동 하나입니다. 같은 조합을 중복 입력하지 마세요.
- 5개 요인은 빈칸 없이 **0~100, 값이 클수록 위험**으로 준비합니다.
- 인구수나 결제액 자체를 넣으려면 감소율 또는 정규화 점수로 먼저 변환합니다.
- 월별 값은 그 월에 존재하는 날짜의 평균입니다. 9월 샘플은 20일까지의 평균입니다.
- 일별 변화는 7일 전, 월별 변화는 전월과 비교합니다. 비교 자료가 없으면 '비교 자료 없음'을 표시하며 임의의 0점으로 만들지 않습니다.
- 화면에서 설정한 가중치는 브라우저 화면 상태에 저장되어 새로고침하면 기본값으로 돌아갑니다. 새 세션의 기본값은 `settings.py`의 `DEFAULT_WEIGHTS`를 바꾸세요.

### 지역·집단별 대응: `data/group_signals.json`

‘대응·서비스 추천’에서 월·행정동·성별·연령대·확인 우선순위를 선택하고, 상세 변화와 서비스 유형을 확인합니다. ‘조치 현황’은 같은 집단을 검토 상태별로 보여 줍니다.

현재 파일은 `isDemo: true`인 **화면 시연용 가상 집계**입니다. 실제 전처리 데이터 및 복지사업 DB는 연결되지 않았습니다.

- `rows`: `month`, `city`, `district`, `gender`, `age`, `flow`(일평균 명), `card`(일평균 건), `sampleCount`(관측 규모), `observedDays`(집계 일수).
- 변화율: `(당월 일평균 - 전월 일평균) / 전월 일평균 × 100`.
- 시연 기준: 두 지표 모두 15% 이상 감소 → 우선 확인, 하나라도 10% 이상 감소 → 확인 필요, 그 외 → 관찰.
- 전월 자료 없음·전월 값 0·지표 누락·관측 규모 30 미만·월 집계 미완료 → 판단 보류. 추천은 보류합니다.
- 성별·연령대는 집단을 구분하며, 그 자체로 위험도를 높이지 않습니다. 지역 전체 대비 변화와 장기 지속성은 아직 반영하지 않습니다.
- 서비스는 유형 제안입니다. 실제 사업·기관·이용 조건 확인 후 연계해야 합니다.
- 조치 상태는 현재 화면에서만 유지하며 새로고침·로그아웃 시 초기화됩니다.

## 지도 교체

`map_boundaries.json`은 행정동 경계를 나타내는 SVG 그림 좌표입니다. 위도·경도나 GeoJSON 형식은 아닙니다.
### 대상자: `data/people.csv`

다음 열을 유지합니다.

```text
person_id,city,name,age,district,risk_score,reason,status,last_contact
```

- `person_id`는 중복되지 않는 ID입니다.
- `risk_score`는 0~100의 개인 점수이며 지역 위험도 가중치와 별도로 관리합니다.
- `status`는 미배정 / 방문 예정 / 상담 완료 / 모니터링 중 하나입니다.
- `last_contact`는 최근 접촉 날짜입니다.
- 현재 목록은 가상의 대상자 64명입니다.

## 지도 교체

`map_boundaries.json`은 원본의 SVG 그림 좌표입니다. 위도·경도나 GeoJSON 형식은 아닙니다.

- 동일한 강남구·춘천시 행정동 자료의 수치를 교체하면 지도를 그대로 사용할 수 있습니다.
- CSV의 행정동 이름은 지도 데이터의 `n` 값과 정확히 일치해야 합니다.
- 새 지자체를 추가하면 해당 지도 경계와 로그인 소속도 함께 추가하세요.
- 지도 코드는 `ui/dashboard.js`의 `mapSVG()`에 있습니다. SVG를 다른 지도 라이브러리로 교체할 때도 이 함수가 출력하는 화면 부분을 바꾸면 됩니다.

## 그래프 종류 교체

`ui/charts.js` 맨 위의 값을 바꾸면 같은 시계열로 다른 그래프를 볼 수 있습니다.

```javascript
const TREND_CHART_TYPE = 'line'; // 꺾은선 그래프
const TREND_CHART_TYPE = 'line'; // 원본의 꺾은선
// 'area'로 변경: 영역 그래프
// 'bar'로 변경: 지역 평균과 선택 동을 나란히 표시하는 막대
```

그림 크기, 여백, 축, 기준선, 선 색은 같은 파일의 `chartSVG()`에 주석을 달았습니다.
다른 시각화는 `ui/dashboard.js`에서 다음 함수를 찾아보세요.

| 함수 | 역할 |
|---|---|
| `mapSVG()` | 위험 단계별 행정동 지도 |
| `detailHTML()` | 선택 지역의 위험도와 5개 요인 막대 |
| `trendCard()` | 추이 자료를 모아서 그래프 함수에 전달 |
| `rankCard()` | 위험도 순위 목록 |
| `viewAnalysis()` | 요인별 기여 누적 막대 표 |

## 구현 범위

7개 화면에서 지도 선택, 위험 단계 필터, 일·월 전환, 가중치 변경, 챗봇 열기·닫기, 성별·연령대 필터, 메뉴 접기·펴기를 지원합니다.
운영체제/브라우저의 밝은·어두운 모드를 따릅니다.

현재 로그인 계정, 집단별 집계, 위험 점수, 예시 로그는 시연용입니다.
챗봇은 질문 유형을 분류하는 규칙 기반 응답입니다.
조치 이력 영구 저장과 실제 인증·DB·AI 연결은 추후 구현할 부분입니다.

## 개발용 검증

검증 도구는 `tests/`에 분리되어 있으며 대시보드 실행에는 필요하지 않습니다.
프로젝트 최상위 폴더에서 실행합니다. JavaScript 계산 검증에는 Node.js가 필요합니다.

```powershell
# Python 실행, CSV 계산 연결, JavaScript 문법 확인
.\.venv\Scripts\python.exe dashboard/tests/check_dashboard.py
```

`tests/check_dashboard.py`는 CSV의 일별 값·월평균·가중 점수와 자료 누락 처리를 검증합니다.

## 데이터·에이전트 연결 위치

- `data_utils.py`: 실제 집계 데이터의 읽기·검사 함수를 연결합니다.
- `main.py`의 `render_app()`: 데이터를 화면 전달 형식인 `payload`로 구성합니다.
- `ui/responses.js`: 집단별 변화율·확인 우선순위·서비스 추천 화면을 담당합니다.
- `ui/dashboard.js`의 `answer()`: 현재 규칙 기반 챗봇의 응답 진입점입니다. 실제 에이전트 연결에는 별도의 서버 호출 및 응답 처리가 필요합니다.
- `tests/`: 데이터 연결 후 계산·화면 진입을 확인하는 개발용 검증 도구입니다.

`data/risk_factors.csv`, `data/group_signals.json`, `data/map_boundaries.json`은 현재 실행에 필요합니다. 실제 데이터 연결이 완료되기 전에는 유지하세요.
원본 7개 화면과 지도 선택, 위험 단계 필터, 일·월 전환, 가중치 변경, 챗봇 열기·닫기, 대상자 필터, 메뉴 접기·펴기 동작을 유지했습니다.
원본처럼 운영체제/브라우저의 밝은·어두운 모드를 따릅니다.

현재 로그인 계정, 대상자, 위험 점수, 예시 로그는 시연용입니다.
챗봇은 질문 유형을 분류하는 규칙 기반 응답입니다.
대상자 수정·배정·방문 결과 저장과 실제 인증·DB·AI 연결은 추후 구현할 부분입니다.

## 확인 도구

`dashboard` 폴더에서 실행합니다. 디자인 검증 도구의 JavaScript 계산 비교에는 Node.js가 필요합니다.

```powershell
# 원본 디자인 버전의 Python 실행, CSS·화면 구조, CSV 계산 연결 확인
.\.venv\Scripts\python.exe verify_design.py

# 보관한 Streamlit 기본 위젯 버전의 동작 확인
.\.venv\Scripts\python.exe verify_dashboard.py
```

`verify_design.py`는 초기 샘플 자료가 원본과 같은 계산 결과를 내는지도 비교합니다.
실제 자료로 교체하면 이 원본 비교 검사의 기대값도 함께 수정해야 합니다.
