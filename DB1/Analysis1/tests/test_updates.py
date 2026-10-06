from pathlib import Path
import sys
import json
import numpy as np
import pandas as pd
import pytest
from analysis.baseline import fit_baseline
from analysis.change_detector import detect_changes
from preprocessing.periods import halfyear,quarter_indices
from preprocessing.resident import preprocess_resident
from preprocessing.household import preprocess_household
from preprocessing.disability import preprocess_disability
from preprocessing.skt_flow import validate_against_reference

ROOT=Path(__file__).resolve().parents[1]

@pytest.fixture(scope='module')
def reference(): return pd.read_csv(ROOT/'data/reference/reference_pca_input_2025H2.csv',dtype={'adm_cd':str})

@pytest.fixture(scope='module')
def bundle(reference): return fit_baseline(reference)[3]

def test_index_and_order_do_not_change_results(reference,bundle):
    shuffled=reference.sample(frac=1,random_state=1)
    shuffled.index=range(100,122)
    _,_,result=detect_changes(shuffled,bundle,'2026H1')
    assert not result.cluster_changed.any()
    np.testing.assert_allclose(result.filter(like='delta_'),0,atol=1e-12)
    np.testing.assert_allclose(result.filter(like='_distance_from_baseline'),0,atol=1e-12)

def test_missing_and_unknown_area_rejected(reference,bundle):
    with pytest.raises(ValueError): detect_changes(reference.iloc[:-1],bundle,'2026H1')
    unknown=reference.copy();unknown.loc[0,'adm_cd']='9999999'
    with pytest.raises(ValueError): detect_changes(unknown,bundle,'2026H1')

def test_halfyear_2026():
    year,quarters,dates=halfyear('2026H1')
    assert year==2026 and quarters==(1,2)
    assert dates.strftime('%Y%m').tolist()==['202601','202602','202603','202604','202605','202606']
    assert halfyear('2026H2')[2].strftime('%Y%m').tolist()==['202607','202608','202609','202610','202611','202612']

def test_new_year_quarter_and_disability_headers(monkeypatch,reference):
    # Schema fixtures derived from the existing snapshot; these are not 2026 observations.
    settings=json.loads((ROOT.parent/'config/db1_config.json').read_text(encoding='utf-8'))['analysis1']['public']
    from preprocessing.loader import read_local
    import preprocessing.resident as resident_module
    import preprocessing.household as household_module
    import preprocessing.disability as disability_module
    resident=read_local(settings['resident'])
    resident.columns=[str(c).replace('2025 3/4','2026 1/4').replace('2025 4/4','2026 2/4') for c in resident.columns]
    monkeypatch.setattr(resident_module,'read_local',lambda *a,**k:resident.copy())
    people=preprocess_resident('fixture',2026,(1,2))
    assert len(people)==22
    household=read_local(settings['household'],sep='\t')
    names=list(household.columns)
    for quarter,start in [(1,2),(2,13)]:
        for n,index in enumerate(range(start,start+11)): names[index]=f'2026 {quarter}/4'+('' if n==0 else f'.{n}')
    household.columns=names
    monkeypatch.setattr(household_module,'read_local',lambda *a,**k:household.copy())
    assert len(preprocess_household('fixture',2026,(1,2)))==22
    disability=read_local(settings['disability'],sep='\t').rename(columns={'2025 년':'2026 년'})
    monkeypatch.setattr(disability_module,'read_local',lambda *a,**k:disability.copy())
    assert len(preprocess_disability('fixture',people,2026))==22
    with pytest.raises(ValueError): preprocess_disability('fixture',people,2027)

def test_reference_requires_full_coverage(reference):
    assert not validate_against_reference(reference.iloc[:1],ROOT/'data/reference/reference_pca_input_2025H2.csv')['ok']

def test_public_source_discovery_uses_requested_quarters(monkeypatch,tmp_path):
    sys.path.insert(0,str(ROOT))
    import update_worker
    resident=tmp_path/'등록인구_2026.csv';resident.touch()
    household=tmp_path/'세대원수별_2026.csv';household.touch()
    disability=tmp_path/'장애인 현황(장애유형별_2026.csv';disability.touch()
    frames={resident:pd.DataFrame(columns=['a','b','c']+[f'2026 {quarter}/4'+('' if n==0 else f'.{n}') for quarter in [1,2] for n in range(22)]),household:pd.DataFrame(columns=['a','b']+[f'2026 {quarter}/4'+('' if n==0 else f'.{n}') for quarter in [1,2] for n in range(11)]),disability:pd.DataFrame(columns=['2026 년'])}
    monkeypatch.setattr(update_worker,'read_local',lambda path,**kw:frames[Path(path)])
    settings={'analysis1':{'public_root':str(tmp_path),'public':{'resident':'old','household':'old','disability':'old','welfare':'old_welfare'}}}
    sources=update_worker.public_sources(settings,{},2026,(1,2))
    assert sources['resident']==str(resident)
    assert sources['household']==str(household)
    assert sources['disability']==str(disability)
    with pytest.raises(ValueError): update_worker.public_sources(settings,{},2026,(3,4))

def test_actual_public_originals_match_reference():
    import runpy
    helper=runpy.run_path(str(ROOT/'tests/test_public_preprocessing.py'))['compare_public_features']
    sources=json.loads((ROOT.parent/'config/db1_config.json').read_text(encoding='utf-8'))['analysis1']['public']
    passed,differences=helper(ROOT/'data/reference/reference_pca_input_2025H2.csv',sources['resident'],sources['household'],sources['disability'],sources['welfare'])
    assert passed,differences
