"""
watchlist_service.py

Simple CRUD wrapper around the `watchlist` SQLite table.
"""
import sqlite3
from typing import Any, Dict, List, Optional
from database import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def add_watchlist_item(symbol: str, company_name: str = "", notes: str = "") -> Optional[int]:
    symbol = symbol.strip().upper()
    if not symbol:
        return None
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO watchlist (symbol, company_name, notes) VALUES (?, ?, ?)",
            (symbol, company_name.strip(), notes.strip()),
        )
        conn.commit()
        rid = cur.lastrowid
        conn.close()
        return rid
    except sqlite3.Error:
        return None


def remove_watchlist_item(item_id: int) -> bool:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM watchlist WHERE id = ?", (item_id,))
        conn.commit()
        changed = cur.rowcount > 0
        conn.close()
        return changed
    except sqlite3.Error:
        return False


def get_watchlist() -> List[Dict[str, Any]]:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM watchlist ORDER BY created_at DESC")
        rows = cur.fetchall()
        res = [dict(zip([c[0] for c in cur.description], r)) for r in rows]
        conn.close()
        return res
    except sqlite3.Error:
        return []


def get_watchlist_item(item_id: int) -> Optional[Dict[str, Any]]:
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT * FROM watchlist WHERE id = ?", (item_id,))
        row = cur.fetchone()
        res = dict(zip([c[0] for c in cur.description], row)) if row else None
        conn.close()
        return res
    except sqlite3.Error:
        return None
