"""Provider definitions, rolling observation windows and same-period SNS context."""
from pathlib import Path
from contextlib import closing
from datetime import date,timedelta
from statistics import median
from collections import defaultdict
import argparse,calendar,csv,json,math,sqlite3
VERSION='source_semantics_v1'
URL='https://data.seoul.go.kr/dataVisual/seoul/seoulLiving.do'
def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,allow_nan=False)
def shift(month,offset):
 y,m=map(int,month[:7].split('-'));n=y*12+m-1+offset;return f'{n//12:04d}-{n%12+1:02d}-01'
def window(month):
 month=month[:10];start=shift(month,-3);end=(date.fromisoformat(month)-timedelta(days=1)).isoformat()
 months=[shift(month,i)[:7] for i in [-3,-2,-1]]
 days=[date.fromisoformat(start)+timedelta(days=i) for i in range((date.fromisoformat(end)-date.fromisoformat(start)).days+1)]
 quarters=sorted({f'{d[:4]}Q{(int(d[5:7])-1)//3+1}' for d in months})
 return {'label_month':month[:7],'observation_start':start,'observation_end':end,'observation_months':months,'exact_quarter':quarters[0] if len(quarters)==1 else None,'overlap_quarters':quarters,'calendar_mon_fri_days':sum(d.weekday()<5 for d in days),'calendar_sat_sun_days':sum(d.weekday()>=5 for d in days),'calendar_days':len(days),'calendar_definition':'literal_Mon_Fri_and_Sat_Sun_not_provider_weekday_holiday_definition','provider_holiday_includes_public_holidays':None,'available_from':None,'publication_note':'manual indicates publication next month; actual file-specific release date not verified; do not infer availability','window_basis':'provider_manual_previous_three_months; source-file date treated as aggregation label','definition_source':URL,'semantics_version':VERSION}
def finite(v):return isinstance(v,(int,float)) and math.isfinite(v)
def sns_summary(group):
 total=sum(r['population'] for r in group)
 usable=[r for r in group if finite(r['value']) and finite(r['population']) and r['population']>=0]
 w=sum(r['population'] for r in usable);nonzero=[r for r in usable if r['value']!=0];nw=sum(r['population'] for r in nonzero)
 coverage=w/total if total>0 else None
 ready=w>=200 and coverage is not None and .8<=coverage<=1.00000001
 return {'sns_index_mean':sum(r['value']*r['population'] for r in usable)/w if ready else None,'sns_index_without_zero_sensitivity':sum(r['value']*r['population'] for r in nonzero)/nw if nw>=200 and total>0 and nw/total>=.8 else None,'finite_population_coverage':coverage,'valid_estimated_population':w,'source_cells':len(group),'zero_cells':sum(r['value']==0 for r in usable),'negative_cells':sum(r['value']<0 for r in usable),'zero_population_share':sum(r['population'] for r in usable if r['value']==0)/total if total else None,'quality_status':'unavailable' if not ready else ('zero_semantics_review' if any(r['value']==0 for r in usable) else 'same_period_relative_only'),'unit':'provider_standardized_z_index','aggregation':'estimated_population_weighted_mean_of_published_sex_age_group_scores','negative_values_valid':True,'zero_note':'standardized zero can represent reference mean; legacy column guide also notes raw reaggregation; do not infer no use','time_series_comparable':False,'percent_change_allowed':False,'individual_contacts_measured':False}
def card_window_comparison(industry,months,prior,age,domain):
 periods=months+prior;common=None
 for period in periods:
  eligible={name for (p,a,d,name),rows in industry.items() if p==period and a==age and d==domain and len(rows)==1 and finite(rows[0].get('use_count')) and rows[0]['use_count']>=0 and rows[0].get('observed_days',0)>=calendar.monthrange(int(period[:4]),int(period[5:7]))[1]}
  common=eligible if common is None else common&eligible
 if not common:return {'change_pct':None,'reason':'insufficient_prior_or_common_full_coverage_industries','matched_industries':[]}
 def daily(selected):
  days=sum(calendar.monthrange(int(p[:4]),int(p[5:7]))[1] for p in selected)
  return sum(industry[(p,age,domain,i)][0]['use_count'] for p in selected for i in common)/days
 current,baseline=daily(months),daily(prior)
 return {'change_pct':(current/baseline-1)*100 if baseline>0 else None,'reason':'ready' if baseline>0 else 'zero_prior_window_count','matched_industries':sorted(common),'current_daily_count':current,'prior_daily_count':baseline,'method':'common_industries_all_six_months_full_calendar_day_coverage','seasonality_adjusted':False,'scope':'merchant_district_not_same_residents'}
