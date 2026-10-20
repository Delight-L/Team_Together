# 코드·파일 정리 기록 (2026-10-19)

작업 기준은 `HyungWoo_React`의 `3d83955`입니다. 프런트엔드·백엔드·파이프라인·실행 도구·문서의
Git 관리 파일과 신규 소스를 조사했습니다. 기능 수정과 대규모 파일 재배치를 섞지 않고,
참조가 없는 코드·중복·현재 안내와 맞지 않는 과거 자료를 정리했습니다.
커밋·push·배포 및 공유 DB 자료 변경은 이번 작업에 포함하지 않습니다.

## 정리한 코드

| 대상 | 처리 | 근거 |
|---|---|---|
| `frontend/src/AnalysisReview.jsx` | 제거 | 현재 화면 소스에서 import·참조하지 않음 |
| `frontend/src/ChatResizer.jsx` | 제거 | 현재 화면 소스에서 import·참조하지 않음 |
| `frontend/src/ReferenceServices.jsx` | 제거 | 현재 사업 매칭 화면에서 사용하지 않는 옛 목록 컴포넌트 |
| `frontend/src/ReportMaterials.jsx` | 제거 | 현재 보고서 화면에서 사용하지 않는 옛 선택 컴포넌트 |
| `frontend/src/chartScale.mjs` | 제거 | 현재 그래프에서 import하지 않는 예전 범위 계산 |
| `frontend/src/regionDirectory.mjs` | 제거 | 현재 목록에서 import하지 않는 예전 정렬 함수 |
| 복지 검색 `compact` | `query_rules.py` 한 곳으로 통합 | `named_program` 내부와 `resources.py`에 같은 정규화가 중복됨. `resources.compact` 접근은 유지 |
| 복지 자료·DB 검색·검색 조건의 서울 날짜 계산 | `backend.common.seoul_now` 재사용 | 각 모듈의 `datetime`·`ZoneInfo` 중복 제거, 시간대와 비교 방식 유지 |
| 지역 분석 엔진 import | 미사용 `pandas`, `AGE_LABEL`·`CORE`, `OUT_OF_SCOPE` 정리 | 해당 모듈에서 사용하지 않음 |
| SSE 이벤트 목록 | 10종을 한 튜플로 선언 | 기존 이벤트 이름·순서·값 유지 |
| `frontend/package.json` | 오래된 테스트 실행 별칭 2개 제거 | 테스트는 Git 제외이며 `briefing.test.mjs`도 현재 저장소에 없음. 로컬 파일의 직접 실행 방법은 문서에 명시 |

제거한 미사용 프런트엔드 모듈은 총 204줄입니다. 소스와 동적 import를 조사했고,
전체 빌드 결과의 번들 이름·크기도 정리 전과 같았습니다. 기존 Git 이력에서 복구할 수 있습니다.

## 파일 이동·문서 통합

| 기존 위치 | 현재 위치·처리 |
|---|---|
| 루트 `챗봇.md` | [과거 챗봇 코드 안내](history/chatbot-guide-legacy.md) |
| 루트 `CHANGES_2026-10-16.md` | [당시 변경 기록](history/changes-2026-10-16.md) |
| `evaluation/run_eval.py` | `evaluation/legacy/run_eval.py` |
| `evaluation/prepare_dataset32.py` | `evaluation/legacy/prepare_dataset32.py` |
| `evaluation/import_dataset.py` | `evaluation/legacy/import_dataset.py` |
| 평가 `results/human_review/`의 중복 요약 | `results/`의 원본 본문으로 연결. 사용자 리뷰는 보존 |
| DB1 `docs/`의 중복 과거 검증 보고서 | `outputs/validation/retrospective_20261007/`의 원본으로 연결 |

평가 실행기 3개는 제거된 이전 파일 저장소 서비스·세션 모듈 또는 개발자 PC의 별도 자료 경로에 의존했습니다.
이를 현재 서비스의 실행 도구와 구분하고 원본은 보존했습니다.
[평가 안내](../backend/agents/regional_analysis/evaluation/README.md)에서 현재 사용할 수 있는
데이터셋 검증·보고서 변환 명령만 안내합니다. 현재 PostgreSQL 서비스용 평가 실행기를 구현한 것은 아닙니다.

루트·프런트엔드·백엔드·파이프라인 README와 폴더·챗봇 구조 문서도 실제 경로에 맞췄습니다.
테스트가 새 checkout에 포함된다는 설명과 v16이 서비스 이전 파일 저장소를 읽는다는 설명을 고쳤습니다.

## 재실행 가능한 파일 검사

