"""
alert_service.py

Manage simple alert definitions persisted in the `alerts` SQLite table.
Supported `condition` strings: 'gt' (price greater than), 'lt' (price less than), 'pct_up' (percent up), 'pct_down'.
"""
import sqlite3
from typing import Any, Dict, List, Optional
from database import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def add_alert(name: str, symbol: str, condition: str, threshold: float, active: bool = True) -> Optional[int]:
    symbol = symbol.strip().upper()
    if condition not in ("gt", "lt", "pct_up", "pct_down"):
        return None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO alerts (name, symbol, condition, threshold, active) VALUES (?, ?, ?, ?, ?)",
            (name.strip(), symbol, condition, threshold, 1 if active else 0),
        )
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid
    except sqlite3.Error:
        return None


def get_alerts() -> List[Dict[str, Any]]:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM alerts ORDER BY created_at DESC")
        rows = cur.fetchall()
        res = [dict(zip([c[0] for c in cur.description], r)) for r in rows]
        conn.close()
        return res
    except sqlite3.Error:
        return []


def update_alert(alert_id: int, name: str, symbol: str, condition: str, threshold: float, active: bool) -> bool:
    symbol = symbol.strip().upper()
    if condition not in ("gt", "lt", "pct_up", "pct_down"):
        return False
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE alerts SET name = ?, symbol = ?, condition = ?, threshold = ?, active = ? WHERE id = ?",
            (name.strip(), symbol, condition, threshold, 1 if active else 0, alert_id),
        )
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed
    except sqlite3.Error:
        return False


def remove_alert(alert_id: int) -> bool:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM alerts WHERE id = ?", (alert_id,))
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed
    except sqlite3.Error:
        return False
