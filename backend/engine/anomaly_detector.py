import logging
import numpy as np
from config import get as get_config
from db import get_conn

log = logging.getLogger(__name__)


def detect(heat_df) -> list[dict]:
    """Detect anomalies using sliding window Z-Score on heat_scores history."""
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

            # Need at least min_pts historical points (excluding current)
            past = [h["total_heat"] for h in history[1:]] if len(history) > 1 else []
            if len(past) < min_pts:
                continue

            arr = np.array(past, dtype=float)
            mean, std = arr.mean(), arr.std()
            if std < 1e-9:
                continue

            zscore = (current - mean) / std

            # Update zscore in db
            conn.execute(
                "UPDATE heat_scores SET zscore=? WHERE code=? AND id=(SELECT MAX(id) FROM heat_scores WHERE code=?)",
                (zscore, code, code),
            )

            if zscore >= threshold:
                anomalies.append({
                    "code": code,
                    "name": row.get("name", ""),
                    "total_heat": round(current, 4),
                    "zscore": round(zscore, 2),
                    "change_pct": row.get("change_pct", 0),
                    "volume_ratio": row.get("volume_ratio", 0),
                })

    anomalies.sort(key=lambda x: x["zscore"], reverse=True)
    log.info("Detected %d anomalies", len(anomalies))
    return anomalies
