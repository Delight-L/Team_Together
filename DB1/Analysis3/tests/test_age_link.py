import importlib.util,json,sqlite3
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('age_link',Path(__file__).parents[1]/'age_link.py')
link=importlib.util.module_from_spec(spec);spec.loader.exec_module(link)

@pytest.fixture
def db(tmp_path):
    path=tmp_path/'test.sqlite'
    with sqlite3.connect(path) as c:
        c.executescript('''CREATE TABLE a2_age_detection(adm_cd,date,age_scheme,age_band,model_version,assessment_status,communication_signal,mobility_signal,combined_signal,isolation_related_candidate,result_json);
        CREATE TABLE a3a_comparison(period,adm_cd,age,domain,payload_json);
        CREATE TABLE a3b_feature(period,district,age,domain,payload_json);
        CREATE TABLE a3_dimension(age,domain);
        CREATE TABLE a3_run(source,period,available_from);''')
        for band,comm in [('30s',1),('40s',0)]:
            c.execute('INSERT INTO a2_age_detection VALUES(?,?,?,?,?,?,?,?,?,?,?)',('1123051','2025-10-01','service',band,'m1','assessed',comm,0,0,0,json.dumps({'any_signal':bool(comm),'행정동':'신사동'})))
        c.execute('INSERT INTO a3_dimension VALUES(?,?)',('30대','A_외식카페'))
        c.execute('INSERT INTO a3a_comparison VALUES(?,?,?,?,?)',('2025Q4','1123051','30대','A_외식카페',json.dumps({'comparison_available':True,'change_pct':-17,'below_prior_min':True})))
        c.execute('INSERT INTO a3b_feature VALUES(?,?,?,?,?)',('2025-10','11680','30대','A_외식카페',json.dumps({'missing_domain':False,'matched_mom_daily_change_pct':-9})))
        c.executemany('INSERT INTO a3_run VALUES(?,?,?)',[('market','2025Q4','2026-01-15'),('card','2025-10',None)])
    return path

def rows(db,table):
    with sqlite3.connect(db) as c:return [json.loads(r[0]) for r in c.execute('SELECT payload_json FROM '+table+' ORDER BY age_band')]

def test_age_scope_and_flags(db,tmp_path):
    link.run(db,tmp_path/'out');a,b=rows(db,'a23_age_detail')
    assert a['market_change_pct']==-17 and b['market_change_pct'] is None
    assert a['card_scope']=='gangnam_merchant_district_customer_age_context'
    assert a['combined_signal']==0 and a['isolation_related_candidate']==0
    assert a['market_period']=='2025Q4' and a['market_alignment']=='retrospective_same_quarter'

def test_availability_and_null(db,tmp_path):
    link.run(db,tmp_path/'out')
    assert all(r['market_period'] is None and r['card_period'] is None for r in rows(db,'a23_age_available_context'))
    assert rows(db,'a23_age_detail')[1]['market_down'] is None

def test_idempotence_and_sources_unchanged(db,tmp_path):
    with sqlite3.connect(db) as c:before=c.execute('SELECT * FROM a2_age_detection').fetchall()
    first=link.run(db,tmp_path/'out');second=link.run(db,tmp_path/'out')
    assert first==second
    with sqlite3.connect(db) as c:assert before==c.execute('SELECT * FROM a2_age_detection').fetchall()
    assert len(rows(db,'a23_age_quarter'))==2
    assert rows(db,'a23_age_quarter')[0]['fully_assessed_months']==1

def test_future_append_and_later_consumption(db,tmp_path):
    link.run(db,tmp_path/'out')
    with sqlite3.connect(db) as c:
        c.execute("INSERT INTO a2_age_detection SELECT adm_cd,'2026-01-01',age_scheme,age_band,model_version,assessment_status,communication_signal,mobility_signal,combined_signal,isolation_related_candidate,result_json FROM a2_age_detection WHERE age_band='30s'")
    link.run(db,tmp_path/'out')
    future=[r for r in rows(db,'a23_age_detail') if r['date'].startswith('2026')][0]
    assert future['market_down'] is None and future['card_down'] is None
    with sqlite3.connect(db) as c:c.execute('INSERT INTO a3a_comparison VALUES(?,?,?,?,?)',('2026Q1','1123051','30대','A_외식카페',json.dumps({'comparison_available':True,'change_pct':-5})))
    link.run(db,tmp_path/'out')
    assert [r for r in rows(db,'a23_age_detail') if r['date'].startswith('2026')][0]['market_change_pct']==-5

def test_partial_signal_unknown_and_first_card_month(db,tmp_path):
    with sqlite3.connect(db) as c:
        c.execute('UPDATE a2_age_detection SET communication_signal=NULL,mobility_signal=0,result_json=? WHERE age_band=?',(json.dumps({'any_signal':None}),'40s'))
        c.execute('UPDATE a3b_feature SET payload_json=?',(json.dumps({'missing_domain':False,'matched_mom_daily_change_pct':None}),))
    link.run(db,tmp_path/'out')
    a,b=rows(db,'a23_age_detail');assert a['card_down'] is None and b['behavior_signal'] is None

def test_model_versions_not_collapsed(db,tmp_path):
    with sqlite3.connect(db) as c:c.execute("INSERT INTO a2_age_detection SELECT adm_cd,date,age_scheme,age_band,'m2',assessment_status,communication_signal,mobility_signal,combined_signal,isolation_related_candidate,result_json FROM a2_age_detection")
    result=link.run(db,tmp_path/'out');assert result['monthly_rows']==4

def test_known_publication_and_period_completion(db,tmp_path):
    with sqlite3.connect(db) as c:
        c.execute("UPDATE a3_run SET available_from='2025-10-20'")
        c.execute('INSERT INTO a3_run VALUES(?,?,?)',('market','2025Q3','2025-10-10'))
        c.execute('INSERT INTO a3a_comparison VALUES(?,?,?,?,?)',('2025Q3','1123051','30대','A_외식카페',json.dumps({'comparison_available':True,'change_pct':-4})))
    link.run(db,tmp_path/'out');a=rows(db,'a23_age_available_context')[0]
    assert a['market_period']=='2025Q3' and a['market_change_pct']==-4
    assert a['card_period']=='2025-10'
