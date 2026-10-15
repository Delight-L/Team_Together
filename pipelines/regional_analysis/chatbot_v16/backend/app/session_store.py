"""세션별 챗봇 인스턴스를 보관하는 간단한 메모리 저장소.

서버 재시작 시 초기화된다. 운영 환경에서는 같은 인터페이스를 Redis 구현으로
교체하면 된다.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from threading import RLock

from chatbot_agent.orchestrator import Chatbot


class SessionStore:
    def __init__(self, project_root: Path, model: str, max_sessions: int = 500):
        self.project_root = project_root
        self.model = model
        self.max_sessions = max_sessions
        self._sessions: OrderedDict[str, Chatbot] = OrderedDict()
        self._lock = RLock()

    def get(self, session_id: str) -> Chatbot:
        with self._lock:
            bot = self._sessions.pop(session_id, None)
            if bot is None:
                bot = Chatbot(self.project_root, model=self.model)
            self._sessions[session_id] = bot
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)
            return bot

    def reset(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def activate_dashboard(self, session_id: str, revision: int, request_hash: str, response: dict,
                           snapshot_database: str) -> dict:
        """Idempotent selection state; error responses never replace a valid segment."""
        with self._lock:
            bot = self.get(session_id)
            current = getattr(bot, "dashboard_state", None)
            if current:
                if revision == current["revision"]:
                    if request_hash != current["request_hash"]:
                        return {"status": "invalid_scope", "narrative": "같은 선택 번호에 다른 조건을 보낼 수 없습니다.", "display": {"events": [], "metrics": []}, "limitations": []}
                    return current["response"]
                if revision < current["revision"]:
                    return {"status": "stale_selection", "narrative": "더 최신 선택 결과가 이미 열려 있습니다.", "display": {"events": [], "metrics": []}, "limitations": []}
            if response["status"] in {"ready", "no_signal", "partial", "not_assessable"}:
                # Rebind before changing the visible selection.  A retained chat
                # session must never answer an S2 dashboard card with its S1 DB.
                with bot._operation_lock:
                    bot.rebind_snapshot(snapshot_database)
                    bot.activate_dashboard_context(response["display"]["scope"], response["context_segment_id"])
                bot.dashboard_state = {"revision": revision, "request_hash": request_hash, "response": response}
            return response
