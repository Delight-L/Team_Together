"""기존 통신·카드 원본을 읽어 종류별 CSV로 합칩니다.

지역 유형 전처리(preprocessing_agent)와는 별도의 작업입니다.
"""

from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data" / "raw"
OUTPUT_DIR = ROOT_DIR / "data" / "processed"
YEAR = "2025"
MONTHS = ["07", "08", "09", "10", "11", "12"]


# dedup -> 중복 제거 여부
def load(month: str, kind: str, dedup: bool = False) -> pd.DataFrame:
    """한 달·한 종류의 통신 원본을 읽습니다."""
    path = RAW_DIR / f"flow_{kind}_pop_{YEAR}{month}.csv"
    data = pd.read_csv(path, sep="|", dtype={"BLOCK_CD": str})
    if dedup:
        data = data.drop_duplicates()
    return data


# ---------------------------------------------------------------------------------------#
# 데이터셋1,2 변환
def cvt2csv():
    """6개월 자료를 합쳐 age/time/wkdy/sh_data CSV를 저장합니다."""
    # 공지사항: flow_time_pop_202512.csv, flow_wkdy_pop_202512.csv 는 중복값 제거 후 사용
    age_tables = []
    time_tables = []
    weekday_tables = []
    for month in MONTHS:
        age_tables.append(load(month, "age"))
        remove_duplicates = month == "12"
        time_tables.append(load(month, "time", dedup=remove_duplicates))
        weekday_tables.append(load(month, "wkdy", dedup=remove_duplicates))

    age_pop = pd.concat(age_tables, ignore_index=True)
    time_pop = pd.concat(time_tables, ignore_index=True)
    wkdy_pop = pd.concat(weekday_tables, ignore_index=True)
    card_path = RAW_DIR / "신한카드_빅콘테스트2026_데이터2.txt"
    sh_data = pd.read_csv(card_path, sep="\t", encoding="cp949")
    # ---------------------------------------------------------------------------------------#

    # 데이터 정제
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    age_pop.to_csv(OUTPUT_DIR / "age_pop.csv", index=False)
    time_pop.to_csv(OUTPUT_DIR / "time_pop.csv", index=False)
    wkdy_pop.to_csv(OUTPUT_DIR / "wkdy_pop.csv", index=False)
    sh_data.to_csv(OUTPUT_DIR / "sh_data.csv", index=False)


if __name__ == "__main__":
    cvt2csv()
