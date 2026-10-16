"""받은 db1.sqlite를 측정용으로 복사하고, v16 엔진이 필요로 하는 두 테이블을 복사본에만 추가합니다.

    python backend/tools/v16_bench/prepare_db.py <원본 db1.sqlite> <출력 폴더>

원본 파일은 바꾸지 않습니다. 출력
- <폴더>/snapshots/db1-real.sqlite  공개 snapshot 경로(불변 파일로 취급)
- <폴더>/work/db1-work.sqlite       작업 DB 경로

복사본에만 추가하는 테이블(PostgreSQL 게시가 하는 변환과 같은 코드를 씁니다: data_pipeline/db1_compat.py)
- pipeline_state: v16 월별 작업기가 만드는 «갱신 완료» 표지. `{"status": "ready"}` 한 행
- ctx_weather:    ctx_weather_month·ctx_weather_window에서 작업기의 weather_context 모양으로 변환
"""
import shutil
import sqlite3
import sys
from pathlib import Path

V16 = Path(__file__).resolve().parents[2] / 'agents' / 'regional_v16'
sys.path.insert(0, str(V16))
from data_pipeline import db1_compat  # noqa: E402

source, target = Path(sys.argv[1]), Path(sys.argv[2])
snapshot = target / 'snapshots' / 'db1-real.sqlite'
work = target / 'work' / 'db1-work.sqlite'
snapshot.parent.mkdir(parents=True, exist_ok=True)
work.parent.mkdir(parents=True, exist_ok=True)

shutil.copyfile(source, snapshot)
with sqlite3.connect(snapshot) as con:
    con.executescript('''
        CREATE TABLE IF NOT EXISTS pipeline_state(id INTEGER PRIMARY KEY CHECK(id=1), payload_json TEXT NOT NULL);
        INSERT OR REPLACE INTO pipeline_state VALUES(1, '{"status": "ready"}');
        CREATE TABLE IF NOT EXISTS ctx_weather(date TEXT PRIMARY KEY, payload_json TEXT NOT NULL);
    ''')
    rows = db1_compat.weather_rows(con) or []
    con.executemany('INSERT OR REPLACE INTO ctx_weather VALUES(?,?)', rows)
shutil.copyfile(snapshot, work)
print('준비 완료:', snapshot, work, f'(ctx_weather {len(rows)}행)')
