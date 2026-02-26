import sqlite3, os, threading
from contextlib import contextmanager
from config import get as get_config

_local = threading.local()


def _db_path():
    p = get_config()["data"]["db_path"]
    base = os.path.dirname(__file__)
    full = os.path.join(base, p)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    return full


@contextmanager
def get_conn():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_db_path())
        _local.conn.row_factory = sqlite3.Row
        _local.conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield _local.conn
        _local.conn.commit()
    except Exception:
        _local.conn.rollback()
        raise


def init_db():
    with get_conn() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS stock_basic (
            code TEXT PRIMARY KEY,
            name TEXT,
            industry TEXT,
            market TEXT,
            updated_at DATETIME DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS trade_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT,
            price REAL,
            change_pct REAL,
            volume REAL,
            amount REAL,
            turnover_rate REAL,
            volume_ratio REAL,
            ts DATETIME DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_trade_code_ts ON trade_snapshots(code, ts);

        CREATE TABLE IF NOT EXISTS sentiment_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            source TEXT NOT NULL,
            post_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            ts DATETIME DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_sent_code_ts ON sentiment_snapshots(code, ts);

        CREATE TABLE IF NOT EXISTS heat_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT,
            trade_heat REAL,
            sentiment_heat REAL,
            total_heat REAL,
            zscore REAL,
            ts DATETIME DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_heat_code_ts ON heat_scores(code, ts);

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            name TEXT,
            total_heat REAL,
            zscore REAL,
            change_pct REAL,
            volume_ratio REAL,
            message TEXT,
            ts DATETIME DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(ts);

        CREATE TABLE IF NOT EXISTS job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_name TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT,
            duration_sec REAL,
            ts DATETIME DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_job_logs_ts ON job_logs(ts);
        """)


def cleanup_old_data(days: int = 90):
    with get_conn() as conn:
        for tbl in ("trade_snapshots", "sentiment_snapshots", "heat_scores", "alerts", "job_logs"):
            conn.execute(f"DELETE FROM {tbl} WHERE ts < datetime('now','localtime','-{days} days')")
