"""Analysis1 원본 파일 → 동별 1행 입력 표 변환기.

raw_data 폴더의 원본 파일 5종을 읽어 강남구 22개 행정동마다 한 줄씩 지역 특성을 만듭니다.
결과는 지역 유형(군집) 분석의 입력이며, 사회적 고립 위험 점수가 아닙니다.
"""
from pathlib import Path
import json

import pandas as pd

# 행정동 코드가 같은데 이름이 바뀐 동은 지금 이름으로 통일합니다(일원2동 → 개포3동).
CURRENT_NAME = {"1123074": "개포3동"}
GANGNAM_DONGS = {
    "신사동", "논현1동", "논현2동", "압구정동", "청담동", "삼성1동", "삼성2동", "대치1동",
    "대치2동", "대치4동", "역삼1동", "역삼2동", "도곡1동", "도곡2동", "개포1동", "개포2동",
    "개포3동", "개포4동", "세곡동", "일원본동", "일원1동", "수서동",
}
# PCA(주성분 분석)에 묶어서 넣을 열 목록입니다.
PCA_MAPPING = {
    "active_pop": ["male_ratio", "age_10_ratio", "age_20_ratio", "age_30_ratio", "age_40_ratio",
                   "age_50_ratio", "age_60_plus_ratio"],
    "time_structure": ["night_ratio", "morning_ratio", "daytime_ratio", "evening_ratio"],
    "resident_age": ["resident_ratio_0_19", "resident_ratio_20_29", "resident_ratio_30_39",
                     "resident_ratio_40_49", "resident_ratio_50_64", "resident_ratio_65_plus"],
    "household_structure": ["hh_1_ratio", "hh_2_ratio", "hh_3_ratio", "hh_4plus_ratio"],
}
# 등록인구 연령 열을 분석용 연령대로 묶는 규칙입니다.
RESIDENT_AGE_GROUPS = {
    "0_19": ["age_0_4", "age_5_9", "age_10_14", "age_15_19"],
    "20_29": ["age_20_24", "age_25_29"],
    "30_39": ["age_30_34", "age_35_39"],
    "40_49": ["age_40_44", "age_45_49"],
    "50_64": ["age_50_54", "age_55_59", "age_60_64"],
    "65_plus": ["age_65_69", "age_70_74", "age_75_79", "age_80_84", "age_85_89", "age_90_94",
                "age_95_99", "age_100_plus"],
}
SKT_COLUMNS = [
    "adm_cd", "dong_name", "flow_per_point", "male_ratio", "age_10_ratio", "age_20_ratio", "age_30_ratio",
    "age_40_ratio", "age_50_ratio", "age_60_plus_ratio", "night_ratio", "morning_ratio", "daytime_ratio",
    "evening_ratio", "weekend_weekday_index",
]
HOUSEHOLD_COLUMNS = ["total", "hh_1", "hh_2", "hh_3", "hh_4", "hh_5", "hh_6", "hh_7", "hh_8", "hh_9", "hh_10plus"]


class PreprocessError(ValueError):
    """원본 파일이 없거나 형식이 달라 전처리를 계속할 수 없을 때 냅니다."""


def read_csv(path: Path) -> pd.DataFrame:
    """원본 CSV는 인코딩·구분자가 제각각이라, 열이 2개 이상 읽히는 조합을 찾을 때까지 시도합니다."""
    for encoding in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        for separator in (",", "\t"):
            try:
                frame = pd.read_csv(path, encoding=encoding, sep=separator, low_memory=False)
            except Exception:
                continue
            if frame.shape[1] > 1:
                return frame
    raise PreprocessError(f"읽을 수 없는 CSV: {path.name}")


def find_file(raw_dir: Path, name_part: str) -> Path:
    """파일 이름에 name_part가 들어간 원본 파일을 찾습니다(날짜·괄호가 달라도 됨)."""
    found = list(raw_dir.glob(f"*{name_part}*"))
    if not found:
        raise PreprocessError(f"원본 폴더에 '{name_part}' 파일이 없습니다.")
    return found[0]


def to_number(column: pd.Series) -> pd.Series:
    """'1,234'·'-' 같은 표기를 숫자로 바꿉니다. '-'는 0으로 봅니다."""
    text = column.astype(str).str.replace(",", "").replace("-", "0")
    return pd.to_numeric(text, errors="coerce")


