import pandas as pd
import pytest
from pathlib import Path
from data.monthly_validation import validate_feature_rows
from analysis.analysis2 import attach_analysis1_context
from run_analysis2_sequential import find_month_file

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture
def monthly():
    df=pd.read_csv(ROOT/'data/reference/gangnam_analysis2_feature_table_2022_2025.csv')
    return df.loc[df.date=='2025-07-01'].copy()

@pytest.mark.parametrize('value',[float('nan'),float('inf'),0,-1])
def test_bad_log_values_rejected(monthly,value):
    monthly.iloc[0,monthly.columns.get_loc('call_contacts')]=value
    with pytest.raises(ValueError):validate_feature_rows(monthly)

def test_wrong_area_and_missing_column_rejected(monthly):
    codes=monthly['행정동코드'].copy()
    monthly.iloc[0,monthly.columns.get_loc('행정동코드')]=9999999
    with pytest.raises(ValueError):validate_feature_rows(monthly,codes)
    with pytest.raises(ValueError):validate_feature_rows(monthly.drop(columns='text_contacts'))

def test_context_must_cover_all_regions(monthly):
    ctx=pd.read_csv(ROOT/'data/reference/gangnam_analysis1_final_region_typology_2025H2.csv')
    with pytest.raises(ValueError):attach_analysis1_context(monthly,ctx.iloc[1:])

def test_2026_month_filename_discovery(tmp_path):
    path=tmp_path/'2026.1월_29개 통신정보.xlsx';path.touch()
    assert find_month_file(tmp_path,2026,1,'29개')==path
