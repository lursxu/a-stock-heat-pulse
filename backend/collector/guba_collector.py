import logging, time, random
import requests
from db import get_conn

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://guba.eastmoney.com/",
})


def _fetch_one(code: str) -> dict:
    """Fetch post count for a stock from eastmoney guba API."""
    # eastmoney guba uses 6-digit code with market prefix
    market = "1" if code.startswith("6") else "0"
    url = f"https://guba.eastmoney.com/interface/GetData.aspx?path=newtopic/api&ps=1&p=1&type=0&code={market}{code}"
    try:
        resp = _SESSION.get(url, timeout=5)
        data = resp.json()
        total = data.get("re", [{}])
        post_count = data.get("count", 0) if isinstance(data.get("count"), int) else 0
        comment_count = sum(item.get("rc", 0) for item in (total if isinstance(total, list) else []))
        return {"post_count": post_count, "comment_count": comment_count}
    except Exception as e:
        log.debug("Guba fetch failed for %s: %s", code, e)
        return {"post_count": 0, "comment_count": 0}


def collect(codes: list[str]):
    """Collect guba sentiment for given stock codes."""
    results = []
    for code in codes:
        info = _fetch_one(code)
        results.append({"code": code, "source": "guba", **info})
        time.sleep(random.uniform(0.1, 0.3))

    if results:
        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO sentiment_snapshots(code,source,post_count,comment_count) VALUES(:code,:source,:post_count,:comment_count)",
                results,
            )
    log.info("Collected guba sentiment for %d stocks", len(results))
    return results
