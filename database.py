import sqlite3

conn = sqlite3.connect("finance.db")
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()
conn.close()
