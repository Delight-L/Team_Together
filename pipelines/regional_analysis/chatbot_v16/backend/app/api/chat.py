from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.app.schemas import ChatRequest, DashboardBriefRequest, ResetRequest
from backend.app.dashboard import build_brief
from chatbot_agent.repository import DataRepository
from data_pipeline.snapshot_manager import active_snapshot
import hashlib

router = APIRouter(prefix="/api")


def _event(name: str, payload: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

@router.post('/dashboard/brief')
async def dashboard_brief(body: DashboardBriefRequest, request: Request):
    from backend.app.config import PROJECT_ROOT
    from data_pipeline.runner import settings
    pointer=active_snapshot(settings(PROJECT_ROOT)['database'])
    if not pointer or body.snapshot_id != pointer['snapshot_id']:
        return {"schema_version": "v16", "selection_revision": body.selection_revision, "snapshot_id": (pointer or {}).get('snapshot_id'), "brief_id": None, "status": "snapshot_changed", "display": {"events": [], "metrics": []}, "narrative": "데이터 공개본이 바뀌었습니다. 대시보드를 새로 조회해 주세요.", "limitations": []}
    # Pin this request to the manifest database that was just validated; do not
    # resolve the active pointer a second time during a concurrent publication.
    try:
        repo=DataRepository(PROJECT_ROOT, db=pointer['database'])
        response=await asyncio.to_thread(build_brief,repo,dong=body.dong,label_month=body.label_month,age_band=body.age_band,snapshot_id=body.snapshot_id,revision=body.selection_revision)
    except (ValueError, FileNotFoundError, OSError) as exc:
        return {"schema_version": "v16", "selection_revision": body.selection_revision, "snapshot_id": body.snapshot_id,
                "brief_id": None, "status": "data_error", "display": {"events": [], "metrics": []},
                "narrative": "선택한 데이터를 지금 읽을 수 없습니다.", "limitations": [str(exc)]}
    digest=hashlib.sha256(body.model_dump_json(exclude={'session_id'}).encode()).hexdigest()
    response=request.app.state.session_store.activate_dashboard(body.session_id,body.selection_revision,digest,response,pointer['database'])
    response.update(schema_version='v16',selection_revision=body.selection_revision,snapshot_id=body.snapshot_id,brief_id=response.get('context_segment_id'))
    return response


@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    store = request.app.state.session_store

    async def stream():
        yield _event("status", {"step": 1, "message": "질문을 확인하고 있습니다."})
        try:
            # pandas/외부 API가 이벤트 루프를 막지 않도록 작업 스레드에서 실행한다.
            result = await asyncio.to_thread(store.get(body.session_id).answer, body.message)
        except Exception:
            yield _event("error", {"message": "답변 처리 중 오류가 발생했습니다. 서버 로그를 확인해 주세요."})
            return

        # 답변 후보는 이미 4단계 검증을 통과했다. UI에는 짧게 나눠 스트리밍한다.
        # The chat bubble displays plain text, not Markdown.  Remove emphasis
        # markers from any template or optional model response before streaming.
        text = result.text.replace("**", "")
        for start in range(0, len(text), 24):
            yield _event("token", {"text": text[start:start + 24]})
            await asyncio.sleep(0)
        if result.follow_ups:
            yield _event("suggestion", {"text": "다음 질문: " + " / ".join(result.follow_ups)})
        yield _event("done", {})

    return StreamingResponse(
        stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/reset")
async def reset(body: ResetRequest, request: Request):
    request.app.state.session_store.reset(body.session_id)
    return {"ok": True}
