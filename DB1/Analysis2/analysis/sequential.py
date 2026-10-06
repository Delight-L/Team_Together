from __future__ import annotations
import pandas as pd
from analysis.analysis2 import run_analysis2_pipeline
from analysis.outputs import build_detection_table, build_evidence_card
from common.config import MIN_HISTORY, ROBUST_Z_SCALE, ROBUST_Z_THRESHOLD, DATE_COLUMN, AREA_CODE_COLUMN

BASELINE_END = pd.Timestamp("2025-06-01")
DETECTION_START = pd.Timestamp("2025-07-01")

def split_baseline_and_stream(feature_df, baseline_end=BASELINE_END):
    df = feature_df.copy()
    df[DATE_COLUMN] = pd.to_datetime(df[DATE_COLUMN])
    df = df.sort_values([DATE_COLUMN, AREA_CODE_COLUMN]).reset_index(drop=True)
    history = df.loc[df[DATE_COLUMN] <= baseline_end].copy()
    stream = df.loc[df[DATE_COLUMN] > baseline_end].copy()
    return history, stream

def run_month(history_df, current_month_df, context_df,
              min_history=MIN_HISTORY, scale=ROBUST_Z_SCALE, threshold=ROBUST_Z_THRESHOLD,
              return_history=False):
    current_month_df = current_month_df.copy()
    current_month_df[DATE_COLUMN] = pd.to_datetime(
    current_month_df[DATE_COLUMN],
    format="mixed",
    )
    months = current_month_df[DATE_COLUMN].drop_duplicates()
    if len(months) != 1:
        raise ValueError("current_month_df must contain exactly one month.")
    current_period = months.iloc[0]

    history_df = history_df.copy()
    history_df[DATE_COLUMN] = pd.to_datetime(
    history_df[DATE_COLUMN],
    format="mixed",
    )
    if (history_df[DATE_COLUMN] >= current_period).any():
        raise ValueError("History must contain only months before the current month.")

    combined = pd.concat([history_df, current_month_df], ignore_index=True)
    result = run_analysis2_pipeline(
        combined, context_df, min_history=min_history, scale=scale, threshold=threshold
    )
    current_result = result.loc[result[DATE_COLUMN] == current_period].copy()
    if len(current_result) != len(current_month_df):
        raise ValueError("Current-month output row count mismatch.")
    if return_history:
        return result
    return current_result

def run_sequential(feature_df, context_df, baseline_end=BASELINE_END):
    """
    baseline_end까지의 데이터를 초기 History로 사용하고,
    이후 데이터를 월별로 순차 처리한다.

    각 월은 반드시 해당 월 이전의 History만 사용한다.
    current month의 탐지가 끝난 뒤에만 History에 append한다.

    signal_status는 run_month() 내부에서
    직전 월 any_signal을 기준으로 계산한다.
    """
    history, stream = split_baseline_and_stream(
        feature_df,
        baseline_end
    )

    monthly_results = []

    for period in sorted(
        pd.to_datetime(stream[DATE_COLUMN]).drop_duplicates()
    ):
        current = stream.loc[
            pd.to_datetime(stream[DATE_COLUMN]) == period
        ].copy()

        current_result = run_month(
            history,
            current,
            context_df
        )

        monthly_results.append(current_result)

        # 현재 월 분석 완료 후에만 History에 추가
        history = pd.concat(
            [history, current],
            ignore_index=True
        )

    if not monthly_results:
        return pd.DataFrame()

    sequential_result = pd.concat(
        monthly_results,
        ignore_index=True
    )

    sequential_result = sequential_result.sort_values(
        [AREA_CODE_COLUMN, DATE_COLUMN]
    ).reset_index(drop=True)

    return sequential_result

def build_sequential_outputs(feature_df, context_df, baseline_end=BASELINE_END):
    result = run_sequential(feature_df, context_df, baseline_end)
    return result, build_detection_table(result), build_evidence_card(result)
