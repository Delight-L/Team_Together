# Team Together 대시보드 작업 현황

강남구의 **지역·집단 단위 활동·소통 변화**를 살피고, 변화가 나타난 동에 대해 2025년 지원사업 계획을 검토하는 담당자용 Streamlit 대시보드입니다. 개인의 고립 여부를 판정하지 않습니다.

## 현재 구현된 흐름

```text
2024·2025년 동별 월간 집계
  → 같은 동의 전년 동월 변화 탐지
  → 2025년 정책 문서의 지역·기간·신호 대조
  → 사업 후보와 제외 이유·문서 쪽수 표시
  → 담당자 현장 확인
  → 같은 동·월의 2025년 결과보고 실적 확보 후 대조
```

마지막 결과보고 실적 대조 단계는 자료를 기다리고 있습니다. 현재 화면의 `검증자료 대기`는 실적이 0이라는 뜻이 아닙니다.

## 지금까지 반영한 작업

| 단계 | 구현 내용 | 현재 상태 |
|---|---|---|
| 동별 변화 탐지 | 2024년과 2025년의 같은 동·같은 달을 비교해 소통 적음, 평일·휴일 외출 적음, 결합 비율 변화를 표시 | 2025년 12개월 × 비교 가능한 21개 동 |
| 탐지 단계 | 소통·외출·결합 지표의 동시 악화를 확인하고 결합 비율 변화 기준으로 `우선 검토`, `전년 동월 변화`, `조건 미충족` 구분 | 현장 확인 순서이며 개인 판정 또는 모델 정확도가 아님 |
| 정책 계획 연결 | 강남구 2025년 공식 계획의 `세곡동행`, `스마트 안부확인`, `동별 사회관계망 형성사업`을 동·월·변화 신호와 대조 | 252개 동·월 × 3개 사업 = 756개 판정, 후보 31건 |
| 근거 표시 | 사업 후보 및 제외 이유와 문서명·PDF 쪽수, 담당 기관, 확인 절차 표시 | 계획 근거이며 운영·접수·효과는 미확인 |
| 대시보드 | `실측 변화 탐지` 화면과 `대응·서비스 추천` 아래 실측 영역 추가 | 기존 시연용 폼은 상단에 유지 |
| 챗봇 | 선택한 동·월 또는 질문에 적힌 동·월의 탐지 값, 사업 근거·제외 이유, 검증자료 상태 설명 | 규칙 기반 자료 안내. 외부 AI 모델이나 복지사업 DB 조회는 연결 전 |
| 결과보고 실적 | 2025년 동·월별 실적 입력 구조와 가져오기 도구 준비 | 실제 실적 0/252건 확보, 화면에는 `검증자료 대기` 표시 |

`개포3동`은 원본 0값과 행정동 명칭·코드 확인 전까지 실측 탐지에서 제외했습니다. 2025년 12월은 21개 동 모두에서 통화·이동 감소가 나타나 공통 원인 확인이 필요합니다.

## 자료의 시점과 해석

| 자료 | 화면에서 쓰는 곳 | 해석 |
|---|---|---|
| `dashboard/data/two_year_dong_metrics.json` | 실측 변화 탐지·대응 | 2024~2025년 동별 원본 집계 재계산. 전년 동월 비교에 사용 |
| `dashboard/data/gangnam_policy_plans_2025.json` | 관련 지원사업 | 2025년 정책 문서의 **계획**. 실제 운영이나 개인 자격을 보증하지 않음 |
| `dashboard/data/policy_recommendation_audit_2025.json` | 사업 후보·제외 근거 | 252개 동·월과 사업 3개를 전수 대조한 결과 |
| `dashboard/data/validation_actuals_2025.json` | 결과보고 실적 대조 | 현재 `records`가 비어 있음. 2025년 같은 동·월의 실적을 받은 뒤 입력 |
| `dashboard/data/risk_factors.csv`, `group_signals.json` | 종합 현황·동별 분석 및 대응 화면 상단 | **2026년 화면 시연용 집계**. 2025년 실측 탐지와 합산하지 않음 |

