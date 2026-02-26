import logging
import pandas as pd
import numpy as np
from config import get as get_config
from db import get_conn

log = logging.getLogger(__name__)


def _normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize, handle edge case where max==min."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(0.0, index=series.index)
    return (series - mn) / (mx - mn)


def calc_trade_heat(df: pd.DataFrame) -> pd.Series:
    w = get_config()["heat_weights"]
    vr = _normalize(df["volume_ratio"].fillna(0)) * w["volume_ratio"]
    tr = _normalize(df["turnover_rate"].fillna(0)) * w["turnover_rate"]
    amt = _normalize(df["amount"].fillna(0)) * w["amount_change"]
    return vr + tr + amt


def calc_sentiment_heat(codes: list[str]) -> dict[str, float]:
    """Calculate sentiment heat from latest snapshot for given codes."""
    if not codes:
        return {}
    w = get_config()["heat_weights"]
    placeholders = ",".join("?" * len(codes))
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT code, source, post_count, comment_count FROM sentiment_snapshots "
            f"WHERE code IN ({placeholders}) AND ts >= datetime('now','localtime','-10 minutes')",
            codes,
        ).fetchall()

    if not rows:
        return {}

    data = {}
    for r in rows:
        code = r["code"]
        if code not in data:
            data[code] = {"guba": 0, "ths_hot": 0}
        total = (r["post_count"] or 0) + (r["comment_count"] or 0)
        src = r["source"]
        if src in ("guba",):
            data[code]["guba"] = total
        else:
            data[code]["ths_hot"] = total

    # Normalize across all codes
    guba_vals = np.array([v["guba"] for v in data.values()], dtype=float)
    xq_vals = np.array([v["ths_hot"] for v in data.values()], dtype=float)

    def _norm(arr):
        mn, mx = arr.min(), arr.max()
        return (arr - mn) / (mx - mn) if mx > mn else np.zeros_like(arr)

    guba_n = _norm(guba_vals)
    xq_n = _norm(xq_vals)

    result = {}
    for i, code in enumerate(data.keys()):
        result[code] = guba_n[i] * w["guba_weight"] + xq_n[i] * w["xueqiu_weight"]
    return result


def calculate(trade_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate combined heat scores and store them."""
    if trade_df.empty:
        return pd.DataFrame()

    cfg = get_config()["heat_weights"]
    trade_df = trade_df.copy()
    trade_df["trade_heat"] = calc_trade_heat(trade_df)

    codes = trade_df["code"].tolist()
    sent = calc_sentiment_heat(codes)

    trade_df["sentiment_heat"] = trade_df["code"].map(sent).fillna(0)
    trade_df["total_heat"] = (
        trade_df["trade_heat"] * cfg["trade"]
        + trade_df["sentiment_heat"] * cfg["sentiment"]
    )

    # Store heat scores
    records = trade_df[["code", "name", "trade_heat", "sentiment_heat", "total_heat"]].copy()
    records["zscore"] = 0.0  # will be filled by anomaly detector
    rows = records.to_dict("records")
    if rows:
        with get_conn() as conn:
            conn.executemany(
                "INSERT INTO heat_scores(code,name,trade_heat,sentiment_heat,total_heat,zscore) "
                "VALUES(:code,:name,:trade_heat,:sentiment_heat,:total_heat,:zscore)",
                rows,
            )
    log.info("Calculated heat scores for %d stocks", len(rows))
    return trade_df
