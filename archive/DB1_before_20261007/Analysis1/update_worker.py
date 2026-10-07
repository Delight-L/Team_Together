from pathlib import Path
import argparse,json,shutil,sys,re
import joblib,numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from preprocessing.periods import halfyear,quarter_indices
from preprocessing.loader import read_local
from preprocessing.archive import prepare_skt_raw,validate_month_coverage
from preprocessing.skt_flow import build_period_from_dir
from preprocessing.pipeline import build_analysis1_pca_input
from analysis.baseline import save_baseline
from analysis.change_detector import detect_changes
from common.config import CONFIG
import db1_store as store


def public_sources(settings,options,year,quarters):
    sources=settings['analysis1']['public'].copy()
    root=Path(settings['analysis1'].get('public_root',Path(sources['resident']).parent))
    patterns={'resident':'등록인구*.csv','household':'세대원수별*.csv','disability':'장애인 현황(장애유형별*.csv'}
    for name,pattern in patterns.items():
        if options.get(name): sources[name]=options[name];continue
        matches=[]
        for path in root.rglob(pattern):
            raw=read_local(path,sep='\t' if name in {'household','disability'} else None)
            try:
                if name=='disability':
                    observation_year=options.get('disability_year') or year
                    if not any(str(c).replace(' ','')==f'{observation_year}년' for c in raw.columns):continue
                else: quarter_indices(raw.columns,year,quarters,22 if name=='resident' else 11,3 if name=='resident' else 2,(options.get('quarter_blocks') or {}).get(name))
                matches.append(path)
            except ValueError:continue
        if not matches: raise ValueError(f'Missing/ambiguous public data: {name} {year} {quarters}')
        if len(matches)!=1:raise ValueError(f'Multiple matching {name} exports; specify the intended path: {matches}')
        sources[name]=str(matches[0])
    if options.get('welfare'): sources['welfare']=options['welfare']
    return sources


