import sqlite3
import json
from typing import Dict, Any, List, Optional
from database import init_database

DB_PATH = "finance.db"

# Ensure database is initialized on import
init_database()

def save_drhp_report(
    company_name: str,
    summary: str,
    red_flags: str,
    ipo_score: Optional[float] = None,
    recommendation: Optional[str] = "Analysis unavailable",
    industry: str = "Not Specified",
    risk_level: str = "N/A",
    confidence: Optional[float] = None,
    structured_data: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Saves a processed DRHP report with AI analysis results to the database safely.
    Allows NULL/None values for ipo_score, confidence, etc.
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
                company_name or "Unknown Entity",
                summary or "Summary unavailable",
                red_flags or "[]",
                ipo_score,
                recommendation or "Analysis unavailable",
                industry or "Not Specified",
                risk_level or "N/A",
                confidence,
                json_str
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
    Retrieves stored DRHP reports from SQLite database.
    Handles NULL fields safely without crashing.
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