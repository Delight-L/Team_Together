import pandas as pd

# ---------------------------------------------------------------------------------------#
# 데이터셋1,2 변환

# 데이터셋1_age_pop 변환 및 복사본 활용
age_pop_202507 = pd.read_csv(r"data\sample_data\flow_age_pop_202507.csv", sep="|").copy()
age_pop_202508 = pd.read_csv(r"data\sample_data\flow_age_pop_202508.csv", sep="|").copy()
age_pop_202509 = pd.read_csv(r"data\sample_data\flow_age_pop_202509.csv", sep="|").copy()
age_pop_202510 = pd.read_csv(r"data\sample_data\flow_age_pop_202510.csv", sep="|").copy()
age_pop_202511 = pd.read_csv(r"data\sample_data\flow_age_pop_202511.csv", sep="|").copy()
age_pop_202512 = pd.read_csv(r"data\sample_data\flow_age_pop_202512.csv", sep="|").copy()

# 데이터셋1_time_pop 변환 및 복사본 활용
time_pop_202507 = pd.read_csv(r"data\sample_data\flow_time_pop_202507.csv", sep="|").copy()
time_pop_202508 = pd.read_csv(r"data\sample_data\flow_time_pop_202508.csv", sep="|").copy()
time_pop_202509 = pd.read_csv(r"data\sample_data\flow_time_pop_202509.csv", sep="|").copy()
time_pop_202510 = pd.read_csv(r"data\sample_data\flow_time_pop_202510.csv", sep="|").copy()
time_pop_202511 = pd.read_csv(r"data\sample_data\flow_time_pop_202511.csv", sep="|").copy()
time_pop_202512 = pd.read_csv(r"data\sample_data\flow_time_pop_202512.csv", sep="|").copy()
# 중복값 제거
time_pop_202512 = time_pop_202512.drop_duplicates()

# 데이터셋1_wkdy_pop 변환 및 복사본 활용
wkdy_pop_202507 = pd.read_csv(r"data\sample_data\flow_wkdy_pop_202507.csv", sep="|").copy()
wkdy_pop_202508 = pd.read_csv(r"data\sample_data\flow_wkdy_pop_202508.csv", sep="|").copy()
wkdy_pop_202509 = pd.read_csv(r"data\sample_data\flow_wkdy_pop_202509.csv", sep="|").copy()
wkdy_pop_202510 = pd.read_csv(r"data\sample_data\flow_wkdy_pop_202510.csv", sep="|").copy()
wkdy_pop_202511 = pd.read_csv(r"data\sample_data\flow_wkdy_pop_202511.csv", sep="|").copy()
wkdy_pop_202512 = pd.read_csv(r"data\sample_data\flow_wkdy_pop_202512.csv", sep="|").copy()
# 중복값 제거
wkdy_pop_202512 = wkdy_pop_202512.drop_duplicates()

# 데이터셋2 변환 및 복사본 활용
sh_data = pd.read_csv(r"data\sample_data\신한카드_빅콘테스트2026_데이터2.txt", sep="\t", encoding="cp949").copy()
# ---------------------------------------------------------------------------------------#
