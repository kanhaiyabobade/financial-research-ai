import sqlite3
from typing import Dict, Any, List

DB_PATH = "finance.db"

def run_migrations():
    """
    Ensures that the database table exists and has the required schema
    including ipo_score and recommendation columns.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verify the table is configured with all columns
        cursor.execute("PRAGMA table_info(drhp_reports);")
        columns = [col[1] for col in cursor.fetchall()]
        
        if columns:
            # Table exists, check for missing columns
            if "ipo_score" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN ipo_score REAL;")
            if "recommendation" not in columns:
                cursor.execute("ALTER TABLE drhp_reports ADD COLUMN recommendation TEXT;")
            conn.commit()
        else:
            # Table doesn't exist, create it with all columns
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS drhp_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                summary TEXT,
                red_flags TEXT,
                ipo_score REAL,
                recommendation TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
            
        conn.close()
    except Exception as e:
        print(f"Migration error: {e}")

# Run automatic migration checks on module import
run_migrations()

def save_drhp_report(company_name: str, summary: str, red_flags: str, ipo_score: float, recommendation: str) -> bool:
    """
    Saves a processed DRHP report with AI analysis results to the database.
    
    Args:
        company_name (str): The name of the IPO company.
        summary (str): The summary text of the DRHP.
        red_flags (str): Identified red flags.
        ipo_score (float): The investment score between 0 and 100.
        recommendation (str): Final investment recommendation (Invest/Watch/Avoid).
        
    Returns:
        bool: True if saving succeeded, False otherwise.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO drhp_reports (company_name, summary, red_flags, ipo_score, recommendation) 
            VALUES (?, ?, ?, ?, ?)
            """,
            (company_name, summary, red_flags, ipo_score, recommendation)
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
    
    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing the records.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, company_name, summary, red_flags, ipo_score, recommendation, created_at 
            FROM drhp_reports 
            ORDER BY created_at DESC
            """
        )
        rows = cursor.fetchall()
        reports = [dict(row) for row in rows]
        conn.close()
        return reports
    except Exception as e:
        print(f"Error fetching DRHP reports: {e}")
        return []