import logging
import akshare as ak
from db import get_conn

log = logging.getLogger(__name__)


def sync():
    """Sync all A-share stock basic info (code, name, industry)."""
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        log.error("Failed to fetch stock list: %s", e)
        return 0

    rows = []
    for _, r in df.iterrows():
        rows.append({
            "code": str(r.get("代码", "")),
            "name": str(r.get("名称", "")),
            "market": "SH" if str(r.get("代码", "")).startswith("6") else "SZ",
        })

    if not rows:
        return 0

    with get_conn() as conn:
        conn.execute("DELETE FROM stock_basic")
        conn.executemany(
            "INSERT INTO stock_basic(code, name, market) VALUES(:code, :name, :market)",
            rows,
        )
    log.info("Synced %d stocks to stock_basic", len(rows))
    return len(rows)
