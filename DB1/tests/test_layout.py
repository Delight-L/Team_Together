from pathlib import Path
import json
import pandas as pd
import db1_store

ROOT=Path(__file__).resolve().parents[1]

def test_operational_config_and_model_locations():
    config=json.loads((ROOT/'config/db1_config.json').read_text(encoding='utf-8'))
    assert (ROOT/config['database']).is_file()
    assert (ROOT/config['analysis1']['baseline_model']).is_file()
    a3path=ROOT/'Analysis3/config/analysis3_config.json'
    a3=json.loads(a3path.read_text(encoding='utf-8'))
    assert (a3path.parent/a3['database']).resolve()==(ROOT/config['database']).resolve()
    assert (ROOT/'Analysis3/db/schema.sql').is_file()

def test_export_routes_history_and_integrated_results(tmp_path):
    db1_store.export_csv(ROOT/'outputs/db1.sqlite',tmp_path/'integrated',tmp_path/'analysis2')
    assert (tmp_path/'integrated/db1_integrated.csv').is_file()
    assert not (tmp_path/'integrated/analysis2_history.csv').exists()
    history=pd.read_csv(tmp_path/'analysis2/history.csv')
    detection=pd.read_csv(tmp_path/'analysis2/detection.csv')
    assert len(history)==1056
    assert len(detection)==132
    assert len(pd.read_csv(tmp_path/'analysis2/monthly/2025-12/features.csv'))==22
    assert len(pd.read_csv(tmp_path/'analysis2/monthly/2025-12/detection.csv'))==22
