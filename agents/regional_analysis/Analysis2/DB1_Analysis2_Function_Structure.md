# DB1 Analysis 2 — 함수화 및 실행 구조

**행동변화 신호탐지 분석의 모듈화 · 재현성 검증 · 자동화 연계 구조**

## 1. 문서 목적

본 문서는 DB1 Analysis 2에서 확정된 분석 방법론을 변경하기 위한 문서가 아니라, Colab에서 검증한 행동변화 신호 탐지 분석을 **로컬 환경에서 반복 실행 가능한 함수 구조로 이전한 과정과 실행 구조**를 정리하기 위한 문서이다.

핵심 목적은 다음 기능을 분리하는 것이다.

- 데이터 입력
- 입력 검증
- 행동변화 계산
- 신호 탐지
- Evidence 생성
- 결과 저장

또한 Colab에서 확정한 Reference 결과와의 회귀 테스트를 통해 함수화 이후에도 동일한 분석 결과가 재현됨을 확인하였다.

따라서 함수화의 핵심은 단순한 코드 분할이 아니라, 검증된 분석 방법론을 변경하지 않은 상태에서 재실행 가능한 모듈로 고정하고 향후 데이터 갱신 및 AI Agent 연계를 위한 실행 경계를 명확히 하는 데 있다.

---

## 2. Analysis 2의 역할과 함수화 원칙

DB1 분석 체계에서:

- **Analysis 1 = WHERE** — 지역의 평상시 구조적 특성
- **Analysis 2 = WHEN** — 평소와 다른 커뮤니케이션·이동 행동 변화가 언제 나타났는지 탐지

함수화 원칙:

1. Analysis 2는 사회적 고립을 직접 진단하거나 판정하는 모델이 아니다.
2. Analysis 1의 군집 정보는 Analysis 2 Detection Core에 투입하지 않는다.
3. 행동신호를 먼저 독립적으로 탐지한 뒤 Analysis 1 Context를 사후 결합한다.
4. Robust Z 임계값 `-2.0`은 임상적·보편적 사회적 고립 기준이 아니라 민감도 분석을 통해 선택한 운영 탐지 기준이다.
5. 미래정보 누수를 방지하기 위해 현재 시점 이전의 과거 데이터만 사용하는 historical-only expanding baseline을 적용한다.

---

## 3. 함수 입력 경계

Analysis 2 함수화에서 공식 입력 경계는 다음 Feature Table로 정의하였다.

| 항목 | 내용 |
|---|---|
| 입력 파일 | `gangnam_analysis2_feature_table_2022_2025.csv` |
| 크기 | 1,056행 × 23열 |
| 분석 단위 | 행정동 × 월 |
| 공간 범위 | 강남구 22개 행정동 |
| 기간 | 2022-01 ~ 2025-12 (48개월) |

```text
원천데이터 수집
      ↓
전처리·결합
      ↓
──────────── 함수 입력 경계 ────────────
      ↓
Analysis 2 행동변화 탐지
      ↓
Detection Table
      ↓
Evidence Card
```

향후 API 등을 통해 원천 데이터가 갱신되더라도 동일한 23개 변수 구조의 Feature Table을 생성하면 Analysis 2 분석 함수에 전달할 수 있도록 경계를 분리하였다.

---

## 4. 디렉터리 및 모듈 구조

```text
Analysis2/
│
├─ gangnam_analysis2_feature_table_2022_2025.csv
├─ run_analysis2.py
├─ (의존성: 프로젝트 루트 requirements.txt)
│
├─ analysis/
│  ├─ __init__.py
│  ├─ analysis2.py
│  └─ outputs.py
│
├─ common/
│  ├─ __init__.py
│  └─ config.py
│
├─ data/
│  ├─ __init__.py
│  ├─ ingestion.py
│  └─ validation.py
│
├─ docs/
│
├─ outputs/
│  ├─ gangnam_analysis2_detection_2022_2025.csv
│  └─ gangnam_analysis2_evidence_card_2022_2025.csv
│
├─ reference/
│  ├─ gangnam_analysis1_final_region_typology_2025H2.csv
│  ├─ gangnam_analysis2_detection_2022_2025.csv
│  └─ gangnam_analysis2_evidence_card_2022_2025.csv
│
└─ tests/
   └─ test_analysis2.py
```

