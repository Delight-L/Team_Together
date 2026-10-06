from pathlib import Path
import argparse, json
import numpy as np, pandas as pd
from preprocessing.archive import prepare_skt_raw, validate_month_coverage
from preprocessing.skt_flow import build_period_from_dir
from preprocessing.pipeline import build_analysis1_pca_input
from preprocessing.periods import halfyear

p=argparse.ArgumentParser(description='Analysis1 2025H2 local preprocessing')
p.add_argument('--skt-source',required=True,help='Folder containing SKT CSV/ZIP files')
p.add_argument('--period',default='2025H2',help='YYYYH1 or YYYYH2')
p.add_argument('--disability-year',type=int)
p.add_argument('--boundary',required=True)
p.add_argument('--resident',required=True); p.add_argument('--household',required=True)
p.add_argument('--disability',required=True); p.add_argument('--welfare',required=True)
p.add_argument('--reference',default='data/reference/reference_pca_input_2025H2.csv')
p.add_argument('--work-dir',default='data/raw/skt'); p.add_argument('--out-dir')
a=p.parse_args()
year,quarters,dates=halfyear(a.period);months=dates.strftime('%Y%m').tolist()
found=prepare_skt_raw(a.skt_source,a.work_dir); validate_month_coverage(found,months)
monthly,skt6=build_period_from_dir(a.work_dir,months,a.boundary,time_profile='baseline')
out=Path(a.out_dir) if a.out_dir else Path(__file__).resolve().parent/'data/processed'/a.period
out.mkdir(parents=True,exist_ok=True)
monthly.to_csv(out/'skt_monthly.csv',index=False,encoding='utf-8-sig')
skt6.to_csv(out/'skt_period.csv',index=False,encoding='utf-8-sig')
full=build_analysis1_pca_input(skt_feature=out/'skt_period.csv',resident_file=a.resident,household_file=a.household,disability_file=a.disability,welfare_file=a.welfare,year=year,quarters=quarters,disability_year=a.disability_year)
full.to_csv(out/'pca_input.csv',index=False,encoding='utf-8-sig')
report={'monthly_shape':list(monthly.shape),'skt_6m_shape':list(skt6.shape),'pca_input_shape':list(full.shape),'months':months}
ref=Path(a.reference)
if ref.exists() and a.period=='2025H2':
    r=pd.read_csv(ref,dtype={'adm_cd':str}); x=full.copy(); x['adm_cd']=x['adm_cd'].astype(str)
    m=r.merge(x,on=['adm_cd','dong_name'],suffixes=('_ref','_act'),validate='one_to_one')
    if len(m)!=22 or len(x)!=22 or set(r.columns)!=set(x.columns): raise ValueError('Reference coverage/schema mismatch')
    diffs={c:float(np.nanmax(np.abs(m[c+'_ref']-m[c+'_act']))) for c in r.columns[2:]}
    report['reference_max_abs_diff']=max(diffs.values()); report['reference_pass']=report['reference_max_abs_diff']<=1e-8
    if not report['reference_pass']: raise ValueError(f'Reference mismatch: {diffs}')
print(json.dumps(report,ensure_ascii=False,indent=2))
