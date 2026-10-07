# React를 처음 쓰는 팀원을 위한 수정·오류 확인 가이드

## 먼저 알아둘 실행 구조

```text
브라우저: React 화면 (frontend/src)
    ↓ /api/... 요청 (frontend/src/api.js)
Python: webapp/server.py (기본 포트 8503)
    ↓ 기존 모듈 재사용
분석 CSV / chatbot/service.py / DB2 / db/mission_store.py
```

React는 화면을 담당합니다. 전처리와 분석은 계속 Python에서 실행합니다. CSV 경로와 `.env` 설정을 React 소스에 복사할 필요가 없습니다. 특히 API 키를 React 파일에 넣으면 빌드 결과를 통해 브라우저에 노출되므로 Python `.env`에서만 관리합니다.

## 파일별 수정 위치

| 하고 싶은 수정 | 파일 | 찾을 이름 |
|---|---|---|
| 메뉴 이름, 화면 제목 | `frontend/src/App.jsx` | `menus`, `titles` |
| 선택 지역·월, 메뉴 접기 | `frontend/src/App.jsx` | `context`, `navCollapsed` |
| 종합 현황 조사 파일·요약 카드·질문 버튼 | `frontend/src/CaseBriefing.jsx` | `CaseBriefing`, `BriefingStats`, `MetricCard` |
| 조사 파일 순서·6개월 그래프 자료·설명 | `frontend/src/briefingData.js` | `rankedCases`, `metricSeries`, `caseNarrative` |
| 지역 현황·후보 판정 | `frontend/src/Briefing.jsx` | `RegionalOverview`, `summarizeRegions` |
| 로그인 화면 | `frontend/src/App.jsx` | `Login` |
| 사업 검토 입력 | `frontend/src/App.jsx` | `Services` |
| 보고서 입력 | `frontend/src/App.jsx` | `Report` |
| 업무 현황·자료 업로드·활동 이력 | `frontend/src/Workspace.jsx` | `Missions`, `Upload`, `Activity` |
| 지도 클릭·확대·라벨 | `frontend/src/VectorMap.jsx` | MapLibre 지도, 지역 선택 콜백 |
| 지도 배경·상태 색상 | `frontend/src/missionMapStyle.js` | 벡터 지도 스타일, 로컬 행정동 소스 |
| 지도 표현 전환·상세 카드 | `frontend/src/MissionMap.jsx`, `frontend/src/Briefing.jsx` | 지도 지연 로딩, 입체/도로 전환, `RegionInsight` |
| 챗봇 디자인·추천 질문·메시지 | `frontend/src/components.jsx` | `ChatPanel` |
| 브리핑 그래프 / 지역 분석 추이 | `frontend/src/CaseBriefing.jsx` / `frontend/src/components.jsx` | `ValueChart` / `Trend` |
| 조사 파일 디자인·반응형 배치 | `frontend/src/case-briefing.css` | `case-board`, `case-paper`, `case-metrics` |
| 공통 색·크기·간격·지도 화면 | `frontend/src/style.css`, `frontend/src/briefing.css` | 해당 클래스 이름 |
| 프런트엔드 서버 통신 | `frontend/src/api.js` | `api` |
| 분석 데이터 조회·API 오류 | `webapp/server.py` | `dashboard_data`, `do_GET`, `do_POST` |
| 그래프 원자료·단위 전달 | `db/analysis_repository.py` | `prepare_analysis2`, `metric_value`, `metric_unit` |
| 복지이음 답변 내용과 AI 호출 | `chatbot/welfare/app/agent/orchestrator.py`, `chatbot/welfare/app/agent/resources.py`, `chatbot/welfare/app/llm/openai_client.py` | `handle_chat`, `search`, `stream` |
| 업무 저장·단계 검증 | `db/mission_store.py` | `save_event` |

## React 문법 최소 설명

```jsx
// district 값이 바뀌면 React가 화면을 다시 그립니다.
const [district, setDistrict] = useState('');

// 버튼을 클릭하면 district를 변경합니다.
<button onClick={() => setDistrict('삼성1동')}>삼성1동</button>

// {} 안은 JavaScript입니다. district가 있으면 상세 화면을 보여줍니다.
{district && <h2>{district} 분석</h2>}
```

