"""동별 월간 위험 변화 탐지 로직."""
from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

if __package__:
    from .config import HISTORY_WINDOW, MIN_RELATIVE_CHANGE_PP, ROBUST_Z_THRESHOLD, RiskMetric
else:
    from config import HISTORY_WINDOW, MIN_RELATIVE_CHANGE_PP, ROBUST_Z_THRESHOLD, RiskMetric
if __package__:
    from .data_provider import resolve_risk_metrics, validate_preprocessed_data
else:
    from data_provider import resolve_risk_metrics, validate_preprocessed_data
if __package__:
    from .region_context import CLUSTER_PROFILES, REGION_CODE_CLUSTER_K3
else:
    from region_context import CLUSTER_PROFILES, REGION_CODE_CLUSTER_K3

BASE_COLUMNS = ["행정동코드", "행정동명", "기준연월"]


@dataclass
class RiskAnalysisResult:
    assessment: pd.DataFrame
    signals: pd.DataFrame
    region_alerts: pd.DataFrame


def _mad(values: pd.Series) -> float:
    return float((values - values.median()).abs().median())


def calculate_relative_change_agent(df: pd.DataFrame, metrics: list[RiskMetric]) -> pd.DataFrame:
    df = validate_preprocessed_data(df)
    parts: list[pd.DataFrame] = []
    for metric in metrics:
        part = df[BASE_COLUMNS + [metric.column]].copy().rename(columns={metric.column: "value"})
        part["value"] = pd.to_numeric(part["value"], errors="coerce")
        part["month"] = pd.to_datetime(part["기준연월"], format="%Y-%m")
        part = part.sort_values(["행정동코드", "month"])
        previous = part.groupby("행정동코드")["value"].shift(1)
        part["change_pct"] = ((part["value"] - previous) / previous) * 100
        part.loc[(previous == 0) | ~np.isfinite(part["change_pct"]), "change_pct"] = np.nan
        part["peer_median_change_pct"] = part.groupby("기준연월")["change_pct"].transform("median")
        part["relative_change_pp"] = part["change_pct"] - part["peer_median_change_pct"]
        part["risk_directed_relative_change_pp"] = metric.direction_sign * part["relative_change_pp"]
        part["metric"] = metric.column
        part["metric_label"] = metric.label
        part["risk_direction"] = metric.risk_direction
        part["meaning"] = metric.meaning
        part["metric_rule_source"] = metric.rule_source
        parts.append(part)
    return pd.concat(parts, ignore_index=True)


def _add_history_statistics(group: pd.DataFrame, history_window: int) -> pd.DataFrame:
    group = group.sort_values("month").copy()
    history = group["risk_directed_relative_change_pp"].shift(1)
    group["historical_median_pp"] = history.rolling(history_window, min_periods=history_window).median()
    group["historical_mad_pp"] = history.rolling(history_window, min_periods=history_window).apply(_mad, raw=False)
    return group


def detect_directional_anomaly_agent(changes: pd.DataFrame, min_relative_change_pp: float, z_threshold: float, history_window: int) -> pd.DataFrame:
    if history_window < 3:
        raise ValueError("Robust Z-score는 최소 3회의 과거 변화 이력이 필요합니다.")
    part = pd.concat([_add_history_statistics(g, history_window) for _, g in changes.groupby(["행정동코드", "metric"], sort=False)], ignore_index=True)
    scale = 1.4826 * part["historical_mad_pp"]
    part["risk_robust_z"] = (part["risk_directed_relative_change_pp"] - part["historical_median_pp"]) / scale
    part.loc[(scale.isna()) | (scale == 0) | ~np.isfinite(part["risk_robust_z"]), "risk_robust_z"] = np.nan
    part["has_enough_history"] = part["risk_robust_z"].notna()
    part["passes_relative_change"] = part["risk_directed_relative_change_pp"] >= min_relative_change_pp
    part["passes_robust_z"] = part["risk_robust_z"] >= z_threshold
    part["is_risk_signal"] = part["passes_relative_change"] & part["passes_robust_z"]
    part["minimum_relative_change_pp"] = min_relative_change_pp
    part["robust_z_threshold"] = z_threshold
    return part


def explain_signal_agent(assessment: pd.DataFrame, context: pd.DataFrame | None = None) -> pd.DataFrame:
    part = assessment.copy()
    part["context_note"] = ""
    part["cluster_profile"] = ""
    part["cluster_check_point"] = ""
    # Analysis 1의 확정 k=3 동별 Context를 사용한다. 전달받은 k=2 CSV는 더 이상 해석에 쓰지 않는다.
    part["cluster_k3"] = part["행정동코드"].astype(str).map(REGION_CODE_CLUSTER_K3)
    for cluster_id, profile in CLUSTER_PROFILES.items():
        selected = part["cluster_k3"] == cluster_id
        part.loc[selected, "context_note"] = f"지역 유형: {profile['name']}"
        part.loc[selected, "cluster_profile"] = profile["feature"]
        part.loc[selected, "cluster_check_point"] = profile["check_point"]
    part["explanation"] = ""
    selected = part["is_risk_signal"]
    part.loc[selected, "explanation"] = (part.loc[selected, "행정동명"] + "의 " + part.loc[selected, "metric_label"] + ": 전월 대비 " + part.loc[selected, "change_pct"].map(lambda v: f"{v:+.1f}%") + ", 같은 달 동 중앙값 대비 위험 방향으로 " + part.loc[selected, "risk_directed_relative_change_pp"].map(lambda v: f"{v:.1f}%p") + " 더 크게 " + part.loc[selected, "risk_direction"] + "했습니다. Robust Z-score는 " + part.loc[selected, "risk_robust_z"].map(lambda v: f"{v:.2f}") + "입니다.")
    return part


def build_region_alerts(signals: pd.DataFrame) -> pd.DataFrame:
    columns = ["행정동코드", "행정동명", "기준연월", "signal_count", "signals", "alert_level", "summary"]
    if signals.empty:
        return pd.DataFrame(columns=columns)
    alerts = signals.groupby(["행정동코드", "행정동명", "기준연월"], as_index=False).agg(signal_count=("metric", "nunique"), signals=("metric_label", lambda xs: ", ".join(sorted(set(xs)))))
    alerts["alert_level"] = np.where(alerts["signal_count"] >= 2, "다중 지표 위험 변화 후보", "위험 변화 후보")
    alerts["summary"] = alerts.apply(lambda r: f"{r['행정동명']}에서 {r['signal_count']}개 지표가 위험 방향의 이례적 변화로 탐지됨.", axis=1)
    return alerts.sort_values(["기준연월", "signal_count", "행정동명"], ascending=[False, False, True])


def run_risk_analysis(preprocessed_monthly_data: pd.DataFrame, context: pd.DataFrame | None = None, min_relative_change_pp: float = MIN_RELATIVE_CHANGE_PP, z_threshold: float = ROBUST_Z_THRESHOLD, history_window: int = HISTORY_WINDOW, metric_columns: list[str] | None = None) -> RiskAnalysisResult:
    metrics = resolve_risk_metrics(preprocessed_monthly_data, metric_columns)
    changes = calculate_relative_change_agent(preprocessed_monthly_data, metrics)
    assessment = detect_directional_anomaly_agent(changes, min_relative_change_pp, z_threshold, history_window)
    assessment = explain_signal_agent(assessment, context)
    signals = assessment.loc[assessment["is_risk_signal"]].copy()
    return RiskAnalysisResult(assessment, signals, build_region_alerts(signals))
