from pathlib import Path
from contextlib import closing
import importlib.util,sys,json,sqlite3,hashlib,math,csv
import pandas as pd
import numpy as np
R=Path(__file__).resolve().parent
DB1=next((p for p in R.parents if (p/'run_db1.py').exists()),Path(r'C:\Users\user\Desktop\Team_Together\DB1'))
O=DB1/'outputs/validation/retrospective_20261007' if (R/'DEPLOYED.txt').exists() else R/'outputs';O.mkdir(parents=True,exist_ok=True)
DB=DB1/'outputs/db1.sqlite'
sys.path.insert(0,str(DB1/'Analysis2'))
import age_detection as ad
import activity_level as al
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def records(f):return json.loads(f.to_json(orient='records',date_format='iso',force_ascii=False,double_precision=15))
def keys(f):return {(str(r['행정동코드']),r['date'].strftime('%Y-%m-%d'),r['age_band']) for _,r in f[f.communication_signal.fillna(False)].iterrows()}
def summarize(f,label,settings):
 summary={'scenario':label,'settings':settings,'rows':len(f),'communication':int(f.communication_signal.fillna(False).sum()),'mobility':int(f.mobility_signal.fillna(False).sum()),'combined':int(f.combined_signal.fillna(False).sum()),'communication_assessable':int(f.communication_signal.notna().sum()),'mobility_assessable':int(f.mobility_signal.notna().sum()),'by_age':[],'months':[]}
 for age,g in f.groupby('age_band'):
  summary['by_age'].append({'age':age,'rows':len(g),'communication':int(g.communication_signal.fillna(False).sum()),'mobility':int(g.mobility_signal.fillna(False).sum()),'combined':int(g.combined_signal.fillna(False).sum()),'communication_assessable':int(g.communication_signal.notna().sum())})
 for date,g in f.groupby('date'):summary['months'].append({'date':date.strftime('%Y-%m-%d'),'communication':int(g.communication_signal.fillna(False).sum()),'mobility':int(g.mobility_signal.fillna(False).sum()),'combined':int(g.combined_signal.fillna(False).sum())})
 return summary
def evaluate(frame,start,end,first,last,label,q=.025,cap=-2,precomputed=None):
 settings={**ad.DEFAULT,'baseline_start':start,'baseline_end':end,'detection_start':first,'lower_quantile':q,'threshold_cap':cap}
 prefix=frame[frame.date.between(pd.Timestamp(start),pd.Timestamp(last))].copy()
 scores,common=ad.compute_scores(prefix,settings) if precomputed is None else (precomputed[0].copy(),precomputed[1].copy())
 calibration=ad.calibrate(scores,common,settings)
 result,commons=ad.detect(scores,common,calibration,settings)
 result=result[result.date.between(pd.Timestamp(first),pd.Timestamp(last))].copy()
 s=summarize(result,label,settings);s['common_calibration_unavailable']=int(calibration[(calibration.scope=='common')&calibration.threshold.isna()].shape[0]);s['signal_keys']=sorted(keys(result))
 columns=['date','행정동코드','행정동','age_band','assessment_status','communication_signal','mobility_signal','combined_signal','communication_absolute_signal','communication_local_signal','review_reasons']
 result[columns].to_csv(O/(label+'_detections.csv'),index=False,encoding='utf-8-sig')
 print(label,s['rows'],s['communication'],s['mobility'],s['combined'],flush=True)
 return s,result,(scores,common)
before=sha(DB)
frame=ad.load_features(DB)
current,current_results,full=evaluate(frame,'2022-01-01','2025-06-01','2025-07-01','2025-12-01','current_reference')
with closing(sqlite3.connect('file:'+DB.as_posix()+'?mode=ro',uri=True)) as c:
 stored=pd.read_sql_query('SELECT adm_cd,date,age_band,communication_signal,mobility_signal,combined_signal FROM a2_age_detection',c)
expected={(r.adm_cd,r.date,r.age_band):tuple(None if pd.isna(getattr(r,m)) else int(getattr(r,m)) for m in ['communication_signal','mobility_signal','combined_signal']) for r in stored.itertuples()}
for r in current_results.itertuples():
 actual=tuple(None if pd.isna(getattr(r,m)) else int(getattr(r,m)) for m in ['communication_signal','mobility_signal','combined_signal'])
 assert expected[(str(r.행정동코드),r.date.strftime('%Y-%m-%d'),r.age_band)]==actual
folds=[]
for start,end,first,last,label in [('2022-01-01','2023-12-01','2024-01-01','2024-12-01','replay_2024'),('2022-01-01','2024-06-01','2024-07-01','2024-12-01','replay_2024H2'),('2022-01-01','2024-12-01','2025-01-01','2025-06-01','replay_2025H1')]:
 s,_,_=evaluate(frame,start,end,first,last,label);folds.append(s)
# Independent prefix recomputation confirms that appended future months do not change past scores.
prefix_settings={**ad.DEFAULT,'baseline_end':'2023-12-01','detection_start':'2024-01-01'}
prefix_scores,prefix_common=ad.compute_scores(frame[frame.date.le(pd.Timestamp('2024-12-01'))],prefix_settings)
score_columns=['date','_area','age_band']+[m+'_'+scope+'_rz' for m in ad.CORE for scope in ['absolute','local']]
a=full[0][full[0].date.le(pd.Timestamp('2024-12-01'))][score_columns].reset_index(drop=True);b=prefix_scores[score_columns].reset_index(drop=True)
pd.testing.assert_frame_equal(a,b,check_exact=True)
variants=[];reference_keys=keys(current_results)
for q in [.01,.025,.05]:
 for cap in [-2,-2.5,-3]:
  label=f'sensitivity_q{q:g}_cap{abs(cap):g}'
  s,_,_=evaluate(frame,'2022-01-01','2025-06-01','2025-07-01','2025-12-01',label,q,cap,full)
  variant_keys={tuple(k) for k in s['signal_keys']};s['retained_reference_signals']=len(reference_keys&variant_keys);s['new_signals']=len(variant_keys-reference_keys);s['jaccard_with_reference']=len(reference_keys&variant_keys)/len(reference_keys|variant_keys) if reference_keys|variant_keys else None
  variants.append(s)
