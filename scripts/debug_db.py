import sqlite3
import pandas as pd
import os

# DB Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "cffex_basis.db")

print(f"Checking DB at: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# 1. Check Table Exists
c.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = c.fetchall()
print(f"Tables: {tables}")

if tables:
    # 2. Check Row Count
    c.execute("SELECT count(*) FROM futures_daily")
    count = c.fetchone()[0]
    print(f"Total Rows: {count}")
    
    # 3. Sample Data (IH2603)
    print("\nSample Data for IH2603:")
    df = pd.read_sql_query("SELECT * FROM futures_daily WHERE symbol LIKE '%IH2603%' LIMIT 5", conn)
    print(df)
    
    # 4. Check ANY IH Contract
    print("\nSample Data for ANY IH Contract:")
    df_any = pd.read_sql_query("SELECT * FROM futures_daily WHERE symbol LIKE 'IH%' LIMIT 5", conn)
    print(df_any)

conn.close()