### 구성별 책임

| 구성 | 책임 |
|---|---|
| `data/` | 입력 파일 로드 및 입력 데이터 검증 |
| `analysis/analysis2.py` | 행동변화 계산, Robust Z, 신호 탐지, Evidence 및 Context 결합 |
| `analysis/outputs.py` | Detection Table과 Evidence Card의 최종 출력 스키마 생성 |
| `common/config.py` | 분석 기준값·컬럼명·기간·임계값 등 공통 설정 관리 |
| `reference/` | Colab에서 확정한 Gold/Reference 결과 보존 |
| `tests/` | 함수화 결과와 Reference 결과의 자동 회귀 검증 |
| `run_analysis2.py` | 입력부터 결과 저장까지 전체 실행을 연결하는 진입점 |

---

## 5. Analysis 2 전체 실행 흐름

```text
Feature Table
1,056 × 23
      ↓
load_analysis2_input()
      ↓
validate_analysis2_input()
      ↓
PASS
      ↓
compute_log_changes()
      ↓
compute_common_adjusted_residuals()
      ↓
compute_mobility_distance_evidence()
      ↓
expanding_robust_z()
      ↓
detect_signals()
      ↓
┌─────────────────────────┐
│ Communication           │
│ Mobility                │
│ Combined / Any          │
└─────────────────────────┘
      ↓
Evidence · Validation 결합
      ├─ 이동거리 Evidence
      ├─ 관심집단 Validation
      └─ New / Continuing
      ↓
Analysis 1 Context 사후 결합
      ↓
build_detection_table()
      ↓
770 × 55
      ↓
build_evidence_card()
      ↓
35 × 29
```

---

## 6. 함수별 역할

| 함수 | 역할 |
|---|---|
| `load_analysis2_input()` | Feature Table 로드 |
| `validate_analysis2_input()` | 행·열·기간·행정동·중복·결측·자료형 검증 |
| `compute_log_changes()` | 행정동별 월간 로그 변화량 계산 |
| `compute_common_adjusted_residuals()` | 강남구 공통 월간 변화를 제거한 잔차 계산 |
| `expanding_robust_z()` | 과거 데이터만 이용한 expanding Robust Z 계산 |
| `detect_signals()` | Communication / Mobility / Combined / Any 신호 탐지 |
| `compute_mobility_distance_evidence()` | 이동거리 변화 Evidence 계산 |
| `attach_mobility_evidence()` | 이동거리 감소 여부를 보조근거로 생성 |
| `attach_communication_validation()` | 커뮤니케이션 관심집단 비율 변화 보조검증 |
| `attach_signal_status()` | New / Continuing 상태 생성 |
| `attach_analysis1_context()` | 탐지 후 Analysis 1 지역 Context 결합 |
| `run_analysis2_pipeline()` | 전체 분석 함수를 순차 실행 |
| `build_detection_table()` | 상세 Detection Table 생성 |
| `build_evidence_card()` | Agent-facing 핵심 Evidence Card 생성 |

---

## 7. 탐지 방법론의 함수 구현

탐지 로직은 다음 순서로 구현하였다.

```text
행정동 내부 월간 변화
        ↓
강남구 공통 변화 제거
        ↓
각 행정동의 과거 변동성 기준 표준화
        ↓
도메인별 동시 하락 조건
        ↓
Signal 생성
```

Detection Core는 다음 4개 원천 행동변수이다.

- `call_contacts`
- `text_contacts`
- `weekday_move_count`
- `weekend_move_count`

이동거리는 탐지 변수가 아니라 독립적인 Evidence로 사용한다.

---

## 8. Robust Z 구현 기준

\[
RZ = 0.6745 \times \frac{x - Median}{MAD}
\]

구현 기준:

