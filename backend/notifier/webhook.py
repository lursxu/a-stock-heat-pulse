import logging, json
import requests
from config import get as get_config
from db import get_conn

log = logging.getLogger(__name__)


def _is_dedup(code: str) -> bool:
    minutes = get_config()["alert"]["dedup_minutes"]
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM alerts WHERE code=? AND ts >= datetime('now','localtime',? || ' minutes')",
            (code, f"-{minutes}"),
        ).fetchone()
    return row is not None


def _format_message(items: list[dict]) -> str:
    lines = ["🔥 A股热度异常告警\n"]
    for i, it in enumerate(items[:10], 1):
        lines.append(
            f"{i}. {it['name']}({it['code']}) "
            f"热度:{it['total_heat']:.3f} Z:{it['zscore']:.1f} "
            f"涨跌:{it.get('change_pct',0):.2f}% 量比:{it.get('volume_ratio',0):.2f}"
        )
    return "\n".join(lines)


def _send_feishu(url: str, text: str):
    payload = {"msg_type": "text", "content": {"text": text}}
    requests.post(url, json=payload, timeout=10)


def _send_dingtalk(url: str, text: str):
    payload = {"msgtype": "text", "text": {"content": text}}
    requests.post(url, json=payload, timeout=10)


def notify(anomalies: list[dict]):
    if not anomalies:
        return

    cfg = get_config()["alert"]

    # Filter duplicates
    filtered = [a for a in anomalies if not _is_dedup(a["code"])]
    if not filtered:
        log.info("All anomalies deduped, skipping")
        return

    # Always store alerts
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO alerts(code,name,total_heat,zscore,change_pct,volume_ratio,message) "
            "VALUES(:code,:name,:total_heat,:zscore,:change_pct,:volume_ratio,:message)",
            [{**a, "message": ""} for a in filtered],
        )
    log.info("Stored %d alerts", len(filtered))

    # Send webhook if configured
    url = cfg.get("webhook_url", "")
    if not url:
        return
    msg = _format_message(filtered)
    try:
        if cfg["webhook_type"] == "feishu":
            _send_feishu(url, msg)
        else:
            _send_dingtalk(url, msg)
        log.info("Sent webhook for %d stocks", len(filtered))
    except Exception as e:
        log.error("Failed to send webhook: %s", e)
