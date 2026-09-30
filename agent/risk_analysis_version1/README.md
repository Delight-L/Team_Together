# 위험변화 탐지 에이전트

동별 월간 집계 데이터에서, 다른 동보다 위험 방향으로 크게 변했고 그 동의 과거 변화폭보다 이례적인 지표를 찾습니다. 개인 단위 판정이 아니라 **현장 확인 우선순위 후보**를 만드는 도구입니다.

## 1. 준비

`main.py`, `analyzer.py`, `data_provider.py`, `config.py` 네 파일을 같은 폴더에 둡니다.

필요 패키지는 한 번만 설치합니다.

```bash
pip install pandas numpy
```

## 2. CSV 필수 열

입력 CSV에는 다음 세 열이 꼭 있어야 합니다.

`행정동코드`, `행정동명`, `기준연월`

`기준연월`은 `2025-07` 형태여야 합니다. 같은 동·같은 월은 한 행만 있어야 합니다.

## 3. 포함된 전처리 CSV로 윈도우에서 실행

1. 이 폴더로 이동합니다.

```bash
cd "C:\Users\user\Desktop\together project\risk_analysis_agent"
```

2. 아래처럼 **한 줄 전체를 한 번에** 입력합니다. 줄 끝의 `\`는 쓰지 않습니다.

```bash
python main.py --input "data\gangnam_db1_dong_month_behavior_mart_2025_07_12(1).csv" --min-relative-change 5 --z-threshold 3.5 --output-dir outputs
```

이 명령은 압축파일에 같이 넣은 전처리 CSV를 임시 입력으로 사용한다. 현재 분석 지표는 `config.py`에 제공 CSV의 실제 열 이름으로 이미 연결돼 있다.

특정 지표만 분석하려면 열 이름을 쉼표로 넣습니다.

```bash
python main.py --input "data\gangnam_db1_dong_month_behavior_mart_2025_07_12(1).csv" --metrics "flow_per_point,평일 총 이동 횟수,휴일 총 이동 횟수 평균" --min-relative-change 5 --z-threshold 2.5 --output-dir outputs
```

## 4. 결과

- `outputs/risk_metric_assessment.csv`: 전체 동·월·지표 판정
- `outputs/risk_metric_signals.csv`: 두 기준을 모두 통과한 변화 후보
- `outputs/risk_region_alerts.csv`: 동·월별 후보 요약

실행이 끝나면 위 CSV 저장 경로 아래에 `[사용자용 위험 변화 후보]`가 바로 출력됩니다. Analysis 1의 확정 `k=3` 동별 지역 Context를 **행정동코드**로 조회해, 지역 유형과 특징을 함께 보여줍니다. 반복되는 확인 포인트는 실행 화면에서 제외하고 코드 내부에만 보관합니다. 따라서 동 이름의 과거 명칭·띄어쓰기와 무관하게 같은 지역을 연결합니다. `data/gangnam_analysis1_cluster_profile_2025H2(1).csv`는 유형별 대표 지표를 보관한 근거 파일입니다. 군집은 위험도 확정값이 아니라 해석 보조 정보입니다.

## 위험 방향

활동·이동·통화 대상은 **감소**, 집 체류·저외출·카카오톡 비사용 비율은 **증가**를 위험 방향으로 설정했다. 개인 판정이 아니라 동별 현장 확인 후보를 찾는 용도다.
# 원본 CSV부터 실행하기

`preprocessing_agent` 폴더가 새로 포함되어 있습니다. 원본 유동인구·통신정보·관심집단 CSV 3개를 넣으면 위험분석 입력 파일을 만들고, `--run-risk` 옵션으로 위험변화 탐지까지 한 번에 실행합니다.

```powershell
python preprocessing_agent\main.py --flow "raw_data\gangnam_db1_clustered_202507_202512.csv" --telecom "raw_data\gangnam_telecom_29info_2025_07_12.csv" --interest "raw_data\gangnam_interest_groups_2025_07_12.csv" --output "outputs\preprocessed_monthly_behavior.csv" --run-risk
```

세 원본 파일에 필요한 열과 검증 규칙은 `preprocessing_agent\README.md`에 정리했습니다.