def process(settings,db,period,bootstrap=False,overrides=None):
    year,quarters,dates=halfyear(period)
    if period=='2025H2' and not bootstrap:
        raise ValueError('Baseline cannot be updated; use initialize')
    options=dict(settings['analysis1'].get('periods',{}).get(period,{}))
    options.update({k:v for k,v in (overrides or {}).items() if v is not None})
    default_effective=dates[-1]+pd.offsets.MonthBegin(1)
    effective=pd.Timestamp(options.get('effective_from') or ('2025-07-01' if bootstrap else default_effective))
    if effective.day!=1 or (not bootstrap and effective<default_effective):
        raise ValueError('Context effective date cannot precede completion of the half-year')
    out=ROOT/'Analysis1/data/processed'/period
    out.mkdir(parents=True,exist_ok=True)
    result_dir=ROOT/'Analysis1/outputs/periods'/period
    result_dir.mkdir(parents=True,exist_ok=True)
    if bootstrap:
        raw_input=pd.read_csv(ROOT/'Analysis1/data/reference/reference_pca_input_2025H2.csv',dtype={'adm_cd':str})
    else:
        sources=public_sources(settings,options,year,quarters)
        months=dates.strftime('%Y%m').tolist()
        raw_dir=ROOT/'Analysis1/data/raw/skt'
        found=prepare_skt_raw(settings['analysis1']['skt_source'],raw_dir)
        validate_month_coverage(found,months)
        monthly,skt=build_period_from_dir(raw_dir,months,settings['analysis1']['boundary'])
        monthly.to_csv(out/'skt_monthly.csv',index=False,encoding='utf-8-sig')
        skt_path=out/'skt_period.csv'
        skt.to_csv(skt_path,index=False,encoding='utf-8-sig')
        raw_input=build_analysis1_pca_input(skt_feature=skt_path,resident_file=sources['resident'],household_file=sources['household'],disability_file=sources['disability'],welfare_file=sources['welfare'],year=year,quarters=quarters,disability_year=options.get('disability_year'),quarter_blocks=options.get('quarter_blocks'))
        raw_input['adm_cd']=raw_input.adm_cd.astype(str)
        options['sources']=sources
    model_path=ROOT/settings['analysis1']['baseline_model']
    if bootstrap:
        if model_path.exists():
            bundle=joblib.load(model_path)
            pd.testing.assert_frame_equal(bundle['baseline_features'][['adm_cd','dong_name']].assign(adm_cd=lambda x:x.adm_cd.astype(str)).reset_index(drop=True),raw_input[['adm_cd','dong_name']].reset_index(drop=True))
            features,balance,change=detect_changes(raw_input,bundle,period)
            if change.cluster_changed.any() or change.filter(like='delta_').abs().to_numpy().max()>1e-10: raise ValueError('Existing baseline model does not match approved reference')
            clusters=features.copy();clusters['cluster']=change.current_cluster;clusters['cluster_type']=change.current_cluster_type
        else:
            features,balance,clusters,bundle=save_baseline(raw_input,model_path.parent,results_dir=ROOT/'Analysis1/outputs/baseline')
        clusters['centroid_distance']=np.linalg.norm(balance.to_numpy()-bundle['kmeans'].cluster_centers_[clusters.cluster.to_numpy(int)],axis=1)
        change=None
    else:
        if not model_path.exists(): raise ValueError('Initialize the approved baseline first')
        features,balance,change=detect_changes(raw_input,model_path,period)
        clusters=features.copy();clusters['cluster']=change.current_cluster;clusters['cluster_type']=change.current_cluster_type
    metadata={'feature_domains':{f:d for d,cols in CONFIG.domains.items() for f in cols},'period':period,'effective_from':str(effective.date()),'public_sources':options,'retrospective_context':bool(bootstrap),'baseline_model':str(model_path)}
    saved=store.commit_a1(db,raw_input,features,clusters,period,str(effective.date()),bootstrap,change,metadata)
    raw_input.to_csv(out/'pca_input.csv',index=False,encoding='utf-8-sig')
    features.to_csv(result_dir/'features.csv',index=False,encoding='utf-8-sig')
    clusters.to_csv(result_dir/'context.csv',index=False,encoding='utf-8-sig')
    if change is not None: change.to_csv(result_dir/'changes.csv',index=False,encoding='utf-8-sig')
    print(json.dumps({'analysis':'analysis1','period':period,'saved':saved,'rows':len(features),'effective_from':str(effective.date())}),flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--config',required=True);p.add_argument('--db');p.add_argument('--period');p.add_argument('--bootstrap',action='store_true');p.add_argument('--scan',action='store_true')
    for name in ['resident','household','disability','welfare','effective-from']: p.add_argument('--'+name)
    p.add_argument('--disability-year',type=int)
    a=p.parse_args();settings=json.loads(Path(a.config).read_text(encoding='utf-8'));db=Path(a.db) if a.db else ROOT/settings['database']
    if a.scan:
        configured=set(settings['analysis1'].get('periods',{}))
        for path in Path(settings['analysis1']['skt_source']).glob('flow_age_pop_*.csv'):
            match=re.fullmatch(r'flow_age_pop_(20\d{2})(\d{2})\.csv',path.name)
            if match:configured.add(f'{match[1]}H{1 if int(match[2])<=6 else 2}')
        for period in sorted(configured):
            if period=='2025H2': continue
            store.initialize(db)
            with store.connect(db) as con:
                exists=con.execute("SELECT 1 FROM db1_run WHERE analysis='analysis1' AND period=?",(period,)).fetchone()
            if not exists:
                try: process(settings,db,period)
                except FileNotFoundError as exc: print(f'{period}: waiting for original files: {exc}',flush=True)
                except ValueError as exc:
                    if str(exc).startswith(('Missing/ambiguous','Disability data for')): print(f'{period}: waiting for public data: {exc}',flush=True)
                    else: raise
    else:
        if not a.period: p.error('--period is required')
        process(settings,db,a.period,a.bootstrap,{k:getattr(a,k) for k in ['resident','household','disability','welfare','effective_from','disability_year']})

if __name__=='__main__':main()
