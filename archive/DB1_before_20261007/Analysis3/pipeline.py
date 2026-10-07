"""Local, append-only ingestion and consumer-context preprocessing for DB1.

Raw files are complete period snapshots. Missing industry rows are not zeros.
Quarter observations are never fabricated as monthly consumption observations.
"""
from pathlib import Path
import calendar, hashlib, json, sqlite3
import numpy as np
import pandas as pd
from mappings import AGES,DOMAINS,CROSSWALK,MARKET_DOMAINS,CARD_DOMAINS,VERSION,harmonize_age

ROOT=Path(__file__).resolve().parent
AGE_COLS={a:f'연령대_{a[:-1] if a.endswith("대") else "60_이상"}_매출_건수' for a in AGES}
AGE_AMOUNT={a:c.replace('건수','금액') for a,c in AGE_COLS.items()}

def payload(value):
 return json.dumps(value,ensure_ascii=False,allow_nan=False,sort_keys=True)

def clean_records(frame):
 return json.loads(frame.to_json(orient='records',force_ascii=False,double_precision=15))

def read_csv(path):
 for enc in ('utf-8-sig','cp949'):
  try:return pd.read_csv(path,encoding=enc)
  except UnicodeDecodeError:pass
 raise ValueError(f'Cannot decode {path}')

def check_numeric(df,columns):
 for c in columns:
  df[c]=pd.to_numeric(df[c],errors='raise')
  if not np.isfinite(df[c]).all() or (df[c]<0).any():raise ValueError(f'Nonfinite/negative {c}')
  if c.endswith('건수') or c=='USE_CNT':
   if not (df[c]%1==0).all():raise ValueError(f'Noninteger count {c}')

def required(df,cols):
 absent=set(cols)-set(df.columns)
 if absent:raise ValueError(f'Missing columns {sorted(absent)}')

def fingerprint(df,keys):
 ordered=df.sort_values(keys).reset_index(drop=True)
 return hashlib.sha256(payload({'columns':sorted(df.columns),'records':clean_records(ordered[sorted(df.columns)])}).encode()).hexdigest()

def quarter_end(period):return pd.Period(period,freq='Q').end_time.normalize()
def quarter_days(period):
 q=pd.Period(period,freq='Q')
 return (q.end_time.normalize()-q.start_time.normalize()).days+1

def read_market(path):
 df=read_csv(path)
 cols=['기준_년분기_코드','행정동_코드','행정동_코드_명','서비스_업종_코드','서비스_업종_코드_명','당월_매출_건수','당월_매출_금액',*AGE_COLS.values(),*AGE_AMOUNT.values()]
 required(df,cols)
 codes=pd.to_numeric(df['행정동_코드'],errors='raise').astype('int64').astype(str)
 unknown=sorted(set(codes[codes.str.startswith('11680')])-set(CROSSWALK))
 if unknown:raise ValueError(f'New Gangnam administrative codes need crosswalk review: {unknown}')
 df=df[codes.isin(CROSSWALK)].copy()
 df['public_adm_cd']=codes[codes.isin(CROSSWALK)]
 if df.empty:raise ValueError(f'No Gangnam data: {path}')
 if df[cols].isna().any().any():raise ValueError('Market required fields missing')
 check_numeric(df,[c for c in cols if c.endswith(('건수','금액'))])
 code=df['기준_년분기_코드'].astype(str)
 if not code.str.fullmatch(r'\d{4}[1-4]').all():raise ValueError('Invalid market quarter')
 df['period']=code.str[:4]+'Q'+code.str[-1]
 df['adm_cd']=df.public_adm_cd.map(lambda c:CROSSWALK[c][0])
 df['adm_nm']=df.public_adm_cd.map(lambda c:CROSSWALK[c][1])
 for r in df[['public_adm_cd','행정동_코드_명']].drop_duplicates().to_dict('records'):
  name=CROSSWALK[r['public_adm_cd']][1]
  if r['행정동_코드_명']!=name and not (r['public_adm_cd']=='11680740' and r['행정동_코드_명']=='일원2동'):
   raise ValueError(f'Administrative name mismatch: {r}')
 if df.duplicated(['period','adm_cd','서비스_업종_코드']).any():raise ValueError('Duplicate market key')
 df['industry']=df['서비스_업종_코드']
 df['domain']=df.industry.map(MARKET_DOMAINS)
 return df.drop(columns=[c for c in df if c.startswith('Unnamed:')])

