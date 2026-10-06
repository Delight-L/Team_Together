# WELFIND React 실행 안내

이 브랜치는 React + Vite 화면과 Python HTTP API를 사용합니다. Python 전처리·Analysis2·챗봇·사업 매칭·SQLite 업무 기록은 기존 모듈을 재사용합니다. 서버는 로컬 시연용이며 `127.0.0.1`에만 바인딩합니다.

## 최초 설치

프로젝트 루트에서 Python 가상환경을 준비한 후:

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
cd frontend
npm install
npm run build
cd ..
.venv/Scripts/python.exe main.py
```

Node.js 22.12 이상을 권장합니다. pnpm 사용 시 `pnpm install`, `pnpm run build`를 사용합니다. pnpm lockfile을 포함하며 esbuild의 설치 스크립트만 허용합니다.

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

터미널 2: `frontend`에서 `npm run dev`

http://127.0.0.1:5173 에서 화면을 개발합니다. Vite가 API와 브랜드 이미지를 Python 서버(8503)로 전달합니다. 빌드 후에는 Python 서버 하나가 화면과 API를 함께 제공합니다. 프런트엔드 변경 후 빌드를 다시 실행하세요.

## 화면과 동작

- 메인 화면: 뷰포트 높이 안에 요약·지도·상세·주요 변화를 배치합니다. 본문 전체는 스크롤하지 않습니다. 긴 상세와 채팅 내용은 패널 내부에서 스크롤합니다.
- 종합 현황: 요약 카드·입체 지도·후보 핀·주요 변화를 표시합니다. 지역 현황은 전체 동 검색·상태 필터·정렬과 평면 지도 중심으로 구성합니다.
- 지역 상세: 동 클릭 시 지도 내부 옆에 REGION INSIGHT가 열립니다. 선택 지역은 챗봇과 공유합니다. 로고를 클릭하면 메뉴를 접고 펼치며, 접힌 상태에는 보미 얼굴이 표시됩니다.
- 챗봇: 지역별 업무 진행 영역을 제거했습니다. 지도/분석/챗봇에서 지역과 기준월을 공유하며, 응답의 ‘분석 근거 보기’로 분석 화면을 엽니다. 지역·월 변경 시 이전 질의 요청을 취소하고 대화를 초기화합니다.
- 보미: 평소에는 정지 이미지, 답변 처리 중에만 전달받은 동작 GIF를 표시합니다. 사용자 OS의 동작 줄이기 설정을 따릅니다. 답변은 완성 후 표시하며 실제 토큰 스트리밍은 아직 사용하지 않습니다.
- 업무: 분석 확인 저장 → 근거 검토 완료 → 실제 DB2 사업 조회·검토 기록 → Word 초안 생성·다운로드 확인 → 최종 저장. 기존 SQLite의 단계 검증을 재사용합니다.
- 업무 현황: 담당자의 저장된 지역·월별 업무를 다시 열어 진행합니다. 챗봇 안의 진행 영역은 제거하고 독립 메뉴로 제공합니다.
- 관리자 데이터: CSV/XLSX 검사·미리보기·DB1 반영, DB1 활동 이력 조회를 연결했습니다. DB1 반영은 화면에 사용하는 저장소 CSV를 자동 교체하지 않습니다.
- 기본 주제 버튼은 AI 호출 없이 저장 자료와 안내문으로 응답합니다. 자유 입력은 총괄 AI가 지역 분석·사업 매칭·보고서·업무 안내 에이전트를 선택하고 담당 에이전트가 답변합니다. 자유 입력에만 Gemini를 호출하며 `.env`의 `GEMINI_API_KEY`, `GEMINI_MODEL`이 필요합니다. DB2 조회에는 기존 DB 연결 설정이 필요합니다. 키는 프런트엔드에 노출하지 않습니다.

## 전환 범위

기존 기본 메뉴의 React 메인 화면·지역 분석·업무 현황·사업 검토·보고서·챗봇·관리자 데이터 반영·DB1 활동 이력을 연결했습니다. 별도 도구의 전년 동월 현장 대응 화면은 기본 메뉴와 별개이며 이 React 화면에 포함하지 않습니다. 비교용 기존 Streamlit 화면은 `python main.py --streamlit`로 실행할 수 있습니다. 원본 Streamlit 브랜치는 변경하지 않습니다.

기존 업무 저장 DB는 `db/runtime/mission_records.sqlite3`이며 Git에서 제외합니다. 새 PC에서 개인 업무 기록이 필요하면 별도 전달하세요. React 챗봇 대화는 화면 세션 안에서만 유지되며 업무 질의 기록으로 자동 저장하지 않습니다.

공유 상태 설계는 [React 공식 문서](https://react.dev/learn/sharing-state-between-components)를 따릅니다.

팀원이 수정할 위치와 오류 확인 순서는 [React 팀원 수정 가이드](docs/React_팀원_수정_가이드.md)에 정리했습니다. 핵심 파일에 한국어 설명 주석을 넣었습니다.

## 검증

```powershell
cd frontend
npm run build
cd ..
.venv/Scripts/python.exe -m unittest discover -s webapp/tests -v
```

API 검사는 실제 분석 CSV를 읽고 임시 SQLite DB에서 로그인·지역 접근·챗봇 근거·업무 순서·Word 초안과 최종 저장을 검사합니다. DB2 경계는 테스트 사업으로 대체하며 실제 DB 쓰기와 Gemini 호출은 하지 않습니다.

