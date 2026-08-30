import sqlite3
import os

DB_PATH = "finance.db"

def init_database():
    """
    Initializes SQLite tables and applies non-destructive schema migrations.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stocks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        price REAL,
        market_cap REAL,
        pe_ratio REAL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS news (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_symbol TEXT,
        headline TEXT,
        sentiment TEXT,
        published_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ipos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        ipo_score REAL,
        risk_score REAL,
        valuation_score REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS drhp_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        summary TEXT,
        red_flags TEXT,
        ipo_score REAL,
        recommendation TEXT,
        industry TEXT,
        risk_level TEXT,
        confidence REAL,
        structured_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Non-destructive migrations for existing drhp_reports database table
    cursor.execute("PRAGMA table_info(drhp_reports);")
    columns = [col[1] for col in cursor.fetchall()]

    migrations = {
        "ipo_score": "ALTER TABLE drhp_reports ADD COLUMN ipo_score REAL;",
        "recommendation": "ALTER TABLE drhp_reports ADD COLUMN recommendation TEXT;",
        "industry": "ALTER TABLE drhp_reports ADD COLUMN industry TEXT;",
        "risk_level": "ALTER TABLE drhp_reports ADD COLUMN risk_level TEXT;",
        "confidence": "ALTER TABLE drhp_reports ADD COLUMN confidence REAL;",
        "structured_data": "ALTER TABLE drhp_reports ADD COLUMN structured_data TEXT;"
    }

    for col_name, alter_stmt in migrations.items():
        if col_name not in columns:
            cursor.execute(alter_stmt)
            print(f"Added missing column '{col_name}' to drhp_reports table.")

    conn.commit()
    conn.close()
    print("Database initialized successfully.")

if __name__ == "__main__":
    init_database()
