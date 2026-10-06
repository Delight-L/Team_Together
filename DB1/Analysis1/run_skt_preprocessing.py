from argparse import ArgumentParser
from pathlib import Path
from preprocessing.skt_flow import build_month_from_dir, validate_against_reference

p=ArgumentParser(description='SKT 유동인구 AGE/TIME/WKDY 월별 전처리')
p.add_argument('--raw-dir',required=True)
p.add_argument('--month',required=True,help='YYYYMM')
p.add_argument('--boundary',required=True,help='EPSG:5179 서울 행정동 경계 GeoJSON')
p.add_argument('--output',default=None)
p.add_argument('--reference',default=None)
a=p.parse_args()

df=build_month_from_dir(a.raw_dir,a.month,a.boundary)
out=Path(a.output or f'data/processed/gangnam_db1_features_{a.month}.csv')
out.parent.mkdir(parents=True,exist_ok=True)
# 기존 산출물 호환을 위해 STD_YM은 저장본에서 제외
df.drop(columns=['STD_YM']).to_csv(out,index=False,encoding='utf-8-sig')
print(f'[OK] saved: {out} / rows={len(df)} / dongs={df.adm_cd.nunique()}')
if a.reference:
    result=validate_against_reference(df,a.reference)
    print('[REFERENCE]',result)
    if not result['ok']: raise SystemExit(2)
