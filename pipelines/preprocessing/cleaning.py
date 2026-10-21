"""공모전 제공 원본(유동인구·카드) → 종합 현황 그룹 자료용 CSV 변환.

data/raw의 월별 원본(flow_age/time/wkdy_pop_2025MM.csv, 신한카드 자료)을 7~12월로 합쳐
data/processed에 저장합니다. 종합 현황의 그룹 자료(db/group_repository.build_snapshot)가 이 결과를 읽습니다.

실행: python pipelines/preprocessing/cleaning.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
MONTHS = ["07", "08", "09", "10", "11", "12"]
CARD_FILE = "신한카드_빅콘테스트2026_데이터2.txt"


def load_flow(month, kind, dedup=False):
    """한 달치 유동인구 원본을 읽습니다. kind는 age·time·wkdy 중 하나입니다."""
    frame = pd.read_csv(
        RAW_DIR / f"flow_{kind}_pop_2025{month}.csv", sep="|", dtype={"BLOCK_CD": str}
    )
    if dedup:
        return frame.drop_duplicates()
    return frame


def combine_months(kind):
    """7~12월을 하나로 합칩니다. 공지에 따라 12월 time·wkdy 자료는 중복 행을 지우고 씁니다."""
    frames = []
    for month in MONTHS:
        dedup = kind in ("time", "wkdy") and month == "12"
        frames.append(load_flow(month, kind, dedup))
    return pd.concat(frames, ignore_index=True)


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    for kind in ["age", "time", "wkdy"]:
        combine_months(kind).to_csv(PROCESSED_DIR / f"{kind}_pop.csv", index=False)
    card = pd.read_csv(RAW_DIR / CARD_FILE, sep="\t", encoding="cp949")
    card.to_csv(PROCESSED_DIR / "sh_data.csv", index=False)
    print(f"[완료] {PROCESSED_DIR}에 age_pop·time_pop·wkdy_pop·sh_data.csv를 저장했습니다.")


if __name__ == "__main__":
    main()