def normalize_dong_names(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["adm_cd"] = frame["adm_cd"].astype(str).str.replace(r"\.0$", "", regex=True)
    frame["dong_name"] = frame["dong_name"].astype(str).str.strip()
    for code, name in CURRENT_NAME.items():
        frame.loc[frame["adm_cd"] == code, "dong_name"] = name
    return frame


def skt_features(frame: pd.DataFrame) -> pd.DataFrame:
    """SKT 유동인구 특성: 필요한 열만 골라 동마다 한 줄로 만듭니다."""
    missing = [column for column in SKT_COLUMNS if column not in frame]
    if missing:
        raise PreprocessError("SKT 유동인구 파일 필수 열 누락: " + ", ".join(missing))
    return normalize_dong_names(frame[SKT_COLUMNS]).drop_duplicates("adm_cd")


def age_column_name(label) -> str:
    """등록인구 헤더(예: '20~24세', '100세 이상')를 열 이름(age_20_24, age_100_plus)으로 바꿉니다."""
    if label == "합계":
        return "total"
    return "age_" + str(label).replace("~", "_").replace("세 이상", "_plus").replace("세", "")


def resident_quarters(frame: pd.DataFrame) -> pd.DataFrame:
    """등록인구 파일을 분기(Q3·Q4)별 표로 나눕니다.

    원본은 1행이 연령 헤더이고, 3번째 열부터 22개 열이 Q3, 그다음 22개 열이 Q4입니다.
    """
    rows = frame[(frame["동별(1)"] == "강남구") & (frame["동별(2)"] != "소계")]
    age_labels = frame.iloc[0, 3:25].tolist()
    quarters = []
    for quarter, start in [("Q3", 3), ("Q4", 25)]:
        part = rows[["동별(2)", "항목"] + list(frame.columns[start:start + 22])].copy()
        part.columns = ["dong_name", "category"] + [age_column_name(label) for label in age_labels]
        for column in part.columns[2:]:
            part[column] = to_number(part[column])
        part["quarter"] = quarter
        quarters.append(part)
    return pd.concat(quarters)


def resident_features(frame: pd.DataFrame) -> pd.DataFrame:
    """주민 연령대 비율과 외국인 비율(Q3·Q4 평균)을 계산합니다."""
    quarters = resident_quarters(frame)
    total = quarters[quarters["category"] == "계"].copy()
    foreign = quarters[quarters["category"] == "등록외국인"][["dong_name", "quarter", "total"]]
    foreign = foreign.rename(columns={"total": "foreign"})

    for group, columns in RESIDENT_AGE_GROUPS.items():
        total["resident_ratio_" + group] = total[columns].sum(axis=1) / total["total"]
    total = total.merge(foreign, on=["dong_name", "quarter"], validate="one_to_one")
    total["foreigner_ratio"] = total["foreign"] / total["total"]

    columns = ["dong_name"] + ["resident_ratio_" + group for group in RESIDENT_AGE_GROUPS] + ["foreigner_ratio"]
    return total[columns].groupby("dong_name", as_index=False).mean()


def resident_totals(frame: pd.DataFrame) -> pd.DataFrame:
    """동별 총인구(Q3·Q4 평균). 장애인·수급자 비율의 분모로 씁니다."""
    rows = frame[(frame["동별(1)"] == "강남구") & (frame["동별(2)"] != "소계") & (frame["항목"] == "계")].copy()
    q3_total = pd.to_numeric(rows.iloc[:, 3], errors="coerce")
    q4_total = pd.to_numeric(rows.iloc[:, 25], errors="coerce")
    rows["resident_total"] = (q3_total + q4_total) / 2
    return rows[["동별(2)", "resident_total"]].rename(columns={"동별(2)": "dong_name"})


def household_features(frame: pd.DataFrame) -> pd.DataFrame:
    """세대원수별 세대 비율(1인·2인·3인·4인 이상, Q3·Q4 평균).

    원본은 3번째 행부터 동별 값이고, 3번째 열부터 11개 열이 Q3, 14번째 열부터 11개 열이 Q4입니다.
    """
    rows = frame.iloc[2:]
    quarters = []
    for start in (2, 13):
        part = rows.iloc[:, [1] + list(range(start, start + 11))].copy()
        part.columns = ["dong_name"] + HOUSEHOLD_COLUMNS
        for column in HOUSEHOLD_COLUMNS:
            part[column] = to_number(part[column])
        quarters.append(part)
    counts = pd.concat(quarters)

    ratios = counts[["dong_name"]].copy()
    ratios["hh_1_ratio"] = counts["hh_1"] / counts["total"]
    ratios["hh_2_ratio"] = counts["hh_2"] / counts["total"]
    ratios["hh_3_ratio"] = counts["hh_3"] / counts["total"]
    four_or_more = ["hh_4", "hh_5", "hh_6", "hh_7", "hh_8", "hh_9", "hh_10plus"]
    ratios["hh_4plus_ratio"] = counts[four_or_more].sum(axis=1) / counts["total"]
    return ratios.groupby("dong_name", as_index=False).mean()


def disability_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """동별 2025년 장애인 수(장애유형 합계, 남녀 계)."""
    if "2025 년" in frame:
        year_column = "2025 년"
    else:
        year_column = next((column for column in frame if "2025" in str(column)), None)
    if not year_column:
        raise PreprocessError("장애인 파일에서 2025년 값 열을 찾지 못했습니다.")
    rows = frame[(frame["장애유형별"] == "합계") & (frame["성별"] == "계")].copy()
    rows["disability_count"] = to_number(rows[year_column])
    return rows[["동별", "disability_count"]].rename(columns={"동별": "dong_name"})


def livelihood_counts(path: Path) -> pd.DataFrame:
    """동별 기초생계급여 수급자 수.

    같은 동 이름이 다른 자치구에도 있으므로, 원본에서 강남구 구간만 잘라 집계합니다.
    """
    raw = pd.read_excel(path, header=None)
    rows = raw.iloc[3:, [0, 1, 2, 4]].copy()
    rows.columns = ["area", "qualification", "age", "count"]
    rows[["area", "qualification"]] = rows[["area", "qualification"]].ffill()
    rows["count"] = pd.to_numeric(rows["count"], errors="coerce")

    start = rows.index[rows["area"] == "강남구"].min()
    after = rows.loc[start:]
    is_other_district = after["area"].astype(str).str.endswith("구") & (after["area"] != "강남구")
    next_district = after.index[is_other_district].min()
    gangnam = rows.loc[start:next_district - 1]

    livelihood = gangnam[gangnam["area"].isin(GANGNAM_DONGS) & (gangnam["qualification"] == "기초생계급여")]
    counts = livelihood.groupby("area", as_index=False)["count"].sum()
    return counts.rename(columns={"area": "dong_name", "count": "livelihood_count"})


def preprocess_raw_dir(raw_dir) -> tuple[pd.DataFrame, dict]:
    """원본 폴더를 읽어 (동별 입력 표, 검증 보고서)를 돌려줍니다."""
    raw_dir = Path(raw_dir)
    resident_file = read_csv(find_file(raw_dir, "등록인구"))

    skt = skt_features(read_csv(find_file(raw_dir, "gangnam_db1_features")))
    resident = resident_features(resident_file)
    totals = resident_totals(resident_file)
    household = household_features(read_csv(find_file(raw_dir, "세대원수별")))
    disability = disability_counts(read_csv(find_file(raw_dir, "장애인 현황(장애유형별")))
    livelihood = livelihood_counts(find_file(raw_dir, "국민기초생활 수급자 동별 현황"))

    # 모든 표를 동 이름으로 붙입니다. 동마다 정확히 한 줄씩이어야 합니다.
    base = skt
    for table in [resident, household, totals, disability, livelihood]:
        base = base.merge(table, on="dong_name", validate="one_to_one")
    base["disability_ratio"] = base["disability_count"] / base["resident_total"]
    base["livelihood_recipient_ratio"] = base["livelihood_count"] / base["resident_total"]
    base = base.drop(columns=["resident_total", "disability_count", "livelihood_count"]).sort_values("adm_cd")

    dong_count = base["adm_cd"].nunique()
    missing_count = int(base.isna().sum().sum())
    if dong_count != 22 or missing_count:
        raise PreprocessError(f"[판단 보류] 22개 동/결측 검증 실패: 동={dong_count}, 결측={missing_count}")

    report = {
        "status": "PASS", "rows": len(base), "unit": "강남구 행정동 1행", "period": "2025H2 구조자료",
        "requires_human_review": False, "rule_version": "analysis1-raw-adapter-v1",
        "note": "지역 유형 맥락용 전처리이며 사회적 고립 위험 점수가 아님",
    }
    return base, report


def save(base: pd.DataFrame, report: dict, output: Path):
    """입력 표(CSV), PCA 열 목록, 검증 보고서를 output 폴더에 저장합니다."""
    output.mkdir(parents=True, exist_ok=True)
    base.to_csv(output / "analysis1_input.csv", index=False, encoding="utf-8-sig")
    (output / "pca_columns.json").write_text(json.dumps(PCA_MAPPING, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "preprocessing_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
