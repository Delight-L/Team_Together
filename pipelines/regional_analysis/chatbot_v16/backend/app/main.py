import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.chat import router
from backend.app.config import APP_TITLE, CORS_ORIGINS, GEMINI_MODEL, PROJECT_ROOT
from backend.app.session_store import SessionStore
from data_pipeline.runner import run,settings,status

@asynccontextmanager
async def lifespan(app):
    cfg=settings(PROJECT_ROOT)
    await asyncio.to_thread(run,PROJECT_ROOT,initialize_only=not cfg['auto_scan_on_startup'])
    yield

app = FastAPI(title=APP_TITLE,lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.state.session_store = SessionStore(PROJECT_ROOT, GEMINI_MODEL)
app.include_router(router)


@app.get("/api/health")
async def health():
    return {"ok": True, "version": 16, "model": GEMINI_MODEL}

@app.get('/api/data/status')
async def data_status():
    return await asyncio.to_thread(status,settings(PROJECT_ROOT)['database'])

# The included frontend build can be used without installing Node.js.
frontend_dist=PROJECT_ROOT/'frontend/dist'
if frontend_dist.is_dir():
    app.mount('/',StaticFiles(directory=str(frontend_dist),html=True),name='frontend')
