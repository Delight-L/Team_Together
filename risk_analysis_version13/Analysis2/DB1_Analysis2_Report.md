# DB1 Analysis 2 — 행동변화 신호 탐지 분석

**SeSAC08 최종프로젝트 · DB1**  
**강남구 22개 행정동 · 2022.01–2025.12**

## 1. Analysis 2의 목적과 역할

Analysis 2의 핵심 질문은 다음과 같다.

> 강남구 각 행정동에서 통신·이동 행동이 해당 지역의 과거 행동 패턴과 비교하여 이례적으로 감소한 시점은 언제인가?

탐지 대상은 사회적 고립 자체가 아니라 **사회적 연결과 관련해 해석할 수 있는 행동변화 신호**이다.

| 구분 | 역할 |
|---|---|
| Analysis 1 | **WHERE** — 지역의 평상시 활동·인구·가구·복지 등 구조적 Context |
| Analysis 2 | **WHEN** — 평소와 다른 통신·이동 행동변화가 나타난 시점 탐지 |

따라서 Analysis 2 결과를 사회적 고립 발생이나 고립 위험지역 등으로 직접 해석하지 않는다.

---

# Part I. Analysis 1 결합 전 독립적인 행동신호 탐지

## 2. 원천 데이터와 분석 단위

2022년 1월부터 2025년 12월까지 총 48개월의 서울 시민생활데이터를 활용하였다.

- 29개 통신정보: 통화·문자·이동 등 직접적인 행동변수
- 10개 관심집단수: 커뮤니케이션이 적은 집단, 평일·휴일 외출이 적은 집단 등 모델 기반 관심집단 정보

원천 분석 단위는 다음과 같다.

```text
행정동 × 성별 × 5세 단위 연령집단 × 월
```

Analysis 2에서는 이를 행정동 × 월 단위로 집계하였다.

- 강남구 행정동: 22개
- 기간: 48개월
- 최종 Feature Table: **1,056행 × 23열**

---

## 3. 관심집단수를 Detection Core로 사용하지 않은 이유

초기에는 다음 관심집단을 핵심 후보로 검토하였다.

- 커뮤니케이션이 적은 집단
- 평일 외출이 적은 집단
- 휴일 외출이 적은 집단

그러나 관심집단수는 직접 관측된 행동량 자체가 아니라 통신 행동 등을 기반으로 정의·추정된 **모델 기반 집단**이다.

또한 행정동코드 `1123074`에서 2024년 1월 이후 세 관심집단수가 모든 성·연령 셀에서 동시에 0으로 전환되는 구조적 단절이 발견되었다. 같은 기간 원시 통신 행동변수는 정상적으로 이어졌다.

따라서 관심집단수는 Detection Core에서 제외하고 **Validation / Evidence**로 사용하였다.

---

## 4. Detection Core 선정

| Domain | 최종 변수 | 의미 |
|---|---|---|
| Communication | `call_contacts` | 평균 통화대상자 수 |
| Communication | `text_contacts` | 평균 문자대상자 수 |
| Mobility | `weekday_move_count` | 평일 총 이동 횟수 |
| Mobility | `weekend_move_count` | 휴일 총 이동 횟수 |

평일·휴일 이동거리도 검토했으나 변화량 기준으로 이동횟수와 매우 높은 상관관계가 확인되어 이동횟수는 Detection Core로 유지하고 이동거리는 탐지 결과를 확인하는 **Evidence**로 분리하였다.

PCA 역시 사용하지 않았다. Core가 4개뿐이고 Communication/Mobility라는 의미구조가 명확하여 차원축소보다 설명가능성 유지가 더 중요하다고 판단하였다.

---

## 5. Analysis 2 Feature Table

최종 전처리 산출물:

`gangnam_analysis2_feature_table_2022_2025.csv`

**1,056행 × 23열**

| 계층 | 주요 내용 |
|---|---|
| Detection Core | 통화·문자 대상자 수, 평일·휴일 이동횟수 |
| Evidence | 평일·휴일 이동거리 |
| QC | 이동 관련 estimated population ratio |
| Validation | `comm_low_rate`, `weekday_outing_low_rate`, `weekend_outing_low_rate`, `interest_structural_issue` |
| Context | 강수일수·강수량·적설일수, 월 일수·평일 수·주말 수 |

이 파일은 Analysis 2에서 전처리가 완료되고 탐지 계산을 시작하기 직전의 기준 데이터셋이다.

---

## 6. 단순 전월 대비 증감률을 사용하지 않은 이유

특정 월에는 강남구 22개 동 대부분의 이동량이 같은 방향으로 크게 변하는 현상이 확인되었다.

따라서 한 행정동의 행동량이 전월보다 감소했다는 사실만으로 해당 동에 특이한 변화가 발생했다고 볼 수 없다.

이에 따라 강남구 전체에서 발생한 공통적인 시간 변화를 먼저 제거하도록 분석을 설계하였다.

---

## 7. 탐지 계산 절차

### 7.1 행정동별 Log Change

각 Core 변수에 대해 전월 대비 상대적 변화를 측정하였다.

