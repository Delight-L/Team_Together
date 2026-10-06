from .loader import read_local
from .resident import preprocess_resident
from .household import preprocess_household
from .disability import preprocess_disability
from .welfare import preprocess_welfare

SKT_COLS = [
    "adm_cd","dong_name","flow_per_point","male_ratio",
    "age_10_ratio","age_20_ratio","age_30_ratio","age_40_ratio",
    "age_50_ratio","age_60_plus_ratio","night_ratio","morning_ratio",
    "daytime_ratio","evening_ratio","weekend_weekday_index"
]

def build_analysis1_pca_input(*, skt_feature, resident_file, household_file,
                              disability_file, welfare_file,year=2025,quarters=(3,4),disability_year=None,quarter_blocks=None):
    skt = read_local(skt_feature)[SKT_COLS].copy()
    resident = preprocess_resident(resident_file,year,quarters,(quarter_blocks or {}).get('resident'))
    household = preprocess_household(household_file,year,quarters,(quarter_blocks or {}).get('household'))
    disability = preprocess_disability(disability_file, resident,disability_year or year)
    welfare = preprocess_welfare(welfare_file, resident)

    out = (
        skt.merge(resident, on="dong_name", validate="one_to_one")
           .merge(household, on="dong_name", validate="one_to_one")
           .merge(disability, on="dong_name", validate="one_to_one")
           .merge(welfare, on="dong_name", validate="one_to_one")
    )
    if len(out) != 22 or out["dong_name"].nunique() != 22 or out["dong_name"].duplicated().any():
        raise ValueError("Analysis1 PCA 입력은 강남구 22개 행정동 1행씩이어야 합니다.")
    if out.isna().any().any():
        raise ValueError("Analysis1 PCA 입력에 결측값이 있습니다.")
    return out
