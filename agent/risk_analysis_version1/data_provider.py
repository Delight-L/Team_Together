"""CSV 입력 검증과 위험 지표 선택."""
from __future__ import annotations

from pathlib import Path
import pandas as pd

if __package__:
    from .config import METRIC_RULES, NON_METRIC_COLUMNS, RiskMetric
else:
    from config import METRIC_RULES, NON_METRIC_COLUMNS, RiskMetric

REQUIRED_COLUMNS = {"행정동코드", "행정동명", "기준연월"}


def load_preprocessed_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"입력 CSV를 찾을 수 없습니다: {path}")
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(path, encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"CSV 인코딩을 읽을 수 없습니다: {path}")


def validate_preprocessed_data(df: pd.DataFrame) -> pd.DataFrame:
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError("필수 컬럼이 없습니다: " + ", ".join(sorted(missing)))
    result = df.copy()
    result["행정동코드"] = result["행정동코드"].astype(str)
    result["기준연월"] = result["기준연월"].astype(str)
    months = pd.to_datetime(result["기준연월"], format="%Y-%m", errors="coerce")
    if months.isna().any():
        raise ValueError("기준연월은 YYYY-MM 형식이어야 합니다. 예: 2025-07")
    if result.duplicated(["행정동코드", "기준연월"]).any():
        raise ValueError("동 × 월 데이터가 중복되어 있습니다.")
    return result


def resolve_risk_metrics(df: pd.DataFrame, requested_columns: list[str] | None = None) -> list[RiskMetric]:
    """설정된 지표를 우선 사용하고, 없으면 지정/숫자 열을 임시 지표로 사용한다."""
    if requested_columns:
        unknown = [col for col in requested_columns if col not in df.columns]
        if unknown:
            raise ValueError("--metrics에 없는 열이 있습니다: " + ", ".join(unknown))
        candidates = requested_columns
    elif METRIC_RULES:
        candidates = [col for col in METRIC_RULES if col in df.columns]
    else:
        candidates = [
            col for col in df.columns
            if col not in NON_METRIC_COLUMNS and pd.api.types.is_numeric_dtype(df[col])
        ]

    metrics: list[RiskMetric] = []
    for col in candidates:
        if col in METRIC_RULES:
            metrics.append(METRIC_RULES[col])
        else:
            metrics.append(RiskMetric(col, col, "감소", -1, f"{col}의 변화", "임시 자동 규칙"))
    if not metrics:
        raise ValueError("분석할 숫자형 지표 열이 없습니다. --metrics 열이름1,열이름2 로 지정하세요.")
    return metrics
