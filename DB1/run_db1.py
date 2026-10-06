"""Run each analysis in its own process to isolate the existing package names."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description='DB1 update and integrated storage')
    parser.add_argument('command',choices=['initialize','analysis1','analysis2','analysis3','scan','watch','export','status'])
    parser.add_argument('--interval',type=int,default=60)
    parser.add_argument('--config',default=str(ROOT/'config/db1_config.json'))
    parser.add_argument('--db')
    parser.add_argument('--period',help='Analysis1 half-year, e.g. 2026H1')
    parser.add_argument('--month',help='Analysis2 month, e.g. 2026-01')
    parser.add_argument('--effective-from',help='Analysis1 Context applicability month YYYY-MM')
    parser.add_argument('--resident'); parser.add_argument('--household'); parser.add_argument('--disability'); parser.add_argument('--welfare')
    parser.add_argument('--disability-year',type=int)
    args=parser.parse_args()
    config=Path(args.config).resolve()
    def worker(kind,extra=()):
        cmd=[sys.executable,str(ROOT/kind/'update_worker.py'),'--config',str(config)]
        if args.db: cmd+=['--db',args.db]
        subprocess.run(cmd+list(extra),check=True)
    def analysis3(command='scan'):
        cmd=[sys.executable,str(ROOT/'Analysis3'/'run_analysis3.py'),command]
        settings=json.loads(config.read_text(encoding='utf-8'))
        selected_db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        cmd+=['--db',str(selected_db)]
        cmd+=['--integrated-exports',str((ROOT/settings.get('exports','outputs/integrated')).resolve())]
        subprocess.run(cmd,check=True)
    if args.command=='initialize':
        worker('Analysis1',['--period','2025H2','--bootstrap'])
        worker('Analysis2',['--initialize'])
        analysis3()
    elif args.command=='analysis1':
        if not args.period: parser.error('--period is required')
        extra=['--period',args.period]
        for key in ['effective_from','resident','household','disability','welfare','disability_year']:
            value=getattr(args,key)
            if value is not None: extra+=['--'+key.replace('_','-'),str(value)]
        worker('Analysis1',extra)
        analysis3()
    elif args.command=='analysis2':
        if not args.month: parser.error('--month is required')
        worker('Analysis2',['--month',args.month])
        analysis3()
    elif args.command=='analysis3':
        analysis3()
    elif args.command=='scan':
        worker('Analysis1',['--scan'])
        worker('Analysis2',['--scan'])
        analysis3()
    elif args.command=='watch':
        if args.interval<10: parser.error('--interval must be at least 10 seconds')
        while True:
            worker('Analysis1',['--scan'])
            worker('Analysis2',['--scan'])
            analysis3()
            time.sleep(args.interval)
    else:
        import db1_store as store
        settings=json.loads(config.read_text(encoding='utf-8'))
        db=Path(args.db) if args.db else ROOT/settings['database']
        if args.command=='export':
            store.export_csv(db,ROOT/settings['exports'])
            analysis3('export')
        else:
            with store.connect(db) as con:
                for table in ['a1_input','a1_context','a1_region_feature','a1_change_detection','a2_feature','a2_detection','a2_evidence']:
                    print(table,con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
                print('runs',con.execute('SELECT analysis,period FROM db1_run ORDER BY analysis,period').fetchall())
            if (ROOT/'Analysis3'/'run_analysis3.py').exists(): analysis3('status')

if __name__=='__main__': main()
