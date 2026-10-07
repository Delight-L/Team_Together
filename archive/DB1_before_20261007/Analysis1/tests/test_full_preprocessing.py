import pandas as pd, numpy as np

def test_regenerated_pca_input_matches_reference():
    ref=pd.read_csv('data/reference/reference_pca_input_2025H2.csv',dtype={'adm_cd':str})
    act=pd.read_csv('data/processed/2025H2/pca_input.csv',dtype={'adm_cd':str})
    assert act.shape==(22,30)
    m=ref.merge(act,on=['adm_cd','dong_name'],suffixes=('_ref','_act'),validate='one_to_one')
    for c in ref.columns[2:]:
        assert np.allclose(m[c+'_ref'],m[c+'_act'],atol=1e-8,rtol=1e-6,equal_nan=True), c
