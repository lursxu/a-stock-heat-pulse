import logging, time, random, re, json
import requests
from db import get_conn

log = logging.getLogger(__name__)

_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://guba.eastmoney.com/",
})
_SESSION.trust_env = False


def _fetch_one(code: str) -> dict:
    """Fetch discussion stats from guba page scraping."""
    url = f"https://guba.eastmoney.com/list,{code}.html"
    try:
        resp = _SESSION.get(url, timeout=8)
        m = re.search(r'var\s+article_list\s*=\s*(\{.*?\});', resp.text, re.DOTALL)
        if not m:
            return {"post_count": 0, "comment_count": 0}
        data = json.loads(m.group(1))
        post_count = data.get("count", 0) or 0
        articles = data.get("re", [])
        if not isinstance(articles, list):
            articles = []
        total_clicks = sum((a.get("post_click_count") or 0) for a in articles)
        total_comments = sum((a.get("post_comment_count") or 0) for a in articles)
        return {"post_count": post_count, "comment_count": total_clicks + total_comments}
    except Exception as e:
        log.debug("Guba fetch failed for %s: %s", code, e)
        return {"post_count": 0, "comment_count": 0}


def collect(codes: list[str]):
    results = []
    for code in codes:
        info = _fetch_one(code)
        results.append({"code": code, "source": "guba", **info})
        time.sleep(random.uniform(0.3, 0.6))
    if results:
        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO sentiment_snapshots(code,source,post_count,comment_count) VALUES(:code,:source,:post_count,:comment_count)",
                results,
            )
    log.info("Collected guba sentiment for %d stocks", len(results))
    return results
