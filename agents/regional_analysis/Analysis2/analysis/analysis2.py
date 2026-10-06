import numpy as np
import pandas as pd

from common.config import (
    DATE_COLUMN,
    AREA_CODE_COLUMN,
    DETECTION_CORE_COLUMNS,
    MOBILITY_EVIDENCE_COLUMNS,
)


def compute_log_changes(df: pd.DataFrame) -> pd.DataFrame:
    """
    행정동별 Detection Core 변수의 전월 대비 로그 변화량을 계산한다.

    log_change_t = log(x_t) - log(x_{t-1})

    첫 달은 비교할 이전 달이 없으므로 log_change가 NaN이다.
    """
    result = df.copy()

    result[DATE_COLUMN] = pd.to_datetime(result[DATE_COLUMN])

    result = result.sort_values(
        [AREA_CODE_COLUMN, DATE_COLUMN]
    ).reset_index(drop=True)

    for col in DETECTION_CORE_COLUMNS:
        result[f"{col}_log_change"] = (
            np.log(result[col])
            - np.log(result.groupby(AREA_CODE_COLUMN)[col].shift(1))
        )

    return result


def compute_common_adjusted_residuals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detection Core 변수의 로그 변화량에서
    같은 달 강남구 22개 행정동의 중앙값(median)을 제거한다.

    residual = dong_log_change - monthly_gangnam_median

    이를 통해 특정 월에 강남구 전체에서 공통적으로 나타난 변화를 제거하고,
    각 행정동에 상대적으로 특이하게 나타난 변화만 남긴다.
    """
    result = df.copy()

    for col in DETECTION_CORE_COLUMNS:
        log_change_col = f"{col}_log_change"
        common_change_col = f"{col}_common_change"
        residual_col = f"{col}_residual"

        result[common_change_col] = (
            result.groupby(DATE_COLUMN)[log_change_col]
            .transform("median")
        )

        result[residual_col] = (
            result[log_change_col]
            - result[common_change_col]
        )

    return result


def expanding_robust_z(
    df: pd.DataFrame,
    min_history: int,
    scale: float,
) -> pd.DataFrame:
    """
    행정동별 Detection Core residual에 대해
    과거 데이터만 사용하는 Expanding Robust Z를 계산한다.

    현재 시점 t의 기준선에는 t 시점의 residual을 포함하지 않는다.
    최소 min_history개의 유효한 과거 residual이 확보된 경우에만 계산한다.

    Robust Z = scale * (x_t - historical_median) / historical_MAD
    """
    result = df.copy()

    for col in DETECTION_CORE_COLUMNS:
        residual_col = f"{col}_residual"
        rz_col = f"{col}_rz"
        baseline_n_col = f"{col}_baseline_n"

        result[rz_col] = np.nan
        result[baseline_n_col] = 0

        for _, group in result.groupby(AREA_CODE_COLUMN, sort=False):
            indices = group.index.tolist()

            for pos, idx in enumerate(indices):
                current_value = result.at[idx, residual_col]

                # 현재 시점 이전의 residual만 사용
                history = (
                    group.iloc[:pos][residual_col]
                    .dropna()
                )

                result.at[idx, baseline_n_col] = len(history)

                if pd.isna(current_value) or len(history) < min_history:
                    continue

                historical_median = history.median()

                mad = np.median(
                    np.abs(history - historical_median)
                )

                # 과거 변동성이 전혀 없는 경우 계산하지 않음
                if mad == 0 or pd.isna(mad):
                    continue

                result.at[idx, rz_col] = (
                    scale
                    * (current_value - historical_median)
                    / mad
                )

    return result


def detect_signals(
    df: pd.DataFrame,
    threshold: float,
) -> pd.DataFrame:
    """
    Expanding Robust Z를 이용해 Communication / Mobility 행동변화 신호를 탐지한다.

    Communication:
        call_contacts_rz와 text_contacts_rz가 모두 threshold 이하

    Mobility:
        weekday_move_count_rz와 weekend_move_count_rz가 모두 threshold 이하

    Combined:
        Communication과 Mobility가 동시에 탐지

    Any:
        두 도메인 중 하나 이상 탐지
    """
    result = df.copy()

    operational_mask = (
        result[
            [
                "call_contacts_rz",
                "text_contacts_rz",
                "weekday_move_count_rz",
                "weekend_move_count_rz",
            ]
        ]
        .notna()
        .all(axis=1)
    )

    result["communication_signal"] = (
        operational_mask
        & (result["call_contacts_rz"] <= threshold)
        & (result["text_contacts_rz"] <= threshold)
    )

    result["mobility_signal"] = (
        operational_mask
        & (result["weekday_move_count_rz"] <= threshold)
        & (result["weekend_move_count_rz"] <= threshold)
    )

    result["combined_signal"] = (
        result["communication_signal"]
        & result["mobility_signal"]
    )

    result["any_signal"] = (
        result["communication_signal"]
        | result["mobility_signal"]
    )

    return result


def compute_mobility_distance_evidence(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mobility Detection Signal의 사후 검증을 위해
    평일·주말 이동거리의 공통변화 조정 residual을 계산한다.

    이동거리 변수는 Detection Core에는 포함하지 않으며,
    탐지된 Mobility 신호를 보조적으로 확인하는 Evidence로만 사용한다.

    계산:
    1. 행정동별 전월 대비 log change
    2. 같은 달 강남구 22개 행정동의 log change 중앙값 계산
    3. 행정동 log change - 월별 중앙값 = residual
    """
    result = df.copy()

    for col in MOBILITY_EVIDENCE_COLUMNS:
        log_change_col = f"{col}_log_change"
        common_change_col = f"{col}_common_change"
        residual_col = f"{col}_residual"

        result[log_change_col] = (
            np.log(result[col])
            - np.log(
                result.groupby(AREA_CODE_COLUMN)[col].shift(1)
            )
        )

        result[common_change_col] = (
            result.groupby(DATE_COLUMN)[log_change_col]
            .transform("median")
        )

        result[residual_col] = (
            result[log_change_col]
            - result[common_change_col]
        )

    return result


