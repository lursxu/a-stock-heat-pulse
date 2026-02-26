"""
回填历史数据：腾讯日K接口（不限流）
日K只有 [date, open, close, high, low, volume]
用 volume 和 amplitude 做归一化，足够建立热度基线
"""
import os, sys, time, logging
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY"):
    os.environ.pop(k, None)

sys.path.insert(0, os.path.dirname(__file__))

import requests
import pandas as pd
from db import init_db, get_conn
from engine import anomaly_detector
import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0"})
SESSION.trust_env = False

KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"


def fetch_klines(symbol: str, beg: str, end: str) -> list:
    try:
        r = SESSION.get(KLINE_URL, params={"param": f"{symbol},day,{beg},{end},30,qfq"}, timeout=8)
        data = r.json().get("data", {})
        key = list(data.keys())[0] if data else None
        if not key or key == "market":
            return []
        return data[key].get("qfqday") or data[key].get("day") or []
    except:
        return []


def backfill(days: int = 15):
    config.load()
    init_db()

    with get_conn() as conn:
        stocks = conn.execute("SELECT code, name FROM stock_basic").fetchall()
    stocks = [dict(s) for s in stocks]
    log.info("Backfilling %d stocks, %d days", len(stocks), days)

    # Collect all klines per stock
    all_data = {}  # date -> [records]
    batch = 50
    for i in range(0, len(stocks), batch):
        chunk = stocks[i:i + batch]
        for s in chunk:
            code, name = s["code"], s["name"]
            prefix = "sh" if code.startswith("6") else "sz"
            symbol = f"{prefix}{code}"
            klines = fetch_klines(symbol, "2026-02-10", "2026-02-26")
            for k in klines:
                if len(k) < 6:
                    continue
                dt = k[0]
                o, c, h, l, vol = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
                if c <= 0:
                    continue
                change_pct = (c - o) / o * 100 if o > 0 else 0
                amplitude = (h - l) / l * 100 if l > 0 else 0
                if dt not in all_data:
                    all_data[dt] = []
                all_data[dt].append({
                    "code": code, "name": name,
                    "price": c, "change_pct": round(change_pct, 2),
                    "volume": vol, "amount": vol * c,  # approximate
                    "turnover_rate": amplitude,  # proxy
                    "volume_ratio": amplitude,   # proxy
                })
        done = min(i + batch, len(stocks))
        if done % 500 == 0 or done == len(stocks):
            log.info("Fetched %d/%d (%.0f%%)", done, len(stocks), done / len(stocks) * 100)
        time.sleep(0.05)

    # Sort dates, exclude today
    import datetime
    today = datetime.date.today().strftime("%Y-%m-%d")
    dates = sorted(d for d in all_data if d != today)
    log.info("Trading days: %s", dates)

    for dt in dates:
        records = all_data[dt]
        ts = f"{dt} 15:00:00"

        with get_conn() as conn:
            existing = conn.execute("SELECT COUNT(*) as c FROM trade_snapshots WHERE ts=?", (ts,)).fetchone()["c"]
            if existing > 100:
                log.info("Skip %s (%d existing)", dt, existing)
                continue

            conn.executemany(
                "INSERT INTO trade_snapshots(code,name,price,change_pct,volume,amount,turnover_rate,volume_ratio,ts) "
                "VALUES(:code,:name,:price,:change_pct,:volume,:amount,:turnover_rate,:volume_ratio,:ts)",
                [{**r, "ts": ts} for r in records],
            )

        # Calculate heat
        df = pd.DataFrame(records)
        cfg = config.get()["heat_weights"]

        def _norm(s):
            mn, mx = s.min(), s.max()
            return (s - mn) / (mx - mn) if mx > mn else pd.Series(0.0, index=s.index)

        df["trade_heat"] = (
            _norm(df["volume_ratio"].fillna(0)) * cfg["volume_ratio"]
            + _norm(df["turnover_rate"].fillna(0)) * cfg["turnover_rate"]
            + _norm(df["amount"].fillna(0)) * cfg["amount_change"]
        )
        df["sentiment_heat"] = 0.0
        df["total_heat"] = df["trade_heat"] * cfg["trade"] + df["sentiment_heat"] * cfg["sentiment"]
        df["zscore"] = 0.0

        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO heat_scores(code,name,trade_heat,sentiment_heat,total_heat,zscore,ts) "
                "VALUES(:code,:name,:trade_heat,:sentiment_heat,:total_heat,:zscore,:ts)",
                [{**r, "ts": ts} for r in df[["code", "name", "trade_heat", "sentiment_heat", "total_heat", "zscore"]].to_dict("records")],
            )
        log.info("Backfilled %s: %d stocks", dt, len(records))

    # Recalculate Z-scores on latest data
    log.info("Recalculating Z-scores...")
    with get_conn() as conn:
        latest_ts = conn.execute("SELECT MAX(ts) as ts FROM heat_scores").fetchone()["ts"]
        rows = conn.execute(
            "SELECT h.code, h.name, h.total_heat, h.trade_heat, h.sentiment_heat, "
            "t.change_pct, t.volume_ratio "
            "FROM heat_scores h LEFT JOIN trade_snapshots t ON h.code=t.code "
            "AND t.ts=(SELECT MAX(ts) FROM trade_snapshots) WHERE h.ts=?", (latest_ts,)
        ).fetchall()
    if rows:
        df = pd.DataFrame([dict(r) for r in rows])
        anomalies = anomaly_detector.detect(df)
        log.info("Anomalies with historical baseline: %d", len(anomalies))
        for a in anomalies[:15]:
            atype = a.get("anomaly_type", "zscore")
            log.info("  %s %-8s z=%6.2f heat=%.4f chg=%+.2f%% box_cv=%.3f breakout=%.1f [%s]",
                     a["code"], a["name"], a["zscore"], a["total_heat"],
                     a.get("change_pct", 0), a.get("box_cv", 0), a.get("breakout", 0), atype)

    log.info("Done!")


if __name__ == "__main__":
    backfill(int(sys.argv[1]) if len(sys.argv) > 1 else 15)
