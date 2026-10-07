from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from common.config import Analysis1Config, CONFIG
from common.result_schema import AnalysisResult
from data.validation import validate_table, require_pass


PCA_GROUPS = {
    "active_pop": 2,
    "time_structure": 2,
    "resident_age": 2,
    "household_structure": 2,
}


def fit_pca_block(
    df: pd.DataFrame,
    columns: Sequence[str],
    prefix: str,
    n_components: int = 2,
) -> tuple[pd.DataFrame, dict]:
    """Standardize a compositional block, then return PCA scores and metadata."""
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{prefix}: missing PCA source columns: {missing}")
    x = df[list(columns)].astype(float)
    if x.isna().any().any():
        raise ValueError(f"{prefix}: PCA source contains missing values.")

    scaler = StandardScaler()
    xz = scaler.fit_transform(x)
    pca = PCA(n_components=n_components)
    scores = pca.fit_transform(xz)

    score_df = pd.DataFrame(
        scores,
        index=df.index,
        columns=[f"{prefix}_pc{i+1}" for i in range(n_components)],
    )
    meta = {
        "source_columns": list(columns),
        "explained_variance_ratio": pca.explained_variance_ratio_.tolist(),
        "cumulative_explained_variance": float(pca.explained_variance_ratio_.sum()),
        "scaler": scaler,
        "pca": pca,
    }
    return score_df, meta


def build_feature_table(
    base_df: pd.DataFrame,
    *,
    pca_columns: Mapping[str, Sequence[str]],
    config: Analysis1Config = CONFIG,
) -> tuple[pd.DataFrame, dict]:
    """
    Build the approved 13-feature Analysis 1 table.

    base_df must already be one row per administrative dong and contain:
    - activity_intensity
    - weekend_weekday_index
    - foreigner_ratio
    - disability_ratio
    - livelihood_recipient_ratio
    - raw columns required by each PCA block.

    Spatial joins / source-specific reshaping belong in preprocessing adapters,
    not in this statistical core.
    """

    base_df = base_df.rename(
        columns=config.input_feature_map
    ).copy()

    key_cols = [config.area_key]
    if config.area_name in base_df.columns:
        key_cols.append(config.area_name)

    direct = [
        "activity_intensity",
        "weekend_weekday_index",
        "foreigner_ratio",
        "disability_ratio",
        "livelihood_recipient_ratio",
    ]
    report = validate_table(
        base_df,
        key_cols + direct,
        area_key=config.area_key,
        expected_areas=config.expected_areas,
        unique_area=True,
        non_numeric_columns=key_cols,
    )
    require_pass(report)

    out = base_df[key_cols + direct].copy()
    artifacts: dict = {"pca": {}}

    for prefix, n_components in PCA_GROUPS.items():
        if prefix not in pca_columns:
            raise ValueError(f"Missing PCA mapping for '{prefix}'.")
        scores, meta = fit_pca_block(
            base_df, pca_columns[prefix], prefix, n_components=n_components
        )
        out = pd.concat([out, scores], axis=1)
        artifacts["pca"][prefix] = meta

    feature_cols = [c for cols in config.domains.values() for c in cols]
    out = out[key_cols + feature_cols]

    final_report = validate_table(
        out,
        key_cols + feature_cols,
        area_key=config.area_key,
        expected_areas=config.expected_areas,
        unique_area=True,
        non_numeric_columns=key_cols,
    )
    require_pass(final_report)
    artifacts["validation"] = final_report
    return out, artifacts


def balance_domains(
    feature_df: pd.DataFrame,
    config: Analysis1Config = CONFIG,
) -> tuple[pd.DataFrame, StandardScaler]:
    """
    Z-score all 13 features and apply 1/sqrt(n) inside each domain.
    This equalizes expected squared-distance contribution across four domains.
    """
    feature_cols = [c for cols in config.domains.values() for c in cols]
    scaler = StandardScaler()
    z = pd.DataFrame(
        scaler.fit_transform(feature_df[feature_cols]),
        columns=feature_cols,
        index=feature_df.index,
    )

    balanced = z.copy()
    for _, cols in config.domains.items():
        weight = 1.0 / math.sqrt(len(cols))
        balanced.loc[:, list(cols)] *= weight

    return balanced, scaler