\[
\Delta(i,t)=\log(X(i,t))-\log(X(i,t-1))
\]

---

### 7.2 강남구 공통변화 제거

같은 달 강남구 22개 행정동의 변화량 중앙값을 계산하였다.

\[
Residual(i,t)
=
\Delta(i,t)
-
Median(\Delta(Gangnam,t))
\]

Residual은 같은 시기 강남구 전체의 공통 변화를 감안하고도 해당 행정동이 상대적으로 얼마나 다르게 움직였는지를 나타낸다.

---

### 7.3 Historical-only Expanding Robust Z

행정동별 Residual 변동성이 서로 다르기 때문에 Median과 MAD를 사용하는 Robust Z-score를 적용하였다.

\[
RZ =
0.6745
\times
\frac{x-Median}{MAD}
\]

현재 월을 판단할 때 미래 데이터는 사용하지 않았다.

- Baseline: Historical-only Expanding
- 최소 과거 이력: 12개월
- 미래정보 누수 방지
- 운영 탐지기간: 2023-02 ~ 2025-12
- 운영 탐지 단위: 35개월 × 22개 동 = **770 동×월**

---

## 8. 탐지 임계값 후보 비교

Robust Z 임계값을 -1.5, -2.0, -2.5, -3.0의 네 후보로 실제 데이터에 적용하여 탐지 민감도를 비교하였다.

| Robust Z 기준 | Communication | Mobility | Combined | Any Signal |
|---:|---:|---:|---:|---:|
| ≤ -1.5 | 28 | 49 | 5 | 72 |
| **≤ -2.0** | **10** | **26** | **1** | **35** |
| ≤ -2.5 | 7 | 15 | 1 | 21 |
| ≤ -3.0 | 4 | 3 | 0 | 7 |

---

## 9. 최종 임계값 Robust Z ≤ -2.0 선정 근거

최종 운영 기준은 **Robust Z ≤ -2.0**으로 선택하였다.

이는 보편적인 사회적 고립의 경계가 아니라 이번 데이터에서 탐지 민감도와 특이성 사이의 균형을 확보하기 위한 **운영적 임계값**이다.

- -1.5: Any Signal 72건
- -2.0: Any Signal 35건
- -2.5: Any Signal 21건
- -3.0: Any Signal 7건

-2.0에서는 770개 탐지 가능 동×월의 약 4.5%가 남아 검토 가능한 규모와 희소성의 균형을 보였다.

또한 -2.0에서 탐지된 Mobility Signal 26건 중 23건(88.5%)에서 평일 또는 휴일 이동거리도 감소하여, Detection에 사용하지 않은 독립 Evidence가 상당수 신호를 같은 방향으로 뒷받침했다.

---

## 10. Domain Signal 판정

| Signal | 판정 조건 | 의미 |
|---|---|---|
| Communication | call RZ ≤ -2 AND text RZ ≤ -2 | 통화·문자 대상자 수가 동시에 과거 변동범위에서 이례적으로 낮아진 경우 |
| Mobility | weekday move RZ ≤ -2 AND weekend move RZ ≤ -2 | 평일·휴일 이동횟수가 동시에 이례적으로 낮아진 경우 |
| Combined | Communication AND Mobility | 두 행동영역에서 같은 동×월에 신호가 동시에 나타난 경우 |

Combined는 더 많은 행동영역에서 변화가 동시에 나타났다는 뜻이며 사회적 고립 위험등급을 의미하지 않는다.

---

## 11. 최종 Detection 결과

| 구분 | 건수 |
|---|---:|
| 탐지 가능 동 × 월 | 770 |
| Any Signal | 35 |
| Communication Signal | 10 |
| Mobility Signal | 26 |
| Combined Signal | 1 |
| Communication only | 9 |
| Mobility only | 25 |

Combined Signal은 2024년 12월 수서동에서 1건 확인되었다.

여기까지의 탐지는 Analysis 1 정보를 사용하지 않고 독립적으로 수행하였다.

---

## 12. Detection 결과 Evidence 검증

### Mobility Evidence

Mobility Signal 26건 가운데 **23건(88.5%)**에서 평일 또는 휴일 이동거리도 감소하였다.

이동거리는 탐지조건에 포함하지 않으면서 탐지 결과를 보조하는 Evidence로 사용하였다.

### Communication Validation

Communication Signal 10건 가운데 **5건(50%)**에서 커뮤니케이션이 적은 집단 비율도 증가하였다.

일치도가 50%였기 때문에 관심집단 정보는 Detection 조건으로 추가하지 않고 독립적인 Validation으로 유지하였다.

---

## 13. 연속 Signal 검토

35건 중 5건은 같은 행정동에서 전월에 이어 연속적으로 탐지되었다.

| 상태 | 건수 | 해석 |
|---|---:|---|
| New | 30 | 직전월에 Signal이 없었던 탐지 |
| Continuing | 5 | 직전 탐지월과 시간적으로 중첩되는 연속 행동신호 |

