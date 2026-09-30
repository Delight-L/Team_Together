# Team Together · 고립예방 대시보드

지자체별 사회적 고립 위험도를 살펴보는 Streamlit 시연용 대시보드입니다.
`dashboard/isolation-dashboard_260921.html`의 디자인을 적용했으며,
Python으로 CSV를 읽어 지도·상세 카드·추이·순위·대상자 목록에 연결합니다.

## 실행하기

Python 3.10 이상을 준비한 뒤 저장소를 내려받아 실행합니다.

```bash
git clone --branch docoup3 --single-branch https://github.com/Delight-L/Team_Together.git
cd Team_Together/dashboard
python -m venv .venv
```

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
Windows에서는 최초 설치 후 `dashboard/run_dashboard.bat`를 더블클릭해 실행할 수도 있습니다.
가상환경은 저장소에 포함하지 않으므로 각 컴퓨터에서 처음 한 번 만들어야 합니다.

## 시연 계정

| 소속 | 아이디 | 비밀번호 |
|---|---|---|
| 강남구 | gangnam01 | demo1234 |
| 춘천시 | chuncheon01 | demo1234 |
| 전체 관리자 | admin | admin1234 |

모든 계정·대상자·위험 점수는 시연용입니다. 로그인은 실제 서비스 인증 기능이 아닙니다.

## 구성

- `dashboard/main.py`: 데이터 연결 및 실행 시작점
- `dashboard/settings.py`: 데이터 경로, 기본 가중치, 위험 기준
- `dashboard/data_utils.py`: CSV 읽기, 입력 검사, Python 계산 함수
- `dashboard/data/`: 위험 요인 CSV, 가상 대상자 CSV, 지도 경계
- `dashboard/ui/`: 원본 디자인과 메뉴·지도·그래프·챗봇 동작
- `dashboard/main_native.py`, `dashboard/charts.py`: Streamlit 기본 위젯 학습용 버전

새 데이터를 추가하거나 시각화를 바꾸는 방법은 [대시보드 사용안내](dashboard/사용안내.md)를 참고하세요.
실행과 데이터 변경 위치에 파트별 한국어 주석을 달았습니다.

## 확인

`dashboard` 폴더에서 실행합니다. 디자인 검증 도구의 JavaScript 계산 비교에는 Node.js가 필요합니다.

```powershell
.\.venv\Scripts\python.exe verify_design.py
.\.venv\Scripts\python.exe verify_dashboard.py
```

디자인 검증에는 초기 샘플 데이터와 원본 계산 결과를 비교하는 검사가 포함됩니다.
실제 자료로 교체하면 해당 검사의 기대값도 함께 수정해야 합니다.

현재 로그인·챗봇·로그는 시연용이며, 실제 인증·DB 저장·AI 서비스 연결은 포함하지 않습니다.