| 항목 | 기준 |
|---|---|
| 최소 과거 관측치 | 12개 residual observation |
| Baseline | Expanding |
| 누수 방지 | 현재 시점 이전 데이터만 사용 |
| 운영 탐지기간 | 2023-02 ~ 2025-12 |
| 운영 탐지 단위 | 22개 행정동 × 35개월 = 770건 |
| Communication Signal | call과 text Robust Z가 모두 임계값 이하 |
| Mobility Signal | 평일·주말 이동횟수 Robust Z가 모두 임계값 이하 |
| Combined Signal | Communication과 Mobility가 동시에 탐지 |
| Any Signal | 두 도메인 중 하나 이상 탐지 |

---

## 9. Robust Z Threshold -2.0 선정 근거

임계값은 사회적 고립을 정의하는 임상적·보편적 기준이 아니라, 탐지 민감도와 운영 가능한 신호 규모 사이의 균형을 확인하기 위한 민감도 분석을 통해 선정하였다.

| Threshold | Communication | Mobility | Combined | Any |
|---:|---:|---:|---:|---:|
| -1.5 | 28 | 49 | 5 | 72 |
| **-2.0** | **10** | **26** | **1** | **35** |
| -2.5 | 7 | 15 | 1 | 21 |
| -3.0 | 4 | 3 | 0 | 7 |

-1.5에서는 72건으로 신호 범위가 넓었고, -2.5와 -3.0에서는 각각 21건과 7건으로 보수적인 탐지가 이루어졌다.

-2.0에서는 전체 운영 탐지 770건 중 35건(약 4.5%)이 추출되어 해석 및 운영이 가능한 희소 신호 집합을 형성하였다.

또한 Mobility Signal 26건 중 23건(88.5%)에서 평일 또는 주말 이동거리 감소가 함께 관찰되어 독립적인 Evidence가 탐지 결과를 보조하였다.

따라서 -2.0은 민감도·특이성, 해석 가능성 및 운영 규모를 종합적으로 고려한 운영 기준으로 사용한다.

---

# Part II. 최종 산출물

## 10. Detection Table

**파일**

`gangnam_analysis2_detection_2022_2025.csv`

| 항목 | 내용 |
|---|---|
| 크기 | 770행 × 55열 |
| 대상 | 운영 탐지기간의 모든 행정동 × 월 |
| 용도 | 상세 분석 검증, 추적, 대시보드 및 후속 분석 |

Detection Table은 신호 여부와 관계없이 운영 탐지기간의 전체 행정동-월을 보존한다.

포함 정보:

- 원천 행동값
- 로그 변화량
- 강남구 공통 변화
- Residual
- Expanding Robust Z
- 도메인별 Signal
- 이동거리 Evidence
- 관심집단 Validation

---

## 11. Evidence Card

**파일**

`gangnam_analysis2_evidence_card_2022_2025.csv`

| 항목 | 내용 |
|---|---|
| 크기 | 35행 × 29열 |
| 대상 | `any_signal=True`인 행동변화 신호 35건 |
| 용도 | AI Agent가 탐지된 사건의 근거와 Context를 해석하기 위한 입력 |

Evidence Card는 다음 정보를 제공한다.

- Signal Type
- Communication / Mobility / Combined
- Core 변수별 Robust Z
- 이동거리 Evidence
- 관심집단 Validation
- New / Continuing
- 이전 Signal 시점
- 날씨·달력 Context
- Analysis 1 지역유형

최종 탐지 결과:

- Any: 35건
- Communication: 10건
- Mobility: 26건
- Combined: 1건
- New: 30건
- Continuing: 5건

원천 행동변수가 최근 3개월 평균 성격을 갖는 점을 고려하여 Continuing을 곧바로 위험 악화나 장기 지속으로 해석하지 않는다.

---

# Part III. Reference 기반 재현성 검증

## 12. 회귀 테스트 구조

함수화 과정에서 분석 방법론이 변경되지 않았음을 확인하기 위해 Colab에서 확정한 Detection Table과 Evidence Card를 `reference/` 디렉터리에 Gold Output으로 보존하였다.

로컬 함수 결과와 Reference 결과를 비교하는 회귀 테스트를 구성하였다.

