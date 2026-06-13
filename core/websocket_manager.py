"""
WebSocket manager — handles multiple clients and broadcasts.
All agent updates push through here so the frontend gets live events.
"""
import json
from typing import Dict
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active.pop(client_id, None)

    async def send_personal(self, message: dict, client_id: str):
        ws = self.active.get(client_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                self.disconnect(client_id)

    async def broadcast(self, message: dict):
        """Send to all connected clients."""
        dead = []
        for cid, ws in self.active.items():
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.disconnect(cid)

    async def broadcast_event(self, event_type: str, data: dict):
        await self.broadcast({"type": event_type, "data": data})


ws_manager = ConnectionManager()
