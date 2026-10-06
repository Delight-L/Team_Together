from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
c=json.loads((ROOT/'config/db1_config.json').read_text(encoding='utf-8'))['analysis1']
args=[sys.executable,str(ROOT/'Analysis1/run_full_preprocessing.py'),'--skt-source',c['skt_source'],'--boundary',c['boundary'],'--period','2025H2','--reference',str(ROOT/'Analysis1/data/reference/reference_pca_input_2025H2.csv'),'--work-dir',str(ROOT/'Analysis1/data/raw/skt'),'--out-dir',str(ROOT/'Analysis1/data/processed/2025H2')]
for name,path in c['public'].items():args+=['--'+name,path]
subprocess.run(args,check=True)
