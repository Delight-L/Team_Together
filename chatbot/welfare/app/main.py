import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from chatbot.welfare.app.agent.orchestrator import handle_chat
from chatbot.welfare.app.config import settings
from chatbot.welfare.app.agent.resources import RESOURCES
from chatbot.welfare.app.schemas import ChatRequest

app = FastAPI(title="복지이음")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health():
    return {"ok": True, "model": settings.openai_model, "key_set": bool(settings.openai_api_key), "mode": "ai" if settings.openai_api_key else "local", "resource_count": len(RESOURCES)}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    async def sse():
        async for event, payload in handle_chat(req.messages):
            yield f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        sse(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
