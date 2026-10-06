# 복지탐정 WELFIND

지역·인구집단의 행동 변화 근거를 확인하고 복지사업 검토와 보고로 연결하는 Streamlit 대시보드입니다. 개인의 사회적 고립을 판정하지 않습니다.

## 실행

Python 3.13 환경에서 `python -m pip install -r requirements.txt`로 준비합니다.

```powershell
python main.py
python main.py --chatbot
python main.py --chatbot-cli
python main.py --analysis --no-download
python main.py --preprocess-analysis1 --raw-dir "원본폴더"
python main.py --preprocess --no-download
python main.py --risk --input "월별행동.csv"
```

대시보드는 보관된 version11 Analysis2 결과를 읽습니다. `--analysis`는 전처리와 Analysis2를 다시 실행합니다. `--risk --input`은 기존 v1 월별 입력 분석을 유지한 별도 도구입니다. DB2 사업 조회에는 루트 `.env`의 DB 연결 설정이 필요합니다. 키와 개인 업로드 자료는 커밋하지 않습니다.

## 폴더 안내

| 폴더 | 역할 |
| --- | --- |
| `dashboard/` | 화면, 컴포넌트, 업무 대화상자, 보고서 |
| `chatbot/` | 시작 메뉴, 근거 설명, 데이터 질의, 독립 실행 화면 |
| `agents/` | Analysis2, v1 분석 도구, 복지사업 매칭 |
| `preprocessing/` | 지역 유형·월별 행동 자료 전처리 |
| `db/` | 공통 PostgreSQL 연결, 로컬 SQLite 업무 기록 |
| `ci/` | 브랜드 가이드, 투명 로고·캐릭터, 컬러 팔레트 |
| `docs/` | 사용자 안내와 변경 이력 |
| `external/` | 공모전 참고 자료 |

## 화면과 AI 동작

브랜드 기본색은 `#2563EB`, 보조색은 `#60A5FA`, 연결 강조색은 `#10B981`, 텍스트는 `#1E293B`입니다. 지도는 원래 행정 경계를 유지하며 마우스·키보드로 지역을 강조합니다. 장식 높이는 분석 수치가 아닙니다.

챗봇 메뉴 선택, 저장된 결과 확인, 기본 근거 안내는 AI를 호출하지 않습니다. ‘AI 에이전트 사용’을 켠 뒤 질문을 보낼 때만 호출을 허용합니다. 서버도 명시적인 호출 조건을 확인하며, Gemini 설정이 없으면 규칙 기반 안내를 제공합니다. `.env`의 `GEMINI_API_KEY`, `GEMINI_MODEL`로 연결합니다.

이전 `dashboard/data/mission_records.sqlite3`가 있으면 최초 실행 시 `db/runtime/`로 복사 이관하며 원본을 보존합니다.

[화면 수정 안내](dashboard/README.md) · [정리 및 검증 기록](docs/2026-10-06_대시보드_정리.md)
