import asyncio
import json
import logging
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)

_clients: list[WebSocket] = []


async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    _clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        pass
    finally:
        _clients.remove(ws)


async def broadcast(data: dict):
    msg = json.dumps(data, ensure_ascii=False, default=str)
    for ws in list(_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            _clients.remove(ws)
