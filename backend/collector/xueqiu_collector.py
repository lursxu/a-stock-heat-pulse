import logging, time, random
import requests
from db import get_conn

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
})
_SESSION.trust_env = False


def _ensure_token():
    """Visit xueqiu.com to get cookie token."""
    if not _SESSION.cookies.get("xq_a_token"):
        try:
            _SESSION.get("https://xueqiu.com/", timeout=5)
        except Exception:
            pass


def _fetch_one(code: str) -> dict:
    prefix = "SH" if code.startswith("6") else "SZ"
    symbol = f"{prefix}{code}"
    url = f"https://stock.xueqiu.com/v5/stock/quote.json?symbol={symbol}&extend=detail"
    try:
        _ensure_token()
        resp = _SESSION.get(url, timeout=5)
        data = resp.json().get("data", {}).get("quote", {})
        # Use followers_count and total_shares as proxy for discussion heat
        return {
            "post_count": data.get("followers", 0) or 0,
            "comment_count": data.get("comments", 0) or 0,
        }
    except Exception as e:
        log.debug("Xueqiu fetch failed for %s: %s", code, e)
        return {"post_count": 0, "comment_count": 0}


def collect(codes: list[str]):
    results = []
    for code in codes:
        info = _fetch_one(code)
        results.append({"code": code, "source": "xueqiu", **info})
        time.sleep(random.uniform(0.2, 0.5))

    if results:
        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO sentiment_snapshots(code,source,post_count,comment_count) VALUES(:code,:source,:post_count,:comment_count)",
                results,
            )
    log.info("Collected xueqiu sentiment for %d stocks", len(results))
    return results
