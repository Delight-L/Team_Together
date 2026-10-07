from pathlib import Path
import argparse
from preprocessing.pipeline import build_analysis1_pca_input
from preprocessing.periods import halfyear

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--skt',required=True); p.add_argument('--resident',required=True); p.add_argument('--household',required=True); p.add_argument('--disability',required=True); p.add_argument('--welfare',required=True)
 p.add_argument('--output',default='data/processed/analysis1_pca_input.csv')
 p.add_argument('--period',default='2025H2');p.add_argument('--disability-year',type=int)
 a=p.parse_args();year,quarters,_=halfyear(a.period); df=build_analysis1_pca_input(skt_feature=a.skt,resident_file=a.resident,household_file=a.household,disability_file=a.disability,welfare_file=a.welfare,year=year,quarters=quarters,disability_year=a.disability_year)
 out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True); df.to_csv(out,index=False,encoding='utf-8-sig'); print(f'SAVED {out} shape={df.shape}')
if __name__=='__main__': main()
