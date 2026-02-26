import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from config import get as get_config, update as update_config
from db import get_conn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")
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


# ── System status ────────────────────────────────────────────

@router.get("/status")
async def system_status(_=Depends(_check_auth)):
    from main import scheduler, get_running_jobs
    with get_conn() as conn:
        stock_count = conn.execute("SELECT COUNT(*) as c FROM stock_basic").fetchone()["c"]
        latest_heat_ts = conn.execute("SELECT MAX(ts) as ts FROM heat_scores").fetchone()["ts"]
        latest_trade_ts = conn.execute("SELECT MAX(ts) as ts FROM trade_snapshots").fetchone()["ts"]
        today_anomalies = conn.execute(
            "SELECT COUNT(*) as c FROM alerts WHERE ts >= date('now','localtime')"
        ).fetchone()["c"]
        today_scans = conn.execute(
            "SELECT COUNT(*) as c FROM job_logs WHERE job_name='collect_trade' AND status='ok' AND ts >= date('now','localtime')"
        ).fetchone()["c"]
        # Recent errors
        recent_errors = conn.execute(
            "SELECT job_name, message, ts FROM job_logs WHERE status='error' ORDER BY ts DESC LIMIT 5"
        ).fetchall()

    jobs = scheduler.get_jobs()
    next_scan = None
    for j in jobs:
        if j.id == "full_scan" and j.next_run_time:
            next_scan = str(j.next_run_time)

    return {
        "stock_count": stock_count,
        "latest_heat_ts": latest_heat_ts,
        "latest_trade_ts": latest_trade_ts,
        "today_anomalies": today_anomalies,
        "today_scans": today_scans,
        "next_scan": next_scan,
        "running_jobs": get_running_jobs(),
        "recent_errors": [dict(r) for r in recent_errors],
    }


# ── Heat data ────────────────────────────────────────────────

