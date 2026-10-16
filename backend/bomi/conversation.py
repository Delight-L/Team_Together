"""서버 비밀키와 로그인 세션으로 서명한 대화 조건·출처 스냅샷. 클라이언트가 내용을 바꾸면 거절합니다.

질문 전문 이력은 저장하지 않습니다. 개인정보를 가린 검색 문장과 공개 사업 근거 5건만,
최대 24시간 유지합니다. 서버 재시작 후에도 같은 로그인 세션이면 검증할 수 있습니다.
"""
import base64
import hashlib
import hmac
import json
import time
from functools import lru_cache
from datetime import datetime, timezone
from backend.bomi import events as contract

TTL = 24 * 60 * 60
MAX_TOKEN = 600000


@lru_cache(maxsize=1)
def server_secret():
    """브라우저가 아는 세션 토큰만으로 서명하지 않습니다. 서버 전용 키는 공유 DB에 보존합니다."""
    from backend.db.welfare_search_store import snapshot_secret
    return snapshot_secret()


def signing_key(session):
    return hmac.new(server_secret(), str(session).encode(), hashlib.sha256).digest()


def scope(context):
    return {k: context.get(k, "") for k in ("city", "district", "age", "month")}


def pack(state, session):
    if not session:
        raise ValueError("대화 상태를 저장하려면 로그인 세션이 필요합니다.")
    raw = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(raw).decode()
    signature = hmac.new(signing_key(session), body.encode(), hashlib.sha256).hexdigest()
    token = body + "." + signature
    if len(token) > MAX_TOKEN:
        raise ValueError("대화 근거가 너무 큽니다. 사업을 좁혀 다시 질문하세요.")
    return token


def unpack(token, session, context):
    if not token:
        return {}
    if not isinstance(token, str) or len(token) > MAX_TOKEN or not session:
        raise ValueError("대화 상태가 올바르지 않습니다. 새 대화를 시작하세요.")
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(signing_key(session), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError()
        state = json.loads(base64.urlsafe_b64decode(body))
        if state["expires"] < time.time() or state["scope"] != scope(context):
            raise ValueError()
        return state
    except (ValueError, KeyError, TypeError):
        raise ValueError("대화 상태가 만료되었거나 변경되었습니다. 새 대화를 시작하세요.") from None


def snapshot(records):
    result = []
    for record in records[:5]:
        item = {k: v for k, v in record.items() if k not in ("snapshot_hash", "captured_at")}
        canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        item["snapshot_hash"] = hashlib.sha256(canonical.encode()).hexdigest()
        item["captured_at"] = record.get("captured_at") or datetime.now(timezone.utc).isoformat()
        result.append(item)
    return result


def events_with_state(events, state, context, session):
    """sources 이벤트는 서버 검색 결과입니다. 사용자가 보낸 원문 자료는 절대 저장하지 않습니다."""
    try:
        for event, payload in events:
            if event == "sources":
                records = snapshot(payload.get("records") or [])
                state = {"scope": scope(context), "expires": time.time() + TTL,
                    "anchor": payload.get("query", "")[:3000], "records": records,
                    "selected_ids": [r["id"] for r in records]}
                payload = {**payload, "records": records}
                yield contract.conversation(pack(state, session))
            if event == "actions" and state.get("records"):
                actions = []
                for action in payload.get("actions", []):
                    if action.get("reportDraft"):
                        action = {**action, "reportDraft": {**action["reportDraft"], "evidence_token": pack(state, session)}}
                    actions.append(action)
                payload = {**payload, "actions": actions}
            yield event, payload
    finally:
        close = getattr(events, "close", None)
        if close:
            close()
