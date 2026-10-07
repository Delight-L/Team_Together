import pandas as pd
from .loader import read_local
from .periods import quarter_indices

def preprocess_resident(path,year=2025,quarters=(3,4),quarter_blocks=None):
    raw=read_local(path)
    labels=raw.iloc[0,3:25].tolist()
    rows=raw[(raw['동별(1)']=='강남구') & (raw['동별(2)']!='소계')].copy()
    def quarter(name,indices):
        out=rows[['동별(2)','항목']+list(raw.columns[indices])].copy()
        cols=['dong_name','category','resident_total']
        for x in labels[1:]:
            clean=str(x).replace('~','_').replace('세 이상','_plus').replace('세','')
            cols.append('age_'+clean)
        out.columns=cols; out['quarter']=name
        for c in cols[2:]: out[c]=pd.to_numeric(out[c].replace('-',0),errors='coerce')
        return out
    blocks=quarter_indices(raw.columns,year,quarters,22,3,quarter_blocks)
    q=pd.concat([quarter(label,indices) for label,indices in blocks],ignore_index=True)
    t=q[q.category=='계'].copy()
    groups={
      'resident_0_19':['age_0_4','age_5_9','age_10_14','age_15_19'],
      'resident_20_29':['age_20_24','age_25_29'],
      'resident_30_39':['age_30_34','age_35_39'],
      'resident_40_49':['age_40_44','age_45_49'],
      'resident_50_64':['age_50_54','age_55_59','age_60_64'],
      'resident_65_plus':['age_65_69','age_70_74','age_75_79','age_80_84','age_85_89','age_90_94','age_95_99','age_100_plus']}
    for k,v in groups.items(): t[k]=t[v].sum(axis=1); t[k.replace('resident_','resident_ratio_')]=t[k]/t.resident_total
    f=q[q.category=='등록외국인'][['dong_name','quarter','resident_total']].rename(columns={'resident_total':'foreigner_count'})
    t=t.merge(f,on=['dong_name','quarter'],validate='one_to_one'); t['foreigner_ratio']=t.foreigner_count/t.resident_total
    ratio=[x.replace('resident_','resident_ratio_') for x in groups]
    return t.groupby('dong_name',as_index=False)[['resident_total']+ratio+['foreigner_ratio']].mean()
