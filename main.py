"""
MetaMentor AI Workspace — FastAPI Backend
Run: uvicorn main:app --reload --host 0.0.0.0 --port 8000
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.config import settings
from core.database import init_db, get_db
from core.websocket_manager import ws_manager
from api.routes import router as api_router
from services.agent_orchestrator import AgentOrchestrator


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    await init_db()
    yield


app = FastAPI(
    title="MetaMentor AI Workspace",
    description="AI Operating System for Teams",
    version="1.0.0",
    lifespan=lifespan,
)
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {
        "message": "MetaMentor Backend API Running Successfully"
    }
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


# ── WebSocket endpoint ─────────────────────────────────────────────────────────

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            # Handle ping/keepalive
            if msg.get("type") == "ping":
                await ws_manager.send_personal({"type": "pong"}, client_id)
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}
