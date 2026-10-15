"""Portable, locked coordinator for isolated Analysis1/Analysis2 workers."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def settings(root=ROOT, db=None, exports=None):
    root=Path(root).resolve()
    cfg=json.loads((root/'config/data_pipeline.json').read_text(encoding='utf-8'))
    cfg['root']=str(root)
    default_db_path=root/cfg['database']
    override=db or os.getenv('DB1_DATABASE_PATH')
    cfg['database']=str(Path(override).resolve() if override else root/cfg['database'])
    if exports:export_path=Path(exports).resolve()
    elif override and Path(cfg['database'])!=default_db_path:
        database_path=Path(cfg['database']);export_path=database_path.parent/(database_path.stem+'_exports')
    else:export_path=root/cfg['exports']
    cfg['exports']=str(export_path)
    cfg['analysis2']={key:str(root/value) for key,value in cfg['analysis2'].items()}
    return cfg

@contextmanager
def locked(db):
    path=Path(str(db)+'.lock'); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('a+b') as handle:
        if sys.platform=='win32':
            import msvcrt
            handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
            msvcrt.locking(handle.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(),fcntl.LOCK_EX)
        try: yield
        finally:
            if sys.platform=='win32':
                handle.seek(0); msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle.fileno(),fcntl.LOCK_UN)

def run(root=ROOT, db=None, exports=None, initialize_only=False, through=None,
        analysis1_input=None, analysis1_period=None):
    cfg=settings(root,db,exports)
    with locked(cfg['database']):
        work=Path(str(cfg['database'])+'.runtime.json')
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
    import sqlite3
    path=Path(db)
    if not path.is_file(): return {'status':'uninitialized','version':15}
    with sqlite3.connect(path) as con:
        row=con.execute('SELECT payload_json FROM pipeline_state WHERE id=1').fetchone()
        result=json.loads(row[0]) if row else {'status':'uninitialized'}
        try:
            from data_pipeline.snapshot_manager import active_snapshot
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
