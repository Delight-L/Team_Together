import pandas as pd

def build_detection_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 Analysis2 파이프라인 결과에서 운영 탐지구간 770행을 추출하고,
    Colab 기준 Detection Table 스키마(55열)로 변환한다.
    """
    result = df.copy()

    # 4개 Detection Core RZ가 모두 존재하는 운영 탐지구간만 사용
    operational_mask = result[
        [
            "call_contacts_rz",
            "text_contacts_rz",
            "weekday_move_count_rz",
            "weekend_move_count_rz",
        ]
    ].notna().all(axis=1)

    result = result.loc[operational_mask].copy()

    # signal_type 생성
    result["signal_type"] = pd.NA

    result.loc[
        result["communication_signal"] & ~result["mobility_signal"],
        "signal_type"
    ] = "Communication"

    result.loc[
        ~result["communication_signal"] & result["mobility_signal"],
        "signal_type"
    ] = "Mobility"

    result.loc[
        result["combined_signal"],
        "signal_type"
    ] = "Combined"

    # 내부 계산용 컬럼명을 Colab 최종 산출물 스키마로 변환
    rename_map = {
        "call_contacts_common_change":
            "call_contacts_gangnam_median_change",
        "text_contacts_common_change":
            "text_contacts_gangnam_median_change",
        "weekday_move_count_common_change":
            "weekday_move_count_gangnam_median_change",
        "weekend_move_count_common_change":
            "weekend_move_count_gangnam_median_change",

        "call_contacts_residual":
            "call_contacts_residual_change",
        "text_contacts_residual":
            "text_contacts_residual_change",
        "weekday_move_count_residual":
            "weekday_move_count_residual_change",
        "weekend_move_count_residual":
            "weekend_move_count_residual_change",

        "call_contacts_rz":
            "call_contacts_residual_change_expanding_rz",
        "text_contacts_rz":
            "text_contacts_residual_change_expanding_rz",
        "weekday_move_count_rz":
            "weekday_move_count_residual_change_expanding_rz",
        "weekend_move_count_rz":
            "weekend_move_count_residual_change_expanding_rz",

        "call_contacts_baseline_n":
            "call_contacts_residual_change_history_n",
        "text_contacts_baseline_n":
            "text_contacts_residual_change_history_n",
        "weekday_move_count_baseline_n":
            "weekday_move_count_residual_change_history_n",
        "weekend_move_count_baseline_n":
            "weekend_move_count_residual_change_history_n",

        "weekday_move_distance_residual":
            "weekday_move_distance_residual_change",
        "weekend_move_distance_residual":
            "weekend_move_distance_residual_change",

        "comm_validation_support":
            "communication_interest_support",
    }

    result = result.rename(columns=rename_map)

    detection_columns = [
        "date",
        "행정동코드",
        "행정동",
        "call_contacts",
        "text_contacts",
        "weekday_move_count",
        "weekend_move_count",
        "weekday_move_distance",
        "weekend_move_distance",
        "weekday_count_est_ratio",
        "weekday_distance_est_ratio",
        "weekend_count_est_ratio",
        "weekend_distance_est_ratio",
        "comm_low_rate",
        "weekday_outing_low_rate",
        "weekend_outing_low_rate",
        "rain_days",
        "rainfall_mm",
        "snow_days",
        "days_in_month",
        "weekday_days",
        "weekend_days",
        "interest_structural_issue",
        "call_contacts_log_change",
        "text_contacts_log_change",
        "weekday_move_count_log_change",
        "weekend_move_count_log_change",
        "call_contacts_gangnam_median_change",
        "text_contacts_gangnam_median_change",
        "weekday_move_count_gangnam_median_change",
        "weekend_move_count_gangnam_median_change",
        "call_contacts_residual_change",
        "text_contacts_residual_change",
        "weekday_move_count_residual_change",
        "weekend_move_count_residual_change",
        "call_contacts_residual_change_expanding_rz",
        "call_contacts_residual_change_history_n",
        "text_contacts_residual_change_expanding_rz",
        "text_contacts_residual_change_history_n",
        "weekday_move_count_residual_change_expanding_rz",
        "weekday_move_count_residual_change_history_n",
        "weekend_move_count_residual_change_expanding_rz",
        "weekend_move_count_residual_change_history_n",
        "communication_signal",
        "mobility_signal",
        "combined_signal",
        "any_signal",
        "signal_type",
        "weekday_move_distance_residual_change",
        "weekend_move_distance_residual_change",
        "weekday_distance_down",
        "weekend_distance_down",
        "mobility_distance_support",
        "comm_low_rate_change",
        "communication_interest_support",
    ]

    result = result[detection_columns].copy()

    result = (
        result
        .sort_values(["date", "행정동코드"])
        .reset_index(drop=True)
    )

    return result


def build_evidence_card(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analysis2 전체 파이프라인 결과에서 탐지된 신호만 추출하여
    Agent 입력용 Evidence Card를 생성한다.
    """
    result = df.loc[df["any_signal"]].copy()

    # 동일 행정동 내 신호 발생 순서
    result = (
        result
        .sort_values(["행정동코드", "date"])
        .reset_index(drop=True)
    )

    # Signal 유형
    result["signal_type"] = pd.NA

    result.loc[
        result["communication_signal"] & ~result["mobility_signal"],
        "signal_type"
    ] = "Communication"

    result.loc[
        ~result["communication_signal"] & result["mobility_signal"],
        "signal_type"
    ] = "Mobility"

    result.loc[
        result["combined_signal"],
        "signal_type"
    ] = "Combined"

    # 동일 행정동의 직전 탐지 신호
    result["previous_signal_date"] = (
        result
        .groupby("행정동코드")["date"]
        .shift(1)
    )

    # 직전 신호와의 개월 차이
    current_date = pd.to_datetime(result["date"])
    previous_date = pd.to_datetime(result["previous_signal_date"])

    result["months_since_previous_signal"] = (
        (current_date.dt.year - previous_date.dt.year) * 12
        + (current_date.dt.month - previous_date.dt.month)
    )

    # 직전 탐지가 바로 전월인지 여부
    result["consecutive_signal"] = (
        result["months_since_previous_signal"] == 1
    )

    # 내부 분석 컬럼명 → 최종 산출물 컬럼명
    rename_map = {
        "call_contacts_rz":
            "call_contacts_residual_change_expanding_rz",
        "text_contacts_rz":
            "text_contacts_residual_change_expanding_rz",
        "weekday_move_count_rz":
            "weekday_move_count_residual_change_expanding_rz",
        "weekend_move_count_rz":
            "weekend_move_count_residual_change_expanding_rz",

        "weekday_move_distance_residual":
            "weekday_move_distance_residual_change",
        "weekend_move_distance_residual":
            "weekend_move_distance_residual_change",

        "comm_validation_support":
            "communication_interest_support",
    }

    result = result.rename(columns=rename_map)

    evidence_columns = [
        "date",
        "행정동코드",
        "행정동",
        "signal_type",
        "signal_status",
        "communication_signal",
        "mobility_signal",
        "combined_signal",
        "call_contacts_residual_change_expanding_rz",
        "text_contacts_residual_change_expanding_rz",
        "weekday_move_count_residual_change_expanding_rz",
        "weekend_move_count_residual_change_expanding_rz",
        "weekday_move_distance_residual_change",
        "weekend_move_distance_residual_change",
        "mobility_distance_support",
        "comm_low_rate_change",
        "communication_interest_support",
        "interest_structural_issue",
        "rain_days",
        "rainfall_mm",
        "snow_days",
        "days_in_month",
        "weekday_days",
        "weekend_days",
        "cluster",
        "cluster_type",
        "previous_signal_date",
        "months_since_previous_signal",
        "consecutive_signal",
    ]

    result = result[evidence_columns].copy()

    # Reference 산출물과 동일한 월 → 행정동 순서
    result = (
        result
        .sort_values(["date", "행정동코드"])
        .reset_index(drop=True)
    )

    return result