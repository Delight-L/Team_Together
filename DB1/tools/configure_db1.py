"""Discover the currently supplied original-data locations; do not alter originals."""
from pathlib import Path
import argparse,json

def configure(source_root,output):
    source_root=Path(source_root)
    originals=source_root/'공모전 원본 데이터'
    public=source_root/'서울시 공공데이터'
    def one(pattern,root=public):
        hits=list(root.rglob(pattern))
        if len(hits)!=1: raise ValueError(f'Expected one source for {pattern}: {hits}')
        return str(hits[0])
    skt=list(originals.rglob('flow_age_pop_202507.csv'))
    canonical=[p.parent for p in skt if '전처리' not in str(p.parent)]
    if len(canonical)!=1: raise ValueError('Set the canonical SKT source directory explicitly')
    settings={
      'database':'outputs/db1.sqlite','exports':'outputs/integrated',
      'analysis1':{'skt_source':str(canonical[0]),'public_root':str(public),'boundary':one('서울_행정동_경계_2017_EPSG5179.geojson'),
        'public':{'resident':one('등록인구(연령별_동별)*.csv'),'household':one('세대원수별*.csv'),
        'disability':one('장애인 현황(장애유형별, 동별).csv'),'welfare':one('국민기초생활 수급자 동별 현황*.xlsx')},
        'periods':{'2025H2':{'disability_year':2025,'welfare_observation':'2024-05'}},
        'baseline_model':'Analysis1/models/2025H2/analysis1_baseline_2025H2.joblib'},
      'analysis2':{'telecom_dir':str(Path(one('2025.7월*29개*.xlsx')).parent),
        'interest_dir':str(Path(one('2025.7월*10개*.xlsx')).parent),
        'rain':one('강수량*강수일수*.csv'),'diary':one('일기일수*.csv')}}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Saved {output}')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-root',required=True);p.add_argument('--output',default=str(Path(__file__).resolve().parents[1]/'config/db1_config.json'));a=p.parse_args();configure(a.source_root,a.output)
