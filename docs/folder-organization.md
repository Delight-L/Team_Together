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
│  ├─ db/                    공유 DB 연결·조회·저장
│  ├─ services/              계정·Word 보고서 생성
│  └─ resources/             지도 자료·보고서 서식
├─ pipelines/
│  ├─ db1/                   Analysis1·2·3·맥락 분석·검증·모델
│  ├─ preprocessing/         공통 전처리·재현 코드
│  ├─ regional_analysis/     DB1 실행·서비스 반영 연결과 기존 Analysis2 자료
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
기존 Analysis2 구현은 `pipelines/regional_analysis/Analysis2`에 보존하며,
현재 통합 실행기는 `pipelines/db1`을 호출합니다. 두 구현의 통합·삭제는 별도 검증 후 결정합니다.

루트 `.env`, 가상환경 `.venv`, `frontend/node_modules`는 계속 같은 위치를 사용합니다.
관리자 AI 설정은 `backend/db/runtime/ai_settings.json`에 보관하며 Git에서 제외합니다.
`TEAM_TOGETHER_DATA_ROOT`는 저장소와 같은 자료 배치를 가진 기준 폴더를 지정합니다.
지역 유형 원자료의 상대 위치는 `pipelines/preprocessing/regional_types/raw_data`입니다.

## 팀원 실행 방법

1. 변경이 반영된 브랜치를 받아 주세요.
2. `frontend`에서 `pnpm install`, `pnpm run build`를 실행합니다. 잠금 파일이 있는 배포본에서는 설치에 `--frozen-lockfile`을 사용합니다.
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
