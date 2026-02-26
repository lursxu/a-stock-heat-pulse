import logging
import requests
import pandas as pd
from db import get_conn

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0"})

SINA_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


def _fetch_page(page: int, num: int = 80) -> list[dict]:
    try:
        r = _SESSION.get(SINA_URL, params={
            "page": page, "num": num, "sort": "changepercent", "asc": 0, "node": "hs_a",
        }, timeout=15)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        log.debug("Sina page %d failed: %s", page, e)
        return []


def collect() -> pd.DataFrame:
    """Fetch all A-share quotes from Sina finance and store snapshot."""
    all_rows = []
    for page in range(1, 80):  # ~5000 stocks / 80 per page
        data = _fetch_page(page)
        if not data:
            break
        for item in data:
            all_rows.append({
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "price": float(item.get("trade", 0) or 0),
                "change_pct": float(item.get("changepercent", 0) or 0),
                "volume": float(item.get("volume", 0) or 0),
                "amount": float(item.get("amount", 0) or 0),
                "turnover_rate": float(item.get("turnover", 0) or 0) if "turnover" in item else 0,
                "volume_ratio": float(item.get("volume_ratio", 0) or 0) if "volume_ratio" in item else 0,
            })

    if not all_rows:
        log.warning("No trade data fetched")
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)

    # Compute volume_ratio from volume if not provided: volume / avg_volume approximation
    # For now just use raw data, volume_ratio will be 0 for sina source

    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO trade_snapshots(code,name,price,change_pct,volume,amount,turnover_rate,volume_ratio) "
            "VALUES(:code,:name,:price,:change_pct,:volume,:amount,:turnover_rate,:volume_ratio)",
            all_rows,
        )
    log.info("Collected %d trade records from Sina", len(all_rows))
    return df
