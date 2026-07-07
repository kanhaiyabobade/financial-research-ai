import sqlite3
import os

db_file = "finance.db"

if not os.path.exists(db_file):
    print(f"Error: {db_file} does not exist. Run database.py first to create it.")
else:
    print(f"Found database file: {db_file}")
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Query all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    print("\n--- Database Tables & Schema ---")
    if not tables:
        print("No tables found in the database.")
    else:
        for table in tables:
            table_name = table[0]
            if table_name == "sqlite_sequence":
                continue
            print(f"\nTable: {table_name}")
            
            # Query column details for each table
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            for col in columns:
                # col is a tuple: (cid, name, type, notnull, dflt_value, pk)
                col_name = col[1]
                col_type = col[2]
                is_pk = " (Primary Key)" if col[5] else ""
                print(f"  - {col_name}: {col_type}{is_pk}")
                
    conn.close()
