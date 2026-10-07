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
| 종합 현황·지역 비교·후보 집계 | `frontend/src/Briefing.jsx` | `Briefing`, `RegionalOverview`, `summarizeRegions` |
| 로그인 화면 | `frontend/src/App.jsx` | `Login` |
| 사업 검토 입력 | `frontend/src/App.jsx` | `Services` |
| 보고서 입력 | `frontend/src/App.jsx` | `Report` |
| 업무 현황·자료 업로드·활동 이력 | `frontend/src/Workspace.jsx` | `Missions`, `Upload`, `Activity` |
| 지도 클릭·색·라벨·팝업 | `frontend/src/Briefing.jsx` | `MissionMap`, `RegionInsight` |
| 챗봇 디자인·추천 질문·메시지 | `frontend/src/components.jsx` | `ChatPanel` |
| 추이 그래프 | `frontend/src/components.jsx` | `Trend` |
| 색·크기·간격·화면 높이 | `frontend/src/style.css`, `frontend/src/briefing.css` | 해당 클래스 이름 |
| 프런트엔드 서버 통신 | `frontend/src/api.js` | `api` |
| 분석 데이터 조회·API 오류 | `webapp/server.py` | `dashboard_data`, `do_GET`, `do_POST` |
| 챗봇 답변 내용과 AI 호출 | `chatbot/service.py` | `explain_question` |
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
| 사업 조회 실패 | Python 터미널, `.env` | DB 주소·계정·권한과 `db2.reviewed_service_candidates` 조회 가능 여부 |
| AI 모드가 규칙 설명으로 돌아옴 | `.env`, 답변의 모드 표시 | `GEMINI_API_KEY`와 `GEMINI_MODEL`, 외부 연결 확인 |
| 저장 버튼이 비활성화됨 | 지역 분석 화면 | 지역 선택 → 분석 확인 → 근거 검토 → 사업 검토 순서 |
| `EADDRINUSE` 또는 Windows 10048 | 실행 터미널 | 같은 포트 서버가 이미 실행 중. 기존 터미널 Ctrl+C 또는 `python main.py --port 8504` |

## 메인 화면 스크롤을 막는 부분

`style.css`의 `.app-shell`은 `height: 100dvh`, `overflow: hidden`을 사용합니다. `.main-content`, `.overview`, `.distribution-grid`의 `min-height: 0`은 패널이 부모 높이보다 커지지 않도록 합니다. 이 값을 없애거나 카드 높이를 과하게 늘리면 하단이 잘릴 수 있습니다. 긴 목록과 대화는 `.table-scroll`, `.chat-messages`, `.scroll-view` 안에서만 스크롤합니다.

메인 카드 추가 시 1366×768 및 1920×1080에서 지도·상세·입력창이 모두 보이는지 확인하세요. 모바일에서는 상세 패널이 지도 아래로 배치됩니다.

## 지켜야 할 연결 규칙

- 지역과 월은 `App`의 `context` 하나로 공유합니다. 챗봇 안에 별도 지역 상태를 만들지 마세요.
- `null` 분석값을 0으로 바꾸면 이력 부족이 정상 수치처럼 보입니다. 화면에서는 `—`로 표시합니다.
- 전월 변화율과 Robust Z는 다릅니다. 전월 증가여도 공통 변화 제거 후 상대적으로 낮아 후보가 될 수 있습니다.
- 후보 개수는 지표 개수, 후보 지역은 동 개수입니다. 4개 지표를 4개 동으로 세지 마세요.
- 사용자 질문과 사업 설명은 React 텍스트로 표시합니다. 외부 문자열을 `dangerouslySetInnerHTML`로 넣지 마세요.
- 보고서/업무 저장은 서버의 단계 검증을 거칩니다. 프런트에서 `done` 숫자만 추가하는 방식으로 저장을 대신하지 마세요.

[React 공식 상태 공유 설명](https://react.dev/learn/sharing-state-between-components)


## 이번 화면의 핵심 연결

- 로고 클릭은 `navCollapsed`를 반전합니다. 접힌 로고는 `ci/bomi-face.png`입니다.
- 동 클릭은 공통 `district`를 바꾸므로 지도 팝업과 챗봇의 지역이 동시에 바뀝니다.
- `Bomi`는 `busy`가 참인 동안에만 `ci/bomi-waiting.gif`를 보여줍니다. 답변 완료/실패/취소 후에는 정지 PNG로 돌아옵니다. OS의 동작 줄이기가 켜져 있으면 GIF를 사용하지 않습니다. `bomi-direction.gif`는 전달받은 예비 자산입니다.
- 신규/연속 후보는 이전 분석월과 현재 분석월의 실제 후보를 비교합니다. 건물 배경은 일러스트이며 실제 건물 위치가 아닙니다.
- 종합 현황은 우선 확인 후보 중심, 지역 현황은 전체 동 검색·필터·정렬 중심입니다.

## 기본 주제와 자유 대화의 AI 비용 경계

ChatPanel.send(question, topic)에서 버튼은 고정 topic ID를, 직접 입력은 null을 보냅니다. 서버는 chatbot/orchestrator.py의 topic_reply와 free_reply로 분리합니다. 기본 버튼은 API 키가 있어도 AI를 호출하지 않습니다.

자유 대화는 총괄 라우팅 1회와 전문 답변 1회, 총 2회 모델 요청을 사용합니다. 총괄의 agent 출력은 고정 허용 목록으로 검사하며 임의 코드/파일 실행을 허용하지 않습니다. 지역 에이전트는 현재 CSV, 사업 에이전트는 기존 DB2 매칭 조회를 사용합니다. 보고서 에이전트는 작성 절차를 안내하며 문서를 자동 저장하지 않습니다. 구체적인 사업 조회에 필요한 동이 없으면 선택을 요청합니다.

동을 선택하지 않은 대화는 소속 도시의 현재 월 자료만 사용합니다. 다른 도시 접근 검증과 업무 저장의 동 선택 검증은 유지합니다. AI 키·모델 설정이 없거나 연결 실패하면 명시적인 안내를 반환합니다.

검사: .venv/Scripts/python.exe -m unittest discover -s chatbot/tests -v 및 API 검사. 외부 AI는 mock으로 대체하므로 테스트에서 토큰을 사용하지 않습니다.