def read_card(path):
 df=read_csv(path)
 cols=['TA_YMD','MCT_SGG_CD','MCT_RY_CD','CLN_SGG_CD','SEX_CCD','AGE_CCD','TS_AT','USE_CNT']
 required(df,cols)
 df=df[df.MCT_SGG_CD.isin(['서울 강남구','서울시 강남구'])].copy()
 if df.empty:raise ValueError(f'No Gangnam card data: {path}')
 df['CLN_SGG_CD']=df.CLN_SGG_CD.fillna('정보없음')
 if df[[c for c in cols if c!='CLN_SGG_CD']].isna().any().any():raise ValueError('Card required fields missing')
 df=df[cols] # exported index is not a business key
 df['MCT_SGG_CD']='서울 강남구'
 if df.duplicated([c for c in cols if c not in ('TS_AT','USE_CNT')]).any():raise ValueError('Duplicate card business key')
 check_numeric(df,['TS_AT','USE_CNT'])
 dates=pd.to_datetime(df.TA_YMD.astype(str),format='%Y%m%d',errors='raise')
 df['date']=dates.dt.strftime('%Y-%m-%d')
 df['period']=dates.dt.strftime('%Y-%m')
 df['age']=df.AGE_CCD.map(harmonize_age)
 df['domain']=df.MCT_RY_CD.map(CARD_DOMAINS)
 return df

def prepare(config):
 """Validate all files before committing. Incomplete periods wait, malformed files fail."""
 if config.get('minimum_same_quarter_history',3)<3:raise ValueError('Minimum same-quarter history must be at least 3')
 pd.Period(config.get('first_detection_quarter','2025Q3'),freq='Q')
 packets={};waiting=[]
 for source,root,reader in [('market',config['market_root'],read_market),('card',config['card_root'],read_card)]:
  files=sorted(Path(root).glob('*.csv'))
  if not files:waiting.append(f'{source}: no CSV files')
  for path in files:
   df=reader(path)
   for period,g in df.groupby('period',sort=True):
    complete=set(g.adm_cd)=={v[0] for v in CROSSWALK.values()} if source=='market' else (set(g.date)==set(pd.date_range(period,periods=calendar.monthrange(int(period[:4]),int(period[5:]))[1]).strftime('%Y-%m-%d')) and set(g.age)==set(AGES))
    if not complete:
     waiting.append(f'{source} {period}: incomplete region/day/age coverage ({path.name})');continue
    keys=['adm_cd','industry'] if source=='market' else ['date','MCT_RY_CD','AGE_CCD','CLN_SGG_CD','SEX_CCD']
    digest=fingerprint(g,keys)
    end=quarter_end(period) if source=='market' else pd.Period(period,'M').end_time.normalize()
    available=config.get('available_from',{}).get(source+':'+period)
    if available:
     available=str(pd.Timestamp(available).date())
     if pd.Timestamp(available)<end:raise ValueError('Publication date before observation end')
    key=(source,period)
    if key in packets:
     if packets[key]['digest']!=digest:raise ValueError(f'Conflicting complete snapshots for {key}')
     packets[key]['paths'].append(str(path));continue
    if source=='market':
     records=clean_records(g.sort_values(keys))
    else:
     agg=g.groupby(['AGE_CCD','age','MCT_RY_CD'],as_index=False).agg(use_count=('USE_CNT','sum'),amount=('TS_AT','sum'),observed_days=('date','nunique'),raw_rows=('date','size'))
     agg=agg.rename(columns={'AGE_CCD':'age_raw','MCT_RY_CD':'industry'})
     agg['domain']=agg.industry.map(CARD_DOMAINS)
     records=clean_records(agg)
    packets[key]={'digest':digest,'records':records,'paths':[str(path)],'available':available,'metadata':{'raw_rows':len(g),'count_total':int(g['당월_매출_건수' if source=='market' else 'USE_CNT'].sum()),'amount_total':float(g['당월_매출_금액' if source=='market' else 'TS_AT'].sum()),'domain_mapping_version':VERSION,'district':'11680','scope':'merchant_dong' if source=='market' else 'merchant_district'}}
 return packets,waiting

