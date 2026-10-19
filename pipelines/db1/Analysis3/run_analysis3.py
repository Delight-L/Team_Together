from pathlib import Path as _DatabasePath
import sys as _database_sys
_database_sys.path.insert(0, str(next(p for p in _DatabasePath(__file__).resolve().parents if (p/'pipelines/db1').is_dir())))
from pipelines.db1 import database
import sys
from pathlib import Path as _SettingsPath
sys.path.insert(0,str(_SettingsPath(__file__).resolve().parents[1]))
from db1_settings import load_settings
from pathlib import Path
import argparse,json,time
from pipeline import prepare,apply_packets,export,status

ROOT=Path(__file__).resolve().parent
def main():
 parser=argparse.ArgumentParser(description='Analysis3 preprocessing and DB1 consumption context')
 parser.add_argument('command',choices=['scan','status','export','watch'],nargs='?',default='scan')
 parser.add_argument('--config',default=str(ROOT/'config/analysis3_config.json'))
 parser.add_argument('--db1-config',default=str(ROOT.parent/'config/db1_config.json'))
 parser.add_argument('--db')
 parser.add_argument('--exports')
 parser.add_argument('--integrated-exports')
 parser.add_argument('--interval',type=int,default=60)
 args=parser.parse_args()
 config_path=Path(args.config).resolve()
 config=load_settings(config_path)
 db=database.workspace(args.db or config['database'])
 outputs=Path(args.exports).resolve() if args.exports else (ROOT/config['exports']).resolve()
 integrated=Path(args.integrated_exports).resolve() if args.integrated_exports else (ROOT/config.get('integrated_exports','../outputs/integrated')).resolve()
 if args.command=='status':
     print(json.dumps(status(db),ensure_ascii=False,indent=2))
     return
 if args.command=='export':
     export(db,outputs,integrated,context_config=args.db1_config)
     return
 def scan():
  packets,waiting=prepare(config)
  result=apply_packets(db,packets,config)
  export(db,outputs,integrated,context_config=args.db1_config,context_ingest=True)
  result['waiting']=waiting
  logs=ROOT/'logs'
  logs.mkdir(exist_ok=True)
  (logs/'last_scan.json').write_text(json.dumps({**result,'status':status(db)},ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(result,ensure_ascii=False))
  print(json.dumps(status(db),ensure_ascii=False))
 if args.command=='watch':
  if args.interval<10:
      parser.error('--interval must be at least 10 seconds')
  while True:
      scan()
      time.sleep(args.interval)
 else:
     scan()

if __name__=='__main__':
    main()