정책 카드의 추천은 **현장 검토 후보**입니다. 2025년 계획 문서의 수치나 2026년 보도자료를 2025년 동별 실적처럼 사용하지 않습니다. 현재 자료만으로 탐지 정확도나 사업 효과를 계산할 수 없습니다.

## 저장소에서 실행하기

Python 3.10 이상이 필요합니다. 저장소 최상위(`Team_Together`)에서 다음 명령을 실행합니다.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r dashboard\requirements.txt
.\.venv\Scripts\python.exe main.py
```

macOS / Linux:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -r dashboard/requirements.txt
./.venv/bin/python main.py
```

브라우저에서 `http://localhost:8501`을 엽니다. 로그인 화면의 `강남구 · gangnam01 / demo1234` 시연 계정을 선택해 들어갈 수 있습니다. 로그인 기능과 계정은 시연용입니다. Windows의 `dashboard/run_dashboard.bat`도 저장소 최상위 `.venv`를 만든 뒤 사용할 수 있습니다.

최상위 `main.py`는 기본 실행 시 대시보드를 열고, `python main.py --preprocess` 실행 시 팀의 기존 전처리 CSV를 준비합니다. 대시보드 의존성은 `dashboard/requirements.txt`에 있습니다.

## 주요 파일

| 경로 | 역할 |
|---|---|
| `main.py`, `dashboard/main.py` | 실행 진입점과 데이터 로딩 |
| `dashboard/detection_data.py` | 전년 동월 변화 및 탐지 단계 계산 |
| `dashboard/policy_data.py`, `dashboard/recommendation_audit.py` | 2025년 사업 계획 로딩과 후보·제외 판정 생성 |
| `dashboard/validation_data.py`, `dashboard/import_validation.py` | 결과보고 실적 검사와 입력표 가져오기 |
| `dashboard/ui/detection.js` | 실측 탐지·사업 검토 화면과 실측 챗봇 답변 |
| `dashboard/ui/dashboard.js`, `layout.html`, `style.css` | 메뉴·화면·챗봇 조작과 디자인 |
| `dashboard/data/policy_recommendation_audit_2025.md` | 사업 판정 결과 요약 |
| `dashboard/tests/check_dashboard.py`, `check_dashboard.cjs` | 계산·화면 진입·자료 누락 처리 확인 |

## 결과보고 자료가 도착하면

1. **2025년, 같은 행정동·같은 월**의 발굴·상담·방문·서비스 연계 실적만 입력합니다. 문서번호, 기준월, 단위(명/가구), 중복 처리 기준을 함께 기록합니다.
2. 저장소 밖에 보관한 `2025_동별_검증입력_청구대응표.xlsx`에 수치를 적고 저장소 최상위에서 다음을 실행합니다.

   ```powershell
   .\.venv\Scripts\python.exe -m dashboard.import_validation "C:\자료경로\2025_동별_검증입력_청구대응표.xlsx"
   ```

3. `dashboard/data/validation_actuals_2025.json`에 반영된 내용을 확인한 뒤 대시보드를 다시 실행합니다. 여러 달의 합계는 임의로 월별 배분하지 않고, 빈칸을 0으로 바꾸지 않습니다.

원본 결과보고서와 실적이 채워진 엑셀은 현재 Git 브랜치에 넣지 않았습니다. 검증 입력 도구는 같은 동·월을 찾지 못하거나 출처 정보가 빠진 경우 가져오기를 중단합니다.

## 다음 작업

1. 실측 화면에서 담당자가 남기는 **검토 상태, 현장 확인 결과, 사업 연계 여부, 메모, 확인 날짜**를 저장하고 다시 볼 수 있게 하기.
2. 공개청구 결과보고서가 오면 위 입력표로 같은 동·월의 실적을 확인해 반영하기.
3. 실적 확보 범위와 자료의 한계를 표시하며 탐지 결과와 실적을 나란히 검토하기.

## 확인

저장소 최상위에서 다음 검사를 실행합니다. JavaScript 검사에는 Node.js가 필요합니다.

```powershell
.\.venv\Scripts\python.exe dashboard\tests\check_dashboard.py
```

마지막 반영 시 Python 진입점, JavaScript 문법, 계산 40,420건 및 자료 누락 처리가 통과했습니다.