def safe_ratio(a,b):return None if b is None or b==0 or a is None else float(a/b)
def pct(a,b):
 r=safe_ratio(a,b)
 return None if r is None else (r-1)*100

def store_payload(con,table,keys,record):
 cols=','.join([*keys,'payload_json'])
 vals=[*keys.values(),payload(record)]
 con.execute(f'INSERT INTO {table}({cols}) VALUES({",".join("?" for _ in vals)})',vals)

def market_frames(con):
 rows=con.execute('SELECT payload_json FROM a3a_industry ORDER BY period,adm_cd,industry').fetchall()
 return pd.DataFrame([json.loads(r[0]) for r in rows])

def make_market_features(con,config):
 df=market_frames(con)
 if df.empty:return
 periods=sorted(df.period.unique()); codes=sorted({v[0] for v in CROSSWALK.values()})
 groups={(p,c,d):g for (p,c,d),g in df[df.domain.notna()].groupby(['period','adm_cd','domain'])}
 counts={key:{r['industry']:{age:int(r[col]) for age,col in AGE_COLS.items()} for r in g.to_dict('records')} for key,g in groups.items()}
 def basket_count(key,basket,age):return sum(counts[key][industry][age] for industry in basket)
 features=[];comparisons=[]
 first=config.get('first_detection_quarter','2025Q3');minimum=config.get('minimum_same_quarter_history',3)
 for p in periods:
  days=quarter_days(p)
  prior=[x for x in periods if x<p and x[-1]==p[-1]]
  for code in codes:
   for domain in DOMAINS:
    g=groups.get((p,code,domain)); observed=0 if g is None else len(g)
    total=None if g is None else int(g['당월_매출_건수'].sum())
    amount=None if g is None else float(g['당월_매출_금액'].sum())
    capture=None if g is None else int(g[list(AGE_COLS.values())].sum().sum())
    expected=sum(d==domain for d in MARKET_DOMAINS.values())
    past=[groups.get((x,code,domain)) for x in prior]
    common=set() if g is None or not past or any(t is None for t in past) else set(g.industry).intersection(*(set(t.industry) for t in past))
    for age,col in AGE_COLS.items():
     count=None if g is None else int(g[col].sum())
     f={'period':p,'adm_cd':code,'age':age,'domain':domain,'count':count,'amount':None if g is None else float(g[AGE_AMOUNT[age]].sum()),'daily_count':safe_ratio(count,days),'days':days,'observed_industries':observed,'defined_industries':expected,'observed_share':observed/expected,'age_capture_ratio':safe_ratio(capture,total),'domain_total_count':total,'domain_total_amount':amount,'missing_domain':g is None,'age_basis':'customer_age','location_basis':'merchant_dong'}
     features.append(f)
     if p<first:continue
     current=None if not common else basket_count((p,code,domain),common,age)
     current_daily=safe_ratio(current,days)
     baselines=[basket_count((x,code,domain),common,age)/quarter_days(x) for x in prior] if common else []
     valid=len(baselines)>=minimum
     base_mean=sum(baselines)/len(baselines) if baselines else None
     changed=pct(current_daily,base_mean) if valid else None
     c={'period':p,'adm_cd':code,'age':age,'domain':domain,'baseline_n':len(baselines),'baseline_periods':prior if common else [],'baseline_latest':prior[-1] if common else None,'baseline_method':'expanding_prior_same_quarter_matched_industries','matched_industries':sorted(common),'matched_industry_count':len(common),'current_observed_industry_count':observed,'matched_current_count':current,'matched_current_daily_count':current_daily,'baseline_daily_mean':base_mean,'baseline_daily_min':min(baselines) if baselines else None,'baseline_daily_max':max(baselines) if baselines else None,'change_pct':changed,'comparison_available':valid,'below_prior_min':bool(current_daily<min(baselines)) if valid else None,'above_prior_max':bool(current_daily>max(baselines)) if valid else None,'gangnam_change_percentile':None,'gangnam_compare_n':0,'comparison_reason':'ready' if valid else 'insufficient_matched_same_quarter_history'}
     # Exact prior quarter / year, never shift across missing periods; common-basket comparisons.
     for label,prev in [('qoq',str(pd.Period(p,'Q')-1)),('yoy',str(pd.Period(p,'Q')-4))]:
      pg=groups.get((prev,code,domain));basket=set() if g is None or pg is None else set(g.industry)&set(pg.industry)
      c[label+'_matched_industry_count']=len(basket)
      c[label+'_daily_change_pct']=None if not basket else pct(basket_count((p,code,domain),basket,age)/days,basket_count((prev,code,domain),basket,age)/quarter_days(prev))
     comparisons.append(c)
 for f in features:
  store_payload(con,'a3a_feature',{'period':f['period'],'adm_cd':f['adm_cd'],'age':f['age'],'domain':f['domain'],'observed_industries':f['observed_industries']},f)
 comp=pd.DataFrame(comparisons)
 if not comp.empty:
  valid=comp.change_pct.notna() & comp.comparison_available
  comp.loc[valid,'gangnam_change_percentile']=comp[valid].groupby(['period','age','domain']).change_pct.rank(method='average',pct=True)
  comp.loc[valid,'gangnam_compare_n']=comp[valid].groupby(['period','age','domain']).change_pct.transform('count')
  for c in clean_records(comp):store_payload(con,'a3a_comparison',{k:c[k] for k in ('period','adm_cd','age','domain','baseline_n','comparison_available')},c)
 for p in periods:
  for code in codes:
   g=df[(df.period==p)&(df.adm_cd==code)]
   cs=[c for c in comparisons if c['period']==p and c['adm_cd']==code]
   summary={'period':p,'adm_cd':code,'observed_industries':len(g),'count':int(g['당월_매출_건수'].sum()),'amount':float(g['당월_매출_금액'].sum()),'daily_count':float(g['당월_매출_건수'].sum())/quarter_days(p),'age_capture_ratio':safe_ratio(float(g[list(AGE_COLS.values())].sum().sum()),float(g['당월_매출_건수'].sum())),'compared_age_domain_cells':sum(c['comparison_available'] for c in cs),'below_prior_min_cells':sum(c['below_prior_min'] is True for c in cs),'above_prior_max_cells':sum(c['above_prior_max'] is True for c in cs),'interpretation':'merchant_area_consumption_context_not_resident_consumption'}
   store_payload(con,'a3a_quarter_summary',{'period':p,'adm_cd':code},summary)