주요 통신·이동 변수는 최근 3개월 평균을 사용하므로 인접 월의 관측기간이 상당 부분 겹친다.

따라서 Continuing을 독립 사건의 반복이나 위험의 지속적 악화로 해석하지 않는다.

---

# Part II. Analysis 1 결합 후 지역 Context 해석

## 14. Analysis 1 결합 원칙

Analysis 1은 Detection이 끝난 이후에만 결합하였다.

```text
Analysis 2 행동데이터
        ↓
35개 Signal 확정
        ↓
Analysis 1 지역 Context 결합
```

Analysis 1의 군집정보는 Analysis 2 탐지 알고리즘에 입력되지 않았다.

Analysis 1 최종 지역유형 테이블의 `cluster`와 `cluster_type`을 행정동코드 기준으로 결합하여, 탐지된 신호가 발생한 지역의 평상시 구조적 배경을 설명하는 Context로 사용하였다.

---

## 15. Analysis 1 Context 결합 결과

| 검증 항목 | 결과 |
|---|---|
| Signal 수 | 35건 유지 |
| cluster 결측 | 0 |
| cluster_type 결측 | 0 |
| 행정동명 표준화 | 1123074는 최종 출력에서 개포3동 사용 |

### 지역유형별 Signal 분포

| Analysis 1 지역유형 | Signal | Signal 발생 행정동 수 |
|---|---:|---:|
| 고활동·청년유동·1인가구 중심형 | 7 | 6 |
| 고령·2인가구·구조적 복지배경 특화형 | 5 | 2 |
| 중간활동·다인가구 중심형 | 23 | 9 |

이 분포를 위험도 순위로 해석해서는 안 된다. Cluster별 포함 행정동 수가 다르고 Analysis 1 자체가 위험도를 측정하는 분석이 아니기 때문이다.

Analysis 2는 **언제 이례적인 행동변화가 나타났는가**를, Analysis 1은 **그 신호가 발생한 지역은 평상시에 어떤 구조적 특성을 가진 곳인가**를 설명한다.

---

## 16. 최종 Evidence Card

최종 Agent 입력용:

`gangnam_analysis2_evidence_card_2022_2025.csv`

**35행 × 29열**

Signal은 총 17개 행정동에서 확인되었다.

| 계층 | 포함 정보 |
|---|---|
| Detection | Signal Type, Communication/Mobility/Combined, Core 변수별 Historical-only Expanding Robust Z |
| Evidence / Validation | 이동거리 변화, Mobility distance support, 관심집단 변화, Communication interest support |
| Temporal Context | New/Continuing, 이전 Signal 시점 |
| External Context | 강수량·강수일수·적설일수, 평일·주말 수 |
| Regional Context | Analysis 1 cluster, cluster_type |

---

## 17. 최종 산출물

| 파일 | 역할 | 규모 |
|---|---|---:|
| `gangnam_analysis2_feature_table_2022_2025.csv` | 전처리 완료·탐지 계산 직전 기준 데이터 | 1,056 × 23 |
| `gangnam_analysis2_detection_2022_2025.csv` | 운영형 탐지 상세 결과 및 검증용 데이터 | 770 × 55 |
| `gangnam_analysis2_evidence_card_2022_2025.csv` | AI Agent 해석용 Signal Evidence Card | 35 × 29 |

---

## 18. 해석 범위와 한계

- Robust Z ≤ -2.0은 사회적 고립의 임상적·정책적 기준이 아니라 sensitivity analysis를 통해 선택한 운영적 임계값이다.
- 통신·이동 행동의 감소가 곧 사회적 고립을 의미하지 않는다.
- 생활패턴, 지역행사, 기상, 휴일 등 다양한 요인이 행동량에 영향을 줄 수 있다.
- 주요 통신·이동 변수는 최근 3개월 평균이므로 Signal은 특정 한 달의 순간적 사건보다 해당 시점을 포함하는 최근 행동기간의 변화로 해석해야 한다.
- 분석 단위가 행정동 × 월이므로 개인을 식별하거나 개인의 사회적 고립 상태를 판정할 수 없다.
- Analysis 1의 지역유형은 Signal의 발생원인이나 위험도를 설명하는 변수가 아니라 탐지 이후 지역의 구조적 배경을 이해하기 위한 Context이다.
- 관심집단수에서 확인된 구조적 단절 때문에 관심집단 정보는 Detection Core가 아닌 보조 Validation으로 사용하였다.

---

## 19. 분석 요약

Analysis 2는 사회적 고립을 직접 판정하는 모델이 아니라, 강남구의 공통적인 월별 변화를 제거하고 각 행정동의 과거 행동 변동범위와 비교하여 통신 및 이동 행동의 이례적인 감소 시점을 탐지하는 분석이다.

탐지 임계값은 -1.5, -2.0, -2.5, -3.0의 민감도를 비교하고 독립 Evidence를 검토하여 **Robust Z ≤ -2.0**을 운영 기준으로 선정하였다.

탐지 완료 이후에만 Analysis 1의 지역유형을 결합하여 행동신호의 지역적 맥락을 해석하도록 설계하였다.
