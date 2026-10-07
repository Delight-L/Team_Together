import hashlib,json,sqlite3,sys
from pathlib import Path
import pandas as pd
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import apply_packets,status,payload,read_card,read_market,make_card_features,make_market_features,prepare,DERIVED,AGES,DOMAINS,harmonize_age
BASE=Path(__file__).resolve().parents[2]/'test_db1.sqlite'
if not BASE.exists():BASE=Path(__file__).resolve().parents[2]/'outputs/db1.sqlite'
CONFIG=json.loads((Path(__file__).resolve().parents[1]/'config/analysis3_config.json').read_text(encoding='utf-8'))

@pytest.fixture
def database(tmp_path):
 p=tmp_path/'db.sqlite'
 with sqlite3.connect(BASE) as src,sqlite3.connect(p) as dst:src.backup(dst)
 return p

def originals(con):
 return {t:hashlib.sha256(payload(con.execute('SELECT * FROM '+t+' ORDER BY 1,2').fetchall()).encode()).hexdigest() for t in ('a1_context','a2_feature','a2_detection','a2_evidence','db1_run')}

def source_packet(con,source,old,new):
 table='a3a_industry' if source=='market' else 'a3b_industry'
 records=[json.loads(r[0]) for r in con.execute(f'SELECT payload_json FROM {table} WHERE period=?',(old,))]
 for r in records:
  if source=='market':r['period']=new;r['기준_년분기_코드']=int(new[:4]+new[-1])
 return {'records':records,'digest':'synthetic_'+new,'paths':['synthetic_fixture'],'available':None,'metadata':{'fixture':True}}

def test_actual_counts_and_join():
 s=status(BASE)
 assert s['a3_run']==22 and s['a3a_feature']==22*16*6*5
 assert s['a3a_comparison']==22*2*6*5
 assert s['a3b_feature']==6*6*5 and s['a3b_total']==36
 assert s['v_a123_monthly']==132 and s['v_a123_detail']==132*30
 assert s['behavior_signal_months']==1 and s['integrity']=='ok'
 with sqlite3.connect(BASE) as c:
  assert c.execute('SELECT DISTINCT adm_nm FROM v_a123_detail WHERE any_signal=1').fetchall()==[('삼성1동',)]
  assert c.execute('SELECT COUNT(*) FROM v_a123_available_context WHERE a3a_summary IS NOT NULL OR a3b_summary IS NOT NULL').fetchone()[0]==0

def test_source_totals_reconcile():
 with sqlite3.connect(BASE) as c:
  for source,p,j in c.execute('SELECT source,period,metadata_json FROM a3_run'):
   metadata=json.loads(j)
   table='a3a_quarter_summary' if source=='market' else 'a3b_month_summary'
   summary=[json.loads(r[0]) for r in c.execute(f'SELECT payload_json FROM {table} WHERE period=?',(p,))]
   assert sum(r['count'] for r in summary)==metadata['count_total']
   assert sum(r['amount'] for r in summary)==pytest.approx(metadata['amount_total'],rel=1e-12)

def test_history_cutoff_and_basket():
 with sqlite3.connect(BASE) as c:
  for (j,) in c.execute('SELECT payload_json FROM a3a_comparison'):
   r=json.loads(j)
   assert all(p<r['period'] and p[-1]==r['period'][-1] for p in r['baseline_periods'])
   assert r['comparison_available']==(r['baseline_n']>=3)
   assert r['matched_industry_count']<=r['current_observed_industry_count']

def test_new_month_and_quarter_append_without_past_change(database):
 with sqlite3.connect(database) as c:
  before=originals(c)
  prior=[r[0] for r in c.execute('SELECT payload_json FROM a3a_comparison ORDER BY period,adm_cd,age,domain')]
  packets={('market','2026Q1'):source_packet(c,'market','2025Q1','2026Q1'),('card','2026-01'):source_packet(c,'card','2025-12','2026-01')}
 result=apply_packets(database,packets,CONFIG)
 assert result['stored_periods']==2
 with sqlite3.connect(database) as c:
  assert originals(c)==before
  assert [r[0] for r in c.execute("SELECT payload_json FROM a3a_comparison WHERE period<'2026Q1' ORDER BY period,adm_cd,age,domain")]==prior
  new=[json.loads(r[0]) for r in c.execute("SELECT payload_json FROM a3b_feature WHERE period='2026-01'")]
  assert len(new)==30 and all(r['days']==31 for r in new)
  assert any(r['relative_change_pp'] is not None for r in new)
  comp=[json.loads(r[0]) for r in c.execute("SELECT payload_json FROM a3a_comparison WHERE period='2026Q1'")]
  assert len(comp)==660 and any(r['baseline_n']==4 for r in comp)
 assert apply_packets(database,packets,CONFIG)=={'stored_periods':0,'unchanged_periods':2}

