# Analysis1 → DB1 저장 구조

- `a1_region_baseline`: 2025H2 행정동 유형/cluster 기준점 (22행)
- `a1_region_feature`: 행정동×기간×13 Feature long format (Baseline 286행)
- `a1_change_detection`: 신규 기간별 행정동 변화 요약
- `a1_change_feature`: 신규 기간별 13 Feature 변화 상세

모델/전처리 artifact(`joblib`, 원본, PCA 직전 22×30 CSV)는 SQLite에 넣지 않고 파일로 관리합니다.
DB의 결합 키는 `adm_cd`와 `period`입니다.
