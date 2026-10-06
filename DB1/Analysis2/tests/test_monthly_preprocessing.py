import pandas as pd
import numpy as np
from preprocessing.monthly_features import build_month_feature_table

def test_202201_202202_raw_to_feature_matches_reference():
    reference = pd.read_csv("data/reference/gangnam_analysis2_feature_table_2022_2025.csv")
    reference["date"] = pd.to_datetime(reference["date"])
    generated = []
    for year, month in [(2022,1),(2022,2)]:
        generated.append(build_month_feature_table(
            f"tests/fixtures/{year}.{month:02d}_telecom.xlsx",
            f"tests/fixtures/{year}.{month:02d}_interest.xlsx",
            "tests/fixtures/rain.csv",
            "tests/fixtures/weather_days.csv",
            year, month
        ))
    generated = pd.concat(generated, ignore_index=True).sort_values(["date","행정동코드"]).reset_index(drop=True)
    expected = reference[reference["date"].isin([pd.Timestamp("2022-01-01"),pd.Timestamp("2022-02-01")])].sort_values(["date","행정동코드"]).reset_index(drop=True)
    assert generated.shape == (44,23)
    assert list(generated.columns) == list(expected.columns)
    assert generated["행정동코드"].equals(expected["행정동코드"])
    assert generated["행정동"].equals(expected["행정동"])
    assert generated["interest_structural_issue"].equals(expected["interest_structural_issue"])
    for col in generated.columns:
        if col in ["date","행정동코드","행정동","interest_structural_issue"]:
            continue
        np.testing.assert_allclose(generated[col], expected[col], rtol=0, atol=1e-12, equal_nan=True)