window_variants=[]
for start,end in [('2023-01-01','2025-06-01'),('2022-01-01','2024-12-01')]:
 # Scores use only this start and contemporaneously preceding observations; thresholds stop at end.
 s,res,_=evaluate(frame,start,end,'2025-07-01','2025-12-01','window_'+start[:4]+'_'+end[:7]);ks=keys(res);s['retained_reference_signals']=len(ks&reference_keys);window_variants.append(s)
case_sensitivity=[]
for code,date,age in sorted(reference_keys,key=lambda k:(k[1],k[0],k[2])):
 name=current_results[(current_results['행정동코드'].astype(str)==code)&current_results.date.eq(pd.Timestamp(date))&current_results.age_band.eq(age)]['행정동'].iloc[0]
 case_sensitivity.append({'adm_cd':code,'date':date,'age_band':age,'dong':name,'retained_in_threshold_variants':sum((code,date,age) in {tuple(k) for k in s['signal_keys']} for s in variants),'threshold_variants':len(variants),'retained_in_window_variants':sum((code,date,age) in {tuple(k) for k in s['signal_keys']} for s in window_variants),'window_variants':len(window_variants)})
# Alternative same-calendar-month reference methods are diagnostics, not operational changes.
features=json.loads(frame.to_json(orient='records',date_format='iso',force_ascii=False))
events=[{'adm_cd':code,'date':date,'age_band':age,'model_version':'diagnostic','communication_signal':1,'mobility_signal':0} for code,date,age in sorted(reference_keys)]
level_comparisons=[]
for label,fn,minyears,start in [('median_all_baseline',None,3,'2022-01-01'),('mean_all_baseline',lambda v:sum(v)/len(v),3,'2022-01-01'),('median_recent_two_years',None,2,'2023-01-01')]:
 old_median=al.median;old_min=al.SETTINGS['min_same_month_years']
 try:
  # Keep peer common-change aggregation as median; switch only calendar-month reference by preparing input-normalization comparison below.
  if fn is None:
   al.SETTINGS['min_same_month_years']=minyears
   _,tracks,_=al.compute([r for r in features if r['date'][:10]>=start],events)
  else:
   # Use independent calculator so the district common statistic remains a median.
   _,base_tracks,_=al.compute(features,events);tracks=[]
   from statistics import median
   table={(str(r['행정동코드']),r['age_band'],r['date'][:10]):r for r in features}
   refs={}
   for code in set(k[0] for k in table):
    for age in set(k[1] for k in table):
     for month in range(1,13):
      for m in al.METRICS:
       vv=[r[m] for (co,ag,da),r in table.items() if co==code and ag==age and da<=al.BASELINE_END and int(da[5:7])==month and al.valid(r,m)]
       refs[(code,age,month,m)]=fn(vv) if len(vv)>=3 else None
   for r in base_tracks:
    z=dict(r);z['seasonal_change_pct']={};z['local_change_pct']={}
    for m in al.METRICS:
     def ratio(code):
      t=table[(code,r['age_band'],r['date'])];p=table[(code,r['age_band'],r['reference_date'])];bt=refs[(code,r['age_band'],int(r['date'][5:7]),m)];bp=refs[(code,r['age_band'],int(r['reference_date'][5:7]),m)]
      return (t[m]/bt)/(p[m]/bp) if bt and bp and al.valid(t,m) and al.valid(p,m) else None
     value=ratio(r['adm_cd']);peer=[ratio(co) for co in set(k[0] for k in table)];peer=[x for x in peer if x is not None];common=median(peer) if len(peer)>=11 else None
     z['seasonal_change_pct'][m]=(value-1)*100 if value is not None else None;z['local_change_pct'][m]=(value/common-1)*100 if value is not None and common else None
    z['seasonal_state']=al.state(list(z['seasonal_change_pct'].values()));z['local_state']=al.state(list(z['local_change_pct'].values()));tracks.append(z)
  latest=[r for r in tracks if r['date']=='2025-12-01'];level_comparisons.append({'method':label,'baseline_start':start,'minimum_same_month_years':minyears,'latest':latest})
 finally:al.median=old_median;al.SETTINGS['min_same_month_years']=old_min
print('Level method comparison complete',flush=True)
assert before==sha(DB),'Read-only validation changed DB'
payload={'source_db':str(DB),'source_db_sha256':before,'current_reference':current,'historical_replays':folds,'threshold_variants':variants,'window_variants':window_variants,'case_sensitivity':case_sensitivity,'level_method_comparisons':level_comparisons,'validation':{'operational_flags_exactly_reproduced':True,'prefix_scores_future_invariant':True,'database_unchanged':True,'no_ground_truth_labels':True,'retrospective_publication_dates_not_verified':True}}
(O/'validation_results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
pd.DataFrame(case_sensitivity).to_csv(O/'signal_sensitivity.csv',index=False,encoding='utf-8-sig')
pd.DataFrame([{k:v for k,v in s.items() if not isinstance(v,(dict,list))} for s in variants+window_variants]).to_csv(O/'scenario_summary.csv',index=False,encoding='utf-8-sig')
print('Validation complete; operational DB unchanged',flush=True)