def test_conflict_rolls_back_entire_batch(database):
 with sqlite3.connect(database) as c:
  count=c.execute('SELECT COUNT(*) FROM a3_run').fetchone()[0]
  packets={('card','2026-01'):source_packet(c,'card','2025-12','2026-01'),('market','2025Q3'):source_packet(c,'market','2025Q3','2025Q3')}
 with pytest.raises(ValueError,match='overwrite blocked'):apply_packets(database,packets,CONFIG)
 with sqlite3.connect(database) as c:
  assert c.execute('SELECT COUNT(*) FROM a3_run').fetchone()[0]==count
  assert c.execute("SELECT COUNT(*) FROM a3b_industry WHERE period='2026-01'").fetchone()[0]==0

def test_missing_domain_remains_null(database):
 with sqlite3.connect(database) as c:
  c.execute("DELETE FROM a3a_industry WHERE period='2025Q4' AND adm_cd='1123058' AND domain='E_의료건강'")
  for t in ('a3a_feature','a3a_comparison','a3a_quarter_summary'):c.execute('DELETE FROM '+t)
  make_market_features(c,CONFIG)
  r=json.loads(c.execute("SELECT payload_json FROM a3a_feature WHERE period='2025Q4' AND adm_cd='1123058' AND domain='E_의료건강' LIMIT 1").fetchone()[0])
  assert r['count'] is None and r['missing_domain'] and r['observed_industries']==0

def test_month_gap_not_previous_observation(database):
 with sqlite3.connect(database) as c:
  c.execute("DELETE FROM a3b_industry WHERE period='2025-11'")
  for t in ('a3b_feature','a3b_total','a3b_month_summary'):c.execute('DELETE FROM '+t)
  make_card_features(c)
  records=[json.loads(r[0]) for r in c.execute("SELECT payload_json FROM a3b_feature WHERE period='2025-12'")]
  assert all(r['relative_change_pp'] is None for r in records)

def test_publication_dates_no_future_leakage(database):
 with sqlite3.connect(database) as c:
  c.execute("UPDATE a3_run SET available_from='2026-02-01' WHERE source='market'")
  c.execute("UPDATE a3_run SET available_from='2025-12-20' WHERE source='card' AND period='2025-11'")
  r=c.execute("SELECT a3a_summary,a3b_period FROM v_a123_available_context WHERE date='2025-12-01' LIMIT 1").fetchone()
  assert r==(None,'2025-11')

def test_immutable_policy(database):
 with pytest.raises(ValueError,match='policy changed'):apply_packets(database,{},dict(CONFIG,minimum_same_quarter_history=4))

@pytest.mark.parametrize('age',['60 대','70대','80 대','90대'])
def test_senior_age(age):assert harmonize_age(age)=='60대이상'

@pytest.mark.parametrize('kind',['negative','nan','duplicate'])
def test_bad_card_rejected(tmp_path,kind):
 r={'TA_YMD':20260101,'MCT_SGG_CD':'서울 강남구','MCT_RY_CD':'한식','CLN_SGG_CD':'서울','SEX_CCD':'남성','AGE_CCD':'20 대','TS_AT':1000,'USE_CNT':1}
 if kind=='negative':r['USE_CNT']=-1
 if kind=='nan':r['USE_CNT']=float('nan')
 f=pd.DataFrame([r,r] if kind=='duplicate' else [r]);p=tmp_path/'bad.csv';f.to_csv(p,index=False,encoding='utf-8-sig')
 with pytest.raises(ValueError):read_card(p)

def test_senior_totals_from_raw(database):
 with sqlite3.connect(database) as c:
  raw=[json.loads(j) for (j,) in c.execute("SELECT payload_json FROM a3b_industry WHERE period='2025-12' AND age='60대이상'")]
  t=json.loads(c.execute("SELECT payload_json FROM a3b_total WHERE period='2025-12' AND age='60대이상'").fetchone()[0])
  assert t['count']==sum(r['use_count'] for r in raw)

def test_first_month_is_unavailable():
 with sqlite3.connect(BASE) as c:
  rs=[json.loads(j) for (j,) in c.execute("SELECT payload_json FROM a3b_feature WHERE period='2025-07'")]
  assert all(r['relative_change_pp'] is None and r['baseline_status']=='no_previous_month' for r in rs)

