from __future__ import annotations
import calendar
from pathlib import Path
import numpy as np
import pandas as pd

def _weighted_mean(group, value_col, weight):
    values = pd.to_numeric(group[value_col], errors="coerce")
    weights = pd.to_numeric(weight, errors="coerce")
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return np.nan
    return np.average(values[mask], weights=weights[mask])

def _weather_value(rain_df, diary_df, year, month):
    key = f"{year}. {month:02d}"
    rainfall = pd.to_numeric(
        rain_df.loc[rain_df["항목"].eq("강수량 (㎜)"), key], errors="coerce"
    ).iloc[0]
    rain_days = pd.to_numeric(
        rain_df.loc[rain_df["항목"].eq("강수일수 (일)"), key], errors="coerce"
    ).iloc[0]
    snow_raw = diary_df.loc[diary_df["시점"].eq(key), "눈"].iloc[0]
    snow_days = 0.0 if str(snow_raw).strip() == "-" else float(snow_raw)
    return float(rain_days), float(rainfall), float(snow_days)

def build_month_feature_table(
    telecom_path,
    interest_path,
    rain_path,
    diary_path,
    year,
    month,
    district="강남구",
):
    telecom = pd.read_excel(telecom_path)
    interest = pd.read_excel(interest_path)
    rain = pd.read_csv(rain_path, encoding="utf-8-sig")
    diary = pd.read_csv(diary_path, encoding="utf-8-sig")

    return build_month_feature_frames(telecom, interest, rain, diary, year, month, district)


def build_month_feature_frames(telecom, interest, rain, diary, year, month, district="강남구"):

    telecom = telecom.loc[telecom["자치구"].eq(district)].copy()
    interest = interest.loc[interest["자치구"].eq(district)].copy()

    if telecom[["행정동코드","행정동"]].drop_duplicates().shape[0] != 22:
        raise ValueError("통신정보의 강남구 행정동이 22개가 아닙니다.")
    if interest[["행정동코드","행정동명"]].drop_duplicates().shape[0] != 22:
        raise ValueError("관심집단의 강남구 행정동이 22개가 아닙니다.")

    move_specs = [
        ("weekday_move_count", "평일 총 이동 횟수", "평일 총 이동 횟수 미추정 인구수", "weekday_count_est_ratio"),
        ("weekend_move_count", "휴일 총 이동 횟수 평균", "휴일 이동 미추정 인구수", "weekend_count_est_ratio"),
        ("weekday_move_distance", "평일 총 이동 거리 합계", "평일 총 이동 거리 미추정 인구수", "weekday_distance_est_ratio"),
        ("weekend_move_distance", "휴일 총 이동 거리 합계", "휴일 총 이동 거리 미추정 인구수", "weekend_distance_est_ratio"),
    ]

    rows = []
    for (code, name), group in telecom.groupby(["행정동코드","행정동"], sort=True):
        total_pop = pd.to_numeric(group["총인구수"], errors="coerce")
        row = {
            "date": pd.Timestamp(year, month, 1),
            "행정동코드": int(code),
            "행정동": name,
            "call_contacts": _weighted_mean(group, "평균 통화대상자 수", total_pop),
            "text_contacts": _weighted_mean(group, "평균 문자대상자 수", total_pop),
        }
        total = total_pop.sum()
        for out_col, value_col, missing_col, ratio_col in move_specs:
            estimated = total_pop - pd.to_numeric(group[missing_col], errors="coerce")
            row[out_col] = _weighted_mean(group, value_col, estimated)
            row[ratio_col] = estimated.sum() / total
        rows.append(row)
    result = pd.DataFrame(rows)

    interest_rows = []
    for (code, _), group in interest.groupby(["행정동코드","행정동명"], sort=True):
        one_person = pd.to_numeric(group["1인가구수"], errors="coerce")
        denominator = one_person.sum()
        raw_cols = [
            "커뮤니케이션이 적은 집단",
            "평일 외출이 적은 집단",
            "휴일 외출이 적은 집단",
        ]
        sums = [pd.to_numeric(group[c], errors="coerce").sum() for c in raw_cols]
        interest_rows.append({
            "행정동코드": int(code),
            "comm_low_rate": sums[0] / denominator,
            "weekday_outing_low_rate": sums[1] / denominator,
            "weekend_outing_low_rate": sums[2] / denominator,
            # 원 보고서의 구조적 단절 정의: 세 관심집단이 동시에 전 셀 0인 동×월.
            "interest_structural_issue": bool(all(v == 0 for v in sums)),
        })
    result = result.merge(pd.DataFrame(interest_rows), on="행정동코드", validate="one_to_one")

    rain_days, rainfall_mm, snow_days = _weather_value(rain, diary, year, month)
    result["rain_days"] = rain_days
    result["rainfall_mm"] = rainfall_mm
    result["snow_days"] = snow_days

    n_days = calendar.monthrange(year, month)[1]
    dates = pd.date_range(pd.Timestamp(year, month, 1), periods=n_days, freq="D")
    result["days_in_month"] = n_days
    result["weekday_days"] = int((dates.weekday < 5).sum())
    result["weekend_days"] = int((dates.weekday >= 5).sum())

    columns = [
        "date","행정동코드","행정동",
        "call_contacts","text_contacts",
        "weekday_move_count","weekend_move_count",
        "weekday_move_distance","weekend_move_distance",
        "weekday_count_est_ratio","weekday_distance_est_ratio",
        "weekend_count_est_ratio","weekend_distance_est_ratio",
        "comm_low_rate","weekday_outing_low_rate","weekend_outing_low_rate",
        "rain_days","rainfall_mm","snow_days",
        "days_in_month","weekday_days","weekend_days",
        "interest_structural_issue",
    ]
    return result[columns].sort_values("행정동코드").reset_index(drop=True)