```powershell
python scripts/audit_repository.py
python scripts/audit_repository.py --output .tmp/repository-audit.json
```

검사 도구는 Git에서 보이는 파일을 읽어 Python 문법, 프런트엔드 로컬 import,
미참조 모듈 후보, 동일한 텍스트 파일, 큰 소스 파일을 출력합니다.
파일을 이동·삭제하거나 DB에 연결하지 않습니다. `--output`은 지정한 JSON만 기록합니다.
미참조 후보는 동적 사용·실행 진입점 확인이 필요한 조사 결과이며 자동 삭제 대상이 아닙니다.

정리 후 검사 대상에서 Python 문법 오류·프런트엔드 import 누락·미참조 모듈 후보·동일 텍스트 파일은 모두 0건입니다.
이는 원자료·바이너리·무시된 로컬 파일의 중복이나 모든 실행 경로의 정상 동작을 보증하는 수치는 아닙니다.

## 검증

| 검사 | 결과 |
|---|---|
| 전체 프런트엔드 빌드 | 통과. 기존 번들 이름·크기와 동일. 큰 번들 경고는 기존과 동일 |
| Python 문법·로컬 프런트엔드 import | 오류 0건 |
| 로컬 HTTP `/api/health` | 200, `status=ok`, `frontendBuilt=true` |
| 정리 전후 문자열 정규화·고유 사업명 판별 | 31건 출력 동일 |
| 날짜 경계·복지자료 변환 | 12건 출력 동일 |
| 평가 데이터셋 형식 검사 | 32개 유효. 답변 정확도 검증과는 별개 |
| 에이전트·DB2 비교 테스트 | 133개 통과, 43개 건너뜀, 기존과 동일한 11개 실패. 새로운 실패 식별자는 없음 |

비교 테스트는 로컬에 남아 있던 `backend/bomi/tests`와 `backend/db/tests/test_welfare_chatbot_repository.py`입니다.
제거된 `backend.agents.v16_service`를 import하는 과거 `test_mobility_direction_explanation.py`는
수집 단계부터 실패하는 옛 검사라 비교 실행에서 제외했습니다. 테스트 파일을 Git에 다시 추가하지 않았습니다.

## 기존 실패 11개와 별도 기능 작업

이번 구조 정리로 아래 문제를 해결했다고 주장하지 않습니다.

| 실패 검사 | 개수 | 남은 확인 |
|---|---:|---|
| 저장소 밖 SQL 검사 | 1 | 새 `dashboard_repository.py`도 저장소 구현인데 기존 허용 목록에 없음 |
| 이벤트 개수 검사 | 1 | 기존 9종 대신 현재 `conversation`을 포함한 10종 계약으로 검증해야 함 |
| 출력 안전 검사 | 2 | 복지 응답·보고서 생성 선행 조건을 현재 계약으로 재현하고 moderation 경로 검증 필요 |
| 보고서 생성 | 2 | 제거된 `RESOURCES` 참조, 현재 근거·업무 기록 계약과 `reportDraft` 생성 조건 확인 필요 |
| 지역 설명 문장 | 1 | 의미가 아닌 특정 문장을 기대하는 기존 검사와 현재 설명의 적합성 구분 필요 |
| 복지 검색·AI 전달 자료 | 2 | 다른 지역 사업의 참고 추천은 허용된 동작입니다. 지역·이용 조건 구분과 새 표현 자료 구조를 검증해야 함 |
| DB2 검색·캐시 | 2 | 임시 이전 파일 저장소 fixture와 새 PostgreSQL catalog 검색 경로의 차이를 분리해 검증 필요 |

특히 지역 범위, 안전 검사, 보고서 근거 전달은 테스트 기대값만 바꾸어 통과시킬 문제가 아닙니다.
재현 입력과 실제 데이터 흐름으로 별도 수정·검증해야 합니다.

## 보존·범위

- 원자료, 모델, 라이선스·출처, 분석 결과, 기존 평가와 사용자 리뷰, 로컬 설정·stash는 유지했습니다.
- `main.py` 및 웹·분석·전처리·수집 진입점과 배포 설정은 유지했습니다.
- `App.jsx`와 큰 CSS 파일을 무리하게 분할하거나 전역 포맷을 바꾸지 않았습니다.
  현재 기능 문제를 먼저 분리한 뒤 책임별 분할과 스타일 정리를 검토하는 편이 안전합니다.

## 후속 저장소 전환

