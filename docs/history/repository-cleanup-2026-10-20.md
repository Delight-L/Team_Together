> 과거 계획·구현·검증 기록입니다. 현재 실행 방법은 [문서 안내](../README.md)를 따르세요.

# main 기준 코드 정리 (2026-10-20)

기준 커밋은 원격 `main`의 `f80644f`입니다. 원격 조회로 `main`과 `HyungWoo_React`가
같은 커밋임을 확인했습니다. 작업은 `codex/main-cleanup-20261020`에서 진행했습니다.
기능·주요 폴더 구조를 유지하며 미사용·중복 코드를 정리하고, 지역 분석 엔진의 버전식 이름을 바꾸는 범위입니다.
정리 이후 사용자 요청에 따라 커밋·main 병합·push를 진행합니다.
아래 검증은 로컬 작업 범위이며, 배포 결과 확인과는 별개입니다.

## 정리한 항목

| 대상 | 처리·확인 근거 |
|---|---|
| `frontend/src/serviceText.mjs` | 화면·동적 import·실행 도구에서 참조하지 않는 옛 사업 요약 모듈 제거. 보고서에서 쓰는 Python 구현은 유지하고 오래된 화면 참조 주석만 수정 |
| React 내부 미사용 기능 | `Experience.jsx`의 `Comparison`·`CompareChart`·색상표, `components.jsx`의 `Trend`, `reviewPresentation.mjs`의 옛 사업 필터·조건표 제거. 현재 지역 분석 화면·사업 검토는 별도 구현을 사용 |
| 패널 크기 조절 CSS | 생성되지 않는 `chat-resized`·`chat-resizer`·`chat-resizing` 선택자 제거. 현재 패널에도 적용되는 일반 위치 규칙은 유지 |
| `backend/api/common.py`의 `rows_for_month` | 호출되지 않는 전체 동 조회 함수 제거. 실제 지역 근거 조회·권한 검사는 유지 |
| `Analysis2/run_analysis2_sequential.py` | 호출되지 않는 `parse_month`, `load_history` 제거. 후자는 이미 사라진 `STATE_DIR`, `HISTORY_PATH`, `INITIAL_HISTORY_PATH`를 참조. 현재 PostgreSQL 작업기 진입점과 월 검증·파일 선택 함수 유지 |
| `regional_types/preprocessor.py` | 현재 서비스가 DB1 `Analysis1/service_adapter.py`를 실행하므로 사용하지 않는 옛 CSV·인구·가구·복지 전처리 함수 7개와 미구현 API 함수 1개 제거. 현재 subprocess 호출과 결과 저장은 유지 |
| Python import | 백엔드·분석·전처리·검증 도구의 사용하지 않는 import 제거 |

제거한 Python 함수는 총 11개입니다. 전처리의 중복 구현을 없애고 기존 DB1 구현을
계속 사용합니다. 데이터 계산식·SQL·정렬·검증 조건은 바꾸지 않았습니다.
수정한 Python 파일 중 유지되는 최상위 함수·클래스 158개의 AST가 기준 커밋과 같음을 확인했습니다.
이름·설명·로그·응답 모드 문구가 바뀐 정의는 이 수치에서 제외했습니다.

## 지역 분석 엔진 이름

| 이전 | 현재 |
|---|---|
| `backend/agents/regional_v16/` | `backend/agents/regional_analysis/` |
| `backend/bomi/adapters/v16.py` | `backend/bomi/adapters/regional_analysis.py` |
| `backend/api/routes_v16.py` | `backend/api/routes_regional_analysis.py` |
| 어댑터 `V16_ROOT` | `REGIONAL_ANALYSIS_ROOT` |
| 지역 분석 담당의 `_v16` 메서드 | `_engine_reply` |

엔진·평가 자료는 위치를 옮겼습니다. 게시 모듈 import, 서버 라우트 연결, 무시 규칙,
현재 안내 문서·흐름도의 경로도 함께 변경했습니다. 답변의 모드·출처에는 `지역 분석`을 표시합니다.
엔진 폴더의 49개 Git 관리 파일 중 46개는 내용이 같고, 나머지 3개는 게시 import·미사용 import·안내 경로를 수정했습니다.
과거 평가 파일 이름·검증 결과·버전 메타데이터는 과거 실행을 식별하므로 유지합니다.

다음은 저장 자료와 기존 호출의 호환성을 위한 이름이며 이번에 바꾸지 않습니다.

- DB의 `db1_v16`, `db1.v16_*` 스키마·테이블·뷰.
- 기존 직접 조회 주소 `/api/chat/v16`과 설정 응답의 `v16Available`.
- 기존 라우트 식별자 `regional_v16` 및 보미 라우터의 과거 이름 대응표.

