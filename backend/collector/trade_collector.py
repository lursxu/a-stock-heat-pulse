import logging
import requests
import pandas as pd
from db import get_conn

log = logging.getLogger(__name__)

QT_URL = "https://qt.gtimg.cn/q="


def _build_symbol(code: str) -> str:
    if code.startswith("6") or code.startswith("9"):
        return f"sh{code}"
    return f"sz{code}"


def _parse_line(line: str) -> dict | None:
    """Parse one Tencent quote line: v_sh600519="1~name~code~price~..."."""
    line = line.strip().rstrip(";")
    if "=" not in line or '~' not in line:
        return None
    raw = line.split("=", 1)[1].strip('"')
    p = raw.split("~")
    if len(p) < 50:
        return None
    try:
        return {
            "code": p[2],
            "name": p[1],
            "price": float(p[3]) if p[3] else 0,
            "change_pct": float(p[32]) if p[32] else 0,
            "volume": float(p[6]) if p[6] else 0,       # 成交量(手)
            "amount": float(p[37]) if p[37] else 0,      # 成交额(万)
            "turnover_rate": float(p[38]) if p[38] else 0,  # 换手率
            "volume_ratio": float(p[49]) if p[49] else 0,   # 量比
        }
    except (ValueError, IndexError):
        return None


def _fetch_batch(symbols: list[str]) -> list[dict]:
    try:
        r = requests.get(QT_URL + ",".join(symbols), timeout=15)
        results = []
        for line in r.text.split(";"):
            d = _parse_line(line)
            if d and d["price"] > 0:
                results.append(d)
        return results
    except Exception as e:
        log.warning("Tencent batch fetch failed: %s", e)
        return []


def collect() -> pd.DataFrame:
    """Fetch all A-share quotes from Tencent and store snapshot."""
    with get_conn() as conn:
        rows = conn.execute("SELECT code FROM stock_basic").fetchall()
    codes = [r["code"] for r in rows]

    if not codes:
        log.warning("No stocks in stock_basic, run sync_basic first")
        return pd.DataFrame()

    all_rows = []
    batch_size = 50
    for i in range(0, len(codes), batch_size):
        batch = [_build_symbol(c) for c in codes[i:i + batch_size]]
        all_rows.extend(_fetch_batch(batch))

    if not all_rows:
        log.warning("No trade data fetched")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO trade_snapshots(code,name,price,change_pct,volume,amount,turnover_rate,volume_ratio) "
            "VALUES(:code,:name,:price,:change_pct,:volume,:amount,:turnover_rate,:volume_ratio)",
            all_rows,
        )
    log.info("Collected %d trade records from Tencent", len(all_rows))
    return df