def evaluate_kmeans(
    x: pd.DataFrame,
    config: Analysis1Config = CONFIG,
) -> pd.DataFrame:
    rows = []
    for k in config.k_candidates:
        model = KMeans(n_clusters=k, random_state=config.random_state, n_init=50)
        labels = model.fit_predict(x)
        sizes = pd.Series(labels).value_counts().sort_index().tolist()
        rows.append({
            "k": k,
            "silhouette": float(silhouette_score(x, labels)),
            "inertia": float(model.inertia_),
            "cluster_sizes": "/".join(map(str, sizes)),
            "has_singleton": any(s == 1 for s in sizes),
        })
    return pd.DataFrame(rows)


def perturbation_stability(
    x: pd.DataFrame,
    *,
    k_values: Sequence[int] = (2, 3),
    config: Analysis1Config = CONFIG,
) -> pd.DataFrame:
    rng = np.random.default_rng(config.random_state)
    rows = []
    x_arr = x.to_numpy(dtype=float)

    for k in k_values:
        base = KMeans(
            n_clusters=k, random_state=config.random_state, n_init=50
        ).fit_predict(x_arr)

        for noise_sd in config.perturbation_noise:
            aris = []
            for i in range(config.perturbation_repeats):
                noisy = x_arr + rng.normal(0.0, noise_sd, size=x_arr.shape)
                labels = KMeans(
                    n_clusters=k,
                    random_state=config.random_state + i + 1,
                    n_init=20,
                ).fit_predict(noisy)
                aris.append(adjusted_rand_score(base, labels))

            rows.append({
                "k": k,
                "noise_sd": noise_sd,
                "mean_ari": float(np.mean(aris)),
                "ari_ge_threshold_rate": float(
                    np.mean(np.asarray(aris) >= config.ari_threshold)
                ),
            })
    return pd.DataFrame(rows)


def fit_final_clusters(
    feature_df: pd.DataFrame,
    balanced: pd.DataFrame,
    config: Analysis1Config = CONFIG,
) -> tuple[pd.DataFrame, KMeans]:
    model = KMeans(
        n_clusters=config.final_k,
        random_state=config.random_state,
        n_init=100,
    )
    labels = model.fit_predict(balanced)
    result = feature_df.copy()
    result["cluster"] = labels
    return result, model


def build_cluster_profile(
    cluster_df: pd.DataFrame,
    raw_profile_df: pd.DataFrame | None,
    *,
    profile_columns: Sequence[str] | None = None,
    config: Analysis1Config = CONFIG,
) -> pd.DataFrame:
    """
    Reconnect cluster labels to interpretable original variables.
    raw_profile_df should be one row per dong.
    """
    if raw_profile_df is None:
        numeric = [
            c for c in cluster_df.select_dtypes(include="number").columns
            if c != "cluster"
        ]
        return cluster_df.groupby("cluster")[numeric].mean()

    cols = list(profile_columns or [
        c for c in raw_profile_df.select_dtypes(include="number").columns
        if c != config.area_key
    ])
    merged = cluster_df[[config.area_key, "cluster"]].merge(
        raw_profile_df[[config.area_key] + cols],
        on=config.area_key,
        how="left",
        validate="one_to_one",
    )
    return merged.groupby("cluster")[cols].mean()


def _json_safe_pca_meta(pca_artifacts: dict) -> dict:
    result = {}
    for name, meta in pca_artifacts.items():
        result[name] = {
            "source_columns": meta["source_columns"],
            "explained_variance_ratio": meta["explained_variance_ratio"],
            "cumulative_explained_variance": meta["cumulative_explained_variance"],
        }
    return result


