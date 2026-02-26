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
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _clients:
            _clients.remove(ws)


async def broadcast(data: dict):
    msg = json.dumps(data, ensure_ascii=False, default=str)
    for ws in list(_clients):
        try:
            await ws.send_text(msg)
        except Exception:
            if ws in _clients:
                _clients.remove(ws)


def broadcast_sync(data: dict):
    """Sync wrapper for broadcast, safe to call from background threads."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(broadcast(data))
        else:
            loop.run_until_complete(broadcast(data))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        loop.run_until_complete(broadcast(data))
        loop.close()
