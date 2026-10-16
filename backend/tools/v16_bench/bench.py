"""실제 db1.sqlite로 v16 성능 측정. 인자: <old|pg> <db 경로> <출력 json> [반복 수]

old = 원본 backend_old(SQLite), pg = backend(PostgreSQL: 같은 db를 pgserver에 게시). backend의 SQLite 서빙은 제거되어 측정 대상이 아닙니다. 질문마다 저장소를 새로 만듭니다(웹 서비스가 요청마다 만드는 것과 같음).
엔진 계층(execute)과 챗봇 답변 전체(v16 reply) 두 수준을 잽니다. 결과 내용의 해시도 함께 남겨 두 구현의 출력을 비교합니다.
"""
import collections
import dataclasses
import hashlib
import json
import os
import sqlite3
import statistics
import sys
import time
import tracemalloc
from pathlib import Path
from unittest.mock import patch

label, db, out = sys.argv[1], Path(sys.argv[2]).resolve(), Path(sys.argv[3])
runs = int(sys.argv[4]) if len(sys.argv) > 4 else 9
project = Path(__file__).resolve().parents[3]  # 프로젝트 루트(Team_Together)
engine_root = project / ('backend_old' if label == 'old' else 'backend') / 'agents' / 'regional_v16'
PG = label == 'pg'
sys.path.insert(0, str(project))
sys.path.insert(0, str(engine_root))
os.environ['DB1_DATABASE_PATH'] = str(db)

# ── DB 호출 횟수 계측 ───────────────────────────────────────────────
stats = collections.Counter()
_real_connect = sqlite3.connect


class _Counted:
    def __init__(self, inner):
        self._inner = inner

    def execute(self, sql, *args):
        stats['queries'] += 1
        return self._inner.execute(sql, *args)

    def close(self):
        return self._inner.close()

    def __enter__(self):
        self._inner.__enter__()
        return self

    def __exit__(self, *exc):
        return self._inner.__exit__(*exc)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _counting_connect(*args, **kwargs):
    stats['connections'] += 1
    return _Counted(_real_connect(*args, **kwargs))


sqlite3.connect = _counting_connect

# ── 실제 자료에서 질문 재료 고르기(두 구현이 같은 질문을 받도록) ────────────
with _real_connect(db.as_uri() + '?mode=ro', uri=True) as meta:
    names = [r[0] for r in meta.execute('SELECT DISTINCT adm_nm FROM a1_context ORDER BY adm_nm')]
    signal_dong, signal_month = None, None
    for date, payload in meta.execute('SELECT date,result_json FROM a2_detection ORDER BY date'):
        row = json.loads(payload)
        if row.get('any_signal'):
            signal_dong, signal_month = row['행정동'], date[:7]
            break
signal_dong = signal_dong or names[0]
signal_month = signal_month or '2025-09'
other = [n for n in names if n != signal_dong][:2]
BANDS = ('20s', '30s', '40s', '50s', '60plus')

from chatbot_agent.query_service import execute  # noqa: E402
from chatbot_agent.schemas import QueryIntent  # noqa: E402

if not PG:
    from chatbot_agent.repository import DataRepository  # noqa: E402  (원본 backend_old의 SQLite 저장소)
else:
    import tempfile
    import pgserver
    import sqlalchemy
    from chatbot_agent.pg_repository import PostgresDb1Repository
    from data_pipeline.publish_postgres import publish
    _server = pgserver.get_server(tempfile.mkdtemp(prefix='pgreal_'), cleanup_mode='stop')
    PG_ENGINE = sqlalchemy.create_engine(_server.get_uri().replace('postgresql://', 'postgresql+psycopg2://', 1))
    _t = time.perf_counter()
    _published = publish(db, PG_ENGINE)
    print('PUBLISH', {k: v for k, v in _published.items() if k != 'tables'}, round(time.perf_counter() - _t, 2), 's', file=sys.stderr)
    print('PUBLISH rows', _published['tables'], file=sys.stderr)

