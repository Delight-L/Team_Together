import pandas as pd
from .loader import read_local
GANGNAM=['신사동','논현1동','논현2동','압구정동','청담동','삼성1동','삼성2동','대치1동','대치2동','대치4동','역삼1동','역삼2동','도곡1동','도곡2동','개포1동','개포2동','개포3동','개포4동','세곡동','일원본동','일원1동','수서동']

def preprocess_disability(path,resident,year=2025):
    raw=read_local(path,sep='\t')
    x=raw[(raw['동별'].isin(GANGNAM)) & (raw['장애유형별']=='합계') & (raw['성별']=='계')].copy()
    matches=[c for c in x.columns if str(c).replace(' ','')==f'{year}년']
    if len(matches)!=1: raise ValueError(f'Disability data for {year} is missing or ambiguous')
    x['disability_count']=pd.to_numeric(x[matches[0]].replace('-',0),errors='raise')
    if (x.groupby('동별').disability_count.nunique()>1).any(): raise ValueError('Conflicting disability counts')
    # 원본에 동일 key 중복 세트가 존재하므로 동일값이면 1개 대표값만 사용
    x=x.groupby('동별',as_index=False).disability_count.first().rename(columns={'동별':'dong_name'})
    out=resident[['dong_name','resident_total']].merge(x,on='dong_name',validate='one_to_one')
    out['disability_ratio']=out.disability_count/out.resident_total
    return out[['dong_name','disability_ratio']]
