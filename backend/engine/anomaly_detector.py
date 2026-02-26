import logging
import numpy as np
from config import get as get_config
from db import get_conn

log = logging.getLogger(__name__)


def _calc_stats(current: float, past: list[float]) -> dict:
    arr = np.array(past, dtype=float)
    mean, std = arr.mean(), arr.std()
    zscore = (current - mean) / std if std > 1e-9 else ((current - mean) / 1e-9 if current > mean else 0.0)

    box_upper = np.percentile(arr, 75)
    box_lower = np.percentile(arr, 25)
    iqr = box_upper - box_lower
    box_cv = (std / mean) if mean > 1e-9 else 999

    breakout = 0.0
    if iqr > 1e-9:
        breakout = max(0, (current - box_upper) / iqr)
    elif current > mean and mean > 1e-9:
        breakout = (current - mean) / mean * 10

    return {"zscore": zscore, "box_cv": box_cv, "box_upper": box_upper, "box_lower": box_lower, "breakout": breakout, "mean": mean, "std": std}


def detect(heat_df) -> list[dict]:
    """
    Detect anomalies by comparing today's trade_heat against
    daily-deduplicated historical trade_heat (one value per day).
    This avoids noise from intraday repeated snapshots.
    """
    if heat_df.empty:
        return []

    cfg = get_config()["detection"]
    threshold = cfg["zscore_threshold"]
    window = cfg["window_size"]
    min_pts = cfg["min_data_points"]

    anomalies = []
    with get_conn() as conn:
        for _, row in heat_df.iterrows():
            code = row["code"]
            current_trade = row.get("trade_heat", row["total_heat"])
            current_total = row["total_heat"]

            # Get daily-deduplicated history: one record per day (latest per day)
            history = conn.execute(
                "SELECT trade_heat, total_heat, DATE(ts) as day "
                "FROM heat_scores WHERE code=? AND id IN "
                "(SELECT MAX(id) FROM heat_scores WHERE code=? GROUP BY DATE(ts)) "
                "ORDER BY day DESC LIMIT ?",
                (code, code, window + 1),
            ).fetchall()

            # Exclude today, keep only past days
            today_day = None
            if history:
                today_day = history[0]["day"]
            past_trade = [h["trade_heat"] for h in history[1:] if h["trade_heat"] is not None]

            if len(past_trade) < min_pts:
                continue

            stats = _calc_stats(current_trade, past_trade)
            zscore = stats["zscore"]

            is_zscore_anomaly = zscore >= threshold
            is_stable_box = stats["box_cv"] < 0.3
            is_breakout = is_stable_box and stats["breakout"] >= 3.0

            # Additional filter: trade_heat must be meaningfully above historical mean
            # This prevents low-heat stocks with tiny fluctuations from triggering
            heat_lift = (current_trade - stats["mean"]) / stats["mean"] if stats["mean"] > 1e-4 else 0
            is_meaningful = heat_lift > 1.0 and current_trade > 0.08  # doubled AND above absolute floor

            # Filter out stocks already in an active box (high historical mean)
            # A stock with mean trade_heat > 0.05 is already "warm", needs stronger signal
            if stats["mean"] > 0.05:
                is_meaningful = is_meaningful and heat_lift > 2.0  # need 3x for warm stocks

            # Update zscore in db
            conn.execute(
                "UPDATE heat_scores SET zscore=? WHERE code=? AND id=(SELECT MAX(id) FROM heat_scores WHERE code=?)",
                (zscore, code, code),
            )

            if (is_zscore_anomaly or is_breakout) and is_meaningful:
                anomalies.append({
                    "code": code,
                    "name": row.get("name", ""),
                    "total_heat": round(current_total, 4),
                    "trade_heat": round(current_trade, 4),
                    "zscore": round(zscore, 2),
                    "change_pct": row.get("change_pct", 0),
                    "volume_ratio": row.get("volume_ratio", 0),
                    "breakout": round(stats["breakout"], 2),
                    "box_cv": round(stats["box_cv"], 4),
                    "box_upper": round(stats["box_upper"], 4),
                    "box_lower": round(stats["box_lower"], 4),
                    "hist_mean": round(stats["mean"], 4),
                    "anomaly_type": "box_breakout" if (is_breakout and not is_zscore_anomaly) else "zscore",
                })

    anomalies.sort(key=lambda x: x["zscore"], reverse=True)
    log.info("Detected %d anomalies", len(anomalies))
    return anomalies
