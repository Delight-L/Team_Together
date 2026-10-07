from pathlib import Path
import pandas as pd
import argparse
from preprocessing.skt_flow import build_period_from_dir
p=argparse.ArgumentParser()
p.add_argument('--raw-dir',default='data/raw/skt')
p.add_argument('--boundary',default='data/raw/boundary/seoul_dong_2017_epsg5179.geojson')
p.add_argument('--start',default='202507'); p.add_argument('--end',default='202512')
p.add_argument('--out-dir',default='data/processed')
a=p.parse_args()
start=pd.to_datetime(a.start,format='%Y%m'); end=pd.to_datetime(a.end,format='%Y%m')
if end<start: raise ValueError('end must not precede start')
months=pd.date_range(start,end,freq='MS').strftime('%Y%m').tolist()
monthly,period=build_period_from_dir(a.raw_dir,months,a.boundary)
out=Path(a.out_dir); out.mkdir(parents=True,exist_ok=True)
monthly.to_csv(out/f'gangnam_skt_monthly_{a.start}_{a.end}.csv',index=False,encoding='utf-8-sig')
period.to_csv(out/f'gangnam_skt_period_features_{a.start}_{a.end}.csv',index=False,encoding='utf-8-sig')
print('months:',months,'monthly:',monthly.shape,'period:',period.shape)
