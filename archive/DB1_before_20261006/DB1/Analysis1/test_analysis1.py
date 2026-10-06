import numpy as np
import pandas as pd

from analysis.analysis1 import run_analysis1


rng = np.random.default_rng(42)
n = 22

df = pd.DataFrame({
    "dong_code": [f"D{i:02d}" for i in range(1, n + 1)],
    "dong_name": [f"테스트동{i:02d}" for i in range(1, n + 1)],

    # 직접 사용하는 Feature
    "activity_intensity": rng.normal(500, 100, n),
    "weekend_weekday_index": rng.uniform(0.6, 1.0, n),
    "foreigner_ratio": rng.uniform(0.01, 0.10, n),
    "disability_ratio": rng.uniform(0.02, 0.08, n),
    "livelihood_recipient_ratio": rng.uniform(0.01, 0.08, n),

    # 유동인구 성·연령 구조
    "active_male_ratio": rng.uniform(0.4, 0.6, n),
    "active_age_10_ratio": rng.uniform(0.05, 0.15, n),
    "active_age_20_ratio": rng.uniform(0.10, 0.25, n),
    "active_age_30_ratio": rng.uniform(0.10, 0.25, n),
    "active_age_40_ratio": rng.uniform(0.10, 0.20, n),
    "active_age_50_ratio": rng.uniform(0.10, 0.20, n),
    "active_age_60_plus_ratio": rng.uniform(0.10, 0.30, n),

    # 시간대 구조
    "night_ratio": rng.uniform(0.05, 0.20, n),
    "morning_ratio": rng.uniform(0.10, 0.25, n),
    "daytime_ratio": rng.uniform(0.35, 0.60, n),
    "evening_ratio": rng.uniform(0.10, 0.30, n),

    # 주민 연령 구조
    "resident_0_19_ratio": rng.uniform(0.05, 0.20, n),
    "resident_20_29_ratio": rng.uniform(0.08, 0.20, n),
    "resident_30_39_ratio": rng.uniform(0.08, 0.20, n),
    "resident_40_49_ratio": rng.uniform(0.08, 0.20, n),
    "resident_50_64_ratio": rng.uniform(0.10, 0.25, n),
    "resident_65_plus_ratio": rng.uniform(0.08, 0.30, n),

    # 가구 구조
    "hh_1_ratio": rng.uniform(0.20, 0.60, n),
    "hh_2_ratio": rng.uniform(0.15, 0.35, n),
    "hh_3_ratio": rng.uniform(0.10, 0.30, n),
    "hh_4_plus_ratio": rng.uniform(0.05, 0.25, n),
})


pca_columns = {
    "active_pop": [
        "active_male_ratio",
        "active_age_10_ratio",
        "active_age_20_ratio",
        "active_age_30_ratio",
        "active_age_40_ratio",
        "active_age_50_ratio",
        "active_age_60_plus_ratio",
    ],
    "time_structure": [
        "night_ratio",
        "morning_ratio",
        "daytime_ratio",
        "evening_ratio",
    ],
    "resident_age": [
        "resident_0_19_ratio",
        "resident_20_29_ratio",
        "resident_30_39_ratio",
        "resident_40_49_ratio",
        "resident_50_64_ratio",
        "resident_65_plus_ratio",
    ],
    "household_structure": [
        "hh_1_ratio",
        "hh_2_ratio",
        "hh_3_ratio",
        "hh_4_plus_ratio",
    ],
}


result = run_analysis1(
    df,
    pca_columns=pca_columns,
    raw_profile_df=df,
    data_period="TEST",
    data_version="synthetic-v1",
    output_dir="test_output",
)

print("\n===== ANALYSIS 1 TEST =====")
print("status:", result.status)
print("n_areas:", result.metrics.get("n_areas"))
print("n_features:", result.metrics.get("n_features"))
print("final_k:", result.metrics.get("final_k"))
print("cluster_sizes:", result.metrics.get("final_cluster_sizes"))
print("warnings:", result.warnings)
print("outputs:", result.outputs)