def save_outputs(
    *,
    feature_df: pd.DataFrame,
    balanced: pd.DataFrame,
    k_metrics: pd.DataFrame,
    stability: pd.DataFrame,
    clusters: pd.DataFrame,
    profile: pd.DataFrame,
    pca_artifacts: dict,
    feature_scaler: StandardScaler,
    cluster_model: KMeans,
    output_dir: str | Path,
    result: AnalysisResult,
) -> dict[str, str]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    paths = {
        "features": out / "analysis1_features.csv",
        "balanced_features": out / "analysis1_balanced_features.csv",
        "k_metrics": out / "analysis1_k_metrics.csv",
        "stability": out / "analysis1_perturbation_stability.csv",
        "clusters": out / "analysis1_clusters.csv",
        "profile": out / "analysis1_cluster_profile.csv",
        "model_bundle": out / "analysis1_model_bundle.joblib",
        "run_manifest": out / "analysis1_run_manifest.json",
    }

    feature_df.to_csv(paths["features"], index=False, encoding="utf-8-sig")
    balanced.to_csv(paths["balanced_features"], index=False, encoding="utf-8-sig")
    k_metrics.to_csv(paths["k_metrics"], index=False, encoding="utf-8-sig")
    stability.to_csv(paths["stability"], index=False, encoding="utf-8-sig")
    clusters.to_csv(paths["clusters"], index=False, encoding="utf-8-sig")
    profile.to_csv(paths["profile"], encoding="utf-8-sig")

    joblib.dump({
        "pca": pca_artifacts,
        "feature_scaler": feature_scaler,
        "kmeans": cluster_model,
    }, paths["model_bundle"])

    result.outputs = {k: str(v) for k, v in paths.items()}
    manifest = result.to_dict()
    manifest["created_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["methodology"] = {
        "final_k": CONFIG.final_k,
        "domains": {k: list(v) for k, v in CONFIG.domains.items()},
        "domain_weight_rule": "1/sqrt(number_of_features_in_domain)",
        "interpretation": "regional context; not a social-isolation risk score",
    }
    manifest["pca"] = _json_safe_pca_meta(pca_artifacts)
    paths["run_manifest"].write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {k: str(v) for k, v in paths.items()}


def run_analysis1(
    base_df: pd.DataFrame,
    *,
    pca_columns: Mapping[str, Sequence[str]],
    raw_profile_df: pd.DataFrame | None = None,
    profile_columns: Sequence[str] | None = None,
    data_period: str | None = None,
    data_version: str | None = None,
    output_dir: str | Path | None = None,
    config: Analysis1Config = CONFIG,
) -> AnalysisResult:
    """
    Stable entry point for VSCode scripts and future AI Agent orchestration.

    The Agent should call this function rather than changing internal statistical
    steps. On failure, status=FAIL is returned and the caller decides whether to
    retain the previous successful version.
    """
    result = AnalysisResult(
        analysis_id="analysis1",
        status="RUNNING",
        data_period=data_period,
        data_version=data_version,
    )
    try:
        feature_df, artifacts = build_feature_table(
            base_df, pca_columns=pca_columns, config=config
        )
        balanced, feature_scaler = balance_domains(feature_df, config)
        k_metrics = evaluate_kmeans(balanced, config)
        stability = perturbation_stability(balanced, config=config)
        clusters, cluster_model = fit_final_clusters(feature_df, balanced, config)
        profile = build_cluster_profile(
            clusters,
            raw_profile_df,
            profile_columns=profile_columns,
            config=config,
        )

        final_sizes = clusters["cluster"].value_counts().sort_index().to_dict()
        result.validation = artifacts["validation"]
        result.metrics = {
            "n_areas": int(feature_df[config.area_key].nunique()),
            "n_features": int(sum(len(v) for v in config.domains.values())),
            "final_k": config.final_k,
            "final_cluster_sizes": {str(k): int(v) for k, v in final_sizes.items()},
            "k_metrics": k_metrics.to_dict(orient="records"),
            "perturbation_stability": stability.to_dict(orient="records"),
        }

        # Agent-facing review flags: do not silently bless unstable structures.
        warnings = []
        if any(v == 1 for v in final_sizes.values()):
            warnings.append("Final clustering contains a singleton cluster.")
        final_stab = stability[stability["k"] == config.final_k]
        if not final_stab.empty and (final_stab["mean_ari"] < 0.8).any():
            warnings.append("Final k has mean ARI below 0.8 at one or more noise levels.")
        result.warnings = warnings
        result.requires_human_review = bool(warnings)
        result.status = "WARNING" if warnings else "PASS"

        out_dir = Path(output_dir or config.output_dir)
        result.outputs = save_outputs(
            feature_df=feature_df,
            balanced=balanced,
            k_metrics=k_metrics,
            stability=stability,
            clusters=clusters,
            profile=profile,
            pca_artifacts=artifacts["pca"],
            feature_scaler=feature_scaler,
            cluster_model=cluster_model,
            output_dir=out_dir,
            result=result,
        )
        return result

    except Exception as exc:
        result.status = "FAIL"
        result.requires_human_review = True
        result.warnings.append(f"{type(exc).__name__}: {exc}")
        return result
