import json,sqlite3,runpy
from pathlib import Path
import pandas as pd
from analysis.outputs import build_detection_table,build_evidence_card

ROOT=Path(__file__).resolve().parents[1]

def test_actual_raw_database_results_match_reference():
    with sqlite3.connect(ROOT.parent/'outputs/db1.sqlite') as con:
        result=pd.DataFrame([json.loads(r[0]) for r in con.execute('SELECT result_json FROM a2_detection ORDER BY date,adm_cd')])
        evidence=pd.DataFrame([json.loads(r[0]) for r in con.execute('SELECT evidence_json FROM a2_evidence ORDER BY date,adm_cd')])
    result['date']=pd.to_datetime(result.date)
    helper=runpy.run_path(str(ROOT/'tests/test_analysis2.py'))['compare_with_reference']
    for name,build in [('detection',build_detection_table),('evidence_card',build_evidence_card)]:
        ref=pd.read_csv(ROOT/f'data/reference/gangnam_analysis2_{name}_2022_2025.csv')
        ref=ref.loc[pd.to_datetime(ref.date)>=pd.Timestamp('2025-07-01')].reset_index(drop=True)
        actual=build(result) if name=='detection' else evidence[ref.columns]
        helper(actual,ref)
