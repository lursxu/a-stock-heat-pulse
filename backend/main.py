import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from apscheduler.schedulers.background import BackgroundScheduler

import config
from db import init_db, cleanup_old_data, get_conn
from collector import basic_collector, trade_collector, guba_collector, xueqiu_collector
from engine import heat_calculator, anomaly_detector
from notifier import webhook
from api.routes import router
from api.ws import ws_endpoint, broadcast_sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger(__name__)

scheduler = BackgroundScheduler()

# Track running jobs
_running_jobs: dict[str, dict] = {}


def _log_job(name, func):
    t0 = time.time()
    _running_jobs[name] = {"status": "running", "started_at": time.strftime("%H:%M:%S"), "progress": ""}
    broadcast_sync({"type": "job_status", "jobs": _running_jobs})
    try:
        result = func()
        dur = time.time() - t0
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO job_logs(job_name,status,message,duration_sec) VALUES(?,?,?,?)",
                (name, "ok", str(result)[:200], round(dur, 2)),
            )
        _running_jobs.pop(name, None)
        broadcast_sync({"type": "job_done", "job": name, "status": "ok", "duration": round(dur, 1), "message": str(result)[:200], "jobs": _running_jobs})
        log.info("Job [%s] ok in %.1fs", name, dur)
        return result
    except Exception as e:
        dur = time.time() - t0
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO job_logs(job_name,status,message,duration_sec) VALUES(?,?,?,?)",
                (name, "error", str(e)[:200], round(dur, 2)),
            )
        _running_jobs.pop(name, None)
        broadcast_sync({"type": "job_done", "job": name, "status": "error", "duration": round(dur, 1), "message": str(e)[:100], "jobs": _running_jobs})
        log.exception("Job [%s] failed in %.1fs: %s", name, dur, e)
        return None


def job_sync_basic():
    return _log_job("sync_basic", basic_collector.sync)

def job_collect_trade():
    return _log_job("collect_trade", trade_collector.collect)

def job_collect_sentiment():
    def _do():
        cfg = config.get()
        top_n = cfg["scanner"]["top_n_for_sentiment"]
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT code FROM heat_scores WHERE ts=(SELECT MAX(ts) FROM heat_scores) ORDER BY trade_heat DESC LIMIT ?", (top_n,)
            ).fetchall()
        codes = [r["code"] for r in rows]
        if not codes:
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT code FROM trade_snapshots WHERE ts=(SELECT MAX(ts) FROM trade_snapshots) ORDER BY volume_ratio DESC LIMIT ?", (top_n,)
                ).fetchall()
            codes = [r["code"] for r in rows]
        if not codes:
            return "no codes"
        guba_collector.collect(codes[:100])
        xueqiu_collector.collect(codes[:100])
        return f"sentiment for {len(codes[:100])} stocks"
    return _log_job("collect_sentiment", _do)

def job_calc_heat():
    def _do():
        with get_conn() as conn:
            latest_ts = conn.execute("SELECT MAX(ts) as ts FROM trade_snapshots").fetchone()["ts"]
            if not latest_ts:
                return "no trade data"
            rows = conn.execute(
                "SELECT code,name,price,change_pct,volume,amount,turnover_rate,volume_ratio FROM trade_snapshots WHERE ts=?", (latest_ts,)
            ).fetchall()
        if not rows:
            return "no trade data"
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        heat_df = heat_calculator.calculate(df)
        return f"heat for {len(heat_df)} stocks"
    return _log_job("calc_heat", _do)

def job_detect_anomaly():
    def _do():
        with get_conn() as conn:
            latest_ts = conn.execute("SELECT MAX(ts) as ts FROM heat_scores").fetchone()["ts"]
            if not latest_ts:
                return "no heat data"
            rows = conn.execute(
                "SELECT h.code, h.name, h.total_heat, h.trade_heat, h.sentiment_heat, "
                "t.change_pct, t.volume_ratio "
                "FROM heat_scores h LEFT JOIN trade_snapshots t ON h.code=t.code "
                "AND t.ts=(SELECT MAX(ts) FROM trade_snapshots) WHERE h.ts=?", (latest_ts,)
            ).fetchall()
        if not rows:
            return "no data"
        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        anomalies = anomaly_detector.detect(df)
        webhook.notify(anomalies)

        top_items = df.nlargest(50, "total_heat")[
            ["code", "name", "total_heat", "trade_heat", "sentiment_heat", "change_pct", "volume_ratio"]
        ].to_dict("records")
        broadcast_sync({"type": "update", "ranking": top_items, "anomalies": anomalies[:20]})
        return f"{len(anomalies)} anomalies"
    return _log_job("detect_anomaly", _do)

def job_cleanup():
    retention = config.get()["data"]["retention_days"]
    return _log_job("cleanup", lambda: cleanup_old_data(retention))

def run_scan():
    log.info("=== Scan cycle start ===")
    _running_jobs["full_scan"] = {"status": "running", "started_at": time.strftime("%H:%M:%S"), "progress": ""}
    steps = [
        ("collect_trade", job_collect_trade),
        ("calc_heat", job_calc_heat),
        ("collect_sentiment", job_collect_sentiment),
        ("calc_heat_2", job_calc_heat),
        ("detect_anomaly", job_detect_anomaly),
    ]
    for i, (step_name, fn) in enumerate(steps):
        _running_jobs["full_scan"]["progress"] = f"{i+1}/{len(steps)} {step_name}"
        broadcast_sync({"type": "job_status", "jobs": _running_jobs})
        fn()
    _running_jobs.pop("full_scan", None)
    broadcast_sync({"type": "job_done", "job": "full_scan", "status": "ok", "jobs": _running_jobs})
    log.info("=== Scan cycle done ===")


def get_running_jobs():
    return dict(_running_jobs)


@asynccontextmanager
async def lifespan(application):
    config.load()
    init_db()
    cfg = config.get()
    interval = cfg["scanner"]["interval_minutes"]
    scheduler.add_job(job_sync_basic, "cron", hour=9, minute=0, id="sync_basic", replace_existing=True)
    scheduler.add_job(run_scan, "cron", minute=f"*/{interval}", hour="9-15", id="full_scan", replace_existing=True)
    scheduler.add_job(job_cleanup, "cron", hour=3, id="cleanup", replace_existing=True)
    scheduler.start()
    log.info("Scheduler started, scan interval=%d min", interval)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="A-Stock Heat Pulse", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.add_api_websocket_route("/ws", ws_endpoint)

_static = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_static):
    app.mount("/assets", StaticFiles(directory=os.path.join(_static, "assets")), name="assets")
    _index = os.path.join(_static, "index.html")

    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        return FileResponse(_index)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