@router.get("/heat/ranking")
async def heat_ranking(page: int = 1, size: int = 50, sort: str = "total_heat", _=Depends(_check_auth)):
    offset = (page - 1) * size
    allowed_sorts = {"total_heat", "trade_heat", "sentiment_heat", "zscore", "change_pct", "volume_ratio", "amount", "turnover_rate"}
    if sort not in allowed_sorts:
        sort = "total_heat"
    # For columns from trade_snapshots, prefix with t.
    sort_col = f"t.{sort}" if sort in ("change_pct", "volume_ratio", "amount", "turnover_rate") else f"h.{sort}"
    with get_conn() as conn:
        latest = conn.execute("SELECT MAX(ts) as ts FROM heat_scores").fetchone()
        if not latest or not latest["ts"]:
            return {"items": [], "total": 0}
        ts = latest["ts"]
        rows = conn.execute(
            f"SELECT h.code, h.name, h.trade_heat, h.sentiment_heat, h.total_heat, h.zscore, h.ts, "
            f"t.change_pct, t.volume_ratio, t.turnover_rate, t.amount "
            f"FROM heat_scores h LEFT JOIN trade_snapshots t ON h.code=t.code "
            f"AND t.ts=(SELECT MAX(ts) FROM trade_snapshots) "
            f"WHERE h.ts=? ORDER BY {sort_col} DESC LIMIT ? OFFSET ?",
            (ts, size, offset),
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM heat_scores WHERE ts=?", (ts,)).fetchone()["c"]
    return {"items": [dict(r) for r in rows], "total": total, "ts": ts}


@router.get("/heat/trend/{code}")
async def heat_trend(code: str, hours: int = 24, _=Depends(_check_auth)):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT total_heat, trade_heat, sentiment_heat, zscore, ts FROM heat_scores "
            "WHERE code=? AND ts >= datetime('now','localtime',? || ' hours') ORDER BY ts",
            (code, f"-{hours}"),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Alerts ───────────────────────────────────────────────────

@router.get("/alerts")
async def alerts(page: int = 1, size: int = 50, code: str = "", _=Depends(_check_auth)):
    offset = (page - 1) * size
    with get_conn() as conn:
        if code:
            rows = conn.execute(
                "SELECT * FROM alerts WHERE code=? ORDER BY ts DESC LIMIT ? OFFSET ?", (code, size, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) as c FROM alerts WHERE code=?", (code,)).fetchone()["c"]
        else:
            rows = conn.execute("SELECT * FROM alerts ORDER BY ts DESC LIMIT ? OFFSET ?", (size, offset)).fetchall()
            total = conn.execute("SELECT COUNT(*) as c FROM alerts").fetchone()["c"]
    return {"items": [dict(r) for r in rows], "total": total}


@router.get("/alerts/{alert_id}")
async def alert_detail(alert_id: int, _=Depends(_check_auth)):
    with get_conn() as conn:
        alert = conn.execute("SELECT * FROM alerts WHERE id=?", (alert_id,)).fetchone()
        if not alert:
            raise HTTPException(404, "Alert not found")
        alert = dict(alert)
        # Get heat trend around alert time
        trend = conn.execute(
            "SELECT total_heat, trade_heat, sentiment_heat, zscore, ts FROM heat_scores "
            "WHERE code=? AND ts BETWEEN datetime(?, '-2 hours') AND datetime(?, '+1 hours') ORDER BY ts",
            (alert["code"], alert["ts"], alert["ts"]),
        ).fetchall()
    alert["trend"] = [dict(r) for r in trend]
    return alert


# ── Stock basic info ─────────────────────────────────────────

@router.get("/stocks")
async def stock_list(keyword: str = "", _=Depends(_check_auth)):
    with get_conn() as conn:
        if keyword:
            rows = conn.execute(
                "SELECT code, name, market FROM stock_basic WHERE code LIKE ? OR name LIKE ? LIMIT 50",
                (f"%{keyword}%", f"%{keyword}%"),
            ).fetchall()
        else:
            rows = conn.execute("SELECT code, name, market FROM stock_basic LIMIT 50").fetchall()
        total = conn.execute("SELECT COUNT(*) as c FROM stock_basic").fetchone()["c"]
    return {"items": [dict(r) for r in rows], "total": total}


# ── Jobs ─────────────────────────────────────────────────────

@router.get("/jobs")
async def job_list(_=Depends(_check_auth)):
    from main import scheduler, get_running_jobs
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id, "name": job.name or job.id,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    with get_conn() as conn:
        logs = conn.execute(
            "SELECT job_name, status, message, duration_sec, ts FROM job_logs "
            "WHERE id IN (SELECT MAX(id) FROM job_logs GROUP BY job_name) ORDER BY ts DESC"
        ).fetchall()
    return {"jobs": jobs, "logs": [dict(r) for r in logs], "running": get_running_jobs()}


@router.get("/jobs/logs")
async def job_logs(job_name: str = "", page: int = 1, size: int = 50, _=Depends(_check_auth)):
    offset = (page - 1) * size
    with get_conn() as conn:
        if job_name:
            rows = conn.execute(
                "SELECT * FROM job_logs WHERE job_name=? ORDER BY ts DESC LIMIT ? OFFSET ?", (job_name, size, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) as c FROM job_logs WHERE job_name=?", (job_name,)).fetchone()["c"]
        else:
            rows = conn.execute("SELECT * FROM job_logs ORDER BY ts DESC LIMIT ? OFFSET ?", (size, offset)).fetchall()
            total = conn.execute("SELECT COUNT(*) as c FROM job_logs").fetchone()["c"]
    return {"items": [dict(r) for r in rows], "total": total}


@router.post("/jobs/{job_id}/trigger")
async def trigger_job(job_id: str, _=Depends(_check_auth)):
    from main import job_sync_basic, job_collect_trade, job_collect_sentiment, job_calc_heat, job_detect_anomaly, run_scan, _running_jobs
    if job_id in _running_jobs:
        raise HTTPException(409, f"Job {job_id} is already running")
    job_map = {
        "sync_basic": job_sync_basic, "full_scan": run_scan,
        "collect_trade": job_collect_trade, "collect_sentiment": job_collect_sentiment,
        "calc_heat": job_calc_heat, "detect_anomaly": job_detect_anomaly,
    }
    fn = job_map.get(job_id)
    if not fn:
        raise HTTPException(404, f"Job {job_id} not found")
    import asyncio
    asyncio.get_event_loop().run_in_executor(None, fn)
    return {"ok": True, "message": f"Job {job_id} triggered"}


# ── Config ───────────────────────────────────────────────────

@router.get("/config")
async def get_cfg(_=Depends(_check_auth)):
    cfg = get_config()
    safe = {k: v for k, v in cfg.items() if k != "auth"}
    return safe

@router.put("/config")
async def put_cfg(body: dict, _=Depends(_check_auth)):
    body.pop("auth", None)
    update_config(body)
    return {"ok": True}