def make_card_features(con):
 rows=con.execute('SELECT period,payload_json FROM a3b_industry ORDER BY period,age_raw,industry').fetchall()
 if not rows:return
 df=pd.DataFrame([{'period':p,**json.loads(j)} for p,j in rows])
 periods=sorted(df.period.unique());out=[];totals=[]
 total_lookup={};groups={(p,a,d):g for (p,a,d),g in df[df.domain.notna()].groupby(['period','age','domain'])}
 for p in periods:
  days=calendar.monthrange(int(p[:4]),int(p[5:]))[1]
  for age in AGES:
   g=df[(df.period==p)&(df.age==age)]
   if g.empty:continue
   prev=str(pd.Period(p,'M')-1); prev_total=total_lookup.get((prev,age))
   t={'period':p,'district':'11680','age':age,'count':int(g.use_count.sum()),'amount':float(g.amount.sum()),'daily_count':float(g.use_count.sum())/days,'days':days,'observed_industries':g.industry.nunique()}
   t['mom_daily_change_pct']=None if prev_total is None else pct(t['daily_count'],prev_total['daily_count'])
   total_lookup[p,age]=t;totals.append(t)
   for domain in DOMAINS:
    dg=groups.get((p,age,domain));pg=groups.get((prev,age,domain))
    common=set() if dg is None or pg is None else set(dg.industry)&set(pg.industry)
    current=None if dg is None else int(dg.use_count.sum())
    observed=0 if dg is None else dg.industry.nunique()
    current_daily=safe_ratio(current,days)
    prev_daily=None if pg is None else float(pg.use_count.sum())/calendar.monthrange(int(prev[:4]),int(prev[5:]))[1]
    matched_change=None if not common else pct(float(dg[dg.industry.isin(common)].use_count.sum())/days,float(pg[pg.industry.isin(common)].use_count.sum())/calendar.monthrange(int(prev[:4]),int(prev[5:]))[1])
    # The total age control also uses only industries present in BOTH adjacent months.
    prior_g=df[(df.period==prev)&(df.age==age)]
    total_common=set(g.industry)&set(prior_g.industry)
    matched_control=None if not total_common else pct(float(g[g.industry.isin(total_common)].use_count.sum())/days,float(prior_g[prior_g.industry.isin(total_common)].use_count.sum())/calendar.monthrange(int(prev[:4]),int(prev[5:]))[1])
    f={'period':p,'district':'11680','age':age,'domain':domain,'count':current,'amount':None if dg is None else float(dg.amount.sum()),'daily_count':current_daily,'days':days,'observed_industries':observed,'defined_industries':sum(d==domain for d in CARD_DOMAINS.values()),'observed_industry_days_min':None if dg is None else int(dg.observed_days.min()),'missing_domain':dg is None,'mom_daily_change_pct':pct(current_daily,prev_daily),'matched_mom_daily_change_pct':matched_change,'matched_industry_count':len(common),'matched_control_change_pct':matched_control,'relative_change_pp':None if matched_change is None or matched_control is None else matched_change-matched_control,'baseline_status':'no_previous_month' if prev_total is None else 'adjacent_month_descriptive_only','count_share_of_all_industries':safe_ratio(current,t['count']),'amount_per_transaction':None if dg is None else safe_ratio(float(dg.amount.sum()),current),'location_basis':'merchant_district','resident_scope':'all_customer_residences','seasonal_history_available':False}
    out.append(f)
 for t in totals:store_payload(con,'a3b_total',{k:t[k] for k in ('period','district','age')},t)
 for f in out:store_payload(con,'a3b_feature',{k:f[k] for k in ('period','district','age','domain','observed_industries')},f)
 for p in periods:
  g=df[df.period==p]
  summary={'period':p,'district':'11680','count':int(g.use_count.sum()),'amount':float(g.amount.sum()),'observed_industries':g.industry.nunique(),'core_count_share':safe_ratio(float(g[g.domain.notna()].use_count.sum()),float(g.use_count.sum())),'scope':'district_merchant_consumption_context_not_dong_observation'}
  store_payload(con,'a3b_month_summary',{'period':p,'district':'11680'},summary)

