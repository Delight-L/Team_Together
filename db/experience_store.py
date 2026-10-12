"""지역 협업 기록과 체험 피드백. 기존 업무/보고서를 변경하지 않습니다."""
import json
import sqlite3
from datetime import date
from db.mission_store import connection, timestamp


def scope(context):
    user = context['user']
    return json.dumps([user['id'] if user.get('trial') else 'team',
                       context['city'], context['district'], context['month']], ensure_ascii=False)


def load(context):
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS experience (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        row = db.execute('SELECT value FROM experience WHERE key=?', (scope(context),)).fetchone()
        return json.loads(row[0]) if row else {'version': 0, 'checks': {}, 'history': []}


def regional_history(context):
    namespace, city, district, _ = json.loads(scope(context))
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS experience (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        items = []
        for key, value in db.execute('SELECT key,value FROM experience'):
            owner, saved_city, saved_district, month = json.loads(key)
            if (owner, saved_city, saved_district) == (namespace, city, district):
                items.append({'month': month, 'record': json.loads(value)})
        return sorted(items, key=lambda item: item['month'], reverse=True)


def save(context, body):
    fields = {}
    for name, limit in [('assignee', 80), ('note', 2000), ('followup', 2000), ('due', 10)]:
        value = body.get(name, '')
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError('입력 내용의 길이 또는 형식을 확인하세요.')
        fields[name] = value.strip()
    if fields['due']:
        date.fromisoformat(fields['due'])
    checks = body.get('checks', {})
    if not isinstance(checks, dict) or any(k not in {'season', 'event', 'definition', 'source'} or type(v) is not bool for k, v in checks.items()):
        raise ValueError('확인 항목이 유효하지 않습니다.')
    fields['checks'] = checks
    fields['status'] = body.get('status', '확인 예정')
    if fields['status'] not in {'확인 예정', '기관 문의 중', '조치 진행', '후속 확인 완료'}:
        raise ValueError('후속 조치 상태가 유효하지 않습니다.')
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS experience (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT value FROM experience WHERE key=?', (scope(context),)).fetchone()
        old = json.loads(row[0]) if row else {'version': 0, 'history': []}
        if body.get('version') != old['version']:
            raise ValueError('다른 담당자가 기록을 변경했습니다. 최신 기록을 불러온 뒤 다시 저장하세요.')
        event = fields | {'actor': context['user']['id'], 'at': timestamp()}
        result = fields | {'version': old['version'] + 1, 'history': old['history'] + [event]}
        db.execute('INSERT OR REPLACE INTO experience VALUES (?,?)', (scope(context), json.dumps(result, ensure_ascii=False)))
        return result


def feedback(user, body):
    message = body.get('message', '')
    kind = body.get('kind')
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValueError('의견을 1~2,000자로 입력하세요.')
    if kind not in {'이해하기 어려움', '기능 오류', '추가 요구'}:
        raise ValueError('의견 종류를 선택하세요.')
    page = body.get('page', '')
    if not isinstance(page, str) or len(page) > 80:
        raise ValueError('화면 정보가 유효하지 않습니다.')
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS experience_feedback (id INTEGER PRIMARY KEY, actor TEXT, kind TEXT, page TEXT, message TEXT, created_at TEXT)')
        db.execute('INSERT INTO experience_feedback(actor,kind,page,message,created_at) VALUES (?,?,?,?,?)',
                   (user['id'], kind, page, message.strip(), timestamp()))
    return {'saved': True}


def feedback_list():
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS experience_feedback (id INTEGER PRIMARY KEY, actor TEXT, kind TEXT, page TEXT, message TEXT, created_at TEXT)')
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute('SELECT * FROM experience_feedback ORDER BY id DESC LIMIT 200')]