| 검증 대상 | 결과 |
|---|---|
| 입력 Feature Table | 1,056 × 23 / validation PASS |
| 함수화 전체 분석 결과 | 1,056 × 64 |
| Detection Table | 770 × 55 / Reference 재현 |
| Evidence Card | 35 × 29 / Reference FULL MATCH |
| pytest | `PASSED / 1 passed` |

Detection CSV를 저장한 뒤 다시 읽어 Reference와 비교할 때 일부 실수형 컬럼에서 최대 약 `1.59×10⁻¹²` 수준의 차이가 확인되었다.

이는 CSV 직렬화 및 재로딩 과정에서 발생하는 부동소수점 표현 차이이며 `np.allclose()` 기준에서는 모두 동일하였다.

따라서 자동 회귀 테스트는:

- 수치형 컬럼 → tolerance 기반 비교
- 문자열·Boolean → 정확 일치
- 날짜 컬럼 → `YYYY-MM-DD` 형식으로 정규화

하여 비교하도록 구성하였다.

---

## 13. 실행 환경 및 재현 방법

검증된 환경:

```text
Python 3.12.14
numpy 2.5.3
pandas 3.0.6
pytest 9.1.1
```

### 의존성 설치

```bash
conda activate analysis2
pip install -r requirements.txt  # 프로젝트 루트에서 실행
```

### 전체 분석 실행

```bash
python run_analysis2.py
```

### 회귀 테스트

```bash
python -m pytest tests/test_analysis2.py -v
```

### 환경 의존성 검사

```bash
python -m pip check
```

검증 결과:

```text
No broken requirements found.
```

---

# Part IV. 향후 자동화 및 AI Agent 연계

## 14. 자동화 구조

현재 함수 구조는 원천데이터의 수집·갱신과 분석 로직을 분리한다.

향후 공공데이터 포털 API 또는 정기 수집 절차를 통해 원천 데이터를 갱신하고 동일한 Feature Table 스키마를 생성하면 기존 Analysis 2 분석 코드를 변경하지 않고 반복적으로 행동변화 신호를 탐지할 수 있다.

```text
공공/API 원천데이터 갱신
        ↓
전처리 및 23-column Feature Table 생성
        ↓
Analysis 2 함수 실행
        ↓
Detection Table
        ↓
Evidence Card
        ↓
AI Agent
```

---

## 15. AI Agent 연계 원칙

함수화의 최종 의미는 단순히 분석 코드를 여러 함수로 나눈다는 데 있지 않다.

검증된 분석 방법론을:

- 입력 경계가 명확하고
- 출력 스키마가 명확하며
- 반복 실행 가능하고
- Reference 회귀 테스트가 가능한

모듈로 고정함으로써 향후 월별 자동 갱신 및 AI Agent 연결이 가능한 기반을 마련하는 데 있다.

AI Agent는 Evidence Card를 기반으로 탐지된 행동변화와 Context를 해석해야 하며, Analysis 2의 Detection Core를 임의로 변경해서는 안 된다.

특히 다음 원칙을 유지한다.

- Detection Core 변경 금지
- Historical-only Expanding Baseline 유지
- Robust Z 계산 방식 유지
- 운영 임계값 변경 시 재검토 및 회귀 테스트
- Analysis 1 Context는 Detection 이후에만 결합

---

## 16. 함수화 완료 상태

| 항목 | 상태 |
|---|---|
| 공식 함수 입력 경계 정의 | 완료 — Feature Table 1,056 × 23 |
| 입력 로드·검증 분리 | 완료 |
| 행동변화 탐지 로직 함수화 | 완료 |
| Detection / Evidence 출력 로직 분리 | 완료 |
| Analysis 1 Context 사후 결합 | 완료 |
| Colab Reference 재현 | 완료 |
| 자동 회귀 테스트 | 완료 — pytest 1 passed |
| 실행 환경 고정 | 완료 — requirements.txt |
| 의존성 검사 | 완료 — No broken requirements found |
| 자동화·Agent 연계 입력 구조 | 준비 완료 |