DERIVED=['a3a_feature','a3a_comparison','a3b_feature','a3b_total','a3a_quarter_summary','a3b_month_summary']
def apply_packets(db,packets,config):
 db=Path(db)
 if not db.exists():raise ValueError('Initialize Analysis1/2 DB first; DB1 database does not exist')
 with sqlite3.connect(db,timeout=60) as con:
  con.execute('PRAGMA foreign_keys=ON')
  if con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='v_db1_integrated'").fetchone()[0]!=1:raise ValueError('Missing DB1 integrated view')
  con.executescript((ROOT/'db/schema.sql').read_text(encoding='utf-8'))
  con.execute('BEGIN IMMEDIATE')
  con.executemany('INSERT OR IGNORE INTO a3_dimension VALUES(?,?)',[(a,d) for a in AGES for d in DOMAINS])
  policy=payload({'version':VERSION,'minimum_same_quarter_history':config.get('minimum_same_quarter_history',3),'first_detection_quarter':config.get('first_detection_quarter','2025Q3'),'market_domains':MARKET_DOMAINS,'card_domains':CARD_DOMAINS,'crosswalk':CROSSWALK})
  old_policy=con.execute('SELECT policy_json FROM a3_policy WHERE id=1').fetchone()
  if old_policy and old_policy[0]!=policy:raise ValueError('Stored preprocessing policy changed; explicit versioned migration required')
  if not old_policy:con.execute('INSERT INTO a3_policy VALUES(1,?)',(policy,))
  expected={v[0] for v in CROSSWALK.values()}
  stored={r[0] for r in con.execute('SELECT DISTINCT adm_cd FROM a1_context')}
  if expected!=stored:raise ValueError('Crosswalk differs from Analysis1 region set')
  changed=0;skipped=0
  for (source,p),packet in sorted(packets.items()):
   old=con.execute('SELECT fingerprint,version,available_from FROM a3_run WHERE source=? AND period=?',(source,p)).fetchone()
   if old:
    if tuple(old)!=(packet['digest'],VERSION,packet['available']):raise ValueError(f'{source} {p}: stored snapshot or publication metadata differs; overwrite blocked')
    skipped+=1;continue
   last=con.execute('SELECT MAX(period) FROM a3_run WHERE source=?',(source,)).fetchone()[0]
   if last is not None and p<last:raise ValueError(f'{source} {p}: historical backfill would alter past baselines; explicit migration required')
   for r in packet['records']:
    if source=='market':store_payload(con,'a3a_industry',{'period':p,'adm_cd':r['adm_cd'],'industry':r['industry'],'domain':r['domain']},r)
    else:store_payload(con,'a3b_industry',{'period':p,'district':'11680','age_raw':r['age_raw'],'age':r['age'],'industry':r['industry'],'domain':r['domain']},r)
   metadata={**packet['metadata'],'paths':packet['paths'],'observation_period':p,'availability_policy':'explicit_date_only_else_retrospective'}
   con.execute('INSERT INTO a3_run(source,period,fingerprint,version,available_from,metadata_json) VALUES(?,?,?,?,?,?)',(source,p,packet['digest'],VERSION,packet['available'],payload(metadata)))
   changed+=1
  if changed or not con.execute('SELECT COUNT(*) FROM a3a_feature').fetchone()[0]:
   for table in DERIVED:con.execute(f'DELETE FROM {table}')
   make_market_features(con,config);make_card_features(con)
  if con.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Foreign key validation failed')
 return {'stored_periods':changed,'unchanged_periods':skipped}

