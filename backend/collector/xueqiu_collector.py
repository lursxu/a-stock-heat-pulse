"""
同花顺热股排行采集器 (替代雪球，雪球有WAF拦截)
数据源: 10jqka.com.cn 热股排行API
提供: 热度排名、热度值
"""
import logging
import requests
from db import get_conn

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
_SESSION.trust_env = False

_URL = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"


def collect(codes: list[str] = None):
    """Fetch THS hot stock ranking and store as sentiment data."""
    results = []
    try:
        r = _SESSION.get(_URL, params={"stock_type": "a", "type": "hour", "list_type": "normal", "page_size": 100}, timeout=15)
        data = r.json()
        stock_list = data.get("data", {}).get("stock_list", [])
        # Build a map: code -> hot_rank_score
        hot_map = {}
        for i, item in enumerate(stock_list):
            code = item.get("code", "")
            rate = float(item.get("rate", 0) or 0)
            hot_map[code] = {"rank": i + 1, "rate": rate}

        # If codes specified, only store those; otherwise store all
        target_codes = codes if codes else list(hot_map.keys())
        for code in target_codes:
            info = hot_map.get(code)
            if info:
                results.append({
                    "code": code, "source": "ths_hot",
                    "post_count": 100 - info["rank"],  # higher rank = higher score
                    "comment_count": int(info["rate"]),
                })
            # Stocks not in hot list get 0
    except Exception as e:
        log.warning("THS hot fetch failed: %s", e)

    if results:
        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO sentiment_snapshots(code,source,post_count,comment_count) VALUES(:code,:source,:post_count,:comment_count)",
                results,
            )
    log.info("Collected THS hot sentiment for %d stocks", len(results))
    return results
