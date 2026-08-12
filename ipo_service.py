import sqlite3
import json
from typing import Dict, Any, List, Optional

DB_PATH = "finance.db"

def run_migrations():
    """
    Ensures that the database table exists and has the required schema
    including structured data, risk_level, industry, and confidence columns.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("PRAGMA table_info(drhp_reports);")
        columns = [col[1] for col in cursor.fetchall()]
        
        if columns:
            if "ipo_score" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN ipo_score REAL;")
            if "recommendation" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN recommendation TEXT;")
            if "industry" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN industry TEXT;")
            if "risk_level" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN risk_level TEXT;")
            if "confidence" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN confidence REAL;")
            if "structured_data" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN structured_data TEXT;")
            conn.commit()
        else:
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
            conn.commit()
            
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

# Run automatic migration checks on module import
run_migrations()

def save_drhp_report(
    company_name: str,
    summary: str,
    red_flags: str,
    ipo_score: float,
    recommendation: str,
    industry: str = "Not Specified",
    risk_level: str = "Moderate",
    confidence: float = 75.0,
    structured_data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Saves a processed DRHP report with AI analysis results to the database.
    Supports both standard summary strings and full structured analysis objects.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        json_str = json.dumps(structured_data) if structured_data else None
        
        cursor.execute(
            """
            INSERT INTO drhp_reports (
                company_name, summary, red_flags, ipo_score, recommendation,
                industry, risk_level, confidence, structured_data
            ) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                company_name, summary, red_flags, ipo_score, recommendation,
                industry, risk_level, confidence, json_str
            )
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving DRHP report: {e}")
        return False

def get_all_reports() -> List[Dict[str, Any]]:
    """
    Retrieves all stored DRHP reports from the SQLite database.
    Automatically parses structured_data JSON if available.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, company_name, summary, red_flags, ipo_score, recommendation, 
                   industry, risk_level, confidence, structured_data, created_at 
            FROM drhp_reports 
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()
        reports = []
        for row in rows:
            rec = dict(row)
            # Parse JSON string if present
            s_data = rec.get("structured_data")
            if s_data:
                try:
                    rec["parsed_structured_data"] = json.loads(s_data)
                except Exception:
                    rec["parsed_structured_data"] = None
            else:
                rec["parsed_structured_data"] = None
            reports.append(rec)
        conn.close()
        return reports
    except Exception as e:
        print(f"Error fetching DRHP reports: {e}")
        return []