import pandas as pd
from .loader import read_local
from .periods import quarter_indices

def preprocess_household(path,year=2025,quarters=(3,4),quarter_blocks=None):
    raw=read_local(path,sep='\t')
    src=raw.iloc[2:].copy()
    if '동별(1)' in raw.columns:
        districts=raw['동별(1)'].ffill()
        if districts.eq('강남구').any():
            src=src.loc[districts.loc[src.index].eq('강남구') & src['동별(2)'].ne('소계')]
    names=['household_total','hh_1','hh_2','hh_3','hh_4','hh_5','hh_6','hh_7','hh_8','hh_9','hh_10_plus']
    frames=[]
    for quarter, idx in quarter_indices(raw.columns,year,quarters,11,2,quarter_blocks):
        q=src.iloc[:,[1]+list(idx)].copy(); q.columns=['dong_name']+names; q['quarter']=quarter
        for c in names: q[c]=pd.to_numeric(q[c].replace('-',0),errors='coerce')
        frames.append(q)
    q=pd.concat(frames,ignore_index=True)
    q['hh_4plus']=q[['hh_4','hh_5','hh_6','hh_7','hh_8','hh_9','hh_10_plus']].sum(axis=1)
    for c in ['hh_1','hh_2','hh_3','hh_4plus']: q[c+'_ratio']=q[c]/q.household_total
    cols=['household_total','hh_1_ratio','hh_2_ratio','hh_3_ratio','hh_4plus_ratio']
    return q.groupby('dong_name',as_index=False)[cols].mean()