def small_sources(tmp_path):
 card=tmp_path/'card';market=tmp_path/'market';card.mkdir();market.mkdir()
 rs=[]
 for date in pd.date_range('2026-01-01','2026-01-31'):
  for age in AGES:
   rs.append({'TA_YMD':int(date.strftime('%Y%m%d')),'MCT_SGG_CD':'서울 강남구','MCT_RY_CD':'한식','CLN_SGG_CD':'서울','SEX_CCD':'남성','AGE_CCD':age,'TS_AT':1000,'USE_CNT':1})
 frame=pd.DataFrame(rs);frame.to_csv(card/'january.csv',index=False,encoding='utf-8-sig')
 return dict(CONFIG,card_root=str(card),market_root=str(market)),frame

def test_complete_future_calendar_and_incomplete_wait(tmp_path):
 config,frame=small_sources(tmp_path)
 packets,wait=prepare(config)
 assert ('card','2026-01') in packets
 frame=frame[frame.TA_YMD!=20260131];frame.to_csv(Path(config['card_root'])/'january.csv',index=False,encoding='utf-8-sig')
 packets,wait=prepare(config)
 assert not packets and any('2026-01: incomplete' in x for x in wait)

def test_duplicate_files_are_not_added_and_conflict_rejected(tmp_path):
 config,frame=small_sources(tmp_path)
 frame.to_csv(Path(config['card_root'])/'copy.csv',index=True,encoding='utf-8-sig')
 packets,_=prepare(config)
 assert len(packets)==1 and len(packets['card','2026-01']['paths'])==2
 frame.loc[0,'USE_CNT']=2;frame.to_csv(Path(config['card_root'])/'copy.csv',index=False,encoding='utf-8-sig')
 with pytest.raises(ValueError,match='Conflicting complete'):prepare(config)

def test_publication_before_observation_rejected(tmp_path):
 config,_=small_sources(tmp_path);config['available_from']={'card:2026-01':'2026-01-10'}
 with pytest.raises(ValueError,match='before observation end'):prepare(config)

def test_unrecognized_public_code_rejected(tmp_path):
 with sqlite3.connect(BASE) as c:r=json.loads(c.execute('SELECT payload_json FROM a3a_industry LIMIT 1').fetchone()[0])
 r['행정동_코드']=11680801
 pd.DataFrame([r]).to_csv(tmp_path/'newcode.csv',index=False,encoding='utf-8-sig')
 with pytest.raises(ValueError,match='crosswalk review'):read_market(tmp_path/'newcode.csv')

def test_shared_runner_scan_order(tmp_path,monkeypatch):
 import importlib.util
 runner_path=Path(__file__).resolve().parents[2]/'run_db1.py'
 spec=importlib.util.spec_from_file_location('runner_for_test',runner_path)
 runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
 config=tmp_path/'db1_config.json';config.write_text(json.dumps({'database':'outputs/db1.sqlite'}))
 calls=[]
 monkeypatch.setattr(runner.subprocess,'run',lambda cmd,**kw:calls.append(cmd))
 monkeypatch.setattr(sys,'argv',['run_db1.py','scan','--config',str(config),'--db',str(BASE)])
 runner.main()
 assert len(calls)==3
 assert 'Analysis1' in calls[0][1] and 'Analysis2' in calls[1][1] and 'Analysis3' in calls[2][1]
 assert calls[2][2]=='scan' and calls[2][calls[2].index('--db')+1]==str(BASE.resolve())

def test_new_behavior_month_without_consumption_is_retained(database):
 apply_packets(database,{},CONFIG)
 with sqlite3.connect(database) as c:
  r=list(c.execute("SELECT * FROM a2_feature WHERE adm_cd='1123058' AND date='2025-12-01'").fetchone());r[1]='2026-01-01'
  c.execute('INSERT INTO a2_feature VALUES(?,?,?,?,?)',r)
  d=list(c.execute("SELECT * FROM a2_detection WHERE adm_cd='1123058' AND date='2025-12-01'").fetchone());d[1]='2026-01-01'
  c.execute('INSERT INTO a2_detection VALUES(?,?,?,?,?,?,?,?,?,?)',d)
  detail=c.execute("SELECT COUNT(*),SUM(a3a_feature IS NULL),SUM(a3b_month_context IS NULL) FROM v_a123_detail WHERE date='2026-01-01'").fetchone()
  assert detail==(30,30,30)

def test_historical_backfill_requires_explicit_migration(database):
 with sqlite3.connect(database) as c:
  packet=source_packet(c,'market','2023Q3','2023Q3')
  c.execute("DELETE FROM a3_run WHERE source='market' AND period='2023Q3'")
 with pytest.raises(ValueError,match='historical backfill'):apply_packets(database,{('market','2023Q3'):packet},CONFIG)
