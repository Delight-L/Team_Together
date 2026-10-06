from __future__ import annotations
import numpy as np
import pandas as pd
from common.config import CONFIG
from db.analysis1_repository import Analysis1Repository

def _domain_map(config=CONFIG):
    return {feature: domain for domain, features in config.domains.items() for feature in features}

def baseline_to_db_frames(final_df, feature_cols, period="2025H2", config=CONFIG):
    df = final_df.copy()
    key = config.area_key
    name = config.area_name
    if key not in df.columns or name not in df.columns:
        raise ValueError(f"Analysis1 DB export requires columns: {key}, {name}")

    label_col = next((c for c in ["cluster_type","cluster_label","유형","cluster_name","type_label"] if c in df.columns), None)
    labels = {
        0:"고활동·청년유동·1인가구 중심형",
        1:"고령·2인가구·구조적 복지배경 특화형",
        2:"중간활동·다인가구 중심형",
    }
    base = pd.DataFrame({
        "adm_cd": df[key].astype(str),
        "adm_nm": df[name].astype(str),
        "baseline_period": period,
        "cluster_id": df["cluster"].astype(int),
        "cluster_label": df[label_col].astype(str) if label_col else df["cluster"].map(labels),
        "pca1": df["pca1"] if "pca1" in df else np.nan,
        "pca2": df["pca2"] if "pca2" in df else np.nan,
        "centroid_distance": df["centroid_distance"] if "centroid_distance" in df else np.nan,
    })

    long = df[[key, name] + list(feature_cols)].rename(columns={key:"adm_cd", name:"adm_nm"}).melt(
        id_vars=["adm_cd","adm_nm"], var_name="feature_name", value_name="feature_value"
    )
    long["period"] = period
    dm = _domain_map(config)
    long["domain"] = long["feature_name"].map(dm)
    if long["domain"].isna().any():
        raise ValueError("Unknown Analysis1 feature domain: " + ", ".join(long.loc[long.domain.isna(),"feature_name"].unique()))
    long["is_baseline"] = 1
    return base, long

def export_baseline(db_path, final_df, feature_cols, period="2025H2", config=CONFIG):
    repo = Analysis1Repository(db_path)
    repo.initialize()
    base, features = baseline_to_db_frames(final_df, feature_cols, period, config)
    repo.upsert_baseline(base)
    repo.upsert_features(features)
    return base, features
