import sys as _settings_sys
from pathlib import Path as _SettingsPath
_settings_sys.path.insert(0, str(_SettingsPath(__file__).resolve().parents[1]))
from db1_settings import load_settings
from pathlib import Path
import argparse,json
from preprocessing.pipeline import build_analysis1_pca_input
from preprocessing.periods import halfyear

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--skt',required=True); p.add_argument('--resident',required=True); p.add_argument('--household',required=True); p.add_argument('--welfare',required=True)
 p.add_argument('--output',default='data/processed/analysis1_pca_input.csv')
 p.add_argument('--period',default='2025H2'); p.add_argument('--config',default=str(Path(__file__).resolve().parents[1]/'config/db1_config.json'));p.add_argument('--db')
 a=p.parse_args();year,quarters,_=halfyear(a.period); df=build_analysis1_pca_input(skt_feature=a.skt,resident_file=a.resident,household_file=a.household,welfare_file=a.welfare,year=year,quarters=quarters)
 from elder_context import attach_cluster_feature
 settings=load_settings(a.config);df,_=attach_cluster_feature(a.db or Path(__file__).resolve().parents[1]/settings['database'],settings,df,a.period)
 out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False,encoding='utf-8-sig'); print(f'SAVED {out} shape={df.shape}')
if __name__=='__main__': main()
