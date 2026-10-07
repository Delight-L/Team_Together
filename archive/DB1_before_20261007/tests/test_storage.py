from pathlib import Path
import json,sqlite3,sys
import subprocess
import pandas as pd
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import db1_store as store

@pytest.fixture
def db(tmp_path):
    source=ROOT/'outputs/db1.sqlite'
    target=tmp_path/'db.sqlite'
    with store.connect(source) as original,store.connect(target) as copied:original.backup(copied)
    return target

def test_raw_replay_stored_and_integrated(db):
    with store.connect(db) as con:
        assert con.execute('SELECT COUNT(*) FROM a2_feature').fetchone()[0]==1056
        assert con.execute('SELECT COUNT(*) FROM a2_detection').fetchone()[0]==132
        assert con.execute('SELECT COUNT(*) FROM a2_evidence').fetchone()[0]==1
        assert con.execute('SELECT COUNT(*) FROM v_db1_integrated').fetchone()[0]==132
        counts=con.execute('SELECT date,SUM(any_signal) FROM a2_detection GROUP BY date ORDER BY date').fetchall()
        assert [count for date,count in counts]==[0,0,0,0,0,1]
        signal=con.execute('SELECT adm_nm,signal_status,a1_cluster_type FROM v_db1_integrated WHERE any_signal=1').fetchone()
        assert signal[0]=='삼성1동' and signal[1]=='New' and signal[2]
        assert con.execute('PRAGMA foreign_key_check').fetchall()==[]

def test_history_preserves_float_values(db):
    with store.connect(db) as con:history=store.history(con)
    ref=pd.read_csv(ROOT/'Analysis2/data/reference/gangnam_analysis2_feature_table_2022_2025.csv')
    history=history.sort_values(['date','행정동코드']).reset_index(drop=True)
    ref['date']=pd.to_datetime(ref.date);ref=ref.sort_values(['date','행정동코드']).reset_index(drop=True)
    pd.testing.assert_frame_equal(history[ref.columns],ref,check_dtype=False,atol=1e-12,rtol=0)

def test_repeat_and_changed_input_blocked(db):
    with store.connect(db) as con:
        row=con.execute("SELECT fingerprint FROM db1_run WHERE analysis='analysis2' AND period='2025-12-01'").fetchone()
        assert store.already_processed(con,'analysis2','2025-12-01',row[0])
        with pytest.raises(ValueError):store.already_processed(con,'analysis2','2025-12-01','changed')

def test_transaction_rolls_back_on_invalid_evidence(db):
    with store.connect(db) as con:
        features=store.history(con)
        outputs=pd.DataFrame([json.loads(row[0]) for row in con.execute("SELECT result_json FROM a2_detection WHERE date='2025-12-01' ORDER BY adm_cd")])
    current=features.loc[features.date==pd.Timestamp('2025-12-01')].copy();current['date']=pd.Timestamp('2026-01-01')
    outputs['date']=pd.Timestamp('2026-01-01')
    evidence=pd.DataFrame([{'date':'2026-01-01','행정동코드':9999999}])
    with pytest.raises(sqlite3.IntegrityError):store.commit_a2(db,current,outputs,evidence,'2025H2')
    with store.connect(db) as con:
        assert con.execute('SELECT COUNT(*) FROM a2_feature').fetchone()[0]==1056
        assert con.execute("SELECT COUNT(*) FROM db1_run WHERE period='2026-01-01'").fetchone()[0]==0

def test_future_context_not_applied_to_earlier_month(db):
    with store.connect(db) as con:
        rows=con.execute("SELECT * FROM a1_context WHERE period='2025H2'").fetchall()
        for row in rows:
            con.execute('INSERT INTO a1_context VALUES(?,?,?,?,?,?,?,?)',(row[0],'2026H1',row[2],'2026-07-01',row[4],row[5],row[6],row[7]))
    with store.connect(db) as con:
        assert store.context_for(con,'2026-06-01')[0]=='2025H2'
        assert store.context_for(con,'2026-07-01')[0]=='2026H1'

def test_new_a1_period_persists_without_replacing_baseline(db,tmp_path):
    # Hypothetical update used only in an isolated test DB, not real 2026 data.
    frame=pd.read_csv(ROOT/'Analysis1/data/reference/reference_pca_input_2025H2.csv')
    frame['flow_per_point']*=1.02
    path=tmp_path/'fixture_input.csv';frame.to_csv(path,index=False)
    cmd=[sys.executable,str(ROOT/'Analysis1/run_change_detection.py'),'--input',str(path),'--baseline',str(ROOT/'Analysis1/models/2025H2/analysis1_baseline_2025H2.joblib'),'--period','2026H1','--db',str(db),'--out-dir',str(tmp_path/'outputs')]
    subprocess.run(cmd,check=True,capture_output=True,text=True)
    subprocess.run(cmd,check=True,capture_output=True,text=True)
    with store.connect(db) as con:
        assert con.execute('SELECT COUNT(*) FROM a1_region_baseline').fetchone()[0]==22
        assert con.execute('SELECT COUNT(*) FROM a1_input').fetchone()[0]==44
        assert con.execute('SELECT COUNT(*) FROM a1_region_feature').fetchone()[0]==572
        assert con.execute('SELECT COUNT(*) FROM a1_change_detection').fetchone()[0]==22
        assert con.execute('SELECT COUNT(*) FROM a1_change_feature').fetchone()[0]==286
        assert store.context_for(con,'2026-06-01')[0]=='2025H2'
        assert store.context_for(con,'2026-07-01')[0]=='2026H1'
        assert con.execute('SELECT COUNT(*) FROM v_db1_integrated').fetchone()[0]==132
