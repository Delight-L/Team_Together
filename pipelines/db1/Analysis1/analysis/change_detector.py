"""저장된 기준 모델로 새 기간을 분류하고, 기준 기간과의 차이를 계산합니다.

새 기간의 자료로 모델을 다시 학습하지 않습니다. 기준 모델의 표준화 값과
PCA·군집 중심을 그대로 사용해야 기간 간 비교 기준이 달라지지 않습니다.
"""

from pathlib import Path
import math
import joblib
import numpy as np
import pandas as pd
from common.config import CONFIG


def _features(df, bundle, config=CONFIG):
    """기준 모델과 같은 열 순서로 현재 기간의 특성 표를 만듭니다."""
    df = df.rename(columns=config.input_feature_map).copy()
    area_columns = [config.area_key, config.area_name]
    feature_frame = df[
        area_columns
        + [
            'activity_intensity',
            'weekend_weekday_index',
            'foreigner_ratio',
            'elderly_living_alone_rate_65plus',
            'livelihood_recipient_ratio',
        ]
    ].copy()
    for block_name, source_columns in bundle['pca_columns'].items():
        pca_model = bundle['pca'][block_name]
        source_values = df[source_columns].astype(float)
        standardized_values = pca_model['scaler'].transform(source_values)
        pca_scores = pca_model['pca'].transform(standardized_values)[:, :2]
        feature_frame[block_name + '_pc1'] = pca_scores[:, 0]
        feature_frame[block_name + '_pc2'] = pca_scores[:, 1]
    feature_columns = [column for columns in config.domains.values() for column in columns]
    return feature_frame[area_columns + feature_columns]


def detect_changes(base_df, bundle_or_path, period, config=CONFIG):
    """22개 동의 자료를 검사하고 (현재 특성, 가중치 적용 특성, 변화 결과)를 반환합니다."""
    from data.validation import validate_table, require_pass

    base_df = base_df.copy().reset_index(drop=True)
    base_df[config.area_key] = base_df[config.area_key].astype(str)
    loaded = (
        joblib.load(bundle_or_path) if isinstance(bundle_or_path, (str, Path)) else bundle_or_path
    )
    if loaded['domains'] != config.domains:
        raise ValueError(
            'Analysis1 model feature domains differ; explicit model migration required'
        )
    required = list(
        dict.fromkeys(
            [
                'flow_per_point',
                'weekend_weekday_index',
                'foreigner_ratio',
                'elderly_living_alone_rate_65plus',
                'livelihood_recipient_ratio',
            ]
            + [column for columns in loaded['pca_columns'].values() for column in columns]
        )
    )
    require_pass(
        validate_table(
            base_df,
            [config.area_key, config.area_name] + required,
            area_key=config.area_key,
            expected_areas=22,
            unique_area=True,
            non_numeric_columns=[config.area_key, config.area_name],
        )
    )
    if set(base_df[config.area_key]) != set(
        loaded['baseline_features'][config.area_key].astype(str)
    ):
        raise ValueError('Current area codes must match baseline')
    bundle = loaded
    current_features = _features(base_df, bundle, config)
    feature_columns = [column for columns in config.domains.values() for column in columns]
    balanced_features = pd.DataFrame(
        bundle['feature_scaler'].transform(current_features[feature_columns]),
        columns=feature_columns,
        index=current_features.index,
    )
    for columns in config.domains.values():
        balanced_features.loc[:, list(columns)] *= 1 / math.sqrt(len(columns))
    model = bundle['kmeans']
    labels = model.predict(balanced_features)
    cluster_distances = model.transform(balanced_features)
    changes = current_features[[config.area_key, config.area_name]].copy()
    changes.insert(2, 'period', period)
    changes['current_cluster'] = labels
    changes['current_cluster_type'] = changes.current_cluster.map(bundle['cluster_type'])
    changes['current_centroid_distance'] = cluster_distances[np.arange(len(labels)), labels]
    baseline_clusters = (
        bundle['baseline_clusters']
        .rename(columns={'cluster': 'baseline_cluster', 'cluster_type': 'baseline_cluster_type'})
        .copy()
    )
    baseline_clusters[config.area_key] = baseline_clusters[config.area_key].astype(str)
    changes = changes.merge(
        baseline_clusters.drop(columns=[config.area_name]),
        on=[config.area_key],
        validate='one_to_one',
    )
    changes['cluster_changed'] = changes.current_cluster != changes.baseline_cluster
    baseline_features = bundle['baseline_features'].copy()
    baseline_features[config.area_key] = baseline_features[config.area_key].astype(str)
    feature_comparison = current_features.merge(
        baseline_features.drop(columns=[config.area_name]),
        on=[config.area_key],
        suffixes=('_current', '_baseline'),
        validate='one_to_one',
    )
    for column in feature_columns:
        changes = changes.merge(
            feature_comparison[[config.area_key, config.area_name]].assign(
                **{
                    f'delta_{column}': feature_comparison[f'{column}_current']
                    - feature_comparison[f'{column}_baseline']
                }
            ),
            on=[config.area_key, config.area_name],
            validate='one_to_one',
        )
    baseline_balanced = bundle['baseline_balanced'].copy()
    baseline_balanced.index = baseline_features[config.area_key].astype(str).values
    for domain, columns in config.domains.items():
        domain_distances = []
        for row_index, row in current_features.iterrows():
            domain_distances.append(
                float(
                    np.linalg.norm(
                        balanced_features.iloc[row_index][list(columns)].to_numpy()
                        - baseline_balanced.loc[str(row[config.area_key]), list(columns)].to_numpy()
                    )
                )
            )
        changes[f'{domain}_distance_from_baseline'] = domain_distances
    baseline_codes = bundle['baseline_clusters'].copy()
    baseline_codes[config.area_key] = baseline_codes[config.area_key].astype(str)
    old_labels = (
        baseline_codes.set_index(config.area_key)
        .loc[current_features[config.area_key], 'cluster']
        .to_numpy(int)
    )
    aligned = baseline_balanced.loc[current_features[config.area_key]].to_numpy(float)
    old_distance = np.linalg.norm(aligned - model.cluster_centers_[old_labels], axis=1)
    changes['centroid_distance_delta'] = changes.current_centroid_distance.to_numpy() - old_distance
    return current_features, balanced_features, changes
