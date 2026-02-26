import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from apscheduler.schedulers.background import BackgroundScheduler

import config
from db import init_db, cleanup_old_data
from collector import trade_collector, guba_collector, xueqiu_collector
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


@asynccontextmanager
async def lifespan(application):
    config.load()
    init_db()
    interval = config.get()["scanner"]["interval_minutes"]
    scheduler.add_job(run_scan, "interval", minutes=interval, id="scan", replace_existing=True)
    retention = config.get()["data"]["retention_days"]
    scheduler.add_job(lambda: cleanup_old_data(retention), "cron", hour=3, id="cleanup", replace_existing=True)
    scheduler.start()
    log.info("Scheduler started, interval=%d min", interval)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="A-Stock Heat Pulse", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(router)
app.add_api_websocket_route("/ws", ws_endpoint)

# Serve frontend static files if built
_static = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(_static):
    app.mount("/", StaticFiles(directory=_static, html=True), name="static")


def run_scan():
    """Execute one full scan cycle."""
    try:
        cfg = config.get()
        log.info("=== Scan cycle start ===")

        # 1. Collect trade data
        trade_df = trade_collector.collect()
        if trade_df.empty:
            log.warning("No trade data, skipping cycle")
            return

        # 2. Pre-filter top N by volume_ratio for sentiment collection
        top_n = cfg["scanner"]["top_n_for_sentiment"]
        top_codes = (
            trade_df.nlargest(top_n, "volume_ratio")["code"].tolist()
            if "volume_ratio" in trade_df.columns
            else []
        )

        # 3. Collect sentiment (with graceful degradation)
        try:
            guba_collector.collect(top_codes)
        except Exception as e:
            log.warning("Guba collection failed, degrading: %s", e)
        try:
            xueqiu_collector.collect(top_codes)
        except Exception as e:
            log.warning("Xueqiu collection failed, degrading: %s", e)

        # 4. Calculate heat scores
        heat_df = heat_calculator.calculate(trade_df)

        # 5. Detect anomalies
        anomalies = anomaly_detector.detect(heat_df)

        # 6. Send alerts
        webhook.notify(anomalies)

        # 7. Broadcast to websocket clients
        top_items = heat_df.nlargest(50, "total_heat")[
            ["code", "name", "total_heat", "trade_heat", "sentiment_heat", "change_pct", "volume_ratio"]
        ].to_dict("records")

        loop = asyncio.new_event_loop()
        loop.run_until_complete(broadcast({
            "type": "update",
            "ranking": top_items,
            "anomalies": anomalies[:10],
        }))
        loop.close()

        log.info("=== Scan cycle done, %d anomalies ===", len(anomalies))
    except Exception as e:
        log.exception("Scan cycle error: %s", e)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
