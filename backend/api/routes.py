import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from config import get as get_config, update as update_config
from db import get_conn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")

# Simple token-based auth
_tokens: set[str] = set()


def _check_auth(request: Request):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token not in _tokens:
        raise HTTPException(401, "Unauthorized")


@router.post("/auth")
async def auth(body: dict):
    pwd = body.get("password", "")
    if pwd == get_config()["auth"]["password"]:
        import secrets
        token = secrets.token_hex(16)
        _tokens.add(token)
        return {"token": token}
    raise HTTPException(403, "Wrong password")


@router.get("/heat/ranking")
async def heat_ranking(page: int = 1, size: int = 50, _=Depends(_check_auth)):
    offset = (page - 1) * size
    with get_conn() as conn:
        # Get latest batch timestamp
        latest = conn.execute("SELECT MAX(ts) as ts FROM heat_scores").fetchone()
        if not latest or not latest["ts"]:
            return {"items": [], "total": 0}
        ts = latest["ts"]
        rows = conn.execute(
            "SELECT code,name,trade_heat,sentiment_heat,total_heat,zscore,ts "
            "FROM heat_scores WHERE ts=? ORDER BY total_heat DESC LIMIT ? OFFSET ?",
            (ts, size, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM heat_scores WHERE ts=?", (ts,)).fetchone()["c"]
    return {"items": [dict(r) for r in rows], "total": total}


@router.get("/heat/trend/{code}")
async def heat_trend(code: str, hours: int = 24, _=Depends(_check_auth)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT total_heat,trade_heat,sentiment_heat,zscore,ts FROM heat_scores "
            "WHERE code=? AND ts >= datetime('now','localtime',? || ' hours') ORDER BY ts",
            (code, f"-{hours}"),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/alerts")
async def alerts(page: int = 1, size: int = 50, _=Depends(_check_auth)):
    offset = (page - 1) * size
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM alerts ORDER BY ts DESC LIMIT ? OFFSET ?", (size, offset)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM alerts").fetchone()["c"]
    return {"items": [dict(r) for r in rows], "total": total}


@router.get("/config")
async def get_cfg(_=Depends(_check_auth)):
    cfg = get_config()
    # Don't expose password
    safe = {k: v for k, v in cfg.items() if k != "auth"}
    return safe


@router.put("/config")
async def put_cfg(body: dict, _=Depends(_check_auth)):
    # Prevent overwriting auth from API
    body.pop("auth", None)
    update_config(body)
    return {"ok": True}


@router.post("/job/trigger")
async def trigger_job(_=Depends(_check_auth)):
    from main import run_scan
    import asyncio
    asyncio.get_event_loop().run_in_executor(None, run_scan)
    return {"ok": True, "message": "Scan triggered"}
