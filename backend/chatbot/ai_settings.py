"""기관 전체의 외부 AI 설정: 사용 여부(기본 꺼짐), 제공사, 모델, API 키.

- 관리자가 «AI 설정» 화면에서 바꾸며, 공유 PostgreSQL work.app_settings에 저장합니다.
  (배포 서버의 파일은 재시작·재배포 때 지워지므로 파일에 두지 않습니다.)
- 키를 화면에서 넣지 않았으면 .env의 키(OPENAI_API_KEY 등)를 씁니다.
- 키 원문은 화면으로 돌려보내지 않고 끝 4자리만 보여 줍니다.
"""

from dataclasses import dataclass
import copy
import json
import os
import threading
import time

from sqlalchemy import text

from backend.chatbot.welfare.app.config import settings as env_settings
from backend.db import work_store

SETTING_KEY = "ai"
# 질문마다 원격 DB를 다시 읽지 않도록 잠시 기억합니다. 이 서버에서 저장하면 바로 비웁니다.
CACHE_SECONDS = 30
_cache = {"at": 0.0, "value": None}
PROVIDERS = {
    "openai": {"label": "OpenAI", "default_model": "gpt-4o-mini", "env_keys": ["OPENAI_API_KEY"]},
    "anthropic": {
        "label": "Anthropic (Claude)",
        "default_model": "claude-opus-5-5",
        "env_keys": ["ANTHROPIC_API_KEY"],
    },
    "gemini": {
        "label": "Google Gemini",
        "default_model": "gemini-2.5-flash",
        "env_keys": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
    },
}
_lock = threading.Lock()


@dataclass(frozen=True)
class AIConfig:
    enabled: bool
    provider: str
    model: str
    api_key: str
    key_source: str  # '설정 화면', '.env', '' 중 하나

    @property
    def ready(self):
        """외부 AI를 실제로 부를 수 있는 상태인지(사용 켜짐 + 키 있음)."""
        return self.enabled and bool(self.api_key)


def _read(fresh=False):
    now = time.monotonic()
    if not fresh and _cache["value"] is not None and now - _cache["at"] < CACHE_SECONDS:
        return copy.deepcopy(_cache["value"])
    with work_store.transaction() as db:
        row = db.execute(
            text("SELECT value FROM work.app_settings WHERE key=:key"), {"key": SETTING_KEY}
        ).fetchone()
    try:
        saved = json.loads(row[0]) if row else {}
    except json.JSONDecodeError:
        saved = {}
    _cache.update(at=now, value=saved)
    return copy.deepcopy(saved)


def _write(saved):
    with work_store.transaction() as db:
        db.execute(
            text("""INSERT INTO work.app_settings (key,value) VALUES (:key,:value)
            ON CONFLICT (key) DO UPDATE SET value=excluded.value"""),
            {"key": SETTING_KEY, "value": json.dumps(saved, ensure_ascii=False)},
        )
    _cache.update(at=0.0, value=None)


def _env_key(provider):
    if provider == "openai" and env_settings.openai_api_key:
        return env_settings.openai_api_key
    for name in PROVIDERS[provider]["env_keys"]:
        if os.getenv(name):
            return os.getenv(name)
    return ""


def current():
    """지금 적용할 AI 설정입니다. 저장한 적이 없으면 꺼짐 상태의 OpenAI 설정입니다."""
    saved = _read()
    provider = saved.get("provider") if saved.get("provider") in PROVIDERS else "openai"
    model = (saved.get("models") or {}).get(provider) or ""
    if not model:
        model = (
            env_settings.openai_model
            if provider == "openai"
            else PROVIDERS[provider]["default_model"]
        )
    stored_key = (saved.get("keys") or {}).get(provider) or ""
    if stored_key:
        key, source = stored_key, "설정 화면"
    else:
        key = _env_key(provider)
        source = ".env" if key else ""
    return AIConfig(bool(saved.get("enabled", False)), provider, model, key, source)


def openai_key():
    """유해 콘텐츠 검사(OpenAI 무료 API)에 쓸 OpenAI 키입니다. 없으면 빈 문자열입니다."""
    stored = (_read().get("keys") or {}).get("openai") or ""
    return stored or _env_key("openai")


def public_view():
    """관리자 화면에 보여 줄 설정입니다. 키 원문은 넣지 않습니다."""
    config = current()
    saved = _read()
    providers = []
    for provider, info in PROVIDERS.items():
        stored_key = (saved.get("keys") or {}).get(provider) or ""
        key = stored_key or _env_key(provider)
        providers.append(
            {
                "id": provider,
                "label": info["label"],
                "defaultModel": info["default_model"],
                "model": (saved.get("models") or {}).get(provider) or "",
                "hasKey": bool(key),
                "keyHint": ("…" + key[-4:]) if key else "",
                "keySource": "설정 화면" if stored_key else (".env" if key else ""),
            }
        )
    return {
        "enabled": config.enabled,
        "provider": config.provider,
        "model": config.model,
        "ready": config.ready,
        "moderation": bool(openai_key()),
        "providers": providers,
    }


def save(changes):
    """관리자 변경을 저장합니다. apiKey가 비어 있으면 기존 키를 유지하고, clearKey이면 지웁니다."""
    provider = changes.get("provider")
    if provider not in PROVIDERS:
        raise ValueError("AI 제공사를 목록에서 선택하세요.")
    model = str(changes.get("model") or "").strip()
    if len(model) > 100 or any(c.isspace() for c in model):
        raise ValueError("모델 이름은 공백 없이 100자 이내로 입력하세요.")
    api_key = str(changes.get("apiKey") or "").strip()
    if len(api_key) > 300 or any(c.isspace() for c in api_key):
        raise ValueError("API 키 형식이 올바르지 않습니다.")

    with _lock:
        saved = _read(fresh=True)
        saved["enabled"] = bool(changes.get("enabled"))
        saved["provider"] = provider
        saved.setdefault("models", {})[provider] = model
        keys = saved.setdefault("keys", {})
        if changes.get("clearKey"):
            keys.pop(provider, None)
        elif api_key:
            keys[provider] = api_key
        _write(saved)
    return public_view()