SCHEMA='''
CREATE TABLE IF NOT EXISTS a2_observation_window(date TEXT PRIMARY KEY,payload_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ctx_sns_index(adm_cd TEXT NOT NULL,date TEXT NOT NULL,age_band TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,date,age_band));
CREATE TABLE IF NOT EXISTS a23_observation_context(adm_cd TEXT NOT NULL,date TEXT NOT NULL,age_band TEXT NOT NULL,model_version TEXT NOT NULL,payload_json TEXT NOT NULL,PRIMARY KEY(adm_cd,date,age_band,model_version));
CREATE VIEW IF NOT EXISTS v_a123_age_source_context AS
 SELECT d.adm_cd,d.date AS source_label_date,d.age_band,d.model_version,d.assessment_status,d.communication_signal,d.mobility_signal,d.combined_signal,d.result_json,
 json_extract(w.payload_json,'$.observation_start') AS observation_start,json_extract(w.payload_json,'$.observation_end') AS observation_end,w.payload_json AS observation_window_json,s.payload_json AS same_period_sns_json,o.payload_json AS observation_consumption_json
 FROM a2_age_detection d LEFT JOIN a2_observation_window w ON w.date=d.date LEFT JOIN ctx_sns_index s ON s.adm_cd=d.adm_cd AND s.date=d.date AND s.age_band=d.age_band LEFT JOIN a23_observation_context o ON o.adm_cd=d.adm_cd AND o.date=d.date AND o.age_band=d.age_band AND o.model_version=d.model_version;
'''
def upsert_guard(c,table,fields,values,payload):
 where=' AND '.join(f'{k}=?' for k in fields);text=canonical(payload)
 old=c.execute(f'SELECT payload_json FROM {table} WHERE {where}',values).fetchone()
 if old and old[0]!=text:raise ValueError('Changed historical source context: explicit revision required '+str(values))
 if old:return 0
 c.execute(f"INSERT INTO {table} VALUES({','.join('?' for _ in range(len(values)+1))})",list(values)+[text]);return 1
