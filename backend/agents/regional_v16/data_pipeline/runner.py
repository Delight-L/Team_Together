"""Portable, locked coordinator for isolated Analysis1/Analysis2 workers."""
from __future__ import annotations
from pathlib import Path as _DatabasePath
import sys as _database_sys
_database_sys.path.insert(0, str(next(p for p in _DatabasePath(__file__).resolve().parents if (p/'pipelines/db1').is_dir())))
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys

from pipelines.db1 import database

ROOT = Path(__file__).resolve().parents[1]

def settings(root=ROOT, db=None, exports=None):
    root=Path(root).resolve()
    cfg=json.loads((root/'config/data_pipeline.json').read_text(encoding='utf-8'))
    cfg['root']=str(root)
    cfg['database']=database.workspace(db or os.getenv('DB1_PIPELINE_SCHEMA') or cfg['database'])
    export_path=Path(exports).resolve() if exports else root/cfg['exports']
    cfg['exports']=str(export_path)
    cfg['analysis2']={key:str(root/value) for key,value in cfg['analysis2'].items()}
    return cfg

def locked(db):
    return database.locked(db)


def run(root=ROOT, db=None, exports=None, initialize_only=False, through=None,
        analysis1_input=None, analysis1_period=None):
    cfg=settings(root,db,exports)
    with locked(cfg['database']):
        work=Path(cfg['exports'])/'pipeline.runtime.json'
        work.parent.mkdir(parents=True,exist_ok=True)
        work.write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
        def worker(name,*args):
            subprocess.run([sys.executable,str(Path(cfg['root'])/'data_pipeline'/name),
                            '--config',str(work),*args],cwd=cfg['root'],check=True)
        worker('analysis1_worker.py','--bootstrap')
        if analysis1_input:
            if not analysis1_period: raise ValueError('--analysis1-period is required')
            worker('analysis1_worker.py','--input',str(Path(analysis1_input).resolve()),
                   '--period',analysis1_period)
        args=['--initialize-only'] if initialize_only else []
        if through: args+=['--through',through]
        worker('monthly_worker.py',*args)
    return status(cfg['database'])

def status(db):
    if not database.exists(db): return {'status':'uninitialized','version':16}
    with database.connect(db,readonly=True) as con:
        if 'pipeline_state' not in con.table_names(): return {'status':'ready','version':16,'workspace':database.workspace(db)}
        row=con.execute('SELECT payload_json FROM pipeline_state WHERE id=1').fetchone()
        result=json.loads(row[0]) if row else {'status':'uninitialized'}
        try:
            from data_pipeline.publication import active_snapshot
            snapshot=active_snapshot(db)
        except Exception: snapshot=None
        result.update(version=16,initial_end='2025-06',active_snapshot_id=(snapshot or {}).get('snapshot_id'),
            history_rows=con.execute('SELECT COUNT(*) FROM a2_feature').fetchone()[0],
            history_end=con.execute('SELECT MAX(date) FROM a2_feature').fetchone()[0],
            detection_rows=con.execute('SELECT COUNT(*) FROM a2_detection').fetchone()[0],
            age_detection_rows=con.execute('SELECT COUNT(*) FROM a2_age_detection').fetchone()[0])
        return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db'); p.add_argument('--exports');p.add_argument('--initialize-only',action='store_true')
    p.add_argument('--through',help='Last label month to process, YYYY-MM')
    p.add_argument('--status',action='store_true')
    p.add_argument('--analysis1-input');p.add_argument('--analysis1-period')
    a=p.parse_args()
    if a.status: result=status(settings(db=a.db)['database'])
    else: result=run(db=a.db,exports=a.exports,initialize_only=a.initialize_only,through=a.through,
                    analysis1_input=a.analysis1_input,analysis1_period=a.analysis1_period)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
