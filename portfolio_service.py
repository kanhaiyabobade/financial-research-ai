"""
portfolio_service.py

Business logic layer for the Portfolio Intelligence module.
Handles all CRUD operations on the portfolio_holdings SQLite table.
No external API calls — purely local data persistence.
"""

import sqlite3
from typing import Any, Dict, List, Optional
from database import DB_PATH


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_to_dict(cursor: sqlite3.Cursor, row: sqlite3.Row) -> Dict[str, Any]:
    """Convert a sqlite3.Row into a plain Python dict."""
    return dict(zip([col[0] for col in cursor.description], row))


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def add_holding(
    symbol: str,
    quantity: float,
    avg_buy_price: float,
    company_name: str = "",
    notes: str = "",
) -> Optional[int]:
    """
    Insert a new holding into portfolio_holdings.

    Returns the new row ID on success, or None on failure.
    """
    symbol = symbol.strip().upper()
    if not symbol or quantity <= 0 or avg_buy_price < 0:
        return None

    try:
        conn = _get_conn()
        cursor = conn.cursor()
        # Also populate legacy 'buy_price' column (NOT NULL from original schema)
        cursor.execute(
            """
            INSERT INTO portfolio_holdings (symbol, company_name, quantity, buy_price, avg_buy_price, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol, company_name.strip(), quantity, avg_buy_price, avg_buy_price, notes.strip()),
        )
        conn.commit()
        new_id = cursor.lastrowid
        conn.close()
        return new_id
    except sqlite3.Error:
        return None


def get_all_holdings() -> List[Dict[str, Any]]:
    """
    Return all holdings ordered by symbol, newest first within each symbol.
    """
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM portfolio_holdings
            ORDER BY symbol ASC, created_at DESC
            """
        )
        rows = cursor.fetchall()
        result = [_row_to_dict(cursor, r) for r in rows]
        conn.close()
        return result
    except sqlite3.Error:
        return []


def get_holding_by_id(holding_id: int) -> Optional[Dict[str, Any]]:
    """Return a single holding by primary-key ID, or None if not found."""
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM portfolio_holdings WHERE id = ?", (holding_id,))
        row = cursor.fetchone()
        result = _row_to_dict(cursor, row) if row else None
        conn.close()
        return result
    except sqlite3.Error:
        return None


def update_holding(
    holding_id: int,
    symbol: str,
    quantity: float,
    avg_buy_price: float,
    company_name: str = "",
    notes: str = "",
) -> bool:
    """
    Update an existing holding by ID.

    Returns True on success, False on failure.
    """
    symbol = symbol.strip().upper()
    if not symbol or quantity <= 0 or avg_buy_price < 0:
        return False

    try:
        conn = _get_conn()
        cursor = conn.cursor()
        # Keep legacy buy_price in sync with avg_buy_price
        cursor.execute(
            """
            UPDATE portfolio_holdings
            SET symbol = ?, company_name = ?, quantity = ?, buy_price = ?,
                avg_buy_price = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (symbol, company_name.strip(), quantity, avg_buy_price, avg_buy_price, notes.strip(), holding_id),
        )
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed
    except sqlite3.Error:
        return False


def delete_holding(holding_id: int) -> bool:
    """
    Delete a holding by ID.

    Returns True on success, False on failure.
    """
    try:
        conn = _get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM portfolio_holdings WHERE id = ?", (holding_id,))
        conn.commit()
        changed = cursor.rowcount > 0
        conn.close()
        return changed
    except sqlite3.Error:
        return False


def get_portfolio_market_data(symbols: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Batch-fetch current market data for a list of symbols using yfinance.

    Returns a dict keyed by symbol (uppercased). Each value:
        {
          "current_price": float | None,
          "prev_close":    float | None,
          "company_name":  str,
          "currency":      str,
          "error":         str | None,   # set when ticker lookup failed
        }

    Never raises — bad tickers get an entry with current_price=None and an error message.
    """
    import yfinance as yf

    result: Dict[str, Dict[str, Any]] = {}

    for sym in symbols:
        sym_upper = sym.strip().upper()
        try:
            ticker = yf.Ticker(sym_upper)
            info = ticker.info or {}

            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
            company_name = info.get("longName") or info.get("shortName") or sym_upper
            currency = info.get("currency") or "INR"

            if current_price is None and prev_close is None:
                # Ticker may be invalid or data unavailable
                result[sym_upper] = {
                    "current_price": None,
                    "prev_close": None,
                    "company_name": sym_upper,
                    "currency": currency,
                    "sector": info.get("sector") or None,
                    "error": f"No price data returned for '{sym_upper}'. Check ticker symbol.",
                }
            else:
                result[sym_upper] = {
                    "current_price": current_price,
                    "prev_close": prev_close,
                    "company_name": company_name,
                    "currency": currency,
                    "sector": info.get("sector") or None,
                    "error": None,
                }
        except Exception as exc:
            result[sym_upper] = {
                "current_price": None,
                "prev_close": None,
                "company_name": sym_upper,
                "currency": "INR",
                "error": str(exc),
            }

    return result


if __name__ == "__main__":
    # Smoke-test
    from database import init_database
    init_database()

    rid = add_holding("RELIANCE.NS", 10, 2800.0, "Reliance Industries Ltd", "Test holding")
    assert rid is not None, "add_holding failed"

    holdings = get_all_holdings()
    assert any(h["id"] == rid for h in holdings), "get_all_holdings failed"

    ok = update_holding(rid, "RELIANCE.NS", 15, 2750.0, "Reliance Industries Ltd", "Averaged down")
    assert ok, "update_holding failed"

    ok = delete_holding(rid)
    assert ok, "delete_holding failed"

    holdings_after = get_all_holdings()
    assert not any(h["id"] == rid for h in holdings_after), "delete_holding did not remove row"

    print("✓ All portfolio_service smoke tests passed.")
