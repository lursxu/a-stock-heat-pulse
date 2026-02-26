import logging
import requests
from db import get_conn

log = logging.getLogger(__name__)

SINA_URL = "https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData"


def sync():
    """Sync all A-share stock basic info from Sina."""
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})

    all_rows = []
    for page in range(1, 80):
        try:
            r = session.get(SINA_URL, params={
                "page": page, "num": 80, "sort": "symbol", "asc": 1, "node": "hs_a",
            }, timeout=15)
            data = r.json() if r.status_code == 200 else []
        except Exception:
            data = []
        if not data:
            break
        for item in data:
            code = item.get("code", "")
            all_rows.append({
                "code": code,
                "name": item.get("name", ""),
                "market": "SH" if code.startswith("6") else "SZ",
            })

    if not all_rows:
        log.warning("No stock basic data fetched")
        return 0

    with get_conn() as conn:
        conn.execute("DELETE FROM stock_basic")
        conn.executemany(
            "INSERT INTO stock_basic(code, name, market) VALUES(:code, :name, :market)",
            all_rows,
        )
    log.info("Synced %d stocks to stock_basic", len(all_rows))
    return len(all_rows)
