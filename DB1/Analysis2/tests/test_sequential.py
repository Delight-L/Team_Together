import pandas as pd
import numpy as np
from data.ingestion import load_analysis2_input
from analysis.analysis2 import run_analysis2_pipeline
from analysis.sequential import run_sequential
from common.config import MIN_HISTORY, ROBUST_Z_SCALE, ROBUST_Z_THRESHOLD

def test_sequential_matches_historical_only():
    df = load_analysis2_input("data/reference/gangnam_analysis2_feature_table_2022_2025.csv")
    ctx = pd.read_csv("data/reference/gangnam_analysis1_final_region_typology_2025H2.csv")
    df["date"] = pd.to_datetime(df["date"])

    legacy = run_analysis2_pipeline(df, ctx, MIN_HISTORY, ROBUST_Z_SCALE, ROBUST_Z_THRESHOLD)
    legacy = legacy.loc[legacy["date"] >= pd.Timestamp("2025-07-01")].sort_values(["date","행정동코드"]).reset_index(drop=True)
    seq = run_sequential(df, ctx).sort_values(["date","행정동코드"]).reset_index(drop=True)

    assert len(seq) == 132
    assert seq["any_signal"].equals(legacy["any_signal"])
    assert seq["signal_status"].fillna("NA").equals(legacy["signal_status"].fillna("NA"))

    for col in seq.columns.intersection(legacy.columns):
        if pd.api.types.is_numeric_dtype(seq[col]) and pd.api.types.is_numeric_dtype(legacy[col]):
            np.testing.assert_allclose(
                pd.to_numeric(seq[col], errors="coerce"),
                pd.to_numeric(legacy[col], errors="coerce"),
                rtol=0, atol=1e-12, equal_nan=True
            )
