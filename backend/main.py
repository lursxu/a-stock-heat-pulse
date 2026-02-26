import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager

# Remove proxy for this process - Chinese financial APIs don't need proxy
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
from api.ws import ws_endpoint, broadcast

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def _log_job(name, func):
    """Run a job function and log result to job_logs table."""
    t0 = time.time()
    try:
        result = func()
        dur = time.time() - t0
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO job_logs(job_name,status,message,duration_sec) VALUES(?,?,?,?)",
                (name, "ok", str(result)[:200], round(dur, 2)),
            )
        log.info("Job [%s] ok in %.1fs", name, dur)
        return result
    except Exception as e:
        dur = time.time() - t0
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO job_logs(job_name,status,message,duration_sec) VALUES(?,?,?,?)",
                (name, "error", str(e)[:200], round(dur, 2)),
            )
        log.exception("Job [%s] failed in %.1fs: %s", name, dur, e)
        return None


# ── Individual Jobs ──────────────────────────────────────────

def job_sync_basic():
    """同步A股基础数据（股票列表）"""
    return _log_job("sync_basic", basic_collector.sync)


def job_collect_trade():
    """采集实时交易行情"""
    return _log_job("collect_trade", trade_collector.collect)


def job_collect_sentiment():
    """采集舆情数据（仅对交易热度Top N股票）"""
    def _do():
        cfg = config.get()
        top_n = cfg["scanner"]["top_n_for_sentiment"]
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT code FROM heat_scores WHERE ts=(SELECT MAX(ts) FROM heat_scores) "
                "ORDER BY trade_heat DESC LIMIT ?", (top_n,)
            ).fetchall()
        codes = [r["code"] for r in rows]
        if not codes:
            # Fallback: use trade_snapshots
            with get_conn() as conn:
                rows = conn.execute(
                    "SELECT code FROM trade_snapshots WHERE ts=(SELECT MAX(ts) FROM trade_snapshots) "
                    "ORDER BY volume_ratio DESC LIMIT ?", (top_n,)
                ).fetchall()
            codes = [r["code"] for r in rows]
        if not codes:
            return "no codes to collect"
        guba_collector.collect(codes[:100])
        xueqiu_collector.collect(codes[:100])
        return f"collected sentiment for {len(codes[:100])} stocks"
    return _log_job("collect_sentiment", _do)


def job_calc_heat():
    """计算热度分"""
    def _do():
        # Get latest trade snapshot
        with get_conn() as conn:
            latest_ts = conn.execute("SELECT MAX(ts) as ts FROM trade_snapshots").fetchone()["ts"]
            if not latest_ts:
                return "no trade data"
            rows = conn.execute(
                "SELECT code,name,price,change_pct,volume,amount,turnover_rate,volume_ratio "
                "FROM trade_snapshots WHERE ts=?", (latest_ts,)
            ).fetchall()

        if not rows:
            return "no trade data"

        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        heat_df = heat_calculator.calculate(df)
        return f"calculated heat for {len(heat_df)} stocks"
    return _log_job("calc_heat", _do)


def job_detect_anomaly():
    """异常检测 + 告警推送"""
    def _do():
        with get_conn() as conn:
            latest_ts = conn.execute("SELECT MAX(ts) as ts FROM heat_scores").fetchone()["ts"]
            if not latest_ts:
                return "no heat data"
            rows = conn.execute(
                "SELECT h.code, h.name, h.total_heat, h.trade_heat, h.sentiment_heat, "
                "t.change_pct, t.volume_ratio "
                "FROM heat_scores h LEFT JOIN trade_snapshots t ON h.code=t.code "
                "AND t.ts=(SELECT MAX(ts) FROM trade_snapshots) "
                "WHERE h.ts=?", (latest_ts,)
            ).fetchall()

        if not rows:
            return "no data"

        import pandas as pd
        df = pd.DataFrame([dict(r) for r in rows])
        anomalies = anomaly_detector.detect(df)
        webhook.notify(anomalies)

        # Broadcast to websocket
        top_items = df.nlargest(50, "total_heat")[
            ["code", "name", "total_heat", "trade_heat", "sentiment_heat", "change_pct", "volume_ratio"]
        ].to_dict("records")

        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(broadcast({
                "type": "update",
                "ranking": top_items,
                "anomalies": anomalies[:10],
            }))
            loop.close()
        except Exception:
            pass

        return f"{len(anomalies)} anomalies"
    return _log_job("detect_anomaly", _do)


def job_cleanup():
    """清理过期数据"""
    retention = config.get()["data"]["retention_days"]
    return _log_job("cleanup", lambda: cleanup_old_data(retention))


# ── Full scan (chains the jobs) ─────────────────────────────

def run_scan():
    """Execute one full scan cycle: trade -> heat -> sentiment -> detect."""
    log.info("=== Scan cycle start ===")
    job_collect_trade()
    job_calc_heat()
    job_collect_sentiment()
    # Recalc with sentiment
    job_calc_heat()
    job_detect_anomaly()
    log.info("=== Scan cycle done ===")


# ── App lifecycle ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(application):
    config.load()
    init_db()
    cfg = config.get()
    interval = cfg["scanner"]["interval_minutes"]

    # Individual scheduled jobs
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
        # Serve index.html for all non-API routes (SPA history mode)
        return FileResponse(_index)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
