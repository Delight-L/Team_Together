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
    parser.add_argument('command',choices=['initialize','analysis1','analysis1-elder','survey-context','analysis2','analysis2-age','analysis2-age-detect','analysis2-activity','source-semantics','evidence-context','analysis3','scan','watch','export','status'])
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
        cmd+=['--db',str(selected_db),'--db1-config',str(config)]
        cmd+=['--integrated-exports',str((ROOT/settings.get('exports','outputs/integrated')).resolve())]
        subprocess.run(cmd,check=True)
        if command!='status':
            activity_level()
            source_semantics()
            survey_context(export_only=True)
    def activity_level():
        import sqlite3
        from contextlib import closing
        settings=json.loads(config.read_text(encoding='utf-8'))
        selected_db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        with closing(sqlite3.connect(selected_db)) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_detection'").fetchone(): return
        subprocess.run([sys.executable,str(ROOT/'Analysis2/activity_level.py'),'--db',str(selected_db),'--output',str(ROOT/'Analysis2/outputs/activity_level')],check=True)
    def source_semantics():
        import sqlite3
        from contextlib import closing
        settings=json.loads(config.read_text(encoding='utf-8'))
        selected_db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        with closing(sqlite3.connect(selected_db)) as con:
            if not con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_raw'").fetchone(): return
        subprocess.run([sys.executable,str(ROOT/'Context/source_semantics.py'),'--db',str(selected_db),'--output',str(ROOT/'Analysis2/outputs/source_semantics')],check=True)
        evidence_context()
    def evidence_context():
        settings=json.loads(config.read_text(encoding='utf-8'))
        selected_db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        subprocess.run([sys.executable,str(ROOT/'Context/evidence_context.py'),'--config',str(config),'--db',str(selected_db),'--output',str(ROOT/'Context/outputs/evidence')],check=True)
    def survey_context(export_only=False):
        settings=json.loads(config.read_text(encoding='utf-8'))
        if not settings.get('survey_context'): return
        selected_db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        cmd=[sys.executable,str(ROOT/'Context/survey.py'),'--config',str(config),'--db',str(selected_db),'--output',str((ROOT/settings.get('exports','outputs/integrated')).resolve())]
        if export_only: cmd+=['--export-only']
        subprocess.run(cmd,check=True)
    if args.command=='initialize':
        worker('Analysis1',['--period','2025H2','--bootstrap'])
        worker('Analysis2',['--initialize'])
        analysis3()
    elif args.command=='survey-context':
        survey_context()
    elif args.command=='analysis1':
        if not args.period: parser.error('--period is required')
        extra=['--period',args.period]
        for key in ['effective_from','resident','household','disability','welfare','disability_year']:
            value=getattr(args,key)
            if value is not None: extra+=['--'+key.replace('_','-'),str(value)]
        worker('Analysis1',extra)
        analysis3()
    elif args.command=='analysis1-elder':
        settings=json.loads(config.read_text(encoding='utf-8'))
        selected_db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        subprocess.run([sys.executable,str(ROOT/'Analysis1/elder_context.py'),'--db',str(selected_db),'--config',str(config),'--output',str((ROOT/settings.get('exports','outputs/integrated')).resolve())],check=True)
    elif args.command=='analysis2':
        if not args.month: parser.error('--month is required')
        worker('Analysis2',['--month',args.month])
        analysis3()
    elif args.command=='analysis2-age':
        cmd=[sys.executable,str(ROOT/'Analysis2/age_features.py'),'--config',str(config)]
        if args.db: cmd+=['--db',args.db]
        if args.month: cmd+=['--month',args.month]
        subprocess.run(cmd,check=True)
    elif args.command=='analysis2-age-detect':
        settings=json.loads(config.read_text(encoding='utf-8'))
        db=Path(args.db).resolve() if args.db else (ROOT/settings['database']).resolve()
        subprocess.run([sys.executable,str(ROOT/'Analysis2/age_detection.py'),'--db',str(db)],check=True)
        analysis3('export')
    elif args.command=='analysis2-activity':
        activity_level()
    elif args.command=='evidence-context':
        evidence_context()
    elif args.command=='source-semantics':
        source_semantics()
    elif args.command=='analysis3':
        analysis3()
    elif args.command=='scan':
        survey_context()
        worker('Analysis1',['--scan'])
        worker('Analysis2',['--scan'])
        analysis3()
    elif args.command=='watch':
        if args.interval<10: parser.error('--interval must be at least 10 seconds')
        while True:
            survey_context()
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
            with store.connect(db) as con:
                has_age=con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_feature'").fetchone()
            if has_age:
                subprocess.run([sys.executable,str(ROOT/'Analysis2/age_features.py'),'--db',str(db),'--export-only'],check=True)
                with store.connect(db) as con:
                    has_age_detection=con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_detection'").fetchone()
                if has_age_detection:
                    subprocess.run([sys.executable,str(ROOT/'Analysis2/age_detection.py'),'--db',str(db),'--export-only'],check=True)
            analysis3('export')
            survey_context(export_only=True)
        else:
            with store.connect(db) as con:
                for table in ['a1_input','a1_context','a1_region_feature','a1_change_detection','a2_feature','a2_detection','a2_evidence']:
                    print(table,con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])
                if con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_activity_followup'").fetchone():
                    print('a2_activity_followup',con.execute('SELECT COUNT(*) FROM a2_activity_followup').fetchone()[0])
                print('runs',con.execute('SELECT analysis,period FROM db1_run ORDER BY analysis,period').fetchall())
                if con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_feature'").fetchone():
                    print('a2_age_feature',con.execute('SELECT age_scheme,COUNT(*) FROM a2_age_feature GROUP BY age_scheme').fetchall())
                if con.execute("SELECT 1 FROM sqlite_master WHERE name='a2_age_detection'").fetchone():
                    print('a2_age_detection',con.execute('SELECT COUNT(*),SUM(communication_signal),SUM(mobility_signal),SUM(combined_signal) FROM a2_age_detection').fetchone())
            if (ROOT/'Analysis3'/'run_analysis3.py').exists(): analysis3('status')

if __name__=='__main__': main()
