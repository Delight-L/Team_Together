import numpy as np
import pandas as pd
from preprocessing.resident import preprocess_resident
from preprocessing.household import preprocess_household
from preprocessing.disability import preprocess_disability
from preprocessing.welfare import preprocess_welfare

def compare_public_features(reference_file, resident_file, household_file, disability_file, welfare_file, atol=1e-12):
    ref = pd.read_csv(reference_file, encoding="utf-8-sig")
    resident = preprocess_resident(resident_file)
    household = preprocess_household(household_file)
    disability = preprocess_disability(disability_file, resident)
    welfare = preprocess_welfare(welfare_file, resident)
    generated = resident.merge(household,on="dong_name").merge(disability,on="dong_name").merge(welfare,on="dong_name")
    common = [c for c in generated.columns if c in ref.columns and c != "dong_name"]
    m = ref.merge(generated,on="dong_name",suffixes=("_ref","_new"),validate="one_to_one")
    diffs = {c: float(np.max(np.abs(m[c+"_ref"]-m[c+"_new"]))) for c in common}
    passed = all(v <= atol for v in diffs.values()) and len(m)==22
    return passed, diffs

if __name__ == "__main__":
    print("이 모듈의 compare_public_features()에 로컬 원본 경로를 전달해 검증하세요.")