def export(db,directory,integrated_directory=None):
 directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
 integrated_directory=Path(integrated_directory) if integrated_directory else ROOT.parent/'outputs/integrated'
 integrated_directory.mkdir(parents=True,exist_ok=True)
 integrated_names={'v_a2_quarter':'analysis2_quarter','v_a123_monthly':'analysis123_monthly','v_a123_detail':'analysis123_detail','v_a123_available_context':'analysis123_available_context'}
 with sqlite3.connect(db) as con:
  tables=['a3_run',*DERIVED,'v_a2_quarter','v_a123_monthly','v_a123_detail','v_a123_available_context']
  def flatten_context(frame):
   prefixes={'a3a_summary':'a3a','a3b_summary':'a3b','a3a_feature':'a3a_feature','a3a_comparison':'a3a_comparison','a3b_month_context':'a3b_context'}
   for column,prefix in prefixes.items():
    if column not in frame:continue
    values=[{} if pd.isna(j) else json.loads(j) for j in frame[column]]
    expanded=pd.DataFrame(values,index=frame.index)
    frame=frame.drop(columns=column)
    for c in expanded:
     name=prefix+'_'+c
     if name not in frame:frame[name]=expanded[c]
   return frame
  for t in tables:
   frame=pd.read_sql_query(f'SELECT * FROM {t}',con)
   if 'payload_json' in frame:
    expanded=pd.DataFrame([json.loads(j) for j in frame.payload_json])
    frame=frame.drop(columns='payload_json')
    for c in expanded:
     if c not in frame:frame[c]=expanded[c]
   frame=flatten_context(frame)
   for c in frame:
    if frame[c].map(lambda x:isinstance(x,(list,dict))).any():frame[c]=frame[c].map(lambda x:payload(x) if isinstance(x,(list,dict)) else x)
   folder=integrated_directory if t in integrated_names else directory
   name=integrated_names.get(t,t)
   tmp=folder/(name+'.csv.tmp');frame.to_csv(tmp,index=False,encoding='utf-8-sig');tmp.replace(folder/(name+'.csv'))
  detail=flatten_context(pd.read_sql_query('SELECT * FROM v_a123_detail WHERE any_signal=1',con))
  for c in detail:
   if detail[c].map(lambda x:isinstance(x,(list,dict))).any():detail[c]=detail[c].map(lambda x:payload(x) if isinstance(x,(list,dict)) else x)
  detail.to_csv(integrated_directory/'signal_context_detail.csv',index=False,encoding='utf-8-sig')
  mapping=[]
  for source,table in [('market','a3a_industry'),('card','a3b_industry')]:
   for industry,domain,j in con.execute(f'SELECT industry,domain,MIN(payload_json) FROM {table} GROUP BY industry,domain'):
    r=json.loads(j)
    mapping.append({'source':source,'industry':industry,'industry_name':r.get('서비스_업종_코드_명',industry),'domain':domain,'included_core':domain is not None,'mapping_version':VERSION,'source_taxonomies_identical':False})
  (directory/'mappings').mkdir(exist_ok=True)
  pd.DataFrame(mapping).to_csv(directory/'mappings/industry_mapping.csv',index=False,encoding='utf-8-sig')
  pd.DataFrame([{'public_adm_cd':c,'adm_cd':v[0],'adm_nm':v[1],'legacy_alias':'일원2동' if c=='11680740' else ''} for c,v in CROSSWALK.items()]).to_csv(directory/'mappings/region_crosswalk.csv',index=False,encoding='utf-8-sig')

def status(db):
 with sqlite3.connect(db) as con:
  counts={t:con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0] for t in ['a3_run','a3a_industry','a3b_industry',*DERIVED,'v_a123_monthly','v_a123_detail']}
  counts['behavior_signal_months']=con.execute('SELECT COUNT(*) FROM v_a123_monthly WHERE any_signal=1').fetchone()[0]
  counts['integrity']=con.execute('PRAGMA integrity_check').fetchone()[0]
  last=dict(con.execute('SELECT source,MAX(period) FROM a3_run GROUP BY source').fetchall())
  counts['last_market_quarter']=last.get('market')
  counts['last_card_month']=last.get('card')
  counts['next_expected_market']=None if 'market' not in last else str(pd.Period(last['market'],'Q')+1)
  counts['next_expected_card']=None if 'card' not in last else str(pd.Period(last['card'],'M')+1)
 return counts