- `props`: 부모 컴포넌트가 자식에게 전달하는 값/함수입니다. `ChatPanel`의 `context`가 예시입니다.
- `useState`: 화면에서 기억할 값입니다. 값을 직접 바꾸지 말고 `setDistrict` 같은 갱신 함수로 바꿉니다.
- `useEffect`: 상태 변경에 따라 API 조회 같은 작업을 실행합니다. 두 번째 인자의 배열은 언제 다시 실행할지 정합니다.
- `useMemo`: 값이 바뀔 때만 필터링/객체를 다시 만듭니다. 꼭 필요한 최적화보다 공유 context의 안정성을 위해 사용합니다.
- `async / await`: API 응답을 기다립니다. 실패는 `try / catch`에서 처리합니다.
- `map`: 여러 데이터로 여러 화면 요소를 만듭니다. 각 요소에 고유한 `key`가 필요합니다.
- JSX는 HTML과 비슷합니다. `className`, `onClick`을 쓰고 태그는 반드시 닫습니다. 주석은 JavaScript에서 `//`, JSX 내부에서 `{/* 설명 */}`입니다.

## 수정하고 확인하는 순서

1. Python 서버를 실행합니다: 프로젝트 루트에서 `.venv/Scripts/python.exe main.py`.
2. 다른 터미널에서 `cd frontend`, `pnpm run dev`를 실행합니다.
3. http://127.0.0.1:5173 을 열어 수정합니다. 개발 서버는 저장한 변경을 자동 반영합니다.
4. 수정 후 `frontend`에서 `pnpm run build`로 문법/번들 오류를 확인합니다.
5. 시연용 http://127.0.0.1:8503 에서 새로고침합니다. 이 주소는 마지막 빌드 결과를 사용하므로 빌드를 생략하면 수정 전 화면이 나옵니다.

## 오류가 났을 때

브라우저 F12 → **Console**은 React/JavaScript 오류, **Network**는 서버 통신을 보여줍니다. Python 터미널에는 API/CSV/DB 오류의 실제 traceback이 찍힙니다.

| 증상 | 먼저 볼 곳 | 확인할 사항 |
|---|---|---|
| `frontend ... pnpm run build` 안내 | frontend 폴더 | 의존성 설치와 빌드가 완료됐는지 |
| 화면이 하얗게 나오거나 JSX 오류 | Console, `pnpm run build` | 오류 파일/줄의 닫는 태그, 괄호, import 이름 |
| 수정한 내용이 안 보임 | 접속 URL | 8503에서는 다시 빌드해야 함. 개발은 5173 사용 |
| 질문/조회에 `Failed to fetch`, `ECONNREFUSED` | Network, Python 터미널 | Python 서버가 8503에서 실행 중인지 |
| 401 | 로그인 | 서버 재시작 시 메모리 세션이 초기화되므로 다시 로그인 |
| 분석 CSV 누락 | Python 터미널 | `agents/regional_analysis/Analysis2/outputs`에 detection CSV가 있는지 |
| 사업 조회 실패 | Python 터미널, `.env` | DB 주소·계정·권한과 `db2.local_welfare_services` 조회 가능 여부 |
| 복지이음이 자료 검색 안내로 돌아옴 | `.env`, 답변의 모드 표시 | `OPENAI_API_KEY`와 `OPENAI_MODEL`, 외부 연결 확인 |
| 저장 버튼이 비활성화됨 | 지역 분석 화면 | 지역 선택 → 분석 확인 → 근거 검토 → 사업 검토 순서 |
| `EADDRINUSE` 또는 Windows 10048 | 실행 터미널 | 같은 포트 서버가 이미 실행 중. 기존 터미널 Ctrl+C 또는 `python main.py --port 8504` |

## 메인 화면 스크롤을 막는 부분

`style.css`의 `.app-shell`은 `height: 100dvh`, `overflow: hidden`을 사용합니다. `.main-content`, `.overview`, `.distribution-grid`의 `min-height: 0`은 패널이 부모 높이보다 커지지 않도록 합니다. 이 값을 없애거나 카드 높이를 과하게 늘리면 하단이 잘릴 수 있습니다. 긴 목록과 대화는 `.table-scroll`, `.chat-messages`, `.scroll-view` 안에서만 스크롤합니다.

종합 현황은 `case-briefing.css`에서 PC 화면(1201px 이상)의 문서·그래프 높이를 남는 공간에 맞춰 중앙 스크롤 없이 표시합니다. `min-height: 0`과 그래프의 유연한 높이를 유지하세요. 좁은 화면에서는 접근성을 위해 본문 스크롤을 허용하며 문서 위에 가로 목록과 전체 지역 선택을 표시합니다. 지도는 지역 현황 메뉴에 남아 있습니다.

