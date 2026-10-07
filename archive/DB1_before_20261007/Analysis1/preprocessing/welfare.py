import pandas as pd

def preprocess_welfare(path, resident):
    """서울시 동별 기초생활수급자 원본에서 강남구 생계급여 수급자 비율을 생성한다."""
    raw = pd.read_excel(path, header=None)
    welfare = raw.iloc[3:, [0, 1, 2, 4]].copy()
    welfare.columns = ["area", "qualification", "age_group", "recipient_count"]
    welfare["area"] = welfare["area"].ffill()
    welfare["qualification"] = welfare["qualification"].ffill()
    welfare["recipient_count"] = pd.to_numeric(welfare["recipient_count"], errors="coerce")

    # 서울 전체에는 동일 동명이 존재할 수 있으므로 반드시 강남구 블록을 먼저 제한한다.
    gangnam_idx = welfare.index[welfare["area"] == "강남구"].tolist()
    if not gangnam_idx:
        raise ValueError("복지 원본에서 강남구 블록을 찾을 수 없습니다.")
    start = min(gangnam_idx)
    after = welfare.loc[start:].copy()
    district_rows = after[after["area"].astype(str).str.endswith("구")][["area"]].copy()
    district_rows = district_rows[district_rows["area"].ne(district_rows["area"].shift())]
    next_start = district_rows[district_rows["area"] != "강남구"].index.min()
    block = welfare.loc[start:] if pd.isna(next_start) else welfare.loc[start:next_start-1]

    dongs = set(resident["dong_name"])
    livelihood = block[
        block["area"].isin(dongs)
        & (block["qualification"] == "기초생계급여")
    ].copy()

    counts = (
        livelihood.groupby("area", as_index=False)["recipient_count"].sum()
        .rename(columns={"area": "dong_name", "recipient_count": "livelihood_count"})
    )
    out = resident[["dong_name", "resident_total"]].merge(
        counts, on="dong_name", how="left", validate="one_to_one"
    )
    out["livelihood_count"] = out["livelihood_count"].fillna(0)
    out["livelihood_recipient_ratio"] = out["livelihood_count"] / out["resident_total"]
    return out[["dong_name", "livelihood_recipient_ratio"]]