def attach_mobility_evidence(df: pd.DataFrame) -> pd.DataFrame:
    """
    이동거리 변화 방향을 Evidence 변수로 계산한다.

    Detection 자체에는 영향을 주지 않는다.
    Evidence는 전체 분석 행에서 계산하며,
    Mobility Signal에 대한 검증 시 해당 신호 행만 필터링하여 사용한다.
    """
    result = df.copy()

    result["weekday_distance_down"] = (
        result["weekday_move_distance_residual"] < 0
    )

    result["weekend_distance_down"] = (
        result["weekend_move_distance_residual"] < 0
    )

    result["mobility_distance_both_down"] = (
        result["weekday_distance_down"]
        & result["weekend_distance_down"]
    )

    result["mobility_distance_support"] = (
        result["weekday_distance_down"]
        | result["weekend_distance_down"]
    )

    return result


def attach_communication_validation(df: pd.DataFrame) -> pd.DataFrame:
    """
    Communication Signal에 관심집단 기반 보조 Validation을 부착한다.

    comm_low_rate의 전월 대비 증가 여부를 확인한다.

    이 지표는 Detection 조건에는 사용하지 않으며,
    이미 탐지된 Communication Signal의 보조 해석에만 사용한다.
    """
    result = df.copy()

    result["comm_low_rate_change"] = (
        result
        .groupby(AREA_CODE_COLUMN)["comm_low_rate"]
        .diff()
    )

    result["comm_validation_support"] = (
        result["comm_low_rate_change"] > 0
    )

    return result


def attach_signal_status(df: pd.DataFrame) -> pd.DataFrame:
    """
    탐지된 Any Signal에 New / Continuing 상태를 부착한다.

    - New:
      해당 월에 신호가 탐지되었지만 직전 월에는 신호가 없었던 경우

    - Continuing:
      해당 월에 신호가 탐지되었고 직전 월에도 신호가 있었던 경우

    주의:
    원천 행동변수는 최근 3개월 평균 기반이므로
    Continuing을 '위험 악화' 또는 '장기 지속 위험'으로 해석하지 않는다.
    """
    result = df.copy()

    result = result.sort_values(
        [AREA_CODE_COLUMN, DATE_COLUMN]
    ).reset_index(drop=True)

    previous_signal = (
        result.groupby(AREA_CODE_COLUMN)["any_signal"]
        .shift(1)
        .fillna(False)
        .astype(bool)
    )

    result["signal_status"] = pd.NA

    signal_mask = result["any_signal"]

    result.loc[
        signal_mask & ~previous_signal,
        "signal_status"
    ] = "New"

    result.loc[
        signal_mask & previous_signal,
        "signal_status"
    ] = "Continuing"

    return result


def attach_analysis1_context(
    df: pd.DataFrame,
    context_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Analysis2 Detection 결과에 Analysis1 지역유형 Context를 결합한다.

    Analysis1 Context는 Detection 이후에만 결합하며,
    행동변화 신호 탐지 조건에는 사용하지 않는다.

    Join key:
        Analysis2 행정동코드
        Analysis1 adm_cd
    """
    result = df.copy()

    context = context_df[
        ["adm_cd", "dong_name", "cluster", "cluster_type"]
    ].copy()

    # 결합키 자료형 통일
    result[AREA_CODE_COLUMN] = (
        pd.to_numeric(result[AREA_CODE_COLUMN], errors="raise")
        .astype(int)
    )

    context["adm_cd"] = (
        pd.to_numeric(context["adm_cd"], errors="raise")
        .astype(int)
    )

    # Analysis1은 행정동당 1행이어야 한다.
    if context["adm_cd"].duplicated().any():
        raise ValueError(
            "Analysis1 Context에 중복된 adm_cd가 존재합니다."
        )

    result = result.merge(
        context,
        how="left",
        left_on=AREA_CODE_COLUMN,
        right_on="adm_cd",
        validate="many_to_one",
    )

    return result


def run_analysis2_pipeline(
    df: pd.DataFrame,
    context_df: pd.DataFrame,
    min_history: int,
    scale: float,
    threshold: float,
) -> pd.DataFrame:
    """
    Analysis2 전체 분석 파이프라인을 순서대로 실행한다.

    Feature Table
        → Detection Core log change
        → Gangnam common-change adjustment
        → Mobility distance evidence
        → Historical expanding Robust Z
        → Signal detection
        → Mobility evidence
        → Communication validation
        → Signal status
        → Analysis1 context

    Analysis1 Context는 Detection 완료 이후에만 결합한다.
    """
    result = compute_log_changes(df)

    result = compute_common_adjusted_residuals(result)

    result = compute_mobility_distance_evidence(result)

    result = expanding_robust_z(
        result,
        min_history=min_history,
        scale=scale,
    )

    result = detect_signals(
        result,
        threshold=threshold,
    )

    result = attach_mobility_evidence(result)

    result = attach_communication_validation(result)

    result = attach_signal_status(result)

    result = attach_analysis1_context(
        result,
        context_df=context_df,
    )

    return result