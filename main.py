import pandas as pd
from pathlib import Path
from preprocessing.cleaning import cvt2csv

#전처리 폴더 지정
PROCESSED = Path(__file__).resolve().parent / "data" / "processed"
# print(PROCESSED)

#전처리 여부 확인
if not (PROCESSED / "time_pop.csv").exists():
    cvt2csv()

#전처리된 데이터
time_pop = pd.read_csv(PROCESSED / "time_pop.csv", dtype={"BLOCK_CD": str})
age_pop = pd.read_csv(PROCESSED / "age_pop.csv", dtype={"BLOCK_CD": str})
wkdy_pop = pd.read_csv(PROCESSED / "wkdy_pop.csv", dtype={"BLOCK_CD": str})
sh_data = pd.read_csv(PROCESSED / "sh_data.csv", dtype={"BLOCK_CD": str})

