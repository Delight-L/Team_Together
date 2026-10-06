import argparse,pandas as pd
from analysis.baseline import save_baseline
from pathlib import Path
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--out-dir',default=str(ROOT/'models/2025H2'));p.add_argument('--results-dir',default=str(ROOT/'outputs/baseline'));a=p.parse_args();d=pd.read_csv(a.input,dtype={'adm_cd':str});f,b,c,_=save_baseline(d,a.out_dir,results_dir=a.results_dir);print({'features':f.shape,'balanced':b.shape,'clusters':c.shape,'cluster_sizes':c.cluster.value_counts().sort_index().to_dict()})
