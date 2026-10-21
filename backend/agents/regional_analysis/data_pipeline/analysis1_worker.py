"""Use the approved frozen PCA/scaling/K-means model for local feature inputs."""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# 분석 코드·모델·참조자료는 공식 DB1 파이프라인(pipelines/db1)을 그대로 씁니다.
DB1 = ROOT.parents[2] / 'pipelines' / 'db1'
sys.path.insert(0, str(DB1))
sys.path.insert(0, str(DB1 / 'Analysis1'))
import joblib
import numpy as np
import pandas as pd
import db1_store as store
from analysis.change_detector import detect_changes
from common.config import CONFIG


def process(cfg, bootstrap, input_path=None, period=None):
    period = '2025H2' if bootstrap else period
    if not period or not re.fullmatch(r'20\d{2}H[12]', period):
        raise ValueError('Use YYYYH1 or YYYYH2')
    if not bootstrap and period <= '2025H2':
        raise ValueError('The approved 2025H2 baseline is immutable')
    source = (
        DB1 / 'Analysis1/data/reference/reference_pca_input_2025H2.csv'
        if bootstrap
        else Path(input_path)
    )
    frame = pd.read_csv(source, dtype={'adm_cd': str})
    model_path = DB1 / cfg['analysis1']['baseline_model']
    model = joblib.load(model_path)
    model_sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    store.initialize(cfg['database'])
    with store.connect(cfg['database']) as con:
        old = con.execute(
            "SELECT metadata_json FROM db1_run WHERE analysis='analysis1' AND period='2025H2'"
        ).fetchone()
        if old and json.loads(old[0]).get('model_sha256', model_sha) != model_sha:
            raise ValueError('Approved k-means model changed; explicit migration required')
    features, balanced, change = detect_changes(frame, model, period)
    if bootstrap and (
        change.cluster_changed.any() or change.filter(like='delta_').abs().to_numpy().max() > 1e-10
    ):
        raise ValueError('Saved model does not reproduce the approved reference')
    clusters = features.copy()
    clusters['cluster'] = change.current_cluster
    clusters['cluster_type'] = change.current_cluster_type
    clusters['centroid_distance'] = np.linalg.norm(
        balanced.to_numpy() - model['kmeans'].cluster_centers_[clusters.cluster.to_numpy(int)],
        axis=1,
    )
    y = int(period[:4])
    h = int(period[-1])
    effective = (
        '2025-07-01' if bootstrap else f'{y if h == 1 else y + 1}-{7 if h == 1 else 1:02d}-01'
    )
    metadata = {
        'feature_domains': {f: d for d, cols in CONFIG.domains.items() for f in cols},
        'period': period,
        'effective_from': effective,
        'retrospective_context': bootstrap,
        'model_file': cfg['analysis1']['baseline_model'],
        'method': 'frozen_PCA_scaler_kmeans_predict',
        'model_sha256': model_sha,
        'scope': 'existing_22_Gangnam_dongs',
        'new_region_requires_model_and_feature_approval': True,
    }
    saved = store.commit_a1(
        cfg['database'],
        frame,
        features,
        clusters,
        period,
        effective,
        bootstrap,
        None if bootstrap else change,
        metadata,
    )
    print(
        json.dumps(
            {
                'analysis1': period,
                'saved': saved,
                'rows': len(features),
                'effective_from': effective,
            }
        ),
        flush=True,
    )


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--config', required=True)
    p.add_argument('--bootstrap', action='store_true')
    p.add_argument('--input')
    p.add_argument('--period')
    a = p.parse_args()
    process(json.loads(Path(a.config).read_text(encoding='utf-8')), a.bootstrap, a.input, a.period)
