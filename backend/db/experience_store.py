"""지역 협업 기록(검토·후속 조치). 기존 업무/보고서를 변경하지 않습니다."""
import json
from datetime import date

from sqlalchemy import text

from backend.db.mission_store import timestamp
from backend.db.work_store import lock, transaction


def scope(context):
    user = context['user']
    # 기록은 같은 지역 담당자가 함께 봅니다. 'team'은 기존 저장 기록과 같은 키를 유지하기 위한 값입니다.
    return json.dumps(['team', context['city'], context['district'], context['month']], ensure_ascii=False)


def load(context):
    with transaction() as db:
        row = db.execute(text('SELECT value FROM work.experience WHERE key=:key'), {'key': scope(context)}).fetchone()
        return json.loads(row[0]) if row else {'version': 0, 'checks': {}, 'history': []}


def regional_history(context):
    namespace, city, district, _ = json.loads(scope(context))
    with transaction() as db:
        items = []
        for key, value in db.execute(text('SELECT key,value FROM work.experience')):
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
    key = scope(context)
    with transaction() as db:
        lock(db, key)
        row = db.execute(text('SELECT value FROM work.experience WHERE key=:key'), {'key': key}).fetchone()
        old = json.loads(row[0]) if row else {'version': 0, 'history': []}
        if body.get('version') != old['version']:
            raise ValueError('다른 담당자가 기록을 변경했습니다. 최신 기록을 불러온 뒤 다시 저장하세요.')
        event = fields | {'actor': context['user']['id'], 'at': timestamp()}
        result = fields | {'version': old['version'] + 1, 'history': old['history'] + [event]}
        db.execute(text('INSERT INTO work.experience (key,value) VALUES (:key,:value) '
                        'ON CONFLICT (key) DO UPDATE SET value=excluded.value'),
                   {'key': key, 'value': json.dumps(result, ensure_ascii=False)})
        return result