def run(db,output=None):
 with closing(sqlite3.connect(db)) as c:
  rows=c.execute("SELECT date,adm_cd,age_code,raw_json FROM a2_age_raw WHERE kind='telecom' ORDER BY date,adm_cd,sex,age_code").fetchall()
  features={(r[0],r[1],r[2]):json.loads(r[3]) for r in c.execute("SELECT adm_cd,date,age_band,feature_json FROM a2_age_feature WHERE age_scheme='service'")}
  groups=defaultdict(list)
  for label,code,age,raw in rows:
   r=json.loads(raw);band='60plus' if age>=60 else f'{age//10*10}s'
   groups[(label,code,band)].append({'value':r.get('SNS 사용횟수'),'population':r['총인구수']})
  windows={label:window(label) for label,_,_ in groups}
  sns={}
  for (label,code,age),g in sorted(groups.items()):
   s=sns_summary(g);s.update(adm_cd=code,date=label,age_band=age,adm_nm=features[(code,label,age)]['행정동']);sns[(code,label,age)]=s
  for label in windows:
   for age in ['20s','30s','40s','50s','60plus']:
    peers=[s for (code,d,a),s in sns.items() if d==label and a==age and s['sns_index_mean'] is not None]
    for s in peers:
     values=[x['sns_index_mean'] for x in peers];s['same_period_gangnam_age_median']=median(values) if len(values)>=11 else None
     s['same_period_gangnam_age_percentile']=(sum(v<s['sns_index_mean'] for v in values)+.5*sum(v==s['sns_index_mean'] for v in values))/len(values) if len(values)>=11 else None
     s['same_period_peer_n']=len(values)
  market={(r[0],r[1],r[2],r[3]):json.loads(r[4]) for r in c.execute('SELECT period,adm_cd,age,domain,payload_json FROM a3a_comparison')}
  card={(r[0],r[1],r[2]):json.loads(r[3]) for r in c.execute('SELECT period,age,domain,payload_json FROM a3b_feature')}
  industry=defaultdict(list)
  for period,age,domain,name,payload in c.execute('SELECT period,age,domain,industry,payload_json FROM a3b_industry'):industry[(period,age,domain,name)].append(json.loads(payload))
  contexts=[];comparison_cache={}
  for code,label,age,model in c.execute('SELECT adm_cd,date,age_band,model_version FROM a2_age_detection ORDER BY date,adm_cd,age_band'):
   w=windows[label];consumption_age={'20s':'20대','30s':'30대','40s':'40대','50s':'50대','60plus':'60대이상'}[age]
   domains=[]
   for domain in ['A_외식카페','B_여가운동','C_대면생활서비스','D_생활필수','E_의료건강']:
    q=w['exact_quarter'];local=market.get((q,code,consumption_age,domain)) if q else None
    cp=[{'period':month,**card[(month,consumption_age,domain)]} for month in w['observation_months'] if (month,consumption_age,domain) in card]
    prior=[shift(w['observation_start'],i)[:7] for i in [-3,-2,-1]]
    prior_available=all((month,consumption_age,domain) in card for month in prior)
    cache_key=(label,consumption_age,domain)
    if cache_key not in comparison_cache:comparison_cache[cache_key]=card_window_comparison(industry,w['observation_months'],prior,consumption_age,domain)
    comparison=comparison_cache[cache_key]
    domains.append({'domain':domain,'market_period':q,'market_alignment':'exact_full_quarter' if q else 'no_exact_quarter_match','market_change_pct':local.get('change_pct') if local and local.get('comparison_available') else None,'market_baseline_n':local.get('baseline_n') if local else None,'market_comparison':local,'card_observation_months':w['observation_months'],'card_available_months':[p['period'] for p in cp],'card_monthly_context':cp,'card_full_window_available':len(cp)==3,'card_previous_window_months':prior,'card_previous_window_available':prior_available,'card_window_change_pct':comparison['change_pct'],'card_window_comparison':comparison,'card_comparison_reason':comparison['reason'] if prior_available else 'insufficient_prior_window_history','interpretation':'merchant_context_not_same_residents; observational_alignment_not_causality'})
   contexts.append({'adm_cd':code,'date':label,'age_band':age,'model_version':model,'observation_window':w,'domains':domains,'retrospective_only':True,'legacy_same_label_month_consumption_is_contemporaneous':False})
  import consumption_enrichment as enrichment
  c.executescript(SCHEMA+enrichment.SCHEMA);counts={'a2_observation_window':0,'ctx_sns_index':0,'a23_observation_context':0}
  enriched=0
  with c:
   anchors,added=enrichment.anchor_changes(c)
   for label,w in sorted(windows.items()):counts['a2_observation_window']+=upsert_guard(c,'a2_observation_window',['date'],[label],w)
   for (code,label,age),s in sorted(sns.items()):counts['ctx_sns_index']+=upsert_guard(c,'ctx_sns_index',['adm_cd','date','age_band'],[code,label,age],s)
   for p in contexts:
    inserted,updated=enrichment.upsert_context(c,p,added)
    counts['a23_observation_context']+=inserted;enriched+=updated
   enrichment.finish_anchors(c,anchors)
  summary={'enriched_consumption_rows':enriched,'inserted':counts,'source_label_months':len(windows),'sns_cells':len(sns),'aligned_context_rows':len(contexts),'existing_signal_rules_modified':False,'holiday_definition_confirmed':False,'sns_time_comparison_allowed':False}
 if output:export(db,output)
 return summary
def export(db,output):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 with closing(sqlite3.connect(db)) as c:
  for table in ['a2_observation_window','ctx_sns_index','a23_observation_context']:
   cursor=c.execute('SELECT * FROM '+table+' ORDER BY date')
   with (output/(table+'.csv')).open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.writer(f);w.writerow([x[0] for x in cursor.description]);w.writerows(cursor)
  signals=[dict(zip(['adm_cd','source_label_date','age_band','model_version','assessment_status','communication_signal','mobility_signal','combined_signal','result_json','observation_start','observation_end','observation_window_json','same_period_sns_json','observation_consumption_json'],r)) for r in c.execute('SELECT * FROM v_a123_age_source_context WHERE communication_signal=1 OR mobility_signal=1 ORDER BY source_label_date,adm_cd,age_band')]
  for s in signals:
   for k in list(s):
    if k.endswith('_json'):s[k]=json.loads(s[k]) if s[k] else None
  (output/'signal_source_context.json').write_text(json.dumps(signals,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--output');args=p.parse_args();print(json.dumps(run(args.db,args.output),ensure_ascii=False,indent=2))