위 테스트 수치는 구조 정리 당시의 기록입니다. 이후 분석·전처리를 PostgreSQL로 전환했고,
호환되지 않는 구 저장소 테스트·종속 파일은 원문과 해시를 확인해 `db1_regional_archive.source_archive`에 보존했습니다.
현재 전환의 검증 범위는 [PostgreSQL 이관 기록](postgresql-migration-2026-10-19.md)을 참고하세요.

## 추가 정리: 로컬 임시 파일·브랜드 이미지·Python 가독성

아래는 앞선 정리 이후 사용자 승인으로 진행한 추가 작업입니다.

| 대상 | 처리 |
|---|---|
| 과거 렌더링용 브라우저 프로필 4개 | `.tmp` 안의 경로·하위 링크 여부를 검사하고 393개 파일, 약 64.52MiB 제거 |
| 화면 확인 이미지·로그 113개 | 로컬 `output/archive/2026-10-19/screenshots-and-logs.zip`으로 압축. 원래 경로와 SHA-256을 `manifest.json`에 기록하고 압축 내부 내용의 해시까지 확인한 후 원래 파일 제거 |
| 비어 있는 생성물 폴더 7개 | 이미지 보관 이후 비어 있는 렌더링·미리보기 폴더 제거 |
| 브랜드 보관 원본 | PNG 5개·PPTX 1개를 `assets/brand/source/`로 이동. 서비스용 로고·캐릭터 경로 유지 |
| `frontend/src/assets/bomi-tablet.png` | 소스·문서·실행 도구의 참조가 없는 이미지 제거. Git 이력으로 복원 가능 |
| Python 64개 파일 | 한 줄 조건문·예외 처리 등 588개 블록과 세미콜론 구분 521곳을 펼침. 파일별 변경 전후 AST 동일 확인 |
| `chatbot_agent/repository.py` | 별도로 압축 문장·긴 표현식을 펼치고 `frame`, `row`, `quarter`, `observation_window`, `query_cache` 등 역할이 드러나는 이름과 한국어 설명 적용 |
| [코드 읽기 안내](code-reading-guide.md) | 실행 시작점 → API → 보미 → DB 조회를 읽는 순서와 앞으로의 가독성·삭제 기준 추가 |

가독성을 손본 Python 파일은 총 65개입니다. 64개는 문장 배치만 바꿨고,
DB 조회 파일 1개는 동작 비교를 동반하여 이름과 표현식도 정리했습니다.
기존 함수의 진입점·분석 계산식·SQL 조건·정렬 기준을 유지하는 범위입니다.
모든 클래스·비동기 처리·분석 알고리즘을 초급 문법으로 다시 설계한 작업은 아닙니다.

`.tmp`의 DB 덤프·백업·설정·이관 기록, 분석 원자료·모델·그래프, 테스트 원본은 보존했습니다.
특히 `.tmp`에는 복구 자료도 있으므로 폴더 전체 삭제 대상으로 취급하지 않습니다.
압축본과 비교 검증 자료는 Git 제외인 로컬 파일입니다.

### 이번 추가 작업의 검증

- 64개 파일: 문장 배치 변경 전후 AST 동일.
- DB 조회: 가짜 DB를 이용한 580개 비교 통과. 표 값·순서, SQL·인자, 빈 결과, 없는 동,
  월 경계, 결측 신호, 캐시 재사용, 예외 후 정리, 소비 필터, 보조 조회를 비교. 외부 연결 없음.
- 기존 테스트: 저장소 설정 위치 1개와 v16의 AI 끔·명시적 지역/기간 범위 검사 2개, 총 3개 통과.
- 저장소 정적 검사: Python 문법 오류·프런트엔드 import 누락·미참조 모듈 후보·동일 텍스트 파일 0건. `git diff --check` 통과.
- 이동한 브랜드 원본 6개의 SHA-256이 Git 원본과 같음을 확인.
- 프런트엔드 빌드 통과. 500kB 초과 번들 경고 있음.
- 전체 테스트 통과를 의미하지 않음. 더 넓은 로컬 v16 테스트 실행은 완료가 지연되어 중단하고,
  이번 변경에 필요한 외부 연결 없는 비교와 위 3개 테스트로 검증 범위를 좁힘.

변경 전 원본·비교 스크립트·결과는 `.tmp/readability-20261019/`에 보관합니다.
압축본은 Python `zipfile` 또는 일반 압축 프로그램으로 열 수 있으며,
프로젝트 루트 기준으로 압축을 풀면 원래 상대경로를 복원할 수 있습니다.
실수로 기존 파일을 덮어쓰지 않도록 먼저 별도 폴더에 풀어 확인하세요.
커밋·push·배포와 DB 변경은 수행하지 않았습니다.
