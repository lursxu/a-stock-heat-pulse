import logging
import akshare as ak
import pandas as pd
from db import get_conn

log = logging.getLogger(__name__)

COLUMNS_MAP = {
    "代码": "code", "名称": "name", "最新价": "price",
    "涨跌幅": "change_pct", "成交量": "volume", "成交额": "amount",
    "换手率": "turnover_rate", "量比": "volume_ratio",
}


def collect() -> pd.DataFrame:
    """Fetch all A-share realtime quotes and store snapshot."""
    try:
        df = ak.stock_zh_a_spot_em()
    except Exception as e:
        log.error("Failed to fetch trade data: %s", e)
        return pd.DataFrame()

    df = df.rename(columns=COLUMNS_MAP)
    cols = list(COLUMNS_MAP.values())
    df = df[[c for c in cols if c in df.columns]].copy()

    for c in ("price", "change_pct", "volume", "amount", "turnover_rate", "volume_ratio"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["code"])

    rows = df.to_dict("records")
    if rows:
        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO trade_snapshots(code,name,price,change_pct,volume,amount,turnover_rate,volume_ratio) "
                "VALUES(:code,:name,:price,:change_pct,:volume,:amount,:turnover_rate,:volume_ratio)",
                rows,
            )
    log.info("Collected %d trade records", len(rows))
    return df