Q = QueryIntent
ENGINE_CASES = {
    '신호 목록 (2025-07~12)': Q('find_region', 'signals', start_month='2025-07', end_month='2025-12'),
    '신호 목록 (연령 60+)': Q('find_region', 'signals', start_month='2025-07', end_month='2025-12', age_band='60plus'),
    '동 변화 이유': Q('track_change', 'reason', dong=signal_dong, dongs=(signal_dong,), start_month=signal_month, end_month=signal_month),
    '동 활동 추이 (6개월)': Q('track_change', 'activity', dong=signal_dong, dongs=(signal_dong,), start_month='2025-07', end_month='2025-12'),
    '연령별 변화 (5개 연령)': Q('track_change', 'age_activity', dong=signal_dong, dongs=(signal_dong,), start_month=signal_month, end_month=signal_month, age_bands=BANDS),
    '지역 유형': Q('plan_review', 'context', dong=other[0], dongs=(other[0],), start_month='2025-12', end_month='2025-12'),
    '지역 배경 (보조 자료)': Q('plan_review', 'support', dong=signal_dong, dongs=(signal_dong,), start_month=signal_month, end_month=signal_month),
    '소비 (2개 동·6개월)': Q('plan_review', 'consumption', dong=other[0], dongs=tuple(other), start_month='2025-07', end_month='2025-12'),
    '소비 (연령 20대)': Q('plan_review', 'consumption', dong=other[0], dongs=(other[0],), start_month='2025-07', end_month='2025-12', age_band='20s'),
    '이례적 변화 순위': Q('track_change', 'anomaly', start_month='2025-07', end_month='2025-12', metric='weekday_move_count'),
    '직전 월 신호 여부': Q('track_change', 'previous', dong=signal_dong, dongs=(signal_dong,), start_month=signal_month, end_month=signal_month),
}
QUESTIONS = {
    '2025년 하반기 이상신호 탐지 지역': '2025년 하반기 이상신호 탐지 지역 알려줘',
    f'{signal_dong} 신호 이유': f'{signal_dong}은 왜 신호가 났어?',
    f'{signal_dong} 지역 배경': f'{signal_dong} 지역 배경 정보 보여줘',
    f'{signal_dong} 연령대별 변화': f'{signal_dong} 연령대별 변화는?',
    f'{other[0]} 소비 변화': f'{other[0]} 소비 변화는?',
    '이상신호 판정 기준': '이상신호 판정 기준은?',
    f'{other[0]} 지역 유형': f'{other[0]} 지역 유형은?',
}
CONTEXT = {'city': '강남구', 'district': '', 'month': '2025-12'}


def fingerprint(value):
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


def measure(call):
    """call()을 워밍업 2회 + runs회 재고, DB 호출 수·메모리 정점·출력 해시를 남깁니다."""
    error = None
    for _ in range(2):
        try:
            result = call()
        except Exception as exc:  # 예외도 동작의 일부(두 구현을 비교)
            error, result = f'{type(exc).__name__}: {str(exc)[:80]}', None
    times = []
    for _ in range(runs):
        started = time.perf_counter()
        try:
            call()
        except Exception:
            pass
        times.append((time.perf_counter() - started) * 1000)
    stats.clear()
    try:
        result = call()
    except Exception:
        pass
    counts = dict(stats)
    tracemalloc.start()
    try:
        call()
    except Exception:
        pass
    peak = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()
    return {'median_ms': statistics.median(times), 'min_ms': min(times), 'max_ms': max(times),
            'connections': counts.get('connections', 0), 'queries': counts.get('queries', 0),
            'peak_mb': peak, 'hash': fingerprint(result if error is None else error), 'error': error}


def engine_call(intent):
    def call():
        repo = PostgresDb1Repository(PG_ENGINE) if PG else DataRepository(engine_root, db=db)
        try:
            return dataclasses.asdict(execute(repo, intent))
        finally:
            if hasattr(repo, 'close'):
                repo.close()
    return call


def reply_call(question):
    if label == 'old':
        from backend.agents import v16_service as service
        from backend.chatbot import ai_settings
        from backend.chatbot.welfare.app.llm import client  # noqa: F401
    else:
        from backend.bomi.adapters import v16 as service
        from backend.chatbot import ai_settings

    def call():
        extra = (patch.object(service, '_engine', return_value=PG_ENGINE),) if PG else ()
        for patcher in extra:
            patcher.start()
        try:
            with patch.object(ai_settings, 'current', return_value=ai_settings.AIConfig(False, 'openai', 'm', '', '')):
                return service.reply(question, [], CONTEXT, use_ai=False)
        finally:
            for patcher in reversed(extra):
                patcher.stop()
    return call


report = {'label': label, 'db': str(db), 'runs': runs, 'dong': signal_dong, 'month': signal_month, 'engine': {}, 'reply': {}}
for name, intent in ENGINE_CASES.items():
    report['engine'][name] = measure(engine_call(intent))
    print(f"[{label}] engine {name}: {report['engine'][name]['median_ms']:.1f} ms", file=sys.stderr)
for name, question in QUESTIONS.items():
    report['reply'][name] = measure(reply_call(question))
    print(f"[{label}] reply  {name}: {report['reply'][name]['median_ms']:.1f} ms", file=sys.stderr)
out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