Git 제외인 로컬 테스트 원본에는 예전 import가 남아 있습니다. 이번 검증은 테스트 원본을
덮어쓰지 않고, 임시 실행기에서 import를 새 모듈에 연결해 실행했습니다.
로컬 테스트를 직접 실행하려면 어댑터 import를 새 경로로 맞춰야 합니다.

## 조사했지만 보존한 항목

- 동일한 소스 함수 본문과 동일한 텍스트 파일은 이번 정적 검사에서 발견되지 않았습니다.
- 전체 파일 해시에서는 CSV 중복 6개 묶음을 확인했습니다. 기준 입력과 가공 입력,
  여러 분석 조건에서 우연히 같게 나온 검증 결과입니다. 경로와 분석 조건을 보존해야 하므로 제거하지 않았습니다.
- 모델·원자료·브랜드 원본·평가·출처·라이선스·설정·로컬 백업은 보존했습니다.
- `backend/db/connection.py`의 환경설정 초기화 import, 서버의 외부 호환 export,
  `pipelines/db1/database.py`의 DB 예외 export는 단순 미사용 검사만으로 제거하지 않았습니다.
- 독립 실행·검증·재사용 분석 도구는 웹 화면에서 직접 import하지 않는다는 이유만으로 제거하지 않았습니다.
- 긴 CSS·App 파일의 분할, DB 스키마 변경, 대규모 폴더 통합은 이번 범위에 포함하지 않았습니다.
- `toast.jsx`의 `Toaster`는 현재 화면에 마운트되지 않지만 `Workspace.jsx`에 알림 발송 코드가 남아 있습니다.
  발송·표시가 끊긴 기능 문제일 수 있으므로 이 파일을 자동 삭제하지 않았습니다. 알림 표시 복원은 별도 기능 변경입니다.

## 검증

| 확인 | 결과 |
|---|---|
| `python scripts/audit_repository.py` | Python 문법 오류·프런트엔드 import 누락·미참조 프런트엔드 모듈·동일 텍스트 파일 0건 |
| `npm run build` | 통과. 기존 500kB 초과 번들 경고 있음 |
| 프런트엔드 진입점 참조 탐색 | `main.jsx`에서 도달하지 못하는 소스 모듈 0개 |
| 기존 로컬 검사 중 외부 연결 없는 범위 | 33개 통과. 지역·기간·연령 문맥, AI 끔, 제공사 실패 안내, 화면 요약, 출처·분석 설명 검사 |
| 실제 원자료 전처리 | 통과. 강남구 22개 동 입력·프로필·메타데이터 생성 |
| 서버·게시 모듈 import | 통과. 기존 `/api/chat/v16` 주소가 새 처리 모듈에 연결됨 |
| `git diff --check` | 통과 |

로컬 검사 실행기는 `.tmp/check_cleanup_20261020.py`, 구조 비교는
`.tmp/cleanup-20261020-comparison.json`, 전처리 결과는 `.tmp/cleanup-20261020-preprocessing/`에 있습니다.
공유 DB를 읽는 더 넓은 대화 검사와 다른 제공사 검사 1개는 대기가 길어 중단·제외했습니다.
관리자 설정 읽기는 테스트에서 고정했습니다. 전체 테스트, 실제 공유 DB 게시·대화,
외부 AI 및 배포 UI의 정상 동작을 검증한 것은 아닙니다.

## 문서 통합 후속 작업 (2026-10-20)

- 폴더 구성·코드 읽기 안내를 `docs/development-guide.md`로 통합했습니다.
- PostgreSQL 저장소·DB1 서비스 통합 안내를 `docs/data-operations.md`로 통합했습니다.
- 보고서 에이전트·템플릿 명세를 `docs/report-guide.md`로 통합했습니다.
- 과거 계획·이관·정리·수정 명세는 `docs/history/`로 모았습니다. 분석·출처·평가 자료는 원래 분석 영역에 보존했습니다.
- MD 파일은 저장소 전체 70개에서 67개, `docs/` 최상위는 16개에서 8개로 줄었습니다.
- 문서 목차를 읽는 순서로 바꾸고, 전체 MD의 상대 링크·제목 앵커를 검사했습니다.
- 전달본 검사와 원자료 재계산의 차이, 보고서 작성 조건, 템플릿 위치·해시,
  수집 테스트 경로·예약 작업 시간대 검사, 초기 OCI 도구의 이전 범위를 현재 소스로 확인했습니다.
- 문서만 수정했습니다. 공유 DB 반영·수집·예약 작업 등록·인프라 이전·Word 렌더를 실행한 것은 아닙니다.
