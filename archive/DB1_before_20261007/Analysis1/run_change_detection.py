from pathlib import Path
import argparse,sys
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))
from analysis.change_detector import detect_changes
from preprocessing.periods import halfyear
from common.config import CONFIG
import db1_store as store

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',required=True);p.add_argument('--baseline',required=True);p.add_argument('--period',required=True)
    p.add_argument('--out-dir',default=str(ROOT/'Analysis1/data/results/analysis1_detection'))
    p.add_argument('--db',default=str(ROOT/'outputs/db1.sqlite'));p.add_argument('--effective-from')
    a=p.parse_args();_,_,dates=halfyear(a.period)
    effective=pd.Timestamp(a.effective_from or dates[-1]+pd.offsets.MonthBegin(1))
    if effective<dates[-1]+pd.offsets.MonthBegin(1):raise ValueError('Context cannot apply before period completion')
    d=pd.read_csv(a.input,dtype={'adm_cd':str});f,b,x=detect_changes(d,a.baseline,a.period)
    c=f.copy();c['cluster']=x.current_cluster;c['cluster_type']=x.current_cluster_type
    metadata={'feature_domains':{f:domain for domain,cols in CONFIG.domains.items() for f in cols},'input':str(Path(a.input).resolve())}
    store.commit_a1(a.db,d,f,c,a.period,str(effective.date()),False,x,metadata)
    out=Path(a.out_dir);out.mkdir(parents=True,exist_ok=True)
    f.to_csv(out/f'analysis1_features_{a.period}.csv',index=False,encoding='utf-8-sig')
    x.to_csv(out/f'analysis1_change_detection_{a.period}.csv',index=False,encoding='utf-8-sig')
    print({'features':f.shape,'detection':x.shape,'cluster_changed':int(x.cluster_changed.sum()),'db':a.db})
if __name__=='__main__':main()
