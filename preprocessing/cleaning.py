import pandas as pd
import os

os.makedirs(r"./data/processed", exist_ok=True)
months = ["07", "08", "09", "10", "11", "12"]

# dedup -> 중복 제거 여부
def load(month: str, kind: str, dedup: bool = False) -> pd.DataFrame:
    df = pd.read_csv(f"./data/raw/flow_{kind}_pop_2025{month}.csv", sep="|", dtype={"BLOCK_CD": str})
    return df.drop_duplicates() if dedup else df

# ---------------------------------------------------------------------------------------#
# 데이터셋1,2 변환
def cvt2csv():
    # 공지사항: flow_time_pop_202512.csv, flow_wkdy_pop_202512.csv 는 중복값 제거 후 사용
    age_pop = pd.concat([load(m, "age") for m in months], ignore_index=True)
    time_pop = pd.concat([load(m, "time", dedup=(m == "12")) for m in months], ignore_index=True)
    wkdy_pop = pd.concat([load(m, "wkdy", dedup=(m == "12")) for m in months], ignore_index=True)
    sh_data = pd.read_csv("./data/raw/신한카드_빅콘테스트2026_데이터2.txt", sep="\t", encoding="cp949")
    # ---------------------------------------------------------------------------------------#

    #데이터 정제
    age_pop.to_csv("./data/processed/age_pop.csv", index=False)
    time_pop.to_csv("./data/processed/time_pop.csv", index=False)
    wkdy_pop.to_csv("./data/processed/wkdy_pop.csv", index=False)
    sh_data.to_csv("./data/processed/sh_data.csv", index=False)


if __name__ == "__main__":
    cvt2csv()