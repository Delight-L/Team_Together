# 폴더 구성과 작업 위치

화면은 `frontend`, 웹 서비스는 `backend`, 데이터 준비·분석은 `pipelines`에서 작업합니다.
프로젝트 루트에서 `python main.py`로 실행하는 방식은 유지합니다.

```text
Team_Together/
├─ frontend/                 React 화면·화면 테스트
├─ backend/
│  ├─ api/                   HTTP API·로그인·관리자·업무·대화 요청
│  ├─ chatbot/               보미 대화·가드레일·AI 연결
│  │  └─ welfare/app/dialogue/  복지사업 검색과 대화 처리
│  ├─ agents/                총괄·보고서 작성·사업 매칭
│  │  └─ regional_v16/       v16 지역 변화 신호 에이전트(근거 DB는 git 제외)
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
├─ docs/                     팀 문서·아키텍처·외부 참고자료
├─ scripts/                  실행·이관·정기 수집 도구
├─ deploy/                   배포 설정
├─ runtime/                  로컬 실행 로그
└─ main.py                   공통 실행 시작점
```

## 기존 폴더는 어디로 갔나요?

| 기존 위치 | 새 위치 |
|---|---|
| `frontend/` | 동일 |
| `webapp/` | `backend/api/` |
| `chatbot/` | `backend/chatbot/` |
| `chatbot/welfare/app/agent/` | `backend/chatbot/welfare/app/dialogue/` |
| `agents/supervisor.py`, `report_writer.py`, `service_matching.py` | `backend/agents/` |
| `agents/regional_analysis/` | `pipelines/regional_analysis/` |
| `agents/regional_analysis/chatbot_v16/` (shinwon 브랜치) | `backend/agents/regional_v16/` (DB1 복사본·단독 서버는 정리하고 `pipelines/db1` 사용) |
| `agents/risk_analysis/` | `pipelines/risk_analysis/` |
| `db/` | `backend/db/` |
| `db/collect_welfare.py` | `pipelines/welfare/collect.py` |
| `DB1/` | `pipelines/db1/` |
| `preprocessing/` | `pipelines/preprocessing/` |
| `shared/accounts.py`, `shared/report.py` | `backend/services/` |
| `shared/data/` | `backend/resources/data/` |
| `docs/약식보고서_서식_보고서.docx` | `backend/resources/templates/약식보고서_서식_보고서.docx` |
| `ci/` | `assets/brand/` |
| `external/` | `docs/references/` |

`backend/db`는 DB를 읽고 저장하는 코드이고, `pipelines/db1`은 분석 결과를 만드는 코드입니다.
PostgreSQL의 `db1`, `db2`, `work` 스키마 이름과 테이블은 폴더 이동과 관계없이 유지합니다.
보미 총괄은 `backend/agents/supervisor.py`, 복지 대화 처리는 `backend/chatbot/welfare/app/dialogue/`에 있습니다.

## 자료 보존 기준

이번 정리는 파일 이동과 경로 수정입니다. 기존 분석 코드·모델·입력·검증 결과는 삭제하지 않습니다.
분석 내부의 `data`, `models`, `outputs`는 실행·재현 경로를 유지하기 위해 해당 파이프라인에 보관합니다.
Analysis2 구현은 `pipelines/db1/Analysis2` 하나입니다. `python main.py --preprocess` 증분 갱신도 이 폴더의 `run_analysis2.py`(전체 기간 일괄 실행)를 호출합니다.
예전 복사본(`pipelines/regional_analysis/Analysis2`)은 2026-10-16에 정리했습니다. 같은 feature table로 실행한 탐지 결과·근거 카드가 바이트 단위로 같음을 확인했습니다.
다만 통합본은 입력 검증이 더 엄격해(이력 검증, Analysis1 지역 유형 누락 검사) 앞으로 들어올 자료에 문제가 있으면 예전보다 일찍 멈출 수 있습니다.

v16 지역 변화 신호 에이전트(`backend/agents/regional_v16`)는 답변 근거로 `outputs/db1.sqlite`(약 100MB, git 제외)를 읽습니다.
다른 위치에 둘 때는 `DB1_DATABASE_PATH`로 지정하고, 파일이 없으면 보미가 기존 지역 분석 담당으로 답합니다.
이 DB를 새로 만드는 작업기도 `pipelines/db1`의 분석 코드를 그대로 씁니다.

루트 `.env`, 가상환경 `.venv`, `frontend/node_modules`는 계속 같은 위치를 사용합니다.
관리자 AI 설정은 공유 PostgreSQL `work.app_settings`에 보관합니다(배포 서버 재시작 후에도 유지).
`TEAM_TOGETHER_DATA_ROOT`는 저장소와 같은 자료 배치를 가진 기준 폴더를 지정합니다.
지역 유형 원자료의 상대 위치는 `pipelines/preprocessing/regional_types/raw_data`입니다.

## 팀원 실행 방법

1. 변경이 반영된 브랜치를 받아 주세요.
2. `frontend`에서 `npm ci`, `npm run build`를 실행합니다. 의존성을 추가하거나 변경할 때는 `npm install`을 사용하며, `package-lock.json`도 함께 저장합니다.
3. 프로젝트 루트에서 기존 Python 서버를 종료하고 `python main.py`를 다시 실행합니다.
4. 과거 명령의 Python 모듈 경로를 새 경로로 바꿉니다.

```powershell
python main.py
python main.py --analysis --no-download
python main.py --preprocess-analysis1 --raw-dir "pipelines/preprocessing/regional_types/raw_data"
python -m pipelines.welfare.collect --help
python pipelines/db1/run_db1.py --help
python -m pytest backend/api/tests backend/db/tests backend/chatbot/tests -q
```

DB1의 개별 분석 테스트는 서로 같은 이름의 내부 모듈을 사용하므로,
`pipelines/db1/run_tests.ps1`처럼 분석별 폴더에서 별도 프로세스로 실행합니다.
`pipelines/db1/outputs/db1.sqlite`가 `version https://git-lfs.github.com/spec/v1`로 시작하면
실제 SQLite가 아닌 전달 포인터입니다. 해당 파일이 필요한 테스트는 실제 DB 전달본을 받은 뒤 실행해야 합니다.

## 폴더별 문서 찾기

README는 [프로젝트 루트](../README.md), [frontend](../frontend/README.md), [backend](../backend/README.md), [pipelines](../pipelines/README.md), [DB1](../pipelines/db1/README.md), [docs](README.md)에 둡니다. 작은 하위 폴더의 실행·출처·검증 설명은 해당 영역 README의 목차에서 찾습니다. 상세 설계·검증 기록은 기존 이름의 문서로 보존합니다.
