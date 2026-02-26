import logging
import numpy as np
from config import get as get_config
from db import get_conn

log = logging.getLogger(__name__)


def detect(heat_df) -> list[dict]:
    """
    Detect anomalies using:
    1. Z-Score on sliding window
    2. Box range (箱体) identification + breakout detection
    A stock is anomalous if its heat was stable (low volatility) then suddenly spikes.
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
            current = row["total_heat"]

            history = conn.execute(
                "SELECT total_heat FROM heat_scores WHERE code=? ORDER BY ts DESC LIMIT ?",
                (code, window + 1),
            ).fetchall()

            past = [h["total_heat"] for h in history[1:]] if len(history) > 1 else []
            if len(past) < min_pts:
                continue

            arr = np.array(past, dtype=float)
            mean, std = arr.mean(), arr.std()
            if std < 1e-9:
                zscore = (current - mean) / 1e-9 if current > mean else 0
            else:
                zscore = (current - mean) / std

            # Box range analysis: check if recent history was stable then current breaks out
            box_upper = np.percentile(arr, 75)
            box_lower = np.percentile(arr, 25)
            iqr = box_upper - box_lower
            box_cv = (std / mean) if mean > 1e-9 else 999  # coefficient of variation

            # Breakout score: how far above the box upper bound
            breakout = 0
            if iqr > 1e-9:
                breakout = max(0, (current - box_upper) / iqr)
            elif current > mean and mean > 1e-9:
                breakout = (current - mean) / mean * 10

            # Combined anomaly: stable box + sudden spike
            # A low CV means the stock was in a tight range (箱体平稳)
            is_stable_box = box_cv < 0.5  # relatively stable history
            is_zscore_anomaly = zscore >= threshold
            is_breakout = breakout >= 1.5  # 1.5x IQR above Q3

            is_anomaly = is_zscore_anomaly or (is_stable_box and is_breakout)

            # Update zscore in db
            conn.execute(
                "UPDATE heat_scores SET zscore=? WHERE code=? AND id=(SELECT MAX(id) FROM heat_scores WHERE code=?)",
                (zscore, code, code),
            )

            if is_anomaly:
                anomalies.append({
                    "code": code,
                    "name": row.get("name", ""),
                    "total_heat": round(current, 4),
                    "zscore": round(zscore, 2),
                    "change_pct": row.get("change_pct", 0),
                    "volume_ratio": row.get("volume_ratio", 0),
                    "breakout": round(breakout, 2),
                    "box_cv": round(box_cv, 4),
                    "box_upper": round(box_upper, 4),
                    "box_lower": round(box_lower, 4),
                    "anomaly_type": "zscore" if is_zscore_anomaly else "box_breakout",
                })

    anomalies.sort(key=lambda x: x["zscore"], reverse=True)
    log.info("Detected %d anomalies", len(anomalies))
    return anomalies
