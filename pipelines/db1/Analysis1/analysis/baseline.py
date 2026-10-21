"""행정동 특성을 표준화하고 지역 유형의 기준 모델과 결과 표를 만듭니다.

원자료 → PCA로 묶은 특성 → 영역별 가중치 적용 → 군집 분류 순서입니다.
모델의 지역 유형은 개인의 고립 여부나 지역의 우열을 뜻하지 않습니다.
"""

from __future__ import annotations
from pathlib import Path
import joblib
import pandas as pd
from common.config import CONFIG
from analysis.analysis1 import build_feature_table, balance_domains, fit_final_clusters

PCA_COLUMNS = {
    'active_pop': [
        'male_ratio',
        'age_10_ratio',
        'age_20_ratio',
        'age_30_ratio',
        'age_40_ratio',
        'age_50_ratio',
        'age_60_plus_ratio',
    ],
    'time_structure': ['night_ratio', 'morning_ratio', 'daytime_ratio', 'evening_ratio'],
    'resident_age': [
        'resident_ratio_0_19',
        'resident_ratio_20_29',
        'resident_ratio_30_39',
        'resident_ratio_40_49',
        'resident_ratio_50_64',
        'resident_ratio_65_plus',
    ],
    'household_structure': ['hh_1_ratio', 'hh_2_ratio', 'hh_3_ratio', 'hh_4plus_ratio'],
}
CLUSTER_TYPE = {
    0: '고활동·청년유동·1인가구 중심형',
    1: '고령·2인가구·구조적 복지배경 특화형',
    2: '중간활동·다인가구 중심형',
}


def fit_baseline(base_df, config=CONFIG):
    """(특성 표, 가중치 적용 표, 군집 표, 재사용할 모델 묶음)을 반환합니다."""
    feature_frame, pca_artifacts = build_feature_table(
        base_df, pca_columns=PCA_COLUMNS, config=config
    )
    balanced_frame, feature_scaler = balance_domains(feature_frame, config)
    clusters, cluster_model = fit_final_clusters(feature_frame, balanced_frame, config)
    clusters['cluster_type'] = clusters.cluster.map(CLUSTER_TYPE)
    bundle = {
        'model_version': 'analysis1_2025H2_elder_v2',
        'baseline_period': '2025H2',
        'pca_columns': PCA_COLUMNS,
        'pca': pca_artifacts['pca'],
        'feature_scaler': feature_scaler,
        'kmeans': cluster_model,
        'domains': config.domains,
        'cluster_type': CLUSTER_TYPE,
        'baseline_features': feature_frame.copy(),
        'baseline_balanced': balanced_frame.copy(),
        'baseline_clusters': clusters[
            [config.area_key, config.area_name, 'cluster', 'cluster_type']
        ].copy(),
    }
    return feature_frame, balanced_frame, clusters, bundle


def save_baseline(base_df, output_dir, config=CONFIG, results_dir=None):
    """기준 모델과 CSV를 지정한 폴더에 저장하고 계산 결과도 반환합니다."""
    model_directory = Path(output_dir)
    model_directory.mkdir(parents=True, exist_ok=True)
    results_directory = Path(results_dir) if results_dir is not None else model_directory
    results_directory.mkdir(parents=True, exist_ok=True)
    feature_frame, balanced_frame, clusters, bundle = fit_baseline(base_df, config)
    feature_frame.to_csv(
        results_directory / 'gangnam_analysis1_features_2025H2.csv',
        index=False,
        encoding='utf-8-sig',
    )
    pd.concat(
        [
            feature_frame[[config.area_key, config.area_name]].reset_index(drop=True),
            balanced_frame.reset_index(drop=True),
        ],
        axis=1,
    ).to_csv(
        results_directory / 'gangnam_analysis1_balanced_features_2025H2.csv',
        index=False,
        encoding='utf-8-sig',
    )
    clusters.to_csv(
        results_directory / 'gangnam_analysis1_baseline_clusters_2025H2.csv',
        index=False,
        encoding='utf-8-sig',
    )
    joblib.dump(bundle, model_directory / 'analysis1_baseline_2025H2.joblib')
    return feature_frame, balanced_frame, clusters, bundle