조사 파일은 `briefingData.js`의 `casePage`로 7곳씩 나누며, 선택 지역으로 마지막 항목을 덮어쓰지 않습니다. 후보가 많은 달에도 모든 지역을 페이지 버튼으로 볼 수 있어야 합니다. 기준월 변경 시 첫 페이지, 지역 선택 상자 변경 시 선택한 지역의 페이지로 이동합니다.

메인 카드 추가 시 1366×768 및 1920×1080에서 카드·목록·입력창이 접근 가능한지 확인하세요.

## 지켜야 할 연결 규칙

- 지역과 월은 `App`의 `context` 하나로 공유합니다. 챗봇 안에 별도 지역 상태를 만들지 마세요.
- `null` 분석값을 0으로 바꾸면 이력 부족이 정상 수치처럼 보입니다. 화면에서는 `—`로 표시합니다.
- 전월 변화율과 Robust Z는 다릅니다. 전월 증가여도 공통 변화 제거 후 상대적으로 낮아 후보가 될 수 있습니다.
- 후보 개수는 지표 개수, 후보 지역은 동 개수입니다. 4개 지표를 4개 동으로 세지 마세요.
- 브리핑 그래프는 `metric_value`의 실제 지표값을 사용합니다. 원자료가 없을 때만 `change_pct`로 전환하고 단위를 %로 바꿉니다. 누락값을 만들거나 미래 월을 포함하지 마세요.
- `AI에게 질문하기`는 실제 근거를 담은 입력 초안만 준비합니다. 클릭 직후 자동으로 외부 AI를 호출하지 않습니다.
- 사용자 질문과 사업 설명은 React 텍스트로 표시합니다. 외부 문자열을 `dangerouslySetInnerHTML`로 넣지 마세요.
- 보고서/업무 저장은 서버의 단계 검증을 거칩니다. 프런트에서 `done` 숫자만 추가하는 방식으로 저장을 대신하지 마세요.

[React 공식 상태 공유 설명](https://react.dev/learn/sharing-state-between-components)


## 이번 화면의 핵심 연결

- 로고 클릭은 `navCollapsed`를 반전합니다. 접힌 로고는 `ci/bomi-face.png`입니다.
- 동 클릭은 공통 `district`를 바꾸므로 지도 팝업과 챗봇의 지역이 동시에 바뀝니다.
- `Bomi`는 `busy`가 참인 동안에만 `ci/bomi-waiting.gif`를 보여줍니다. 답변 완료/실패/취소 후에는 정지 PNG로 돌아옵니다. OS의 동작 줄이기가 켜져 있으면 GIF를 사용하지 않습니다. `bomi-direction.gif`는 전달받은 예비 자산입니다.
- 신규/연속 후보는 이전 분석월과 현재 분석월의 실제 후보를 비교합니다. 건물 배경은 일러스트이며 실제 건물 위치가 아닙니다.
- 종합 현황은 우선 확인 후보 중심, 지역 현황은 전체 동 검색·필터·정렬 중심입니다.

## 브리핑 질문과 복지이음 연결

`CaseBriefing`의 질문 버튼은 `caseQuestionDraft`로 실제 지역·월·변화율·Robust Z를 담은 초안을 만듭니다. `App`이 공통 지역과 `chatDraft`를 갱신하고 `ChatPanel`이 같은 지역·월인지 확인한 뒤 입력창에 한 번 적용합니다. 사용자가 전송하기 전에는 AI 요청이 없습니다.

질문을 전송하면 `ChatPanel.send` → `/api/chat` → `chatbot/welfare/service.py` → 가져온 `chatbot/welfare/app/agent/orchestrator.py`의 `handle_chat`으로 이어집니다. 추천 질문과 자유 질문 모두 같은 복지 자료 검색과 답변 흐름을 사용합니다. OpenAI 키가 있으면 AI 답변, 키가 없거나 AI 연결이 실패하면 자료 검색 안내를 제공합니다. DB2 사업 검토와 업무 저장은 별도 메뉴에서 기존 검증 순서를 따릅니다.

검사: `frontend`에서 `node --test tests/briefing.test.mjs`, 프로젝트 루트에서 `.venv/Scripts/python.exe -m unittest discover -s webapp/tests -v`. API 검사는 외부 AI 호출과 실제 업무 DB 쓰기를 대체합니다.
